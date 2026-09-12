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
    "platform_chart.not_yet_collected": "not collected yet — from {since}",
    "platform_chart.collected_since": "{label} measured since {since}",
    "platform_chart.week_of": "the week of {d}",
    "platform_chart.day_of": "{d}",
    "platform_chart.recap_title": "Over the period",
    "platform_chart.recap_platform": "Platform",
    "platform_chart.recap_total": "Total",
    "platform_chart.recap_measured": "Measured",
    "platform_chart.recap_all": "Total",
    "platform_chart.recap_other": "Other platforms",
    "platform_chart.recap_over_period": "Over the period",
    "platform_chart.recap_unit": "Unit",
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
