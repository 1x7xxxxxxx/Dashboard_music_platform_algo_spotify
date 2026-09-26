"""A join never multiplies the grain of the side it enriches.

Type: Sub
Uses: the live schema (v_meta_campaign_daily, v_meta_engagement_daily, v_meta_ad_daily,
      meta_insights_*), src/dashboard read as AST
Depends on: tests/db_gate.py (the live half skips without Postgres), migration 138
Persists in: nothing — the synthetic tenants and their rows are deleted on exit

Measured on `spotify_etl_review`, 2026-09-26. Meta Ads read its engagement raw from
`meta_insights_engagement` — one row per campaign AND per day, plus 21 lifetime rows —
and joined it to per-campaign or per-day frames on `campaign_name` alone:

  * the chart merge turned 21 campaigns into 252 rows; « the 12 biggest spenders »
    drew 12 copies of ONE campaign (12 x 755.52 EUR, 12 x 5 963 clicks);
  * the Saves / Shares / Interactions tiles summed lifetime rows and days: exactly 2x
    (1 094 / 16 / 957 320 for 547 / 8 / 478 968);
  * the summary table joined day x day under `SUM(p.spend)`: 24 176.64 EUR for a
    755.52 EUR campaign (x 32);
  * and the Réglages tab joined `meta_ads x meta_insights` on `ad_id` alone, adding
    the sandbox tenant's copies: 6 168.70 EUR shown for 3 087.82 EUR spent.

No guard saw any of it: the metrics-layer ratchet did not list the engagement table and
matched only `FROM <fact>`, never `JOIN <fact>`; and a fan-out that plotly stacks on one
y-category is a reduction no test looked for.

Three halves:
  * live, synthetic: two tenants seeded with the exact shapes above (lifetime row, days,
    a copied `ad_id`); each surface's OWN query must return one row per campaign and the
    gold total. The numbers are small and chosen so each defect gives a distinct wrong
    total;
  * live, real data: on every tenant present, the summary table totals what
    `v_meta_campaign_daily` totals, and each Réglages axis totals the tenant's own spend;
  * static: every `merge` under the display surfaces declares `validate=` — pandas then
    RAISES on a non-unique key at run time — with the unvalidated ones frozen under a
    per-file ceiling that only goes down.

Class: `a-join-that-multiplies-the-grain` (family `deux-surfaces-deux-nombres`).
"""
from __future__ import annotations

import ast
import datetime as dt
import uuid
from pathlib import Path

import pytest

from tests.db_gate import requires_live_db

_ROOT = Path(__file__).resolve().parents[1]


# ── live, synthetic ───────────────────────────────────────────────────────

def _db():
    from tests.db_gate import dsn
    from src.database.postgres_handler import PostgresHandler
    return PostgresHandler(**dsn())


def _tenant(db, tag: str) -> int:
    slug = f"fanout-{tag}-{uuid.uuid4().hex[:8]}"
    return db.fetch_query("INSERT INTO saas_artists (name, slug, tier, active) "
                          "VALUES (%s, %s, 'free', FALSE) RETURNING id", (slug, slug))[0][0]


_DAYS = {"c1": (10, 20, 30), "c2": (5, 5)}          # spend per day → gold total 70
_SAVES = {"c1": (1, 2, 3), "c2": (1, 1)}            # saves per day → gold total 8


def _seed_campaigns(db, tenant: int) -> None:
    today = dt.date.today()
    for camp, spends in _DAYS.items():
        for i, spend in enumerate(spends):
            day = today - dt.timedelta(days=i + 1)
            for table, col in (("meta_insights_performance", "date_start"),
                               ("meta_insights_performance_day", "day_date")):
                db.execute_query(f"INSERT INTO {table} (artist_id, campaign_name, {col}, "
                                 "spend) VALUES (%s, %s, %s, %s)", (tenant, camp, day, spend))
            saves = _SAVES[camp][i]
            for table, col in (("meta_insights_engagement", "date_start"),
                               ("meta_insights_engagement_day", "day_date")):
                db.execute_query(f"INSERT INTO {table} (artist_id, campaign_name, {col}, "
                                 "saves, shares, page_interactions) VALUES (%s, %s, %s, %s, 0, 0)",
                                 (tenant, camp, day, saves))
    # The lifetime rows of the earlier collector: no `_day` twin.
    old = today - dt.timedelta(days=40)
    db.execute_query("INSERT INTO meta_insights_performance (artist_id, campaign_name, "
                     "date_start, spend) VALUES (%s, 'c1', %s, 60)", (tenant, old))
    db.execute_query("INSERT INTO meta_insights_engagement (artist_id, campaign_name, "
                     "date_start, saves, shares, page_interactions) "
                     "VALUES (%s, 'c1', %s, 6, 0, 0)", (tenant, old))


