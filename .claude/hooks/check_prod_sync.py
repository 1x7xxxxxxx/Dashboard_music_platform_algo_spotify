#!/usr/bin/env python3
"""
Hook PostToolUse — prod-sync reminder after editing a prod-affecting file.

Fires after Write/Edit on an Alembic revision / DB layer / deploy-ops file. Prints a
soft reminder (stderr) to confirm repo↔IPC stay in sync, so a schema change that never
reaches the deployed Industrial PC (a drift class) is caught EARLY, not post-deployment.
Always exits 0 (non-blocking).

The durable rule it nudges: apply schema changes via an ALEMBIC REVISION, never a manual
ALTER on the IPC Postgres, and keep the deployed DB at the Alembic head.

---
rex: []
---
"""
import json
import os
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if data.get("tool_name") not in ("Write", "Edit"):
        sys.exit(0)
    fp = data.get("tool_input", {}).get("file_path", "")
    if not fp:
        sys.exit(0)

    norm = fp.replace("\\", "/")
    base = os.path.basename(norm)
    is_revision = "/database/migrations/versions/" in norm and norm.endswith(".py")
    hit = any([
        is_revision,
        base == "alembic.ini",
        norm.endswith("/database/migrations/env.py"),
        "/database/" in norm and norm.endswith(".py"),                  # DB layer / repos
        # ^ was "/src/Application/database/" — a path from the repo this payload was
        #   cut from, so this condition could never be true anywhere else. The six
        #   other conditions are already layout-agnostic; this one was the odd one out.
        base.startswith("docker-compose"),
        "/infra/docker/" in norm,                                      # Dockerfiles
        "/tools/ops/" in norm and ("deploy" in base or norm.endswith(".sh")),
    ])
    if not hit:
        sys.exit(0)

    msg = (f"⚠ prod-affecting file edited ({base}) — confirm repo↔IPC stay in sync "
           "(schema + deploy). Apply schema changes via an ALEMBIC REVISION "
           "(database/migrations/versions/), never a manual ALTER on the IPC Postgres.")
    if is_revision:
        msg += (" New revision → keep the deployed IPC DB at the Alembic head and update "
                "architecture/database_schema.md + the CLAUDE.md head ref.")
    print(msg, file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
