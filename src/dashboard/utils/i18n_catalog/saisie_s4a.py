"""EN catalog for the saisie_s4a view."""

EN = {
    "saisie_s4a.title": "📝 S4A manual entry",
    "saisie_s4a.intro": "**Spotify for Artists only** signals (no API) to enter per track. "
                        "They feed the ML prediction « 🚀 Road to Algo ».",
    "saisie_s4a.invalid_session": "Invalid session.",
    "saisie_s4a.no_tracks": "No track available (S4A timeline is empty).",
    # Fixed grid
    "saisie_s4a.fixed_header": "📊 Playlist adds per window + Discovery Mode",
    "saisie_s4a.fixed_caption": "Enter, per track, the playlist adds as shown in S4A "
                               "(7 days / 28 days / 12 months) and the Discovery Mode state. Bulk save.",
    "saisie_s4a.help_feeds_ml": "Feeds the ML",
    "saisie_s4a.radio_count_label": "📻 Number of songs currently in Spotify Radio",
    "saisie_s4a.radio_count_help": "Per-artist counter shown in S4A. Feeds the ML "
                                   "(HowManySongsDoYouHaveInRadioRightNow feature).",
    "saisie_s4a.nonalgo_help": "Organic streams (search, profile, direct) over 28d — "
                               "excluding Discover Weekly / Release Radar / Radio / autoplay. Feeds the ML.",
    "saisie_s4a.save_grid": "💾 Save grid",
    "saisie_s4a.saved_fixed": "Saved: {pa} playlist values + {dm} Discovery Mode + "
                              "{na} non-algo streams + Radio = {radio}.",
    # Custom grid
    "saisie_s4a.custom_header": "📅 Custom range (e.g. first days post-release)",
    "saisie_s4a.custom_start": "Start",
    "saisie_s4a.custom_end": "End",
    "saisie_s4a.start_before_end": "The start date must precede the end date.",
    "saisie_s4a.save_custom": "💾 Save custom range",
    "saisie_s4a.saved_custom": "Range {start} → {end} saved for {n} tracks.",
    # Shared
    "saisie_s4a.error": "Error: {exc}",
}
