"""EN strings for the SoundCloud view."""

EN = {
    "soundcloud.no_data": "No SoundCloud data found. Run the collector.",
    "soundcloud.no_data_claim_hint": (
        "Are your releases published under a label's or a collective's account? "
        "Declare them below: we will collect their plays even when hosted elsewhere."
    ),
    "soundcloud.sql_error_kpi": "SQL error (KPIs): {err}",
    "soundcloud.plays": "Plays",
    "soundcloud.comments": "Comments",
    "soundcloud.top_tracks": "🏆 My tracks compared",
    # Le catalogue sur un axe temporel — demandé le 2026-09-21.
    "soundcloud.catalog_header": "📊 Whole catalogue — plays, likes, reposts, comments",
    "soundcloud.plays_axis": "Cumulative plays",
    "soundcloud.engagement_axis": "Likes, reposts, comments (cumulative)",
    "soundcloud.likes": "Likes",
    "soundcloud.reposts": "Reposts",
    "soundcloud.catalog_dropped": "⚠️ **{k} day(s) dropped** ({d}): the cumulative fell "
                                  "below its own maximum there — a collection that "
                                  "answered wrong, not an audience loss. Plotting them "
                                  "would draw a fall that never happened.",
    "soundcloud.catalog_likes_dropped": "⚠️ **{k} day(s) without readable likes**: at "
                                        "least one track read 0 likes there after "
                                        "having counted some — a failed read, not "
                                        "likes withdrawn. The likes curve skips them.",
    "soundcloud.catalog_unreadable": "No readable reading: every collected day carries a "
                                     "receding cumulative, which signals a broken "
                                     "collection.",

    # La base 100, repointée sur la couche or.

    # Le classement en figure.
    "soundcloud.eng_rate": "Engagement %",
    "soundcloud.eng_rate_def": "Engagement % = (likes + reposts + comments) ÷ plays",
    "soundcloud.age_header": "📈 The whole catalogue, at equal age",
    "soundcloud.age_pick": "Tracks to compare",
    "soundcloud.age_metric": "Counter",
    "soundcloud.age_empty": "No readable reading of this counter for these tracks.",
    "soundcloud.age_axis": "Days since upload",
    "soundcloud.age_value_axis": "Cumulative {m}",
}
