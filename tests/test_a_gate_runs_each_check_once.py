"""The static-gates step never runs a check that `audit_runner --static` already runs.

Type: Sub
Uses: yaml, .claude/scripts/audit_runner.py, .github/workflows/ci.yml
Depends on: nothing — parses the workflow and the error-class catalogue

On 2026-09-25 the « Portes statiques » job was the CI's critical path (~200 s, against
~130 s per suite shard). `tools/dev/gold_coverage.py --check` cost 20 s and ran TWICE in
it: once as the signature of `a-generated-document-asserts-a-stale-state` inside
`audit_runner --static`, once as its own line a few rows lower. `check_ci_waste.py`
reported « no demonstrable waste »: it is a fleet tool and does not read this catalogue.
"""
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / ".claude" / "scripts"))
import audit_runner  # noqa: E402

_CI = _ROOT / ".github/workflows/ci.yml"
_CATALOGUE = _ROOT / ".claude/dev-docs/error-classes.md"

# Run on purpose BEFORE `--static`: a signature that cannot even parse is reported as
# such first, instead of surfacing as one BROKEN verdict among 48 (its own REX entry).
_ORDERED_BEFORE_STATIC = frozenset({".claude/scripts/audit_runner.py --lint"})


def _command(line: str) -> str:
    """`uv run --frozen python X a` and `python3 X a` both reduce to `X a`."""
    words = line.split()
    for i, w in enumerate(words):
        if w in ("python", "python3"):
            return " ".join(words[i + 1:])
    return ""


def _static_signatures() -> set[str]:
    headers = audit_runner.parse_all_headers(_CATALOGUE.read_text(encoding="utf-8"))
    return {_command(c["signature"]) for c in headers
            if c["signature"] and c["kind"] == "deterministic"
            and "pytest" not in c["signature"]} - {""}


def _duplicated_in_gates(workflow: dict, static: set[str]) -> list[str]:
    steps = workflow["jobs"]["gates"]["steps"]
    runs_static = [s.get("run", "") for s in steps
                   if "audit_runner.py --static" in s.get("run", "")]
    if not runs_static:
        return []
    explicit = {_command(line) for line in runs_static[0].splitlines()
                if not line.strip().startswith("#")} - {""}
    return sorted((explicit & static) - _ORDERED_BEFORE_STATIC)


def test_no_gate_runs_a_check_twice() -> None:
    doubles = _duplicated_in_gates(yaml.safe_load(_CI.read_text(encoding="utf-8")),
                                   _static_signatures())
    assert not doubles, (
        f"{doubles} run as their own line AND as a signature of `audit_runner --static` "
        "in the same step: the critical path pays them twice. Drop the explicit line.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """The step as it was on 2026-09-25 must be refused."""
    before = {"jobs": {"gates": {"steps": [{"run": (
        "uv run --frozen python .claude/scripts/audit_runner.py --lint\n"
        "uv run --frozen python .claude/scripts/audit_runner.py --static\n"
        "# uv run --frozen python tools/dev/commented.py --check\n"
        "uv run --frozen python tools/dev/gold_coverage.py --check\n")}]}}}
    static = {"tools/dev/gold_coverage.py --check", ".claude/scripts/audit_runner.py --lint",
              "tools/dev/commented.py --check"}
    assert _duplicated_in_gates(before, static) == ["tools/dev/gold_coverage.py --check"]
