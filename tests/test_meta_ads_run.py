"""Characterization tests — MetaAdsApiCollector.run() end-to-end with stub SDK.

Goal: pin the CURRENT observable behaviour of the orchestrator (run /
_fetch_all_insights / persistence) using the injectable __init__ seam
(db=, ad_account=, creds=) plus the FakeAdAccount stub. No real Meta token,
no live Postgres. These tests must stay GREEN against the un-refactored
collector so an upcoming mixin split can be proven behaviour-preserving.

Pinned behaviours (assertion targets):
  * insights_only=True → config tables NOT upserted; the four insight API
    levels still queried; perf/eng/day/ad insight tables populated.
  * full_history=True → campaigns/adsets/ads/creatives upserted to their
    tables; _prune_renamed_campaigns runs (DELETE on campaign-grain tables);
    insight tables populated; row counts match the fixture.
  * smart-incremental (full_history=False) → since-date passed to get_insights
    equals MAX(day_date)-3 days read from the DB.
  * goal resolution → an OFFSITE_CONVERSIONS adset yields results+CPR; a
    LINK_CLICKS adset yields results with CPR suppressed (None) in the
    upserted perf rows.
  * per-table / per-chunk persistence → _persist_insights upserts each
    monthly chunk and each breakdown table separately.
"""
from datetime import date, timedelta

import pytest

from src.collectors.meta_ads_api_collector import MetaAdsApiCollector
from tests.fakes.meta_sdk import FakeAdAccount


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeDB:
    """Records upserts/deletes; routes fetch_query by a substring match.

    Extends the recording _FakeDB pattern from test_meta_ads_collector with a
    routable fetch_query so the smart-incremental MAX(day_date) lookup and the
    insights_only campaign reload can be characterized.
    """

    def __init__(self, fetch_routes=None):
        self.upserts = []   # [(table, rows)]
        self.deletes = []   # [(query, params)]
        self.fetches = []   # [(query, params)]
        self._routes = fetch_routes or {}

    def upsert_many(self, table, data, conflict_columns=None, update_columns=None):
        self.upserts.append((table, [dict(r) for r in data]))
        return len(data)

    def execute_query(self, query, params=None):
        self.deletes.append((query, params))

    def fetch_query(self, query, params=None):
        self.fetches.append((query, params))
        for substr, result in self._routes.items():
            if substr in query:
                return result
        return []

    # convenience accessors -----------------------------------------------------

    def rows_for(self, table):
        out = []
        for t, rows in self.upserts:
            if t == table:
                out.extend(rows)
        return out

    def tables_upserted(self):
        return {t for t, _ in self.upserts}


# ---------------------------------------------------------------------------
# Fixture: 2 campaigns, 2 adsets, 2 ads, insights across two months
# ---------------------------------------------------------------------------

# Two recent months so full_history chunks to ~2-3 monthly buckets but the
# fixture stays small and deterministic regardless of run date.
_TODAY = date.today()
# A recent day inside the current monthly chunk (always <= today, after day-1).
_M_THIS = max(_TODAY - timedelta(days=2), _TODAY.replace(day=1)).isoformat()
# A day in the previous month (inside the earliest chunk).
_M_PREV = (_TODAY.replace(day=1) - timedelta(days=15)).isoformat()

# C1 → OFFSITE_CONVERSIONS adset (conversion goal → CPR computed)
# C2 → LINK_CLICKS adset (traffic goal → CPR suppressed)
_CAMPAIGNS = [
    {'id': 'C1', 'name': 'Camp One', 'status': 'ACTIVE', 'objective': 'OUTCOME_SALES',
     'daily_budget': '1000', 'lifetime_budget': None,
     'start_time': _M_PREV + 'T00:00:00+0000', 'stop_time': None,
     'created_time': _M_PREV, 'updated_time': _M_THIS},
    {'id': 'C2', 'name': 'Camp Two', 'status': 'PAUSED', 'objective': 'OUTCOME_TRAFFIC',
     'daily_budget': None, 'lifetime_budget': '5000',
     'start_time': _M_PREV + 'T00:00:00+0000', 'stop_time': None,
     'created_time': _M_PREV, 'updated_time': _M_THIS},
]

