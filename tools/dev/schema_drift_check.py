#!/usr/bin/env python3
"""
prod ↔ canonical schema drift detector.

The version-controlled schema (`init_db.sql` + `migrations/*.sql`) is the source
of truth; the live prod DB must equal it. Drift creeps in when a column/table is
added to prod outside migrations (manual ALTER, an old code path) or a migration
is never applied. A code path that then reads/writes the drifted column works in
prod but 500s on a fresh install / in CI — exactly the youtube_videos bug.

This compares two `table.column` dumps (one per line, sorted) and reports:
  - PROD-EXTRA      : in prod, not canonical (manual ALTER / orphan / old schema)
  - CANONICAL-EXTRA : in canonical, not prod (migration not applied on prod)
For prod-extra columns it greps src/ to flag USED (→ must be reconciled into the
canonical schema) vs ORPHAN (safe to drop on prod or document).

Usage:
  schema_drift_check.py <prod_dump.tsv> <canonical_dump.tsv>
  # each dump: `SELECT table_name||'.'||column_name FROM information_schema.columns
  #            WHERE table_schema='public' ORDER BY 1`
  # `make schema-check` provisions a throwaway canonical + dumps prod, then calls this.

Exit 1 if any drift is found (report-only by policy — drift can be intentional;
triage the report, do not auto-ALTER prod).

Type: Utility (dev tooling)
"""
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"


def _load(path: str) -> set[str]:
    return {ln.strip() for ln in Path(path).read_text().splitlines() if "." in ln}


def _used_in_src(column: str) -> bool:
    """True if `column` (the bare name) appears in src/ outside schema/init files."""
    try:
        out = subprocess.run(
            ["grep", "-rlwE", column, str(_SRC)],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except Exception:
        return False
    files = [f for f in out.splitlines() if "schema" not in f and "init_db" not in f]
    return bool(files)


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: schema_drift_check.py <prod_dump.tsv> <canonical_dump.tsv>", file=sys.stderr)
        sys.exit(2)
    prod, canon = _load(sys.argv[1]), _load(sys.argv[2])
    prod_tables = {x.split(".", 1)[0] for x in prod}
    canon_tables = {x.split(".", 1)[0] for x in canon}

    prod_extra = sorted(prod - canon)
    canon_extra = sorted(canon - prod)
    tables_prod_only = sorted(prod_tables - canon_tables)

    print(f"prod: {len(prod)} cols / {len(prod_tables)} tables · "
          f"canonical: {len(canon)} cols / {len(canon_tables)} tables\n")

    if tables_prod_only:
        print("## TABLES in prod, absent from canonical (declare in init_db.sql or drop):")
        for t in tables_prod_only:
            tag = "USED" if _used_in_src(t) else "orphan?"
            print(f"  [{tag}] {t}")
        print()

    if prod_extra:
        print("## COLUMNS in prod, absent from canonical:")
        for col in prod_extra:
            tbl, name = col.split(".", 1)
            if tbl in tables_prod_only:
                continue  # already reported as a whole-table drift
            tag = "USED → reconcile into canonical" if _used_in_src(name) else "orphan → drop on prod / document"
            print(f"  [{tag}] {col}")
        print()

    if canon_extra:
        print("## COLUMNS in canonical, absent from prod (migration not applied on prod?):")
        for col in canon_extra:
            print(f"  {col}")
        print()

    if prod_extra or canon_extra:
        print("⚠ schema drift found — triage above (report-only; never auto-ALTER prod). "
              "USED items belong in the version-controlled schema; orphans can be dropped/documented.")
        sys.exit(1)
    print("✅ prod schema == canonical (init_db.sql + migrations)")
    sys.exit(0)


if __name__ == "__main__":
    main()
