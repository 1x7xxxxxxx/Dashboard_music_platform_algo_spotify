"""Guard: the seeded plan row and the real gating describe the same offer.

Type: Utility
Uses: json, re, pathlib
Triggers: pytest
Persists in: nothing

`PLAN_FEATURES` gates the app. `subscription_plans.features` is seeded from the SQL in
the same module and read by NO code — which is exactly why it drifted unnoticed when
`export_pdf` moved to Premium on 2026-09-04: the row still announced it as Free.

A value nobody reads and nobody updates is the most durable form of wrong
documentation: the day something does query it — an export, an admin table, a future
pricing page — it answers with the state of two versions ago.

This compares the three surfaces that must agree:
  1. `_FREE_FEATURES` (the gate),
  2. the JSON seeded by `SCHEMAS['subscription_plans']` (the catalogue),
  3. `migrations/085…` (what production actually holds).
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
sys.path.insert(0, str(REPO))

SCHEMA_PY = REPO / "src" / "database" / "stripe_schema.py"
MIGRATION = REPO / "migrations" / "085_the_seeded_plan_row_follows_the_code.sql"


def _seeded_free() -> set[str]:
    """The JSON array seeded for the `free` plan — read from the AST, not the text.

    The SQL lives inside a Python string constant, so the structural step is: parse
    the module, find that constant, and only THEN read the SQL it holds. Matching the
    module text would make this guard the thing it exists to prevent.
    """
    tree = ast.parse(SCHEMA_PY.read_text(encoding="utf-8"))
    sql_blobs = [n.value for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)
                 and "INSERT INTO subscription_plans" in n.value]
    assert sql_blobs, (
        "no Python constant seeds subscription_plans any more — the catalogue moved "
        "and this guard is now blind")
    m = re.search(r"\('free',\s*[\d.]+,\s*\d+,\s*'(\[[^']+\])'\)", sql_blobs[0])
    assert m, "the seeded 'free' row is no longer recognisable in the SQL"
    return set(json.loads(m.group(1)))


def test_the_seeded_row_matches_the_gate():
    from src.database.stripe_schema import PLAN_FEATURES

    seeded = _seeded_free()
    gate = set(PLAN_FEATURES["free"])
    # `sacem` and `db_health` are gated but were never part of the sold catalogue —
    # they are plumbing, not an offer line. The catalogue may be a SUBSET; it may
    # never claim something the gate refuses.
    overclaimed = sorted(seeded - gate)
    assert not overclaimed, (
        f"the seeded plan row promises {overclaimed}, which PLAN_FEATURES does not "
        "grant to Free. Anyone reading the catalogue — an export, an admin table, a "
        "pricing page — would advertise a feature the app locks."
    )


def test_the_migration_holds_the_same_list_as_the_seed():
    """Production must not be told something the code stopped saying."""
    sql = MIGRATION.read_text(encoding="utf-8")
    body = sql[sql.index("SET features ="):sql.index("::jsonb")]
    # `[a-z0-9_]`, pas `[a-z_]` : la première version manquait
    # `spotify_s4a_combined` — un chiffre au milieu d'un nom — et accusait la migration
    # d'un écart qui n'existait pas. Un garde qui se trompe de raison en criant reste
    # un garde qui crie : la sanction est la même, la confiance non.
    listed = set(re.findall(r'"([a-z0-9_]+)"', body))
    assert listed == _seeded_free(), (
        f"migration 085 and the seed disagree: only in the migration "
        f"{sorted(listed - _seeded_free())}, only in the seed "
        f"{sorted(_seeded_free() - listed)}. Production and a fresh install would "
        "then describe two different offers."
    )
