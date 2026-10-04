"""Every slash command and skill is named where it can FIRE, or explicitly allowed (R366).

Measured 2026-10-04: `/check-env`, `/logs-airflow`, `/run-tests` had 0 invocations and
were named only in `tooling-reference.md` — a table, which this repository has measured
never triggers anything (33 spawns from imperative rules, 0 from tables). `/run-tests` even
contradicted the « never bare pytest » rule. They were archived; this keeps the next one out.

An imperative surface is one that acts: hooks, scripts, settings, rules, other commands,
skills, agents, workflows, the Makefile, and CLAUDE.md OUTSIDE its tables.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("arch_benchmark_r366", REPO / "tools/dev/arch_benchmark.py")
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)

# A component with no imperative trigger, kept on purpose — each with its reason.
ALLOWED = {
    ".claude/commands/review-architecture.md": "/review-* : invoqué à la main par le propriétaire (décision en attente, R366)",
    ".claude/commands/review-dag.md": "/review-* : invoqué à la main par le propriétaire (décision en attente, R366)",
    ".claude/commands/review-db-schema.md": "/review-* : invoqué à la main par le propriétaire (décision en attente, R366)",
}


def components(root: Path = REPO) -> list[str]:
    return sorted([str(p.relative_to(root)) for p in root.glob(".claude/commands/*.md")]
                  + [str(p.relative_to(root)) for p in root.glob(".claude/skills/*/SKILL.md")])


def orphans(root: Path = REPO) -> list[str]:
    surfaces = ab.imperative_surfaces(root)
    return [c for c in components(root) if not ab.trigger_sites(c, surfaces) and c not in ALLOWED]


def test_every_command_and_skill_is_named_where_it_can_fire() -> None:
    bad = orphans()
    assert not bad, (
        f"No imperative surface names {bad}: they can never fire. Name them in a hook, a rule "
        "or another command with an arrow — or archive them (archive/README.md, one line each).")


def test_the_allowlist_holds_no_dead_entry() -> None:
    assert not [c for c in ALLOWED if not (REPO / c).exists()]


def _tree(tmp: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp / rel).write_text(text, encoding="utf-8")
    return tmp


def test_a_table_or_the_reference_doc_is_not_a_trigger(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        ".claude/commands/ghost.md": "x",
        ".claude/dev-docs/tooling-reference.md": "Run `/ghost` to do it.",
        "CLAUDE.md": "| `/ghost` | a table row |\n",
    })
    assert orphans(root) == [".claude/commands/ghost.md"]


def test_a_hook_or_a_prose_line_is_a_trigger(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        ".claude/commands/adr.md": "x", ".claude/skills/db-schema/SKILL.md": "x",
        ".claude/hooks/h.py": "print('run /adr now')",
        "CLAUDE.md": "→ Full patterns: `.claude/skills/db-schema/SKILL.md`\n",
    })
    assert orphans(root) == []


def test_the_bare_word_and_a_longer_name_are_not_a_trigger(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        ".claude/commands/sweep.md": "x",
        ".claude/hooks/h.py": "# sweep the repo, then /sweep-all and a/sweep path",
    })
    assert orphans(root) == [".claude/commands/sweep.md"]
