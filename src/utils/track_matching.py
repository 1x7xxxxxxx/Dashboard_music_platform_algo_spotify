"""Cross-platform track title matching + release-date reference.

Type: Utility
Uses: PostgresHandler (caller-provided — never opens its own connection)
Depends on: s4a_songs_global (source), track_release_reference (target)
Persists in: track_release_reference

The same track is spelled differently on each platform:
    S4A    "Je ne parle pas très bien le français - Remix"
    Apple  "Je ne parle pas très bien le français (Remix)"
    S4A    "Ca te dérange..."   Apple  "Ça te dérange..."   (accent)

`normalize_track_title` collapses these to a single match_key (accents stripped,
remix/original markers unified) so platform-local names can join to the canonical
release date held in `track_release_reference`. Remix and original keep DISTINCT
keys — they have distinct release dates.
"""
import logging
import re
import unicodedata
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Characters S4A replaces with '_' in export filenames (Windows-reserved set).
# s4a_song_timeline / ml_song_predictions are filename-derived (so they carry
# '_'), while CSV/API tables (s4a_songs_global, tracks, track_popularity_history,
# campaign_track_mapping) keep the real chars. canonical_song() bridges the two
# for EXACT per-track joins — unlike normalize_track_title(), it preserves accents
# and remix/original markers, so distinct tracks stay distinct.
_FS_INVALID_CHARS = r'<>:"/\|?*'
_FS_INVALID_TO = '_' * len(_FS_INVALID_CHARS)


def canonical_song(name: str) -> str:
    """Map a title to the filename-derived form (S4A-invalid chars -> '_')."""
    if not name:
        return ''
    return ''.join('_' if c in _FS_INVALID_CHARS else c for c in str(name))


def canonical_song_sql(col: str) -> str:
    """SQL expression mirroring canonical_song(). `col` must be a trusted identifier
    (a column name from our own code), never user input."""
    return f"translate({col}, '{_FS_INVALID_CHARS}', '{_FS_INVALID_TO}')"


def _strip_accents(text: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFKD', text)
        if not unicodedata.combining(c)
    )


# ── Les MARQUEURS DE VERSION ──────────────────────────────────────────────────
#
# Jusqu'au 2026-09-06, `remix` était le SEUL marqueur reconnu. Tous les autres
# devenaient des mots ordinaires du titre, puis étaient absorbés par la règle
# d'inclusion de `title_similarity`, qui rend 0,90 — au-dessus du seuil
# d'auto-acceptation de 0,80. Mesuré ce jour-là, chacun à 0,90 alors qu'il s'agit
# d'une sortie DIFFÉRENTE, avec sa propre date : (Radio Edit), (Extended Mix),
# (Sped Up), (Live), (Instrumental), - VIP, II, Pt. 2.
#
# Le secteur le dit dans son propre modèle : DDEX sépare **Title** et **Version
# Title**, et chaque version — remix, radio edit, live — porte son PROPRE ISRC. Nos
# propres relevés de distributeur le confirment : `imusician_sales_detail` porte une
# colonne `track_version` dont les valeurs réelles sont « Original » et « Remix ».
#
# `original` est délibérément absent : l'original EST le titre de base, et c'est le
# comportement actuel qu'il faut préserver — les clés de `track_release_reference`
# construites depuis « … - Original » ne portent aucun marqueur.
_VERSION_VOCAB: tuple[tuple[str, str], ...] = (
    # (marqueur canonique, motif) — les formes les plus longues d'abord, sinon
    # « radio edit » serait capté par « edit » et perdrait sa spécificité.
    ('radio_edit', r'radio\s+edit'),
    ('extended', r'extended(?:\s+(?:mix|version))?'),
    ('club', r'club\s+mix'),
    ('sped_up', r'sped\s+up'),
    ('slowed', r'slowed(?:\s*\+?\s*reverb)?'),
    ('part', r'(?:part|pt)\s*\.?\s*(?:\d+|[ivx]+)\b'),
    # `remix\w*` couvre « remixed » et « remixes ». La forme à tiret l'exigeait avec
    # une frontière de mot (`remix\b`), donc « - Remixed by Bob » n'était PAS reconnu :
    # le titre restait « base » face à un « remix », les statuts divergeaient, et le
    # score tombait à 0,0 — aucun candidat, échec silencieux.
    ('remix', r'remix\w*'),
    ('rework', r'rework\w*'),
    ('instrumental', r'instrumental'),
    ('acoustic', r'acoustic\w*'),
    ('dub', r'dub(?:\s+mix)?'),
    ('vip', r'vip'),
    ('edit', r'edit'),
    ('live', r'live'),
    ('demo', r'demo'),
    ('cover', r'cover'),
)

