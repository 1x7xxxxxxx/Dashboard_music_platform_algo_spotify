"""A finding rendered in the email but absent from the send decision is a silent check.

Measured 2026-08-21 in `airflow/dags/alert_monitor.py`. `central_apps_broken` was
rendered in the body AND put first in the subject line — and was NOT part of
`has_issues`, the condition that decides whether any email is sent at all. So a
shared app that stopped authenticating, ALONE, produced nothing: the function
returned early before building anything.

It was masked only by coincidence — Meta happened to be broken and stale at the
same time, and staleness was in the decision. The check written specifically to
break a months-long silence was itself silent under the one condition it targeted.

Error class: finding-rendered-but-not-alerted.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DAG = ROOT / "airflow/dags/alert_monitor.py"


def _source() -> str:
    return DAG.read_text(encoding="utf-8")


def _has_issues_expression() -> str:
    tree = ast.parse(_source())
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and node.targets
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "has_issues"):
            return ast.unparse(node.value)
    raise AssertionError("has_issues is no longer assigned in alert_monitor")


def _xcom_pull_targets() -> set[str]:
    """Every local name assigned from an xcom_pull inside the alert function."""
    src = _source()
    start = src.index("def send_consolidated_alert(")
    end = src.index("\ndef ", start + 1) if "\ndef " in src[start + 1:] else len(src)
    body = src[start:end]
    return set(re.findall(r"^\s*(\w+)\s*=\s*ti\.xcom_pull", body, re.M))


def test_every_pulled_finding_takes_part_in_the_send_decision() -> None:
    """The sweep, not the instance: any future check gets the same treatment."""
    expression = _has_issues_expression()
    pulled = _xcom_pull_targets()
    assert pulled, "no xcom_pull found — the parser is looking in the wrong place"

    # `freshness` is filtered into `stale_sources`, which IS in the decision.
    derived = {"freshness"}
    missing = sorted(n for n in pulled - derived if n not in expression)
    assert not missing, (
        f"{missing} are pulled and rendered but do not take part in has_issues. "
        "If one of them is the ONLY problem, no email is sent at all — the check "
        "becomes a silent one, which is exactly what it was written to prevent."
    )


def test_the_canary_has_a_watchdog_at_all() -> None:
    """No global signal can see a per-tenant break; only the canary can."""
    src = _source()
    assert "def check_canary_health(" in src, (
        "nothing watches the canary tenant. A source stays fresh as long as ONE "
        "tenant collects, and that is almost always the admin — so the per-tenant "
        "pipeline can be fully broken with every global light green."
    )
    assert "task_id='check_canary_health'" in src, (
        "check_canary_health exists but is not wired as a task — a detector with "
        "no schedule is the 672-silent-failures shape all over again."
    )


def test_the_canary_task_feeds_the_consolidated_alert() -> None:
    """Only the DEPENDENCY expression counts, not the operator definitions above it.

    The first version of this test spanned from `t_creds` to `>> t_alert` with
    DOTALL, which swept up every `t_x = PythonOperator(...)` in between — so
    `t_canary` was "found" even after being removed from the dependency line.
    A mutation that unwired the task left it green.
    """
    src = _source()
    lines = [ln for ln in src.splitlines() if ">> t_alert" in ln]
    assert lines, "nothing feeds t_alert any more — re-read before trusting this"

    # The fan-in may be split over several physical lines; take the statement that
    # closes the list, plus its continuation lines, and nothing else.
    idx = src.splitlines().index(lines[-1])
    all_lines = src.splitlines()
    start = idx
    while start > 0 and not all_lines[start].lstrip().startswith("["):
        start -= 1
    statement = "\n".join(all_lines[start:idx + 1])
    assert "t_alert" in statement
    assert "t_canary" in statement, (
        "t_canary is not upstream of t_alert, so its xcom is never read.\n"
        f"dependency statement:\n{statement}"
    )


@pytest.mark.parametrize("needle", ["canary_problems", "CANARI", "check_canary_health"])
def test_the_canary_finding_reaches_the_reader(needle: str) -> None:
    """Pushed, pulled, rendered, and in the subject — all four, or it is decoration."""
    assert needle in _source(), f"{needle!r} missing: the canary finding stops somewhere"


# ── The detector itself, seen RED ────────────────────────────────────────────
# Everything above checks wiring. Wiring a detector that never fires is the same
# decoration in a different place, so the logic gets exercised directly.

def _load_check_canary_health():
    """Execute just that function — importing the DAG would require Airflow."""
    import logging
    import types

    src = _source()
    tree = ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "check_canary_health")
    mod = types.ModuleType("canary_under_test")
    mod.logger = logging.getLogger("canary_under_test")
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<test>", "exec"),  # noqa: S102
         mod.__dict__)
    return mod.check_canary_health


class _TI:
    def __init__(self) -> None:
        self.pushed: dict = {}

    def xcom_push(self, key: str, value: object) -> None:
        self.pushed[key] = value


class _FakeDB:
    def __init__(self, tenants, platforms, age_hours) -> None:
        self._tenants, self._platforms, self._age = tenants, platforms, age_hours

    def fetch_query(self, sql, params=None):  # noqa: ANN001
        if "FROM saas_artists" in sql:
            return self._tenants
        if "artist_credentials" in sql:
            return [(p,) for p in self._platforms]
        return [(self._age,)]

    def close(self) -> None:
        pass


def _run(monkeypatch, db) -> list:
    import src.database.postgres_handler as ph

    monkeypatch.setattr(ph.PostgresHandler, "from_env_or_config",
                        classmethod(lambda cls: db))
    ti = _TI()
    _load_check_canary_health()(task_instance=ti)
    return ti.pushed["canary_problems"]


def test_a_canary_that_stopped_collecting_is_reported(monkeypatch) -> None:
    problems = _run(monkeypatch,
                    _FakeDB([(471, "Canary")], ["youtube"], age_hours=400))
    assert problems and "400h ago" in problems[0]["reason"], problems


def test_a_canary_that_never_collected_is_reported(monkeypatch) -> None:
    problems = _run(monkeypatch,
                    _FakeDB([(471, "Canary")], ["youtube"], age_hours=None))
    assert problems and "NEVER collected" in problems[0]["reason"], problems


def test_a_missing_canary_is_itself_the_finding(monkeypatch) -> None:
    """Absence must not read as health — with no canary the detector is simply off."""
    problems = _run(monkeypatch, _FakeDB([], [], age_hours=None))
    assert problems and "no canary tenant exists" in problems[0]["reason"], problems


def test_a_healthy_canary_reports_nothing(monkeypatch) -> None:
    assert _run(monkeypatch,
                _FakeDB([(471, "Canary")], ["youtube"], age_hours=2)) == []


def test_a_platform_the_canary_never_declared_is_not_a_problem(monkeypatch) -> None:
    """Only what it declared. Meta needs real ownership, so it never will."""
    assert _run(monkeypatch,
                _FakeDB([(471, "Canary")], [], age_hours=None)) == []
