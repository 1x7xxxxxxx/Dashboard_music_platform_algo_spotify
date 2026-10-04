"""The generated measurement documents are generated on demand, never versioned.

Type: Hook
Uses: git ls-files, .gitignore
Depends on: a git checkout (no database)
Persists in: nothing

R345 (2026-10-04). `error-class-health.{md,json}`, `error-class-families.md` and
`gold-coverage.md` churned in 302 of 652 commits since 2026-09-20 and nobody read them —
only the gates that checked they were fresh. A versioned generated document that nothing
regenerates is a document that asserts a stale state (`a-generated-document-asserts-a-stale-
state`): once they are out of git, there is no committed state left to go stale. Their
ratchets compute the numbers for the tree (`tools/dev/generated_cache.py`).

This guard refuses the regression: one of them back in the index, or dropped from
`.gitignore` (where `make error-health` would write it as an untracked file, one
`git add -A` away from being versioned again).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GENERATED = (
    ".claude/dev-docs/error-class-health.md",
    ".claude/dev-docs/error-class-health.json",
    ".claude/dev-docs/error-class-families.md",
    ".claude/dev-docs/gold-coverage.md",
    ".generated-cache/",
)


def offenders(tracked: set[str], gitignore: str) -> list[str]:
    """Every generated path that is tracked, or not named in `.gitignore`. Pure."""
    ignored = {ln.strip() for ln in gitignore.splitlines()}
    out = [f"tracked: {p}" for p in GENERATED
           if p in tracked or (p.endswith("/") and any(t.startswith(p) for t in tracked))]
    out += [f"not ignored: {p}" for p in GENERATED if p not in ignored]
    return out


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    clean = "\n".join(GENERATED)
    assert offenders(set(), clean) == []
    assert offenders({".claude/dev-docs/gold-coverage.md"}, clean) == [
        "tracked: .claude/dev-docs/gold-coverage.md"]
    assert offenders({".generated-cache/gold-coverage-abc.txt"}, clean) == [
        "tracked: .generated-cache/"]
    assert offenders(set(), clean.replace(".claude/dev-docs/error-class-health.json", "")) == [
        "not ignored: .claude/dev-docs/error-class-health.json"]


def test_no_generated_document_is_versioned() -> None:
    tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                 text=True, check=True).stdout.splitlines())
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    found = offenders(tracked, gitignore)
    assert not found, (
        f"{found} — a generated measurement document is versioned again (R345). Nothing "
        "regenerates it on commit, so it would assert a stale state within a day. "
        "Remedy: `git rm --cached <path>` and keep it in `.gitignore`.")
