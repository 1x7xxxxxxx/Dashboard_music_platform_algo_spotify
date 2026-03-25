"""ETL Run History — dashboard view for etl_run_log + circuit breaker state.

Shows:
  - Summary KPIs: total runs, success rate, avg duration
  - Run history table (last 200 rows) with color-coded status
  - Per-DAG trend chart: runs per day × status
  - Circuit breaker state panel with admin reset buttons
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import is_admin

STATUS_COLORS = {
    'success': '#27ae60',
    'partial': '#f39c12',
    'failed':  '#e74c3c',
    'running': '#3498db',
    'skipped': '#95a5a6',
}

CIRCUIT_COLORS = {
    'closed':    '#27ae60',
    'open':      '#e74c3c',
    'half_open': '#f39c12',
}


def show():
    if not is_admin():
        st.error("🔒 Accès réservé aux administrateurs.")
        return

    st.title("🗂️ Historique ETL")
    st.caption("Logs des runs Airflow persistés en base — table `etl_run_log`")

    db = get_db_connection()
    if db is None:
        st.error("❌ Base de données inaccessible.")
        return

    try:
        _section_kpis(db)
        st.markdown("---")
        _section_run_history(db)
        st.markdown("---")
        _section_trend(db)
        st.markdown("---")
        _section_circuit_breakers(db)
    finally:
        db.close()


# ── KPIs ─────────────────────────────────────────────────────────

def _section_kpis(db):
    rows = db.fetch_query(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'success')  AS ok,
            COUNT(*) FILTER (WHERE status = 'failed')   AS failed,
            COUNT(*) FILTER (WHERE status = 'partial')  AS partial,
            ROUND(AVG(duration_ms) FILTER (WHERE duration_ms IS NOT NULL))::int AS avg_ms,
            SUM(rows_inserted) AS total_rows
        FROM etl_run_log
        WHERE started_at >= NOW() - INTERVAL '7 days'
        """
    )
    if not rows or not rows[0][0]:
        st.info("Aucun run enregistré dans les 7 derniers jours. "
                "Vérifiez que `DagRunLogger` est utilisé dans vos DAGs.")
        return

    total, ok, failed, partial, avg_ms, total_rows = rows[0]
    success_rate = round(100 * (ok or 0) / total, 1) if total else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Runs (7j)", total)
    c2.metric("Taux succès", f"{success_rate}%",
              delta=f"{ok} OK / {failed} KO",
              delta_color="normal")
    c3.metric("Durée moyenne", f"{avg_ms or 0:,} ms")
    c4.metric("Lignes insérées", f"{int(total_rows or 0):,}")
    c5.metric("Runs en échec", failed,
              delta_color="inverse")


# ── Run history table ─────────────────────────────────────────────

def _section_run_history(db):
    st.subheader("Derniers runs")

    # Filters
    col_dag, col_status, col_days = st.columns(3)
    dag_filter = col_dag.text_input("Filtrer par DAG", placeholder="ex: soundcloud")
    status_filter = col_status.selectbox(
        "Statut", ["Tous", "success", "failed", "partial", "running", "skipped"]
    )
    days = col_days.slider("Fenêtre (jours)", 1, 30, 7)

    conditions = ["started_at >= NOW() - INTERVAL '%s days'" % days]
    params = []
    if dag_filter:
        conditions.append("dag_id ILIKE %s")
        params.append(f'%{dag_filter}%')
    if status_filter != "Tous":
        conditions.append("status = %s")
        params.append(status_filter)

    where = " AND ".join(conditions)
    df = db.fetch_df(
        f"""
        SELECT
            id,
            dag_id,
            platform,
            artist_id,
            status,
            rows_inserted,
            rows_failed,
            duration_ms,
            started_at,
            error_type,
            error_message
        FROM etl_run_log
        WHERE {where}
        ORDER BY started_at DESC
        LIMIT 200
        """,
        tuple(params) if params else None,
    )

    if df.empty:
        st.info("Aucun run correspondant.")
        return

    # Format columns
    df['started_at'] = pd.to_datetime(df['started_at']).dt.strftime('%d/%m %H:%M')
    df['duration'] = df['duration_ms'].apply(
        lambda ms: f"{ms:,} ms" if pd.notna(ms) else "—"
    )
    df['status_badge'] = df['status'].apply(
        lambda s: f":{_st_color(s)}[{s}]"
    )

    display_cols = ['dag_id', 'platform', 'artist_id', 'status',
                    'rows_inserted', 'rows_failed', 'duration', 'started_at', 'error_type']
    st.dataframe(
        df[display_cols],
        hide_index=True,
        width='stretch',
        column_config={
            'status': st.column_config.TextColumn('Status'),
            'rows_inserted': st.column_config.NumberColumn('Rows OK'),
            'rows_failed': st.column_config.NumberColumn('Rows KO'),
            'duration': st.column_config.TextColumn('Durée'),
            'dag_id': st.column_config.TextColumn('DAG'),
            'started_at': st.column_config.TextColumn('Démarré'),
        },
    )

    # Expandable error details
    failed_df = df[df['status'] == 'failed']
    if not failed_df.empty:
        with st.expander(f"❌ Détail des {len(failed_df)} erreurs"):
            for _, row in failed_df.iterrows():
                st.markdown(
                    f"**{row['dag_id']}** `{row['started_at']}` — "
                    f"`{row['error_type'] or '?'}`: {row['error_message'] or '—'}"
                )


