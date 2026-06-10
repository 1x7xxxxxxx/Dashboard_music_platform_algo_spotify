"""EN catalog for the perf_monitor view."""

EN = {
    "perf_monitor.admin_only": "Admins only.",
    "perf_monitor.title": "⚡ Performance Dashboard",
    "perf_monitor.caption": "Streamlit render time per page · Current session only (not persisted across sessions)",
    "perf_monitor.realtime_header": "Real-time status",
    # KPI metrics
    "perf_monitor.metric_last_render": "Last render",
    "perf_monitor.help_last_render": "Python time to render the last page (DB + computation + Streamlit)",
    "perf_monitor.no_render_yet": "— (navigate to a page)",
    "perf_monitor.metric_db_ping": "DB ping",
    "perf_monitor.db_unreachable": "❌ Unreachable",
    "perf_monitor.help_db_ping": "Round-trip latency of SELECT 1 on PostgreSQL",
    "perf_monitor.metric_ram": "RAM process",
    "perf_monitor.help_ram": "RSS memory of the Streamlit process",
    "perf_monitor.psutil_missing": "psutil not installed",
    "perf_monitor.metric_cpu": "CPU process",
    "perf_monitor.help_cpu": "CPU of the Streamlit process over 0.1s",
    # Thresholds
    "perf_monitor.thresholds_header": "Alert thresholds",
    "perf_monitor.thresholds_table": """
| Indicator | 🟢 OK | 🟠 Watch | 🔴 Migrate |
|---|---|---|---|
| Render time | < 1 000 ms | 1 000 – 3 000 ms | > 3 000 ms |
| DB ping | < 50 ms | 50 – 200 ms | > 200 ms |
| RAM process | < 400 MB | 400 – 800 MB | > 800 MB |
| CPU process | < 30 % | 30 – 70 % | > 70 % |

**Streamlit → React/Next.js migration trigger**: render time > 3 000 ms repeatedly with several artists connected simultaneously.
""",
    # Session history
    "perf_monitor.history_header": "Session history ({count} renders)",
    "perf_monitor.history_empty": "Navigate across several pages to populate the history.",
    "perf_monitor.col_page": "Page",
    "perf_monitor.col_renders": "Renders",
    "perf_monitor.col_avg": "Avg (ms)",
    "perf_monitor.col_max": "Max (ms)",
    "perf_monitor.col_min": "Min (ms)",
    "perf_monitor.axis_time": "Time",
    "perf_monitor.raw_log_expander": "Raw log (last 100 renders)",
}
