#!/usr/bin/env python3
"""Did a verification command JUDGE its subject, or did it fall over? Pure.

Type: Utility
Uses: nothing (re only)
Triggers: imported by .claude/scripts/audit_runner.py, tools/dev/mutate_guards.py,
          tools/dev/probe_error_management.py, tools/dev/arch_benchmark.py
Depends on: the text pytest prints (E-lines at --tb=short/long, the -r short summary)
Persists in: nothing

R495 — class `a-crash-credited-as-a-judgement`. A non-zero exit has three readings, not
two: a RED judgement (an assertion, a `pytest.fail`, a gate that refuses), GREEN, and a
CRASH (NameError, ImportError, a setup ERROR, a dead ssh) — the command produced no
verdict at all. Thirteen tools read the exit code alone, so a crash came out as « HIT »,
« seen red », « refused », or « threshold crossed ».

The predicates are TOOL-SPECIFIC on purpose (code-critic, R495): « no assert E-line » is
evidence of a crash only in pytest output printed with a traceback style that has E-lines.
Applied to a `grep` exiting 1, it would call every hit a crash. For a non-pytest command
the only crash evidence is a Python traceback header at the start of a line.

ORDER matters: a judgement wins over any traceback in the same output. A FAILED test that
runs a subprocess expected to fail carries a genuine `Traceback (most recent call last)`
under « Captured stderr » — and it is still a judgement.

Known blind spots (guard_scope of the class): an assertion whose message wraps a crash
text still reads as a judgement; a judgement raised as `E   ValueError` / `SystemExit`
reads as a crash; pytest output printed with `--tb=line`/`--tb=no` and no `-r` summary
has nothing to read, and keeps the old reading (red).

---
rex: []
---
"""
from __future__ import annotations

import re

GREEN, RED, CRASH = "green", "red", "crash"

_TRACEBACK = re.compile(r"^Traceback \(most recent call last\)", re.M)
_JUDGEMENT_E = re.compile(r"^E\s+(?:AssertionError\b|assert\b|Failed:)", re.M)
_ANY_E = re.compile(r"^E\s", re.M)
_JUDGEMENT_MSG = re.compile(r"^(?:AssertionError\b|assert\b|Failed:|\[XPASS\(strict\)\])")
_SUMMARY = re.compile(r"^(FAILED|ERROR)\s+(\S+?)(?:\s+-\s+(.*))?$", re.M)
_PYTEST_CMD = re.compile(r"(?:^|[\s/])(?:py\.test|pytest)\b|-m\s+pytest\b")


def looks_like_traceback(output: str) -> bool:
    """A Python traceback header at the start of a line."""
    return bool(_TRACEBACK.search(output or ""))


def is_judgement_pytest(output: str) -> bool:
    """pytest output (tb=short/long) carries at least one assertion or `Failed:` E-line."""
    return bool(_JUDGEMENT_E.search(output or ""))


def is_pytest_command(cmd: str) -> bool:
    return bool(_PYTEST_CMD.search(cmd or ""))


def summary_nodes(output: str) -> list[tuple[str, str, str]]:
    """(FAILED|ERROR, node-id, message) from pytest's `-r` short summary."""
    return [(k, n, (m or "").strip()) for k, n, m in _SUMMARY.findall(output or "")]


def node_kind(outcome: str, message: str) -> str:
    """One summary line → RED (a judgement), CRASH, or '' (cannot tell from the line).

    ERROR is a setup/teardown/collection failure: the test body never judged anything.
    """
    if outcome == "ERROR":
        return CRASH
    if not message:
        return ""
    return RED if _JUDGEMENT_MSG.search(message) else CRASH


def classify_pytest(rc: int, output: str) -> str:
    """Three-way verdict of a pytest run. rc ∉ {0, 1} never judged anything."""
    if rc == 0:
        return GREEN
    if rc != 1:
        return CRASH
    if is_judgement_pytest(output):
        return RED
    kinds = [node_kind(k, m) for k, _n, m in summary_nodes(output)]
    if RED in kinds:
        return RED
    if CRASH in kinds or _ANY_E.search(output or "") or looks_like_traceback(output):
        return CRASH
    return RED          # nothing to read (--tb=no without -r): keep the old reading


def classify_command(rc: int, output: str) -> str:
    """Three-way verdict of an arbitrary command: only a traceback header is a crash."""
    if rc == 0:
        return GREEN
    if is_judgement_pytest(output):
        return RED
    if rc == 1 and looks_like_traceback(output):
        return CRASH
    return RED


def classify(rc: int, output: str, *, pytest: bool) -> str:
    return classify_pytest(rc, output) if pytest else classify_command(rc, output)
