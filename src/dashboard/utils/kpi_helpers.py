"""Fonctions KPI réutilisables par toutes les views du dashboard."""
import logging
from datetime import datetime

import streamlit as st

logger = logging.getLogger(__name__)

# Read-only metadata getters below are wrapped in @st.cache_data(ttl=_KPI_TTL). The
# DB handle is passed as `_db` (leading underscore) so Streamlit excludes the
# unhashable connection from the cache key — entries are keyed on artist_id only.
# kpi_helpers is imported only by Streamlit views (no Airflow caller).
#
# UNE DURÉE DE CACHE SE RÈGLE SUR LE RYTHME DE LA SOURCE, PAS SUR LA PRUDENCE.
#
# Ces dix helpers lisaient des tables alimentées UNE FOIS PAR NUIT par les DAGs de
# collecte, avec un TTL de 60 secondes : à partir de la 61ᵉ seconde, dix requêtes
# repartaient chercher un nombre dont on savait qu'il ne changerait pas avant le
# lendemain. Le TTL de 60 s protégeait contre une fraîcheur que la source ne fournit
# pas.
#
# Il reste UN moment où ces nombres changent en pleine journée : quand l'artiste
# déclenche une collecte depuis le dashboard. Ce moment est déjà connu du code —
# `collection_trigger` et la page Credentials y purgent `cached_last_run_per_dag`.
# `clear_kpi_caches()` s'y greffe, et c'est ce qui rend le TTL long sans effet de
# bord visible : on ne fait pas confiance à l'horloge, on écoute l'événement.
_KPI_TTL = 600


# SEUILS DE FRAÎCHEUR — DEUX CONTRATS, DEUX BARÈMES (en heures).
#
# Un seul barème servait les deux, et il était calibré sur les API : vert < 24 h,
# orange < 72 h, rouge au-delà. Appliqué à un CSV, il rend un fichier déposé il y a
# **trois jours** en ROUGE — « c'est en rouge alors qu'on a que 3 jours de retard »
# (2026-09-12). Le rouge doit vouloir dire « quelque chose est cassé » ; s'il
# s'allume sur un comportement normal, on apprend à ne plus le regarder, et il ne
# dira plus rien le jour où ça casse vraiment.
#
#   API  — une collecte tourne CHAQUE MATIN. Passer une nuit est déjà anormal, deux
#          est une panne. Inchangé.
#   CSV  — personne ne dépose un export tous les jours. Spotify for Artists publie
#          par semaine ; une semaine sans dépôt est ordinaire, un mois est un
#          abandon. D'où 7 j / 30 j, demandés et non déduits.
_FRESH_H = 24
_WARN_H = 72
_CSV_FRESH_H = 24 * 7        # une semaine : le rythme de publication de S4A
_CSV_WARN_H = 24 * 30        # un mois sans dépôt — là, la donnée est vraiment vieille

# Filtre ligne "Total" des CSV Spotify for Artists
ARTIST_NAME_FILTER = "1x7xxxxxxx"


# ─── Fraîcheur des sources ──────────────────────────────────────────────────

