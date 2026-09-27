"""Vue DB Health — Monitoring des imports et de la fraîcheur des données.

Type: Feature
Uses: pg_stat_user_tables (system), collected_at columns across all analytics tables
Depends on: get_db_connection, get_artist_id, is_admin
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date

from src.dashboard.utils import get_db_connection, charts
from src.dashboard.utils.i18n import t
from src.dashboard.auth import get_artist_id, is_admin
from src.database.postgres_handler import validate_table, validate_columns


# ── Dataset registry ──────────────────────────────────────────────────────────
# Each entry: table scoped by artist_id, with collected_at for import tracking.
# s4a_song_timeline carries a per-song "Total" summary row named after the artist;
# CLAUDE.md mandates excluding it via `song NOT ILIKE %ARTIST_NAME_FILTER%` on every
# query, else counts/dates are inflated by that synthetic row.
from src.utils.artist_name_filter import (
    ARTIST_NAME_FILTER as _ARTIST_NAME_FILTER,
)

_DATASETS = [
    {'key': 's4a_timeline',       'table': 's4a_song_timeline',            'label': 'S4A Timeline',
     'song_filter': True},
    {'key': 's4a_global',         'table': 's4a_songs_global',             'label': 'S4A Songs Global'},
    {'key': 's4a_audience',       'table': 's4a_audience',                 'label': 'S4A Audience'},
    {'key': 'meta_insights',      'table': 'meta_insights_performance_day','label': 'Meta Ads Insights'},
    {'key': 'youtube_stats',      'table': 'youtube_video_stats',          'label': 'YouTube Stats'},
    {'key': 'soundcloud',         'table': 'soundcloud_tracks_daily',      'label': 'SoundCloud'},
    {'key': 'instagram',          'table': 'instagram_daily_stats',        'label': 'Instagram'},
    {'key': 'imusician_summary',  'table': 'imusician_release_summary',    'label': 'iMusician Résumé'},
    {'key': 'imusician_sales',    'table': 'imusician_sales_detail',       'label': 'iMusician Ventes'},
    {'key': 'track_pop',          'table': 'track_popularity_history',     'label': 'Popularité Tracks'},
    {'key': 'ml_preds',           'table': 'ml_song_predictions',          'label': 'Prédictions ML',
     'ts_col': 'prediction_date'},  # override: no collected_at on this table
]

_FRESHNESS_ERROR_DAYS = 30   # red


def _load_health(db, artist_id) -> pd.DataFrame:
    """Query summary stats for every dataset: total rows, first/last import date."""
    rows = []
    today = date.today()
    for ds in _DATASETS:
        table = ds['table']
        ts = ds.get('ts_col', 'collected_at')
        # CLAUDE.md rule #8 — explicit allowlist + identifier check before f-string SQL.
        validate_table(table)
        validate_columns([ts])
        conds, params = [], []
        if artist_id:
            conds.append("artist_id = %s")
            params.append(artist_id)
        if ds.get('song_filter'):
            conds.append("song NOT ILIKE %s")
            params.append(f"%{_ARTIST_NAME_FILTER}%")
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        try:
            r = db.fetch_query(
                f"SELECT COUNT(*), MIN({ts}), MAX({ts}) FROM {table}{where}",
                tuple(params),
            )
            total, first_ts, last_ts = r[0] if r else (0, None, None)
            last_date = pd.to_datetime(last_ts).date() if last_ts else None
            first_date = pd.to_datetime(first_ts).date() if first_ts else None
            age_days = (today - last_date).days if last_date else None
        except Exception:
            total, first_date, last_date, age_days = 0, None, None, None

        rows.append({
            'key':        ds['key'],
            'label':      ds['label'],
            'table':      table,
            'total':      int(total or 0),
            'first_date': first_date,
            'last_date':  last_date,
            'age_days':   age_days,
        })
    return pd.DataFrame(rows)


def _load_daily_by_tenant(db, artist_id) -> pd.DataFrame:
    """Rows written per (dataset, tenant, day) over the 8 last COMPLETE days.

    R249 (fiche 72). The complete days only: today is still being collected, and a day
    in progress compared with full days would read as a dip every morning — the same
    reason `alert_monitor.check_row_dips` reads `day < CURRENT_DATE`."""
    frames = []
    for ds in _DATASETS:
        table, ts = ds['table'], ds.get('ts_col', 'collected_at')
        # CLAUDE.md rule #8 — explicit allowlist + identifier check before f-string SQL.
        validate_table(table)
        validate_columns([ts])
        conds = [f"{ts}::date >= CURRENT_DATE - 8", f"{ts}::date < CURRENT_DATE",
                 "artist_id IS NOT NULL"]
        params = []
        if artist_id:
            conds.append("artist_id = %s")
            params.append(artist_id)
        if ds.get('song_filter'):
            conds.append("song NOT ILIKE %s")
            params.append(f"%{_ARTIST_NAME_FILTER}%")
        try:
            df = db.fetch_df(
                f"""SELECT artist_id AS tenant, {ts}::date AS day, COUNT(*) AS n_rows
                    FROM {table} WHERE {" AND ".join(conds)} GROUP BY 1, 2""",
                tuple(params))
        except Exception:                                            # noqa: BLE001
            continue
        if df is not None and not df.empty:
            frames.append(df.assign(dataset=ds['label']))
    if not frames:
        return pd.DataFrame(columns=["dataset", "tenant", "day", "n_rows"])
    return pd.concat(frames, ignore_index=True)


def _show_health_table(df_health: pd.DataFrame):
    st.subheader(t("db_health.table_header", "🏥 État des datasets"))

    # KPI summary row
    populated = df_health[df_health['total'] > 0]
    stale     = populated[populated['age_days'] > _FRESHNESS_ERROR_DAYS]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(t("db_health.kpi_active", "Datasets actifs"),    len(populated))
    k2.metric(t("db_health.kpi_empty", "Datasets vides"),     len(df_health) - len(populated))
    k3.metric(t("db_health.kpi_total_rows", "Total lignes DB"),    f"{df_health['total'].sum():,}")
    k4.metric(t("db_health.kpi_stale", "Datasets obsolètes (>30j)"), len(stale),
              delta=None if stale.empty else "⚠️", delta_color="inverse")

    # Detail table
    col_total = t("db_health.col_total_rows", "Lignes totales")
    col_first = t("db_health.col_first_import", "Premier import")
    col_last  = t("db_health.col_last_import", "Dernier import")
    col_age   = t("db_health.col_age_days", "Âge (jours)")
    display = df_health[[
        'label', 'table', 'total', 'first_date', 'last_date', 'age_days'
    ]].copy()
    display.columns = [
        t("db_health.col_dataset", "Dataset"), t("db_health.col_table", "Table"), col_total,
        col_first, col_last, col_age
    ]
    display[col_total] = display[col_total].apply(lambda x: f"{x:,}")
    display[col_age] = display[col_age].apply(
        lambda x: t("db_health.age_days_suffix", "{n}j").format(n=x) if x is not None else "—"
    )
    display[col_first] = display[col_first].apply(
        lambda x: str(x) if x else "—"
    )
    display[col_last] = display[col_last].apply(
        lambda x: str(x) if x else "—"
    )
    st.dataframe(display, hide_index=True, width='stretch')


# R249 (fiches 70-71, owner 2026-09-27 : « on peut supprimer », « sert à rien ») : the
# freshness bar and the weekly heat-map are gone — the table above carries the same
# dates. Fiche 72 (« détecter les anomalies d'ingestion ») replaces the batch-size chart.

def ingestion_gaps(daily: pd.DataFrame, yesterday: date) -> pd.DataFrame:
    """Per (dataset, tenant): rows EXPECTED yesterday (the mean of the 7 days before) and
    rows RECEIVED, with a verdict. Pure.

    « creux » reuses the nightly check's rule (`volume_monitor.is_partial_collection`:
    fewer than a third of usual, zero excluded). « muet » is zero rows from a feed that
    wrote on at least 5 of those 7 days — a DAILY feed; a weekly CSV import is silent
    most days by nature and must not raise an alert every morning."""
    from src.utils.volume_monitor import MIN_BASELINE_ROWS, is_partial_collection
    cols = ["dataset", "tenant", "expected", "received", "verdict"]
    if daily is None or daily.empty:
        return pd.DataFrame(columns=cols)
    d = daily.assign(day=pd.to_datetime(daily["day"]).dt.date)
    before = [yesterday - pd.Timedelta(days=k).to_pytimedelta() for k in range(1, 8)]
    out = []
    for (ds, tenant), g in d.groupby(["dataset", "tenant"]):
        per_day = g.groupby("day")["n_rows"].sum()
        received = float(per_day.get(yesterday, 0))
        past = [float(per_day.get(x, 0)) for x in before]
        expected = sum(past) / 7
        if is_partial_collection(received, expected):
            verdict = "creux"
        elif received == 0 and sum(v > 0 for v in past) >= 5 and expected >= MIN_BASELINE_ROWS:
            verdict = "muet"
        else:
            verdict = "ok"
        out.append((ds, tenant, expected, received, verdict))
    return pd.DataFrame(out, columns=cols)


def _show_ingestion_gaps(daily: pd.DataFrame) -> None:
    st.subheader(t("db_health.gaps_header", "🚨 Anomalies d'ingestion — attendu contre reçu"))
    st.caption(t("db_health.gaps_caption",
                 "Hier, pour chaque jeu de données : les lignes attendues (moyenne des 7 jours "
                 "d'avant, somme des artistes) contre les lignes reçues. Alerte quand un "
                 "artiste reçoit moins d'un tiers de d'habitude, ou rien sur un flux quotidien."))
    gaps = ingestion_gaps(daily, date.today() - pd.Timedelta(days=1).to_pytimedelta())
    if gaps.empty:
        st.info(t("db_health.no_data", "Aucune donnée disponible."))
        return
    tot = gaps.groupby("dataset")[["expected", "received"]].sum().sort_values("expected")
    fig = go.Figure([
        go.Bar(y=tot.index, x=tot["expected"], orientation="h", marker_color="#c8ced6",
               name=t("db_health.gaps_expected", "Attendu")),
        go.Bar(y=tot.index, x=tot["received"], orientation="h", marker_color="#1f77b4",
               name=t("db_health.gaps_received", "Reçu"),
               text=[f"{v:,.0f}".replace(",", " ") for v in tot["received"]],
               textposition="outside", cliponaxis=False)])
    fig.update_layout(barmode="group", height=max(300, 40 * len(tot) + 120),
                      xaxis_title=t("db_health.gaps_axis", "lignes (hier)"),
                      margin=dict(l=10, r=40, t=20, b=20))
    fig.update_yaxes(automargin=True)   # the dataset names were cut (render, 2026-09-27)
    charts.plotly_chart(fig, width="stretch")
    alerts = gaps[gaps["verdict"] != "ok"]
    if alerts.empty:
        st.success(t("db_health.gaps_none", "✅ Aucune anomalie : chaque artiste a reçu hier "
                                            "au moins un tiers de ses lignes habituelles."))
        return
    st.warning(t("db_health.gaps_alert", "⚠️ {n} anomalie(s) d'ingestion hier :").format(
        n=len(alerts)))
    st.dataframe(alerts.rename(columns={
        "dataset": t("db_health.col_dataset", "Jeu de données"),
        "tenant": t("common.artist", "Artiste"),
        "expected": t("db_health.gaps_expected", "Attendu"),
        "received": t("db_health.gaps_received", "Reçu"),
        "verdict": t("db_health.gaps_verdict", "Constat")}).round(1),
        hide_index=True, width="stretch")


# ── Entrypoint ────────────────────────────────────────────────────────────────

def show():
    st.title(t("db_health.title", "🗄️ Santé des données"))
    st.markdown(t("db_health.intro", "Suivi des imports, de la fraîcheur et des volumes, par jeu de données."))

    # Tenant first, connection second: `st.stop()` raises, and raised between
    # the open and the `try` it skipped the `finally` — the connection leaked on
    # every invalid session. See the same fix in `utils.view_session()`.
    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin():
            st.error(t("db_health.session_invalid", "Session invalide."))
            st.stop()
        artist_id = None  # admin: cross-tenant view

    db = get_db_connection()
    try:
        with st.spinner(t("db_health.spinner", "Chargement des métriques DB…")):
            df_health  = _load_health(db, artist_id)
            df_daily   = _load_daily_by_tenant(db, artist_id)

        _show_health_table(df_health)
        st.markdown("---")
        _show_ingestion_gaps(df_daily)

    finally:
        db.close()