_ADSETS = [
    {'id': 'AS1', 'name': 'AdSet One', 'campaign_id': 'C1', 'status': 'ACTIVE',
     'optimization_goal': 'OFFSITE_CONVERSIONS', 'billing_event': 'IMPRESSIONS',
     'daily_budget': '1000', 'lifetime_budget': None,
     'start_time': _M_PREV, 'end_time': None,
     'targeting': {'geo_locations': {'countries': ['FR', 'BE']},
                   'genders': [1], 'age_min': 18, 'age_max': 45,
                   'publisher_platforms': ['facebook', 'instagram']}},
    {'id': 'AS2', 'name': 'AdSet Two', 'campaign_id': 'C2', 'status': 'PAUSED',
     'optimization_goal': 'LINK_CLICKS', 'billing_event': 'LINK_CLICKS',
     'daily_budget': None, 'lifetime_budget': '5000',
     'start_time': _M_PREV, 'end_time': None,
     'targeting': {'geo_locations': {'countries': ['US']}}},
]

_ADS = [
    {'id': 'AD1', 'name': 'Ad One', 'adset_id': 'AS1', 'campaign_id': 'C1',
     'status': 'ACTIVE', 'creative': {'id': 'CR1'},
     'created_time': _M_PREV, 'updated_time': _M_THIS},
    {'id': 'AD2', 'name': 'Ad Two', 'adset_id': 'AS2', 'campaign_id': 'C2',
     'status': 'PAUSED', 'creative': {'id': 'CR2'},
     'created_time': _M_PREV, 'updated_time': _M_THIS},
]


def _campaign_daily_insights():
    """Campaign-level daily rows (level='campaign', no breakdown), 2 months."""
    return [
        {'campaign_name': 'Camp One', 'date_start': _M_PREV,
         'spend': '20.00', 'impressions': 1000, 'reach': 800, 'frequency': '1.2',
         'cpm': '20.0', 'cpc': '0.4', 'ctr': '5.0', 'inline_link_clicks': 50,
         'actions': [{'action_type': 'offsite_conversion.custom.1', 'value': '10'}]},
        {'campaign_name': 'Camp One', 'date_start': _M_THIS,
         'spend': '30.00', 'impressions': 1500, 'reach': 1200, 'frequency': '1.25',
         'cpm': '20.0', 'cpc': '0.5', 'ctr': '4.0', 'inline_link_clicks': 60,
         'actions': [{'action_type': 'offsite_conversion.custom.1', 'value': '15'}]},
        {'campaign_name': 'Camp Two', 'date_start': _M_THIS,
         'spend': '12.00', 'impressions': 600, 'reach': 500, 'frequency': '1.2',
         'cpm': '20.0', 'cpc': '0.3', 'ctr': '6.0', 'inline_link_clicks': 40,
         'actions': [{'action_type': 'link_click', 'value': '40'}]},
    ]


def _ad_daily_insights():
    """Ad-level daily rows (level='ad', no breakdown)."""
    return [
        {'ad_id': 'AD1', 'date_start': _M_THIS, 'spend': '30.00', 'impressions': 1500,
         'clicks': 70, 'reach': 1200, 'frequency': '1.25', 'cpc': '0.5', 'cpm': '20.0',
         'ctr': '4.0', 'actions': [{'action_type': 'offsite_conversion.custom.1',
                                    'value': '15'}]},
        {'ad_id': 'AD2', 'date_start': _M_THIS, 'spend': '12.00', 'impressions': 600,
         'clicks': 40, 'reach': 500, 'frequency': '1.2', 'cpc': '0.3', 'cpm': '20.0',
         'ctr': '6.0', 'actions': [{'action_type': 'link_click', 'value': '40'}]},
    ]


def _age_breakdown():
    return [
        {'campaign_name': 'Camp One', 'age': '25-34', 'date_start': _M_THIS,
         'spend': '50.00', 'impressions': 2500, 'reach': 2000, 'frequency': '1.25',
         'cpm': '20.0', 'cpc': '0.45', 'ctr': '4.5', 'inline_link_clicks': 110,
         'actions': [{'action_type': 'offsite_conversion.custom.1', 'value': '25'}]},
    ]


def _country_breakdown():
    return [
        {'campaign_name': 'Camp One', 'country': 'FR', 'date_start': _M_THIS,
         'spend': '50.00', 'impressions': 2500, 'reach': 2000, 'frequency': '1.25',
         'cpm': '20.0', 'cpc': '0.45', 'ctr': '4.5', 'inline_link_clicks': 110,
         'actions': [{'action_type': 'offsite_conversion.custom.1', 'value': '25'}]},
    ]


