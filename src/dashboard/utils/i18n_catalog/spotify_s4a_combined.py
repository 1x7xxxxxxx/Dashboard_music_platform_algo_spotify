"""EN strings for the Spotify & Spotify for Artists view."""

EN = {
    "spotify_s4a_combined.title": "🎵 Spotify & Spotify for Artists",

    # §0 — the clocks
    "spotify_s4a_combined.clocks": "ⓘ **{n}** tracks measured, the most recent up to "
                                   "**{d}**. The Spotify for Artists CSV is imported "
                                   "around a release: each track therefore has its own "
                                   "end date, and a missing measurement is not a "
                                   "missing stream.",

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
    "spotify_s4a_combined.releases_caption": "Compared over their **first {h} days**, "
                                             "the shortest measured series in the "
                                             "selection. Measurement available per "
                                             "release — {detail}.",
    "spotify_s4a_combined.pre_release": "↩︎ {n} stream(s) dated the **day before** a "
                                        "release are not in these curves: Spotify "
                                        "publishes at midnight in the earliest time "
                                        "zone, and the report dates in another.",

    # §2 — audience
    "spotify_s4a_combined.audience_header": "👥 Am I gaining listeners, or do the same "
                                            "ones replay?",
    "spotify_s4a_combined.no_audience": "No audience report imported. Import it from "
                                        "**📂 Add my Spotify for Artists & Apple "
                                        "figures**.",
    "spotify_s4a_combined.kpi_listeners": "👥 Listeners (last complete month)",
    "spotify_s4a_combined.kpi_ratio": "🔁 Streams per listener-day",
    "spotify_s4a_combined.listener_days": "Listener-days",
    "spotify_s4a_combined.ratio_short": "Streams / listener-day",
    "spotify_s4a_combined.ratio_axis": "× per listener-day",
    "spotify_s4a_combined.audience_caption": "**Listener-days**: one unique listener "
                                             "counted once per day of listening — "
                                             "someone who returns on ten days counts "
                                             "ten times. The lower panel therefore says "
                                             "how often people listen, not how many "
                                             "people listen. When it falls at steady "
                                             "volume, the audience renews without "
                                             "becoming loyal.",

    # §3 — momentum
    "spotify_s4a_combined.momentum_header": "🔥 What is moving right now",
    "spotify_s4a_combined.no_recent": "No track measured over the last {n} imported days.",
    "spotify_s4a_combined.lifetime": "Lifetime total",
    "spotify_s4a_combined.recent_window": "last {n} measured days",
    "spotify_s4a_combined.momentum_caption": "Solid bar: the **last {n} measured days** "
                                             "(up to {d}). Grey bar: the total since "
                                             "release.",
    "spotify_s4a_combined.momentum_excluded": "**{k} track(s) excluded**: no measurement "
                                              "in this window.",

    # §4 — the ads pointer
    "spotify_s4a_combined.ads_header": "💸 When should I run ads again?",
    "spotify_s4a_combined.ads_body": "The link between ad spend and streams lives on "
                                     "**🎵 META x Spotify** — budget, results and "
                                     "streams on one time axis. This page does not "
                                     "repeat it: two definitions of the same figure "
                                     "always end up diverging.",
    "spotify_s4a_combined.goto_meta": "🎵 Open META x Spotify",

    # The drawer
    "spotify_s4a_combined.detail_header": "🎸 Track detail",
    "spotify_s4a_combined.select_song": "Track",
    "spotify_s4a_combined.streams_per_day": "Streams / day",
    "spotify_s4a_combined.detail_caption": "Series started at the **first stream** "
                                           "({d}), not at the first day of the file: "
                                           "Spotify exports the account timeline and "
                                           "writes 0 there before the release.",
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
}
