"""EN strings for the Instagram view."""

EN = {
    "instagram.engagement_by_cohort": (
        "Likes and comments EARNED TO DATE, by month of publication ({label})"),
    "instagram.month_published": "Month published",
    "instagram.engagement_cohort_note": (
        "Each bar groups the posts **published** that month and shows the likes they "
        "have accumulated **up to today** — not the ones received during that month. "
        "Instagram only gives us a current counter per post: there is no history to "
        "derive a monthly engagement from, and inventing it would be worse than not "
        "showing it. The period filter therefore applies to the **publication** date."),
    "instagram.title": "📸 Instagram - Performance",
    "instagram.account": "Account: @{username}",
    "instagram.kpi_followers": "👥 Followers",
    "instagram.kpi_follows": "➡️ Following",
    "instagram.kpi_media": "📸 Posts",
    "instagram.kpi_last_update": "📅 Last update",
    "instagram.no_data": "No Instagram data. Run the collector.",
    "instagram.community_growth": "📈 Community growth",
    "instagram.no_history": "No history data for this period.",
    "instagram.followers_evolution": "Follower Evolution ({label})",
    "instagram.followers_axis": "Number of followers",
    "instagram.base100_header": "📈 Relative evolution (base 100)",
    "instagram.not_enough_history": "Not enough history for an evolution (≥2 collections).",
    "instagram.followers": "Followers",
    "instagram.follows": "Following",
    "instagram.publications": "Posts",
    "instagram.base100_title": "Relative evolution — base 100 ({label})",
    "instagram.metric_lbl": "Metric",
    "instagram.base100_axis": "Base 100 (1st point = 100)",
    "instagram.history_error": "History error: {err}",
    "instagram.engagement_header": "📝 Engagement & posts",
    "instagram.no_posts": "No posts in this period.",
    "instagram.likes_comments_axis": "Likes + comments",
    "instagram.engagement_rate_title": "Engagement rate ≈ (avg. eng./post) ÷ followers — indicative",
    "instagram.rate_axis": "Rate (%)",
    "instagram.rate_expander": "📈 Engagement rate (indicative)",
    "instagram.rate_caption": (
        "Indicative: followers = latest snapshot (follower history "
        "is sparse vs the posts' time span)."
    ),
    "instagram.recent_posts": "#### Recent posts",
    "instagram.col_preview": "Preview",
    "instagram.col_link": "Link",
    "instagram.col_open": "Open",
    "instagram.col_caption": "Caption",
    "instagram.col_published": "Published on",
    "instagram.col_comments": "💬 Comments",
    "instagram.insights_unavailable": (
        "Insights (impressions/reach/saved/shares) unavailable: "
        "the Meta API only provides them for posts < 90 days old with "
        "the instagram_manage_insights scope. Re-collect after a "
        "recent post."
    ),
    "instagram.no_media": "No posts collected for this period.",
    "instagram.media_error": "Posts error: {err}",
}
