"""One place decides how to reach the database. Everything else asks it.

Installed 2026-08-22. `src/dashboard/utils/get_db_connection` restated the precedence
as `DATABASE_URL → config.yaml` and skipped the middle step, while
`pg_connect.resolve_kwargs` reads `DATABASE_HOST → config.yaml` and never looks at
`DATABASE_URL`.

Measured in production the same day:

    streamlytics_dashboard / streamlytics_api : DATABASE_URL only
    airflow_scheduler                          : DATABASE_HOST / NAME / USER only
    every container                            : no config.yaml at all

So the two halves of one product reached one database through two mechanisms, and
neither worked in the other's place. Setting `DATABASE_HOST` on the dashboard, or
`DATABASE_URL` on the scheduler, breaks that half in silence — the dashboard falling
through to a `config.yaml` that is not there.

`PostgresHandler.from_env_or_config()` already knows all three sources; it was written
on 2026-08-21 for this exact reason, and its docstring already described the
asymmetry. This file stops a fourth copy appearing.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The one implementation, plus the module it delegates to.
_ALLOWED_TO_RESOLVE = {
    REPO / "src" / "database" / "postgres_handler.py",
    REPO / "src" / "utils" / "pg_connect.py",
}
_SCANNED_TREES = [REPO / "src", REPO / "airflow" / "dags", REPO / "tools"]
_DSN_VARS = {"DATABASE_URL", "DATABASE_HOST", "DATABASE_PORT",
             "DATABASE_NAME", "DATABASE_USER", "DATABASE_PASSWORD"}


def _modules_reading_dsn_env() -> dict:
    """{path: [vars]} for every module that reads a DSN variable itself."""
    out: dict[str, list[str]] = {}
    for tree_root in _SCANNED_TREES:
        for path in sorted(tree_root.rglob("*.py")):
            if path in _ALLOWED_TO_RESOLVE:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            found = []
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                    continue
                if node.value in _DSN_VARS:
                    found.append(f"{node.value}:{node.lineno}")
            if found:
                out[str(path.relative_to(REPO))] = found
    return out


def test_the_dashboard_uses_the_shared_door():
    """The specific regression: the dashboard's own precedence, missing a step."""
    src = (REPO / "src" / "dashboard" / "utils" / "__init__.py").read_text("utf-8")
    assert "from_env_or_config()" in src, (
        "get_db_connection no longer delegates — whatever it does instead is a "
        "second precedence, and the last one omitted DATABASE_HOST, which is the "
        "only thing Airflow has"
    )
    assert "config_loader.load()" not in src, (
        "the config.yaml fallback is back in the dashboard; it belongs in the one "
        "resolver"
    )


def test_no_new_module_resolves_the_database_itself():
    """A ratchet, not a ban: the known readers are listed, growth fails.

    Some entries below are legitimate — a DAG passing DATABASE_* through to a
    container, a tool printing which source it used. What must not happen is a NEW
    module quietly inventing a fourth precedence.
    """
    # The measured state on 2026-08-22 — 14 modules, all pre-existing. This is a
    # RATCHET, deliberately not a ban: rewriting fourteen DAGs was not the ask, and
    # each of these reads the Airflow container's own env, which is legitimate where
    # it happens. What must not happen is a FIFTEENTH module quietly inventing
    # another precedence.
    #
    # The list may shrink, never grow. Removing an entry as it is migrated is the
    # intended direction of travel.
    known = {
        "src/api/main.py",
        "src/dashboard/utils/usage_tracker.py",
        "airflow/dags/alert_monitor.py",
        "airflow/dags/apple_music_csv_watcher.py",
        "airflow/dags/data_quality_check.py",
        "airflow/dags/distrokid_csv_watcher.py",
        "airflow/dags/imusician_csv_watcher.py",
        "airflow/dags/ml_outcome_labeling.py",
        "airflow/dags/ml_scoring_daily.py",
        "airflow/dags/onboarding_report.py",
        "airflow/dags/s4a_csv_watcher.py",
        "airflow/dags/spotify_api_daily.py",
        "airflow/dags/weekly_digest.py",
        "airflow/dags/youtube_daily.py",
    }
    offenders = sorted(set(_modules_reading_dsn_env()) - known)
    assert not offenders, (
        "new module(s) reading DSN environment variables directly:\n  "
        + "\n  ".join(offenders)
        + "\nUse PostgresHandler.from_env_or_config(). Two precedences meant the "
          "dashboard and the scheduler could not use each other's configuration; a "
          "third would mean nobody can say how the app finds its database."
    )


def test_the_known_list_has_not_rotted():
    """An entry for a module that no longer reads a DSN var hides the next one.

    Same reasoning as the acknowledged-red list on the external health probe: a
    stale exemption is an exemption nobody re-examines.
    """
    reading = set(_modules_reading_dsn_env())
    known = {
        "src/api/main.py", "src/dashboard/utils/usage_tracker.py",
        "airflow/dags/alert_monitor.py", "airflow/dags/apple_music_csv_watcher.py",
        "airflow/dags/data_quality_check.py", "airflow/dags/distrokid_csv_watcher.py",
        "airflow/dags/imusician_csv_watcher.py", "airflow/dags/ml_outcome_labeling.py",
        "airflow/dags/ml_scoring_daily.py", "airflow/dags/onboarding_report.py",
        "airflow/dags/s4a_csv_watcher.py", "airflow/dags/spotify_api_daily.py",
        "airflow/dags/weekly_digest.py", "airflow/dags/youtube_daily.py",
    }
    stale = sorted(known - reading)
    assert not stale, (
        f"{stale} no longer read a DSN variable — remove them from the ratchet so it "
        "keeps measuring something"
    )


def test_the_sweep_can_see_a_direct_read():
    """Non-vacuity: prove the AST walk recognises the shape it forbids."""
    tree = ast.parse('import os\nx = os.getenv("DATABASE_HOST")\n')
    hits = [n for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and n.value == "DATABASE_HOST"]
    assert hits, "the walk does not see a DSN variable — it guards nothing"


def test_the_shared_door_still_knows_all_three_sources():
    src = (REPO / "src" / "database" / "postgres_handler.py").read_text("utf-8")
    fn = src[src.index("def from_env_or_config"):]
    fn = fn[:fn.index("\n    def ")]
    assert "DATABASE_URL" in fn and "resolve_kwargs" in fn, (
        "the shared resolver lost a source; every caller now inherits that gap"
    )