# `kind` et `at` : ce que l'artiste doit savoir de CHAQUE source, déclaré à côté
# d'elle plutôt que résumé en prose au-dessus de la grille.
#
#   kind="api"  la collecte part toute seule, `at` est l'heure du cron (Europe/Paris)
#   kind="csv"  la source ne bouge qu'au dépôt d'un fichier, donc `at` est None
#
# Les heures sont celles des DAGs (`airflow/dags/*.py`, `schedule="0 H * * *"`) :
# Meta 5 h, Spotify 7 h, YouTube 8 h, SoundCloud 9 h, Instagram 10 h. Les recopier
# ici est une duplication assumée et gardée par
# `tests/test_the_announced_collection_time_is_the_real_one.py`, qui les compare aux
# DAGs — annoncer une heure fausse est pire que n'en annoncer aucune.
SOURCES_CONFIG = [
    {
        "label": "Spotify API",
        "kind": "api",
        "at": "07:00",
        "icon": "🎸",
        "table": "artists",
        "col": "collected_at",
        "artist_col": None,
        # `artists` PK is the Spotify string id, not the saas artist_id. Scope per
        # tenant through the saas_artists.spotify_artist_id bridge so a fresh account
        # doesn't inherit another tenant's freshness (an unbridged tenant matches
        # nothing → "no data"). Trusted constant (no user input) — validated against
        # _ALLOWED_ARTIST_FILTERS before interpolation (CLAUDE.md rule #8).
        "artist_filter": "artist_id IN (SELECT spotify_artist_id FROM saas_artists WHERE id = %s)",
    },
    {
        "label": "Spotify S4A",
        "kind": "csv",
        "at": None,
        "icon": "🎵",
        "table": "s4a_song_timeline",
        "col": "collected_at",
        "artist_col": "artist_id",
    },
    {
        "label": "YouTube",
        "kind": "api",
        "at": "08:00",
        "icon": "🎬",
        "table": "youtube_channel_history",
        "col": "collected_at",
        "artist_col": "artist_id",
    },
    {
        "label": "SoundCloud",
        "kind": "api",
        "at": "09:00",
        "icon": "☁️",
        "table": "soundcloud_tracks_daily",
        "col": "collected_at",  # DATE
        "artist_col": "artist_id",
    },
    {
        "label": "Instagram",
        "kind": "api",
        "at": "10:00",
        "icon": "📸",
        "table": "instagram_daily_stats",
        "col": "collected_at",  # DATE
        "artist_col": "artist_id",
    },
    {
        "label": "Apple Music",
        "kind": "csv",
        "at": None,
        "icon": "🍎",
        "table": "apple_songs_performance",
        "col": "collected_at",
        "artist_col": "artist_id",
    },
    {
        "label": "Meta Ads",
        "kind": "api",
        "at": "05:00",
        "icon": "📱",
        "table": "meta_insights_performance_day",
        "col": "collected_at",
        "artist_col": "artist_id",
    },
    {
        "label": "iMusician",
        "kind": "csv",
        "at": None,
        "icon": "💰",
        "table": "imusician_monthly_revenue",
        "col": "updated_at",
        "artist_col": "artist_id",
    },
]

# Allowlists — protect f-string identifier interpolation in get_source_freshness()
_ALLOWED_TABLES     = frozenset(s["table"]      for s in SOURCES_CONFIG)
_ALLOWED_COLS       = frozenset(s["col"]        for s in SOURCES_CONFIG)
_ALLOWED_ARTIST_COLS = frozenset(s["artist_col"] for s in SOURCES_CONFIG if s.get("artist_col"))
_ALLOWED_ARTIST_FILTERS = frozenset(s["artist_filter"] for s in SOURCES_CONFIG if s.get("artist_filter"))


