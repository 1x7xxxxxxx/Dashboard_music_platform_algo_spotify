"""EN catalog for the etl_logs view."""

EN = {
    "etl_logs.admin_only": "🔒 Access restricted to administrators.",
    "etl_logs.title": "🗂️ ETL History",
    "etl_logs.caption": "Airflow run logs persisted in database — table `etl_run_log`",
    # KPIs
    "etl_logs.kpis_empty": "No runs recorded in the last 7 days. "
                           "Check that `DagRunLogger` is used in your DAGs.",
    "etl_logs.kpi_runs": "Runs (7d)",
    "etl_logs.kpi_success_rate": "Success rate",
    "etl_logs.kpi_avg_duration": "Avg duration",
    "etl_logs.kpi_rows_inserted": "Rows inserted",
    "etl_logs.kpi_failed_runs": "Failed runs",
    # Run history
    "etl_logs.history_header": "Latest runs",
    "etl_logs.filter_dag": "Filter by DAG",
    "etl_logs.filter_dag_placeholder": "e.g. soundcloud",
    "etl_logs.filter_status": "Status",
    "etl_logs.filter_status_all": "All",
    "etl_logs.filter_window": "Window (days)",
    "etl_logs.no_matching_runs": "No matching runs.",
    "etl_logs.truncation_notice": "⚠️ Showing the 200 most recent runs out of {total} total — "
                                  "refine using the filters above.",
    "etl_logs.col_status": "Status",
    "etl_logs.col_rows_ok": "Rows OK",
    "etl_logs.col_rows_ko": "Rows KO",
    "etl_logs.col_duration": "Duration",
    "etl_logs.col_dag": "DAG",
    "etl_logs.col_started": "Started",
    "etl_logs.error_expander": "❌ Details of {count} errors",
    # Trend
    "etl_logs.trend_header": "Trend per DAG (14 days)",
    "etl_logs.trend_empty": "Not enough data to display the trend.",
    "etl_logs.chart_runs": "Runs",
    "etl_logs.chart_date": "Date",
    "etl_logs.chart_status": "Status",
    # Circuit breakers
    "etl_logs.cb_header": "🔌 Circuit Breakers",
    "etl_logs.cb_caption": "If a circuit is OPEN, the corresponding DAG skips collection "
                           "to avoid burning retries on known-broken credentials.",
    "etl_logs.cb_none": "✅ No circuit breaker recorded — all platforms are operating normally.",
    "etl_logs.cb_failures": "{icon} **{platform}** (artist #{artist_id}) — "
                            "<span style='color:{color};font-weight:bold'>{state}</span> "
                            "— {failures} failure(s)",
    "etl_logs.cb_last_failure": "Last failure: {last_fail} | ",
    "etl_logs.cb_next_retry": "Next retry: {reset_at}",
    "etl_logs.cb_error": "Error: {error}",
    "etl_logs.cb_reset_btn": "↺ Reset",
    "etl_logs.cb_reset_ok": "Circuit {platform} reset.",
    "etl_logs.cb_reset_err": "Error: {err}",
}
