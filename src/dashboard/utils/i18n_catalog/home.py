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
