"""Vue Upload CSV — Brick 5.

Accessible à tous les utilisateurs authentifiés.
- Artiste : importe des CSV pour son propre artist_id.
- Admin    : sélectionne l'artiste cible.

Flux : Upload (multi-fichier) → Détection auto du type → Aperçu → Confirmer tout.
"""
import sys
from pathlib import Path
import streamlit as st
import re

import pandas as pd

from src.dashboard.utils.i18n import t
from src.transformers.s4a_csv_parser import MissingFromFilenameError
from src.dashboard.utils.cache_invalidation import purge_after_write
from src.dashboard.utils.csv_serialization import (
    _read_headers, _serialization_label, _sniff_sep,
)

_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)


# ─────────────────────────────────────────────
# Platform registry  (key → DB config)
# ─────────────────────────────────────────────
#
# Il a DÉMÉNAGÉ dans `utils/csv_platforms.py` le 2026-09-12, et il est ré-importé
# ici sous son nom d'origine — les lecteurs de ce module n'ont pas bougé.
#
# La raison est mesurée : la mise en route a besoin de ses huit libellés pour
# afficher « OK / NOK » par type de fichier, et importer CETTE vue pour les lire
# coûtait **1 073 ms au premier rendu de l'accueil** (pandas + transformateurs +
# Streamlit, pour huit chaînes). Un registre de données n'a pas à traîner un
# importateur derrière lui.
from src.dashboard.utils.csv_platforms import _PLATFORMS


# ─────────────────────────────────────────────
# Auto-detection
# ─────────────────────────────────────────────

_BOM_FORMS = (
    "\ufeff",      # le BOM décodé en UTF-8
    "ï»¿",         # le même octets-pour-octets, décodé en latin-1 ou cp1252
)


def _normalise_header(col: str) -> str:
    """Un en-tête comparable : sans BOM, sans espaces, en minuscules.

    Trois formes du même caractère invisible peuvent arriver ici selon l'encodage
    par lequel le fichier a été lu. Aucune n'est un blanc, donc `strip()` seul les
    laisse toutes passer — et une comparaison `"date" in cols` échoue sur un en-tête
    qui s'AFFICHE « date ». C'est ce qui rend la classe si coûteuse : le message
    d'erreur montre la bonne colonne.
    """
    out = str(col or "")
    for form in _BOM_FORMS:
        out = out.replace(form, "")
    return out.lower().strip()


def _detect_platform(filename: str, columns: list[str]) -> str | None:
    """Return a platform key from filename + column headers, or None if unknown.

    Detection is ordered from most specific to least specific to avoid false positives.
    """
    name = filename.lower()
    # `\ufeff` n'est PAS un blanc : `str.strip()` ne le retire pas. Une colonne
    # arrivée par un autre chemin — un parseur tiers, un fichier recollé à la main —
    # porterait donc encore son BOM ici, et la détection échouerait de nouveau en
    # silence. Le lecteur d'en-têtes le retire déjà à la source ; ceci est la
    # seconde couche, celle qui rend la classe impossible plutôt qu'improbable.
    cols = {_normalise_header(c) for c in columns}

    def has_any(*opts):
        return any(o in cols for o in opts)

    _STREAMS = ('streams', 'ecoutes', 'écoutes', 'stream count', 'streams count')

    # DistroKid — bank details ('sale month' + USD earnings is highly specific;
    # disambiguated from iMusician sales by 'store' vs 'shop')
    if 'sale month' in cols and 'earnings (usd)' in cols:
        return 'distrokid_sales'

    # iMusician — sales (ISRC + shop is highly specific)
    if 'isrc' in cols and has_any('shop', 'shop name'):
        return 'imusician_sales'

    # iMusician — summary (release title + a revenue/streams column; aligned with the
    # parser's required cols so a real export isn't rejected on a column rename)
    if has_any('release title', 'release') and has_any('track streams', 'total revenue', 'revenue'):
        return 'imusician_summary'

    # Apple Music (unchanged — already flexible, and Benken's Apple import worked)
    if any(c in cols for c in ['morceau', 'song title']) and \
       any(c in cols for c in ['écoutes', 'plays', 'play count', 'lectures']):
        return 'apple'

    # S4A audience : `listeners` EST le discriminant, et rien d'autre.
    #
    # Le jeton « audience » du nom de fichier a été retiré le 2026-09-06, et il a
    # fallu un garde pour le voir : gardé même comme simple « départage », il
    # classait « Kimono - Audience-timeline.csv » — une timeline dont le TITRE
    # contient le mot — parmi les exports d'audience. Un nom de fichier porte le nom
    # d'un morceau ; il ne peut pas servir d'indice sur le contenu.
    #
    # Un export d'audience sans colonne `listeners` n'existe pas : c'est la colonne
    # que cet export est fait pour livrer.
    if has_any('listeners', 'auditeurs') and 'date' in cols and 'song' not in cols:
        return 's4a_audience'

    # L'export « Depuis le début » de S4A (`…-songs-all.csv`) est REFUSÉ ICI, à la
    # détection, et non trois couches plus bas.
    #
    # Il était détecté par son propre nom de fichier (ci-dessous), puis rejeté par
    # `_detect_window` (`s4a_csv_parser.py`) avec un message conseillant de RENOMMER le
    # fichier. Or renommer ne corrige rien : Spotify renvoie auditeurs et sauvegardes à
    # ZÉRO sur cet export, c'est la donnée qui est inutilisable. L'artiste était donc
    # envoyé faire un geste sans effet, deux fois de suite. Le refuser au bon endroit
    # permet de dire la vraie raison ET le vrai remède.
    if 'songs-all' in name or 'songs_all' in name:
        return 's4a_songs_all_rejected'

    # LA MÊME REFUS, SANS LE NOM. Un export « Depuis le début » renommé — ou
    # simplement téléchargé par un navigateur qui suffixe `(1)` — passait la branche
    # ci-dessus et était accepté comme un catalogue valide, alors que ses auditeurs
    # et ses sauvegardes sont à ZÉRO. La donnée est reconnaissable en elle-même :
    # un catalogue par titre dont les colonnes `listeners` ET `saves` existent et ne
    # contiennent que des zéros ne peut pas être un vrai export sur 12 mois.
    #
    # Le contrôle se fait donc à la LECTURE (`_parse_file`), où les valeurs sont
    # disponibles — la détection ne voit que les en-têtes, et ceux d'un export
    # « Depuis le début » sont identiques à ceux d'un export sur 12 mois.

    # S4A songs-all (per-song catalogue): 'song' + release_date (or filename signal).
    if 'song' in cols and ('release_date' in cols or 'saves' in cols):
        return 's4a_songs_global'

    # S4A timeline par titre : date + écoutes, sans colonne de titre. AUCUNE
    # condition sur le nom du fichier.
    #
    # L'exclusion `'audience' not in name` a été retirée le 2026-09-06 : « tous les
    # fichiers, peu importe leur nom, doivent être reconnus ». Elle était en plus
    # dangereuse dans les deux sens — un titre contenant le mot « audience »
    # (« Kimono à semelle de fer - Audience-timeline.csv ») était refusé, et un
    # export d'audience renommé serait passé pour une timeline.
    #
    # Elle est INUTILE parce que la branche audience passe avant et retient déjà tout
    # ce qui porte `listeners` ; ce qui arrive ici n'en a pas. Le départage se fait
    # donc sur les colonnes, où il a toujours été.
    if 'date' in cols and has_any(*_STREAMS) and 'song' not in cols:
        return 's4a'

    return None