def _placement_breakdown():
    return [
        {'campaign_name': 'Camp One', 'publisher_platform': 'facebook',
         'platform_position': 'feed', 'date_start': _M_THIS,
         'spend': '50.00', 'impressions': 2500, 'reach': 2000, 'frequency': '1.25',
         'cpm': '20.0', 'cpc': '0.45', 'ctr': '4.5', 'inline_link_clicks': 110,
         'actions': [{'action_type': 'offsite_conversion.custom.1', 'value': '25'}]},
    ]


def _ad_country_breakdown():
    return [
        {'ad_id': 'AD1', 'country': 'FR', 'date_start': _M_THIS,
         'spend': '30.00', 'impressions': 1500, 'reach': 1200, 'frequency': '1.25',
         'cpm': '20.0', 'cpc': '0.5', 'ctr': '4.0', 'inline_link_clicks': 60,
         'actions': [{'action_type': 'offsite_conversion.custom.1', 'value': '15'}]},
        # An unknown ad_id (not in goal_by_ad) must be dropped by the FK guard.
        {'ad_id': 'GHOST', 'country': 'US', 'date_start': _M_THIS,
         'spend': '99.00', 'impressions': 99, 'reach': 99, 'frequency': '1.0',
         'cpm': '1.0', 'cpc': '1.0', 'ctr': '1.0', 'inline_link_clicks': 1,
         'actions': []},
    ]


def _insights_table():
    """Full routing table for get_insights, keyed (level, breakdown-tuple)."""
    placement_bd = ('publisher_platform', 'platform_position')
    return {
        ('campaign', None): _campaign_daily_insights(),
        ('ad', None): _ad_daily_insights(),
        ('campaign', ('age',)): _age_breakdown(),
        ('campaign', ('country',)): _country_breakdown(),
        ('campaign', placement_bd): _placement_breakdown(),
        ('ad', ('country',)): _ad_country_breakdown(),
        ('ad', ('age',)): [],
        ('ad', placement_bd): [],
        ('adset', ('country',)): [],
        ('adset', ('age',)): [],
        ('adset', placement_bd): [],
    }


def _make_account():
    return FakeAdAccount(campaigns=_CAMPAIGNS, adsets=_ADSETS, ads=_ADS,
                         insights=_insights_table())


@pytest.fixture
def _patch_creatives(monkeypatch):
    """Patch AdCreative so _fetch_creatives returns deterministic content.

    _fetch_creatives does a module-level `from ... import AdCreative` then
    `AdCreative(cid).api_get(fields=)`. We replace the class with a stub that
    yields a title/body/CTA per creative id.
    """
    class _Field:
        id = 'id'
        title = 'title'
        body = 'body'
        call_to_action_type = 'call_to_action_type'
        thumbnail_url = 'thumbnail_url'

    class _FakeCreative:
        Field = _Field

        def __init__(self, cid):
            self._cid = cid

        def api_get(self, fields=None):
            from tests.fakes.meta_sdk import FakeNode
            return FakeNode({'id': self._cid, 'title': f'Title {self._cid}',
                             'body': f'Body {self._cid}',
                             'call_to_action_type': 'LEARN_MORE'})

    monkeypatch.setattr(
        'facebook_business.adobjects.adcreative.AdCreative', _FakeCreative,
    )
    return _FakeCreative


# ---------------------------------------------------------------------------
# full_history=True — end-to-end config + insight persistence
# ---------------------------------------------------------------------------

