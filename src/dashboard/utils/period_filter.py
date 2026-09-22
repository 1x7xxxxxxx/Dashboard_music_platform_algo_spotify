"""
Type: Utility
Uses: streamlit, PostgresHandler (passed in — never opens its own connection)
Depends on: src.database.postgres_handler.PostgresHandler
Persists in: nothing (read-only span query on the caller's connection)
Triggers: rendered inside a view's show(); reruns on widget change

Unified "smart + simple" period filter shared by every dashboard view.

Auto-default heuristic: query the source's data span for the current artist;
if history <= 90 days -> current month, else current year. Presets: current
week/month/year, since last release, all history, custom range.

SQL safety: table / date_column / artist_column are validated against module
frozensets before any interpolation (CLAUDE.md rule #8); the artist value is
always %s-parameterized. The span query runs on the caller's `db` (no second
connection — CLAUDE.md rule #9); no @st.cache_data (a single indexed MIN/MAX
aggregate is cheaper than the unhashable-handler / extra-connection workarounds
caching would require).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

from src.database.postgres_handler import PostgresHandler
from src.dashboard.utils.date_format import format_date

# ⚠️ UNE TABLE À FILTRE OBLIGATOIRE N'ENTRE PAS ICI.
#
# `_data_span` interpole ce nom dans un `SELECT MIN(...), MAX(...) FROM {table}` SANS
# aucun prédicat métier. Tant que `s4a_song_timeline` y figurait, l'étendue proposée
# par le sélecteur de période était celle de TOUTE la table — ligne « Total » des CSV
# comprise, et tous titres confondus, alors que la figure d'à côté ne trace qu'un
# titre. La règle transverse #8 du dépôt impose `AND song NOT ILIKE '%1x7xxxxxxx%'`
# sur toute lecture de cette table ; une f-string qui ne porte aucun prédicat ne peut
# structurellement pas la respecter.
#
# Le correctif n'est PAS d'ajouter le filtre ici — un garde textuel ne verrait jamais
# le défaut, parce que le SQL recousu par `ast.JoinedStr` vaut littéralement
# « SELECT MIN( )::date, MAX( )::date FROM  WHERE 1=1 » : le nom de la table n'y
# apparaît pas. Le correctif est que seules des VUES OR entrent dans cette liste.
# Elles portent leurs prédicats en elles, donc la question ne se pose plus.
#
# Classe : `a-span-read-from-a-table-that-carries-a-mandatory-filter`.
_ALLOWED_TABLES = frozenset({
    "meta_insights_performance_day",
    "youtube_channel_history",
    # Ajoutée le 2026-09-21 : « Top Contenus » bornait les vidéos par sa PROPRE
    # liste de préréglages. Un sélecteur par page est une définition de « période »
    # par page — et celle-ci ne bornait pas sur l'étendue réelle, donc laissait
    # choisir une fenêtre vide.
    "youtube_videos",
    "soundcloud_tracks_daily",
    "instagram_daily_stats",
    "instagram_media",
    "hypeddit_daily_stats",
    # Couche or — ces relations portent leurs règles (retrait de la ligne « Total »,
    # déduplication par (date, titre), locataire non nul) et sont donc sûres à borner.
    "v_s4a_song_daily",
    "v_s4a_audience_daily",
    "v_s4a_release_cohort",
    "v_apple_song_cumulative",
})

# Les tables retirées de l'allowlist, avec la vue qui les remplace. Nommer le
# remplacement évite qu'on remette la table « parce que ça marchait avant ».
# ⚠️ LA RAISON EST PAR TABLE, pas commune — corrigé le 2026-09-21.
#
# Le message d'erreur en disait UNE pour toutes : « son étendue inclurait la ligne
# "Total" et tous les titres ». C'est vrai des deux tables S4A et FAUX de la
# troisième, dont le défaut est d'un autre genre. Un garde qui refuse pour la
# mauvaise raison envoie le lecteur chercher le mauvais problème — et ici il
# l'aurait envoyé chercher un filtre manquant là où la table n'a simplement plus
# d'écrivain.
_REPLACED_BY_GOLD = {
    "s4a_song_timeline": (
        "v_s4a_song_daily",
        "son étendue inclurait la ligne « Total » des CSV et les doublons "
        "(date, titre) — deux règles que la vue or applique"),
    "s4a_audience": (
        "v_s4a_audience_daily",
        "son étendue inclurait la ligne « Total » des CSV"),
    # Retirée le 2026-09-21, et pas pour une règle oubliée : `apple_songs_history`
    # n'est écrite par RIEN. Déclarée, autorisée ici, lue par trois surfaces,
    # alimentée par personne — l'import CSV écrit `apple_songs_performance`. Un
    # artiste a donc lu « la dernière mesure remonte au 2025-12-11 » le jour même
    # où il déposait un export.
    "apple_songs_history": (
        "v_apple_song_cumulative",
        "plus RIEN ne l'écrit depuis des mois — l'import CSV alimente "
        "`apple_songs_performance`, et la vue or réunit les deux (migration 131)"),
}
_ALLOWED_DATE_COLUMNS = frozenset({
    # `day` est la colonne de date des VUES de la couche or (`v_s4a_song_daily`,
    # `v_platform_levels`). Une surface qui lit la couche or plutôt que le fait doit
    # pouvoir se borner comme les autres — sans ça, le seul moyen de filtrer une
    # période était de revenir à la table brute, ce qui est exactement l'inverse du
    # but. Ajoutée le 2026-09-12 avec la migration 105.
    "day_date", "date", "day", "month", "collected_at", "first_seen", "timestamp",
    "track_created_at", "published_at",
})
_ALLOWED_ARTIST_COLUMNS = frozenset({"artist_id"})
# Entity (track/song) label columns the entity_period_filter may select on.
# Les colonnes sur lesquelles une étendue peut être RESTREINTE à ce qui est tracé.
# `match_key` sert la couche or des sorties (migration 119), où l'entité n'est plus
# un nom d'affichage mais la clé canonique.
_ALLOWED_ENTITY_COLUMNS = frozenset({"title", "song_name", "song", "match_key"})

_PRESETS = {
    "current": "📅 En cours",
    "last_release": "🚀 Depuis dernière release",
    "all": "♾️ Tout l'historique",
    "custom": "🎯 Plage personnalisée",
}
_GRAINS = {"week": "Semaine", "month": "Mois", "year": "Année"}


@dataclass(frozen=True)
class PeriodWindow:
    start: _dt.date
    end: _dt.date
    label: str
    preset_key: str
    is_all_history: bool

    def sql_between(self, column: str) -> tuple[str, tuple]:
        """`(' AND col BETWEEN %s AND %s ', (start, end))` — `('', ())` if all-history."""
        if column not in _ALLOWED_DATE_COLUMNS:
            raise ValueError(f"PeriodWindow.sql_between: column '{column}' not allowed")
        if self.is_all_history:
            return "", ()
        return f" AND {column} BETWEEN %s AND %s ", (self.start, self.end)


def _validate(table: str, date_column: str, artist_column: str) -> None:
    if table in _REPLACED_BY_GOLD:
        remplacement, pourquoi = _REPLACED_BY_GOLD[table]
        raise ValueError(
            f"smart_period_filter: '{table}' ne peut pas être bornée directement — "
            f"{pourquoi}. Utilise '{remplacement}'.")
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"smart_period_filter: table '{table}' not in allowlist")
    if date_column not in _ALLOWED_DATE_COLUMNS:
        raise ValueError(f"smart_period_filter: date_column '{date_column}' not in allowlist")
    if artist_column not in _ALLOWED_ARTIST_COLUMNS:
        raise ValueError(f"smart_period_filter: artist_column '{artist_column}' not in allowlist")


def _data_span(
    db: PostgresHandler, table: str, date_column: str,
    artist_column: str, artist_id: Optional[int],
    entity_column: Optional[str] = None, entity_value: Optional[str] = None,
) -> tuple[Optional[_dt.date], Optional[_dt.date]]:
    """L'étendue de CE QUI EST TRACÉ, pas celle de la table.

    Sans `entity_column`, le sélecteur proposait à un titre mesuré sur 646 jours
    l'étendue de tous les titres réunis. L'utilisateur croit alors choisir dans une
    fenêtre qui existe, et obtient une figure vide sur ses bords.
    """
    if entity_column is not None and entity_column not in _ALLOWED_ENTITY_COLUMNS:
        raise ValueError(f"_data_span: entity_column '{entity_column}' not in allowlist")
    sql = f"SELECT MIN({date_column})::date, MAX({date_column})::date FROM {table} WHERE 1=1"
    params: tuple = ()
    if artist_id is not None:
        sql += f" AND {artist_column} = %s"
        params = (artist_id,)
    if entity_column is not None and entity_value is not None:
        sql += f" AND {entity_column} = %s"
        params = (*params, entity_value)
    rows = db.fetch_query(sql, params or None)
    if rows and rows[0][0] is not None:
        return rows[0][0], rows[0][1]
    return None, None


def latest_release_date(db, artist_id: Optional[int]) -> Optional[_dt.date]:
    """La date de la DERNIÈRE sortie du locataire — une seule définition.

    Ajoutée le 2026-09-21. La demande était « pour la croissance quotidienne,
    mets la dernière release en automatique — fais ça pour toute l'app », et le
    mot qui compte est *toute* : un défaut appliqué page par page devient une
    définition par page. Celle-ci est la référence canonique
    (`track_release_reference`, nourrie par les dates S4A), la même que le
    mapping cross-plateforme et la cohorte de sorties.

    Rend `None` sans référence — le sélecteur retombe alors sur le début de
    l'historique et le DIT, ce qui est le bon comportement pour un compte neuf :
    une fenêtre ancrée sur une sortie qui n'existe pas serait vide.
    """
    if artist_id is None:
        return None
    try:
        rows = db.fetch_query(
            "SELECT MAX(release_date)::date FROM track_release_reference "
            "WHERE artist_id = %s AND release_date IS NOT NULL", (artist_id,))
    except Exception:      # noqa: BLE001 — une fenêtre par défaut ne casse pas une page
        return None
    return rows[0][0] if rows and rows[0][0] else None


def _default_preset(
    span_days: Optional[int], override: Optional[str],
) -> tuple[str, str]:
    """Return (preset_key, grain) for the initial selection."""
    if override in _PRESETS:
        return override, "year"
    if span_days is not None and span_days <= 90:
        return "current", "month"
    return "current", "year"


def _resolve_window(
    preset: str, grain: str, today: _dt.date,
    span_min: Optional[_dt.date], span_max: Optional[_dt.date],
    latest_release: Optional[_dt.date],
    custom: Optional[tuple[_dt.date, _dt.date]],
) -> PeriodWindow:
    """Pure resolution — no Streamlit. Unit-tested directly."""
    floor = span_min or today
    if preset == "all":
        return PeriodWindow(floor, span_max or today, _PRESETS["all"], "all", True)
    if preset == "custom" and custom:
        s, e = custom
        return PeriodWindow(s, e, f"{format_date(s)} → {format_date(e)}", "custom", False)
    if preset == "last_release":
        start = latest_release or floor
        return PeriodWindow(start, today, _PRESETS["last_release"], "last_release", False)
    if grain == "week":
        start = today - _dt.timedelta(days=today.weekday())
    elif grain == "year":
        start = today.replace(month=1, day=1)
    else:
        start = today.replace(day=1)
    return PeriodWindow(start, today, f"{_GRAINS[grain]} en cours", "current", False)


def smart_period_filter(
    db: PostgresHandler,
    *,
    table: str,
    date_column: str,
    artist_id: Optional[int],
    key: str,
    latest_release: Optional[_dt.date] = None,
    latest_release_resolver: Optional[Callable[[], Optional[_dt.date]]] = None,
    default_override: Optional[str] = None,
    artist_column: str = "artist_id",
) -> PeriodWindow:
    """Render the shared period selector and return the resolved window."""
    _validate(table, date_column, artist_column)
    # Toutes les clés de CE sélecteur portent le locataire, pour la raison écrite dans
    # `_widget_key` : une plage de dates ou un grain choisis pour un artiste ne doivent
    # pas être réinjectés dans la page d'un autre.
    key = _widget_key(key, artist_id)
    span_min, span_max = _data_span(db, table, date_column, artist_column, artist_id)
    span_days = (span_max - span_min).days if span_min and span_max else None
    init_preset, init_grain = _default_preset(span_days, default_override)

    preset = st.segmented_control(
        "Période", list(_PRESETS), key=f"{key}_preset",
        format_func=lambda k: _PRESETS[k], default=init_preset,
    ) or init_preset

    grain = init_grain
    if preset == "current":
        grain = st.segmented_control(
            "Granularité", list(_GRAINS), key=f"{key}_grain",
            format_func=lambda g: _GRAINS[g], default=init_grain,
        ) or init_grain

    custom = None
    if preset == "custom":
        rng = st.date_input(
            "Plage", value=(span_min or st.session_state.get("_today", _dt.date.today()),
                            span_max or _dt.date.today()),
            format="DD/MM/YYYY", key=f"{key}_custom",
        )
        if isinstance(rng, tuple) and len(rng) == 2:
            custom = rng
        else:
            st.info("Sélectionnez une date de fin."); st.stop()

    if preset == "last_release" and latest_release is None and latest_release_resolver:
        latest_release = latest_release_resolver()
    if preset == "last_release" and latest_release is None:
        st.caption("Date de release inconnue — début de l'historique utilisé.")

    return _resolve_window(
        preset, grain, _dt.date.today(), span_min, span_max, latest_release, custom,
    )


@dataclass(frozen=True)
class EntitySpec:
    """Per-view declaration for a release-anchored entity + period selector.

    `entity_column` is the label users pick and downstream queries filter on
    (e.g. soundcloud `title`, apple `song_name`). "Latest release" ordering uses
    `MIN(release_column)`; if `release_column` is None it falls back to
    `date_column` (the time-series column the period span uses). Set
    `release_column` to a true upload/release date (e.g. soundcloud
    `track_created_at`) when `date_column` is merely the ingest time.
    """
    table: str
    entity_column: str
    date_column: str
    multi: bool = True
    default_count: int = 1
    release_column: Optional[str] = None

    @property
    def _release_col(self) -> str:
        return self.release_column or self.date_column


def _validate_entity(spec: EntitySpec) -> None:
    _validate(spec.table, spec.date_column, "artist_id")
    if spec._release_col not in _ALLOWED_DATE_COLUMNS:
        raise ValueError(
            f"entity_period_filter: release_column '{spec._release_col}' not in allowlist"
        )
    if spec.entity_column not in _ALLOWED_ENTITY_COLUMNS:
        raise ValueError(
            f"entity_period_filter: entity_column '{spec.entity_column}' not in allowlist"
        )


def _entity_default(options: list, multi: bool, n: int):
    """Pure: latest-N (multi) or latest (single) from release-DESC options."""
    if not options:
        return [] if multi else None
    return options[:max(1, n)] if multi else options[0]


def _entity_key(prefix: str, primary: Optional[str]) -> str:
    return f"{prefix}_{primary or 'all'}"


def _widget_key(prefix: str, artist_id: Optional[int]) -> str:
    """La clé d'un widget porte TOUJOURS le locataire.

    `key_prefix` est une constante par vue (« apple_daily », « sc »), jamais scopée.
    Or `st.session_state` persiste entre les changements de page dans la même session
    du navigateur : un administrateur qui choisit un titre sur l'artiste A puis ouvre
    la même page pour l'artiste B retrouve la valeur de A injectée dans le widget de B.
    Si ce titre n'existe pas dans le catalogue de B, Streamlit lève sur une valeur par
    défaut hors options — la page ne s'affiche plus.

    L'accueil applique déjà cette convention (`home_trend_mode_{artist_id}`) ; elle
    n'avait pas été étendue ici.
    """
    return f"{prefix}_{artist_id or 'na'}"


def _entity_options(
    db: PostgresHandler, spec: EntitySpec, artist_id: Optional[int],
) -> list:
    sql = (
        f"SELECT {spec.entity_column} FROM {spec.table} WHERE 1=1"
        + (" AND artist_id = %s" if artist_id is not None else "")
        + f" GROUP BY {spec.entity_column} "
        f"ORDER BY MIN({spec._release_col}) DESC NULLS LAST"
    )
    rows = db.fetch_query(sql, (artist_id,) if artist_id is not None else None)
    return [r[0] for r in rows] if rows else []


def entity_period_filter(
    db: PostgresHandler,
    *,
    spec: EntitySpec,
    artist_id: Optional[int],
    key_prefix: str,
    label: str = "Filtrer",
    default_override: Optional[str] = "last_release",
    preferred_default=None,
):
    """Render entity selector + the shared period filter (release-anchored).

    Returns `(selection, PeriodWindow)` — `selection` is a list when
    `spec.multi`, else a scalar (or None). Replaces the per-view duplicated
    resolver/sort/key wiring; the period UI is the unchanged smart_period_filter.
    """
    _validate_entity(spec)
    options = _entity_options(db, spec, artist_id)
    default = _entity_default(options, spec.multi, spec.default_count)

    # `preferred_default` — 2026-09-21. Le classement par date de sortie n'est pas
    # toujours le bon défaut : sur SoundCloud, `track_created_at` est la date
    # d'UPLOAD, et le titre le plus récemment uploadé du locataire 1 porte
    # **4 écoutes et 0 like**. La page s'ouvrait donc sur son titre le plus vide.
    #
    # ⚠️ IL PASSE PAR `default=`, PAS PAR `st.session_state`. Pré-remplir l'état
    # d'un widget qui reçoit AUSSI un `default=` déclenche l'avertissement
    # Streamlit « created with a default value but also had its value set via the
    # Session State API » — et le comportement y est non spécifié. Le premier jet
    # faisait exactement ça. Ici l'appelant propose, le widget dispose, et un choix
    # ultérieur de l'artiste écrase le tout par le mécanisme normal.
    if preferred_default is not None:
        voulus = ([preferred_default] if not isinstance(preferred_default, (list, tuple))
                  else list(preferred_default))
        retenus = [v for v in voulus if v in options]
        if retenus:
            default = retenus if spec.multi else retenus[0]

    if spec.multi:
        selection = st.multiselect(
            label, options, default=default,
            key=_widget_key(f"{key_prefix}_ent", artist_id),
        )
    else:
        idx = options.index(default) if default in options else 0
        selection = st.selectbox(
            label, options, index=idx if options else None,
            key=_widget_key(f"{key_prefix}_ent", artist_id),
        )

    sel_list = selection if spec.multi else ([selection] if selection else [])
    primary = sel_list[0] if sel_list else (options[0] if options else None)

    def _release_resolver() -> Optional[_dt.date]:
        if not sel_list:
            return None
        rows = db.fetch_query(
            f"SELECT MIN({spec._release_col})::date FROM {spec.table} "
            f"WHERE artist_id = %s AND {spec.entity_column} = ANY(%s)",
            (artist_id, sel_list),
        )
        return rows[0][0] if rows and rows[0][0] else None

    # DÉFAUT « DEPUIS LA DERNIÈRE SORTIE » — 2026-09-21, pour toute l'app.
    #
    # Sans lui, `_default_preset(span, None)` rendait « en cours » : l'année (ou
    # le mois) civile en cours. Mesuré ce jour-là sur Apple, dont les relevés
    # sont espacés de plusieurs mois : la page n'affichait **qu'un seul point**,
    # et donc aucun gain, sur un titre qui en a trois. Une fenêtre calendaire est
    # le mauvais cadre pour une donnée qu'on dépose à la main.
    #
    # L'ancre reste l'entité choisie quand elle en a une (`_release_resolver`) ;
    # sinon on retombe sur la dernière sortie du locataire, puis sur le début de
    # l'historique. Trois crans, du plus précis au plus sûr.
    window = smart_period_filter(
        db, table=spec.table, date_column=spec.date_column,
        artist_id=artist_id, key=_entity_key(key_prefix, primary),
        latest_release_resolver=(
            lambda: _release_resolver() or latest_release_date(db, artist_id)),
        default_override=default_override,
    )
    return selection, window
