#!/usr/bin/env python3
"""The generated measurements, computed ONCE per state of the tree and shared.

Type: Utility
Uses: tools/dev/error_class_health.py (build), tools/dev/gold_coverage.py (build), git
Triggers: the ratchets and value-reading tests (tests/test_the_*_only_improve*.py, …),
          tools/dev/error_debt.py, reopen_check.py, error_class_metrics.py,
          error_class_families.py (recurrence column)
Persists in: .generated-cache/ (gitignored) — one file per generator, keyed by the tree

Why this exists (R345, 2026-10-04)
----------------------------------
Until R345 the generators' output was VERSIONED (`error-class-health.{md,json}`,
`gold-coverage.md`) and every reader opened the committed file in < 0.2 s. 302 commits out
of 652 since 2026-09-20 touched one of them, and nothing read them except the gates that
checked they were fresh. They are now generated on demand — but the ratchets still need the
NUMBERS, and recomputing them costs ~7 s (health: a full git replay) and ~20 s (gold map).
Under xdist each worker is its own process, so an `lru_cache` would pay that per worker
(code-critic R345). This file cache is keyed by the hash of the WORKING TREE as git would
commit it (a throwaway index + `git add -A` + `write-tree`): an edit anywhere — a test, a
tool, the catalogue — changes the key, so a stale number can never be served; ignored files
do not, so writing the cache does not invalidate it.
"""
from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".generated-cache"


def tree_key(root: Path = ROOT) -> str:
    """The tree hash of the working tree, untracked-but-not-ignored files included."""
    def git(*args: str, env: dict | None = None) -> str:
        return subprocess.run(["git", *args], cwd=root, env=env, check=True,
                              capture_output=True, text=True).stdout.strip()

    with tempfile.TemporaryDirectory() as tmp:
        index = Path(tmp) / "index"
        src = Path(git("rev-parse", "--git-path", "index"))
        src = src if src.is_absolute() else root / src
        if src.exists():
            shutil.copy(src, index)              # keeps the stat cache: add -A is fast
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}
        git("add", "-A", env=env)
        return git("write-tree", env=env)


def cached(name: str, compute: Callable[[], str], root: Path = ROOT) -> str:
    """`compute()` for this tree, computed once across processes (flock) and reused."""
    cache = root / ".generated-cache"
    cache.mkdir(exist_ok=True)
    key = tree_key(root)
    target = cache / f"{name}-{key}.txt"
    with open(cache / f"{name}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if target.exists():
            return target.read_text(encoding="utf-8")
        value = compute()
        for old in cache.glob(f"{name}-*.txt"):
            old.unlink()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(value, encoding="utf-8")
        tmp.replace(target)
        return value


def _tool(module: str):
    sys.path.insert(0, str(ROOT / "tools" / "dev"))
    return __import__(module)


def health() -> tuple[str, str]:
    """(json, md) exactly as `make error-health` would write them."""
    raw = cached("error-class-health",
                 lambda: json.dumps(list(_tool("error_class_health").build())))
    js, md = json.loads(raw)
    return js, md


def health_payload() -> dict:
    return json.loads(health()[0])


def health_doc() -> str:
    return health()[1]


def gold_doc() -> str:
    """`gold-coverage.md` exactly as `make gold-coverage` would write it."""
    return cached("gold-coverage", lambda: _tool("gold_coverage").build())
