"""EN strings for the Meta Ads creatives view."""

EN = {
    # ── One page: ranking, spend Pareto, best settings, one creative's timeline ──
    "meta_creatives.gain_unknown": "Streams gained: not separable — this creative ran with others in its campaign, or without a confirmed linked track. To measure it, run it alone.",
    "meta_creatives.gain_metric": "Streams gained (creative alone in its campaign)",
    "meta_creatives.gain_help": "The track's streams during the campaign above its level of the 28 days before. Cost per stream gained: {c}.",
    "meta_creatives.section_ranking": "🏁 Your creatives, ranked",
    "meta_creatives.no_ranking": "No creative with any spend.",
    "meta_creatives.hook_cpr": "Cost per result (€)",
    "meta_creatives.hook_spend": "Spend it was judged on (€)",
    "meta_creatives.hooks_absent": (
        "Your creative titles do not name a hook (yet). Name them \"Hook 1 — …\", "
        "\"Hook 2 — …\", \"Sans hook — …\": this chart will then compare the "
        "cost per result of each opening."),
    "meta_creatives.rank_sort": "Sort by",
    "meta_creatives.rank.cpr": "CPR (€)",
    "meta_creatives.rank.total_spend": "Spend (€)",
    "meta_creatives.rank.total_results": "Outbound clicks",
    "meta_creatives.rank.avg_ctr": "CTR (%)",
    "meta_creatives.rank.cpm": "CPM (€)",
    "meta_creatives.rank.cpc": "CPC (€)",
    "meta_creatives.unit_money": "Euros",
    "meta_creatives.unit_counts": "Volumes",
    "meta_creatives.unit_rate": "Rate (%)",
    "meta_creatives.partial_weeks": (
        "{n} week(s) are not drawn: fewer than half of their days were measured, and "
        "summing them at full height would read as a drop that never happened. The "
        "line breaks there — we do not know."),
    'meta_creatives.uncollected_admin': '🛠️ Recoverable with a full-history collection (which re-fetches the ad config, not only the insights): Airflow → `meta_ads_api_daily` → *Trigger DAG w/ config* `{{"full_history": true}}`. Caveats: the ads must still exist on Meta\'s side, and Meta only keeps insights ~37 months.',
    "meta_creatives.title": "🎨 Meta Ads Creatives",
    "meta_creatives.no_data": (
        'No creative data. Check that Meta Ads is connected in **🔑 Credentials API** — the collection starts by itself when you save, and its state shows in the sidebar.'),
    "meta_creatives.no_creative_campaign": "No creative for this campaign.",
    # Uncollected-campaigns notice
    "meta_creatives.uncollected_title": "⚠️ {n} campaign(s) missing from the creative ranking",
    "meta_creatives.uncollected_body": (
        '**{n} campaign(s) did spend**, but the **per-creative** breakdown could not be retrieved. Common case: a **paused or archived** campaign — Meta stops serving its ad-by-ad detail.\n\nThe campaign total is still correct; only the split across creatives is missing. Tell the administrator if those campaigns matter to you.'),
    # Timeline
    "meta_creatives.timeline_title": "📈 Creative evolution over time",
    "meta_creatives.no_adlevel_insights": "No creative with ad-level insights for this selection.",
    "meta_creatives.creative": "Creative",
    "meta_creatives.no_timeseries": "No time series for this creative.",
    "meta_creatives.no_data_period": "No data for the selected period.",
    "meta_creatives.metric.spend": "Spend (€)",
    "meta_creatives.metric.impressions": "Impressions",
    "meta_creatives.metric.clicks": "Clicks",
    "meta_creatives.metric.reach": "Reach",
    "meta_creatives.metric.conversions": "Results",
    "meta_creatives.metric.ctr": "CTR (%)",
    "meta_creatives.metric.cpr": "CPR (€)",
    "meta_creatives.unit_cpr": "Cost per result (€)",
    "meta_creatives.pair_caption": "Blue: « {a} » · orange: « {b} » · grey: a creative of both campaigns.",
    'meta_creatives.section_best': '🧪 Your best settings',
    'meta_creatives.bs_creative': 'Creative',
    'meta_creatives.bs_hook': 'Hook',
    'meta_creatives.bs_country': 'Country',
    'meta_creatives.bs_placement': 'Placement',
    'meta_creatives.bs_platform': 'Platform',
    'meta_creatives.bs_age': 'Age',
    'meta_creatives.bs_cta': 'Call-to-action button (€/click)',
    'meta_creatives.bs_objective': 'Objective (€/click)',
    'meta_creatives.bs_empty': 'Not enough measured spend yet to compare your settings.',
    'meta_creatives.hooks_expander': '🎣 Hooks in detail — {part:.0f} % of the spend carries a named hook',
    'meta_creatives.compare_with': 'Compare with',
    'meta_creatives.compare_none': '— none —',
    'meta_creatives.tl_totals': '**Total spend** {spend} € · **Average CPR** {cpr}',
    # R568
    "meta_creatives.uncollected_row": "- **{c}** — {ads} ad(s) · {spend} €",
    "meta_creatives.goal_unknown": "unknown goal",
    "meta_creatives.tl_context": "{campaign} ({goal})",
    "meta_creatives.section_pareto": "💶 Where the money went",
    "meta_creatives.pareto_x": "Spend (€)",
    "meta_creatives.pareto_campaigns": "Campaigns",
    "meta_creatives.pareto_empty": "No campaign chosen.",
    "meta_creatives.bs_goal": "Ad set optimisation (€/outbound click)",
}
