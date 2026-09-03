#!/usr/bin/env python3
"""Are the shell scripts this repo ships actually executable where it counts?

Ported from msdr_predictive_maintenance, class `md5-audit-blind-to-file-mode`,
after verifying the same defect is live here.

---
rex:
  - date: 2026-09-03
    issue: "7 of the 12 tracked .sh were indexed 100644, including tools/migrate.sh (Makefile:46 and over SSH to prod :52) and tools/prod_introspect.sh, whose own usage line reads `./tools/prod_introspect.sh` — impossible from a fresh clone."
    fix: "Read the git INDEX, not the working tree: this repo lives on /mnt/c (DrvFs), where the disk does not report the exec bit back to git. `git ls-files -s` is the only honest source here."
    severity: warn
---

## Why the index and not the disk

The repo lives on `/mnt/c` — a DrvFs mount. The working tree's mode bits are
synthesised by the driver and do not round-trip to git, so `find -perm` answers a
question about the mount, not about what a `git clone` on the server will produce.
`git ls-files -s` prints the mode git actually stores. On this machine the disk lies;
the index does not.

## Why this is not hypothetical here

`tools/infra_health_cron.sh:7` says it in the repo's own words: *"(would have caught
the 2026-06-14 incident: db_backup.sh lost its exec bit → no pg_dump since 06-12)"*.
The incident happened, the detector for its neighbourhood was written — and the class
itself was never catalogued. `exec bit`, `chmod`, `100644` returned **zero** hits
across the 2909-line error-class catalogue on 2026-09-03.

The scripts survive today only because every caller happens to write `bash tools/…`,
which is permission-immune. That is the inverted form of the original defect: the
guard passes because the caller works around what it was meant to check.
"""
from __future__ import annotations

import subprocess
import sys

# Scripts that are DELIBERATELY not executable: sourced, not run. Empty today — kept
# so the first legitimate exception is a one-line edit with a reason, rather than a
# pressure to weaken the check.
_SOURCED_ONLY: set[str] = set()


def non_executable_scripts() -> list[str]:
    """Tracked `*.sh` whose stored mode is 100644, in path order."""
    out = subprocess.run(
        ["git", "ls-files", "-s", "--", "*.sh"],
        capture_output=True, text=True, check=True).stdout
    found = []
    for line in out.splitlines():
        if not line.strip():
            continue
        mode, _, rest = line.partition(" ")
        path = rest.split("\t", 1)[-1]
        if mode == "100644" and path not in _SOURCED_ONLY:
            found.append(path)
    return sorted(found)


def main() -> int:
    offenders = non_executable_scripts()
    if not offenders:
        print("✅ every tracked .sh carries its exec bit in the git index")
        return 0
    print(f"⚠ {len(offenders)} tracked .sh stored as 100644 — a fresh clone cannot run them:")
    for p in offenders:
        print(f"   {p}")
    print("\n   Fix:  git update-index --chmod=+x <path>   (then commit)")
    print("   Not `chmod` alone: on /mnt/c the disk mode never reaches the index.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
