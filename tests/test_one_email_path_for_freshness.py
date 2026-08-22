"""Guard — freshness has exactly ONE path to your inbox.

Error class `watchdog-becomes-the-noise`.

`src/utils/freshness_monitor.run_freshness_alerts()` existed with ZERO callers and
sent its own separate email, with its own subject line. The alerting that actually
reaches you is `alert_monitor.check_data_freshness`, folded into the single nightly
digest. Wiring the orphan would have produced two emails for one fact — and the
second failure mode of an alert system is not silence, it is being ignored.

Dead code is not inert either: that function filtered on `stale` alone and never
looked at `error`, so a probe that FAILED would have been reported as a stale
source — the `broken-probe-rendered-as-user-fault` defect the live path no longer
has. An orphan preserves the bugs its neighbours have already fixed, and it reads
as a working feature to whoever finds it next.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _email_senders(path: Path) -> list[str]:
    """Functions in `path` that construct or send an EmailAlert."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name in {"EmailAlert", "send_alert", "send_email"}:
                    out.append(fn.name)
                    break
    return out


def test_the_freshness_module_sends_no_email_of_its_own() -> None:
    senders = _email_senders(ROOT / "src/utils/freshness_monitor.py")
    assert not senders, (
        f"freshness_monitor sends mail from {senders} — freshness already reaches "
        f"the inbox through alert_monitor's consolidated digest. A second path means "
        f"two emails for one fact."
    )


def test_the_removed_orphan_has_not_come_back() -> None:
    tree = ast.parse((ROOT / "src/utils/freshness_monitor.py").read_text(encoding="utf-8"))
    names = {n.name for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "run_freshness_alerts" not in names, (
        "run_freshness_alerts is back. It had no callers and sent its own email; "
        "if freshness alerting needs to change, change alert_monitor."
    )


def test_alert_monitor_is_still_the_one_that_alerts() -> None:
    """If this stops being true, the guard above is protecting nothing."""
    src = (ROOT / "airflow/dags/alert_monitor.py").read_text(encoding="utf-8")
    # `deliver_or_raise` since 2026-08-22: the consolidated alert stopped calling
    # `EmailAlert().send_alert(...)` directly, because that call returns False on an
    # unconfigured container and the result was being discarded — three nights of
    # findings vanished with a green task. Both spellings mean "this module is the
    # one that sends"; asserting only the old one would fail on the fix.
    sends = "EmailAlert" in src or "deliver_or_raise" in src
    assert "check_data_freshness" in src and sends, (
        "alert_monitor no longer carries the freshness path — the single-sender "
        "assumption this file guards is no longer true"
    )
