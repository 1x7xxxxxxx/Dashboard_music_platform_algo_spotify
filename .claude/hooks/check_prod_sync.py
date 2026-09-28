#!/usr/bin/env python3
"""
Hook PostToolUse — prod-sync reminder after editing a file that reaches production.

Type: Hook
Triggers: PostToolUse Write/Edit (.claude/settings.json)
Uses: nothing but the edited path

Fires after Write/Edit on a SQL migration, the database layer, a compose file, the deploy
folder or the deploy script, and prints (stderr) the gesture THIS repo uses to keep the
repository and production in step. Always exits 0 (non-blocking).

R310 (2026-09-28): until then this hook was an unmodified copy from another project — it
spoke of an Industrial PC and of Alembic revisions, neither of which exists here, and its
triggers (`/database/migrations/versions/`, `alembic.ini`, `/infra/docker/`) could never fire
on this layout. The gesture it now names is the one CLAUDE.md prescribes: an ADDITIVE file in
`migrations/`, `make migrate` locally, `make migrate-prod` only after a green CI and a backup,
then `make sync-check` (migration ledger, tools/ mount, crontab).

---
rex: []
---
"""
import json
import os
import sys


def is_prod_affecting(path: str) -> bool:
    """Does editing `path` change what production runs? Pure."""
    norm = path.replace("\\", "/")
    base = os.path.basename(norm)
    return any([
        "/migrations/" in norm and norm.endswith(".sql"),
        "/src/database/" in norm and norm.endswith(".py"),
        base.startswith("docker-compose"),
        "/deploy/" in norm,
        norm.endswith("/tools/deploy.sh") or norm.endswith("/tools/migrate.sh"),
    ])


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if data.get("tool_name") not in ("Write", "Edit"):
        sys.exit(0)
    fp = data.get("tool_input", {}).get("file_path", "")
    if not fp or not is_prod_affecting(fp):
        sys.exit(0)

    msg = (f"⚠ fichier qui atteint la production modifié ({os.path.basename(fp)}) — "
           "une migration est un fichier ADDITIF dans migrations/ ; `make migrate` en local, "
           "`make migrate-prod` seulement après une CI verte et une sauvegarde ; puis "
           "`make sync-check` (registre des migrations, montage tools/, crontab).")
    print(msg, file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
