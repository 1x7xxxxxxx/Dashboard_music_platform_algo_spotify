"""EN strings for the YouTube view."""

EN = {
    "youtube.channel_header": "📈 Channel Evolution",
    "youtube.subscribers": "Subscribers",
    "youtube.total_views": "Total Views",
    "youtube.channel_chart_title": "Growth: Subscribers vs Total Views",
    "youtube.cumulative_views": "Cumulative Views",
    "youtube.no_channel_history": "No channel history yet.",
    "youtube.top_header": "🏆 Top Content (Multi-Axis Analysis)",
    "youtube.type_short": "Short 📱",
    "youtube.type_video": "Video 📹",
    "youtube.content_type": "Content type",
    "youtube.n_videos": "Number of videos",
    "youtube.views": "Views",
    "youtube.comments": "Comments",
    "youtube.ratio_views_like": "Views/Like Ratio",
    "youtube.top_chart_title": "Top {n} {type}",
    "youtube.no_video_category": "No video in this category.",
    "youtube.no_video_db": "No video found in the database.",
    "youtube.error": "Error: {err}",
    # La légende d'honnêteté qui remplace les trois tuiles (2026-09-21).
    "youtube.channel_caption": "**Subscribers**: YouTube rounds this counter to three "
                               "significant figures on the public API — only {n} "
                               "distinct value(s) over {j} days of readings here, hence "
                               "the staircase. The exact daily figure exists, but it "
                               "needs **channel-owner** access (YouTube Analytics API), "
                               "not an API key.\n\n"
                               "**Views**: the curve sums the PER-VIDEO counters, which "
                               "move by single units ({vues}). The counter YouTube shows "
                               "for the channel reads {chaine} — it includes private and "
                               "deleted videos and internal aggregates that are absent "
                               "from the catalogue analysed here. Seeing them diverge is "
                               "information, not an error.",
    "youtube.cohort_notice": "Ranked **by publication date**: the window picks the "
                             "videos RELEASED in the period. The figures are the ones "
                             "**earned to date**, since publication — not the activity "
                             "of the period.",
}