@st.cache_data(ttl=_KPI_TTL)
def get_source_freshness(_db, artist_id):
    """Return {label: {icon, last_dt}} for each source in a single UNION ALL query.

    Replaces 7 sequential SELECT MAX() calls with one round-trip.
    Identifiers are validated against allowlists before interpolation.
    """
    db = _db
    # Validate all identifiers against allowlists before building the query
    for src in SOURCES_CONFIG:
        if src["table"] not in _ALLOWED_TABLES:
            raise ValueError(f"Table not in allowlist: {src['table']}")
        if src["col"] not in _ALLOWED_COLS:
            raise ValueError(f"Column not in allowlist: {src['col']}")
        if (not src.get("skip_artist_filter") and not src.get("artist_filter")
                and src["artist_col"] not in _ALLOWED_ARTIST_COLS):
            raise ValueError(f"Artist column not in allowlist: {src['artist_col']}")
        if src.get("artist_filter") and src["artist_filter"] not in _ALLOWED_ARTIST_FILTERS:
            raise ValueError(f"Artist filter not in allowlist: {src['artist_filter']}")

    branches = []
    params = []
    for src in SOURCES_CONFIG:
        custom_filter = src.get("artist_filter")
        if artist_id is not None and custom_filter:
            branches.append(
                f"SELECT '{src['label']}' AS label, MAX({src['col']}) AS last_dt"
                f" FROM {src['table']} WHERE {custom_filter}"
            )
            params.append(artist_id)
        elif artist_id is not None and not src.get("skip_artist_filter"):
            branches.append(
                f"SELECT '{src['label']}' AS label, MAX({src['col']}) AS last_dt"
                f" FROM {src['table']} WHERE {src['artist_col']} = %s"
            )
            params.append(artist_id)
        else:
            branches.append(
                f"SELECT '{src['label']}' AS label, MAX({src['col']}) AS last_dt"
                f" FROM {src['table']}"
            )
    query = " UNION ALL ".join(branches)
    params = tuple(params)

    label_to_icon = {src["label"]: src["icon"] for src in SOURCES_CONFIG}
    result = {src["label"]: {"icon": src["icon"], "last_dt": None} for src in SOURCES_CONFIG}

    try:
        rows = db.fetch_query(query, params) if params else db.fetch_query(query)
        for label, val in rows:
            if val is not None and not isinstance(val, datetime):
                val = datetime(val.year, val.month, val.day, 0, 0, 0)
            result[label] = {"icon": label_to_icon.get(label, ""), "last_dt": val}
    except Exception:
        pass  # return defaults (all None) on failure

    return result


def freshness_status(last_dt, kind: str = "api"):
    """(emoji, couleur, libellé) selon l'âge de `last_dt` ET la nature de la source.

    `kind` vient de `SOURCES_CONFIG` et vaut `"api"` ou `"csv"`. Il ne change pas la
    mesure, il change le BARÈME : une API muette depuis trois jours est en panne, un
    CSV non redéposé depuis trois jours est un mardi ordinaire. Le défaut reste
    `"api"`, le barème le plus strict — une source dont on ignore la nature est
    surveillée comme la plus exigeante, jamais l'inverse.

    DEUX HORLOGES ÉTAIENT SOUSTRAITES L'UNE DE L'AUTRE. `datetime.now()` nu rend
    l'heure LOCALE de l'hôte, tandis que `last_dt` sort d'une colonne sans fuseau où
    les collecteurs écrivent de l'UTC. Tous les âges de fraîcheur de la page étaient
    donc faux d'une heure l'hiver, de deux l'été — assez pour qu'une source collectée
    il y a 23 h s'affiche « il y a 25 h » et bascule de vert à orange.

    Mesuré le 2026-09-10 : 7,9 % des lignes de `youtube_video_stats` changent même de
    JOUR selon le fuseau retenu. Une date qui circule sans dire d'où elle vient finit
    par décider d'un verdict.

    On compare donc deux instants du même référentiel : l'heure courante en UTC contre
    un horodatage qu'on déclare UTC, ce qu'il est.
    """
    if last_dt is None:
        return "⚫", "#888888", "Pas de données"
    from datetime import timezone as _tz
    _now = datetime.now(_tz.utc)
    _ref = last_dt if last_dt.tzinfo is not None else last_dt.replace(tzinfo=_tz.utc)
    age_h = (_now - _ref).total_seconds() / 3600
    _fresh, _warn = ((_CSV_FRESH_H, _CSV_WARN_H) if kind == "csv"
                     else (_FRESH_H, _WARN_H))
    if age_h < _fresh:
        return "🟢", "#1DB954", (f"Il y a {int(age_h)}h" if age_h < 24
                                 else f"Il y a {int(age_h / 24)}j")
    elif age_h < _warn:
        days = int(age_h / 24)
        return "🟠", "#FFA500", f"Il y a {days}j"
    else:
        days = int(age_h / 24)
        return "🔴", "#FF4444", f"Il y a {days}j"


# ─── KPI Streams ────────────────────────────────────────────────────────────

