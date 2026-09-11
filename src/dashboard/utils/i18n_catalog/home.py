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
    "home.freshness_api_hint": "Nothing to do: it runs on its own every morning, Paris time.",
    "home.freshness_csv": "📂 You upload these",
    "home.freshness_csv_hint": "These sources only move when a file is dropped — no API gives them to us.",
    "home.freshness_every_day": "every day at {h}",
    "home.freshness_on_upload": "on every upload",
    "home.streams_header": "🎧 Total streams",
    "platform_chart.caption_period": (
        "Plays **{unit}**, platform by platform. A gap in {shape} means no "
        "measurement {when} — not zero plays."),
    "platform_chart.caption_cumulative": (
        "Running total **since the start of the period**, platform by platform. "
        "A break in {shape} means no measurement — not a counter falling back."),
    "platform_chart.too_thin": (
        "{label} is not drawn: only **{measured} reading(s)**, and an area needs two. "
        "Its figures stay in the table below."),
    "platform_chart.coarsened": (
        "**{asked}** gives a single point over this period — an area needs at least "
        "two. Showing **{used}**. 🎎 Apple Music only exists at the Yearly step: widen "
        "the period to see it again."),
    "platform_chart.too_coarse": (
        "{label} does not appear at this step: none of its {unit}s is measured on "
        "enough days to make an honest total. Pick a finer step to see it."),
    "platform_chart.gaps_unstacked": (
        "Over {total} {unit}, some platforms were not measured everywhere ({who}). "
        "Their line stops there — a blank, never a zero: a zero would say \"no "
        "plays\"."),
    "platform_chart.gaps": (
        "Over {total} {unit}, some platforms were not measured everywhere ({who}). "
        "Their area stops there; the others carry on, so the total for those {unit} is "
        "lower — no play was lost."),
    "home.trend_mode": "Display",
    "home.mode_cumulative": "Cumulative",
    "home.mode_absolute": "Per period",
    "home.mode_share": "Share of each platform",
    "home.mode_facets": "Each on its own scale",
    "home.trend_share_hint": (
        "A platform can be invisible without being absent: if one carries most of the "
        "total, the others fall below one pixel. **Each on its own scale** gives every "
        "platform its own panel, and makes the smallest one readable."),
    "home.trend_step": "Step",
    "home.step_auto": "Automatic",
    "home.step_week": "Weekly",
    "home.step_year": "Yearly",
    "home.trend_apple_hint": (
        "🎎 **Apple Music** only appears at the **Yearly** step: its exports are period "
        "totals, not daily figures. Spreading one over 365 days would invent a value "
        "nobody measured."),
    "home.trend_sources": "Sources shown",
    "home.trend_sources_legend": "👆 Click a platform in the legend to hide it.",
    "home.trend_sources_ph": "All sources",
    "home.trend_title": "All your platforms, one screen",
    "home.trend_discarded": (
        "⏸️ Plays measured but **not chartable**: {parts}. They happened between two "
        "collections more than a day apart — we know how many, never on which day. "
        "Pinning them to a date would invent a spike."),
    "home.trend_no_series": (
        "Not enough history yet to draw a trend: it takes at least two consecutive "
        "days of collection on one platform."),
    # Onboarding tracker
    "home.matrix_caption": "Per platform — hover a box for the detail:",
    "home.onboarding_creds": "🔑 Configure API credentials",
    "home.onboarding_s4a": "📂 Upload a Spotify for Artists CSV",
    "home.onboarding_apple": "🍎 Upload an Apple Music CSV",
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
