"""EN catalog for the onboarding view."""

EN = {
    # Step 1 — Welcome
    "onboarding.welcome_title": "🎵 Welcome to streaMLytics!",
    "onboarding.admin_preview": (
        "🔧 **Admin account.** Landing on this page automatically only arms for an "
        "**artist** account whose setup is unfinished — an admin has no `artist_id`, "
        "so no setup. You see this page exactly as an artist sees it, but you will "
        "never be brought here on your own.\n\n"
        "To replay the whole journey, sign in with the **sandbox** account: that is "
        "the tenant made for it."
    ),
    "onboarding.pick_action": "👉 Tick what you want to set up now",
    "onboarding.pick_hint": "You do not have to connect everything. The rest will wait in the **API Credentials** tab, later, inside the app.",
    "onboarding.trial_offer": "🎁 **Premium free for 1 month** (30 days), until **{date}**.\n\nAfter that your account returns to **Free**: you keep your data, your connections and your exports. You lose **🚀 Road to Algo** (Discover Weekly trigger predictions), **revenue forecasts** and the **Meta × Spotify cross-analyses**.",
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
    # Step 2 — Credentials
    "onboarding.matrix_legend":
        "**Set up**: the identifier is entered. **Responds**: the platform "
        "answered us. **Data**: figures have arrived.",
    "onboarding.status_unavailable": (
        "⚠️ Could not read your connection status ({err}). The list below may show "
        "“not connected” by mistake — retry in a moment before reconfiguring anything."
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
    # Les lignes de valeur et de piège par plateforme ont été retirées de l'écran le
    # 2026-09-04 — « on ne garde uniquement les sections à cocher ». Elles vivent
    # désormais là où elles servent : le guide de chaque onglet pour le piège, la
    # colonne pour la valeur. `onboarding.need` reste : son appelant est l'écran
    # d'attente après inscription, où il n'y a rien d'autre à faire que rassembler
    # ses identifiants.
    "onboarding.locked_platform": "🔒 {icon} **{label}** — *Available on the {plan} plan*",
    "onboarding.back": "← Back",
    "onboarding.next_finish": "Next: Finish →",
    # Step 3 — Ready
    "onboarding.go_dashboard": "🏠 Go to dashboard →",
    # Sidebar progress
    "onboarding.steps_header": "### Steps",
    "onboarding.step1": "1. Welcome & pick",
    "onboarding.step2": "2. Where you stand",
    # The four numbered blocks of the welcome step
    "onboarding.b1_title": "1. streaMLytics in brief",
    "onboarding.brief_1": "**All your data in one place, pulled every day, "
                          "automatically** — Spotify, Instagram, Meta Ads, YouTube, "
                          "SoundCloud, Apple Music. Your credentials are encrypted; "
                          "you never re-enter them.",
    "onboarding.brief_2": "**Spotify algorithm predictions** — when a track is likely "
                          "to trigger Discover Weekly or Release Radar, from machine "
                          "learning models trained on your own data.",
    "onboarding.brief_3": "**Marketing campaign optimisation (Instagram Ads, Meta "
                          "Ads)** — linking what you spend on promotion to what it "
                          "actually produces in streams.",
    "onboarding.figure_mine": "📈 **Your own figures**",
    "onboarding.b0_title": "0. Your language",
    "onboarding.b0_help": "It applies to the whole app and to your PDF guide. "
                          "We remember it: you only pick it once.",
    "onboarding.b2_title": "2. Your welcome offer",
    "onboarding.b2_after": "Below: what you keep for ever (Free), and what you lose "
                           "after the month if you do not go Premium. **Your data stays "
                           "yours either way** — nothing is deleted, and the CSV export "
                           "stays free.",
    "onboarding.enter_app": "🏠 Go to the app →",
    "onboarding.keep_landing": "Show this page on login until my setup is complete",
    "onboarding.keep_landing_unsaved": "⚠️ Preference not saved — try again later.",
    "onboarding.setup_complete": "✅ Your setup is complete ({done}/{total}). "
                                 "This page will no longer open on login.",
    "onboarding.setup_progress": "Setup: **{done}/{total}** — until it is complete, "
                                 "login brings you back here.",

    "onboarding.feat_meta_budget": (
        "+ 💶 **How much to put back on which campaign** — scale up, hold or cut, "
        "campaign by campaign, from the cost per listen gained"
    ),
    "onboarding.status_title": "📋 Where you stand",
    "onboarding.pick_first_time": (
        "The minutes shown are **first-time** effort. After that, everything updates on its own."
    ),
    # Les trois colonnes du sélecteur — le geste, pas le goût.
    "onboarding.col.quick": "⭐ Start here",
    "onboarding.col.longer": "A little longer",
    "onboarding.col.csv": "By file (CSV)",
}
