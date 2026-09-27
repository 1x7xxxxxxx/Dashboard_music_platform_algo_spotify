#!/usr/bin/env python3
"""Does the current diff carry a test that WRITES to the database, or a migration?

Type: Utility (dev tooling)
Uses: git (status + unpushed commits)
Triggers: `make test-changed` → `schema-check-local --shared-tables` when it answers yes
Persists in: nothing

R228 (2026-09-27). Two fixtures green locally went red in CI (R219): the local
database is a copy of prod, the CI one is built from init_db.sql + migrations, and
they differed on 13 NOT NULL. `make schema-check-local` sees that drift in ~26 s —
too slow for every loop, exactly right when a test that writes rows is being
edited. Exit 0 = yes (run the check), 1 = no.
"""
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
# A write, as a test performs it: raw SQL or the handler's upsert.
_WRITE = re.compile(r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|upsert_many)\b", re.I)


def writes_db(source: str) -> bool:
    return bool(_WRITE.search(source))


def _changed() -> list[str]:
    cmds = (["git", "status", "--porcelain", "--", "tests", "migrations"],
            ["git", "diff", "--name-only", "@{u}..", "--", "tests", "migrations"])
    names: set[str] = set()
    for cmd in cmds:
        out = subprocess.run(cmd, cwd=_REPO, capture_output=True, text=True).stdout
        names |= {ln[3:] if cmd[1] == "status" else ln for ln in out.splitlines() if ln.strip()}
    return sorted(names)


def needs_schema_check(paths: list[str]) -> bool:
    for rel in paths:
        if rel.startswith("migrations/") and rel.endswith(".sql"):
            return True
        f = _REPO / rel
        if rel.startswith("tests/") and rel.endswith(".py") and f.is_file() \
                and writes_db(f.read_text(errors="replace")):
            return True
    return False


if __name__ == "__main__":
    sys.exit(0 if needs_schema_check(_changed()) else 1)
