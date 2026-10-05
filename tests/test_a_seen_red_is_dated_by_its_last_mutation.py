"""A red seen by hand is dated by its NEWEST mutation, not its first (R412).

Type: Test
Uses: tools/dev/arch_benchmark.py (last_red, proof_state)
Depends on: `git log` of one tracked test file
Persists in: nothing

SEEN_RED entries grow by appending: « 2026-10-04 — mutation A ; 2026-10-05 — mutation B ».
The benchmark read the first ten characters, so a guard re-mutated after its file changed
still read « vu rouge périmé — re-muter » — 11 proofs on 2026-10-05, 7 of them re-mutated
that same day by R368. The harness report asked for work already done.

Mutation record (2026-10-05): `last_red` returning `detail[:10]` → RED (both tests).
Not covered: a file edited later on the SAME day as its mutation — the dates are days.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("arch_benchmark", ROOT / "tools/dev/arch_benchmark.py")
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)

_TRACKED = "tools/dev/arch_benchmark.py"   # any tracked file: `git log` dates it


def test_the_newest_date_wins_wherever_it_is_written() -> None:
    assert ab.last_red("2026-10-04 — A → 1 rouge ; 2026-10-05 — R368 : B → 1 rouge") == "2026-10-05"
    assert ab.last_red("2026-09-27 — seule mutation") == "2026-09-27"


def test_a_proof_remutated_after_its_file_changed_is_not_stale() -> None:
    req = {"preuve": {"pytest": f"{_TRACKED}::x"}}
    never = lambda _p: False  # noqa: E731
    old = ab.proof_state(req, "vert", {_TRACKED: "2000-01-01 — mutation"}, never)
    assert old["vu_rouge"]["perime"] is True
    redone = ab.proof_state(req, "vert", {_TRACKED: "2000-01-01 — A ; 2999-01-01 — B"}, never)
    assert redone["vu_rouge"]["perime"] is False, redone
