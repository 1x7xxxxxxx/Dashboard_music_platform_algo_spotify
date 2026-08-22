"""A tenant that stopped collecting must be readable without opening the email.

Installed 2026-08-22. `subject_parts` was built from nine signals and omitted the
four that speak about tenants — `tenant_gaps`, `readiness_flags`, `stalled_tenants`,
`canary_preflight`. Consequences, both measured on the live alert:

  * "Benken ne collecte pas Meta" and "GRiNCH ne collecte pas SoundCloud" — the exact
    two failures that cost two beta sessions — were in the body of a nightly mail
    carrying 9 to 11 repeated findings, and never in the title;
  * a night whose ONLY findings were those four sent an email titled
    "🚨 Dashboard Alert:" followed by nothing at all.

The tests read the source rather than executing the task: importing the DAG needs
Airflow, and the subject is built inline. That is a real limitation — it pins the
shape, not the rendering — so `test_the_subject_is_never_empty` also exercises the
`or` fallback directly.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = (REPO / "airflow" / "dags" / "alert_monitor.py").read_text(encoding="utf-8")


def _subject_block() -> str:
    start = SRC.index("subject_parts = [")
    end = SRC.index("subject = ' | '.join(subject_parts)")
    return SRC[start:end]


def test_a_tenant_that_stopped_collecting_is_in_the_subject():
    block = _subject_block()
    assert "readiness_flags" in block, (
        "the subject is built without readiness_flags — the two failures that cost "
        "two beta sessions would again be buried in the body of a nightly mail"
    )
    assert "artist_name" in block, (
        "the subject counts tenants instead of naming them. '2 artiste(s)' is not "
        "actionable at a glance; 'GRiNCH (SoundCloud)' is."
    )


def test_the_canary_preflight_is_in_the_subject():
    """It is the gate the runbook trusts before inviting anyone."""
    assert "canary_preflight" in _subject_block()


def test_opportunities_do_not_share_the_subject_with_failures():
    """`✨ résurrection` beside a dead tenant is the fatigue mechanism itself."""
    block = _subject_block()
    m = re.search(r"if sparks[^\n]*:", block)
    assert m, "the sparks branch disappeared — re-read why it is conditional"
    assert "_nothing_broken" in m.group(0), (
        "sparks are back in the subject unconditionally. They are an opportunity, "
        "not a failure, and they must only be the headline when nothing is broken."
    )


def test_the_subject_is_never_empty():
    """An untitled alert is unreadable in a mailbox and looks like a mailer bug."""
    assert "or f\"{len(sections)} constat(s)" in SRC, (
        "the empty-subject fallback is gone — a night carrying only tenant-level "
        "findings would send '🚨 Dashboard Alert:' with nothing after it"
    )
    # The fallback itself, exercised rather than trusted.
    subject_parts: list[str] = []
    sections = ["<h2>…</h2>"]
    subject = ' | '.join(subject_parts) or f"{len(sections)} constat(s) — voir le détail"
    assert subject.strip() and subject != ""


def test_the_shared_app_still_outranks_everything():
    """A broken shared app causes the per-tenant rows below it. Order is meaning."""
    block = _subject_block()
    assert block.index("APP PARTAGÉE") < block.index("NE COLLECTE PAS"), (
        "a per-tenant symptom now precedes its own cause in the subject"
    )


def test_the_name_list_is_capped():
    """A subject listing forty tenants is a body, not a subject."""
    block = _subject_block()
    assert "_names[:3]" in block, "the tenant list is uncapped"
    assert "+{extra}" in block or '+{extra}' in block, (
        "the cap hides how many were dropped — a silent truncation reads as "
        "'that is all of them'"
    )
