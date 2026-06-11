"""EN strings for the Meta Ads creatives view."""

EN = {
    "meta_creatives.title": "🎨 Meta Ads Creatives",
    "meta_creatives.subtitle": (
        "Your creatives ranked by CPR — based on Meta Ads API data (meta_ads × meta_insights)."
    ),
    "meta_creatives.no_data": (
        "No creative data available. Check that the **meta_ads_api_daily** DAG has "
        "collected data via the Meta Ads API (tables `meta_ads` + `meta_insights`)."
    ),
    "meta_creatives.filter_by_campaign": "Filter by campaign",
    "meta_creatives.all_campaigns": "All",
    "meta_creatives.no_creative_campaign": "No creative for this campaign.",
    "meta_creatives.tab_ranking": "📋 Ranking",
    "meta_creatives.tab_compare": "🫧 Comparison",
    "meta_creatives.tab_funnel": "🔻 Funnel",
    "meta_creatives.tab_evolution": "📈 Evolution",
    "meta_creatives.tab_fatigue": "🪫 Fatigue",
    "meta_creatives.tab_activity": "🗓️ Activity",
    "meta_creatives.badge_legend": (
        "🟢 Top creative = CPR ≤ {low}€ | 🟡 Average = CPR ≤ {high}€ | "
        "🔴 Underperforming = CPR > {high}€"
    ),
    # Uncollected-campaigns notice
    "meta_creatives.uncollected_title": "⚠️ {n} campaign(s) missing from the creative ranking",
    "meta_creatives.uncollected_body": (
        "**{n} campaign(s) did spend** (collected at campaign level) but **their "
        "per-creative (ad-level) detail was not collected**. Typical case: a "
        "**paused or archived** campaign — its ads switch to "
        "`CAMPAIGN_PAUSED`/`ARCHIVED` status and are only reloaded by a complete "
        "**full-history** collection (which re-fetches the ads config, not just the "
        "insights):\n"
        "- Airflow → DAG `meta_ads_api_daily` → *Trigger DAG w/ config* "
        "`{{\"full_history\": true}}` (run **not** `insights_only`), or\n"
        "- locally: `python airflow/debug_dag/debug_meta_ads_api.py --full-history --write`\n\n"
        "_Caveats:_ (1) per-creative detail is only retrievable while the ads still "
        "exist on Meta's side (not deleted); (2) Meta only keeps insights for "
        "**~37 months** — beyond that, only the campaign total remains available."
    ),
    "meta_creatives.col_campaign": "Campaign",
    "meta_creatives.col_ads": "Ads",
    "meta_creatives.col_campaign_spend": "Campaign spend (€)",
    # Badges
    "meta_creatives.badge_no_result": "⚫ No result",
    "meta_creatives.badge_top": "🟢 Top creative",
    "meta_creatives.badge_avg": "🟡 Around average",
    "meta_creatives.badge_under": "🔴 Underperforming",
    # KPI row
    "meta_creatives.total_spend": "Total spend",
    "meta_creatives.best_cpr": "Best CPR",
    "meta_creatives.median_cpr": "Median CPR",
    "meta_creatives.worst_cpr": "Worst CPR",
    # Ranking table
    "meta_creatives.col_status": "Status",
    "meta_creatives.col_creative": "Creative",
    "meta_creatives.col_spend": "Spend",
    "meta_creatives.col_results": "Results",
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
    "meta_creatives.results": "Results",
    "meta_creatives.frequency": "Frequency",
    "meta_creatives.fatigue_caption": (
        "Rising frequency **and** falling CTR = saturated audience (fatigue) → refresh the creative."
    ),
    "meta_creatives.no_spend_series": "No per-creative spend series.",
    "meta_creatives.heatmap_title": "**🗓️ Spend per creative and per week**",
    "meta_creatives.cumulative_title": "**💰 Cumulative spend per creative**",
    "meta_creatives.cumulative_spend_eur": "Cumulative spend (€)",
}