# ─────────────────────────────────────────────
# Parsing dispatch
# ─────────────────────────────────────────────

# ── La configuration de SÉRIALISATION, résolue une seule fois ─────────────────
#
# « CSV file encoding and schema information must be configured in the target system
#   to ensure appropriate ingestion. Autodetection is a convenience feature provided
#   in many cloud environments but is inappropriate for production ingestion. As a
#   best practice, engineers should record CSV encoding and schema details in file
#   metadata. »  — Reis & Housley, *Fundamentals of Data Engineering*, p. 374
#
# On ne peut pas cesser de deviner : nos fichiers viennent de Spotify, d'Apple et
# parfois d'un Excel français, et rien ne nous laisse configurer la source. Mais on
# peut ENREGISTRER ce qu'on a deviné, et c'est la moitié qui manquait : le
# 2026-09-06, douze fichiers ont été refusés à cause d'un BOM et rien ne disait quel
# encodage avait gagné — l'écran affichait « Colonnes vues : ﻿date, streams », où le
# BOM ne se rend pas.
#
# La résolution vivait en DOUBLE, à l'identique, dans `_read_headers` et
# `_sniff_sep` : deux copies d'une règle est une copie qui divergera. Elle est ici,
# une fois, et les deux appellent.
def _rows_in_table(db, table: str, artist_id: int) -> int:
    """Combien de lignes la BASE porte pour ce locataire dans cette table.

    « It's always good practice to run validation on the data models that are built
      at the end of a pipeline. There are three things you can check on: […]
      checking row count growth (or reduction) in the data model. »
            — Densmore, *Data Pipelines Pocket Reference*, p. 218

    `upsert_many` renvoie `len(data)` : le compte ENVOYÉ, après déduplication. C'est
    une déclaration, pas une mesure — si la base en accepte moins, rien ne le dit.
    Petrella (*Fundamentals of Data Observability*, p. 180) nomme les deux chiffres
    à confronter : « emitted record count » et « committed record count ». Ici on
    n'avait que le premier.

    `table` vient de `_PLATFORMS`, un registre en dur — jamais d'une saisie — et
    passe quand même par `validate_table` (règle transverse #8).
    """
    from src.database.postgres_handler import validate_table
    validate_table(table)
    from psycopg2 import sql as pgsql
    row = db.fetch_query(
        pgsql.SQL("SELECT COUNT(*) FROM {} WHERE artist_id = %s").format(
            pgsql.Identifier(table)),
        (artist_id,),
    )
    return int(row[0][0]) if row else 0


def _store_answer(key: str, answer: dict) -> None:
    """Enregistre la réponse et relance le script — MAIS SEULEMENT SI ELLE CHANGE.

    Le widget conserve sa valeur d'une exécution à l'autre. Relancer dès qu'il en
    porte une boucle sans fin sur le cas qui compte le plus : une réponse qui ne
    suffit pas à faire passer le fichier (une période choisie sur un export dont la
    donnée est par ailleurs invalide). Le fichier resterait dans la liste des
    questions, le widget se re-rendrait avec la même valeur, et on relancerait —
    indéfiniment, sans que rien à l'écran ne l'explique.

    Comparer avant de relancer rend l'appel idempotent : une seule relance par
    réponse RÉELLEMENT nouvelle.
    """
    if st.session_state.get(key) == answer:
        return
    st.session_state[key] = answer
    st.rerun()


def _answers_key(artist_id: int, filename: str) -> str:
    """Session key holding what the artist told us about ONE file."""
    return f"_csv_answer_{artist_id}_{filename}"


def _answers_for(artist_id: int, filename: str) -> dict:
    """What the artist has already answered for this file (empty on first pass)."""
    import streamlit as _st
    return _st.session_state.get(_answers_key(artist_id, filename)) or {}


# Apple ÉCRIT la période dans le nom du fichier, et c'est mieux qu'une question.
#
# Vérifié le 2026-09-08 sur les noms réellement déposés (`csv_upload_log`) :
#
#     songs_1700256678_2015-06-30_2026-09-04.csv
#            ^identifiant   ^début      ^fin
#
# Ce sont les bornes EXACTES de l'export, pas seulement l'année — un export « depuis
# le début » y écrit la date de la première sortie. On les lit donc, et on ne demande
# que si le nom ne les porte pas : un fichier renommé, ou suffixé « (1) » par le
# navigateur, garde le droit d'être importé.
_APPLE_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _apple_period_from_filename(filename: str):
    """(début, fin) lues dans le nom, ou `None` si le nom ne les porte pas.

    Exactement DEUX dates, dans l'ordre : un nom qui en porte une seule, trois, ou
    aucune ne dit pas une période, et deviner laquelle serait la même faute que
    deviner la période elle-même.
    """
    import datetime as _dt
    found = _APPLE_DATE.findall(filename or "")
    if len(found) != 2:
        return None
    try:
        start, end = (_dt.date.fromisoformat(d) for d in found)
    except ValueError:
        return None
    return (start, end) if start <= end else None


def _apple_period_bounds(period: str):
    """(début, fin) d'une période choisie À LA MAIN — le repli quand le nom est muet.

    Une ANNÉE est bornée aux deux extrémités : c'est ce qui permet de la placer dans
    une fenêtre sans la confondre avec un cumul. « Depuis le début » n'a pas de borne
    connue quand personne ne l'écrit, et c'est la valeur des relevés déposés avant que
    la question existe.
    """
    import datetime as _dt
    if period == 'all':
        return None, None
    try:
        year = int(period)
    except (TypeError, ValueError):
        return None, None
    return _dt.date(year, 1, 1), _dt.date(year, 12, 31)


