"""A detector nobody schedules is a detector that finds nothing.

Installed 2026-08-21. `tools/check_central_apps.py` detects exactly the failure
that has been live since 2026-08: the Meta System User token is malformed, every
REST call returns code-190, and Meta and Instagram have collected nothing since.

Nothing ran it on a schedule. `alert_monitor` had eight checks and every one of
them was per-tenant — has this artist declared credentials, is their data fresh,
is their light green. None asked the question one level up: does the app the
whole fleet borrows still work?

That is the same shape as the 672 CSV-watcher failures of 2026-08-20 — a real
failure, a detector that could see it, and no schedule connecting the two. The
cost is identical: weeks of silence.

This pins the connection, not the detector. The detector already had tests; what
it lacked was a caller that runs every day.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path


def _repo_root() -> Path:
    for d in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ found above this test")


REPO = _repo_root()
DAG = REPO / "airflow" / "dags" / "alert_monitor.py"
TOOL = REPO / "tools" / "check_central_apps.py"


def _source() -> str:
    return DAG.read_text(encoding="utf-8")


def test_the_detector_still_exists():
    """Everything below is about wiring; this is the thing being wired."""
    assert TOOL.is_file(), f"{TOOL} is gone — the central-app probes were the point"
    src = TOOL.read_text(encoding="utf-8")
    for probe in ("check_spotify", "check_youtube", "check_soundcloud", "check_meta"):
        assert f"def {probe}" in src, f"{probe} disappeared from the detector"


def test_the_daily_monitor_runs_it():
    src = _source()
    assert "check_central_apps" in src, (
        "alert_monitor no longer calls the central-app check. Every other check in "
        "it is per-tenant; without this one, a shared app that stops authenticating "
        "takes the whole fleet down in silence — measured, not hypothetical."
    )
    assert re.search(r"task_id\s*=\s*['\"]check_central_apps['\"]", src), (
        "the function exists but no task runs it — importing a check is not "
        "scheduling one."
    )


def test_the_task_is_in_the_dependency_chain():
    """A task defined and never chained is parsed, listed, and never run."""
    src = _source()
    chain = re.search(r"\[([^\]]*t_central[^\]]*)\]\s*>>", src)
    assert chain, (
        "t_central is not in the list that feeds send_consolidated_alert. Airflow "
        "would show the task and never schedule it behind the others."
    )


def test_the_result_reaches_the_email():
    """Detecting it and not saying it is the same outcome as not detecting it."""
    src = _source()
    assert "central_apps_broken" in src, "the task pushes no xcom key"
    assert re.search(r"xcom_pull\(task_ids='check_central_apps'", src), (
        "the consolidated alert never reads the result — the check would run, "
        "find the breakage, and tell nobody."
    )
    assert "central_broken" in src and "subject_parts.append" in src, (
        "the result is read but never reaches the subject line"
    )
    assert "central_html" in src, (
        "the subject announces a broken shared app and the body explains nothing"
    )


def test_an_unrunnable_check_does_not_report_success():
    """The failure mode a wiring test cannot catch by presence alone.

    `tools/` is not on the image path in every deployment. If the import fails and
    the task pushes an empty list, the email says everything is fine — which is
    exactly the silence this whole file exists to end.
    """
    tree = ast.parse(_source())
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "check_central_apps"), None)
    assert fn, "check_central_apps is not a function in alert_monitor"

    handlers = [h for n in ast.walk(fn) if isinstance(n, ast.Try) for h in n.handlers]
    import_guard = [
        h for h in handlers
        if isinstance(h.type, ast.Name) and h.type.id == "ImportError"
    ]
    assert import_guard, (
        "no ImportError handler: if tools/ is absent from the image the task "
        "raises, and `trigger_rule='all_done'` sends the email anyway — with no "
        "mention of the platform whose check never ran."
    )
    body = ast.unparse(import_guard[0])
    assert "xcom_push" in body and "could not run" in body, (
        "the ImportError path must push a NON-empty result saying the check could "
        "not run. Pushing nothing is indistinguishable from 'all apps fine'."
    )