class TestRunFullHistory:

    def _run(self, _patch_creatives, fetch_creatives=True):
        db = FakeDB()
        acct = _make_account()
        c = MetaAdsApiCollector(1, db=db, ad_account=acct, creds={})
        total = c.run(full_history=True, fetch_creatives=fetch_creatives)
        return db, acct, total

    def test_config_tables_upserted(self, _patch_creatives):
        db, _acct, _ = self._run(_patch_creatives)
        tables = db.tables_upserted()
        assert {'meta_campaigns', 'meta_adsets', 'meta_ads'} <= tables

    def test_campaign_rows_match_fixture(self, _patch_creatives):
        db, _acct, _ = self._run(_patch_creatives)
        camps = db.rows_for('meta_campaigns')
        assert {r['campaign_id'] for r in camps} == {'C1', 'C2'}
        c1 = next(r for r in camps if r['campaign_id'] == 'C1')
        assert c1['campaign_name'] == 'Camp One'
        assert c1['daily_budget'] == 10.0  # 1000 cents / 100

    def test_adsets_and_ads_match_fixture(self, _patch_creatives):
        db, _acct, _ = self._run(_patch_creatives)
        assert {r['adset_id'] for r in db.rows_for('meta_adsets')} == {'AS1', 'AS2'}
        assert {r['ad_id'] for r in db.rows_for('meta_ads')} == {'AD1', 'AD2'}

    def test_creatives_enrich_meta_ads_via_execute_query(self, _patch_creatives):
        db, _acct, _ = self._run(_patch_creatives)
        creative_updates = [q for q, _ in db.deletes if 'UPDATE meta_ads' in q]
        assert len(creative_updates) == 2  # one UPDATE per ad/creative

    def test_fetch_creatives_false_skips_creative_updates(self, _patch_creatives):
        db, _acct, _ = self._run(_patch_creatives, fetch_creatives=False)
        creative_updates = [q for q, _ in db.deletes if 'UPDATE meta_ads' in q]
        assert creative_updates == []

    def test_prune_renamed_campaigns_runs(self, _patch_creatives):
        db, _acct, _ = self._run(_patch_creatives)
        prunes = [(q, p) for q, p in db.deletes if 'campaign_name <> ALL' in q]
        from src.collectors.meta_ads_api_collector import _CAMPAIGN_GRAIN_TABLES
        assert len(prunes) == len(_CAMPAIGN_GRAIN_TABLES)
        for _q, params in prunes:
            assert params == (1, ['Camp One', 'Camp Two'])  # sorted current names

    def test_insight_tables_populated(self, _patch_creatives):
        db, _acct, _ = self._run(_patch_creatives)
        tables = db.tables_upserted()
        for t in ('meta_insights_performance', 'meta_insights_performance_day',
                  'meta_insights_engagement', 'meta_insights', 'meta_insights_performance_age',
                  'meta_insights_performance_country', 'meta_insights_performance_placement'):
            assert t in tables, t

    def test_returned_total_equals_sum_of_insight_rows(self, _patch_creatives):
        db, _acct, total = self._run(_patch_creatives)
        # total counts every insight row across all returned tables (not config).
        assert total > 0
        # ad-level insights table got exactly the 2 fixture ad rows.
        assert len(db.rows_for('meta_insights')) == 2

    def test_unknown_ad_dropped_by_fk_guard(self, _patch_creatives):
        db, _acct, _ = self._run(_patch_creatives)
        ad_country = db.rows_for('meta_insights_performance_ad_country')
        assert {r['ad_id'] for r in ad_country} == {'AD1'}  # GHOST dropped


# ---------------------------------------------------------------------------
# Goal resolution reflected in upserted perf rows
# ---------------------------------------------------------------------------

class TestGoalResolution:

    def test_conversion_goal_yields_cpr_traffic_goal_suppresses_it(self, _patch_creatives):
        db = FakeDB()
        c = MetaAdsApiCollector(1, db=db, ad_account=_make_account(), creds={})
        c.run(full_history=True)
        perf = db.rows_for('meta_insights_performance')
        c1 = [r for r in perf if r['campaign_name'] == 'Camp One']
        c2 = [r for r in perf if r['campaign_name'] == 'Camp Two']
        # C1 adset goal = OFFSITE_CONVERSIONS → results from offsite_conversion.custom.
        assert all(r['results'] > 0 for r in c1)
        assert any(r['cpr'] is not None for r in c1)
        # C2 adset goal = LINK_CLICKS → results = link_click count, CPR suppressed.
        assert all(r['results'] == 40 for r in c2)
        assert all(r['cpr'] is None for r in c2)


# ---------------------------------------------------------------------------
# insights_only=True — config skipped, campaigns loaded from DB
# ---------------------------------------------------------------------------