def _parse_file(platform_key: str, file, artist_id: int,
                answers: dict | None = None) -> list:
    """Parse an uploaded file for the given platform key. Returns a list of row dicts.

    `answers` carries what the FILE does not and only its name ever did — the song
    title of a timeline export, the 28d/12m window of a "Titres" export. It is
    empty on the first pass; the view fills it after asking, and re-parses.
    """
    filename = getattr(file, 'name', '')
    answers = answers or {}

    if platform_key == 'distrokid_sales':
        # Own reader: TSV or CSV, latin-1 fallback (not plain pd.read_csv)
        from src.transformers.distrokid_parser import DistroKidParser
        return DistroKidParser().parse_upload(file, artist_id=artist_id)

    if platform_key == 'sacem':
        # SACEM statement is an .xlsx ledger — its own parser (not pd.read_csv).
        from src.transformers.sacem_parser import parse_sacem_xlsx
        file.seek(0)
        rows = parse_sacem_xlsx(file)
        for row in rows:
            row['artist_id'] = artist_id
        return rows

    # Même séparateur et même repli d'encodage que la DÉTECTION : sans ça un fichier
    # correctement détecté (tabulé, point-virgulé, latin-1) explosait ici, et l'artiste
    # recevait l'exception brute de pandas au lieu d'une cause.
    df = pd.read_csv(file, sep=_sniff_sep(file), encoding_errors='replace')

    if platform_key == 's4a':
        from src.transformers.s4a_csv_parser import S4ACSVParser
        return S4ACSVParser().parse_timeline(
            df, artist_id=artist_id, filename=filename,
            song_name=answers.get('song', ''))

    if platform_key == 's4a_songs_global':
        # LE REFUS « Depuis le début », RECONNU DANS LES DONNÉES et non dans le nom.
        # Cet export a exactement les mêmes en-têtes qu'un export sur 12 mois ; ce
        # qui le distingue est que Spotify y renvoie auditeurs ET sauvegardes à
        # ZÉRO. Un fichier renommé — ou suffixé « (1) » par le navigateur —
        # échappait au contrôle par nom et était accepté comme un catalogue valide.
        for _col in ('listeners', 'saves'):
            if _col not in df.columns:
                break
        else:
            _num = df[['listeners', 'saves']].apply(
                pd.to_numeric, errors='coerce').fillna(0)
            if len(_num) and (_num.to_numpy() == 0).all():
                raise ValueError(t(
                    "upload_csv.err_songs_all_zero",
                    "Export « Depuis le début » : Spotify y renvoie les auditeurs et "
                    "les sauvegardes à **zéro**, quel que soit le nom du fichier. "
                    "Reprends l'export en réglant la période sur **12 mois**."))
        from src.transformers.s4a_csv_parser import S4ACSVParser
        return S4ACSVParser().parse_songs_global(
            df, artist_id=artist_id, filename=filename,
            window=answers.get('window', ''))

    if platform_key == 's4a_audience':
        from src.transformers.s4a_csv_parser import S4ACSVParser
        return S4ACSVParser().parse_audience(df, artist_id=artist_id)

    if platform_key == 'apple':
        # LA PÉRIODE EST DEMANDÉE, JAMAIS DEVINÉE. L'export Apple n'a aucune colonne
        # de date : c'est le sélecteur de leur interface qui décide, et le fichier
        # n'en garde pas la trace. Sans cette question, trois exports annuels déposés
        # le même jour s'écrasent, et deux exports annuels distincts sont traités
        # comme deux photos d'un cumul — on soustrairait 2023 de 2024, qui sont des
        # périodes DISJOINTES.
        #
        # Même mécanisme que la fenêtre 28 j / 12 mois des exports Spotify : une
        # question sous le tableau, pas une impasse.
        from src.transformers.apple_music_csv_parser import AppleMusicCSVParser
        from src.transformers.s4a_csv_parser import MissingFromFilenameError

        bounds = _apple_period_from_filename(filename)
        if bounds is None:
            period = (answers.get('apple_period') or '').strip()
            if not period:
                raise MissingFromFilenameError(
                    'apple_period',
                    t("upload_csv.ask_apple_period_why",
                      "Ce fichier ne porte pas ses dates. Apple les écrit normalement "
                      "dans le nom (`songs_…_2024-01-01_2024-12-31.csv`) — il a dû "
                      "être renommé. Dis-nous quelle période tu as exportée."))
            bounds = _apple_period_bounds(period)
        rows = AppleMusicCSVParser().parse_songs_performance(df)
        start, end = bounds
        for row in rows:
            row['artist_id'] = artist_id
            row['period_start'] = start
            row['period_end'] = end
        return rows

    if platform_key == 'imusician_summary':
        from src.transformers.imusician_csv_parser import IMusicianCSVParser
        return IMusicianCSVParser().parse_release_summary(df, artist_id=artist_id)

    if platform_key == 'imusician_sales':
        from src.transformers.imusician_csv_parser import IMusicianCSVParser
        return IMusicianCSVParser().parse_sales_detail(df, artist_id=artist_id)

    raise ValueError(f"Plateforme inconnue : {platform_key}")


# ─────────────────────────────────────────────
# View
# ─────────────────────────────────────────────

def _archive_ok(artist_id: int, result: dict) -> None:
    """Keep the bytes of a file that imported cleanly, for 14 days.

    Never raises: the rows are already committed by the time this runs, so failing
    the import because a convenience copy could not be written would trade a working
    feature for a nice-to-have.
    """
    f = result.get('file')
    if f is None:
        return
    try:
        f.seek(0)
        from src.utils.upload_archive import archive_upload
        archive_upload(artist_id, result.get('filename', ''), f.read())
    except Exception:  # noqa: BLE001 — an archive failure must never block an import
        pass


# `show()` a été RETIRÉE le 2026-09-06, et le fait qui l'a décidée est mesurable :
# `app.py` ne l'importe pas. La route `?page=upload_csv` rend `views.credentials`
# depuis la fusion du 2026-09-04 — donc cette fonction n'était atteignable par
# personne. Elle rendait pourtant un titre, une légende et une seconde
# `st.file_uploader`, et `tests/test_views_render_smoke.py` l'appelait directement,
# ce qui la faisait passer pour vivante : un test de rendu ne dit jamais si une page
# est ATTEIGNABLE (`code-nothing-reaches`, déjà six fois dans ce dépôt).
#
# Ce module n'est plus une PAGE : c'est le composant de dépôt que l'onglet
# « 📂 Mes fichiers » de Credentials rend, et le seul du produit.

def _first_song(entry: dict) -> str:
    """Le titre que ce fichier va écrire, quand il en porte un.

    Sur une timeline S4A, il vient du NOM du fichier et de rien d'autre :
    `export (1).csv` s'importe sans erreur sous un morceau nommé « export (1) ».
    L'afficher est ce qui rend une déduction fausse visible AVANT la base.

    Les autres formats portent le titre dans la donnée (`song_name`) : on le montre
    aussi, parce que c'est la clé sur laquelle le mapping cross-plateforme devra
    rapprocher les plateformes — et l'artiste doit pouvoir le lire ici.
    """
    rows = entry.get('rows') or []
    if not rows:
        return ''
    first = rows[0]
    value = first.get('song') or first.get('song_name') or ''
    if len(rows) > 1:
        distinct = {r.get('song') or r.get('song_name') for r in rows}
        if len(distinct) > 1:
            return t("upload_csv.song_many", "{n} titres").format(n=len(distinct))
    return str(value)


def _uploader_key(artist_id: int) -> str:
    """Clé du dépôt, portant un compteur qu'on incrémente pour LE VIDER.

    Streamlit n'offre aucun moyen d'effacer un `file_uploader` : réécrire sa clé de
    session lève. Changer la clé du widget en crée un neuf, donc vide.

    Pourquoi le vider : après un import, les quinze fichiers restaient affichés dans
    la zone de dépôt. Un écran qui montre encore ce qu'on vient de déposer se lit
    « rien n'est parti » — demandé le 2026-09-06, « il faut enlever les fichiers dès
    qu'on a lancé la détection, car ça fait pas import exécuté ».
    """
    nonce = st.session_state.get(f"_csv_uploader_nonce_{artist_id}", 0)
    return f"multi_upload_{artist_id}_{nonce}"


