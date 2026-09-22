"""EN strings for the Meta Ads overview view."""

EN = {
    "meta_ads_overview.scope_period": "**{spend} €** across **{campaigns}** "
                                      "campaign(s), from {start} to {end}.",
    "meta_ads_overview.scope_linked": " **{linked}** campaign(s) are linked to a track: "
                                      "cost per track is readable for those, and only "
                                      "those.",
    "meta_ads_overview.scope_unlinked": " No campaign is linked to a track — so this "
                                        "section answers \"how much did I spend, and who "
                                        "did it reach\", not \"what did this track cost "
                                        "me\". A campaign named like a song is not a link.",
    # Comptes d'agence — déplacés de Credentials vers cette page le 2026-09-05.
    "meta.extra_accounts_title": "➕ Extra ad accounts - for agencies (optional)",
    "meta.extra_accounts_help": (
        "Main account: **{main}** — change it in 🔑 API Credentials. Add the other "
        "accounts to track here, **one per line**."
    ),
    "meta.extra_accounts_field": "Extra accounts",
    "meta.extra_accounts_save": "💾 Save these accounts",
    "meta.extra_accounts_malformed": (
        "❌ Badly formatted account(s): {bad}. Digits only, optionally prefixed with "
        "`act_`, one per line."
    ),
    "meta.extra_accounts_failed": "Could not save — try again in a moment.",
    "meta.extra_accounts_saved": "✅ {n} account(s) tracked.",
    "meta_ads_overview.title": "📱 Meta Ads - Strategic Analysis",
    "meta_ads_overview.db_error": "DB connection error: {e}",
    "meta_ads_overview.scope": "🎯 Analysis Scope",
    "meta_ads_overview.select_campaigns": "Select the campaigns to analyse:",
    "meta_ads_overview.global_perf": "### 🚀 Overall Performance",
    "meta_ads_overview.link_clicks": "Link Clicks",
    "meta_ads_overview.capi_required": (
        "CPR empty: it requires CAPI (server-side events) — no custom "
        "conversion is reported here."),
    # Les six cadres de la performance globale, construits par
    # `t(f"meta_ads_overview.perf.{i}", libellé)`. `_PERF_PANNEAUX` les énumère et
    # `test_the_global_perf_names_every_panel_it_draws` vérifie que chacun a sa clé.
    "meta_ads_overview.perf.0": "Spend (€)",
    "meta_ads_overview.perf.1": "Impressions",
    "meta_ads_overview.perf.2": "Link clicks",
    "meta_ads_overview.perf.3": "CPM (€)",
    "meta_ads_overview.perf.4": "CPC (€)",
    "meta_ads_overview.perf.5": "CPR (€)",
    "meta_ads_overview.engagement": "##### ❤️ Engagement",
    "meta_ads_overview.total_interactions": "⚡ Total Interactions",
    "meta_ads_overview.spotify_clicks": "Spotify Clicks",
    "meta_ads_overview.perf_by_campaign": "📊 Performance by Campaign",
    "meta_ads_overview.budget_eur": "Budget (€)",
    "meta_ads_overview.chart_360": "360° View: Budget vs Volumes vs Ratios",
    "meta_ads_overview.spend_eur": "Spend (€)",
    "meta_ads_overview.time_evolution": "⏳ Time Evolution (Budget vs Results vs CPR)",
    "meta_ads_overview.daily_dynamics": "Daily Dynamics",
    "meta_ads_overview.no_time_data": "No time-series data.",
    "meta_ads_overview.summary_table": "🗃️ Summary Table",
    "meta_ads_overview.targeting_perf": "🎯 Targeting vs Performance",
    "meta_ads_overview.targeting_caption": (
        "Spend & CPR aggregated by ad-set targeting attribute (ad-level results)."
    ),
    "meta_ads_overview.no_targeting_data": "No ad-set targeting data available.",
    "meta_ads_overview.all_platforms": "All",
    "meta_ads_overview.unknown": "Unknown",
    "meta_ads_overview.age_unspecified": "Unspecified",
    "meta_ads_overview.slice_by": "Slice by",
    "meta_ads_overview.dim.optimization_goal": "Optimisation goal",
    "meta_ads_overview.dim.gender": "Targeted gender",
    "meta_ads_overview.dim.publisher_platforms": "Platforms",
    "meta_ads_overview.dim.age_band": "Age band",
    "meta_ads_overview.pareto_by_dim": "Spend & CPR by {dim}",
    "meta_ads_overview.gender.men": "Men",
    "meta_ads_overview.gender.women": "Women",
    "meta_ads_overview.gender.all": "All",
    # La figure fusionnée et la comparaison lisible (2026-09-21).
    "meta_ads_overview.axis_volume": "Spend (€) · clicks",
    "meta_ads_overview.compare_caption": "Campaigns are on the Y axis: a vertical axis "
                                         "reads a long name without rotating it, and this "
                                         "account carries some 90 characters long. Each "
                                         "column has its own scale — a budget in euros "
                                         "and a CPR with three decimals do not share a "
                                         "frame. Sorted by spend: **the CPR on the right "
                                         "reads against the budget on the left**, which "
                                         "is the only way to see whether what you funded "
                                         "most is also what costs least.",
    # R146 — la série nomme le clic sortant.
    "meta_ads_overview.cpr_series": "CPR (€ per outbound click)",
}