# « original » et « original mix » désignent le titre de base : reconnus pour être
# RETIRÉS, jamais pour produire un marqueur.
_NEUTRAL_VERSIONS = r'original(?:\s+mix)?'

# Un suffixe après tiret n'est un marqueur de version que s'il est COURT et que le
# marqueur en occupe la fin. « - Radio Edit », « - Bob Remix », « - Sped Up » : oui.
# « - Live Your Life » : non — c'est un titre qui commence par un mot du vocabulaire,
# et le prendre pour une version rendrait ce morceau introuvable.
_DASH_SUFFIX_MAX_WORDS = 3


def _scan_markers(segment: str) -> set:
    """Les marqueurs de version présents dans un segment déjà normalisé."""
    found = set()
    for tag, pattern in _VERSION_VOCAB:
        if re.search(rf'\b(?:{pattern})', segment):
            found.add(tag)
    return found


def split_version(name: str) -> tuple[str, frozenset]:
    """(titre de base, marqueurs de version) — la lecture structurée d'un titre.

    Les marqueurs sont cherchés là où les distributeurs les écrivent, et nulle part
    ailleurs : dans un groupe entre parenthèses ou crochets, et dans un suffixe court
    après tiret. Spotify écrit « Titre - Remix », Apple écrit « Titre (Remix) », et
    SoundCloud écrit « TITRE (REMIX) Free Download » — d'où le groupe entre
    parenthèses reconnu où qu'il soit, et pas seulement en fin de titre.

    Chercher un marqueur n'importe où dans le titre serait une erreur : « Live Your
    Life » deviendrait une version live de « Your Life ».
    """
    if not name:
        return '', frozenset()
    raw = _strip_accents(str(name)).lower().strip()

    tags: set = set()
    for group in re.findall(r'[\(\[]([^\)\]]*)[\]\)]', raw):
        tags |= _scan_markers(group)

    # Suffixe après le DERNIER tiret entouré d'espaces.
    parts = re.split(r'\s+-\s+', raw)
    if len(parts) > 1:
        suffix = re.sub(r'[\(\[][^\)\]]*[\]\)]', ' ', parts[-1])
        words = suffix.split()
        if 0 < len(words) <= _DASH_SUFFIX_MAX_WORDS:
            for tag, pattern in _VERSION_VOCAB:
                if re.search(rf'\b(?:{pattern})\s*$', suffix.strip()):
                    tags.add(tag)

    # Le titre de base : on retire les marqueurs ET les mentions neutres.
    base = raw
    for _tag, pattern in _VERSION_VOCAB:
        base = re.sub(rf'\b(?:{pattern})', ' ', base)
    base = re.sub(rf'\b(?:{_NEUTRAL_VERSIONS})', ' ', base)
    base = re.sub(r'[^a-z0-9]+', ' ', base).strip()
    base = re.sub(r'\s+', ' ', base)
    return base, frozenset(tags)


def normalize_track_title(name: str) -> str:
    """Return a canonical match key for a track title across platforms.

    Façade sur `split_version`, conservée telle quelle : c'est elle qui produit les
    `match_key` de `track_release_reference`, et une clé qui change cesse de joindre
    les lignes déjà écrites. Pour un remix elle rend « base remix », exactement
    comme avant ; les autres marqueurs n'existaient pas, donc aucune clé existante
    ne bouge.
    """
    base, tags = split_version(name)
    if not base and not tags:
        return ''
    return ' '.join([base] + sorted(t.replace('_', '') for t in tags)) if tags else base


