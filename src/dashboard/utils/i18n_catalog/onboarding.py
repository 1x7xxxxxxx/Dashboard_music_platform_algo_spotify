"""EN catalog for the onboarding view."""

EN = {
    # Step 1 — Welcome
    "onboarding.welcome_title": "🎵 Welcome to streaMLytics!",
    "onboarding.in_brief": "#### streaMLytics in brief\n\n**1. All your data in one place, pulled every day, automatically** — Spotify, Instagram, Meta Ads, YouTube, SoundCloud, Apple Music. Your credentials are encrypted; you never re-enter them.\n\n**2. Spotify algorithm predictions** — when a track is likely to trigger Discover Weekly or Release Radar, and how many streams to expect, from machine learning models trained on your data.\n\n**3. Campaign optimisation** — by linking what you spend on promotion to what it actually produces in streams.",
    "onboarding.pick_action": "👉 Tick what you want to set up now",
    "onboarding.pick_hint": "You do not have to connect everything. The rest will wait in the **API Credentials** tab, later, inside the app.",
    "onboarding.trial_offer": "🎁 **Premium free for 1 month** (30 days), until **{date}**.\n\nAfter that your account returns to **Free**: you keep your data, your connections and your exports. You lose **🚀 Road to Algo** (Discover Weekly trigger predictions), **revenue forecasts** and the **Meta × Spotify cross-analyses**.",
    "onboarding.roadmap_title": "🗺️ Your setup, step by step",
    "onboarding.roadmap_body": "**1. You pick your platforms** · ≈1 min\n→ on the next step, tick whatever you want to connect.\n\n**2. You enter your credentials** · ≈{mins} min for the two recommended ones ({names})\n→ every platform has its own illustrated guide, in the Credentials API tab.\n\n**3. Collection runs tonight** · 0 min\n→ your first charts are there tomorrow morning, then every day.",
    "onboarding.roadmap_partial": "You can stop after a single platform and come back whenever you like — nothing is lost, and each platform you add enriches the others.",
    "onboarding.guide_also_mailed": "You also received it attached to the welcome e-mail — here it is if you prefer to grab it from here.",
    "onboarding.welcome_body": "Your account has been created with the **{plan}** plan. "
                               "Here is what your current plan includes:",
    "onboarding.feat_algo": "+ 🚀 **Know whether a track will trigger Discover Weekly** — before you spend on promotion",
    "onboarding.feat_revenue": "+ 📈 **What your streams will earn** next month",
    "onboarding.feat_meta_x": "+ 🔀 **Which euro of ads produced which streams**",
    "onboarding.feat_spotify": "🎵 Spotify + Spotify for Artists",
    "onboarding.feat_distributors": "💰 Distributors (iMusician, DistroKid…)",
    "onboarding.feat_export_csv": "⬇️ CSV export — a spreadsheet file (Excel-style) with your raw data",
    "onboarding.feat_pdf_weekly": "+ 📄 Your filterable PDF report — on demand, and mailed to you every week",
    "onboarding.feat_creatives": "+ 🎨 **Which creative costs least** per stream gained",
    "onboarding.your_plan": " ← *your plan*",
    "onboarding.upgrade_to": "Upgrade to {tier} →",
    "onboarding.next_data": "Next: Set up my data →",
    # Step 2 — Credentials
    "onboarding.matrix_header": "#### 📋 Where you stand, platform by platform",
    "onboarding.matrix_legend":
        "**Set up**: the identifier is entered. **Responds**: the platform "
        "answered us. **Data**: figures have arrived.",
    "onboarding.creds_title": "🔑 Where do you want to start?",
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
    # The four numbered blocks of the welcome step
    "onboarding.b0_title": "0. Your language",
    "onboarding.b0_help": "It applies to the whole app and to your PDF guide. "
                          "We remember it: you only pick it once.",
    "onboarding.b2_title": "2. Your welcome offer",
    "onboarding.b2_after": "Below: what you keep for ever (Free), and what you lose "
                           "after the month if you do not go Premium. **Your data stays "
                           "yours either way** — nothing is deleted, and the CSV export "
                           "stays free.",
    "onboarding.b3_title": "3. Your getting-started guide",
    "onboarding.download_guide_fr": "🇫🇷 Guide en français (PDF)",
    "onboarding.download_guide_en": "🇬🇧 Guide in English (PDF)",
    "onboarding.roadmap_per_platform": "**What each platform costs you, first time:**",
    # Landing choice — the way out, and the right not to come back
    "onboarding.enter_app": "🏠 Go to the app →",
    "onboarding.keep_landing": "Show this page on login until my setup is complete",
    "onboarding.keep_landing_unsaved": "⚠️ Preference not saved — try again later.",
    "onboarding.setup_complete": "✅ Your setup is complete ({done}/{total}). "
                                 "This page will no longer open on login.",
    "onboarding.setup_progress": "Setup: **{done}/{total}** — until it is complete, "
                                 "login brings you back here.",
}