class TestRunInsightsOnly:

    def _db(self):
        # insights_only reloads campaigns from DB, and _build_goal_maps reloads
        # adsets + ads from DB (since they are not passed).
        return FakeDB(fetch_routes={
            'FROM meta_campaigns': [
                ('C1', 'Camp One', _M_PREV, 'OUTCOME_SALES'),
                ('C2', 'Camp Two', _M_PREV, 'OUTCOME_TRAFFIC'),
            ],
            'FROM meta_adsets': [
                ('AS1', 'C1', 'OFFSITE_CONVERSIONS'),
                ('AS2', 'C2', 'LINK_CLICKS'),
            ],
            'FROM meta_ads': [('AD1', 'AS1'), ('AD2', 'AS2')],
        })

    def test_config_tables_not_upserted(self, _patch_creatives):
        db = self._db()
        c = MetaAdsApiCollector(1, db=db, ad_account=_make_account(), creds={})
        c.run(insights_only=True, full_history=True)
        tables = db.tables_upserted()
        assert 'meta_campaigns' not in tables
        assert 'meta_adsets' not in tables
        assert 'meta_ads' not in tables

    def test_no_config_edge_calls_made(self, _patch_creatives):
        db = self._db()
        acct = _make_account()
        c = MetaAdsApiCollector(1, db=db, ad_account=acct, creds={})
        c.run(insights_only=True, full_history=True)
        methods = {m for m, _f, _p in acct.calls}
        assert 'get_campaigns' not in methods
        assert 'get_ad_sets' not in methods
        assert 'get_ads' not in methods
        assert 'get_insights' in methods  # insight calls still happen

    def test_insight_tables_still_populated(self, _patch_creatives):
        db = self._db()
        c = MetaAdsApiCollector(1, db=db, ad_account=_make_account(), creds={})
        c.run(insights_only=True, full_history=True)
        tables = db.tables_upserted()
        assert 'meta_insights_performance_day' in tables
        assert 'meta_insights' in tables

    def test_no_prune_in_insights_only(self, _patch_creatives):
        db = self._db()
        c = MetaAdsApiCollector(1, db=db, ad_account=_make_account(), creds={})
        c.run(insights_only=True, full_history=True)
        prunes = [q for q, _ in db.deletes if 'campaign_name <> ALL' in q]
        assert prunes == []  # prune is config-path only


# ---------------------------------------------------------------------------
# Smart-incremental date window (full_history=False)
# ---------------------------------------------------------------------------

class TestSmartIncrementalWindow:

    def test_since_date_is_max_day_minus_3(self, _patch_creatives):
        last_day = _TODAY - timedelta(days=10)
        expected_since = (last_day - timedelta(days=3)).strftime('%Y-%m-%d')
        db = FakeDB(fetch_routes={'MAX(day_date)': [(last_day,)]})
        acct = _make_account()
        c = MetaAdsApiCollector(1, db=db, ad_account=acct, creds={})
        c.run(full_history=False)

        # The earliest monthly chunk's since-date must be the month-start of the
        # smart-incremental window; the chunk cursor starts at history_start.replace(day=1).
        first_chunk_since = min(
            p['time_range']['since'] for p in acct.insight_calls
            if p.get('time_range') and p.get('time_increment') == 1
            and p.get('level') == 'campaign'
        )
        month_start = (last_day - timedelta(days=3)).replace(day=1).strftime('%Y-%m-%d')
        assert first_chunk_since == month_start
        # And the MAX(day_date) query was actually issued.
        assert any('MAX(day_date)' in q for q, _ in db.fetches)
        # expected_since lies within the queried window (sanity on the -3d overlap).
        assert expected_since >= month_start


# ---------------------------------------------------------------------------
# Per-chunk / per-table persistence granularity
# ---------------------------------------------------------------------------

class TestPersistenceGranularity:

    def test_each_breakdown_table_upserted_separately(self, _patch_creatives):
        db = FakeDB()
        c = MetaAdsApiCollector(1, db=db, ad_account=_make_account(), creds={})
        c.run(full_history=True)
        # Age/country/placement perf breakdowns each produce their own upsert call.
        upsert_tables = [t for t, _ in db.upserts]
        for t in ('meta_insights_performance_age', 'meta_insights_performance_country',
                  'meta_insights_performance_placement'):
            assert upsert_tables.count(t) >= 1

    def test_day_chunk_perf_rows_have_day_date(self, _patch_creatives):
        db = FakeDB()
        c = MetaAdsApiCollector(1, db=db, ad_account=_make_account(), creds={})
        c.run(full_history=True)
        day_rows = db.rows_for('meta_insights_performance_day')
        assert day_rows  # at least one chunk persisted
        assert all('day_date' in r for r in day_rows)
        assert all('_date' not in r for r in day_rows)  # leak column trimmed at persist
