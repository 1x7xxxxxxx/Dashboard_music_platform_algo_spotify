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

_ALLOWED_TABLES = frozenset({
    "meta_insights_performance_day",
    "apple_songs_history",
    "youtube_channel_history",
    "soundcloud_tracks_daily",
    "instagram_daily_stats",
    "instagram_media",
    "s4a_song_timeline",
    "hypeddit_daily_stats",
})
_ALLOWED_DATE_COLUMNS = frozenset({
    "day_date", "date", "collected_at", "first_seen", "timestamp",
})
_ALLOWED_ARTIST_COLUMNS = frozenset({"artist_id"})
# Entity (track/song) label columns the entity_period_filter may select on.
_ALLOWED_ENTITY_COLUMNS = frozenset({"title", "song_name", "song"})

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
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"smart_period_filter: table '{table}' not in allowlist")
    if date_column not in _ALLOWED_DATE_COLUMNS:
        raise ValueError(f"smart_period_filter: date_column '{date_column}' not in allowlist")
    if artist_column not in _ALLOWED_ARTIST_COLUMNS:
        raise ValueError(f"smart_period_filter: artist_column '{artist_column}' not in allowlist")


def _data_span(
    db: PostgresHandler, table: str, date_column: str,
    artist_column: str, artist_id: Optional[int],
) -> tuple[Optional[_dt.date], Optional[_dt.date]]:
    sql = f"SELECT MIN({date_column})::date, MAX({date_column})::date FROM {table} WHERE 1=1"
    params: tuple = ()
    if artist_id is not None:
        sql += f" AND {artist_column} = %s"
        params = (artist_id,)
    rows = db.fetch_query(sql, params or None)
    if rows and rows[0][0] is not None:
        return rows[0][0], rows[0][1]
    return None, None


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
        return PeriodWindow(s, e, f"{s:%d/%m/%Y} → {e:%d/%m/%Y}", "custom", False)
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
    (e.g. soundcloud `title`, apple `song_name`). Release date per entity is
    `MIN(date_column)` — the same time-series column the period span uses.
    """
    table: str
    entity_column: str
    date_column: str
    multi: bool = True
    default_count: int = 1


def _validate_entity(spec: EntitySpec) -> None:
    _validate(spec.table, spec.date_column, "artist_id")
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


def _entity_options(
    db: PostgresHandler, spec: EntitySpec, artist_id: Optional[int],
) -> list:
    sql = (
        f"SELECT {spec.entity_column} FROM {spec.table} WHERE 1=1"
        + (" AND artist_id = %s" if artist_id is not None else "")
        + f" GROUP BY {spec.entity_column} "
        f"ORDER BY MIN({spec.date_column}) DESC NULLS LAST"
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
):
    """Render entity selector + the shared period filter (release-anchored).

    Returns `(selection, PeriodWindow)` — `selection` is a list when
    `spec.multi`, else a scalar (or None). Replaces the per-view duplicated
    resolver/sort/key wiring; the period UI is the unchanged smart_period_filter.
    """
    _validate_entity(spec)
    options = _entity_options(db, spec, artist_id)
    default = _entity_default(options, spec.multi, spec.default_count)

    if spec.multi:
        selection = st.multiselect(
            label, options, default=default, key=f"{key_prefix}_ent",
        )
    else:
        idx = options.index(default) if default in options else 0
        selection = st.selectbox(
            label, options, index=idx if options else None,
            key=f"{key_prefix}_ent",
        )

    sel_list = selection if spec.multi else ([selection] if selection else [])
    primary = sel_list[0] if sel_list else (options[0] if options else None)

    def _release_resolver() -> Optional[_dt.date]:
        if not sel_list:
            return None
        rows = db.fetch_query(
            f"SELECT MIN({spec.date_column})::date FROM {spec.table} "
            f"WHERE artist_id = %s AND {spec.entity_column} = ANY(%s)",
            (artist_id, sel_list),
        )
        return rows[0][0] if rows and rows[0][0] else None

    window = smart_period_filter(
        db, table=spec.table, date_column=spec.date_column,
        artist_id=artist_id, key=_entity_key(key_prefix, primary),
        latest_release_resolver=_release_resolver,
    )
    return selection, window
