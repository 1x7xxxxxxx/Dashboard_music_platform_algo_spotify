"""R356 — every component of the Claude Code harness is named by a requirement, both ways.

Type: Test
Uses: tools/dev/arch_benchmark.py (load, harness_components, component_errors),
      .claude/settings.json, .claude/dev-docs/architecture/requirements.yaml
Depends on: git ls-files (a component must be versioned to count)
Persists in: nothing

Owner, 2026-10-04 : « le seul livrable qui doit être automatiquement mis à jour en cas de
modification ». The harness report is generated from requirements.yaml; it can only fall
behind the configuration if a component enters without a requirement. What must hold:
1. every hook script registered in settings.json, agent, skill, rule, workflow, slash
   command and `make test*` target appears in some requirement's `composants:`;
2. every name listed in `composants:` resolves (versioned file, or existing make target) —
   a renamed hook must not keep a dead entry green;
3. a component named only in prose (`enonce`) does not count;
4. every harness requirement declares `methode` and `portee` from their enums.

Mutation record (2026-10-04): seen red with the coverage check removed, the dead-component
check removed, the enum check removed, the settings hook regex emptied, and the Makefile
`test` prefix changed.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("arch_benchmark",
                                               ROOT / "tools/dev/arch_benchmark.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)


def test_every_harness_component_has_a_requirement() -> None:
    _, reqs = bench.load()
    errs = bench.component_errors(bench.harness_components(), reqs)
    assert not errs, "harnais non couvert par le catalogue :\n" + "\n".join(errs)


def test_the_component_list_reads_every_kind() -> None:
    comps = bench.harness_components()
    for expected in (".claude/hooks/pre_compact.py", ".claude/hooks/session_summary.py",
                     ".claude/agents/code-critic.md", ".claude/skills/db-schema/SKILL.md",
                     ".claude/rules/python.md", ".claude/workflows/engineering-loop.js",
                     ".claude/commands/capitalise.md", "Makefile:test-changed"):
        assert expected in comps, expected


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    _, reqs = bench.load()
    comps = bench.harness_components()
    # 1. a newly registered hook with no requirement
    settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    settings["hooks"].setdefault("Stop", []).append(
        {"hooks": [{"type": "command", "command": "python3 .claude/hooks/new_dummy_hook.py"}]})
    fake = tmp_path / "settings.json"
    fake.write_text(json.dumps(settings), encoding="utf-8")
    more = bench.harness_components(settings_path=fake)
    assert ".claude/hooks/new_dummy_hook.py" in more
    assert any("new_dummy_hook" in e for e in bench.component_errors(more, reqs))
    # 2. a component named only in an enonce does not count
    prose = [{**r, "composants": [c for c in r.get("composants") or []
                                  if c != ".claude/hooks/pre_compact.py"]}
             if r.get("composants") else r for r in reqs]
    prose.append({"id": "REQ-X", "enonce": ".claude/hooks/pre_compact.py", "methode": "hook",
                  "portee": "generique"})
    assert any("pre_compact" in e for e in bench.component_errors(comps, prose))
    # 3. a dead entry in composants
    dead = [*reqs, {"id": "REQ-Y", "composants": [".claude/hooks/renamed_away.py",
                                                   "Makefile:no-such-target"],
                    "methode": "hook", "portee": "generique"}]
    errs = bench.component_errors(comps, dead)
    assert any("renamed_away" in e for e in errs) and any("no-such-target" in e for e in errs)
    # 4. an enum outside its list
    bad = [*reqs, {"id": "REQ-Z", "composants": [], "methode": "magie", "portee": "partout"}]
    errs = bench.component_errors(comps, bad)
    assert any("magie" in e for e in errs) and any("partout" in e for e in errs)
