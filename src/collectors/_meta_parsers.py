"""Meta Ads collector — pure insight parsers (leaf, imports no siblings).

Type: Sub
Uses: nothing
Depends on: nothing (leaf module to avoid circular imports)

Pure functions, unit-tested: map optimization goals to result actions, extract
performance + engagement dicts from a single insight object.
"""

from typing import Optional

# "Results" = Meta's native result, which keys off the AD SET's optimization_goal
# (mirrors the "Results" column in Ads Manager — Meta counts the optimization event).
# Each goal maps to the action_type that counts as its result. The special sentinel
# 'offsite_conversion' resolves to ONE action_type family (see `_offsite_results`):
# the 'offsite_conversion.custom*' family when present, else the other offsite
# families. Never their union — Meta reports one outbound event under several
# offsite_conversion.* names, and the union counted it twice (2026-09-26). Matches are
# PREFIX matches because Meta appends the conversion id to the action_type
# ('offsite_conversion.custom.1234567890') — an exact match silently returns 0.
# None means the goal has no action-based result (reach/impressions/awareness).
_OFFSITE_PREFIX = 'offsite_conversion'
_CUSTOM_PREFIX = 'offsite_conversion.custom'

_GOAL_RESULT_ACTION = {
    'OFFSITE_CONVERSIONS':  _OFFSITE_PREFIX,
    'ONSITE_CONVERSIONS':   'onsite_conversion',
    'LEAD_GENERATION':      _OFFSITE_PREFIX,
    'QUALITY_LEAD':         _OFFSITE_PREFIX,
    'LINK_CLICKS':          'link_click',
    'LANDING_PAGE_VIEWS':   'landing_page_view',
    'POST_ENGAGEMENT':      'post_engagement',
    'PAGE_LIKES':           'like',
    'THRUPLAY':             'video_view',
    'VIDEO_VIEWS':          'video_view',
    'REACH':                None,
    'IMPRESSIONS':          None,
    'AD_RECALL_LIFT':       None,
}

# Goals whose result is a (paid) conversion → CPR ("cost per result") is meaningful.
# For engagement/traffic/reach goals CPR is suppressed (would imply a conversion).
_CONVERSION_GOALS = frozenset([
    'OFFSITE_CONVERSIONS', 'ONSITE_CONVERSIONS', 'LEAD_GENERATION', 'QUALITY_LEAD',
])


def _results_for_goal(actions: dict, goal: str) -> int:
    """Sum the action(s) that count as the campaign's result for a given optimization goal.

    Falls back to offsite-conversion prefix sum for unknown goals (best effort, never
    silently 0 for a goal we simply haven't mapped). Returns 0 for reach/impression goals.
    """
    g = (goal or '').upper()
    if g in _GOAL_RESULT_ACTION:
        match = _GOAL_RESULT_ACTION[g]
        if match is None:
            return 0
    else:
        match = _OFFSITE_PREFIX  # unknown goal → assume conversion intent
    if match == _OFFSITE_PREFIX:
        return _offsite_results(actions)
    if match == 'onsite_conversion':
        return sum(v for k, v in actions.items() if k.startswith(match))
    return actions.get(match, 0)


def _custom_conversions(actions: dict) -> int:
    """Hypeddit CAPI outbound clicks — the 'offsite_conversion.custom' family.

    Prefix match, not equality: Meta returns the id-suffixed action_type
    ('offsite_conversion.custom.<id>'), and an exact match silently returned 0
    (the 2026-05-28 regression).
    """
    return sum(v for k, v in actions.items() if k.startswith(_CUSTOM_PREFIX))


def _offsite_results(actions: dict) -> int:
    """The result of an offsite-conversion goal: ONE action_type family, never the union.

    Until 2026-09-26 this was `sum(every action_type starting with 'offsite_conversion')`.
    Meta reports one outbound event under more than one offsite_conversion.* name, so
    the union counted it at least twice. Measured on spotify_etl_review,
    meta_insights_performance_day, artist_id=1 (the sandbox tenant 18 is a byte-identical
    mirror and is NOT counted here): on the 196 day-rows with custom_conversions > 0,
    results / custom_conversions lies between 1.977 and 2.574, exactly 2.00 on 118 rows;
    23 139 results against 11 356 custom_conversions.

    Which second name(s) Meta used is NOT observed — no raw `actions` payload was ever
    stored, which is why `offsite_action_types()` now persists them per ad-day. The rule
    below therefore does not name them: when the custom family is present it IS the
    result (it is the single-count reference `custom_conversions` already stored, and
    `custom_conversions <= link_clicks` held on 16/16 campaigns); every other family is
    ignored, whatever it is called. Only when no custom family exists (pixel-only
    conversion, 7 day-rows of artist 1) does the remaining offsite sum apply — unchanged
    from before, and unverified against double-counting for the same reason.
    """
    if any(k.startswith(_CUSTOM_PREFIX) for k in actions):
        return _custom_conversions(actions)
    return sum(v for k, v in actions.items() if k.startswith(_OFFSITE_PREFIX))


