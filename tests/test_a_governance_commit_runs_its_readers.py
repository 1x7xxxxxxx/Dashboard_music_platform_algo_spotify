"""R361 — a commit or a closure that touches a governance file runs the tests that NAME it.

Type: Test
Uses: tools/dev/run_readers.py, .pre-commit-config.yaml, Makefile (roadmap-close)
Depends on: git (ls-files / grep) — no live service
Persists in: nothing

The scenario it replays is R356's (2026-10-04): `make roadmap-close ID=R356` left six
requirements naming the closed line; the closure's hint named two tests, neither of which
reads the catalogue, and main's CI went red. What must hold:
1. the readers of the roadmap include the guard that refuses a requirement pointing at a
   closed line (`test_every_requirement_has_a_probe.py`);
2. a basename shared by another tracked file is NOT used as a needle (it would select
   readers of the other file) — only the full path is;
3. the pre-commit hook fires on the roadmap AND on the catalogue, and `roadmap-close`
   calls the gate and fails if it is red.

Mutation record (2026-10-04): seen red with the shared-basename branch removed from
`needles`, with the hook's `files:` narrowed to checklist.md, and with the `|| exit 1`
dropped from the recipe (1 red each), and with the one-hop loop removed from `readers`. The R356 scenario itself, replayed (a requirement
repointed at the closed R356): `run_readers.py` on the roadmap went red in 45 s.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("run_readers", ROOT / "tools/dev/run_readers.py")
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)

ROADMAP = [".claude/dev-docs/roadmap/checklist.md", ".claude/dev-docs/roadmap/archive.md"]


def test_the_roadmap_readers_include_the_requirement_line_guard() -> None:
    assert "tests/test_every_requirement_has_a_probe.py" in rr.readers(ROADMAP)


def test_a_reader_through_a_tool_script_is_found() -> None:
    """The catalogue's main guard reads requirements.yaml only via arch_benchmark.py."""
    got = rr.readers([".claude/dev-docs/architecture/requirements.yaml"])
    assert "tests/test_every_requirement_has_a_probe.py" in got


def test_a_shared_basename_is_not_a_needle() -> None:
    tracked = ["a/README.md", "b/README.md", "c/unique.yaml"]
    assert rr.needles("a/README.md", tracked) == ["a/README.md"]
    assert rr.needles("c/unique.yaml", tracked) == ["c/unique.yaml", "unique.yaml"]


def test_the_hook_and_the_closure_both_run_the_gate() -> None:
    hooks = [h for repo in yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())["repos"]
             for h in repo["hooks"]]
    gate = next(h for h in hooks if h["id"] == "governance-readers")
    pattern = re.compile(gate["files"])
    for path in [*ROADMAP, ".claude/dev-docs/architecture/requirements.yaml"]:
        assert pattern.search(path), path
    recipe = (ROOT / "Makefile").read_text().split("\nroadmap-close:", 1)[1].split("\n\n", 1)[0]
    line = next(x for x in recipe.splitlines() if "run_readers.py" in x)
    assert "checklist.md" in line and "archive.md" in line and "exit 1" in line
