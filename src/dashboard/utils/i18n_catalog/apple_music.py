"""EN strings for the Apple Music view."""

EN = {
    "apple_music.no_data": "No Apple Music reading yet: import your Apple Music for Artists export from **Import CSV** to see your tracks and the track to push.",
    "apple_music.shazam_rate_header": "🎯 The track to push",
    "apple_music.shazam_rate_empty": "No track has {n} Apple plays yet: the rate would be noise.",
    "apple_music.shazam_rate_hover": "%{y}<br>%{x:,.0f} Shazams / 1,000 plays<br>%{customdata[0]:,.0f} Shazams · %{customdata[1]:,.0f} plays<extra></extra>",
    "apple_music.shazam_rate_title": "Shazams per 1,000 plays — {song} gets searched the most",
    "apple_music.shazam_rate_left_out": "{n} track(s) under {m} Apple plays, not ranked.",
    "apple_music.top10_title": "Top 10 — cumulative streams · total {n}",
    "apple_music.top_hover": '%{y}<br>Streams: %{x:,.0f}<br>⚡ Shazams: %{customdata[0]:,.0f}<extra></extra>',
    "apple_music.shazams_title": "⚡ Shazams · total {n}",
    "apple_music.shazams_hover": "%{y}<br>⚡ Shazams: %{x:,.0f}<extra></extra>",
    "apple_music.error": "❌ Error: {err}",
    # La série d'un titre — cumul en haut, gain entre relevés en bas (2026-09-21).
    # R351 — deux sorties alignées sur J0 (2026-10-04).
    "apple_music.launches_header_cross": "⚡ Shazams since release",
    "apple_music.launches_none": "No release date known for your Apple Music tracks: the "
                                 "comparison is anchored on release day. Dates come from "
                                 "Spotify for Artists — link your tracks in **🔗 Mapping "
                                 "cross-plateforme**.",
    "apple_music.launch_pick": "Releases to compare",
    "apple_music.launch_pick_none": "Pick at least one release.",
    "apple_music.launches_no_reading": "No Apple Music reading covers these tracks since "
                                       "their release: drop an \"all time\" export to see "
                                       "them here.",
    "apple_music.launch_hover": "D+%{x} · %{y:,.0f} Shazam(s) since release<extra></extra>",
    "apple_music.launch_x": "Days since release (D0)",
    "apple_music.launch_y": "Cumulative Shazams since D0",
}
