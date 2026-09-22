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
    "soundcloud.plays_evolution": "📈 Plays evolution",
    "soundcloud.chart_filters": "⚙️ Chart filters",
    "soundcloud.filter_by_tracks": "Filter by tracks",
    "soundcloud.growth_title": "Growth ({start} - {end})",
    "soundcloud.cumulative_plays": "Cumulative Plays",
    "soundcloud.base100_header": "📈 Metric evolution (base 100)",
    "soundcloud.plays": "Plays",
    "soundcloud.comments": "Comments",
    "soundcloud.base100_title": "Metric evolution — base 100 ({label})",
    "soundcloud.base100_axis": "Base 100 (1st pt = 100)",
    "soundcloud.no_data_selection": "No data for this selection (check the dates or tracks).",
    "soundcloud.empty_history": "History empty for now.",
    "soundcloud.history_error": "History error: {err}",
    "soundcloud.top_tracks": "🏆 Top Tracks",
    "soundcloud.sort_by": "Sort by",
    "soundcloud.engagement": "Engagement",
    "soundcloud.col_title": "Title",
    "soundcloud.col_comments": "💬 Comments",
    "soundcloud.col_eng_rate": "💯 Engagement %",
    "soundcloud.col_days_since": "📅 Released (days ago)",
    # Le catalogue sur un axe temporel — demandé le 2026-09-21.
    "soundcloud.catalog_header": "📊 Whole catalogue — plays, likes, reposts, comments",
    "soundcloud.panel_plays": "Cumulative plays",
    "soundcloud.panel_engagement": "Cumulative engagement — likes, reposts, comments",
    "soundcloud.likes": "Likes",
    "soundcloud.reposts": "Reposts",
    "soundcloud.catalog_caption": "**{n} reading(s)** over {t} track(s). These counters "
                                  "are LIFETIME cumulatives: the curve rises or stays "
                                  "flat, it never comes back down.",
    "soundcloud.catalog_dropped": "⚠️ **{k} day(s) dropped** ({d}): the cumulative fell "
                                  "below its own maximum there — a collection that "
                                  "answered wrong, not an audience loss. Plotting them "
                                  "would draw a fall that never happened.",
    "soundcloud.catalog_unreadable": "No readable reading: every collected day carries a "
                                     "receding cumulative, which signals a broken "
                                     "collection.",

    # La base 100, repointée sur la couche or.
    "soundcloud.base100_empty": "No reading over this window for the selection.",
    "soundcloud.base100_nothing": "Nothing to normalise for **{tracks}**: it takes at "
                                  "least two readings with a non-zero value on the same "
                                  "metric. A track with no likes has no likes trend.",
    "soundcloud.base100_caption": "Each metric is 100 at its first readable reading: that "
                                  "is what lets plays in the thousands be compared to "
                                  "comments in the tens. Readings where a counter is 0 "
                                  "AFTER having been positive are dropped — that is a "
                                  "failed read, not a loss of interest. A plain decrease "
                                  "is KEPT: a like can be taken back.",

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
    "soundcloud.base100_out_of_window": "No reading of **{tracks}** in this window. The "
                                        "latest one is from **{last}** — widen the "
                                        "period to see the history again.",
}
