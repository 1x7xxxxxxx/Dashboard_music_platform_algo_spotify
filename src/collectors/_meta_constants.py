"""Meta Ads collector — shared module-level constants (leaf, imports no siblings).

Type: Sub
Uses: nothing
Depends on: nothing (leaf module to avoid circular imports)

Config constants not owned by a helper module, shared across the collector mixins.
"""

# Meta retains insights for 37 months; a time_range start beyond that returns API
# error #3018. We clamp the backfill floor to 36 months — one month inside the hard
# limit so a request never trips on time-of-day/timezone boundary rounding. Archived
# campaigns (now in scope via the broadened status filters) can carry very old or
# even epoch start_time values, which would otherwise push the backfill to 1970.
_META_INSIGHTS_RETENTION_MONTHS = 36

# effective_status allowlists per object level. A PAUSED *campaign* propagates
# CAMPAIGN_PAUSED to its ad sets and CAMPAIGN_PAUSED/ADSET_PAUSED to its ads — those
# values are NOT 'PAUSED', so a ['ACTIVE','PAUSED'] filter silently excludes every
# ad of a paused/archived campaign. The ad would then be absent from meta_ads, and
# its ad-level insights (which the API *does* return) get dropped by the ad_id FK
# guard in _fetch_ad_insights → campaign-level spend present, per-creative detail
# missing. Include the paused/archived states so historical ads are refreshed.
_CAMPAIGN_STATUSES = ['ACTIVE', 'PAUSED', 'ARCHIVED', 'IN_PROCESS', 'WITH_ISSUES']
_ADSET_STATUSES = ['ACTIVE', 'PAUSED', 'CAMPAIGN_PAUSED', 'ARCHIVED',
                   'IN_PROCESS', 'WITH_ISSUES']
_AD_STATUSES = ['ACTIVE', 'PAUSED', 'CAMPAIGN_PAUSED', 'ADSET_PAUSED', 'ARCHIVED',
                'IN_PROCESS', 'WITH_ISSUES']

# Campaign-grain insight tables key by campaign_name (not campaign_id), so a campaign
# RENAME orphans stale rows under the old name. Ad/adset-grain tables key by entity id
# and are immune. _prune_renamed_campaigns deletes rows whose campaign_name is no longer
# returned by the API; it is guarded against an empty fetch (never a mass delete).
_CAMPAIGN_GRAIN_TABLES = frozenset({
    'meta_insights_performance', 'meta_insights_performance_day',
    'meta_insights_performance_age', 'meta_insights_performance_country',
    'meta_insights_performance_placement',
    'meta_insights_engagement', 'meta_insights_engagement_day',
    'meta_insights_engagement_age', 'meta_insights_engagement_country',
    'meta_insights_engagement_placement',
})
