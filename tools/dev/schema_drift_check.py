#!/usr/bin/env python3
"""
prod ↔ canonical schema drift detector.

The version-controlled schema (`init_db.sql` + `migrations/*.sql`) is the source
of truth; the live prod DB must equal it. Drift creeps in when a column/table is
added to prod outside migrations (manual ALTER, an old code path) or a migration
is never applied. A code path that then reads/writes the drifted column works in
prod but 500s on a fresh install / in CI — exactly the youtube_videos bug.

This compares two schema dumps (one object per line, sorted) and reports:
  - PROD-EXTRA      : in prod, not canonical (manual ALTER / orphan / old schema)
  - CANONICAL-EXTRA : in canonical, not prod (migration not applied on prod)

Three kinds of object, distinguished by a line prefix (a bare line = a column, so
older dumps still work):
  `table.column`                    a column
  `key:table:PRIMARY KEY (id)`      a PK / UNIQUE / FK constraint
  `uix:table:(artist_id, video_id)` a UNIQUE index
  `trg:table:trigger:function`      a user trigger (R368 — ADR-018's history lives in them)

Constraints and unique indexes are compared by DEFINITION, never by name: two
databases legitimately name the same constraint differently, and the name is not
what `ON CONFLICT` resolves against. This category was added on 2026-08-20 after a
column-only comparison reported "prod == canonical" while prod's
`youtube_videos` PRIMARY KEY was on `video_id` and the canonical one on `id` —
a divergence that makes a video belong to a single tenant, and that later broke a
production upsert. A drift the checker cannot see is a drift nobody triages.
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


def _load(path: str) -> dict[str, set[str]]:
    """Split a dump file into {columns, keys, unique indexes}."""
    return parse_dump(Path(path).read_text())


def parse_dump(text: str) -> dict[str, set[str]]:
    """Split a dump's text into {columns, keys, unique indexes}. Pure."""
    buckets: dict[str, set[str]] = {"col": set(), "key": set(), "uix": set(), "nn": set(), "trg": set()}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("key:"):
            buckets["key"].add(line[4:])
        elif line.startswith("uix:"):
            buckets["uix"].add(line[4:])
        elif line.startswith("trg:"):
            buckets["trg"].add(line[4:])
        elif line.startswith("nn:"):
            buckets["nn"].add(line[3:])
        elif line.startswith("col:"):
            buckets["col"].add(line[4:])
        elif "." in line:
            buckets["col"].add(line)   # bare line = a column (pre-2026-08 dumps)
    return buckets


def find_drift(live: dict[str, set[str]], canon: dict[str, set[str]]) -> dict:
    """Every difference between a live dump and the canonical one, both sides. Pure.

    `found` is the gate's decision: a column, table, constraint or unique index present
    on ONE side only. Names, not types — see `schema_fingerprint.sql` for why.
    """
    live_tables = {x.split(".", 1)[0] for x in live["col"]}
    canon_tables = {x.split(".", 1)[0] for x in canon["col"]}
    out: dict = {
        "live_extra": sorted(live["col"] - canon["col"]),
        "canon_extra": sorted(canon["col"] - live["col"]),
        "tables_live_only": sorted(live_tables - canon_tables),
    }
    for kind in ("key", "uix", "nn", "trg"):
        lv, cv = live.get(kind, set()), canon.get(kind, set())
        out[f"{kind}_live_only"] = sorted(lv - cv)
        out[f"{kind}_canon_only"] = sorted(cv - lv)
    out["found"] = any(out.values())
    return out


def _table_of(item: str) -> str:
    """`t.col`, `t:KEY (...)` → `t`."""
    return item.replace(":", ".", 1).split(".", 1)[0]


def on_shared_tables(drift: dict) -> dict:
    """The drift restricted to tables BOTH sides have. Pure.

    R228 (2026-09-27): what makes a fixture green locally and red in CI is a column,
    a key or a NOT NULL that differs on a table the CI also builds (R219). A table
    only the local database carries — a leftover nothing writes — cannot flip a
    test that way, and gating on it would make `make test-changed` red for good on
    a debris the developer cannot drop from a test run.
    """
    local_only = set(drift["tables_live_only"])
    out = {k: [x for x in v if _table_of(x) not in local_only]
           for k, v in drift.items() if isinstance(v, list) and k != "tables_live_only"}
    out["tables_live_only"] = []
    out["found"] = any(out.values())
    return out


