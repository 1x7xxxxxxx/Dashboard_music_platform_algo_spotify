"""EN strings for the Meta × Spotify campaign mapping view."""

EN = {
    "meta_mapping.title": "🔗 Cross-platform mapping",
    "meta_mapping.subtitle": "Link your titles across platforms (Spotify, Apple, SoundCloud, "
                             "YouTube) and map your Meta Ad campaigns to tracks. Automatic "
                             "suggestions + manual entry feed META × Spotify and ROI Breakeven.",
    "meta_mapping.tab_overview": "🎵 Titles & coverage",
    "meta_mapping.tab_campaigns": "📣 Meta campaigns",
    # Auto-suggestions (top section)
    "meta_mapping.auto_header": "🤖 Automatic suggestions (campaign → track)",
    "meta_mapping.auto_done": "✅ All Meta campaigns are already mapped (or none collected).",
    "meta_mapping.auto_legend": "Score = name similarity **and** proximity to the release date. "
                                "Reliability: 🟢 ≥ 80 % · 🟡 50–80 % · 🔴 < 50 % (often a junk "
                                "title: DJ set, other artist). Tick **Associate** then save.",
    "meta_mapping.col_confidence": "Confidence",
    "meta_mapping.col_associate": "Associate",
    "meta_mapping.associate_button": "💾 Save (associate / reject)",
    "meta_mapping.campaigns_saved": "{a} associated, {r} rejected.",
    # Campaign backlog
    "meta_mapping.backlog_header": "📋 Campaign backlog",
    "meta_mapping.bl_campaign": "Campaign",
    "meta_mapping.bl_status": "Status",
    "meta_mapping.bl_track": "Mapped track",
    "meta_mapping.bl_start": "Start",
    "meta_mapping.bl_counts": "✅ {a} associated · 🔴 {r} rejected · ⏳ {p} pending",
    "meta_mapping.tab_existing": "Existing mappings",
    "meta_mapping.tab_add": "Manual add",
    "meta_mapping.no_mappings": "No mappings yet. Use the suggestions above or the "
                                "**Manual add** tab.",
    "meta_mapping.delete_title": "Delete a mapping",
    "meta_mapping.select_delete": "Select mapping to delete",
    "meta_mapping.deleted": "Deleted: {label}",
    # `meta_mapping.no_campaigns` a été retirée le 2026-09-06 : elle portait DEUX
    # phrases françaises différentes selon le site d'appel, et cette traduction n'en
    # servait qu'une. Les cinq clés ci-dessous nomment chacune UNE cause mesurée.
    "meta_mapping.empty_no_identity": (
        "No campaigns: your Meta ad account is not set yet. Go to "
        "**🔑 Credentials API → Meta Ads** and paste your Ad Account ID."),
    "meta_mapping.empty_never_ran": (
        "No campaigns: the Meta collection has never run for you yet. Start it with "
        "**🚀 Launch ALL collections** in the sidebar."),
    "meta_mapping.empty_run_failed": (
        "No campaigns: the last Meta collection failed. Nothing for you to do — "
        "we are looking into it."),
    "meta_mapping.empty_no_campaign": (
        "The Meta collection works, and your ad account holds no campaign. There is "
        "nothing to map until you run an ad — this is normal, not an error."),
    "meta_mapping.empty_elsewhere": (
        "The Meta collection works — your performance figures did arrive. However no "
        "campaign is attached to **this** profile: they belong to the first profile "
        "that declared this ad account. That is by design — a campaign never changes "
        "owner — and it only happens when two profiles share one ad account. Nothing "
        "for you to do."),
    "meta_mapping.empty_sandbox": (
        "No campaign, and that is **expected here**: this profile is the sandbox, and "
        "it declares the same ad account as your main profile. A campaign belongs "
        "permanently to the first profile that collected it — yours are all on your "
        "main profile, with their mapping. The sandbox replays onboarding, not "
        "campaign mapping: for that one, sign in with your main account."),
    "meta_mapping.no_tracks": "No tracks found. Import your S4A CSVs first.",
    "meta_mapping.meta_campaign": "Meta campaign",
    "meta_mapping.spotify_track": "Spotify track",
    "meta_mapping.add_btn": "➕ Add mapping",
    "meta_mapping.mapped": "Mapped **{campaign}** → **{track}**",
}