@st.cache_data(ttl=_KPI_TTL)
def get_total_streams_s4a(_db, artist_id):
    """Total streams Spotify S4A — la branche `spotify` de la couche or.

    La déduplication par (jour, titre) et le retrait de la ligne « Total » des CSV
    vivent dans `v_s4a_song_daily` (migration 105), que `v_platform_totals` agrège.
    Les recopier ici les faisait diverger : c'est la plateforme dont le total avait
    trois définitions différentes le 2026-09-11.
    """
    db = _db
    try:
        if artist_id is not None:
            row = db.fetch_query(
                "SELECT COALESCE(SUM(total), 0) FROM v_platform_totals"
                " WHERE platform = 'spotify' AND artist_id = %s", (artist_id,))
        else:
            row = db.fetch_query(
                "SELECT COALESCE(SUM(total), 0) FROM v_platform_totals"
                " WHERE platform = 'spotify'")
        return int(row[0][0] or 0)
    except Exception:      # noqa: BLE001
        return 0


@st.cache_data(ttl=_KPI_TTL)
def get_total_views_youtube(_db, artist_id):
    """Total vues YouTube — la couche OR (`v_platform_totals`, ADR-019).

    Cette fonction lisait `youtube_channel_history.view_count`, le compteur de CHAÎNE,
    prouvé ~10× faux le 2026-09-08 : figé onze jours puis +360 attribués à une seule
    journée, quand YouTube Studio annonçait 64 vues sur la période. Il porte les vidéos
    privées, supprimées et des agrégats internes, et il avance par paliers.

    Elle alimente « Data Wrapped », qui affichait donc un total YouTube différent de
    celui de l'accueil et de l'API pour le même locataire au même instant. Mesuré le
    2026-09-10 sur l'artiste 1 : 120 627 ici contre 118 219 par la définition retenue.
    """
    db = _db
    try:
        if artist_id is not None:
            row = db.fetch_query(
                "SELECT COALESCE(total, 0) FROM v_platform_totals "
                "WHERE artist_id = %s AND platform = 'youtube'", (artist_id,))
        else:
            row = db.fetch_query(
                "SELECT COALESCE(SUM(total), 0) FROM v_platform_totals "
                "WHERE platform = 'youtube'")
        return int(row[0][0] or 0) if row else 0
    except Exception as exc:      # noqa: BLE001
        logger.warning("YouTube total unreadable: %s", type(exc).__name__)
        return 0


@st.cache_data(ttl=_KPI_TTL)
def get_total_plays_soundcloud(_db, artist_id):
    """Total plays SoundCloud — la branche `soundcloud` de la couche or.

    SoundCloud est un COMPTEUR : le total est le dernier relevé de chaque titre, et
    cette règle vit dans `v_soundcloud_track_latest` (migration 107). La version
    recopiée ici dédupliquait par `track_id` SEUL — deux locataires qui repostent le
    même titre n'en gardaient qu'un.
    """
    db = _db
    try:
        if artist_id is not None:
            row = db.fetch_query(
                "SELECT COALESCE(SUM(total), 0) FROM v_platform_totals"
                " WHERE platform = 'soundcloud' AND artist_id = %s", (artist_id,))
        else:
            row = db.fetch_query(
                "SELECT COALESCE(SUM(total), 0) FROM v_platform_totals"
                " WHERE platform = 'soundcloud'")
        return int(row[0][0] or 0)
    except Exception:
        return 0


