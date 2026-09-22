"""EN strings for the Meta Ads creatives view."""

EN = {
    # ── Page unique : décision en haut, puis classement, hooks, fatigue ──────
    "meta_creatives.banner_intro": (
        "**{spend:,.0f} € spent across {n} creative(s).** Here are the three "
        "decisions those numbers carry."),
    "meta_creatives.best_creative": "🏆 Best creative — {nom}",
    "meta_creatives.backed_by": "{spend:.0f} € · {res:,.0f} results",
    "meta_creatives.no_winner": "No creative has enough results yet to be crowned.",
    "meta_creatives.best_hook": "🎣 Best hook — {nom}",
    "meta_creatives.hook_backed_by": (
        "{spend:.0f} € · {n} creative(s) · {part:.0f} % of the named budget"),
    "meta_creatives.no_hook_named": (
        "No hook is named in your creative titles. Name them \"Hook 1 …\", "
        "\"Hook 2 …\", \"Sans hook …\" and this card will tell you which one "
        "converts."),
    "meta_creatives.to_cut": "✂️ Cut this — {nom}",
    "meta_creatives.already_spent": (
        "{spend:.0f} € spent · ~{trop:.0f} € more than your blended cost "
        "({ref:.3f} €)"),
    "meta_creatives.nothing_to_cut": "No creative is drifting on a budget that matters.",
    "meta_creatives.section_ranking": "🏁 Your creatives, ranked",
    "meta_creatives.section_hooks": "🎣 Which hook converts",
    "meta_creatives.section_fatigue": "🪫 Is the audience saturated?",
    "meta_creatives.section_details": "🔬 Dig deeper",
    "meta_creatives.no_ranking": "No creative with any spend.",
    "meta_creatives.ranking_caption": (
        "Best cost per result on top. A missing bar means no measured result, "
        "hence no CPR — it is not a zero."),
    "meta_creatives.ranking_truncated": (
        "Only the {n} highest-spending creatives are drawn; the collapsed table "
        "below holds them all."),
    "meta_creatives.table_expander": "🔢 The ranking down to the cent — table",
    "meta_creatives.funnel_expander": "🔻 One creative's journey — detail",
    "meta_creatives.hook_cpr": "Cost per result (€)",
    "meta_creatives.hook_spend": "Spend it was judged on (€)",
    "meta_creatives.hooks_absent": (
        "Your creative titles do not name a hook (yet). Name them \"Hook 1 — …\", "
        "\"Hook 2 — …\", \"Sans hook — …\": this chart will then compare the "
        "cost per result of each opening."),
    "meta_creatives.hooks_caption": (
        "The hook is read from the NAME you give your creative — Meta does not "
        "know it. **{part:.0f} % of your spend** carries a named hook; the rest "
        "is not ranked here. A lower cost on a tiny spend is not a verdict: that "
        "is what the second panel is for."),
    "meta_creatives.rank.cpr": "CPR (€)",
    "meta_creatives.rank.total_spend": "Spend (€)",
    "meta_creatives.rank.total_results": "Outbound clicks",
    "meta_creatives.rank.avg_ctr": "CTR (%)",
    "meta_creatives.unit_money": "Euros",
    "meta_creatives.unit_counts": "Volumes",
    "meta_creatives.unit_rate": "Rate (%)",
    "meta_creatives.partial_weeks": (
        "{n} week(s) are not drawn: fewer than half of their days were measured, and "
        "summing them at full height would read as a drop that never happened. The "
        "line breaks there — we do not know."),
    'meta_creatives.uncollected_admin': '🛠️ Recoverable with a full-history collection (which re-fetches the ad config, not only the insights): Airflow → `meta_ads_api_daily` → *Trigger DAG w/ config* `{{"full_history": true}}`. Caveats: the ads must still exist on Meta\'s side, and Meta only keeps insights ~37 months.',
    "meta_creatives.title": "🎨 Meta Ads Creatives",
    "meta_creatives.subtitle": (
        "Your creatives ranked by CPR — based on Meta Ads API data (meta_ads × meta_insights)."
    ),
    "meta_creatives.no_data": (
        'No creative data. Check that Meta Ads is connected in **🔑 Credentials API**, then run **🚀 Launch ALL collections** in the sidebar.'),
    "meta_creatives.filter_by_campaign": "Filter by campaign",
    "meta_creatives.all_campaigns": "All",
    "meta_creatives.no_creative_campaign": "No creative for this campaign.",
    "meta_creatives.badge_legend": (
        "🟢 Top creative = CPR ≤ {low}€ | 🟡 Average = CPR ≤ {high}€ | "
        "🔴 Underperforming = CPR > {high}€"
    ),
    # Uncollected-campaigns notice
    "meta_creatives.uncollected_title": "⚠️ {n} campaign(s) missing from the creative ranking",
    "meta_creatives.uncollected_body": (
        '**{n} campaign(s) did spend**, but the **per-creative** breakdown could not be retrieved. Common case: a **paused or archived** campaign — Meta stops serving its ad-by-ad detail.\n\nThe campaign total is still correct; only the split across creatives is missing. Tell the administrator if those campaigns matter to you.'),
    "meta_creatives.col_campaign": "Campaign",
    "meta_creatives.col_ads": "Ads",
    "meta_creatives.col_campaign_spend": "Campaign spend (€)",
    # Badges
    "meta_creatives.badge_no_result": "⚫ No result",
    "meta_creatives.badge_top": "🟢 Top creative",
    "meta_creatives.badge_avg": "🟡 Around average",
    "meta_creatives.badge_under": "🔴 Underperforming",
    # KPI row
    # Ranking table
    "meta_creatives.col_status": "Status",
    "meta_creatives.col_creative": "Creative",
    "meta_creatives.col_spend": "Spend",
    "meta_creatives.col_results": "Outbound clicks",
    "meta_creatives.col_avg_ctr": "Avg CTR",
    # Timeline
    "meta_creatives.timeline_title": "📈 Creative evolution over time",
    "meta_creatives.no_adlevel_insights": "No creative with ad-level insights for this selection.",
    "meta_creatives.creative": "Creative",
    "meta_creatives.no_timeseries": "No time series for this creative.",
    "meta_creatives.no_data_period": "No data for the selected period.",
    "meta_creatives.granularity_weekly": "weekly",
    "meta_creatives.granularity_daily": "daily",
    "meta_creatives.timeline_caption": (
        "Creative **{creative}** · {granularity} granularity · {d_from} → {d_to}. "
        "Click a metric in the legend to show/hide it (double-click = isolate)."
    ),
    "meta_creatives.metric.spend": "Spend (€)",
    "meta_creatives.metric.impressions": "Impressions",
    "meta_creatives.metric.clicks": "Clicks",
    "meta_creatives.metric.reach": "Reach",
    "meta_creatives.metric.conversions": "Results",
    "meta_creatives.metric.ctr": "CTR (%)",
    "meta_creatives.metric.cpr": "CPR (€)",
    # Scatter
    "meta_creatives.no_scatter": "No creative with a CPR (results) for this scatter.",
    "meta_creatives.spend_eur": "Spend (€)",
    "meta_creatives.avg_ctr_pct": "Avg CTR (%)",
    "meta_creatives.impressions": "Impressions",
    "meta_creatives.scatter_caption": (
        "One bubble = one creative. Low = efficient CPR; size = impressions, colour = CTR. "
        "Creatives with no result (missing CPR) are not plotted."
    ),
    # Efficiency / funnel / fatigue / activity
    "meta_creatives.indicator": "Indicator",
    "meta_creatives.no_creative": "No creative.",
    "meta_creatives.clicks": "Clicks",
    "meta_creatives.results": "Outbound clicks",
    "meta_creatives.frequency": "Frequency",
    "meta_creatives.fatigue_caption": (
        "Rising frequency **and** falling CTR = saturated audience (fatigue) → refresh the creative."
    ),
    "meta_creatives.no_spend_series": "No per-creative spend series.",
    "meta_creatives.heatmap_title": "**🗓️ Spend per creative and per week**",
    "meta_creatives.cumulative_title": "**💰 Cumulative spend per creative**",
    "meta_creatives.cumulative_spend_eur": "Cumulative spend (€)",
    "meta_creatives.activity_expander": "🗓️ Creative activity (weekly spend, cumulative) — detail",
    "meta_creatives.scatter_expander": "🔬 CPR × spend scatter — detail",
    "meta_creatives.efficiency_expander": "🔬 Efficiency by creative — detail",
}
