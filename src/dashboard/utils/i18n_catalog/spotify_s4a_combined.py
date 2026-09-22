"""EN strings for the Spotify & Spotify for Artists view."""

EN = {

    # §1 — releases at equal age
    "spotify_s4a_combined.releases_header": "🚀 My releases, at equal age",
    "spotify_s4a_combined.pick_releases": "Releases to compare",
    "spotify_s4a_combined.pick_at_least_one": "Pick at least one release.",
    "spotify_s4a_combined.no_releases": "No release is linked to a Spotify for Artists "
                                        "track. Linking happens in **🔗 Cross-platform "
                                        "mapping**.",
    "spotify_s4a_combined.goto_mapping": "🔗 Link my tracks",
    "spotify_s4a_combined.days_since_release": "Days since release",
    "spotify_s4a_combined.cumulative_streams": "Cumulative streams",

    # §2 — audience
    "spotify_s4a_combined.no_audience": "No audience report imported. Import it from "
                                        "**📂 Add my Spotify for Artists & Apple "
                                        "figures**.",
    "spotify_s4a_combined.listener_days": "Listener-days",
    "spotify_s4a_combined.ratio_short": "Streams / listener-day",
    "spotify_s4a_combined.ratio_axis": "× per listener-day",

    # §3 — momentum
    "spotify_s4a_combined.momentum_header": "🔥 What is moving right now",
    "spotify_s4a_combined.no_recent": "No track measured over the last {n} imported days.",
    "spotify_s4a_combined.lifetime": "Lifetime total",
    "spotify_s4a_combined.recent_window": "last {n} measured days",
    "spotify_s4a_combined.pi_tag": "PI {v}",

    # The drawer
    "spotify_s4a_combined.detail_header": "🎸 Track detail",
    "spotify_s4a_combined.select_song": "Track",
    "spotify_s4a_combined.streams_per_day": "Streams / day",
    "spotify_s4a_combined.detail_caption": "Series started at the **first stream** "
                                           "({d}), not at the first day of the file: "
                                           "Spotify exports the account timeline and "
                                           "writes 0 there before the release.",
    "spotify_s4a_combined.pi_series": "Popularity index (0-100)",
    "spotify_s4a_combined.pi_axis": "Popularity index",
    "spotify_s4a_combined.pi_missing": "No popularity index over this period: this track "
                                       "has no confirmed Spotify link, or the API has "
                                       "not read it yet. Linking happens in **🔗 "
                                       "Cross-platform mapping**.",
    "spotify_s4a_combined.pi_clock": "The **popularity index** is read by the API every "
                                     "day (up to {pi_d}); the streams come from the CSV, "
                                     "imported around a release (up to {s_d}). A stream "
                                     "curve that stops is an import that stopped, not a "
                                     "track that died.",
    "spotify_s4a_combined.saves_header": "💾 Saves and playlist adds",
    "spotify_s4a_combined.saves": "Saves",
    "spotify_s4a_combined.playlist_adds": "Playlist adds",
    "spotify_s4a_combined.followers_header": "🔔 Followers",
    "spotify_s4a_combined.followers": "Followers",
    "spotify_s4a_combined.followers_caption": "Two sources, two clocks: the CSV carries "
                                              "the deep history and stops at the last "
                                              "import; the API reads every day but does "
                                              "not go back before it was switched on. "
                                              "They are never spliced together.",
    "spotify_s4a_combined.source.s4a_csv": "Spotify for Artists CSV",
    "spotify_s4a_combined.source.spotify_api": "Spotify API",

    # Shared empty states
    "spotify_s4a_combined.no_data": "No data available.",
    "spotify_s4a_combined.no_data_period": "No data for this period.",

    # Le bilan annuel, rapatrié de « Data Wrapped » (2026-09-21).
    "spotify_s4a_combined.wrapped_header": "🎁 My yearly recap (Spotify Wrapped for Artists)",
    "spotify_s4a_combined.wrapped_intro": "These figures are in no API: Spotify only "
                                          "publishes them once a year, in your Wrapped for "
                                          "Artists. Enter them here and the year-over-year "
                                          "curve builds itself.",
}
