"""Guard: a script this repo ships can be run from a fresh clone.

Type: Utility
Uses: pytest, subprocess (git)
Triggers: pytest
Persists in: nothing

Error class `exec-bit-lost-outside-the-index`, ported from
`msdr_predictive_maintenance` on 2026-09-03 after confirming it is live here.

**7 of the 12 tracked `.sh` were stored as `100644`.** Among them:

* `tools/migrate.sh` — invoked by `Makefile:46`, and over SSH against **production**
  at `Makefile:52`;
* `tools/dev/check_prod_ledger.sh` — `Makefile:228`, inside `sync-check`;
* `scripts/backup_db.sh`;
* `tools/prod_introspect.sh` — whose own usage block, line 22, reads
  `./tools/prod_introspect.sh`. That invocation **cannot work from a fresh clone**.

## Why the git index and not the filesystem

This repo lives on `/mnt/c`, a DrvFs mount. The working tree's mode bits are
synthesised by the driver and never round-trip to git, so `find -perm` answers a
question about the mount rather than about what a `git clone` produces on the server.
`git ls-files -s` prints the mode git actually stores. **On this machine the disk
lies; the index does not.** A guard reading the disk here would be green forever.

## Why it had never been caught

Every caller happens to write `bash tools/…`, which is permission-immune. The
scripts work, so nothing complains — until something calls one directly, which is
exactly what `prod_introspect.sh`'s own documentation tells a human to do.

And the repo has already paid for this once. `tools/infra_health_cron.sh:7` says so
itself: *"(would have caught the 2026-06-14 incident: db_backup.sh lost its exec bit
→ no pg_dump since 06-12)"*. The incident happened, a detector for its neighbourhood
was written, and the class was never registered — `exec bit`, `chmod` and `100644`
returned zero hits across the 2909-line catalogue.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".claude" / "scripts"))

from check_exec_bit import non_executable_scripts  # noqa: E402


def test_every_tracked_shell_script_is_executable_in_the_index():
    offenders = non_executable_scripts()
    assert not offenders, (
        f"{len(offenders)} tracked .sh stored as 100644, so a fresh clone or a "
        f"`git archive` produces them non-executable: {offenders}.\n"
        "Fix with `git update-index --chmod=+x <path>` and commit. `chmod` alone is "
        "not enough here: the repo is on /mnt/c (DrvFs) and the disk mode never "
        "reaches the index — which is also why this test reads the index."
    )


def test_the_detector_reads_the_index_and_not_the_disk():
    """Pins the one design decision that makes this guard capable of failing.

    Swapped for a filesystem-permission sweep, it would be green on every machine
    that mounts this repo from Windows — i.e. the only machine it runs on.

    Read through the **AST, with docstrings stripped**, and the first draft of this
    test is why. It searched the raw file text for the string that names the wrong
    approach — and the module's own docstring explains that approach in order to
    reject it, so the guard failed on prose that was correct. Fourth time in this
    repo that a textual guard tripped over its own explanation
    (`a-textual-guard-is-blind`); inspecting code means the AST, never a substring.
    """
    import ast

    src = (Path(__file__).resolve().parents[1] / ".claude" / "scripts"
           / "check_exec_bit.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    # Every string literal that is NOT a docstring — i.e. the arguments the module
    # actually passes at runtime.
    docstrings = {id(ast.get_docstring(n, clean=False)) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))}
    literals = [n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n.value) not in docstrings]
    joined = " ".join(literals)

    assert "ls-files" in joined, (
        "the detector no longer asks git for the STORED mode. On /mnt/c a "
        "filesystem check reports the driver's synthesised bits and can never go red."
    )
    assert "-perm" not in joined, (
        "the detector passes -perm to a filesystem tool. That is the version of this "
        "check that cannot fail on this machine."
    )