@st.cache_data(ttl=_KPI_TTL)
def get_total_plays_apple(_db, artist_id):
    """Total plays Apple Music, SANS compter deux fois.

    `SUM(plays)` sur toute la table était juste tant qu'un artiste n'avait qu'un seul
    relevé — ce que la clé lui imposait avant la migration 093. Depuis qu'il peut
    déposer plusieurs exports (« depuis le début », puis un par année, migration 094),
    la somme brute additionne un cumul ET les années qu'il contient déjà : les mêmes
    écoutes deux fois.

    La règle est donc « le dernier cumul s'il existe, sinon la somme des périodes
    bornées » — elle vit dans `platform_timeseries.apple_lifetime_plays`, et les trois
    lecteurs (accueil, Data Wrapped, export PDF) passent par ici.
    """
    if artist_id is not None:
        from src.dashboard.utils.platform_timeseries import apple_lifetime_plays
        return apple_lifetime_plays(_db, artist_id)
    try:
        # Vue flotte (admin) : pas de locataire, donc pas de notion de « son » cumul.
        #
        # LE DERNIER RELEVÉ DE CHAQUE TITRE, comme partout ailleurs.
        #
        # ⚠️ Ce n'est PAS la correction d'un défaut vivant, et le dire importe :
        # mesuré en production le 2026-09-11, la table porte 29 lignes
        # `period_start IS NULL` pour 29 couples (locataire, titre) — **zéro
        # doublon** — donc la somme nue donnait déjà le bon total, 7 875. J'avais
        # d'abord annoncé le contraire en la comparant au dernier instantané GLOBAL
        # (7 435), qui est faux dans l'autre sens : il perd les titres dont le
        # dernier relevé n'est pas le plus récent de la flotte.
        #
        # Ce que le `DISTINCT ON` retire est un risque LATENT : `plays` est un
        # compteur, deux instantanés du même titre peuvent coexister depuis la
        # migration 093 (la clé inclut `snapshot_date`), et ce jour-là la somme nue
        # compterait ce titre deux fois. Le locataire est dans la clé parce que deux
        # artistes peuvent avoir une chanson du même nom. C'est la forme de
        # `v_platform_totals` (ADR-019).
        row = _db.fetch_query(
            "SELECT COALESCE(SUM(total), 0) FROM v_platform_totals"
            " WHERE platform = 'apple'")
        return int(row[0][0] or 0)
    except Exception:      # noqa: BLE001
        return 0


# ─── KPI ML ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=_KPI_TTL)
def get_spotify_popularity(_db, artist_id):
    """Score de popularité Spotify (dernier enregistrement)."""
    db = _db
    try:
        if artist_id is not None:
            row = db.fetch_query(
                "SELECT popularity, track_name FROM track_popularity_history WHERE artist_id = %s ORDER BY date DESC LIMIT 1",
                (artist_id,)
            )
        else:
            row = db.fetch_query(
                "SELECT popularity, track_name FROM track_popularity_history ORDER BY date DESC LIMIT 1"
            )
        if row and row[0][0] is not None:
            return {'score': int(row[0][0]), 'track': row[0][1]}
    except Exception:
        pass
    return None


@st.cache_data(ttl=_KPI_TTL)
def get_instagram_followers(_db, artist_id):
    """Nombre d'abonnés Instagram (dernier snapshot)."""
    db = _db
    try:
        if artist_id is not None:
            row = db.fetch_query(
                """SELECT followers_count, collected_at FROM instagram_daily_stats
                   WHERE artist_id = %s ORDER BY collected_at DESC LIMIT 1""",
                (artist_id,)
            )
        else:
            row = db.fetch_query(
                "SELECT followers_count, collected_at FROM instagram_daily_stats ORDER BY collected_at DESC LIMIT 1"
            )
        if row and row[0][0] is not None:
            return {'followers': int(row[0][0]), 'date': row[0][1]}
    except Exception:
        pass
    return None


@st.cache_data(ttl=_KPI_TTL)
def get_soundcloud_likes(_db, artist_id):
    """Total likes SoundCloud — le dernier relevé de chaque titre.

    `v_platform_totals` ne porte qu'une colonne « total » et ne peut donc pas
    exprimer une deuxième mesure ; les likes se lisent sur la vue de grain,
    `v_soundcloud_track_latest`. Même règle que les écoutes, écrite une seule fois.
    """
    db = _db
    try:
        if artist_id is not None:
            row = db.fetch_query(
                "SELECT COALESCE(SUM(likes_count), 0) FROM v_soundcloud_track_latest"
                " WHERE artist_id = %s", (artist_id,))
        else:
            row = db.fetch_query(
                "SELECT COALESCE(SUM(likes_count), 0) FROM v_soundcloud_track_latest")
        return int(row[0][0] or 0)
    except Exception:
        return 0


