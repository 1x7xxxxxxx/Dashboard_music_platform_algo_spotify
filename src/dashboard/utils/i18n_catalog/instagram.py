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
    "instagram.account": "Account: @{username}",
    "instagram.kpi_followers": "👥 Followers",
    "instagram.kpi_follows": "➡️ Following",
    "instagram.kpi_media": "📸 Posts",
    "instagram.no_data": "No Instagram data. Run the collector.",
    "instagram.community_growth": "📈 Community growth",
    "instagram.nothing_in_window": (
        "No Instagram readings in this period. The latest is from **{last}** — "
        "widen the window to see the history again."),
    "instagram.not_enough_history": "No Instagram reading for this account. Connect it from **🔑 API credentials + CSV imports**.",
    "instagram.followers": "Followers",
    "instagram.follows": "Following",
    "instagram.publications": "Posts",
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
    "instagram.insights_unavailable": "**Impressions, reach, saves and shares are unavailable.** Meta only serves them for posts under **90 days**, and your most recent publication is **{j} days** old. This is not a collection failure: running a collection again will not bring them back. They will return on their own after your next post.",
    "instagram.no_media": "No posts collected for this period.",
    "instagram.media_error": "Posts error: {err}",
    # La communauté en petits multiples, en VRAIES valeurs (2026-09-21).
    "instagram.community_title": "My community over time ({label})",
    "instagram.community_caption": "**{n} reading(s)**, latest on **{d}**. Over the "
                                   "period: **{g:+d} follower(s)**. Each panel has its "
                                   "own scale, tightened on its values — an axis anchored "
                                   "at zero would hide a gain of three followers out of "
                                   "fifteen hundred. All three curves carry their REAL "
                                   "values: nothing is rebased.",
    "instagram.no_posts_in_window": "No publication in this window. The account has **{n}** "
                                    "in total, the latest from **{d}** — **{j} days** ago. "
                                    "Widen the period to see the history again.",
    "instagram.insights_unavailable_scope": "**Impressions, reach, saves and shares are "
                                            "unavailable.** Meta reserves them for posts "
                                            "under 90 days AND the "
                                            "`instagram_manage_insights` scope — check the "
                                            "permission in **🔑 Credentials**.",
}