# ── Trend chart ───────────────────────────────────────────────────

def _section_trend(db):
    st.subheader("Tendance par DAG (14 jours)")

    df = db.fetch_df(
        """
        SELECT
            DATE(started_at) AS day,
            dag_id,
            status,
            COUNT(*) AS runs
        FROM etl_run_log
        WHERE started_at >= NOW() - INTERVAL '14 days'
        GROUP BY day, dag_id, status
        ORDER BY day
        """
    )
    if df.empty:
        st.info("Pas assez de données pour afficher la tendance.")
        return

    df['day'] = pd.to_datetime(df['day'])
    fig = px.bar(
        df,
        x='day',
        y='runs',
        color='status',
        facet_col='dag_id',
        facet_col_wrap=3,
        color_discrete_map=STATUS_COLORS,
        labels={'runs': 'Runs', 'day': 'Date', 'status': 'Statut'},
        height=400,
    )
    fig.update_layout(margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)


# ── Circuit breakers ──────────────────────────────────────────────

def _section_circuit_breakers(db):
    st.subheader("🔌 Circuit Breakers")
    st.caption(
        "Si un circuit est OPEN, le DAG correspondant skip la collecte "
        "pour éviter de brûler des retries sur des credentials connus-cassés."
    )

    rows = db.fetch_query(
        """
        SELECT platform, artist_id, state, failure_count,
               last_failure_at, reset_at, last_error, updated_at
        FROM etl_circuit_breaker
        ORDER BY state DESC, failure_count DESC
        """
    )

    if not rows:
        st.success("✅ Aucun circuit breaker enregistré — toutes les plateformes sont en fonctionnement normal.")
        return

    for row in rows:
        platform, artist_id, state, failures, last_fail, reset_at, last_error, updated = row
        color = CIRCUIT_COLORS.get(state, '#888')
        icon = '🔴' if state == 'open' else ('🟡' if state == 'half_open' else '🟢')

        with st.container():
            col_info, col_btn = st.columns([5, 1])
            with col_info:
                st.markdown(
                    f"{icon} **{platform}** (artiste #{artist_id}) — "
                    f"<span style='color:{color};font-weight:bold'>{state.upper()}</span> "
                    f"— {failures} échec(s)",
                    unsafe_allow_html=True,
                )
                if last_fail:
                    st.caption(
                        f"Dernier échec : {pd.to_datetime(last_fail).strftime('%d/%m %H:%M')} | "
                        + (f"Prochain retry : {pd.to_datetime(reset_at).strftime('%d/%m %H:%M')}" if reset_at else "")
                    )
                if last_error:
                    st.caption(f"Erreur : {last_error[:120]}")

            with col_btn:
                if state != 'closed' and st.button("↺ Reset", key=f"cb_{platform}_{artist_id}"):
                    try:
                        from src.utils.circuit_breaker import reset_circuit
                        reset_circuit(platform, artist_id)
                        st.success(f"Circuit {platform} réinitialisé.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur : {e}")


def _st_color(status: str) -> str:
    return {
        'success': 'green',
        'partial': 'orange',
        'failed':  'red',
        'running': 'blue',
        'skipped': 'gray',
    }.get(status, 'gray')
