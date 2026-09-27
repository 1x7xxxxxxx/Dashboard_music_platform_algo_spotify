"""EN catalog for the db_health view."""

EN = {
    # Entrypoint
    "db_health.title": "🗄️ Data health",
    "db_health.intro": 'Tracking imports, freshness and volumes, per dataset.',
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
    "db_health.no_data": "No data available.",
    "db_health.gaps_header": "🚨 Ingestion anomalies — expected against received",
    "db_health.gaps_caption": (
        "Yesterday, for each dataset: the rows expected (mean of the 7 days before, summed "
        "over artists) against the rows received. Alert when an artist receives less than "
        "a third of usual, or nothing on a daily feed."),
    "db_health.gaps_expected": "Expected",
    "db_health.gaps_received": "Received",
    "db_health.gaps_axis": "rows (yesterday)",
    "db_health.gaps_none": (
        "✅ No anomaly: every artist received at least a third of their usual rows yesterday."),
    "db_health.gaps_alert": "⚠️ {n} ingestion anomaly(ies) yesterday:",
    "db_health.gaps_verdict": "Finding",
}
