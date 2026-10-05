"""Every slash command and skill is named where it can FIRE, or explicitly allowed (R366).

Measured 2026-10-04: `/check-env`, `/logs-airflow`, `/run-tests` had 0 invocations and
were named only in `tooling-reference.md` — a table, which this repository has measured
never triggers anything (33 spawns from imperative rules, 0 from tables). `/run-tests` even
contradicted the « never bare pytest » rule. They were archived; this keeps the next one out.

An imperative surface is one that acts: hooks, scripts, settings, rules, other commands,
skills, agents, workflows, the Makefile, and CLAUDE.md OUTSIDE its tables.

R413 (2026-10-05): the hand-kept allowlist became `invocation: manual — <why>` in the
component's own frontmatter, read here AND by the harness report (one source).
Mutation: `manual_invocation` returning None → RED (2 tests).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("arch_benchmark_r366", REPO / "tools/dev/arch_benchmark.py")
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)



def components(root: Path = REPO) -> list[str]:
    return sorted([str(p.relative_to(root)) for p in root.glob(".claude/commands/*.md")]
                  + [str(p.relative_to(root)) for p in root.glob(".claude/skills/*/SKILL.md")])


def orphans(root: Path = REPO) -> list[str]:
    surfaces = ab.imperative_surfaces(root)
    return [c for c in components(root) if not ab.trigger_sites(c, surfaces)
            and not ab.manual_invocation(c, root)]


def test_every_command_and_skill_is_named_where_it_can_fire() -> None:
    bad = orphans()
    assert not bad, (
        f"No imperative surface names {bad}: they can never fire. Name them in a hook, a rule "
        "or another command with an arrow, declare `invocation: manual — <why>` in their "
        "frontmatter, or archive them (archive/README.md, one line each).")


def test_a_manual_component_says_why() -> None:
    """R413: the exception lives in the component's own frontmatter, with its reason."""
    manual = {c: ab.manual_invocation(c) for c in components() if ab.manual_invocation(c)}
    assert manual, "the three /review-* commands are declared manual"
    assert all(len(why) >= 20 for why in manual.values()), manual


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
