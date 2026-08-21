""""No data" and "no data expected" are different claims. Only one is an incident.

Measured 2026-08-21, minutes after the Meta integration was repaired: the admin ad
account holds 19 ARCHIVED + 15 PAUSED campaigns and ZERO active ones, the API
reports `amount_spent: 0` and no insight row in 90 days. Meta Ads insights only
exist while ads run — so the pipeline is correct and the data is legitimately absent.

Reported as staleness, that fact would have fired `16 577 h stale` every night
forever, for a working pipeline. This repo has paid that tax three times already
(the migrate reporter, the schema diff where 24 of 26 differences were cosmetic,
and the canary tenant). A detector's worth is the share of its findings that
deserve an action.

The suppression is deliberately conservative: any doubt keeps the alert. Silencing
on a guess is worse than one noisy line, because it removes the only signal a real
outage would produce.
"""

from __future__ import annotations

import pytest

from src.utils.freshness_monitor import _silence_reason


class _DB:
    def __init__(self, rows=None, boom=False) -> None:
        self._rows, self._boom = rows, boom
        self.seen: list = []

    def fetch_query(self, sql, params=None):  # noqa: ANN001
        if self._boom:
            raise RuntimeError("connection lost")
        self.seen.append((sql, params))
        return self._rows


def test_no_active_campaign_is_a_legitimate_silence() -> None:
    reason = _silence_reason(_DB([(0, 34)]), "meta_no_active_campaign")
    assert reason and "no ACTIVE campaign" in reason and "34 known" in reason


def test_an_active_campaign_means_the_silence_is_a_real_problem() -> None:
    """Ads running and no insights arriving IS an incident — never suppress that."""
    assert _silence_reason(_DB([(2, 34)]), "meta_no_active_campaign") is None


def test_knowing_nothing_about_campaigns_never_suppresses() -> None:
    """Zero campaign rows may mean the campaign collector is broken too."""
    assert _silence_reason(_DB([(0, 0)]), "meta_no_active_campaign") is None


def test_a_failed_probe_keeps_the_alert() -> None:
    """A check that cannot run must not be able to silence another check."""
    assert _silence_reason(_DB(boom=True), "meta_no_active_campaign") is None


def test_an_unknown_rule_never_suppresses() -> None:
    assert _silence_reason(_DB([(0, 34)]), "some_future_rule") is None


def test_the_probe_is_tenant_scoped_when_asked() -> None:
    """One tenant's paused account must not silence another's broken collection."""
    db = _DB([(0, 34)])
    _silence_reason(db, "meta_no_active_campaign", artist_id=12)
    sql, params = db.seen[-1]
    assert "artist_id = %s" in sql and params == (12,)

    db2 = _DB([(0, 34)])
    _silence_reason(db2, "meta_no_active_campaign")
    assert "artist_id" not in db2.seen[-1][0]


def test_freshness_exposes_why_it_stayed_quiet() -> None:
    """A suppressed alert that leaves no trace is indistinguishable from a bug."""
    import inspect

    from src.utils import freshness_monitor

    src = inspect.getsource(freshness_monitor.check_freshness)
    assert '"expected_silence": expected_silence' in src, (
        "check_freshness suppresses the alert without reporting why. A reader must "
        "be able to tell 'quiet because fine' from 'quiet because broken'."
    )


def test_only_meta_declares_an_expected_silence_today() -> None:
    """Pins the blast radius: a new suppression must be a deliberate edit."""
    from src.utils.freshness_monitor import MONITOR_TARGETS

    declared = {t["source"] for t in MONITOR_TARGETS if t.get("silence_expected")}
    assert declared == {"Meta Ads"}, (
        f"expected silence now declared for {declared}. Every entry here removes an "
        "alert — each one needs the measurement that justifies it."
    )


# ── The readers ──────────────────────────────────────────────────────────────
# Everything above proves the suppression decides correctly. A suppression whose
# verdict nobody displays is not neutral: `stale=False` makes Meta Ads render as
# 🟢 OK next to a two-year-old date, on the admin table, in the readiness matrix
# AND in the "✅ Sources OK" footer of the nightly email. That is a greener lie
# than the nightly false red it replaced. These tests fail if a reader goes away.

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAG = ROOT / "airflow/dags/alert_monitor.py"

_REASON = "no ACTIVE campaign (34 known, none running) — expected"


def test_a_quiet_platform_is_not_reported_as_ok() -> None:
    from src.utils import artist_readiness as ar

    assert ar.platform_status(True, None, True, _REASON) == ar.QUIET
    assert ar.platform_status(True, "2024-09-30", False, _REASON) == ar.QUIET


def test_a_missing_identity_still_outranks_an_expected_silence() -> None:
    """The probe cannot even run without the identity — TODO stays the tenant's move."""
    from src.utils import artist_readiness as ar

    assert ar.platform_status(False, None, True, _REASON) == ar.TODO


def test_without_a_reason_nothing_changes_for_the_existing_statuses() -> None:
    from src.utils import artist_readiness as ar

    assert ar.platform_status(True, None, True) == ar.NO_DATA
    assert ar.platform_status(True, "2026-08-20", True) == ar.STALE
    assert ar.platform_status(True, "2026-08-20", False) == ar.OK