# ─── ROI Breakheaven ─────────────────────────────────────────────────────────

def month_window(from_date, to_date):
    """Les bornes JOUR des mois que la fenêtre demandée chevauche.

    `v_artist_monthly_revenue` n'a pas de grain jour : ses colonnes sont `year` et
    `month`. Il n'existe donc AUCUNE fenêtre exacte côté revenu — le mois est le grain
    natif, pas une approximation qu'on choisit.

    On élargit aux mois entiers plutôt que de restreindre aux mois pleinement contenus,
    parce que restreindre rendrait vide toute fenêtre courte, et qu'un revenu vide est
    indiscernable à l'écran d'un revenu absent. L'élargissement est rendu à l'appelant
    (`effective_from` / `effective_to`) pour qu'il puisse le DIRE — un réglage qu'on ne
    peut pas honorer se dit, il ne se tait pas.

    Le défaut que ce helper retire, lu le 2026-09-10 : le revenu était filtré sur
    `make_date(year, month, 1) BETWEEN from AND to` pendant que la dépense Meta l'était
    sur `day_date`. Une fenêtre 15 janvier → 10 septembre excluait janvier en entier et
    comptait tout septembre — numérateur et dénominateur du ROI sur deux périodes
    différentes.
    """
    import calendar
    import datetime as _dt

    def _as_date(d):
        return d.date() if isinstance(d, _dt.datetime) else d

    lo, hi = _as_date(from_date), _as_date(to_date)
    eff_from = lo.replace(day=1)
    eff_to = hi.replace(day=calendar.monthrange(hi.year, hi.month)[1])
    return eff_from, eff_to


def fmt_eur(val, digits: int = 2) -> str:
    """Un montant, ou « — ». Jamais « 0,00 € » pour une valeur qu'on n'a pas pu lire."""
    if val is None:
        return "—"
    return f"{val:,.{digits}f} €"


@st.cache_data(ttl=_KPI_TTL)
def get_roi_data(_db, artist_id, from_date, to_date):
    """
    Calcule le ROI iMusician / Meta Ads pour une période donnée.
    Retourne revenue_eur, meta_spend, roi_pct, profitable.
    roi_pct = VRAI ROI = (revenus − dépenses) / dépenses × 100
    (0 % = équilibre, négatif = perte). Pas un ratio revenus/dépenses.
    """
    eff_from, eff_to = month_window(from_date, to_date)
    result = {
        # `None` et non `0.0` : une lecture qui échoue ne se déguise pas en « rien
        # gagné ». `profitable=False` par défaut faisait produire un VERDICT métier
        # par une panne de base (règle .claude/rules/python.md § Erreurs et absences).
        'revenue_eur': None,
        'meta_spend': None,
        'total_spend': None,
        'roi_pct': None,
        'profitable': None,
        # La fenêtre RÉELLEMENT couverte, pour que l'appelant l'affiche.
        'effective_from': eff_from,
        'effective_to': eff_to,
        # LE TROISIÈME ÉTAT. « Rien mesuré » et « on n'a pas pu lire » rendent tous
        # deux None ; sans cette liste l'appelant les confond, et affiche « aucune
        # dépense promo » sur une panne de base.
        'unreadable': [],
    }

    # Revenus distributeurs (iMusician + DistroKid, aggregation sur year+month)
    try:
        if artist_id is not None:
            row = _db.fetch_query(
                """SELECT SUM(revenue_eur) FROM v_artist_monthly_revenue
                   WHERE artist_id = %s AND make_date(year, month, 1) BETWEEN %s AND %s""",
                (artist_id, eff_from, eff_to)
            )
        else:
            row = _db.fetch_query(
                """SELECT SUM(revenue_eur) FROM v_artist_monthly_revenue
                   WHERE make_date(year, month, 1) BETWEEN %s AND %s""",
                (eff_from, eff_to)
            )
        raw = row[0][0] if row else None
        result['revenue_eur'] = float(raw) if raw is not None else None
    except Exception as exc:      # noqa: BLE001 — une tuile ne fait pas tomber la page
        logger.warning("ROI revenue unreadable: %s", type(exc).__name__)
        result['unreadable'].append('revenue')

    # Dépenses Meta Ads
    try:
        if artist_id is not None:
            row = _db.fetch_query(
                """SELECT SUM(spend) FROM v_meta_daily
                   WHERE artist_id = %s AND day BETWEEN %s AND %s""",
                (artist_id, eff_from, eff_to)
            )
        else:
            row = _db.fetch_query(
                """SELECT SUM(spend) FROM v_meta_daily
                   WHERE day BETWEEN %s AND %s""",
                (eff_from, eff_to)
            )
        raw = row[0][0] if row else None
        result['meta_spend'] = float(raw) if raw is not None else None
    except Exception as exc:      # noqa: BLE001
        logger.warning("ROI spend unreadable: %s", type(exc).__name__)
        result['unreadable'].append('spend')

    # Promo spend = Meta Ads only (the Hypeddit "budget" the user enters is in fact the
    # Meta-ad budget, not a separate Hypeddit spend — so it must not be double-counted).
    result['total_spend'] = result['meta_spend']
    # Un ROI ne se calcule QUE si les deux côtés sont connus. Un côté inconnu rend le
    # verdict inconnu — il ne le rend pas « déficitaire ».
    known = result['revenue_eur'] is not None and result['total_spend'] is not None
    if known and result['total_spend'] > 0:
        result['roi_pct'] = (
            (result['revenue_eur'] - result['total_spend']) / result['total_spend']) * 100
        result['profitable'] = result['revenue_eur'] >= result['total_spend']

    return result


