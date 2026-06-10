"""Meta Ads collector — insight fetch mixin (all 11 insight tables + goal maps).

Type: Sub
Uses: facebook_business SDK (lazy, in-method), _meta_list, parsers
Depends on: _meta_retry, _meta_parsers, _meta_constants (leaf modules)

Mixed into MetaAdsApiCollector; methods cut verbatim from the original god-module.
"""
import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from dateutil.relativedelta import relativedelta

from ._meta_constants import _META_INSIGHTS_RETENTION_MONTHS
from ._meta_parsers import _extract_eng, _extract_perf, _is_conversion_goal, _results_for_goal
from ._meta_retry import _meta_list

logger = logging.getLogger(__name__)


class _MetaInsightFetchMixin:
    """Insight-fetch methods for MetaAdsApiCollector."""

    def _fetch_all_insights(self, campaigns: list, adsets: list = None,
                            ads: list = None, full_history: bool = False,
                            persist_cb=None) -> dict:
        """Return {table_name: [rows]} for all 11 insight tables.

        Per time chunk: campaign daily/global + ad-level (meta_insights). Plus 3 aggregate
        breakdown calls (age/country/placement). The result action for each row is resolved
        from the ad set optimization goal (campaign-dominant goal for campaign-level rows,
        exact per-ad goal for ad-level rows).
        """
        today = date.today()

        # Resolve optimization goals: dominant per campaign, exact per ad/adset.
        goal_by_campaign, goal_by_ad, goal_by_adset = self._build_goal_maps(
            campaigns, adsets or [], ads or [],
        )

        def _earliest_campaign_start() -> date:
            """Return the earliest campaign start_time, fallback to 1 year ago."""
            starts = []
            for c in campaigns:
                s = c.get('start_time')
                if s:
                    try:
                        starts.append(datetime.fromisoformat(s[:10]).date())
                    except Exception:
                        pass
            return min(starts) if starts else today - timedelta(days=365)

        if full_history:
            history_start = _earliest_campaign_start()
        else:
            # Smart incremental: start from last known data point (minus 3-day overlap
            # to catch late-arriving Meta data), falling back to full history on first run.
            row = self.db.fetch_query(
                "SELECT MAX(day_date) FROM meta_insights_performance_day WHERE artist_id = %s",
                (self.artist_id,),
            )
            last_day = row[0][0] if row and row[0][0] else None
            if last_day is not None:
                history_start = last_day - timedelta(days=3)
            else:
                # No data yet — backfill from first campaign
                history_start = _earliest_campaign_start()
                logger.info(
                    f"No existing insight data for artist_id={self.artist_id} — "
                    f"backfilling from {history_start}"
                )

        # Clamp to Meta's insights retention window (API error #3018 otherwise).
        retention_floor = today - relativedelta(months=_META_INSIGHTS_RETENTION_MONTHS)
        if history_start < retention_floor:
            logger.info(
                f"Clamping backfill start {history_start} → {retention_floor} "
                f"(Meta {_META_INSIGHTS_RETENTION_MONTHS}-month insights retention)"
            )
            history_start = retention_floor

        # Aggregate tables (age/country/placement) always use full range in one shot
        aggregate_start = history_start

        # Daily tables: chunked by month to avoid API timeouts
        chunks = []
        cursor = history_start.replace(day=1)
        while cursor <= today:
            chunk_end = min((cursor + relativedelta(months=1)) - timedelta(days=1), today)
            chunks.append((cursor.strftime('%Y-%m-%d'), chunk_end.strftime('%Y-%m-%d')))
            cursor += relativedelta(months=1)

        # Collect all results
        result = {
            'meta_insights_performance':           [],
            'meta_insights_performance_day':       [],
            'meta_insights_engagement':            [],
            'meta_insights_engagement_day':        [],
            'meta_insights_performance_age':       [],
            'meta_insights_engagement_age':        [],
            'meta_insights_performance_country':   [],
            'meta_insights_engagement_country':    [],
            'meta_insights_performance_placement': [],
            'meta_insights_engagement_placement':  [],
            'meta_insights':                       [],  # ad-level (Créatives view)
            # Ad/adset-level breakdowns (multi-grain Breakdowns view) — perf + engagement.
            'meta_insights_performance_ad_country':      [],
            'meta_insights_engagement_ad_country':       [],
            'meta_insights_performance_ad_placement':    [],
            'meta_insights_engagement_ad_placement':     [],
            'meta_insights_performance_ad_age':          [],
            'meta_insights_engagement_ad_age':           [],
            'meta_insights_performance_adset_country':   [],
            'meta_insights_engagement_adset_country':    [],
            'meta_insights_performance_adset_placement': [],
            'meta_insights_engagement_adset_placement':  [],
            'meta_insights_performance_adset_age':       [],
            'meta_insights_engagement_adset_age':        [],
        }

        # persist() upserts a stage's tables as soon as they are fetched (per-chunk
        # durability); a no-op when no callback is supplied (keeps the fetch pure for tests).
        def persist(partial):
            if persist_cb:
                persist_cb(partial)

        # 1. Global / daily (monthly chunks) + ad-level — persisted per chunk so a late
        #    throttle keeps every month already fetched.
        logger.info(f"  Fetching daily insights ({len(chunks)} monthly chunks)...")
        for since, until in chunks:
            chunk = {
                'meta_insights':                 [],
                'meta_insights_performance':     [],
                'meta_insights_performance_day': [],
                'meta_insights_engagement':      [],
                'meta_insights_engagement_day':  [],
            }
            chunk['meta_insights'].extend(
                self._fetch_ad_insights(since, until, goal_by_ad)
            )
            p, e = self._call_insights(since, until, breakdown=None, time_increment=1,
                                       goal_by_campaign=goal_by_campaign)
            for row in p:
                row['date_start'] = row.pop('_date')
                chunk['meta_insights_performance'].append(row)
                chunk['meta_insights_performance_day'].append({
                    'artist_id':          row['artist_id'],
                    'campaign_name':      row['campaign_name'],
                    'day_date':           row['date_start'],
                    'spend':              row['spend'],
                    'impressions':        row['impressions'],
                    'reach':              row['reach'],
                    'results':            row['results'],
                    'custom_conversions': row['custom_conversions'],
                    'cpr':                row['cpr'],
                    'collected_at':       datetime.now(timezone.utc),
                })
            for row in e:
                row['date_start'] = row.pop('_date')
                chunk['meta_insights_engagement'].append(row)
                day_row = {k: v for k, v in row.items() if k != 'date_start'}
                day_row['day_date'] = row['date_start']
                chunk['meta_insights_engagement_day'].append(day_row)
            persist(chunk)
            for k, v in chunk.items():
                result[k].extend(v)

        # 2. Age breakdown (full range, single call)
        logger.info("  Fetching age breakdown...")
        since = aggregate_start.strftime('%Y-%m-%d')
        until = today.strftime('%Y-%m-%d')
        p, e = self._call_insights(since, until, breakdown=['age'],
                                   goal_by_campaign=goal_by_campaign)
        for row in p:
            row.pop('_date', None)
            result['meta_insights_performance_age'].append(row)
        for row in e:
            row.pop('_date', None)
            result['meta_insights_engagement_age'].append(row)
        persist({'meta_insights_performance_age': result['meta_insights_performance_age'],
                 'meta_insights_engagement_age': result['meta_insights_engagement_age']})

        # 3. Country breakdown
        logger.info("  Fetching country breakdown...")
        p, e = self._call_insights(since, until, breakdown=['country'],
                                   goal_by_campaign=goal_by_campaign)
        for row in p:
            row.pop('_date', None)
            result['meta_insights_performance_country'].append(row)
        for row in e:
            row.pop('_date', None)
            result['meta_insights_engagement_country'].append(row)
        persist({'meta_insights_performance_country': result['meta_insights_performance_country'],
                 'meta_insights_engagement_country': result['meta_insights_engagement_country']})

        # 4. Placement breakdown
        logger.info("  Fetching placement breakdown...")
        p, e = self._call_insights(
            since, until,
            breakdown=['publisher_platform', 'platform_position'],
            goal_by_campaign=goal_by_campaign,
        )
        for row in p:
            row.pop('_date', None)
            result['meta_insights_performance_placement'].append(row)
        for row in e:
            row.pop('_date', None)
            result['meta_insights_engagement_placement'].append(row)
        persist({'meta_insights_performance_placement': result['meta_insights_performance_placement'],
                 'meta_insights_engagement_placement': result['meta_insights_engagement_placement']})

        # 5. Ad-level & adset-level breakdowns (full range, one call per dim×level —
        #    each call yields BOTH perf and engagement rows). Powers the Breakdowns view.
        _bd_levels = (('ad', 'ad_id', goal_by_ad), ('adset', 'adset_id', goal_by_adset))
        _bd_dims = (
            (['country'], 'country'),
            (['publisher_platform', 'platform_position'], 'placement'),
            (['age'], 'age'),
        )
        for level, id_field, goal_map in _bd_levels:
            for breakdown, suffix in _bd_dims:
                logger.info(f"  Fetching {level} {suffix} breakdown...")
                p, e = self._fetch_breakdown(since, until, level, id_field, breakdown, goal_map)
                pt = f'meta_insights_performance_{level}_{suffix}'
                et = f'meta_insights_engagement_{level}_{suffix}'
                result[pt] = p
                result[et] = e
                persist({pt: p, et: e})

        for tbl, rows in result.items():
            logger.info(f"    {tbl}: {len(rows)} rows")
        return result

    def _call_insights(
        self,
        since: str,
        until: str,
        breakdown: list = None,
        time_increment: int = None,
        goal_by_campaign: dict = None,
    ) -> tuple:
        """Single campaign-level API insights call. Returns (perf_rows, eng_rows)."""
        try:
            fields = [
                'campaign_name', 'date_start', 'impressions', 'reach',
                'frequency', 'spend', 'cpm', 'cpc', 'ctr',
                'actions', 'cost_per_action_type', 'inline_link_clicks',
            ]
            params = {
                'level': 'campaign',
                'time_range': {'since': since, 'until': until},
                'limit': 5000,
            }
            if breakdown:
                params['breakdowns'] = breakdown
            if time_increment:
                params['time_increment'] = time_increment

            perf_rows, eng_rows = [], []
            for insight in _meta_list(self.ad_account.get_insights, fields=fields, params=params):
                goal = (goal_by_campaign or {}).get(insight.get('campaign_name'))
                base_perf = _extract_perf(insight, self.artist_id, goal)
                base_eng = _extract_eng(insight, self.artist_id)

                # Attach dimension columns
                base_perf['_date'] = insight.get('date_start')
                base_eng['_date'] = insight.get('date_start')

                if breakdown and 'age' in breakdown:
                    base_perf['age_range'] = insight.get('age', 'Unknown')
                    base_eng['age_range'] = insight.get('age', 'Unknown')
                if breakdown and 'country' in breakdown:
                    base_perf['country'] = insight.get('country', 'Unknown')
                    base_eng['country'] = insight.get('country', 'Unknown')
                if breakdown and 'publisher_platform' in breakdown:
                    base_perf['platform'] = insight.get('publisher_platform', 'Unknown')
                    base_perf['placement'] = insight.get('platform_position', 'Unknown')
                    base_eng['platform'] = insight.get('publisher_platform', 'Unknown')
                    base_eng['placement'] = insight.get('platform_position', 'Unknown')

                perf_rows.append(base_perf)
                eng_rows.append(base_eng)

            return perf_rows, eng_rows
        except Exception:
            logger.exception(f"_call_insights failed (since={since} until={until} breakdown={breakdown})")
            raise

    def _fetch_breakdown(self, since: str, until: str, level: str, id_field: str,
                         breakdown: list, goal_by_entity: dict) -> tuple:
        """Ad-level OR adset-level breakdown (country/placement/age). Returns (perf, eng).

        Single full-range aggregate call (like the campaign breakdowns). Keyed by
        ad_id/adset_id; only entities already in meta_ads/meta_adsets (present in
        goal_by_entity) are kept, to honour the FK. Results/CPR use the entity's exact
        optimization goal. The junk `campaign_name` from _extract_* is trimmed at upsert.
        """
        try:
            fields = [
                id_field, 'date_start', 'impressions', 'reach', 'spend', 'frequency',
                'cpm', 'cpc', 'ctr', 'actions', 'cost_per_action_type', 'inline_link_clicks',
            ]
            params = {
                'level': level,
                'time_range': {'since': since, 'until': until},
                'breakdowns': breakdown,
                'limit': 5000,
            }
            perf_rows, eng_rows = [], []
            for insight in _meta_list(self.ad_account.get_insights, fields=fields, params=params):
                eid = insight.get(id_field)
                if not eid or eid not in goal_by_entity:
                    continue  # unknown entity → would violate the ad_id/adset_id FK
                goal = goal_by_entity.get(eid)
                base_perf = _extract_perf(insight, self.artist_id, goal)
                base_eng = _extract_eng(insight, self.artist_id)
                base_perf[id_field] = eid
                base_eng[id_field] = eid

                if 'age' in breakdown:
                    base_perf['age_range'] = insight.get('age', 'Unknown')
                    base_eng['age_range'] = insight.get('age', 'Unknown')
                if 'country' in breakdown:
                    base_perf['country'] = insight.get('country', 'Unknown')
                    base_eng['country'] = insight.get('country', 'Unknown')
                if 'publisher_platform' in breakdown:
                    base_perf['platform'] = insight.get('publisher_platform', 'Unknown')
                    base_perf['placement'] = insight.get('platform_position', 'Unknown')
                    base_eng['platform'] = insight.get('publisher_platform', 'Unknown')
                    base_eng['placement'] = insight.get('platform_position', 'Unknown')

                perf_rows.append(base_perf)
                eng_rows.append(base_eng)
            return perf_rows, eng_rows
        except Exception:
            logger.exception(
                f"_fetch_breakdown failed (level={level} breakdown={breakdown} "
                f"since={since} until={until})"
            )
            raise

    # ── Goal resolution + ad-level insights ────────────────────────────────────

    def _build_goal_maps(self, campaigns: list, adsets: list, ads: list) -> tuple:
        """Return (goal_by_campaign, goal_by_ad, goal_by_adset).

        goal_by_campaign uses the DOMINANT optimization_goal among a campaign's ad sets
        (campaign-level insights cannot be split per ad set). goal_by_ad and goal_by_adset
        are exact. Falls back to the DB when adsets/ads are not provided (insights_only).
        """
        if not adsets:
            rows = self.db.fetch_query(
                "SELECT adset_id, campaign_id, optimization_goal "
                "FROM meta_adsets WHERE artist_id = %s",
                (self.artist_id,),
            )
            adsets = [{'adset_id': r[0], 'campaign_id': r[1], 'optimization_goal': r[2]}
                      for r in (rows or [])]
        if not ads:
            rows = self.db.fetch_query(
                "SELECT ad_id, adset_id FROM meta_ads WHERE artist_id = %s",
                (self.artist_id,),
            )
            ads = [{'ad_id': r[0], 'adset_id': r[1]} for r in (rows or [])]

        cid_to_name = {c['campaign_id']: c['campaign_name'] for c in campaigns}
        goal_by_adset = {a['adset_id']: a.get('optimization_goal') for a in adsets}

        counter = defaultdict(Counter)
        for a in adsets:
            goal = a.get('optimization_goal')
            cname = cid_to_name.get(a.get('campaign_id'))
            if goal and cname:
                counter[cname][goal] += 1
        goal_by_campaign = {cn: c.most_common(1)[0][0] for cn, c in counter.items()}

        goal_by_ad = {ad['ad_id']: goal_by_adset.get(ad['adset_id']) for ad in ads}
        return goal_by_campaign, goal_by_ad, goal_by_adset

    def _fetch_ad_insights(self, since: str, until: str, goal_by_ad: dict) -> list:
        """Ad-level daily insights → rows for meta_insights (powers the Créatives view).

        `conversions` = the ad set goal's native result (via _results_for_goal); only ads
        already known in meta_ads (present in goal_by_ad) are kept, to honour the ad_id FK.
        """
        try:
            fields = [
                'ad_id', 'date_start', 'impressions', 'clicks', 'spend', 'reach',
                'frequency', 'cpc', 'cpm', 'ctr', 'actions',
            ]
            params = {
                'level': 'ad',
                'time_range': {'since': since, 'until': until},
                'time_increment': 1,
                'limit': 5000,
            }
            rows = []
            for insight in _meta_list(self.ad_account.get_insights, fields=fields, params=params):
                ad_id = insight.get('ad_id')
                if not ad_id or ad_id not in goal_by_ad:
                    continue  # unknown ad → would violate meta_insights.ad_id FK
                actions = {}
                for action in (insight.get('actions') or []):
                    atype = action['action_type']
                    actions[atype] = actions.get(atype, 0) + int(float(action['value']))

                goal = goal_by_ad.get(ad_id)
                conversions = _results_for_goal(actions, goal)
                spend = float(insight.get('spend') or 0)
                is_conversion = _is_conversion_goal(goal)
                rows.append({
                    'artist_id':           self.artist_id,
                    'ad_id':               ad_id,
                    'date':                insight.get('date_start'),
                    'impressions':         int(insight.get('impressions') or 0),
                    'clicks':              int(insight.get('clicks') or 0),
                    'spend':               spend,
                    'reach':               int(insight.get('reach') or 0),
                    'frequency':           float(insight.get('frequency') or 0),
                    'cpc':                 float(insight.get('cpc') or 0),
                    'cpm':                 float(insight.get('cpm') or 0),
                    'ctr':                 float(insight.get('ctr') or 0),
                    'conversions':         conversions,
                    'cost_per_conversion': (round(spend / conversions, 4)
                                            if (is_conversion and conversions > 0) else 0),
                })
            return rows
        except Exception:
            logger.exception(f"_fetch_ad_insights failed (since={since} until={until})")
            raise
