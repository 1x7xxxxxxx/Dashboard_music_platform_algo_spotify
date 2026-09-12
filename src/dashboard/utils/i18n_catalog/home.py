"""EN catalog for the home view."""

EN = {
    # First day: four zeros say "nothing", not "not yet"
    "home.no_data_yet": (
        "🕐 **Your first numbers are not here yet — that is normal.**\n\n"
        "Collection runs **every morning between 9 and 10 am** (Paris time) and fills "
        "this page on its own. You have nothing to do.\n\n"
        "Do not want to wait for tomorrow? The **🚀 Run ALL collections** button in the "
        "sidebar brings your numbers back in ~2 minutes."
    ),
    "home.no_data_hint": (
        "If nothing arrives after a collection, the **🚦 Onboarding health** page says "
        "which source is not answering, and why."
    ),
    "home.launching": "Launching collections…",
    "home.launched": "🚀 Collection launched — your first numbers arrive in "
                     "~2 minutes. Reload the page to see them.",
    "home.launch_refused": "❌ {n} collection(s) refused: {why}",
    "home.launch_unavailable": "⚠️ Launching is not available here. Use the "
                               "**🚀 Run ALL collections** button in the sidebar.",
    "home.title": "🎵 streaMLytics — Music platform dashboard",
    "home.freshness_header": "📡 Data freshness",
    "home.freshness_api": "🔄 Collected automatically",
    "home.freshness_csv": "📂 You upload these",
    "home.freshness_every_day": "every day at {h}",
    "home.freshness_on_upload": "on every upload",
    "home.streams_header": "🎧 Total streams",
    "platform_chart.too_thin": (
        "{label} is not drawn: only **{measured} reading(s)**, and an area needs two. "
        "Its figures stay in the table below."),
    "platform_chart.coarsened": (
        "**{asked}** gives a single point over this period — an area needs at least "
        "two. Showing **{used}**. 🎎 Apple Music only exists at the Yearly step: widen "
        "the period to see it again."),
    "platform_chart.too_coarse": (
        "{label} does not appear at this step: none of its {unit} is measured on "
        "enough days to make an honest total. Pick a finer step to see it."),
    "home.trend_mode": "Display",
    "home.mode_cumulative": "Cumulative",
    "home.mode_absolute": "Per period",
    "home.mode_share": "Share of each platform",
    "home.mode_facets": "Each on its own scale",
    "home.trend_step": "Step",
    "home.step_day": "Daily",
    "home.step_week": "Weekly",
    "home.step_month": "Monthly",
    "home.step_year": "Yearly",
    "home.trend_apple_hint": (
        "🎎 **Apple Music** only appears at the **Yearly** step: its exports are period "
        "totals, not daily figures. Spreading one over 365 days would invent a value "
        "nobody measured."),
    "home.trend_sources": "Sources shown",
    "platform_chart.unmeasured": "▨ No measurement",
    "platform_chart.no_data_hover": "No data collected for this period",
    "platform_chart.recap_all": "Drawn total",
    "platform_chart.recap_metrics": "Indicators",
    # Les trois métriques dérivées ajoutées le 2026-09-12, et les unités de pas
    # qu'elles nomment. « Periods measured » garde le mot « periods » et non
    # « days » : la ligne compte des SEAUX au grain affiché, pas des journées.
    "home.metric_top_share": "🥇 Leading platform",
    "home.metric_top_share_help": (
        "🥇 the platform with the largest share of the period, and its share of the "
        "streams DRAWN — Apple is excluded, its series only exists at yearly step"),
    "home.metric_measured": "📅 Periods measured",
    "home.metric_measured_help": (
        "📅 how many {unit} had at least one platform collected, out of the whole "
        "window — the rest are the hatched bands on the chart"),
    "home.metric_vs_prev": "↔️ vs previous period",
    "home.metric_vs_prev_help": (
        "↔️ change against the window of the SAME LENGTH immediately before this "
        "one — nothing is shown if it was never measured, a “+100 %” against "
        "nothing is not growth"),
    "home.step_days": "days",
    "home.step_weeks": "weeks",
    "home.step_months": "months",
    "home.step_years": "years",
    # Tuiles + métriques dérivées du récapitulatif (2026-09-12)
    "home.total_all_platforms": "🎧 Total streams, all platforms",
    "home.apple_no_window": (
        "Apple Music only reports a total per CSV upload: it cannot be split by "
        "period. Pick « Since the beginning » for its total."),
    "home.ig_is_a_headcount": (
        "A follower HEADCOUNT, not a play count: it cannot be split by period and "
        "is not part of the total above. The change over the period is in the table."),
    "home.metric_best_day": "📈 Best day",
    "home.metric_best_week": "📈 Best week",
    "home.metric_best_month": "📈 Best month",
    "home.metric_best_step": "📈 Best point",
    "home.metric_cost_per_stream": "💸 Cost per stream",
    "home.metric_cost_per_stream_help": (
        "💸 cost per stream = Meta spend over the period ÷ streams over the period "
        "(all platforms, not only the ones the ads targeted)"),
    "home.metric_best_cpr": "🎯 Best CPR",
    "home.metric_best_cpr_help": (
        "🎯 best CPR = the period's campaign with the LOWEST cost per result, "
        "followed by the budget it spent — without it, a very good cost on £18 "
        "reads as repeatable"),
    "home.metric_best_algo": "🔮 Predicted trigger prob.",
    "home.metric_best_algo_help": (
        "🔮 probability PREDICTED by the model that the best-placed track enters an "
        "algorithmic playlist — this is not an observed rate: no outcome has been "
        "recorded yet"),
    "platform_chart.not_yet_collected": "not collected yet — from {since}",
    "platform_chart.collected_since": "{label} measured since {since}",
    "platform_chart.week_of": "the week of {d}",
    "platform_chart.day_of": "{d}",
    "platform_chart.recap_platform": "Platform",
    "platform_chart.recap_total": "Total",
    "platform_chart.recap_other": "Other platforms",
    "home.recap_unit_plays": "plays",
    "home.recap_unit_followers": "followers",
    "home.trend_sources_ph": "All sources",
    "home.trend_discarded": (
        "⏸️ Plays measured but **not chartable**: {parts}. They happened between two "
        "collections more than a day apart — we know how many, never on which day. "
        "Pinning them to a date would invent a spike."),
    "home.trend_nothing_in_window": (
        "No measurement over this period. The latest one is from **{last}** — upload "
        "a recent export, or widen the window to see the history again."),
    "home.trend_no_series": (
        "Not enough history yet to draw a trend: it takes at least two consecutive "
        "days of collection on one platform."),
    # Onboarding tracker
    "home.matrix_caption": "Per platform — hover a box for the detail:",
    "home.onboarding_creds": "🔑 Set up the APIs",
    "home.onboarding_csv": "📂 Upload my files",
    "home.onboarding_mapping": "🔗 Confirm the cross-platform mapping",
    "home.onboarding_playlists": "📝 Enter my playlist adds (S4A)",
    "home.onboarding_playlists_why": (
        "Sharpens the predictive models for Spotify playlist pickups "
        "(Discover Weekly, Radio, Release Radar)."),
    "home.onboarding_pdf": "📄 Generate my first PDF report",
    "home.onboarding_done_header": "#### ✅ Getting started — setup complete",
    "home.onboarding_done": "All getting-started steps are complete. 🎉",
    "home.onboarding_ticks_on_action": "A step is ticked when the action is **done**, not when the page is opened.",
    "home.onboarding_progress": "#### 🚀 Getting started — {done}/{total} steps completed",
    # Pipeline status
    "home.dag_header": "🚦 Pipeline status",
    "home.airflow_unreachable": "Airflow API unreachable — start Docker.",
    "home.no_dags": "No DAGs found. Check that Airflow is running.",
    "home.never_run": "never run",
    "home.dag.data_quality_check": "Data quality",
    "home.display_error": "Display error: {err}",
}