def _clear_uploader(artist_id: int) -> None:
    """Vide la zone de dépôt en changeant la clé du widget."""
    key = f"_csv_uploader_nonce_{artist_id}"
    st.session_state[key] = st.session_state.get(key, 0) + 1


def _last_result_key(artist_id: int) -> str:
    return f"_csv_last_result_{artist_id}"


def _render_after_import(db, artist_id: int, result: dict) -> None:
    """Le bilan d'un import, rendu APRÈS que la zone de dépôt a été vidée.

    Il survit au rerun par la session : `st.rerun()` efface tout ce qui a été écrit
    avant lui, et c'est le défaut exact qui avait rendu invisibles le verdict de
    sauvegarde puis le démarrage automatique de la collecte. Même parade.

    UN SEUL TABLEAU. La détection et le résultat en tenaient deux qui disaient les
    mêmes choses — le fichier, son type, son compte — à quinze lignes d'intervalle.
    """
    n_ok = result.get('n_ok', 0)
    n_err = result.get('n_err', 0)
    total = result.get('total_rows', 0)

    if n_err:
        st.warning(t(
            "upload_csv.done_partial",
            "⚠️ Import terminé : {ok} fichier(s) importé(s), {err} en erreur — "
            "{rows} ligne(s) en base."
        ).format(ok=n_ok, err=n_err, rows=f"{total:,}"))
    else:
        st.success(t(
            "upload_csv.done_all",
            "✅ Import exécuté : {ok} fichier(s), {rows} ligne(s) en base. "
            "Les fichiers ont été retirés de la zone de dépôt."
        ).format(ok=n_ok, rows=f"{total:,}"))

    # LE GESTE SUIVANT, AVANT LE DÉTAIL. Il était sous le tableau et sous les
    # messages d'agrégation : l'artiste lisait « import exécuté », puis quinze
    # lignes de détail, et le bouton arrivait quand il avait déjà quitté l'écran des
    # yeux. Ce qui suit un bilan, c'est l'action suivante ; le détail est là pour
    # qui veut vérifier, pas pour qui veut avancer.
    _render_mapping_cta(artist_id)

    rows = result.get('rows') or []
    if rows:
        st.markdown("---")
        st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')

    # Les messages collectés PENDANT l'import — démarrage de la collecte,
    # référentiel de sorties, agrégations de revenus. Écrits avant le rerun, ils
    # auraient tous disparu.
    _WRITER = {"success": st.success, "warning": st.warning, "caption": st.caption}
    for kind, text in result.get('notes') or []:
        _WRITER.get(kind, st.caption)(text)


def _render_mapping_cta(artist_id: int) -> None:
    """Le geste SUIVANT, nommé et cliquable.

    Un import réussi laisse une question ouverte que nous ne pouvons pas trancher :
    « Kimono à semelle de fer » chez Spotify et « Kimono a semelle de fer » chez
    Apple sont-ils le même morceau ? C'est le rôle du mapping cross-plateforme, et
    l'artiste n'avait aucune raison d'aller l'y chercher dans la barre latérale.
    """
    st.caption(t(
        "upload_csv.mapping_why",
        "Tes fichiers viennent de plusieurs plateformes, qui n'écrivent pas les "
        "titres de la même façon. Le mapping les rapproche pour que tes chiffres "
        "s'additionnent sur le bon morceau."))
    if st.button(t("upload_csv.mapping_cta",
                   "🔗 Confirmer le nom des titres (mapping cross-plateforme) →"),
                 type="primary", key=f"_csv_to_mapping_{artist_id}"):
        # Le bilan est clos par le GESTE, pas par son affichage — voir
        # `utils/pending_notice.py`.
        from src.dashboard.utils.pending_notice import clear_notice
        clear_notice(_last_result_key(artist_id))
        # `goto` et non `_nav_page` + `rerun` : elle retire aussi `?page=`, sans quoi
        # `main()` ré-épingle la page courante au rerun suivant. Une seule règle de
        # navigation dans ce dépôt, et c'est elle.
        from src.dashboard.utils.navigation import goto
        goto('meta_mapping')