def track_title_matches(query: str, candidate: str) -> bool:
    """True if `candidate` (a platform title) refers to the same track as `query`
    (the S4A song), tolerant to cross-platform noise.

    Stratégie : lire chaque titre en (base, marqueurs de version), refuser dès que
    les marqueurs divergent, puis accepter sur l'égalité OU l'inclusion des bases —
    ce qui absorbe le préfixe d'artiste (« 1x7xxxxxxx - … ») et les suffixes
    (« (free download) ») que la normalisation laisse passer.

    La règle sur les marqueurs s'appliquait au seul « remix » jusqu'au 2026-09-06 ;
    elle vaut désormais pour toute la famille — un radio edit, un live et un
    instrumental sont trois sorties distinctes, avec trois dates.
    """
    qb, qt = split_version(query)
    cb, ct = split_version(candidate)
    if not qb or not cb:
        return False
    if qt != ct:
        return False
    return qb == cb or qb in cb or cb in qb


def rebuild_release_reference(db, artist_id: int) -> int:
    """Rebuild track_release_reference for one artist from s4a_songs_global.

    Reads the authoritative S4A release dates, normalizes each song name to a
    match_key, keeps the earliest release_date per key (true original release),
    and upserts. Returns the number of reference rows written. Raises on DB error
    (caller decides how to surface it).
    """
    rows = db.fetch_query(
        "SELECT song, MIN(release_date) AS release_date "
        "FROM s4a_songs_global "
        "WHERE artist_id = %s AND release_date IS NOT NULL "
        "GROUP BY song",
        (artist_id,),
    )

    best: dict[str, tuple[str, object, str]] = {}
    for song, release_date in (rows or []):
        key = normalize_track_title(song)
        if not key:
            continue
        if key not in best or (release_date and best[key][1] and release_date < best[key][1]):
            best[key] = (song, release_date, 's4a_songs_global')

    # ── Le relevé du DISTRIBUTEUR complète l'export Spotify ───────────────────
    #
    # Mesuré le 2026-09-06 sur un catalogue réel : l'export S4A « 12 mois » portait
    # 10 morceaux, le relevé iMusician en portait 12. « Bô bun mon bon monsieur » et
    # « Feet First » sont de VRAIES sorties, avec leur ISRC — invisibles ici parce
    # qu'un export sur douze mois ne contient que ce qui a été écouté sur douze
    # mois. 17 % du catalogue manquait à la référence, donc aucun titre de
    # plateforme ne pouvait s'y rattacher : ils étaient traités comme des intrus.
    #
    # Le relevé est une meilleure source SUR UN POINT et une moins bonne sur un
    # autre : il connaît le catalogue complet et l'ISRC, mais pas la date de
    # sortie — il ne connaît que des mois de vente. S4A garde donc la main sur la
    # date ; le distributeur n'AJOUTE que ce que S4A ignore.
    #
    # `track_version` est le champ Version de DDEX, la même notion que nos marqueurs
    # de version : on le concatène au titre pour que « Remix » produise bien la clé
    # « … remix » et non un doublon du titre de base.
    try:
        dist = db.fetch_query(
            "SELECT DISTINCT track_title, track_version FROM imusician_sales_detail "
            "WHERE artist_id = %s AND track_title IS NOT NULL AND track_title <> ''",
            (artist_id,),
        )
    except Exception as exc:  # noqa: BLE001 — une source d'appoint ne casse pas le socle
        logger.warning("release reference: distributor statement unreadable (%s)", exc)
        dist = []

    for track_title, track_version in (dist or []):
        label = f"{track_title} - {track_version}" if track_version else track_title
        key = normalize_track_title(label)
        if not key or key in best:
            continue          # S4A a déjà ce morceau, et il porte la date de sortie
        best[key] = (label, None, 'imusician_sales_detail')

    if not best:
        return 0

    now = datetime.now(timezone.utc)
    data = [
        {
            'artist_id': artist_id,
            'match_key': key,
            'title': title,
            'release_date': release_date,
            'source': source,
            'updated_at': now,
        }
        for key, (title, release_date, source) in best.items()
    ]
    db.upsert_many(
        table='track_release_reference',
        data=data,
        conflict_columns=['artist_id', 'match_key'],
        update_columns=['title', 'release_date', 'source', 'updated_at'],
    )
    logger.info("track_release_reference rebuilt for artist %s: %d rows", artist_id, len(data))
    return len(data)


def get_release_dates(db, artist_id: int) -> dict[str, object]:
    """Return {match_key: release_date} for an artist from the reference table."""
    rows = db.fetch_query(
        "SELECT match_key, release_date FROM track_release_reference "
        "WHERE artist_id = %s AND release_date IS NOT NULL",
        (artist_id,),
    )
    return {k: rd for k, rd in rows} if rows else {}
