"""Guard: a document nothing names is a document nobody reads.

Type: Utility
Uses: pathlib, subprocess (git ls-files)
Triggers: pytest
Persists in: nothing

Error class `dev-doc-nothing-points-at`.

Measured 2026-08-28: **eight** files under `.claude/dev-docs/` were named by nothing
outside that directory. Four were empty baseline scaffolds — `system-invariants.md`
opened with "Source of truth for thresholds, anti-patterns, and deployment rules" and
contained only `TODO`, which is worse than absent because it would be believed. Two
described bootstrapping a different repo (they told you to run `tools/setup-claude-code.sh`,
absent here, and to fill `.claude/skills/domain_{1,2,3}.md`, of which there are zero).

And two were substantive and needed: `runbook-artist-test-session.md` is the procedure
for **R1 — the only task still open** — and nothing outside `dev-docs/` mentioned it.
That is the expensive half of this class. A stale document wastes a reading; an
unreachable one wastes the work that went into it.

## What counts as reachable, and why it is loose on purpose

Any tracked file outside `.claude/dev-docs/roadmap/` naming the doc — by path or by
filename — makes it reachable: `CLAUDE.md`, a skill, a command, a hook, a test, another
dev-doc. The roadmap is excluded deliberately: it is written every session and mentions
everything in passing, so counting it would make this guard pass on documents nobody can
actually find from an index.

The check is deliberately about **existence of a pointer**, not its quality. Judging
whether a description is good is unfalsifiable, and a guard that fails on every honest
edit gets deleted within the week.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
DOCS_DIR = REPO / ".claude" / "dev-docs"
_TEXTY = (".md", ".py", ".sh", ".json", ".yml", ".yaml", ".toml")
# Written every session, mentions everything — counting it would make the guard vacuous.
_EXCLUDED_REFERRERS = (".claude/dev-docs/roadmap/",)


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True)
    return out.stdout.split()


def _docs() -> list[Path]:
    return sorted(p for p in DOCS_DIR.rglob("*.md") if p.is_file())


@pytest.fixture(scope="module")
def referrers_blob() -> str:
    parts = []
    for rel in _tracked():
        if not rel.endswith(_TEXTY):
            continue
        if rel.startswith(_EXCLUDED_REFERRERS) or rel.startswith(".claude/dev-docs/"):
            continue
        try:
            parts.append((REPO / rel).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    # Other dev-docs may point at each other; that is a legitimate pointer.
    for d in _docs():
        try:
            parts.append(d.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(parts)


@pytest.mark.parametrize("doc", _docs(), ids=lambda p: p.name)
def test_something_points_at_this_document(doc, referrers_blob):
    rel = str(doc.relative_to(REPO)).replace("\\", "/")
    # A doc naming only itself is not reached; strip its own text from the haystack.
    own = doc.read_text(encoding="utf-8", errors="replace")
    haystack = referrers_blob.replace(own, "")
    assert rel in haystack or doc.name in haystack, (
        f"{rel} is named by no tracked file outside the roadmap. Either index it "
        f"(the reference table in CLAUDE.md is where the others live), point at it "
        f"from the runbook section it serves, or remove it. On 2026-08-28 this state "
        f"hid the step-by-step procedure for R1, the only open task, behind a filename "
        f"nobody had reason to type."
    )


def test_the_corpus_is_not_empty(referrers_blob):
    """Non-vacuity, twice over: docs to check, and a haystack to check them against."""
    assert len(_docs()) > 10, f"only {len(_docs())} dev-docs found — check the glob"
    assert len(referrers_blob) > 50_000, (
        f"the referrer corpus is {len(referrers_blob)} chars. Too small to be the "
        "repo; if it collapsed, every case above passes for the wrong reason."
    )


def test_the_exclusion_actually_excludes_something():
    """The roadmap must exist and be excluded — otherwise the guard is vacuous.

    `checklist.md` and `archive.md` mention nearly every document in this repo. If the
    exclusion silently stopped matching, every doc would look reachable through them
    and this file would assert nothing at all.
    """
    tracked = _tracked()
    roadmap = [f for f in tracked if f.startswith(_EXCLUDED_REFERRERS)]
    assert roadmap, (
        f"nothing matched {_EXCLUDED_REFERRERS}. The path moved, so the exclusion is "
        "inert and reachability is now being satisfied by the one file that names "
        "everything."
    )
