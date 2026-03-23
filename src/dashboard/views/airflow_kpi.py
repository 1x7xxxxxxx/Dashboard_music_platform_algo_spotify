import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from src.dashboard.utils.airflow_monitor import AirflowMonitor
from src.dashboard.utils import get_db_connection
from src.utils.freshness_monitor import check_freshness, MONITOR_TARGETS
from src.dashboard.auth import is_admin

def get_quality_metrics():
    """Récupère les KPIs métiers depuis PostgreSQL."""
    db = get_db_connection()
    try:
        # On récupère la moyenne des 7 derniers jours par DAG
        query = """
            SELECT 
                dag_id,
                SUM(total_rows) as total_rows,
                SUM(invalid_rows) as total_invalid,
                SUM(anomalies_confirmed) as total_anomalies,
                AVG(alert_delay_seconds) as avg_alert_delay,
                COUNT(*) as days_count
            FROM etl_daily_metrics
            WHERE run_date >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY dag_id
        """
        df = db.fetch_df(query)
        return df
    except Exception as e:
        st.error(f"Erreur DB Metrics: {e}")
        return pd.DataFrame()
    finally:
        db.close()

def _section_source_status():
    """Onglet : fraîcheur et statut de chaque source de données."""
    st.subheader("📡 État des sources de données")
    db = get_db_connection()
    if db is None:
        return
    try:
        results = check_freshness(db)
    finally:
        db.close()

    rows = []
    for r in results:
        if r['last_dt'] is None:
            age_str = "—"
            statut = "⚫ Jamais collectée"
        elif r['age_h'] is not None:
            age_str = f"{int(r['age_h'])}h" if r['age_h'] < 48 else f"{int(r['age_h'] / 24)}j"
            statut = "🔴 Stale" if r['stale'] else "🟢 OK"
        else:
            age_str = "—"
            statut = "⚫ Erreur"

        date_str = r['last_dt'].strftime("%d/%m/%Y %H:%M") if r['last_dt'] else "—"
        rows.append({
            "Source": r['source'],
            "Dernière collecte": date_str,
            "Âge": age_str,
            "Seuil alerte": f"{r['stale_h']}h",
            "Statut": statut,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df.set_index("Source"), use_container_width=True)

    stale_count = sum(1 for r in results if r['stale'])
    if stale_count:
        st.warning(f"⚠️ {stale_count} source(s) dépassent le seuil de fraîcheur.")
    else:
        st.success("✅ Toutes les sources sont dans les seuils.")

    st.caption(
        "Seuil API (YouTube, SoundCloud, Instagram, Meta) : 48h — "
        "Seuil CSV (Spotify S4A, Apple Music) : 7 jours"
    )


_STATE_ICON = {
    'success': '🟢',
    'failed': '🔴',
    'running': '🔵',
    'skipped': '⚪',
    'upstream_failed': '🟠',
    'queued': '🟡',
    None: '⚫',
    '?': '⚫',
}


def _section_run_logs():
    """Onglet : explorer les runs + logs par tâche."""
    st.subheader("📋 Logs par run")

    monitor = AirflowMonitor()

    # ── Sélecteur DAG ──
    with st.spinner("Chargement des DAGs..."):
        dag_list = monitor.get_dag_list()

    if not dag_list:
        st.error("❌ API Airflow inaccessible. Vérifiez que Docker est lancé.")
        return

    dag_id = st.selectbox("Sélectionner un DAG", dag_list, key="log_dag_id")

    # ── Sélecteur Run ──
    with st.spinner(f"Chargement des runs de {dag_id}..."):
        runs = monitor.get_runs_for_dag(dag_id, limit=20)

    if not runs:
        st.info("Aucun run trouvé pour ce DAG.")
        return

    run_options = {
        f"{_STATE_ICON.get(r['state'], '⚫')} {r['run_id']}  ({r['state']})  — {r['start_date'][:16] if r['start_date'] else '?'}": r['run_id']
        for r in runs
    }
    selected_label = st.selectbox("Sélectionner un Run", list(run_options.keys()), key="log_run_id")
    run_id = run_options[selected_label]

    # ── Task instances ──
    with st.spinner("Chargement des tâches..."):
        tasks = monitor.get_task_instances(dag_id, run_id)

    if not tasks:
        st.info("Aucune tâche trouvée pour ce run.")
        return

    st.markdown("**Tâches du run**")
    cols_header = st.columns([3, 1, 1, 1])
    cols_header[0].markdown("**Task ID**")
    cols_header[1].markdown("**État**")
    cols_header[2].markdown("**Durée**")
    cols_header[3].markdown("**Tentative**")

    for t in tasks:
        icon = _STATE_ICON.get(t['state'], '⚫')
        dur = f"{t['duration']:.1f}s" if t['duration'] else "—"
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        c1.markdown(f"`{t['task_id']}`")
        c2.markdown(f"{icon} {t['state']}")
        c3.markdown(dur)
        c4.markdown(str(t['try_number']))

    st.markdown("---")

    # ── Sélecteur Task pour les logs ──
    task_ids = [t['task_id'] for t in tasks]
    selected_task = st.selectbox("Voir les logs de la tâche", task_ids, key="log_task_id")

    selected_task_info = next((t for t in tasks if t['task_id'] == selected_task), None)
    max_attempt = max(selected_task_info['try_number'] if selected_task_info else 1, 1)
    attempt = st.number_input("Tentative n°", min_value=1, max_value=max_attempt,
                               value=max_attempt, step=1, key="log_attempt")

    if st.button("📄 Charger les logs", type="primary"):
        with st.spinner("Récupération des logs Airflow..."):
            log_text = monitor.get_task_log(dag_id, run_id, selected_task, attempt)

        if log_text:
            # Filtrer les lignes vides au début
            lines = log_text.strip().splitlines()
            # Affichage avec coloration des erreurs
            error_lines = sum(1 for l in lines if 'ERROR' in l or 'CRITICAL' in l)
            warning_lines = sum(1 for l in lines if 'WARNING' in l or 'WARN' in l)

            m1, m2, m3 = st.columns(3)
            m1.metric("Lignes totales", len(lines))
            m2.metric("Erreurs", error_lines, delta_color="inverse" if error_lines > 0 else "off")
            m3.metric("Warnings", warning_lines, delta_color="inverse" if warning_lines > 0 else "off")

            # Logs complets scrollables
            st.text_area(
                f"Logs — {dag_id} / {selected_task} / tentative {attempt}",
                value=log_text,
                height=500,
                key="log_output"
            )

            # Extraire uniquement les lignes ERROR pour diagnostic rapide
            if error_lines > 0:
                with st.expander(f"🔴 Lignes ERROR uniquement ({error_lines})", expanded=True):
                    error_text = "\n".join(l for l in lines if 'ERROR' in l or 'CRITICAL' in l)
                    st.code(error_text, language="text")
        else:
            st.info("Logs vides ou indisponibles.")


def _section_last_runs():
    """Tab: last run per DAG — status, duration, rows inserted."""
    st.subheader("🕐 Dernière exécution par DAG")

    monitor = AirflowMonitor()
    with st.spinner("Chargement des DAGs..."):
        dag_list = monitor.get_dag_list()

    if not dag_list:
        st.error("❌ API Airflow inaccessible. Vérifiez que Docker est lancé.")
        return

    # Fetch last run for every DAG in parallel (sequential calls — Airflow API)
    rows = []
    with st.spinner("Récupération des dernières exécutions..."):
        for dag_id in dag_list:
            runs = monitor.get_runs_for_dag(dag_id, limit=1)
            if runs:
                r = runs[0]
                state = r.get('state') or '?'
                icon = _STATE_ICON.get(state, '⚫')
                start = r.get('start_date', '')
                end = r.get('end_date', '')
                dur_s = r.get('duration_sec')
                dur_str = f"{dur_s:.0f}s" if dur_s else "—"
                start_str = start[:16] if start else "—"
                rows.append({
                    "DAG": dag_id,
                    "Statut": f"{icon} {state}",
                    "Dernier run": start_str,
                    "Durée": dur_str,
                    "_state": state,
                })
            else:
                rows.append({
                    "DAG": dag_id,
                    "Statut": "⚫ jamais exécuté",
                    "Dernier run": "—",
                    "Durée": "—",
                    "_state": None,
                })

    # Rows inserted from etl_daily_metrics (last day per DAG)
    db = get_db_connection()
    rows_inserted: dict = {}
    if db:
        try:
            df_metrics = db.fetch_df(
                """
                SELECT dag_id, SUM(total_rows) AS rows_inserted
                FROM etl_daily_metrics
                WHERE run_date = (
                    SELECT MAX(run_date) FROM etl_daily_metrics m2
                    WHERE m2.dag_id = etl_daily_metrics.dag_id
                )
                GROUP BY dag_id
                """
            )
            if not df_metrics.empty:
                rows_inserted = dict(zip(df_metrics['dag_id'], df_metrics['rows_inserted']))
        except Exception:
            pass
        finally:
            db.close()

    for row in rows:
        row["Lignes insérées"] = int(rows_inserted.get(row["DAG"], 0) or 0)

    df = pd.DataFrame(rows).drop(columns=["_state"])

    # Summary KPIs
    states = [r["_state"] for r in rows]
    n_ok = sum(1 for s in states if s == "success")
    n_fail = sum(1 for s in states if s == "failed")
    n_never = sum(1 for s in states if s is None)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("DAGs totaux", len(rows))
    k2.metric("🟢 Succès", n_ok)
    k3.metric("🔴 Échecs", n_fail, delta_color="inverse")
    k4.metric("⚫ Jamais exécuté", n_never)

    if n_fail:
        failed_dags = [r["DAG"] for r in rows if r["_state"] == "failed"]
        st.error(f"DAGs en échec : {', '.join(f'`{d}`' for d in failed_dags)}")

    st.markdown("---")
    st.dataframe(
        df.set_index("DAG"),
        column_config={
            "Lignes insérées": st.column_config.NumberColumn(format="%d"),
        },
        use_container_width=True,
    )


def show():
    if not is_admin():
        st.error("⛔ Accès réservé à l'administrateur.")
        st.stop()

    st.title("🏗️ Monitoring ETL & Qualité (Global)")
    st.markdown("---")

    tab_etl, tab_sources, tab_last, tab_logs = st.tabs([
        "📊 Performance DAGs", "📡 État des sources",
        "🕐 Dernière exécution", "📋 Logs par Run"
    ])

    with tab_sources:
        _section_source_status()

    with tab_last:
        _section_last_runs()

    with tab_logs:
        _section_run_logs()

    with tab_etl:
        # 1. Récupération des Données (Airflow + DB)
        monitor = AirflowMonitor()

        with st.spinner("Analyse des performances (API + BDD)..."):
            af_data = monitor.get_kpis()
            df_quality = get_quality_metrics()

        if af_data is None:
            st.error("❌ API Airflow injoignable.")
            return

        df_runs = af_data['raw_data']

        if not df_runs.empty:
            stats_tech = []
            for dag_id in df_runs['dag_id'].unique():
                subset = df_runs[df_runs['dag_id'] == dag_id]
                total = len(subset)
                success = len(subset[subset['state'] == 'success'])
                duration = subset['duration_sec'].mean()
                uptime = (success / total * 100) if total > 0 else 0
                stats_tech.append({
                    'dag_id': dag_id,
                    'Taux Succès': uptime,
                    'Temps Exec Moyen (s)': duration,
                    'Uptime API': uptime,
                })

            df_tech = pd.DataFrame(stats_tech)

            if not df_quality.empty:
                df_final = pd.merge(df_tech, df_quality, on='dag_id', how='left').fillna(0)
                df_final['% Invalide'] = df_final.apply(
                    lambda x: (x['total_invalid'] / x['total_rows'] * 100) if x['total_rows'] > 0 else 0, axis=1
                )
                df_final['Taux Anomalie'] = df_final.apply(
                    lambda x: (x['total_anomalies'] / x['total_rows'] * 100) if x['total_rows'] > 0 else 0, axis=1
                )
            else:
                df_final = df_tech
                df_final['% Invalide'] = 0.0
                df_final['Taux Anomalie'] = 0.0
                df_final['avg_alert_delay'] = 0.0

            df_display = df_final[[
                'dag_id', 'Taux Succès', 'Temps Exec Moyen (s)',
                '% Invalide', 'Taux Anomalie', 'Uptime API', 'avg_alert_delay'
            ]].rename(columns={'avg_alert_delay': 'Délai Moy. Alerte (s)'})

            # KPIs globaux
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Exécutions (24h)", af_data['total_runs_24h'])
            c2.metric("Taux Succès Global", f"{af_data['success_rate']:.1f}%")
            c3.metric("% Invalide Moyen", f"{df_display['% Invalide'].mean():.2f}%", delta_color="inverse")
            c4.metric("Échecs (7j)", af_data['failed_count'], delta_color="inverse")

            st.markdown("---")
            st.subheader("📊 Performance par Pipeline")
            st.dataframe(
                df_display.set_index('dag_id'),
                column_config={
                    "Taux Succès": st.column_config.ProgressColumn("Succès", format="%.1f%%", min_value=0, max_value=100),
                    "Uptime API": st.column_config.ProgressColumn("Dispo API", format="%.1f%%", min_value=0, max_value=100),
                    "% Invalide": st.column_config.NumberColumn(format="%.2f %%"),
                    "Temps Exec Moyen (s)": st.column_config.NumberColumn(format="%.1f s"),
                    "Délai Moy. Alerte (s)": st.column_config.NumberColumn(format="%d s"),
                },
                use_container_width=True,
            )

            st.markdown("---")
            st.subheader("⏱️ Chronologie des dernières exécutions")
            gantt_df = df_runs.head(20).copy()
            fig = px.timeline(
                gantt_df,
                x_start="start_date", x_end="end_date", y="dag_id", color="state",
                color_discrete_map={"success": "#00CC96", "failed": "#EF553B", "running": "#636EFA"},
                hover_data=["duration_sec"]
            )
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.info("Aucune donnée d'exécution trouvée dans Airflow.")

if __name__ == "__main__":
    show()