def _seed_ad(db, owner: int, sandbox: int, ad_id: str, camp_id: str) -> None:
    """One ad owned by `owner`; `sandbox` carries insights for the SAME ad_id."""
    db.execute_query("INSERT INTO meta_campaigns (campaign_id, campaign_name, objective, "
                     "artist_id) VALUES (%s, 'c1', 'OUTCOME_ENGAGEMENT', %s)", (camp_id, owner))
    db.execute_query("INSERT INTO meta_ads (ad_id, campaign_id, ad_name, title, call_to_action, "
                     "artist_id) VALUES (%s, %s, 'Fan-out guard ad', 'T', 'LISTEN_NOW', %s)", (ad_id, camp_id, owner))
    day = dt.date.today() - dt.timedelta(days=1)
    for tenant, spend in ((owner, 7), (sandbox, 11)):
        db.execute_query("INSERT INTO meta_insights (artist_id, ad_id, date, spend, clicks, "
                         "impressions) VALUES (%s, %s, %s, %s, 1, 10)",
                         (tenant, ad_id, day, spend))


def _cleanup(db, tenants: list[int], ad_id: str, camp_id: str) -> None:
    for table in ("meta_insights_performance", "meta_insights_performance_day",
                  "meta_insights_engagement", "meta_insights_engagement_day", "meta_insights"):
        for tenant in tenants:
            db.execute_query(f"DELETE FROM {table} WHERE artist_id = %s", (tenant,))
    db.execute_query("DELETE FROM meta_ads WHERE ad_id = %s", (ad_id,))
    db.execute_query("DELETE FROM meta_campaigns WHERE campaign_id = %s", (camp_id,))
    for tenant in tenants:
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (tenant,))


def _surfaces(db, tenant: int) -> dict:
    """Every Meta surface of this class, through its OWN query and frame builder."""
    from src.dashboard.views import meta_ads_overview as mao
    from src.dashboard.views.trigger_algo._tab_reglages import _Q_AXE

    df_perf = db.fetch_df(mao._perf_query(""), (tenant,))
    return {
        "chart": mao._campaign_frame(df_perf),
        "engagement": db.fetch_df(mao._engagement_query(""), (tenant,)),
        "summary": db.fetch_df(mao._summary_query(""), (tenant, tenant)),
        "axes": {axe: db.fetch_query(sql, (tenant,)) for axe, sql in _Q_AXE.items()},
    }


@requires_live_db()
@pytest.mark.xdist_group("meta-fanout")
def test_every_meta_surface_keeps_one_row_per_campaign_and_the_gold_total() -> None:
    db = _db()
    owner, sandbox = _tenant(db, "own"), _tenant(db, "sbx")
    ad_id, camp_id = f"fanout-ad-{uuid.uuid4().hex[:8]}", f"fanout-c-{uuid.uuid4().hex[:8]}"
    try:
        for tenant in (owner, sandbox):
            _seed_campaigns(db, tenant)
        _seed_ad(db, owner, sandbox, ad_id, camp_id)
        s = _surfaces(db, owner)

        chart, eng, summary = s["chart"], s["engagement"], s["summary"]
        assert len(chart) == 2 and chart["campaign_name"].is_unique, (
            f"the chart frame has {len(chart)} rows for 2 campaigns:\n{chart}")
        assert float(chart["spend"].sum()) == 70, (
            f"chart spend {chart['spend'].sum()} != gold 70 (130 = the lifetime row counted)")

        assert len(eng) == 2 and eng["campaign_name"].is_unique, (
            f"the engagement frame has {len(eng)} rows for 2 campaigns — a merge on "
            f"campaign_name would multiply the chart by as much:\n{eng}")
        assert float(eng["saves"].sum()) == 8, (
            f"Saves tile {eng['saves'].sum()} != 8 (14 = the lifetime row counted)")

        assert len(summary) == 2 and summary["campaign_name"].is_unique, summary
        assert float(summary["Dépenses"].sum()) == 70, (
            f"summary-table spend {summary['Dépenses'].sum()} != gold 70 — a day x day "
            "join multiplies every campaign by its number of engagement rows")
        saves = dict(zip(summary["campaign_name"], summary["Saves"]))
        assert float(saves["c1"]) == 6, f"summary Saves for c1: {saves['c1']} != 1+2+3"

        for axe, rows in s["axes"].items():
            total = sum(float(r[2] or 0) for r in rows)
            assert total == 7, (
                f"Réglages axis « {axe} » totals {total} EUR for the owner's 7 — 18 is "
                "the sandbox tenant's copy of the same ad_id added in")
    finally:
        _cleanup(db, [owner, sandbox], ad_id, camp_id)
        db.close()


# ── live, real data ───────────────────────────────────────────────────────

