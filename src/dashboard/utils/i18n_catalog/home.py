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
    "home.freshness_caption": (
        "🔄 **API** sources (Spotify, YouTube, SoundCloud, Instagram, Meta Ads): collected "
        "**automatically every day** for each artist. **File** sources (Spotify for Artists, "
        "Apple Music, distributors): updated **on each CSV import** (folder watched every 15 min)."
    ),
    "home.streams_header": "🎧 Total streams",
    "home.total_all_platforms": "🎧 Total streams across all platforms",
    "platform_chart.too_thin": (
        "{label} is not in the stack: measured on **{measured} day(s) out of {total}**, "
        "it would break the band everywhere. Its figures stay in the table below."),
    "platform_chart.gaps": (
        "White areas are **{missing} day(s) out of {total}** where at least one "
        "platform was not measured. We prefer a blank to a zero: a zero would say "
        "\"no plays\"."),
    "home.apple_no_window": (
        "Apple Music has no daily series: each CSV upload is one dated reading, and the "
        "change is measured between two readings. You have **{n}** so far — the next "
        "upload on another date will fill this in. \"Since the beginning\" shows the total."),
    "home.ig_delta": "over the period",
    "home.ig_no_change": "change: not enough readings",
    "home.trend_step": "Step",
    "home.step_auto": "Automatic",
    "home.step_week": "Weekly",
    "home.step_year": "Yearly",
    "home.trend_apple_hint": (
        "🎎 **Apple Music** only appears at the **Yearly** step: its exports are period "
        "totals, not daily figures. Spreading one over 365 days would invent a value "
        "nobody measured."),
    "home.trend_sources": "Sources shown",
    "home.trend_sources_ph": "All sources",
    "home.trend_title": "All your platforms, one screen",
    "home.trend_caption": (
        "**Daily** plays, platform by platform, over the last 90 days. A gap in a "
        "line means we have no measurement that day — not zero plays."),
    "home.trend_no_series": (
        "Not enough history yet to draw a trend: it takes at least two consecutive "
        "days of collection on one platform."),
    "home.ig_followers": "📸 Instagram Followers",
    # Onboarding tracker
    "home.matrix_caption": "Per platform — hover a box for the detail:",
    "home.onboarding_creds": "🔑 Configure API credentials",
    "home.onboarding_s4a": "📂 Upload a Spotify for Artists CSV",
    "home.onboarding_apple": "🍎 Upload an Apple Music CSV",
    "home.onboarding_run": "🚀 Run your first data collection",
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