@st.cache_data(ttl=_KPI_TTL)
def get_monthly_roi_series(_db, artist_id, from_date, to_date):
    """Monthly revenue vs Meta spend for the period.
    Columns: period_date, distributor_revenue, sacem_revenue, revenue_eur (= the two
    summed), meta_spend. SACEM is kept distinct so the chart can stack it. No Hypeddit
    (the entered Hypeddit budget is in fact the Meta-ad budget — not a real spend)."""
    import pandas as pd

    # LES DEUX SÉRIES SUR LES MÊMES BORNES. Le revenu est mensuel, la dépense
    # quotidienne ; les borner différemment faisait comparer deux périodes.
    eff_from, eff_to = month_window(from_date, to_date)

    def _q(sql_artist, sql_all, cols):
        try:
            if artist_id is not None:
                return _db.fetch_df(sql_artist, (artist_id, eff_from, eff_to))
            return _db.fetch_df(sql_all, (eff_from, eff_to))
        except Exception as exc:      # noqa: BLE001 — une courbe absente ne tue pas la page
            logger.warning("ROI series unreadable (%s): %s", cols[1], type(exc).__name__)
            return pd.DataFrame(columns=cols)

    # Revenue per month — distributor (iMusician + DistroKid) and SACEM split in ONE
    # scan of the revenue view via conditional aggregation (was two separate scans).
    df_rev = _q(
        """SELECT make_date(year, month, 1) AS period_date,
                  SUM(revenue_eur) FILTER (WHERE source IN ('imusician', 'distrokid'))
                      AS distributor_revenue,
                  SUM(revenue_eur) FILTER (WHERE source = 'sacem') AS sacem_revenue
           FROM v_artist_monthly_revenue
           WHERE artist_id = %s AND make_date(year, month, 1) BETWEEN %s AND %s
           GROUP BY year, month ORDER BY year, month""",
        """SELECT make_date(year, month, 1) AS period_date,
                  SUM(revenue_eur) FILTER (WHERE source IN ('imusician', 'distrokid'))
                      AS distributor_revenue,
                  SUM(revenue_eur) FILTER (WHERE source = 'sacem') AS sacem_revenue
           FROM v_artist_monthly_revenue
           WHERE make_date(year, month, 1) BETWEEN %s AND %s
           GROUP BY year, month ORDER BY year, month""",
        ['period_date', 'distributor_revenue', 'sacem_revenue'])

    # Meta spend per month
    df_spend = _q(
        """SELECT DATE_TRUNC('month', day)::date AS period_date, SUM(spend) AS meta_spend
           FROM v_meta_daily
           WHERE artist_id = %s AND day BETWEEN %s AND %s
           GROUP BY 1 ORDER BY 1""",
        """SELECT DATE_TRUNC('month', day)::date AS period_date, SUM(spend) AS meta_spend
           FROM v_meta_daily WHERE day BETWEEN %s AND %s
           GROUP BY 1 ORDER BY 1""",
        ['period_date', 'meta_spend'])

    if df_rev.empty and df_spend.empty:
        return pd.DataFrame()

    if df_rev.empty:
        df_rev = pd.DataFrame(columns=['period_date', 'distributor_revenue', 'sacem_revenue'])
    if df_spend.empty:
        df_spend = pd.DataFrame(columns=['period_date', 'meta_spend'])

    # PAS de `.fillna(0)` : un mois présent côté revenu et absent côté Meta n'a pas
    # « 0 € dépensé », il n'a pas de mesure. Les deux appelants pandas
    # (`revenue_forecast.py`, `_tab_budget_roi.py`) étaient DÉJÀ écrits pour l'absence
    # — `.sum()` saute les NaN et l'un fait même un `dropna` explicite ; c'est le
    # helper qui la leur cachait.
    df = pd.merge(df_rev, df_spend, on='period_date', how='outer')
    # LE TYPE, pas seulement la valeur. `.fillna(0)` coerçait accessoirement ces
    # colonnes en float64 ; en le retirant, psycopg2 les laisse en `object` porteuses
    # de `decimal.Decimal`, et le premier `float - Decimal` d'un appelant lève
    # (`revenue_forecast.py:453`, vu rouge le 2026-09-10). C'est la classe
    # `object-dtype-numeric-op` du catalogue. `errors='coerce'` garde les NaN NaN :
    # on convertit le type, on ne remplit pas l'absence.
    for _col in ('distributor_revenue', 'sacem_revenue', 'meta_spend'):
        if _col in df.columns:
            df[_col] = pd.to_numeric(df[_col], errors='coerce')
    df['revenue_eur'] = df['distributor_revenue'] + df['sacem_revenue']
    df['period_date'] = pd.to_datetime(df['period_date'])
    return df.sort_values('period_date')


