#!/usr/bin/env python3
"""
Hook PostToolUse — prod-sync reminder after editing a prod-affecting file.

Fires after Write/Edit on a schema / migration / fresh-install DDL / deploy-ops
file. Prints a soft reminder (stderr) to run the sync analysis so repo↔prod
divergence (the /youtube drift class — a column present in prod but not in the
version-controlled schema) is caught EARLY, not post-deployment. Always exits 0
(non-blocking). The durable rule it nudges: schema changes via migrations only,
and `init_db.sql` + `*_schema.py` must mirror every migration (fresh-install parity).

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
    is_migration = "/migrations/" in norm and norm.endswith(".sql")
    hit = any([
        is_migration,
        base == "init_db.sql",
        "/src/database/" in norm and norm.endswith(".py"),   # *_schema.py, postgres_handler
        "/tools/" in norm and norm.endswith(".sh"),           # deploy/ops scripts
        base.startswith("docker-compose"),
    ])
    if not hit:
        sys.exit(0)

    msg = (f"⚠ prod-affecting file edited ({base}) — run `make sync-check PROD_SSH=user@host` "
           "to confirm repo↔prod stay in sync (schema-drift + deploy-drift).")
    if is_migration:
        msg += (" New migration → also update init_db.sql + src/database/*_schema.py "
                "so fresh installs/CI match prod (never a manual ALTER on prod).")
    print(msg, file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
