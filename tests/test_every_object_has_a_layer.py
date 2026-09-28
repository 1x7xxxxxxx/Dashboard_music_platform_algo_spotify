"""R258 (REQ-SILVER-01, critic b + e) — every view has a layer, and gold carries its bounds.

Type: Test
Uses: src/utils/metric_registry.py (REGISTRY, SILVER_MODULES), migrations/*.sql,
      src/utils/gold_invariants.py (bound_sql, bounds_findings, duplicate_findings)

The silver/gold identity was a PREFIX shared by both (`v_*`). It is now mechanical: every
view a migration creates (and does not drop) is registered as gold, and the silver layer is
the declared Python modules (ADR-019). A gold column's bound comes from its NATURE and is
declared once in the registry, checked every evening with the invariants.

Mutation record (2026-09-28) : a view removed from REGISTRY → red ; `bound_sql` accepting
an identifier with a quote → red ; `bounds_findings` skipping the upper side → red.
"""
import re
from pathlib import Path

import pytest

from src.utils.gold_invariants import (bound_sql, bounds_findings, duplicate_findings,
                                       registry_module)

ROOT = Path(__file__).resolve().parents[1]
reg = registry_module()           # the SAME loading the evening check uses

_CREATE = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?VIEW\s+"
                     r"(?:IF\s+NOT\s+EXISTS\s+)?(v_[a-z0-9_]+)", re.I)
_DROP = re.compile(r"DROP\s+(?:MATERIALIZED\s+)?VIEW\s+(?:IF\s+EXISTS\s+)?(v_[a-z0-9_]+)", re.I)


def live_views(texts: list[str]) -> set[str]:
    """Views created by the migrations, minus those a LATER migration drops for good. Pure."""
    live: set[str] = set()
    for text in texts:
        events = sorted([(m.start(), "drop", m.group(1).lower()) for m in _DROP.finditer(text)]
                        + [(m.start(), "create", m.group(1).lower())
                           for m in _CREATE.finditer(text)])
        for _, kind, name in events:
            (live.add if kind == "create" else live.discard)(name)
    return live


def test_every_view_is_gold_or_its_layer_is_declared_not_vacuous():
    texts = [p.read_text(encoding="utf-8") for p in sorted((ROOT / "migrations").glob("*.sql"))]
    views = live_views(texts)
    assert len(views) >= 20, "the migrations are no longer read"
    assert not views - set(reg.REGISTRY), f"vues sans couche : {sorted(views - set(reg.REGISTRY))}"
    assert all((ROOT / m).is_file() for m in reg.SILVER_MODULES)
    assert live_views(["CREATE VIEW v_a AS SELECT 1; DROP VIEW v_a;"]) == set()
    assert live_views(["DROP VIEW IF EXISTS v_a; CREATE OR REPLACE VIEW v_a AS SELECT 1"]) == {"v_a"}


def test_a_bound_is_sql_only_for_plain_identifiers():
    ok = frozenset({"v_x", "v_x;drop"})
    assert bound_sql("v_x", "pop", 0, 100, ok) == (
        "SELECT artist_id, count(*) FROM v_x WHERE pop < 0.0 OR pop > 100.0 GROUP BY artist_id")
    for obj, col in (("v_x;drop", "pop"), ("v_x", "a'b"), ("v_other", "pop")):
        with pytest.raises(ValueError):
            bound_sql(obj, col, 0, None, ok)
    with pytest.raises(ValueError):
        bound_sql("v_x", "pop", None, None, ok)


class _Db:
    def __init__(self, rows):
        self.rows, self.sql = rows, []

    def fetch_query(self, sql, *a):
        self.sql.append(sql)
        return self.rows


def test_every_declared_bound_is_checked_and_named():
    m = type("M", (), {"bounds": (("popularity", 0, 100),)})()
    db = _Db([(7, 3)])
    findings, checked = bounds_findings(db, {"v_pop": m})
    assert checked == 1 and "> 100.0" in db.sql[0] and "artiste 7" in findings[0]
    assert sum(len(x.bounds) for x in reg.REGISTRY.values()) >= 7, "no bound declared"


def test_the_duplicate_scan_names_the_double_write():
    assert "deux fois" in duplicate_findings(_Db([("spotify123", 2)]))[0]
    assert duplicate_findings(_Db([])) == []


def test_an_unmapped_spending_campaign_is_named():
    from src.utils.gold_invariants import unmapped_findings
    assert "sans titre" in unmapped_findings(_Db([(1, 2)]))[0]
    assert unmapped_findings(_Db([])) == []
