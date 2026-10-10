"""R508 — the Makefile is its own index, and what it promises it does.

Type: Test
Uses: re, subprocess (`make -n`, `make help`, a tombstone run)
Depends on: Makefile, .github/workflows/ci.yml
Persists in: nothing

Measured on 2026-10-10: 97 targets while CLAUDE.md announced 11; 23 missing from
`.PHONY`; `lint` ran another ruff on another scope than the CI gate; retired targets
still typed from habit (`error-families-check` ×70) answered « No rule to make target »;
and 159 full-suite runs went SERIAL because `make test` took no subset. What must hold:
1. every target is `.PHONY` (none of them builds a file of its own name);
2. `make help` prints every documented target, under a `##@` section;
3. `make test ARGS=…` keeps the computed worker count and does not stamp the push gate;
4. `make lint` runs the CI's exact ruff command;
5. a tombstone fails (exit ≠ 0) and names what replaced it.

Mutation record (2026-10-11): seen red with a target removed from `.PHONY`, `ARGS`
dropped from the `test` recipe, `lint` back to `ruff check src/ tests/`, the `##@`
handling removed from `help`, and a tombstone's `exit 1` removed.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _makefile() -> str:
    return (_ROOT / "Makefile").read_text(encoding="utf-8")


def _make(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["make", "-s", *args], cwd=_ROOT, capture_output=True,
                          text=True, timeout=60)


def _targets(text: str) -> set[str]:
    out: set[str] = set()
    for head in re.findall(r"^([a-z][a-z0-9_ -]*):(?!=)", text, re.M):
        out.update(head.split())
    return out


def test_every_target_is_phony() -> None:
    text = _makefile()
    phony: set[str] = set()
    for line in re.findall(r"^\.PHONY:(.*)$", text, re.M):
        phony.update(line.split())
    targets = _targets(text)
    assert len(targets) > 50, "anti-vacuity: the target regex reads nothing"
    missing = sorted(targets - phony)
    assert not missing, f"targets missing from .PHONY: {missing}"


def test_help_lists_every_documented_target_under_a_section() -> None:
    out, text = _make("help").stdout, _makefile()
    documented = re.findall(r"^([a-z][a-z0-9_-]*):[^\n]*##", text, re.M)
    listed = set(re.findall(r"^  ([a-z][a-z0-9_-]*) ", out, re.M))
    assert set(documented) <= listed, sorted(set(documented) - listed)
    sections = re.findall(r"^##@ (.+)$", text, re.M)
    assert len(sections) >= 5 and all(s in out for s in sections), "##@ sections not printed"


def test_test_with_args_keeps_the_workers_and_skips_the_stamp() -> None:
    subset = str(Path(__file__).relative_to(_ROOT))
    dry = _make("-n", "test", f"ARGS={subset}").stdout
    assert f"pytest {subset} -q -n" in dry, "ARGS= is not the pytest target"
    assert f'[ -n "{subset}" ] && exit' in dry, "a subset would stamp the gate"
    full = _make("-n", "test").stdout
    assert "pytest tests/ -q -n" in full


def test_lint_is_the_ci_gate() -> None:
    ci = (_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    command = re.search(r"run: (uv run --frozen ruff check \S+)", ci).group(1)
    recipe = re.search(r"^lint:.*\n((?:\t.*\n)+)", _makefile(), re.M).group(1)
    assert command in recipe, f"make lint is not `{command}`"


def test_a_tombstone_fails_naming_its_replacement() -> None:
    for name in ("error-families-check", "chart-decisions"):
        run = _make(name)
        assert run.returncode != 0, f"{name} exits 0 — a retired check reads as passed"
        assert "make " in run.stdout + run.stderr, f"{name} does not name its replacement"
