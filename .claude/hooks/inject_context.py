#!/usr/bin/env python3
"""
Hook: UserPromptSubmit — Domain-aware context injection.

Analyzes the user's prompt and injects relevant pattern reminders
before Claude reads the message.

Domains:
  - dashboard : Streamlit views
  - dag       : Airflow DAGs
  - schema    : PostgreSQL tables
  - collector : API/CSV collectors

Output on stdout (read by Claude as additional context).
Always exits 0 — never blocking.
"""
import json
import sys


DOMAINS = {
    "dashboard": {
        "keywords": [
            # Navigation / structure
            "vue", "view", "dashboard", "streamlit", "page", "sidebar",
            "onglet", "navigation",
            # Visual components
            "widget", "plotly", "chart", "kpi",
            "metric", "st.", "button", "bouton", "filter", "filtre",
            # UI action verbs
            "afficher", "affiche", "render",
        ],
        "context": """\
[Context — Streamlit Dashboard View]
• Create src/dashboard/views/<name>.py with a show() function (no arguments).
• Register in app.py: pages dict + routing `elif page == "...": from views.<name> import show; show()`.
• DB connection: use get_db_connection() from src/dashboard/utils/__init__.py.
• Always call db.close() in finally block or use context manager.
• Mandatory filter on s4a_song_timeline: WHERE song NOT ILIKE '%1x7xxxxxxx%'""",
    },
    "dag": {
        "keywords": [
            # Airflow core
            "dag", "airflow", "pythonoperator", "sensor",
            # Collection / pipeline
            "collecte", "pipeline", "orchestr", "watcher",
            # Scheduling
            "scheduler", "schedule", "cron", "catchup", "backfill", "daily",
            # Tasks
            "tâche", "task", "trigger", "retry", "retries",
        ],
        "context": """\
[Context — Airflow DAG]
• Add sys.path.insert(0, '/opt/airflow') at the top of the file.
• Minimum default_args: owner='data_team', depends_on_past=False, retries=2, retry_delay=timedelta(minutes=10).
• Import collectors INSIDE task functions (prevents DAG parse errors).
• Always create the corresponding debug_dag in airflow/debug_dag/debug_<name>.py.
• DAG id must match the filename exactly (without .py).""",
    },
    "schema": {
        "keywords": [
            # Structure
            "schema", "table", "postgres", "postgresql", "migration",
            "create table", "alter table", "init_db",
            # Columns / constraints
            "colonne", "column", "constraint", "unique", "index",
            # DB operations
            "upsert", "upsert_many", "insert_many",
            # General DB references
            "base de données", "postgres_handler",
        ],
        "context": """\
[Context — PostgreSQL Schema]
• Reference model: src/database/youtube_schema.py (SCHEMA dict + create_*_tables() function).
• PostgresHandler.autocommit = True — no manual commit() calls.
• upsert_many(table, data, conflict_columns, update_columns) for idempotent inserts.
• conflict_columns must match exactly the columns in the table's UNIQUE constraint.
• Bootstrap schema in init_db.sql (executed once by Docker entrypoint).""",
    },
    "collector": {
        "keywords": [
            # Classes / modules
            "collector", "src/collectors",
            # Platforms
            "spotify", "youtube", "meta ads", "instagram", "soundcloud",
            "apple music", "facebook",
            # Auth / API
            "oauth", "access_token", "api_key", "rate limit",
            "endpoint", "credential",
            # Project-specific CSV sources
            "s4a", "spotify for artists", "hypeddit",
        ],
        "context": """\
[Context — Collector / API]
• Collectors in src/collectors/ — instantiated and called inside DAG task functions.
• Credentials in DAGs: loaded via credential_loader.load_platform_credentials(artist_id, platform).
• Credentials in dashboard: config_loader.load() → config/config.yaml.
• S4A and Apple Music CSVs are placed in data/ and detected by the watchers.
• INVARIANT: every except block in a collector must `raise` — never return None/[]/{}. Silent returns mark DAG tasks SUCCESS with 0 rows (P2 data-integrity bug). Run /audit-collectors after any collector change.""",
    },
}


def detect_domains(prompt: str) -> list[str]:
    prompt_lower = prompt.lower()
    detected = []
    for domain, cfg in DOMAINS.items():
        matches = sum(1 for kw in cfg["keywords"] if kw in prompt_lower)
        if matches >= 2:
            detected.append(domain)
    return detected


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    prompt = data.get("prompt", "")
    if not prompt:
        sys.exit(0)

    domains = detect_domains(prompt)
    if not domains:
        sys.exit(0)

    blocks = [DOMAINS[d]["context"] for d in domains]
    print("\n".join(blocks))
    sys.exit(0)


if __name__ == "__main__":
    main()
