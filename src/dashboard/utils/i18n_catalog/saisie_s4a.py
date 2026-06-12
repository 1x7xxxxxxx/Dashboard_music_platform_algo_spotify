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
    "saisie_s4a.howto_header": "ℹ️ Where to find these values in Spotify for Artists?",
    "saisie_s4a.howto_nonalgo": "**Non-algo streams (28d)** — per song:\n"
        "Go to **Music → Songs → pick a song → Source of streams**. In the "
        "**“Source of streams”** segmentation, tick **every active source**: "
        "*Artist profile and catalog* · *Listener's playlists and library* · "
        "*Listener's queue*. Enable the **last 28 days** filter, then report the "
        "value shown under **“This period”** here.",
    "saisie_s4a.howto_radio": "**Songs currently in Radio** — per artist:\n"
        "Go to **Music → Playlists**, click **“Custom”** on the **Radio** playlist, "
        "then count the number of songs.",
    "saisie_s4a.radio_count_label": "📻 Number of songs currently in Spotify Radio",
    "saisie_s4a.radio_count_help": "Music → Playlists → “Custom” on the Radio playlist → "
                                   "count the songs. Feeds the ML (HowManySongsDoYouHaveInRadioRightNow).",
    "saisie_s4a.nonalgo_help": "Music → Songs → a song → Source of streams: tick every active "
                               "source + 28-day filter, report “This period”. Excludes "
                               "Discover Weekly / Release Radar / Radio / autoplay. Feeds the ML.",
    "saisie_s4a.save_grid": "💾 Save grid",
    "saisie_s4a.saved_fixed": "Saved: {pa} playlist values + {dm} Discovery Mode + "
                              "{na} non-algo streams + Radio = {radio}.",
    # Realized-outcome grid (training labels)
    "saisie_s4a.outcome_header": "🎯 Realized algorithmic streams (28d) — model training",
    "saisie_s4a.outcome_caption": "Per track, the streams **actually earned** over 28 days via Discover "
                                  "Weekly, Release Radar and Radio. These become the **labels** that teach "
                                  "the model whether it was right (live learning loop, feeds "
                                  "ml_prediction_outcomes).",
    "saisie_s4a.outcome_howto_header": "ℹ️ Where to read DW / RR / Radio streams in Spotify for Artists?",
    "saisie_s4a.outcome_howto": "**Music → Songs → a song → Source of streams**, enable the **last 28 "
                                "days** filter, then report the **Discover Weekly**, **Release Radar** and "
                                "**Radio** rows of the “Source of streams” segmentation. Enter these "
                                "**~4 weeks after** the prediction so the 28-day window is complete — that "
                                "delay is what makes the label honest.",
    "saisie_s4a.outcome_help": "Real Discover Weekly / Release Radar / Radio streams. The 28d feeds the "
                               "model's training labels (thresholds 137 / 130 / 639); the 7d is for tracking.",
    "saisie_s4a.save_outcomes": "💾 Save realized outcomes (7d + 28d)",
    "saisie_s4a.saved_outcomes": "Realized outcomes saved (7d + 28d) for {n} tracks.",
    "saisie_s4a.outcome_custom_header": "📅 Custom range (DW/RR/Radio streams generated)",
    "saisie_s4a.outcome_custom_save": "💾 Save range (algos)",
    "saisie_s4a.outcome_custom_saved": "Range {start} → {end} saved for {n} tracks.",
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