def offsite_action_types(actions: dict) -> Optional[str]:
    """'type=value;...' for every offsite_conversion.* action_type, sorted — or None.

    Persisted per ad-day (meta_insights.offsite_actions, migration 138) so the family
    rule of `_offsite_results` can be AUDITED against Meta's real payload and corrected
    without a second full-history rewrite if it turns out wrong.
    """
    pairs = sorted((k, v) for k, v in actions.items() if k.startswith(_OFFSITE_PREFIX))
    return ';'.join(f'{k}={v}' for k, v in pairs) or None


def _is_conversion_goal(goal: str) -> bool:
    """True if the goal's result is a (paid) conversion → CPR is meaningful.

    Unknown goals are treated as conversion intent, mirroring _results_for_goal's fallback.
    """
    g = (goal or '').upper()
    if g in _GOAL_RESULT_ACTION:
        return _GOAL_RESULT_ACTION[g] in (_OFFSITE_PREFIX, 'onsite_conversion')
    return True


# Mapping from Meta action_type to engagement table column
_ENGAGEMENT_MAP = {
    'post_engagement':               'page_interactions',
    'post_reaction':                 'post_reactions',
    'comment':                       'comments',
    'onsite_conversion.post_save':   'saves',
    'post':                          'shares',
    'like':                          'post_likes',
    'link_click':                    'link_clicks',
}


# ──────────────────────────────────────────────────────────────────────────────
# Helper: extract performance + engagement dicts from a single insight object
# ──────────────────────────────────────────────────────────────────────────────

def _extract_perf(insight, artist_id: int, goal: str = None) -> dict:
    spend = float(insight.get('spend') or 0)
    impressions = int(insight.get('impressions') or 0)
    reach = int(insight.get('reach') or 0)
    frequency = float(insight.get('frequency') or 0)
    link_clicks = int(insight.get('inline_link_clicks') or 0)
    cpm_raw = float(insight.get('cpm') or 0)
    ctr = float(insight.get('ctr') or 0)

    # Aggregate every action type once (action_type → summed value).
    actions = {}
    for action in (insight.get('actions') or []):
        atype = action['action_type']
        actions[atype] = actions.get(atype, 0) + int(float(action['value']))

    # custom_conversions = Spotify button clicks via Hypeddit CAPI. Prefix match catches
    # the id-suffixed action_type ('offsite_conversion.custom.<id>') Meta actually returns.
    custom_conversions = _custom_conversions(actions)
    lp_views = actions.get('landing_page_view', 0)

    # results = Meta's native result for this ad set's optimization goal.
    results = _results_for_goal(actions, goal)

    # CPR ("cost per result") is only meaningful for conversion goals — suppressed
    # otherwise so an engagement/traffic cost-per-action is not mistaken for a conversion CPR.
    cpr = round(spend / results, 4) if (_is_conversion_goal(goal) and results > 0) else None

    return {
        'artist_id':          artist_id,
        'campaign_name':      insight.get('campaign_name', ''),
        'spend':              spend,
        'impressions':        impressions,
        'reach':              reach,
        'frequency':          frequency,
        'results':            results,
        'custom_conversions': custom_conversions,
        'cpr':                cpr,
        'cpm':                cpm_raw or None,
        'link_clicks':        link_clicks,
        'cpc':                round(spend / link_clicks, 4) if link_clicks > 0 else None,
        'ctr':                ctr,
        'lp_views':           lp_views,
    }


def _extract_eng(insight, artist_id: int) -> dict:
    row = {
        'artist_id':        artist_id,
        'campaign_name':    insight.get('campaign_name', ''),
        'page_interactions': 0,
        'post_reactions':   0,
        'comments':         0,
        'saves':            0,
        'shares':           0,
        'link_clicks':      0,
        'post_likes':       0,
    }
    for action in (insight.get('actions') or []):
        col = _ENGAGEMENT_MAP.get(action['action_type'])
        if col:
            row[col] += int(float(action['value']))
    return row
