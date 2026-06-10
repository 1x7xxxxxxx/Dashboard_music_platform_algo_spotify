"""EN catalog for the db_health view."""

EN = {
    # Entrypoint
    "db_health.title": "🗄️ Data health",
    "db_health.intro": "Tracking imports, freshness and volumes per PostgreSQL dataset.",
    "db_health.spinner": "Loading DB metrics…",
    "db_health.session_invalid": "Invalid session.",
    # Health table
    "db_health.table_header": "🏥 Dataset status",
    "db_health.kpi_active": "Active datasets",
    "db_health.kpi_empty": "Empty datasets",
    "db_health.kpi_total_rows": "Total DB rows",
    "db_health.kpi_stale": "Stale datasets (>30d)",
    "db_health.col_dataset": "Dataset",
    "db_health.col_table": "Table",
    "db_health.col_total_rows": "Total rows",
    "db_health.col_first_import": "First import",
    "db_health.col_last_import": "Last import",
    "db_health.col_age_days": "Age (days)",
    "db_health.age_days_suffix": "{n}d",
    # Freshness bar
    "db_health.freshness_header": "⏱️ Freshness per dataset",
    "db_health.freshness_caption": "Days since last import — green ≤14d, orange ≤30d, red >30d",
    "db_health.no_populated": "No populated dataset.",
    "db_health.freshness_xaxis": "Days since last import",
    "db_health.vline_label": "{n}d",
    # Heatmap
    "db_health.heatmap_header": "📅 Import activity — weekly heatmap",
    "db_health.heatmap_caption": "Each cell = new rows ingested this week. White = no activity.",
    "db_health.no_activity_data": "No activity data available.",
    "db_health.no_activity_52w": "No activity over the last 52 weeks.",
    # Cumulative
    "db_health.cumul_header": "📈 Cumulative dataset growth",
    "db_health.cumul_caption": "A plateau = no more imports on this dataset.",
    "db_health.no_data": "No data available.",
    "db_health.datasets_to_show": "Datasets to display",
    "db_health.cumul_yaxis": "Cumulative rows",
    # Batch sizes
    "db_health.batch_header": "📦 Import size per week",
    "db_health.batch_caption": "Very small or very large batches may indicate a collection anomaly.",
    "db_health.no_activity_26w": "No activity over the last 26 weeks.",
    "db_health.batch_yaxis": "New rows",
}