def clear_kpi_caches() -> None:
    """Purge les compteurs mis en cache — appelée quand une collecte est déclenchée.

    Sans elle, un artiste qui lance une collecte depuis le dashboard verrait ses
    anciens totaux pendant dix minutes et conclurait que rien ne s'est passé. C'est
    le seul instant où ces nombres changent hors de la nuit, et il est observable :
    on ne raccourcit donc pas le TTL « au cas où », on purge à cet instant précis.
    """
    for fn in (get_source_freshness, get_total_streams_s4a, get_total_views_youtube,
               get_total_plays_soundcloud, get_total_plays_apple,
               get_spotify_popularity, get_instagram_followers, get_soundcloud_likes,
               get_roi_data, get_monthly_roi_series):
        try:
            fn.clear()
        except Exception:  # noqa: BLE001 — une purge best-effort ne casse pas un clic
            pass

    # Le cache des SÉRIES vit à côté (`series_cache`), parce que
    # `platform_timeseries` doit rester sans Streamlit. Les deux se vident
    # ensemble : les cinq endroits qui appellent cette fonction sont exactement
    # les moments où la donnée change en pleine journée, et il n'y a aucune
    # raison qu'un des deux caches survive à l'autre.
    try:
        from src.dashboard.utils.series_cache import clear as _clear_series
        _clear_series()
    except Exception:  # noqa: BLE001
        pass
