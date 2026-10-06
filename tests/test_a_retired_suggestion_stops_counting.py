"""R417 — a hook suggestion nobody follows is retired, and once retired it stops counting.

Type: Sub
Uses: tools/dev/arch_benchmark.py (live_suggestion_surfaces, still_suggested, component_activity),
      tools/dev/night_run.py (curator_due)
Depends on: .claude/hooks/, .claude/workflows/
Persists in: nothing

48 sessions printed `/retro`, `/rex-promote`, `/continuous-learning`, `/curator`, `/dev-docs`
and `/adr` and none was followed. Three things must hold together: no live surface prints
the retired names again, the report stops counting a suggestion its printer no longer makes
(the transcripts never forget), and the weekly curator pass runs instead of being asked for.
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RETIRED = ("retro", "rex-promote", "continuous-learning", "curator", "dev-docs", "adr")


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bench = _load("tools/dev/arch_benchmark.py", "arch_benchmark_r417")
night = _load("tools/dev/night_run.py", "night_run_r417")


def test_no_live_surface_prints_a_retired_suggestion() -> None:
    surfaces = bench.live_suggestion_surfaces()
    assert any(f.startswith(".claude/hooks/") for f in surfaces)
    assert any(f.startswith(".claude/workflows/") for f in surfaces)
    still = [n for n in RETIRED if bench.still_suggested(n, surfaces)]
    assert not still, (
        f"{still} is printed again by a hook or an injected workflow: R417 retired these "
        "suggestions because 48 sessions never followed one")


def test_a_suggestion_counts_only_while_a_surface_prints_it() -> None:
    usage = {"found": True, "commands": {}, "skills": {}, "last_seen": {},
             "suggested": {"retro": 12}}
    comp = ".claude/commands/retro.md"
    printed = {".claude/hooks/x.py": 'print("run /retro now")'}
    silent = {".claude/hooks/x.py": 'print("run make roadmap-close")'}
    assert bench.component_activity(comp, usage, printed)["suggere"] == 12
    assert bench.component_activity(comp, usage, silent)["suggere"] == 0
    # A path or a longer name is not the suggestion.
    assert not bench.still_suggested("retro", {"f": "see .claude/commands/retro.md"})
    assert not bench.still_suggested("retro", {"f": "run /retro-all"})


def test_the_weekly_curator_is_due_after_seven_days() -> None:
    assert night.curator_due(None, "2026-10-06"), "never run is due"
    assert night.curator_due("garbage\n", "2026-10-06"), "unreadable is due"
    assert night.curator_due("2026-09-25\n", "2026-10-06")
    assert not night.curator_due("2026-09-29\n", "2026-10-06")
