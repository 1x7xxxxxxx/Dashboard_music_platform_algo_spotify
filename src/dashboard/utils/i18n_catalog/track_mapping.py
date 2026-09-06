"""EN catalog for the track_mapping view."""

EN = {
    "track_mapping.no_reference": "No title reference found. Import your S4A CSVs then "
                                  "rebuild the reference below.",
    "track_mapping.rebuild_button": "🔄 Rebuild title reference",
    "track_mapping.rebuilt": "{n} reference title(s) rebuilt.",
    # Tabs
    # Suggestions tab
    # Les titres vus sur une plateforme et rattachés à aucune sortie. Ils
    # disparaissaient en silence — c'est la réponse à « pourquoi ce morceau
    # n'apparaît-il nulle part ? », qui n'existait pas.
    "track_mapping.orphans_header": (
        "🕳️ {n} title(s) seen on a platform and linked to none of your releases"),
    "track_mapping.orphans_help": (
        "Nothing to do if these are edits or mixes. If one of them really is one of "
        "your releases, it is missing from your Spotify for Artists « 12 months » "
        "export — re-import it."),
    "track_mapping.orphan_no_reference": (
        "no reference release — import your S4A « 12 months » export"),
    "track_mapping.orphan_version": (
        "version « {v} »: none of your releases carries that marker"),
    "track_mapping.orphan_no_match": (
        "does not resemble any of your releases — most likely an edit, a mix or "
        "another artist's track"),
    "track_mapping.col_platform": "Platform",
    "track_mapping.col_platform_title": "Title on the platform",
    "track_mapping.col_why": "Why it is not suggested",
    "track_mapping.nothing_to_map": "✅ Nothing to map here (everything is already linked or rejected).",
    "track_mapping.legend": "🟢 ≥80% · 🟡 50–80% · 🔴 <50%. Tick **Accept** (or **Reject** "
                            "to stop suggesting), then save.",
    "track_mapping.save_links_button": "💾 Save links",
    "track_mapping.links_saved": "{n} link(s) saved.",
    # Campaigns tab
    # Dataframe column display labels
    "track_mapping.col_confidence": "Confidence",
    "track_mapping.col_accept": "Accept",
    "track_mapping.col_reject": "Reject",
    "track_mapping.col_track": "Track",
    "track_mapping.col_release": "Release",
    # Unified overview tab (coverage grid + Meta campaigns + suggestions)
    "track_mapping.coverage_header": "🗺️ Cross-platform coverage (recap)",
    "track_mapping.coverage_legend": "✅ = platform linked · “·” = not linked. (Meta campaigns "
                                     "live in the **📣 Meta campaigns** tab.)",
    "track_mapping.suggest_header": "🔎 Suggestions to review",
}