@requires_live_db()
def test_on_real_tenants_the_summary_and_the_axes_total_the_tenants_own_spend() -> None:
    from src.dashboard.views import meta_ads_overview as mao
    from src.dashboard.views.trigger_algo._tab_reglages import _Q_AXE

    db = _db()
    try:
        gold = dict(db.fetch_query("SELECT artist_id, SUM(spend) FROM v_meta_campaign_daily "
                                   "GROUP BY 1"))
        own = dict(db.fetch_query(
            "SELECT mi.artist_id, SUM(mi.spend) FROM meta_insights mi WHERE EXISTS "
            "(SELECT 1 FROM meta_ads ma WHERE ma.ad_id = mi.ad_id "
            "AND ma.artist_id = mi.artist_id) GROUP BY 1"))
        if not gold and not own:
            pytest.skip("no Meta spend on this database — nothing to reconcile")
        wrong = []
        for tenant, total in gold.items():
            got = db.fetch_df(mao._summary_query(""), (tenant, tenant))["Dépenses"].sum()
            if abs(float(got) - float(total)) > 1e-6:
                wrong.append(f"tenant {tenant}: summary {float(got):.2f} != gold {float(total):.2f}")
        for tenant, total in own.items():
            for axe, sql in _Q_AXE.items():
                got = sum(float(r[2] or 0) for r in db.fetch_query(sql, (tenant,)))
                if abs(got - float(total)) > 1e-6:
                    wrong.append(f"tenant {tenant}: Réglages « {axe} » {got:.2f} != "
                                 f"own spend {float(total):.2f}")
        assert not wrong, "\n".join(wrong)
    finally:
        db.close()


# ── static: every merge declares its cardinality ──────────────────────────

_SURFACES = ("src/dashboard", "src/api")

# Unvalidated merges that predate the guard, COUNTED on 2026-09-26 (10 in 7 files) but
# NOT read one by one for the uniqueness of their right key — they are unexamined risks,
# not known defects. The ceiling only goes down: add `validate=` to one, lower its number.
_GRANDFATHERED: dict[str, int] = {
    "src/dashboard/utils/kpi_helpers.py": 1,
    "src/dashboard/views/airflow_kpi.py": 1,
    "src/dashboard/views/meta_x_spotify.py": 2,
    "src/dashboard/views/soundcloud.py": 1,
    "src/dashboard/views/spotify_s4a_combined.py": 2,
    "src/dashboard/views/trigger_algo/_tab_algos.py": 1,
}


def unvalidated_merges(source: str) -> list[int]:
    """Lines of `pd.merge(...)` / `<frame>.merge(...)` calls without `validate=`. Pure."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "merge"
                and not any(k.arg == "validate" for k in node.keywords)):
            out.append(node.lineno)
    return out


def _unvalidated_by_file() -> dict[str, list[int]]:
    out = {}
    for root in _SURFACES:
        for path in sorted((_ROOT / root).rglob("*.py")):
            lines = unvalidated_merges(path.read_text(encoding="utf-8"))
            if lines:
                out[path.relative_to(_ROOT).as_posix()] = lines
    return out


def test_no_new_merge_without_a_declared_cardinality() -> None:
    grown = [f"{f}:{lines} — {len(lines)} unvalidated, ceiling {_GRANDFATHERED.get(f, 0)}"
             for f, lines in _unvalidated_by_file().items()
             if len(lines) > _GRANDFATHERED.get(f, 0)]
    assert not grown, (
        "A merge without `validate=` multiplies the left frame silently when the right "
        "key is not unique — 21 campaigns became 252 rows in meta_ads_overview. Pass "
        "`validate='one_to_one'` / `'many_to_one'`: pandas then raises MergeError at run "
        "time instead of drawing 12 copies of one campaign.\n" + "\n".join(grown))


def test_the_merge_ceiling_is_not_slack() -> None:
    found = {f: len(v) for f, v in _unvalidated_by_file().items()}
    slack = {f: (c, found.get(f, 0)) for f, c in _GRANDFATHERED.items() if c > found.get(f, 0)}
    assert not slack, f"lower these ceilings to the measured count: {slack}"


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the pre-fix merge is named; a validated one, and a non-pandas
    `merge` attribute in a docstring, are not."""
    bad = ("df = pd.merge(df_chart, df_eng[['campaign_name', 'page_interactions']],\n"
           "              on='campaign_name', how='left')\n")
    assert unvalidated_merges(bad) == [1]
    assert unvalidated_merges("m = a.merge(b, on='k', how='left')\n") == [1]
    good = "df = pd.merge(a, b, on='k', how='left', validate='many_to_one')\n"
    assert unvalidated_merges(good) == []
    assert unvalidated_merges('"""pd.merge(a, b)"""\n') == []
