"""EN strings for the Meta × Spotify campaign mapping view."""

EN = {
    "meta_mapping.title": "🔗 Cross-platform mapping",
    "meta_mapping.subtitle": "Link your titles across platforms (Spotify, Apple, SoundCloud, "
                             "YouTube) and map your Meta Ad campaigns to tracks. Automatic "
                             "suggestions + manual entry feed META × Spotify and ROI Breakeven.",
    "meta_mapping.tab_tracks": "🎵 Cross-platform titles",
    "meta_mapping.tab_overview": "🎵 Titles & coverage",
    "meta_mapping.tab_campaigns": "📣 Meta campaigns",
    # Auto-suggestions (top section)
    "meta_mapping.auto_header": "🤖 Automatic suggestions (campaign → track)",
    "meta_mapping.auto_no_reference": "No track reference yet — import your S4A CSVs, then "
                                      "rebuild the reference in **🧩 Multi-platform mapping**.",
    "meta_mapping.auto_done": "✅ All Meta campaigns are already mapped (or none collected).",
    "meta_mapping.auto_legend": "Score = name similarity **and** proximity to the release date. "
                                "Reliability: 🟢 ≥ 80 % · 🟡 50–80 % · 🔴 < 50 % (often a junk "
                                "title: DJ set, other artist). Tick **Associate** then save.",
    "meta_mapping.col_confidence": "Confidence",
    "meta_mapping.col_associate": "Associate",
    "meta_mapping.associate_button": "💾 Associate ticked campaigns",
    "meta_mapping.campaigns_associated": "{n} campaign(s) associated.",
    "meta_mapping.tab_existing": "Existing mappings",
    "meta_mapping.tab_add": "Manual add",
    "meta_mapping.no_mappings": "No mappings yet. Use the suggestions above or the "
                                "**Manual add** tab.",
    "meta_mapping.delete_title": "Delete a mapping",
    "meta_mapping.select_delete": "Select mapping to delete",
    "meta_mapping.deleted": "Deleted: {label}",
    "meta_mapping.no_campaigns": "No campaigns found in `meta_campaigns`. Run the Meta Ads DAG first.",
    "meta_mapping.no_tracks": "No tracks found. Import your S4A CSVs first.",
    "meta_mapping.meta_campaign": "Meta campaign",
    "meta_mapping.spotify_track": "Spotify track",
    "meta_mapping.add_btn": "➕ Add mapping",
    "meta_mapping.mapped": "Mapped **{campaign}** → **{track}**",
}
