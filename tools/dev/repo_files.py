"""The repository's files as git sees them AND as the disk holds them — never a nested copy.

Type: Utility (dev)
Uses: subprocess (`git ls-files`), functools.lru_cache
Depends on: a git checkout of the repository
Triggers: nothing — imported by guards in `tests/`
Persists in: nothing

Why this exists — measured on 2026-10-04 at a92856f9
-----------------------------------------------------
Claude Code creates its agent worktrees INSIDE the repository, under
`.claude/worktrees/<name>/` — each one a full copy of the repo (118 MB each, two on disk
that day). They are ignored only by the LOCAL `.git/info/exclude`
(`**/.claude/worktrees/`, in the block Claude Code writes itself), never by `.gitignore`,
so CI never has them. A guard that walks the disk with `rglob`/`os.walk` from the repo
root or from `.claude/` descends into those copies and judges files that are neither in
the tree nor in CI: `test_a_commit_message_is_not_fed_through_stdin.py` went red on four
files, all under `.claude/worktrees/*/tests/`, and never scanned the real `tests/`.

`.gitignore` is not the lever: an ignore rule does not stop a disk walk. Git's own view
of the tree is. `repo_files()` yields a path only when it is BOTH:

  * in `git ls-files --cached --others --exclude-standard` — tracked, or new and not
    ignored, so an uncommitted file still counts and every ignored path (worktrees,
    generated docs, caches) drops out; and
  * present on disk — `--cached` also lists a tracked file that was deleted, and a
    guard asking « does this script exist? » must not be answered by the index.

The listing runs once per root per process (`lru_cache`), with `-z`.

Limits
------
It needs a git checkout: outside one it RAISES rather than falling back to a raw walk —
a silent fallback would reopen exactly the class it closes. It also cannot see a walk
that does not call it; `install_walk_probe()` below is the execution-side net for that.
"""
from __future__ import annotations

import fnmatch
import glob as _glob
import os
import subprocess
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator

NESTED_COPY = (".claude", "worktrees")
"""The path parts under which Claude Code keeps full git-ignored copies of the repo."""


class NotAGitCheckout(RuntimeError):
    """`git ls-files` could not run at this root — there is no tree to filter by."""


@lru_cache(maxsize=None)
def _git_view(root: str) -> frozenset[str]:
    """Repo-relative POSIX paths git considers part of the tree (tracked or new, unignored)."""
    try:
        out = subprocess.run(
            ["git", "-C", root, "ls-files", "-z", "--cached", "--others",
             "--exclude-standard"],
            capture_output=True, check=True, timeout=60).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise NotAGitCheckout(f"git ls-files failed at {root}: {exc}") from exc
    return frozenset(p for p in out.decode("utf-8", "surrogateescape").split("\0") if p)


def repo_files(root: Path, pattern: str = "*", under: str | Path | None = None) -> list[Path]:
    """Files under `root/under` whose NAME matches `pattern`, in git's view AND on disk.

    `pattern` is matched against the file name, the way `rglob(pattern)` matches it.
    """
    root = Path(root).resolve()
    prefix = "" if under in (None, "", ".") else Path(under).as_posix().strip("/") + "/"
    out: list[Path] = []
    for rel in _git_view(str(root)):
        if prefix and not rel.startswith(prefix):
            continue
        if not fnmatch.fnmatchcase(PurePosixPath(rel).name, pattern):
            continue
        p = root / rel
        if p.is_file():
            out.append(p)
    return sorted(out)


def is_in_nested_copy(path: Path | str, root: Path) -> bool:
    """Is `path` inside a git-ignored copy of the repo nested under `root`?"""
    try:
        rel = Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root)))
    except ValueError:
        return False
    parts = rel.parts
    return any(parts[i:i + len(NESTED_COPY)] == NESTED_COPY
               for i in range(len(parts) - len(NESTED_COPY) + 1))


def install_walk_probe(root: Path, sink: list[str]) -> Callable[[], None]:
    """Wrap Path.rglob/glob, os.walk and glob.glob/iglob; log every yield inside a nested copy.

    Returns the function that restores the originals. Execution-side: it binds whatever
    the walker's receiver is called. Its limits: a walk in a SUBPROCESS, a walk bound
    before installation (`from os import walk`), and a skipped test are invisible to it.
    """
    root = Path(root)
    orig_rglob, orig_pglob = Path.rglob, Path.glob
    orig_walk, orig_gglob, orig_iglob = os.walk, _glob.glob, _glob.iglob

    def _log(item: object) -> None:
        p = item[0] if isinstance(item, tuple) else item
        if isinstance(p, (str, os.PathLike)) and is_in_nested_copy(os.fspath(p), root):
            sink.append(os.fspath(p))

    def _watch(it: Iterator) -> Iterator:
        for item in it:
            _log(item)
            yield item

    def rglob(self: Path, *a: object, **k: object) -> Iterator[Path]:
        return _watch(orig_rglob(self, *a, **k))

    def pglob(self: Path, *a: object, **k: object) -> Iterator[Path]:
        return _watch(orig_pglob(self, *a, **k))

    def walk(*a: object, **k: object) -> Iterator:
        return _watch(orig_walk(*a, **k))

    def gglob(*a: object, **k: object) -> list:
        res = orig_gglob(*a, **k)
        for r in res:
            _log(r)
        return res

    def iglob(*a: object, **k: object) -> Iterator:
        return _watch(orig_iglob(*a, **k))

    Path.rglob, Path.glob = rglob, pglob  # type: ignore[method-assign]
    os.walk, _glob.glob, _glob.iglob = walk, gglob, iglob

    def undo() -> None:
        Path.rglob, Path.glob = orig_rglob, orig_pglob  # type: ignore[method-assign]
        os.walk, _glob.glob, _glob.iglob = orig_walk, orig_gglob, orig_iglob

    return undo
