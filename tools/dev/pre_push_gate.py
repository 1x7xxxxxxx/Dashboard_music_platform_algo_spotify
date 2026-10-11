#!/usr/bin/env python3
"""Pre-push gate: refuse a push whose tree was never seen green by the local suite (R444).

Type: Hook
Uses: git (write-tree, rev-parse, diff-tree)
Triggers: `make test-changed` / `make test` (stamp, on a green run) ; pre-commit pre-push stage (check)
Persists in: .pytest-green-tree (gitignored)

Why: on 2026-10-07 main went red twice (R438 figure ratio, R443 chart review). Both
defects were caught by guards that `make test-changed` runs; both commits were pushed
after targeted tests only. The local gate existed — nothing tied the push to it.

`stamp` records the tree of the WORKING directory (tracked + untracked, .gitignore
honoured), because the suite ran on that tree, not on HEAD. `check` compares it to the
tree of the commit being pushed. A difference limited to the two roadmap files passes:
their readers already run at commit time (`governance-readers`, R361), and every
delivery ends with a roadmap-only commit. R463: so does the night journal
`night-run.jsonl` — append-only, written by `night-start`/`night-done` AFTER the green
run, read by no test as code; counting it refused the night's every push.
Bypass: `git push --no-verify`.

---
rex: []
---
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STAMP = ".pytest-green-tree"
EXEMPT = frozenset({
    ".claude/dev-docs/roadmap/checklist.md",
    ".claude/dev-docs/roadmap/archive.md",
    ".claude/dev-docs/roadmap/night-run.jsonl",
    # R506: detect-secrets rewrites it when a line number shifts — no test reads it.
    ".secrets.baseline",
})
_ZERO = "0" * 40


def _git(root: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                          text=True, env=env).stdout.strip()


def worktree_tree(root: Path) -> str:
    """Tree hash of the working directory as `git add -A` would see it."""
    git_dir = Path(_git(root, "rev-parse", "--absolute-git-dir"))
    with tempfile.TemporaryDirectory() as tmp:
        index = Path(tmp) / "index"
        if (git_dir / "index").exists():
            # copy2, not write_bytes: the copy must keep the index's mtime, or git's
            # racy-entry check trusts a same-size edit made in the same second (R521).
            shutil.copy2(git_dir / "index", index)
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}
        _git(root, "add", "-A", env=env)
        return _git(root, "write-tree", env=env)


def stamp(root: Path) -> str:
    tree = worktree_tree(root)
    (root / STAMP).write_text(tree + "\n")
    return tree


def verdict(root: Path, sha: str) -> tuple[bool, str]:
    """(allowed, reason) for pushing commit `sha`."""
    if not sha or sha == _ZERO:
        return True, "branch deletion"
    pushed = _git(root, "rev-parse", f"{sha}^{{tree}}")
    path = root / STAMP
    if not path.exists():
        return False, "no green local run recorded"
    stamped = path.read_text().strip()
    if stamped == pushed:
        return True, "pushed tree = tree seen green"
    try:
        changed = _git(root, "diff-tree", "-r", "--name-only", stamped, pushed).splitlines()
    except subprocess.CalledProcessError:
        return False, f"stamped tree {stamped[:12]} is unknown to git"
    outside = [f for f in changed if f not in EXEMPT]
    if not outside:
        return True, "only roadmap files changed since the green run"
    head = ", ".join(outside[:5]) + (" …" if len(outside) > 5 else "")
    return False, f"{len(outside)} file(s) changed since the green run: {head}"


def main(argv: list[str]) -> int:
    root = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel"))
    if argv[:1] == ["stamp"]:
        print(f"   tested tree stamped: {stamp(root)[:12]} ({STAMP})")
        return 0
    sha = os.environ.get("PRE_COMMIT_TO_REF") or _git(root, "rev-parse", "HEAD")
    ok, why = verdict(root, sha)
    if ok:
        return 0
    print(f"❌ push refused (R444): {why}.\n"
          "   Run: make test-changed   — it stamps the tree it saw green.\n"
          "   Bypass once, knowingly: git push --no-verify", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