def test_the_quiet_status_carries_its_reason_to_the_reader() -> None:
    """A status with nothing behind it is read as a bug the next time someone looks."""
    from src.utils import artist_readiness as ar

    action = ar.next_action(ar._PLATFORMS[3], ar.QUIET, _REASON)
    assert "Rien à faire" in action and "no ACTIVE campaign" in action


def test_a_quiet_platform_is_not_a_red_flag() -> None:
    """readiness_red_flags drives an alert; a correct pipeline must not feed it."""
    from src.utils import artist_readiness as ar

    assert ar.platform_status(True, None, True, _REASON) != ar.NO_DATA


def test_readiness_propagates_the_reason_end_to_end(monkeypatch) -> None:
    """The wiring, not just the pure functions: freshness → matrix row."""
    import pandas as pd

    from src.utils import artist_readiness as ar
    from src.utils import freshness_monitor

    monkeypatch.setattr(freshness_monitor, "check_freshness", lambda db, aid=None: [
        {"source": "Meta Ads", "last_dt": None, "stale": True,
         "expected_silence": _REASON},
    ])

    class _DB2:
        def fetch_df(self, sql, params=None):  # noqa: ANN001
            return pd.DataFrame([{"platform": "meta",
                                  "extra_config": {"account_id": "act_1"}}])

        def fetch_query(self, sql, params=None):  # noqa: ANN001
            return [(None,)]

    row = next(m for m in ar.artist_readiness(_DB2(), 14) if m["key"] == "meta")
    assert row["status"] == ar.QUIET, row
    assert row["expected_silence"] == _REASON
    assert "no ACTIVE campaign" in row["next_action"]


def test_the_source_table_shows_quiet_instead_of_ok(monkeypatch) -> None:
    """Behavioural, not a substring: the view is run and its table inspected."""
    import src.dashboard.views.airflow_kpi as view

    captured: dict = {}

    class _ST:
        def subheader(self, *a, **k): pass
        def dataframe(self, df, **k): captured["df"] = df
        def warning(self, msg, **k): captured.setdefault("msgs", []).append(msg)
        def success(self, msg, **k): captured.setdefault("msgs", []).append(msg)
        def info(self, msg, **k): captured.setdefault("msgs", []).append(msg)
        def caption(self, msg, **k): captured.setdefault("caps", []).append(msg)

    monkeypatch.setattr(view, "st", _ST())
    monkeypatch.setattr(view, "t", lambda key, default="", **k: default)
    monkeypatch.setattr(view, "check_freshness", lambda db: [
        {"source": "Meta Ads", "last_dt": __import__("datetime").datetime(2024, 9, 30),
         "age_h": 16577.0, "stale": False, "stale_h": 48, "error": None,
         "expected_silence": _REASON},
        {"source": "YouTube", "last_dt": __import__("datetime").datetime(2026, 8, 21),
         "age_h": 3.0, "stale": False, "stale_h": 48, "error": None,
         "expected_silence": None},
    ])

    view._section_source_status(db=None)

    statuses = dict(zip(captured["df"].index, captured["df"]["Statut"]))
    assert "Silence attendu" in statuses["Meta Ads"], statuses
    assert "OK" in statuses["YouTube"], statuses
    assert any("no ACTIVE campaign" in c for c in captured.get("caps", [])), (
        "the table shows a quiet source without ever saying why. A suppressed "
        "alert that leaves no trace is indistinguishable from a dead monitor."
    )


def _assignment_expr(func_name: str, var: str) -> str:
    tree = ast.parse(DAG.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == func_name)
    for node in ast.walk(fn):
        if (isinstance(node, ast.Assign) and node.targets
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == var):
            return ast.unparse(node.value)
    raise AssertionError(f"{var} is no longer assigned in {func_name}")


def test_the_nightly_email_does_not_call_a_quiet_source_ok() -> None:
    """`ok_sources` is a claim about last night's collection, not about silence."""
    expr = _assignment_expr("send_consolidated_alert", "ok_sources")
    assert "expected_silence" in expr, (
        "the ✅ Sources OK footer lists sources whose silence was merely suppressed. "
        f"It would print 'Meta Ads' beside a two-year-old row.\nok_sources = {expr}"
    )


def test_the_reason_survives_the_xcom_hop() -> None:
    """The footer can only read what check_data_freshness serialises."""
    src = DAG.read_text(encoding="utf-8")
    start = src.index("def check_data_freshness(")
    end = src.index("\ndef ", start + 1)
    assert "'expected_silence'" in src[start:end], (
        "check_data_freshness drops expected_silence, so the alert task cannot "
        "tell a quiet source from a healthy one whatever it renders."
    )


def test_the_debug_script_does_not_print_a_quiet_source_as_ok() -> None:
    """Found by sweeping the class, not by looking at the bug: a fourth surface.

    `airflow/debug_dag/debug_alert_monitor.py` is what someone runs when they
    already suspect something — printing `✅ OK (16577h)` there is the worst place
    of all four to reassure them.
    """
    dbg = ast.parse((ROOT / "airflow/debug_dag/debug_alert_monitor.py")
                    .read_text(encoding="utf-8"))
    branches = [n for n in ast.walk(dbg)
                if isinstance(n, ast.If) and "expected_silence" in ast.unparse(n.test)]
    assert branches, (
        "the debug freshness loop renders `not stale` as OK with no expected-silence "
        "branch, so it prints a green line beside a two-year-old row."
    )
