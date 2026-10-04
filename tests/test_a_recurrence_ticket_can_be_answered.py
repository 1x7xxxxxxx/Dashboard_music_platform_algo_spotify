"""R362 — a `recurrence:` ticket can be answered, and the harness report shows what is left.

Type: Test
Uses: tools/dev/defect_log.py (classify, ticket, summary), tools/dev/harness_report.py
Depends on: nothing live — synthetic events in a tmp log
Persists in: nothing

Before R362 a proposal could only stay « à confirmer » forever: nine of them on 2026-10-04,
with no gesture to record the human's verdict, so the count measured nothing. What must hold:
1. an answer needs a known verdict, a reason and an existing proposal;
2. an answered proposal leaves the « à confirmer » count, and a clean return AFTER the
   answer proposes it again (the answer covered only the reds it saw);
3. the harness report turns an open defect and an unanswered ticket into opportunities,
   and an answered one into none.

Mutation record (2026-10-04): seen red with `_answer` ignoring the date of the last clean
return, with `ticket()` accepting any verdict, and with the unanswered filter dropped from
`defect_opportunities`. The CLI test was added after `make defect-ticket` crashed on its
first real use (an argument-padding TypeError the pure tests could not reach).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dev"))

import defect_log as dl  # noqa: E402

_spec = importlib.util.spec_from_file_location("harness_report",
                                               ROOT / "tools/dev/harness_report.py")
hr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hr)

FP = "test:tests/test_x.py::test_y"


def _ev(kind: str, ts: str, **kw) -> dict:
    return {"kind": kind, "fingerprint": FP if kind != "test_green" else "green",
            "ts": f"{ts}T10:00:00.000+00:00", "session": ts, "excerpt": "x", **kw}


def _red(day: str) -> dict:
    return _ev("test_red", day, tree="clean")


def _green(day: str) -> dict:
    return {**_ev("test_green", day, scope="suite", files=[]), "ts": f"{day}T11:00:00.000+00:00"}


def _write(path: Path, events: list[dict]) -> None:
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def _row(path: Path) -> dict:
    return next(r for r in dl.classify(dl.load(path)) if r["fingerprint"] == FP)


def test_an_answer_needs_a_verdict_a_reason_and_a_proposal(tmp_path) -> None:
    log = tmp_path / "d.jsonl"
    _write(log, [_red("2026-10-01")])
    assert dl.ticket(FP, "same-cause", "x", log) == 1          # no proposal yet
    _write(log, [_red("2026-10-01"), _green("2026-10-01"), _red("2026-10-02")])
    assert dl.ticket(FP, "maybe", "x", log) == 1
    assert dl.ticket(FP, "distinct", " ", log) == 1
    assert dl.ticket(FP, "distinct", "two causes", log) == 0
    assert _row(log)["ticket"]["verdict"] == "distinct"


def test_an_answered_ticket_leaves_the_count_until_it_comes_back(tmp_path) -> None:
    log = tmp_path / "d.jsonl"
    events = [_red("2026-10-01"), _green("2026-10-01"), _red("2026-10-02"),
              {**_ev("ticket", "2026-10-03", verdict="same-cause"), "excerpt": "one cause"}]
    _write(log, events)
    rows = dl.classify(dl.load(log))
    assert "billet" not in dl.summary(rows) and _row(log)["ticket"]
    _write(log, events + [_green("2026-10-04"), _red("2026-10-05")])
    assert _row(log)["ticket"] is None
    assert "1 billet(s)" in dl.summary(dl.classify(dl.load(log)))


def test_the_report_lists_open_defects_and_unanswered_tickets_only() -> None:
    rows = [{"fingerprint": "a", "status": "open", "last_seen": "2026-10-04T00", "ticket": None,
             "recurrence_proposal": None},
            {"fingerprint": "b", "status": "green", "last_seen": "2026-10-04T00", "ticket": None,
             "recurrence_proposal": "recurrence:2026-10-01,2026-10-02"},
            {"fingerprint": "c", "status": "green", "last_seen": "2026-10-04T00",
             "recurrence_proposal": "recurrence:2026-10-01,2026-10-02",
             "ticket": {"verdict": "distinct"}}]
    got = {(o["type"], o["ref"]) for o in hr.defect_opportunities(rows)}
    assert got == {("défaut ouvert", "a"), ("billet à répondre", "b")}


def test_the_cli_reaches_the_answer(tmp_path, monkeypatch) -> None:
    log = tmp_path / "d.jsonl"
    _write(log, [_red("2026-10-01"), _green("2026-10-01"), _red("2026-10-02")])
    monkeypatch.setattr(dl, "LOG", log)
    monkeypatch.setattr(dl.ticket, "__defaults__", (log,))
    assert dl.main(["x", "--ticket", FP]) == 1
    assert dl.main(["x", "--ticket", FP, "distinct", "two", "causes"]) == 0
    assert _row(log)["ticket"]["note"] == "two causes"
