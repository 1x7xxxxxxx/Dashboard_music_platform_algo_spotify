"""Debug script — run weekly_digest locally without Airflow.

Usage:
    python airflow/debug_dag/debug_weekly_digest.py
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from airflow.dags.weekly_digest import send_weekly_digest

if __name__ == "__main__":
    result = send_weekly_digest()
    print(f"Result: {result}")
