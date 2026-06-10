import streamlit as st
import pandas as pd
import plotly.express as px
from src.dashboard.utils.airflow_monitor import AirflowMonitor
from src.dashboard.utils import get_db_connection
from src.utils.freshness_monitor import check_freshness
from src.dashboard.auth import is_admin
from src.database.postgres_handler import validate_table, validate_columns
from src.dashboard.utils.i18n import t

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
        st.error(t("airflow_kpi.db_metrics_error", "Erreur DB Metrics: {err}").format(err=e))
        return pd.DataFrame()
    finally:
        db.close()

def _section_source_status():
    """Onglet : fraîcheur et statut de chaque source de données."""
    st.subheader(t("airflow_kpi.source_status_header", "📡 État des sources de données"))
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
            statut = t("airflow_kpi.never_collected", "⚫ Jamais collectée")
        elif r['age_h'] is not None:
            age_str = f"{int(r['age_h'])}h" if r['age_h'] < 48 else f"{int(r['age_h'] / 24)}j"
            statut = t("airflow_kpi.status_stale", "🔴 Stale") if r['stale'] else t("airflow_kpi.status_ok", "🟢 OK")
        else:
            age_str = "—"
            statut = t("airflow_kpi.status_error", "⚫ Erreur")

        date_str = r['last_dt'].strftime("%d/%m/%Y %H:%M") if r['last_dt'] else "—"
        rows.append({
            t("airflow_kpi.col_source", "Source"): r['source'],
            t("airflow_kpi.col_last_collect", "Dernière collecte"): date_str,
            t("airflow_kpi.col_age", "Âge"): age_str,
            t("airflow_kpi.col_alert_threshold", "Seuil alerte"): f"{r['stale_h']}h",
            t("airflow_kpi.col_status", "Statut"): statut,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df.set_index(t("airflow_kpi.col_source", "Source")), width="stretch")

    stale_count = sum(1 for r in results if r['stale'])
    if stale_count:
        st.warning(t("airflow_kpi.sources_stale_warning", "⚠️ {count} source(s) dépassent le seuil de fraîcheur.").format(count=stale_count))
    else:
        st.success(t("airflow_kpi.sources_all_ok", "✅ Toutes les sources sont dans les seuils."))

    st.caption(
        t("airflow_kpi.freshness_caption",
          "Seuil API (YouTube, SoundCloud, Instagram, Meta) : 48h — "
          "Seuil CSV (Spotify S4A, Apple Music) : 7 jours")
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
    st.subheader(t("airflow_kpi.run_logs_header", "📋 Logs par run"))

    monitor = AirflowMonitor()

    # ── Sélecteur DAG ──
    with st.spinner(t("airflow_kpi.loading_dags", "Chargement des DAGs...")):
        dag_list = monitor.get_dag_list()

    if not dag_list:
        st.error(t("airflow_kpi.airflow_unreachable", "❌ API Airflow inaccessible. Vérifiez que Docker est lancé."))
        return

    dag_id = st.selectbox(t("airflow_kpi.select_dag", "Sélectionner un DAG"), dag_list, key="log_dag_id")

    # ── Sélecteur Run ──
    with st.spinner(t("airflow_kpi.loading_runs", "Chargement des runs de {dag}...").format(dag=dag_id)):
        runs = monitor.get_runs_for_dag(dag_id, limit=20)

    if not runs:
        st.info(t("airflow_kpi.no_run_found", "Aucun run trouvé pour ce DAG."))
        return

    run_options = {
        f"{_STATE_ICON.get(r['state'], '⚫')} {r['run_id']}  ({r['state']})  — {r['start_date'][:16] if r['start_date'] else '?'}": r['run_id']
        for r in runs
    }
    selected_label = st.selectbox(t("airflow_kpi.select_run", "Sélectionner un Run"), list(run_options.keys()), key="log_run_id")
    run_id = run_options[selected_label]

    # ── Task instances ──
    with st.spinner(t("airflow_kpi.loading_tasks", "Chargement des tâches...")):
        tasks = monitor.get_task_instances(dag_id, run_id)

    if not tasks:
        st.info(t("airflow_kpi.no_task_found", "Aucune tâche trouvée pour ce run."))
        return

    st.markdown(t("airflow_kpi.run_tasks", "**Tâches du run**"))
    cols_header = st.columns([3, 1, 1, 1])
    cols_header[0].markdown(t("airflow_kpi.col_task_id", "**Task ID**"))
    cols_header[1].markdown(t("airflow_kpi.col_state", "**État**"))
    cols_header[2].markdown(t("airflow_kpi.col_duration", "**Durée**"))
    cols_header[3].markdown(t("airflow_kpi.col_attempt", "**Tentative**"))

    for tr in tasks:
        icon = _STATE_ICON.get(tr['state'], '⚫')
        dur = f"{tr['duration']:.1f}s" if tr['duration'] else "—"
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        c1.markdown(f"`{tr['task_id']}`")
        c2.markdown(f"{icon} {tr['state']}")
        c3.markdown(dur)
        c4.markdown(str(tr['try_number']))

    st.markdown("---")

    # ── Sélecteur Task pour les logs ──
    task_ids = [tr['task_id'] for tr in tasks]
    selected_task = st.selectbox(t("airflow_kpi.select_task_logs", "Voir les logs de la tâche"), task_ids, key="log_task_id")

    selected_task_info = next((tr for tr in tasks if tr['task_id'] == selected_task), None)
    max_attempt = max(selected_task_info['try_number'] if selected_task_info else 1, 1)
    attempt = st.number_input(t("airflow_kpi.attempt_n", "Tentative n°"), min_value=1, max_value=max_attempt,
                               value=max_attempt, step=1, key="log_attempt")

    if st.button(t("airflow_kpi.load_logs_btn", "📄 Charger les logs"), type="primary"):
        with st.spinner(t("airflow_kpi.fetching_logs", "Récupération des logs Airflow...")):
            log_text = monitor.get_task_log(dag_id, run_id, selected_task, attempt)

        if log_text:
            # Filtrer les lignes vides au début
            lines = log_text.strip().splitlines()
            # Affichage avec coloration des erreurs
            error_lines = sum(1 for line in lines if 'ERROR' in line or 'CRITICAL' in line)
            warning_lines = sum(1 for line in lines if 'WARNING' in line or 'WARN' in line)

            m1, m2, m3 = st.columns(3)
            m1.metric(t("airflow_kpi.metric_total_lines", "Lignes totales"), len(lines))
            m2.metric(t("airflow_kpi.metric_errors", "Erreurs"), error_lines, delta_color="inverse" if error_lines > 0 else "off")
            m3.metric(t("airflow_kpi.metric_warnings", "Warnings"), warning_lines, delta_color="inverse" if warning_lines > 0 else "off")

            # Logs complets scrollables
            st.text_area(
                t("airflow_kpi.log_textarea", "Logs — {dag} / {task} / tentative {attempt}").format(
                    dag=dag_id, task=selected_task, attempt=attempt),
                value=log_text,
                height=500,
                key="log_output"
            )

            # Extraire uniquement les lignes ERROR pour diagnostic rapide
            if error_lines > 0:
                with st.expander(t("airflow_kpi.error_lines_only", "🔴 Lignes ERROR uniquement ({count})").format(count=error_lines), expanded=True):
                    error_text = "\n".join(line for line in lines if 'ERROR' in line or 'CRITICAL' in line)
                    st.code(error_text, language="text")
        else:
            st.info(t("airflow_kpi.logs_empty", "Logs vides ou indisponibles."))


def _section_last_runs():
    """Tab: last run per DAG — status, duration, rows inserted."""
    st.subheader(t("airflow_kpi.last_runs_header", "🕐 Dernière exécution par DAG"))

    monitor = AirflowMonitor()
    with st.spinner(t("airflow_kpi.loading_dags", "Chargement des DAGs...")):
        dag_list = monitor.get_dag_list()

    if not dag_list:
        st.error(t("airflow_kpi.airflow_unreachable", "❌ API Airflow inaccessible. Vérifiez que Docker est lancé."))
        return

    # Fetch the last run of every DAG in a single batch call (was N+1: one API
    # round-trip per DAG).
    rows = []
    with st.spinner(t("airflow_kpi.fetching_last_runs", "Récupération des dernières exécutions...")):
        last_states = monitor.get_all_dags_last_state()
        for dag_id in dag_list:
            r = last_states.get(dag_id)
            if r:
                state = r.get('state') or '?'
                icon = _STATE_ICON.get(state, '⚫')
                start = r.get('start_date', '')
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
                    "Statut": t("airflow_kpi.never_run", "⚫ jamais exécuté"),
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
    k1.metric(t("airflow_kpi.metric_total_dags", "DAGs totaux"), len(rows))
    k2.metric(t("airflow_kpi.metric_success", "🟢 Succès"), n_ok)
    k3.metric(t("airflow_kpi.metric_failures", "🔴 Échecs"), n_fail, delta_color="inverse")
    k4.metric(t("airflow_kpi.metric_never_run", "⚫ Jamais exécuté"), n_never)

    if n_fail:
        failed_dags = [r["DAG"] for r in rows if r["_state"] == "failed"]
        st.error(t("airflow_kpi.failed_dags", "DAGs en échec : {dags}").format(
            dags=', '.join(f'`{d}`' for d in failed_dags)))

    st.markdown("---")
    _last_runs_cols = {
        "DAG": t("airflow_kpi.col_dag", "DAG"),
        "Statut": t("airflow_kpi.col_status", "Statut"),
        "Dernier run": t("airflow_kpi.col_last_run", "Dernier run"),
        "Durée": t("airflow_kpi.col_duration_plain", "Durée"),
        "Lignes insérées": t("airflow_kpi.col_rows_inserted", "Lignes insérées"),
    }
    df_display = df.rename(columns=_last_runs_cols)
    st.dataframe(
        df_display.set_index(_last_runs_cols["DAG"]),
        column_config={
            _last_runs_cols["Lignes insérées"]: st.column_config.NumberColumn(format="%d"),
        },
        width="stretch",
    )


# Chaque entrée : (label, dag_id, table, col_date, description)
_INSERTION_TARGETS = [
    ("🎵 Spotify S4A",    "s4a_csv_watcher",          "s4a_song_timeline",            "collected_at", "Lignes de streams quotidiens par chanson"),
    ("☁️ SoundCloud",     "soundcloud_daily",          "soundcloud_tracks_daily",       "collected_at", "Tracks SoundCloud avec play/likes/reposts"),
    ("📸 Instagram",      "instagram_daily",           "instagram_daily_stats",         "collected_at", "Stats Instagram journalières"),
    ("🎬 YouTube",        "youtube_daily",             "youtube_channel_history",       "collected_at", "Historique chaîne YouTube"),
    ("📱 Meta Ads",       "meta_ads_api_daily",        "meta_insights_performance_day", "collected_at", "Insights Meta Ads par jour"),
    ("🎎 Apple Music",    "apple_music_csv_watcher",   "apple_songs_performance",       "collected_at", "Performance Apple Music"),
    ("🤖 ML Scoring",     "ml_scoring_daily",          "ml_song_predictions",           "prediction_date", "Prédictions ML par chanson"),
]


@st.fragment
def _section_insertion_test():
    """Vérifie directement en DB combien de lignes ont été insérées par chaque DAG.

    @st.fragment: the window selectbox only re-runs this section, not the whole
    Monitoring page (which re-fetches all DAG states + KPIs on every rerun).
    """
    st.subheader(t("airflow_kpi.insertion_header", "🗄️ Test d'insertion PostgreSQL par DAG"))
    st.caption(
        t("airflow_kpi.insertion_caption",
          "Comptage direct dans les tables sources — indépendant d'Airflow. "
          "Permet de confirmer qu'un run a bien produit des données en base.")
    )

    db = get_db_connection()
    if db is None:
        st.error(t("airflow_kpi.db_unreachable", "❌ Base de données inaccessible."))
        return

    window = st.selectbox(
        t("airflow_kpi.control_window", "Fenêtre de contrôle"),
        ["Aujourd'hui", "7 derniers jours", "30 derniers jours"],
        format_func=lambda w: {
            "Aujourd'hui": t("airflow_kpi.window_today", "Aujourd'hui"),
            "7 derniers jours": t("airflow_kpi.window_7d", "7 derniers jours"),
            "30 derniers jours": t("airflow_kpi.window_30d", "30 derniers jours"),
        }.get(w, w),
        key="insert_window"
    )
    interval_map = {
        "Aujourd'hui": "1 day",
        "7 derniers jours": "7 days",
        "30 derniers jours": "30 days",
    }
    interval = interval_map[window]

    results = []
    try:
        for label, dag_id, table, col_date, description in _INSERTION_TARGETS:
            # CLAUDE.md rule #8 — explicit allowlist + identifier check before f-string SQL.
            # interval comes from a static interval_map dict (no user input).
            validate_table(table)
            validate_columns([col_date])
            try:
                rows = db.fetch_query(
                    f"""
                    SELECT
                        COUNT(*)                                      AS total_rows,
                        COUNT(DISTINCT DATE({col_date}))              AS distinct_days,
                        MAX({col_date})                               AS last_insert,
                        MIN({col_date})                               AS first_insert
                    FROM {table}
                    WHERE {col_date} >= NOW() - INTERVAL '{interval}'
                    """
                )
                total, days, last_ins, first_ins = rows[0] if rows else (0, 0, None, None)
                last_str = pd.to_datetime(last_ins).strftime('%d/%m %H:%M') if last_ins else '—'

                if total and total > 0:
                    status = t("airflow_kpi.status_ok_check", "✅ OK")
                    color = "green"
                else:
                    status = t("airflow_kpi.status_zero_rows", "⚠️ 0 ligne")
                    color = "red"

                results.append({
                    "Plateforme": label,
                    "DAG": dag_id,
                    "Table": table,
                    "Lignes": int(total or 0),
                    "Jours distincts": int(days or 0),
                    "Dernier insert": last_str,
                    "Statut": status,
                    "_color": color,
                    "Description": description,
                })
            except Exception as e:
                results.append({
                    "Plateforme": label,
                    "DAG": dag_id,
                    "Table": table,
                    "Lignes": 0,
                    "Jours distincts": 0,
                    "Dernier insert": "—",
                    "Statut": f"❌ {str(e)[:60]}",
                    "_color": "red",
                    "Description": description,
                })
    finally:
        db.close()

    # KPI summary
    n_ok = sum(1 for r in results if r["_color"] == "green")
    n_ko = len(results) - n_ok
    c1, c2, c3 = st.columns(3)
    c1.metric(t("airflow_kpi.metric_dags_with_data", "DAGs avec données"), n_ok, f"/ {len(results)}")
    c2.metric(t("airflow_kpi.metric_dags_no_data", "DAGs sans données"), n_ko, delta_color="inverse")
    window_label = {
        "Aujourd'hui": t("airflow_kpi.window_today", "Aujourd'hui"),
        "7 derniers jours": t("airflow_kpi.window_7d", "7 derniers jours"),
        "30 derniers jours": t("airflow_kpi.window_30d", "30 derniers jours"),
    }.get(window, window)
    c3.metric(t("airflow_kpi.metric_window", "Fenêtre"), window_label)

    st.markdown("---")

    # Detail per DAG
    for r in results:
        icon = "✅" if r["_color"] == "green" else "⚠️"
        with st.container():
            col_label, col_rows, col_days, col_last, col_status = st.columns([3, 1, 1, 2, 1])
            col_label.markdown(f"**{r['Plateforme']}**  \n`{r['Table']}`")
            col_rows.metric(t("airflow_kpi.metric_rows", "Lignes"), f"{r['Lignes']:,}")
            col_days.metric(t("airflow_kpi.metric_days", "Jours"), r["Jours distincts"])
            col_last.markdown(f"{t('airflow_kpi.last_insert_label', 'Dernier insert')}  \n`{r['Dernier insert']}`")
            col_status.markdown(f"{icon} **{r['Statut']}**")

        if r["_color"] == "red" and "❌" in r["Statut"]:
            st.error(f"`{r['DAG']}` → {r['Statut']}")
        st.markdown("---")


def show():
    if not is_admin():
        st.error(t("airflow_kpi.access_denied", "⛔ Accès réservé à l'administrateur."))
        st.stop()

    st.title(t("airflow_kpi.title", "🏗️ Monitoring ETL & Qualité (Global)"))
    st.markdown("---")

    tab_etl, tab_sources, tab_last, tab_logs, tab_insert = st.tabs([
        t("airflow_kpi.tab_perf", "📊 Performance DAGs"),
        t("airflow_kpi.tab_sources", "📡 État des sources"),
        t("airflow_kpi.tab_last", "🕐 Dernière exécution"),
        t("airflow_kpi.tab_logs", "📋 Logs par Run"),
        t("airflow_kpi.tab_insert", "🗄️ Test insertion DB"),
    ])

    with tab_sources:
        _section_source_status()

    with tab_last:
        _section_last_runs()

    with tab_logs:
        _section_run_logs()

    with tab_insert:
        _section_insertion_test()

    with tab_etl:
        # 1. Récupération des Données (Airflow + DB)
        monitor = AirflowMonitor()

        with st.spinner(t("airflow_kpi.analyzing_perf", "Analyse des performances (API + BDD)...")):
            af_data = monitor.get_kpis()
            df_quality = get_quality_metrics()

        if af_data is None:
            st.error(t("airflow_kpi.airflow_unreachable_short", "❌ API Airflow injoignable."))
            return

        df_runs = af_data['raw_data'].copy()

        # Run timestamps arrive as ISO strings; some carry a tz offset (+00:00) and some
        # are naive (older rows), so pd.to_datetime / px.timeline raise "Cannot mix
        # tz-aware with tz-naive values". Coerce both columns to naive-UTC once so every
        # downstream consumer (timeline + daily trend) is safe.
        for _col in ('start_date', 'end_date'):
            if _col in df_runs.columns:
                df_runs[_col] = pd.to_datetime(
                    df_runs[_col], utc=True, errors='coerce'
                ).dt.tz_localize(None)

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
            c1.metric(t("airflow_kpi.metric_runs_24h", "Exécutions (24h)"), af_data['total_runs_24h'])
            c2.metric(t("airflow_kpi.metric_global_success", "Taux Succès Global"), f"{af_data['success_rate']:.1f}%")
            c3.metric(t("airflow_kpi.metric_avg_invalid", "% Invalide Moyen"), f"{df_display['% Invalide'].mean():.2f}%", delta_color="inverse")
            c4.metric(t("airflow_kpi.metric_failures_7d", "Échecs (7j)"), af_data['failed_count'], delta_color="inverse")

            st.markdown("---")
            st.subheader(t("airflow_kpi.perf_per_pipeline", "📊 Performance par Pipeline"))
            st.dataframe(
                df_display.set_index('dag_id'),
                column_config={
                    "Taux Succès": st.column_config.ProgressColumn(t("airflow_kpi.col_success", "Succès"), format="%.1f%%", min_value=0, max_value=100),
                    "Uptime API": st.column_config.ProgressColumn(t("airflow_kpi.col_api_uptime", "Dispo API"), format="%.1f%%", min_value=0, max_value=100),
                    "% Invalide": st.column_config.NumberColumn(format="%.2f %%"),
                    "Temps Exec Moyen (s)": st.column_config.NumberColumn(format="%.1f s"),
                    "Délai Moy. Alerte (s)": st.column_config.NumberColumn(format="%d s"),
                },
                width="stretch",
            )

            st.markdown("---")
            st.subheader(t("airflow_kpi.timeline_header", "⏱️ Chronologie des dernières exécutions"))
            gantt_df = df_runs.head(20).copy()
            fig = px.timeline(
                gantt_df,
                x_start="start_date", x_end="end_date", y="dag_id", color="state",
                color_discrete_map={"success": "#00CC96", "failed": "#EF553B", "running": "#636EFA"},
                hover_data=["duration_sec"]
            )
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, width='stretch')

            # ── Taux de succès par DAG ──────────────────────────────────
            st.markdown("---")
            st.subheader(t("airflow_kpi.success_rate_header", "✅ Taux de succès par DAG"))
            fig_success = px.bar(
                df_tech.sort_values("Taux Succès"),
                x="Taux Succès",
                y="dag_id",
                orientation="h",
                color="Taux Succès",
                color_continuous_scale=["#EF553B", "#FFA15A", "#00CC96"],
                range_color=[0, 100],
                labels={"dag_id": t("airflow_kpi.col_dag", "DAG"), "Taux Succès": t("airflow_kpi.chart_success_pct", "Succès (%)")},
                text="Taux Succès",
            )
            fig_success.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
            fig_success.update_layout(coloraxis_showscale=False, height=max(300, len(df_tech) * 40))
            st.plotly_chart(fig_success, width='stretch')

            # ── Tendance journalière des runs ───────────────────────────
            st.markdown("---")
            st.subheader(t("airflow_kpi.daily_trend_header", "📈 Tendance journalière des runs (30 derniers jours)"))
            if "start_date" in df_runs.columns:
                trend_df = df_runs.copy()
                trend_df["date"] = pd.to_datetime(trend_df["start_date"]).dt.date
                trend_df = (
                    trend_df.groupby(["date", "state"])
                    .size()
                    .reset_index(name="count")
                )
                fig_trend = px.bar(
                    trend_df,
                    x="date",
                    y="count",
                    color="state",
                    color_discrete_map={"success": "#00CC96", "failed": "#EF553B", "running": "#636EFA"},
                    labels={"date": t("airflow_kpi.chart_date", "Date"), "count": t("airflow_kpi.chart_run_count", "Nombre de runs"), "state": t("airflow_kpi.chart_status", "Statut")},
                    barmode="stack",
                )
                fig_trend.update_layout(height=320)
                st.plotly_chart(fig_trend, width='stretch')

        else:
            st.info(t("airflow_kpi.no_exec_data", "Aucune donnée d'exécution trouvée dans Airflow."))

if __name__ == "__main__":
    show()
