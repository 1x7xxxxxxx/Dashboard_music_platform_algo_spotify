"""EN catalog for the onboarding view."""

EN = {
    # Step 1 — Welcome
    "onboarding.welcome_title": "🎵 Welcome to streaMLytics!",
    "onboarding.welcome_body": "Your account has been created with the **{plan}** plan. "
                               "Here is what your current plan includes:",
    "onboarding.feat_revenue": "+ 📈 Revenue forecasts",
    "onboarding.feat_creatives": "+ 🎨 Meta Creatives & CPR",
    "onboarding.your_plan": " ← *your plan*",
    "onboarding.upgrade_to": "Upgrade to {tier} →",
    "onboarding.next_data": "Next: Set up my data →",
    # Step 2 — Credentials
    "onboarding.creds_title": "🔑 Where do you want to start?",
    "onboarding.creds_body": (
        "**You do not have to connect everything.** Tick what you want to set up "
        "now — the rest will wait in **API Credentials**."
    ),
    "onboarding.status_unavailable": (
        "⚠️ Could not read your connection status ({err}). The list below may show "
        "“not connected” by mistake — retry in a moment before reconfiguring anything."
    ),
    "onboarding.reco_banner": (
        "⭐ **Recommended to start: {names}** — in {mins} min you see where your "
        "streams come from *and* whether your audience follows. That pair is what "
        "lets you decide something; the rest refines it."
    ),
    "onboarding.already_connected": " — ✅ already connected",
    "onboarding.reco_tag": " — ⭐ recommended",
    "onboarding.effort": " · ≈{mins} min",
    "onboarding.need": "You will need: {need}",
    "onboarding.configure_selection": "Set up my selection ({n}) → ≈{mins} min",
    "onboarding.ready_focus": (
        "Your selection: **{names}** (≈{mins} min). The Credentials page is waiting "
        "with the guide for each — and will tell you whether the connection really "
        "brings data back."
    ),
    "onboarding.go_configure": "🔑 Connect my selection →",
    # Per-platform value / caveat lines (dynamic keys: onboarding.value.* / .caveat.*)
    "onboarding.value.spotify": (
        "Where your streams come from: algorithmic playlists, radio, search — "
        "so where to push your next release."
    ),
    "onboarding.value.instagram": (
        "Whether your audience really follows: followers, reach and the posts that "
        "convert, set against your streaming peaks."
    ),
    "onboarding.value.soundcloud": (
        "Plays, likes and reposts per track — the fastest signal on a track taking off."
    ),
    "onboarding.value.youtube": (
        "Views, likes and comments per video — useful to arbitrate video vs audio-only."
    ),
    "onboarding.value.meta": (
        "What each euro of ads returns in streams — connect it only if you run campaigns."
    ),
    "onboarding.value.apple_music": "Plays and Shazams on Apple, alongside Spotify.",
    "onboarding.caveat.instagram": (
        "⚠️ a **Business or Creator** account linked to a Facebook Page — a personal "
        "account returns no statistics at all."
    ),
    "onboarding.caveat.soundcloud": (
        "⚠️ your tracks must be **public**: a profile with no public track returns nothing."
    ),
    "onboarding.caveat.youtube": (
        "⚠️ if your music is distributed, it is usually the **“… - Topic”** channel "
        "you need, not your personal one."
    ),
    "onboarding.caveat.meta": (
        "⚠️ your ad account must be **shared** with the platform's Business Manager "
        "(asset sharing) — otherwise zero data."
    ),
    "onboarding.locked_platform": "🔒 {icon} **{label}** — *Available on the {plan} plan*",
    "onboarding.back": "← Back",
    "onboarding.next_finish": "Next: Finish →",
    # Step 3 — Ready
    "onboarding.ready_title": "🎉 You're all set!",
    "onboarding.ready_body": "Your dashboard is ready. You can configure your credentials "
                             "at any time from **API Credentials** in the navigation.",
    "onboarding.go_dashboard": "🏠 Go to dashboard →",
    "onboarding.configure_creds": "🔑 Configure credentials",
    "onboarding.tip": "💡 Tip: launch data collection from the "
                      "**Launch ALL collections** button in the sidebar.",
    # Sidebar progress
    "onboarding.steps_header": "### Steps",
    "onboarding.step1": "1. Welcome",
    "onboarding.step2": "2. Data",
    "onboarding.step3": "3. Ready!",
}
