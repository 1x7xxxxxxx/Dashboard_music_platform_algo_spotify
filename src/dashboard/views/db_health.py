"""Vue DB Health — Monitoring des imports et de la fraîcheur des données.

Type: Feature
Uses: pg_stat_user_tables (system), collected_at columns across all analytics tables
Depends on: get_db_connection, get_artist_id, is_admin
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.ui import show_empty_state
from src.dashboard.auth import get_artist_id, is_admin
from src.database.postgres_handler import validate_table, validate_columns


# ── Dataset registry ──────────────────────────────────────────────────────────
# Each entry: table scoped by artist_id, with collected_at for import tracking.
_DATASETS = [
    {'key': 's4a_timeline',       'table': 's4a_song_timeline',            'label': 'S4A Timeline'},
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

_FRESHNESS_WARN_DAYS  = 14   # orange
_FRESHNESS_ERROR_DAYS = 30   # red


def _freshness_color(days: int | None) -> str:
    if days is None:
        return '#555555'
    if days <= _FRESHNESS_WARN_DAYS:
        return '#1DB954'
    if days <= _FRESHNESS_ERROR_DAYS:
        return '#FFA500'
    return '#FF6B6B'


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
        try:
            if artist_id:
                r = db.fetch_query(
                    f"SELECT COUNT(*), MIN({ts}), MAX({ts}) FROM {table} WHERE artist_id = %s",
                    (artist_id,)
                )
            else:
                r = db.fetch_query(
                    f"SELECT COUNT(*), MIN({ts}), MAX({ts}) FROM {table}"
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


def _load_weekly_activity(db, artist_id) -> pd.DataFrame:
    """For each dataset, count new rows per ISO week (collected_at bucketed to Monday)."""
    frames = []
    for ds in _DATASETS:
        table = ds['table']
        ts = ds.get('ts_col', 'collected_at')
        # CLAUDE.md rule #8 — explicit allowlist + identifier check before f-string SQL.
        validate_table(table)
        validate_columns([ts])
        try:
            if artist_id:
                df = db.fetch_df(
                    f"""SELECT DATE_TRUNC('week', {ts})::date AS week,
                               COUNT(*) AS new_rows
                        FROM {table}
                        WHERE artist_id = %s AND {ts} IS NOT NULL
                        GROUP BY 1 ORDER BY 1""",
                    (artist_id,)
                )
            else:
                df = db.fetch_df(
                    f"""SELECT DATE_TRUNC('week', {ts})::date AS week,
                               COUNT(*) AS new_rows
                        FROM {table}
                        WHERE {ts} IS NOT NULL
                        GROUP BY 1 ORDER BY 1"""
                )
            if not df.empty:
                df['dataset'] = ds['label']
                frames.append(df)
        except Exception:
            pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=['week', 'new_rows', 'dataset']
    )


def _load_cumulative(db, artist_id) -> pd.DataFrame:
    """Cumulative row count per week per dataset (for growth curve chart)."""
    df_weekly = _load_weekly_activity(db, artist_id)
    if df_weekly.empty:
        return df_weekly
    df_weekly['week'] = pd.to_datetime(df_weekly['week'])
    frames = []
    for label, grp in df_weekly.groupby('dataset'):
        grp = grp.sort_values('week').copy()
        grp['cumul'] = grp['new_rows'].cumsum()
        frames.append(grp)
    return pd.concat(frames, ignore_index=True)


# ── Section renderers ─────────────────────────────────────────────────────────

def _show_health_table(df_health: pd.DataFrame):
    st.subheader("🏥 État des datasets")

    # KPI summary row
    populated = df_health[df_health['total'] > 0]
    stale     = populated[populated['age_days'] > _FRESHNESS_ERROR_DAYS]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Datasets actifs",    len(populated))
    k2.metric("Datasets vides",     len(df_health) - len(populated))
    k3.metric("Total lignes DB",    f"{df_health['total'].sum():,}")
    k4.metric("Datasets obsolètes (>30j)", len(stale),
              delta=None if stale.empty else "⚠️", delta_color="inverse")

    # Detail table
    display = df_health[[
        'label', 'table', 'total', 'first_date', 'last_date', 'age_days'
    ]].copy()
    display.columns = [
        'Dataset', 'Table', 'Lignes totales',
        'Premier import', 'Dernier import', 'Âge (jours)'
    ]
    display['Lignes totales'] = display['Lignes totales'].apply(lambda x: f"{x:,}")
    display['Âge (jours)'] = display['Âge (jours)'].apply(
        lambda x: f"{x}j" if x is not None else "—"
    )
    display['Premier import'] = display['Premier import'].apply(
        lambda x: str(x) if x else "—"
    )
    display['Dernier import'] = display['Dernier import'].apply(
        lambda x: str(x) if x else "—"
    )
    st.dataframe(display, hide_index=True, width='stretch')


def _show_freshness_bar(df_health: pd.DataFrame):
    st.subheader("⏱️ Fraîcheur par dataset")
    st.caption("Jours depuis le dernier import — vert ≤14j, orange ≤30j, rouge >30j")

    df = df_health[df_health['total'] > 0].copy()
    if show_empty_state(df, "Aucun dataset peuplé."):
        return

    df = df.sort_values('age_days', ascending=True, na_position='last')
    df['color'] = df['age_days'].apply(_freshness_color)
    df['age_label'] = df['age_days'].apply(lambda x: f"{x}j" if x is not None else "—")

    fig = go.Figure(go.Bar(
        x=df['age_days'].fillna(0),
        y=df['label'],
        orientation='h',
        marker_color=df['color'],
        text=df['age_label'],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>%{x} jours depuis le dernier import<extra></extra>',
    ))
    fig.add_vline(x=_FRESHNESS_WARN_DAYS,  line_dash='dash', line_color='#FFA500',
                  annotation_text=f'{_FRESHNESS_WARN_DAYS}j', annotation_position='top right')
    fig.add_vline(x=_FRESHNESS_ERROR_DAYS, line_dash='dash', line_color='#FF6B6B',
                  annotation_text=f'{_FRESHNESS_ERROR_DAYS}j', annotation_position='top right')
    fig.update_layout(
        height=max(300, len(df) * 42),
        xaxis_title="Jours depuis le dernier import",
        yaxis_title=None,
        margin=dict(l=0, r=60, t=20, b=40),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white',
    )
    st.plotly_chart(fig, width='stretch')


def _show_heatmap(df_weekly: pd.DataFrame):
    st.subheader("📅 Activité d'import — heatmap par semaine")
    st.caption("Chaque cellule = nouvelles lignes intégrées cette semaine. Blanc = aucune activité.")

    if show_empty_state(df_weekly, "Aucune donnée d'activité disponible."):
        return

    df_weekly['week'] = pd.to_datetime(df_weekly['week'])
    # Keep last 52 weeks for readability
    cutoff = pd.Timestamp(date.today()) - pd.Timedelta(weeks=52)
    df_weekly = df_weekly[df_weekly['week'] >= cutoff]

    if show_empty_state(df_weekly, "Aucune activité sur les 52 dernières semaines."):
        return

    pivot = df_weekly.pivot_table(
        index='dataset', columns='week', values='new_rows', aggfunc='sum', fill_value=0
    )
    week_labels = [str(c.date()) for c in pivot.columns]

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=week_labels,
        y=pivot.index.tolist(),
        colorscale='Greens',
        hoverongaps=False,
        hovertemplate='<b>%{y}</b><br>Semaine %{x}<br>%{z:,} lignes<extra></extra>',
        colorbar=dict(title='Lignes', thickness=12),
    ))
    fig.update_layout(
        height=max(300, len(pivot) * 44 + 80),
        xaxis=dict(tickangle=-45, nticks=20),
        yaxis_title=None,
        margin=dict(l=0, r=20, t=20, b=80),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white',
    )
    st.plotly_chart(fig, width='stretch')


def _show_cumulative(df_cumul: pd.DataFrame):
    st.subheader("📈 Croissance cumulative des datasets")
    st.caption("Un plateau = plus aucun import sur ce dataset.")

    if show_empty_state(df_cumul, "Aucune donnée disponible."):
        return

    # Dataset selector
    all_datasets = sorted(df_cumul['dataset'].unique())
    selected = st.multiselect(
        "Datasets à afficher",
        options=all_datasets,
        default=all_datasets,
        key="db_health_cumul_select",
    )
    if not selected:
        return

    df_plot = df_cumul[df_cumul['dataset'].isin(selected)]

    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    for i, (label, grp) in enumerate(df_plot.groupby('dataset')):
        grp = grp.sort_values('week')
        fig.add_trace(go.Scatter(
            x=grp['week'], y=grp['cumul'],
            name=label,
            mode='lines+markers',
            line=dict(color=colors[i % len(colors)], width=2),
            marker=dict(size=5),
            hovertemplate=f'<b>{label}</b><br>%{{x|%Y-%m-%d}}<br>%{{y:,}} lignes cumulées<extra></extra>',
        ))
    fig.update_layout(
        height=420,
        xaxis_title=None,
        yaxis_title="Lignes cumulées",
        hovermode='x unified',
        legend=dict(orientation='h', y=-0.2),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white',
    )
    st.plotly_chart(fig, width='stretch')


def _show_batch_sizes(df_weekly: pd.DataFrame):
    st.subheader("📦 Taille des imports par semaine")
    st.caption("Lots très petits ou très grands peuvent indiquer une anomalie de collecte.")

    if show_empty_state(df_weekly, "Aucune donnée disponible."):
        return

    df_weekly = df_weekly.copy()
    df_weekly['week'] = pd.to_datetime(df_weekly['week'])
    cutoff = pd.Timestamp(date.today()) - pd.Timedelta(weeks=26)
    df_plot = df_weekly[df_weekly['week'] >= cutoff]

    if df_plot.empty:
        st.info("Aucune activité sur les 26 dernières semaines.")
        return

    # Dataset filter
    all_datasets = sorted(df_plot['dataset'].unique())
    selected = st.multiselect(
        "Datasets à afficher",
        options=all_datasets,
        default=all_datasets[:5] if len(all_datasets) > 5 else all_datasets,
        key="db_health_batch_select",
    )
    if not selected:
        return

    df_plot = df_plot[df_plot['dataset'].isin(selected)]
    colors = px.colors.qualitative.Plotly

    fig = go.Figure()
    for i, (label, grp) in enumerate(df_plot.groupby('dataset')):
        grp = grp.sort_values('week')
        fig.add_trace(go.Bar(
            x=grp['week'], y=grp['new_rows'],
            name=label,
            marker_color=colors[i % len(colors)],
            hovertemplate=f'<b>{label}</b><br>%{{x|%Y-%m-%d}}<br>%{{y:,}} nouvelles lignes<extra></extra>',
        ))
    fig.update_layout(
        height=380,
        barmode='group',
        xaxis_title=None,
        yaxis_title="Nouvelles lignes",
        hovermode='x unified',
        legend=dict(orientation='h', y=-0.25),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white',
    )
    st.plotly_chart(fig, width='stretch')


# ── Entrypoint ────────────────────────────────────────────────────────────────

def show():
    st.title("🗄️ Santé des données")
    st.markdown("Suivi des imports, fraîcheur et volumes par dataset PostgreSQL.")

    db = get_db_connection()
    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin():
            st.error("Session invalide.")
            st.stop()
        artist_id = None  # admin: cross-tenant view

    try:
        with st.spinner("Chargement des métriques DB…"):
            df_health  = _load_health(db, artist_id)
            df_weekly  = _load_weekly_activity(db, artist_id)
            df_cumul   = _load_cumulative(db, artist_id)

        _show_health_table(df_health)
        st.markdown("---")
        _show_freshness_bar(df_health)
        st.markdown("---")
        _show_heatmap(df_weekly)
        st.markdown("---")
        _show_cumulative(df_cumul)
        st.markdown("---")
        _show_batch_sizes(df_weekly)

    finally:
        db.close()