def render_uploader(db, target_artist_id: int) -> None:
    """Le dépôt de fichiers, sans titre ni ouverture de connexion.

    Extrait de `show()` le 2026-09-04 pour que l'onglet « 📂 Mes fichiers » de la page
    Credentials puisse le rendre. Le `db` est PASSÉ, jamais ouvert ici : les vues de
    ce dépôt sont plafonnées à une connexion (`tests/test_view_connection_budget.py`)
    et la page appelante a déjà dépensé la sienne.
    """
    # Purge opportuniste des archives expirées. ICI et non dans un cron : le
    # répertoire ne grossit QUE quand quelqu'un dépose un fichier, donc la purge n'a
    # besoin de tourner qu'à ce moment-là.
    #
    # Elle vivait dans `show()`, qu'`app.py` n'appelait plus depuis la fusion du
    # 2026-09-04 — donc **plus rien ne purgeait** depuis deux jours, et retirer la
    # fonction morte l'a simplement rendu visible. Déplacée dans la fonction que
    # l'onglet rend réellement, c'est-à-dire là où un fichier arrive.
    try:
        from src.utils.upload_archive import purge_expired
        purge_expired()
    except Exception:  # noqa: BLE001 — une purge ratée ne doit pas fermer la page
        pass

    # ── Upload multi-fichier ───────────────────────────────────────
    # Le mode d'emploi du relevé SACEM était ICI *et* dans la vue 🎼 Royalties SACEM,
    # mot pour mot. Retiré de ce côté le 2026-09-06 : il s'adressait à qui vient
    # déposer des fichiers Spotify et Apple, et la page SACEM est l'endroit où on se
    # trouve quand on cherche un relevé SACEM. Deux copies d'une consigne, c'est une
    # copie qui se périmera sans que personne ne le voie.
    # `txt` EST ACCEPTÉ ICI POUR POUVOIR ÊTRE REFUSÉ PLUS BAS.
    #
    # Ce paramètre est un filtre de Streamlit : ce qu'il écarte n'atteint jamais
    # notre code, donc jamais notre message. Un export ouvert puis ré-enregistré par
    # un tableur, ou téléchargé par un navigateur qui suffixe `.txt`, disparaissait
    # de la zone de dépôt sans un mot — l'artiste voyait son fichier refusé par
    # l'interface elle-même et n'avait rien à corriger.
    #
    # Un `.txt` qui contient un CSV se détecte exactement comme un `.csv` (on ne lit
    # que ses en-têtes) ; un `.txt` qui n'en contient pas tombe dans « Type non
    # reconnu — colonnes vues : … », qui est un refus avec sa raison.
    uploaded_files = st.file_uploader(
        t("upload_csv.uploader_label", "Fichiers CSV / TSV / TXT / XLSX"),
        type=["csv", "tsv", "txt", "xlsx", "xls"],
        accept_multiple_files=True,
        help=t("upload_csv.uploader_help",
               "Glissez tous vos fichiers en même temps. "
               "Le type (S4A timeline, audience, songs-all, Apple, iMusician, "
               "DistroKid, SACEM relevé .xlsx…) est détecté automatiquement."),
        key=_uploader_key(target_artist_id),
    )

    # LES GUIDES SONT RENDUS EN DERNIER quand des fichiers sont déposés — voir la fin
    # de cette fonction. Ici, ils ne s'affichent QUE si la zone est vide : c'est le
    # moment où l'on ne sait pas encore quoi télécharger, donc le seul où une notice
    # aide. Demandé le 2026-09-06 : « déplace les onglets à dérouler de process pour
    # télécharger EN DESSOUS de la détection ».
    #
    # Entre les deux il y a la même idée : ce qu'on regarde après avoir déposé, c'est
    # le résultat, pas la marche à suivre pour déposer.
    if not uploaded_files:
        # LE BILAN DU DERNIER IMPORT, s'il vient d'avoir lieu. On arrive ici juste
        # après avoir vidé la zone de dépôt, donc c'est le SEUL endroit où ce bilan
        # peut se lire : sans lui, l'écran redeviendrait vierge et l'import n'aurait
        # laissé aucune trace visible.
        # `get` borné à la page, et NON `pop`. Le bilan porte un bouton — « 🔗
        # Confirmer le nom des titres » — et un bloc consommé au rendu ne
        # ré-instancie pas ses widgets au rerun du clic : le geste était jeté
        # (classe `consumed-state-hides-its-own-widget`, 2026-09-08).
        from src.dashboard.utils.pending_notice import pending_notice
        _last = pending_notice(_last_result_key(target_artist_id))
        if _last:
            _render_after_import(db, target_artist_id, _last)
            st.markdown("---")
        from src.dashboard.content.csv_guides_st import render_csv_guides
        render_csv_guides()
        return

    # ── Détection + parsing de tous les fichiers ───────────────────
    st.markdown("---")

    file_results = []  # list of dicts: filename, platform_key, label, rows, error

    for f in uploaded_files:
        entry = {'filename': f.name, 'platform_key': None, 'label': '—',
                 'rows': [], 'error': None, 'file': f}
        try:
            f.seek(0)
            seen_cols = []
            if f.name.lower().endswith(('.xlsx', '.xls')):
                # Excel route (SACEM statement) — sheet-based detection, not CSV headers.
                from src.transformers.sacem_parser import is_sacem_statement
                f.seek(0)
                platform_key = 'sacem' if is_sacem_statement(f) else None
            else:
                f.seek(0)
                seen_cols = _read_headers(f)
                platform_key = _detect_platform(f.name, seen_cols)

            if platform_key == 's4a_songs_all_rejected':
                entry['error'] = t(
                    "upload_csv.err_songs_all",
                    "Export « Depuis le début » non exploitable : Spotify y renvoie "
                    "les auditeurs et les sauvegardes à **zéro**. Ce n'est pas le "
                    "nom du fichier qui pose problème — le renommer ne changera "
                    "rien. Reprends l'export en réglant la période sur **12 mois** "
                    "(fichier `…-songs-1year.csv`).")
                platform_key = None

            entry['seen_columns'] = seen_cols
            if platform_key is None and not entry.get('error'):
                # Echo the parsed header columns so a near-miss is diagnosable
                # ("colonnes vues: …") instead of a dead "type non reconnu".
                entry['error'] = t(
                    "upload_csv.err_unknown_type",
                    "Type non reconnu — vérifiez le nom et les colonnes du fichier.")
                if seen_cols:
                    entry['error'] += t(
                        "upload_csv.err_unknown_cols",
                        " Colonnes vues : {cols}").format(cols=", ".join(seen_cols[:12]))
            else:
                entry['platform_key'] = platform_key
                entry['label'] = t(
                    f"upload_csv.platform.{platform_key}",
                    _PLATFORMS[platform_key]['label'])
                f.seek(0)
                entry['rows'] = _parse_file(
                    platform_key, f, target_artist_id,
                    _answers_for(target_artist_id, f.name))
                if not entry['rows']:
                    entry['error'] = t(
                        "upload_csv.err_no_valid_rows",
                        "Aucune ligne valide détectée après parsing.")

        except MissingFromFilenameError as exc:
            # CE N'EST PAS UN REFUS — c'est une question. Le fichier est bon ; il
            # manque une information que Spotify ne met QUE dans le nom (le titre du
            # morceau, la période 28 j / 12 mois) et que la donnée ne porte nulle
            # part. On la demande sous le tableau plutôt que d'afficher une impasse.
            entry['asks'] = {'field': exc.field, 'message': str(exc),
                             'suggestion': exc.suggestion}
            entry['error'] = str(exc)
        except Exception as exc:
            entry['error'] = str(exc)

        file_results.append(entry)

    # ── Le REFUS laisse une trace ──────────────────────────────────
    #
    # Enregistré ICI, à la détection, et pas au moment de l'import : un fichier
    # écarté n'atteint jamais l'import, donc `csv_upload_log` ne le voyait pas. Douze
    # fichiers refusés depuis juin 2026, aucune alerte — l'artiste l'a vu quinze fois
    # à l'écran, et nous zéro.
    #
    # `seen_columns` est la moitié qui rend le refus DIAGNOSTICABLE après coup. Le
    # message à l'écran portait déjà la réponse — un BOM invisible devant `date` —
    # mais personne n'était là pour le lire. En base, `repr()` le rend visible.
    for r in file_results:
        # Une QUESTION en attente n'est pas un refus : le fichier est bon, il lui
        # manque une réponse. La journaliser gonflerait `csv_upload_log` — et donc
        # l'alerte `check_csv_rejections` — d'un défaut qui n'existe pas.
        if not r['error'] or r.get('asks'):
            continue
        try:
            r['file'].seek(0)
            db.execute_query(
                "INSERT INTO csv_upload_log "
                "(artist_id, filename, platform, row_count, status, error_message, "
                " seen_columns, serialization) "
                "VALUES (%s, %s, NULL, 0, 'rejected', %s, %s, %s)",
                (target_artist_id, r['filename'], str(r['error'])[:500],
                 repr(r.get('seen_columns') or [])[:500],
                 _serialization_label(r['file'])),
            )
        except Exception:  # noqa: BLE001 — journaliser ne doit jamais bloquer l'écran
            pass

    # ── Le titre PORTE le compte, et sa couleur porte le verdict ───
    #
    # « 🔍 Détection — 15 fichier(s) » ne disait que ce qu'on avait déposé. Le
    # chiffre qui compte est celui des fichiers RECONNUS sur le total, et il doit se
    # lire sans parcourir le tableau. Demandé le 2026-09-06.
    #
    # Le pluriel est accordé pour de vrai : « 15 fichier(s) à corriger » se lisait
    # comme quinze problèmes alors qu'il y en avait un.
    _n_total = len(file_results)
    _n_ready = sum(1 for r in file_results if not r['error'])
    _n_asked = sum(1 for r in file_results if r.get('asks'))
    _n_bad = _n_total - _n_ready - _n_asked

    _head = t("upload_csv.detection_count", "Détection : {ok}/{total} fichiers reconnus") \
        .format(ok=_n_ready, total=_n_total)
    if _n_ready == _n_total:
        st.success(f"✅ {_head}")
    else:
        _parts = []
        if _n_asked:
            _parts.append(t("upload_csv.detection_asked_one", "{n} fichier à compléter")
                          .format(n=_n_asked) if _n_asked == 1 else
                          t("upload_csv.detection_asked_many", "{n} fichiers à compléter")
                          .format(n=_n_asked))
        if _n_bad:
            _parts.append(t("upload_csv.detection_bad_one", "{n} fichier à corriger")
                          .format(n=_n_bad) if _n_bad == 1 else
                          t("upload_csv.detection_bad_many", "{n} fichiers à corriger")
                          .format(n=_n_bad))
        _banner = f"{_head} — {', '.join(_parts)}"
        (st.error if _n_bad else st.warning)(
            f"{'❌' if _n_bad else '⚠️'} {_banner}")

    # ── UN SEUL TABLEAU ────────────────────────────────────────────
    #
    # Il y en avait deux — « Détection » puis « Résultats de l'import » — qui
    # nommaient le même fichier, le même type et un compte, à quinze lignes
    # d'intervalle. Consolidés le 2026-09-06 : celui-ci porte les colonnes de
    # résultat, vides tant que l'import n'a pas eu lieu, et c'est LUI qu'on
    # mémorise pour le réafficher après.
    summary_rows = []
    for r in file_results:
        if r.get('asks'):
            status = t("upload_csv.status_needs_answer",
                       "❓ Une précision est demandée juste sous ce tableau")
            count = '—'
        elif r['error']:
            status = f"❌ {r['error']}"
            count = '—'
        else:
            status = t("upload_csv.status_ready", "✅ Prêt")
            count = len(r['rows'])
        # LE TITRE EST AFFICHÉ, parce qu'il est DÉDUIT. Sur une timeline, le titre
        # du morceau vient du nom du fichier et de rien d'autre : `export (1).csv`
        # s'importe sans erreur sous un morceau nommé « export (1) ». Le montrer est
        # ce qui rend une déduction fausse visible AVANT qu'elle n'entre en base —
        # la colonne reste vide pour tous les autres types.
        # Les colonnes de résultat sont posées VIDES dès maintenant : `dict.update`
        # conserve l'ordre d'insertion, donc les déclarer ici est ce qui garde
        # « Statut » en dernière colonne une fois l'import fait.
        summary_rows.append({
            t("upload_csv.col_file", "Fichier"): r['filename'],
            t("upload_csv.col_detected_type", "Type détecté"): r['label'],
            t("upload_csv.col_song", "Titre retenu"): _first_song(r),
            t("upload_csv.col_rows", "Lignes"): count,
            t("upload_csv.col_merged", "Fusionnées"): '',
            t("upload_csv.col_added", "Nouvelles en base"): '',
            t("upload_csv.col_status", "Statut"): status,
        })

    st.dataframe(pd.DataFrame(summary_rows), hide_index=True, width='stretch')

    # ── Ce que le fichier ne dit pas : on le DEMANDE ───────────────
    #
    # Deux informations chez Spotify for Artists ne sont dans aucun fichier — le
    # titre du morceau d'un export timeline (colonnes `date, streams`) et la période
    # 28 jours / 12 mois d'un export « Titres ». Elles ne vivent que dans le NOM.
    #
    # Jusqu'au 2026-09-06, les deux finissaient en impasse : la première rendait zéro
    # ligne sous « Aucune ligne valide détectée après parsing » — un message qui
    # accuse le contenu alors que le contenu est bon ; la seconde conseillait de
    # RENOMMER le fichier, c'est-à-dire de fabriquer à la main la donnée manquante,
    # sans aucun moyen de vérifier ce qu'on écrit.
    #
    # Les deux sont la même faute : deviner, ou faire deviner. Le champ ci-dessous
    # est la seule réponse honnête, et il n'apparaît QUE sur les fichiers concernés —
    # un export au nom Spotify d'origine ne le voit jamais.
    asked = [r for r in file_results if r.get('asks')]
    if asked:
        st.warning(t(
            "upload_csv.asks_header",
            "❓ {n} fichier(s) sont valides mais il leur manque une information que "
            "Spotify ne met que dans le nom du fichier. Renseigne-la ici — le fichier "
            "s'importera tout seul ensuite."
        ).format(n=len(asked)))

        for r in asked:
            field = r['asks']['field']
            st.caption(f"**{r['filename']}** — {r['asks']['message']}")
            key = _answers_key(target_artist_id, r['filename'])
            if field == 'song':
                value = st.text_input(
                    t("upload_csv.ask_song", "Titre du morceau"),
                    value=r['asks'].get('suggestion', ''),
                    key=f"{key}_song_widget",
                    placeholder=t("upload_csv.ask_song_ph", "ex. Kimono à semelle de fer"),
                )
                if value.strip():
                    _store_answer(key, {'song': value.strip()})
            elif field == 'apple_period':
                import datetime as _dt
                _year = _dt.date.today().year
                _years = [str(y) for y in range(_year, _year - 6, -1)]
                choice = st.selectbox(
                    t("upload_csv.ask_apple_period", "Période couverte par cet export"),
                    options=[''] + ['all'] + _years,
                    format_func=lambda v: {
                        '': t("upload_csv.ask_apple_period_ph", "— choisis la période —"),
                        'all': t("upload_csv.apple_period_all", "Depuis le début"),
                    }.get(v, v),
                    key=f"{key}_apple_period_widget",
                )
                if choice:
                    _store_answer(key, {'apple_period': choice})
            else:
                choice = st.selectbox(
                    t("upload_csv.ask_window", "Période couverte par cet export"),
                    options=['', '12m', '28d'],
                    format_func=lambda v: {
                        '': t("upload_csv.ask_window_ph", "— choisis la période —"),
                        '12m': t("upload_csv.window_12m", "12 mois"),
                        '28d': t("upload_csv.window_28d", "28 jours"),
                    }[v],
                    key=f"{key}_window_widget",
                )
                if choice:
                    _store_answer(key, {'window': choice})

    # ── Aperçus (collapse par défaut) ──────────────────────────────
    ok_results = [r for r in file_results if not r['error']]
    if not ok_results:
        if not asked:
            st.error(t("upload_csv.err_no_valid_file",
                       "Aucun fichier valide à importer."))
        return

    # LES APERÇUS PAR FICHIER ONT ÉTÉ RETIRÉS le 2026-09-06 : « le panneau de
    # détection, on consolide tout en un seul tableau, là il y en a plusieurs ».
    #
    # Un dépliant par fichier, c'est quinze dépliants pour un import S4A normal —
    # donc quinze décisions (« dois-je l'ouvrir ? ») pour une information que
    # personne n'a demandée : le tableau au-dessus dit déjà le type détecté et le
    # nombre de lignes, qui sont les deux chiffres sur lesquels on décide.

    # ── Taux USD→EUR (DistroKid paie en USD, le dashboard est en EUR) ──
    fx_rate = None
    if any(r['platform_key'] == 'distrokid_sales' for r in ok_results):
        from src.utils.distrokid_rollup import default_fx_rate
        fx_rate = st.number_input(
            t("upload_csv.fx_label", "Taux de conversion USD → EUR (DistroKid)"),
            min_value=0.0, value=default_fx_rate(), step=0.01, format="%.4f",
            help=t("upload_csv.fx_help",
                   "Les montants DistroKid sont en USD ; les revenus mensuels "
                   "affichés dans Distributeur sont convertis en EUR avec ce taux. "
                   "Défaut : DISTROKID_USD_EUR_RATE (.env) ou 0.92."),
        )

    # ── Confirmation, JUSTE SOUS le tableau ────────────────────────
    n_ok = len(ok_results)
    n_skip = len(file_results) - n_ok
    label = t("upload_csv.import_button", "✅ Importer {n} fichier(s)").format(n=n_ok)
    if n_skip:
        label += t("upload_csv.import_button_skip", "  (⚠️ {n} ignoré(s))").format(n=n_skip)

    # DÉCLENCHEMENT AUTOMATIQUE quand TOUS les fichiers sont reconnus. Demandé le
    # 2026-09-06. Le raisonnement : s'il n'y a rien à trier, il n'y a rien à décider,
    # et un bouton qui n'offre qu'un seul choix n'est pas une décision — c'est une
    # étape de plus. L'artiste du jour a lu « ✅ Prêt » et cru l'import fait ; le
    # journal de production ne portait aucune ligne, parce que ce bouton attendait.
    #
    # Dès qu'UN fichier est refusé, on redemande : là il y a un arbitrage — importer
    # les autres quand même, ou repartir chercher le manquant.
    #
    # L'idempotence tient à la signature du LOT (noms + tailles), pas à un simple
    # drapeau : Streamlit ré-exécute le script à chaque interaction, donc sans elle
    # le même dépôt se réimporterait à chaque clic ailleurs sur la page. Un nouveau
    # dépôt change la signature et redéclenche, ce qui est le comportement voulu.
    _signature = tuple(sorted((r['filename'], len(r['rows'])) for r in ok_results))
    _AUTO_KEY = f"_csv_autoimport_{target_artist_id}"
    _auto = bool(ok_results) and not n_skip and st.session_state.get(_AUTO_KEY) != _signature

    # LE BOUTON EST RENDU DANS TOUS LES CAS, y compris quand le déclenchement
    # automatique va faire le travail au même passage. Demandé le 2026-09-06 :
    # « même si l'import est lancé automatiquement, il faut quand même mettre le
    # bouton pour valider l'action à faire ».
    #
    # Ce n'est pas une redondance : une action qui se produit sans qu'aucun contrôle
    # ne la porte à l'écran ne se distingue pas d'une action qui ne s'est pas
    # produite — c'est exactement ce qui s'est passé le jour où l'artiste a lu
    # « ✅ Prêt » et cru l'import fait. Le bouton nomme le geste ; l'automatisme
    # évite d'avoir à le cliquer quand il n'y a rien à arbitrer.
    _clicked = st.button(label, type="primary", key=f"_csv_import_{target_artist_id}",
                         width="stretch")
    if _auto:
        st.session_state[_AUTO_KEY] = _signature
        st.info(t("upload_csv.auto_import",
                  "🚀 Les {n} fichiers sont reconnus — import lancé automatiquement.")
                .format(n=n_ok))

    if _auto or _clicked:
        # LE TABLEAU DE RÉSULTAT EST LE TABLEAU DE DÉTECTION, complété.
        # Deux tableaux disaient le fichier, le type et un compte à quinze lignes
        # d'intervalle ; celui-ci est le même objet, enrichi en place.
        _row_for = dict(zip([r['filename'] for r in file_results], summary_rows))
        total_ok = 0
        total_err = 0
        # LES MESSAGES D'APRÈS-IMPORT SONT COLLECTÉS, PAS ÉCRITS.
        #
        # Tout ce qui suit se termine par `st.rerun()` — nécessaire pour vider la
        # zone de dépôt — et un rerun efface tout ce qui a été écrit avant lui. Six
        # messages vivaient ici (démarrage de la collecte, référentiel de sorties,
        # agrégations iMusician et DistroKid) : les laisser en `st.success` les
        # aurait rendus invisibles, exactement comme le verdict de sauvegarde l'a
        # été. Ils voyagent donc par la session et sont rendus après le rerun.
        _notes: list[tuple[str, str]] = []

        for r in ok_results:
            cfg = _PLATFORMS[r['platform_key']]
            try:
                # LE COMPTE ÉMIS ET LE COMPTE COMMITÉ SONT DEUX CHIFFRES.
                # On ne disposait que du premier ; le second se mesure ici, à la
                # destination, sans toucher au chemin d'écriture qu'empruntent les
                # seize DAGs. La différence n'est pas une anomalie — un ré-import
                # met à jour sans ajouter, et voir « 0 nouvelle » sur 400 lignes
                # traitées est alors la bonne réponse, pas un silence.
                before = _rows_in_table(db, cfg['table'], target_artist_id)
                count = db.upsert_many(
                    table=cfg['table'],
                    data=r['rows'],
                    conflict_columns=cfg['conflict_columns'],
                    update_columns=cfg['update_columns'],
                )
                total_ok += count
                # LA FUSION SE DIT. `upsert_many` déduplique sur la clé de conflit
                # avant d'écrire, et ne renvoie que ce qui reste : un fichier de
                # 400 lignes pouvait en importer 12 sans que rien ne l'indique à
                # l'écran (seul un `logger.warning` le disait, dans un journal que
                # personne n'ouvre). L'écart entre ce qu'on envoie et ce qu'on
                # reçoit est la seule mesure disponible — on l'affiche.
                merged = len(r['rows']) - count
                added = _rows_in_table(db, cfg['table'], target_artist_id) - before
                # Archived only HERE, in the success branch: `count` is the proof
                # the rows reached the database. A copy of every file that failed
                # to import would fill the directory with the uninteresting case —
                # the one worth keeping is a file that imported cleanly and still
                # produced numbers that look wrong a week later.
                _archive_ok(target_artist_id, r)
                _row_for[r['filename']].update({
                    t("upload_csv.col_rows", "Lignes"): count,
                    t("upload_csv.col_merged", "Fusionnées"): (
                        merged if merged > 0 else ''),
                    t("upload_csv.col_added", "Nouvelles en base"): added,
                    t("upload_csv.col_status", "Statut"): t(
                        "upload_csv.status_imported", "✅ Importé"),
                })
                # LA SÉRIALISATION EST ÉCRITE AUSSI SUR LE SUCCÈS. Un fichier lu
                # avec le mauvais séparateur ne lève pas : il importe des chiffres
                # faux, qu'on relira des semaines plus tard sans rien pour
                # comprendre. C'est le cas où la trace vaut le plus, et c'est
                # précisément celui qu'on ne journalisait pas.
                r['file'].seek(0)
                db.execute_query(
                    "INSERT INTO csv_upload_log "
                    "(artist_id, filename, platform, row_count, status, serialization) "
                    "VALUES (%s, %s, %s, %s, 'success', %s)",
                    (target_artist_id, r['filename'], r['platform_key'], count,
                     _serialization_label(r['file'])),
                )
            except Exception as exc:
                total_err += 1
                _row_for[r['filename']].update({
                    t("upload_csv.col_rows", "Lignes"): 0,
                    t("upload_csv.col_merged", "Fusionnées"): '',
                    t("upload_csv.col_added", "Nouvelles en base"): 0,
                    t("upload_csv.col_status", "Statut"): f'❌ {exc}',
                })
                try:
                    db.execute_query(
                        "INSERT INTO csv_upload_log "
                        "(artist_id, filename, platform, row_count, status, error_message) "
                        "VALUES (%s, %s, %s, 0, 'error', %s)",
                        (target_artist_id, r['filename'], r['platform_key'], str(exc)[:500]),
                    )
                except Exception:
                    pass  # audit log failure must never block the UI

        # DEUX CHOSES APRÈS UN IMPORT, ET ELLES SONT DISTINCTES.
        #
        # 1. Purger les caches (600 s) : sinon l'écran dit « ✅ Importé » et le
        #    chiffre ne bouge pas pendant dix minutes. Voir `cache_invalidation`.
        # 2. Démarrer la collecte SI le parcours vient de se boucler — ici plutôt
        #    que sur un bouton, l'import étant l'un des deux gestes qui le
        #    complètent (avant le 2026-09-06 rien ne partait).
        #
        # Les confondre était le défaut : `autostart_if_journey_complete` ne fait
        # rien une fois la première collecte enregistrée, donc à TOUS les
        # ré-imports — le cas courant d'un locataire installé. S'appuyer sur lui
        # pour purger revenait à ne jamais purger.
        purge_after_write(total_ok)
        _launched = _not_launched = {}
        try:
            from src.dashboard.app import COLLECTION_DAGS
            from src.dashboard.utils.collection_trigger import (
                autostart_if_journey_complete,
            )
            from src.utils import airflow_trigger as _trigger
            _launched, _not_launched = autostart_if_journey_complete(
                db, target_artist_id, st.session_state, _trigger, COLLECTION_DAGS)
        except Exception:  # noqa: BLE001 — un démarrage raté ne casse pas l'import
            pass
        if _launched:
            _notes.append(("success", t(
                "upload_csv.autostart_ok",
                "🚀 Ta configuration est complète — la collecte vient de démarrer "
                "toute seule ({n} sources). Tes premiers chiffres arrivent d'ici "
                "quelques minutes.").format(n=len(_launched))))
        elif _not_launched:
            # On le DIT. Un démarrage automatique qui échoue en silence laisse
            # l'artiste devant une quatrième étape ⬜ sans savoir qu'on a essayé.
            _notes.append(("warning", t(
                "upload_csv.autostart_failed",
                "⚠️ La collecte automatique n'a pas pu démarrer. Lance-la depuis la "
                "barre latérale, ou réessaie plus tard.")))

        # If S4A global summary was imported, rebuild the canonical
        # release-date reference (authoritative source for "latest release"
        # across all platforms). Non-blocking — never fails the import.
        if any(r['platform_key'] == 's4a_songs_global' for r in ok_results):
            try:
                from src.utils.track_matching import rebuild_release_reference
                n_ref = rebuild_release_reference(db, target_artist_id)
                if n_ref:
                    _notes.append(("caption", t(
                        "upload_csv.ref_updated",
                        "🎵 Référentiel de sorties mis à jour ({n} titres).")
                        .format(n=n_ref)))
            except Exception as exc:  # noqa: BLE001 — reference is best-effort
                _notes.append(("caption", t(
                    "upload_csv.ref_failed",
                    "⚠️ Référentiel de sorties non mis à jour : {err}")
                    .format(err=exc)))

        # If an iMusician sales report was imported, roll its per-line detail up
        # into monthly_revenue so the Distributeur view + ROI surface it. Manual
        # entries are preserved. Non-blocking — never fails the import.
        if any(r['platform_key'] == 'imusician_sales' for r in ok_results):
            try:
                from src.utils.imusician_rollup import rollup_sales_to_monthly
                n_months = rollup_sales_to_monthly(db, target_artist_id)
                if n_months:
                    _notes.append(("caption", t(
                        "upload_csv.monthly_aggregated",
                        "💰 Revenus mensuels agrégés ({n} mois) — visibles dans Distributeur.")
                        .format(n=n_months)))
            except Exception as exc:  # noqa: BLE001 — roll-up is best-effort
                _notes.append(("caption", t(
                    "upload_csv.monthly_failed",
                    "⚠️ Agrégation des revenus mensuels non effectuée : {err}")
                    .format(err=exc)))

        # Same monthly roll-up for DistroKid, with the USD→EUR rate chosen above.
        if any(r['platform_key'] == 'distrokid_sales' for r in ok_results):
            try:
                from src.utils.distrokid_rollup import rollup_sales_to_monthly as dk_rollup
                n_months = dk_rollup(db, target_artist_id, fx_rate=fx_rate)
                if n_months:
                    _notes.append(("caption", t(
                        "upload_csv.dk_aggregated",
                        "💰 Revenus DistroKid agrégés ({n} mois, "
                        "taux {rate:.4f}) — visibles dans Distributeur.")
                        .format(n=n_months, rate=fx_rate)))
            except Exception as exc:  # noqa: BLE001 — roll-up is best-effort
                _notes.append(("caption", t(
                    "upload_csv.dk_failed",
                    "⚠️ Agrégation des revenus DistroKid non effectuée : {err}")
                    .format(err=exc)))

        # LE BILAN PASSE PAR LA SESSION, ET LA ZONE DE DÉPÔT EST VIDÉE.
        #
        # Deux demandes du 2026-09-06 qui n'en font qu'une : les quinze fichiers
        # restaient affichés dans la zone de dépôt après l'import, et un écran qui
        # montre encore ce qu'on vient de déposer se lit « rien n'est parti ».
        # Streamlit n'a aucune API pour vider un `file_uploader` — on change la clé
        # du widget, ce qui en crée un neuf, donc vide.
        #
        # Vider impose de relancer le script, et `st.rerun()` efface tout ce qui a
        # été écrit avant lui : le bilan doit donc voyager par la session, comme le
        # verdict de sauvegarde et le démarrage automatique de la collecte avant lui.
        st.session_state[_last_result_key(target_artist_id)] = {
            'rows': summary_rows,
            'n_ok': len(ok_results) - total_err,
            'n_err': total_err,
            'total_rows': total_ok,
            'notes': _notes,
        }
        _clear_uploader(target_artist_id)
        st.rerun()

    # LES GUIDES, TOUT EN BAS. Demandé le 2026-09-06 : « déplace les onglets à
    # dérouler de process pour télécharger en dessous de la détection ».
    #
    # Hors du bloc d'import — donc rendus qu'on ait cliqué ou non : quelqu'un qui
    # vient de voir un fichier refusé a besoin de relire comment l'exporter, et c'est
    # précisément là qu'il est. Repliés, ils ne coûtent rien à qui n'en a pas besoin.
    st.markdown("---")
    from src.dashboard.content.csv_guides_st import render_csv_guides
    render_csv_guides()
