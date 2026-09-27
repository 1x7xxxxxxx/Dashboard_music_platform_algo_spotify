"""An alert firing for a day reaches the SUBJECT of the evening recap (R227, 2026-09-27).

Type: Test
Uses: src.utils.ops_alerts (long_firing), airflow/dags/alert_monitor.py (source)
Depends on: nothing — pure selection + a structural read of the DAG
Persists in: nothing

`ConnectionPoolExhausted` fired 27 h on the API and was only a line in the BODY of a
recap that landed, unread, in the trash. « Firing now » and « firing for a day » read the
same; the second deserves the subject line.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_only_a_still_firing_day_long_alert_is_selected() -> None:
    from src.utils.ops_alerts import long_firing
    alerts = [
        {"alertname": "ConnectionPoolExhausted", "still_firing": True, "firing_hours": 27.0},
        {"alertname": "RenderLatencyDegraded", "still_firing": True, "firing_hours": 2.0},
        {"alertname": "HostDiskAlmostFull", "still_firing": False, "firing_hours": None},
    ]
    assert [a["alertname"] for a in long_firing(alerts)] == ["ConnectionPoolExhausted"]


def test_the_recap_subject_reads_the_long_alerts() -> None:
    src = (ROOT / "airflow/dags/alert_monitor.py").read_text(encoding="utf-8")
    body = src[src.index("def send_consolidated_alert"):]
    assert "long_firing(ops_alerts)" in body and "subject_parts.append" in body, (
        "the recap subject no longer names an alert that has fired for a day")
