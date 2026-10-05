"""EN strings for the SoundCloud view."""

EN = {
    "soundcloud.kpi_plays": "🎧 Total Plays",
    "soundcloud.kpi_likes": "❤️ Total Likes",
    "soundcloud.kpi_reposts": "🔄 Total Reposts",
    "soundcloud.kpi_comments": "💬 Total Comments",
    "soundcloud.likes_caption": "ℹ️ **{n} tracks**, last reading on **{d}**. Likes and history reliable since 2026-05-15 (OAuth user-token collection). S4A/Apple CSV sources not linked — separate matter.",
    "soundcloud.no_data": "No SoundCloud data found. Run the collector.",
    "soundcloud.no_data_claim_hint": (
        "Are your releases published under a label's or a collective's account? "
        "Declare them below: we will collect their plays even when hosted elsewhere."
    ),
    "soundcloud.sql_error_kpi": "SQL error (KPIs): {err}",
    "soundcloud.plays": "Plays",
    "soundcloud.comments": "Comments",
    "soundcloud.top_tracks": "🏆 My tracks compared",
    "soundcloud.sort_by": "Compare on",
    "soundcloud.col_title": "Title",
    "soundcloud.col_comments": "💬 Comments",
    "soundcloud.col_eng_rate": "💯 Engagement %",
    "soundcloud.col_days_since": "📅 Released (days ago)",
    # Le catalogue sur un axe temporel — demandé le 2026-09-21.
    "soundcloud.catalog_header": "📊 Whole catalogue — plays, likes, reposts, comments",
    "soundcloud.plays_axis": "Cumulative plays",
    "soundcloud.engagement_axis": "Likes, reposts, comments (cumulative)",
    "soundcloud.likes": "Likes",
    "soundcloud.reposts": "Reposts",
    "soundcloud.catalog_caption": "**{n} reading(s)** over {t} track(s). These counters "
                                  "are LIFETIME cumulatives: the curve rises or stays "
                                  "flat, it never comes back down.",
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
    "soundcloud.top_volume": "Volume — {m}",
    "soundcloud.top_rate": "Engagement rate (%)",
    "soundcloud.eng_rate": "Engagement %",
    "soundcloud.top_table": "🔢 The detailed figures",
    "soundcloud.top_caption": "The top {n} tracks, sorted by **{m}**. On the right, the "
                              "**engagement rate** — (likes + reposts + comments) ÷ plays: "
                              "it is what tells a widely played track from one that makes "
                              "people REACT, and a volume sort buries it. The detailed "
                              "figures stay in the drawer below.",
    "soundcloud.age_header": "📈 The whole catalogue, at equal age",
    "soundcloud.age_pick": "Tracks to compare",
    "soundcloud.age_metric": "Counter",
    "soundcloud.age_pick_one": "Pick at least one track.",
    "soundcloud.age_empty": "No readable reading of this counter for these tracks.",
    "soundcloud.age_axis": "Days since upload",
    "soundcloud.age_value_axis": "Cumulative {m}",
    "soundcloud.age_caption": "SoundCloud only gives today's counter: each curve starts at "
                              "the track's age on the first collected reading, not at its "
                              "upload. Two tracks compare where their curves overlap.",
}