def unreadable_dumps(dumps: dict[str, dict[str, set[str]]]) -> list[str]:
    """Paths whose dump carries no column at all. Pure.

    A real schema always has columns; a dump with none is a read that failed.
    """
    return [path for path, dump in dumps.items() if not dump["col"]]


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
    shared_only = "--shared-tables" in sys.argv
    if shared_only:
        sys.argv.remove("--shared-tables")
    if len(sys.argv) not in (3, 4):
        print("usage: schema_drift_check.py <live_dump.tsv> <canonical_dump.tsv> [label]",
              file=sys.stderr)
        sys.exit(2)
    # The label names WHICH live database was compared. It defaulted to "prod" and
    # was printed verbatim when `schema-check-local` compared the LOCAL database —
    # a report that misnames what it measured is how a green gets misread.
    side = sys.argv[3] if len(sys.argv) == 4 else "prod"
    prod_all, canon_all = _load(sys.argv[1]), _load(sys.argv[2])
    unreadable = unreadable_dumps({sys.argv[1]: prod_all, sys.argv[2]: canon_all})
    if unreadable:
        # R495 — an empty dump is a psql/ssh that never answered. Diffed, it reports
        # every column of the other side as « absent » and exits 1: a crash read as
        # drift. Exit 2 is « no verdict », distinct from drift (1) and clean (0).
        print(f"⊘ dump illisible, sans aucune colonne : {', '.join(unreadable)} — la "
              "lecture du schéma a échoué, ce n'est PAS une dérive", file=sys.stderr)
        sys.exit(2)
    prod, canon = prod_all["col"], canon_all["col"]
    prod_tables = {x.split(".", 1)[0] for x in prod}
    canon_tables = {x.split(".", 1)[0] for x in canon}
    drift = find_drift(prod_all, canon_all)
    prod_extra, canon_extra = drift["live_extra"], drift["canon_extra"]
    tables_prod_only = drift["tables_live_only"]

    print(f"{side}: {len(prod)} cols / {len(prod_tables)} tables · "
          f"canonical: {len(canon)} cols / {len(canon_tables)} tables\n")

    if tables_prod_only:
        print("## TABLES in prod, absent from canonical (declare in init_db.sql or drop):")
        for t in tables_prod_only:
            tag = "USED" if _used_in_src(t) else "orphan?"
            print(f"  [{tag}] {t}")
        print()

    if prod_extra:
        print(f"## COLUMNS in {side}, absent from canonical:")
        for col in prod_extra:
            tbl, name = col.split(".", 1)
            if tbl in tables_prod_only:
                continue  # already reported as a whole-table drift
            tag = "USED → reconcile into canonical" if _used_in_src(name) else "orphan → drop on prod / document"
            print(f"  [{tag}] {col}")
        print()

    if canon_extra:
        print(f"## COLUMNS in canonical, absent from {side} (migration not applied there?):")
        for col in canon_extra:
            print(f"  {col}")
        print()

    # ── Constraints and unique indexes — what ON CONFLICT actually resolves ──
    for kind, label in (("key", "CONSTRAINTS (PK / UNIQUE / FK)"),
                        ("uix", "UNIQUE INDEXES"),
                        ("trg", "TRIGGERS (a lost trg_revision_* loses history, ADR-018)")):
        only_prod, only_canon = drift[f"{kind}_live_only"], drift[f"{kind}_canon_only"]
        if not (only_prod or only_canon):
            continue
        print(f"## {label} — divergent (compared by definition, not by name):")
        for item in only_prod:
            print(f"  [{side} only]{' ' * max(1, 12 - len(side))}{item}")
        for item in only_canon:
            print(f"  [canonical only] {item}")
        if kind == "trg":
            print("  → a trigger present on one side only: an UPDATE writes history there "
                  "and not here. Reconcile by migration.\n")
            continue
        print("  → a difference here changes which rows can coexist and which "
              "`ON CONFLICT` targets resolve. Reconcile before deploying code that "
              "upserts on them.\n")

    # ── NOT NULL — R219 (2026-09-27): the fingerprint compared names, keys and unique
    # indexes, never nullability, so 13 columns NOT NULL in canonical and NULLable in
    # prod passed as « prod == canonical » — until two test fixtures, green locally,
    # went red in CI. Only on columns BOTH sides have: a missing column is reported above.
    both = prod & canon
    nn_prod = [c for c in drift["nn_live_only"] if c in both]
    nn_canon = [c for c in drift["nn_canon_only"] if c in both]
    if nn_prod or nn_canon:
        print("## NOT NULL — divergent:")
        for c in nn_canon:
            print(f"  [NOT NULL in canonical only] {c}  → CI refuses a NULL that {side} accepts")
        for c in nn_prod:
            print(f"  [NOT NULL in {side} only]{' ' * max(1, 8 - len(side))}{c}  → {side} refuses what CI accepts")
        print("  → a test green on one side is red on the other. Reconcile by migration "
              "(SET / DROP NOT NULL), never by editing a fixture to fit.\n")

    if shared_only and drift["found"] and not on_shared_tables(drift)["found"]:
        print(f"✅ {side} == canonical on every table both carry — "
              f"{len(tables_prod_only)} {side}-only table(s) reported above, not gated (R228)")
        sys.exit(0)
    if drift["found"]:
        print("⚠ schema drift found — triage above (report-only; never auto-ALTER prod). "
              "USED items belong in the version-controlled schema; orphans can be dropped/documented.")
        sys.exit(1)
    print(f"✅ {side} schema == canonical (init_db.sql + migrations)")
    sys.exit(0)


if __name__ == "__main__":
    main()
