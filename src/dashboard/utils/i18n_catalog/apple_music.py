"""EN strings for the Apple Music view."""

EN = {
    "apple_music.overview": "📊 Overview",
    "apple_music.kpi_streams": "▶️ Total Streams (Cumulative)",
    "apple_music.kpi_shazams": "⚡ Total Shazams (Cumulative)",
    "apple_music.top_header": "🏆 Top Songs (Cumulative)",
    "apple_music.top10_title": "Top 10 — cumulative streams at the last reading",
    "apple_music.top_hover": '%{y}<br>Streams: %{x:,.0f}<br>⚡ Shazams: %{customdata[0]:,.0f}<extra></extra>',
    "apple_music.shazams_title": "⚡ Shazams — same titles, same order",
    "apple_music.shazams_hover": "%{y}<br>⚡ Shazams: %{x:,.0f}<extra></extra>",
    "apple_music.daily_growth": "📈 Streams & Shazams over time",
    "apple_music.song_select": "🔍 Track (latest release by default)",
    "apple_music.nothing_in_window": "No Apple Music reading for **{song}** over this window. The latest one is from **{last}** — widen the window, or drop a more recent export.",
    "apple_music.not_enough_history": "📉 Only one reading for this track: it takes two export drops to measure a gain.",
    "apple_music.select_prompt": "👈 Select a song — or import Apple Music CSVs several days in a row.",
    "apple_music.error": "❌ Error: {err}",
    # La série d'un titre — cumul en haut, gain entre relevés en bas (2026-09-21).
    "apple_music.cumulative_panel": "Cumulative at each reading",
    "apple_music.gain_panel": "Gained between two readings",
    "apple_music.shazams": "Shazams",
    "apple_music.gain_plays": "Streams gained",
    "apple_music.gain_shazams": "Shazams gained",
    "apple_music.gain_label": "+{n} / {d} d",
    "apple_music.gain_hover": "%{y:,.0f} stream(s) gained over %{customdata} day(s)<extra></extra>",
    "apple_music.gain_sh_hover": "%{y:,.0f} Shazam(s) gained<extra></extra>",
    "apple_music.series_title": "{song} · {label}",
    "apple_music.series_caption": "**{n} reading(s)** over the window. An Apple export is "
                                  "dropped by hand: readings are not daily, and the gap "
                                  "between two runs from **{mini} to {maxi} days** here. "
                                  "Every bar therefore carries its own span — one gain is "
                                  "only comparable to another over an equal span.",
    # R351 — deux sorties alignées sur J0 (2026-10-04).
    "apple_music.launches_header": "⚡ Shazams since release — two releases compared",
    "apple_music.launches_none": "No release date known for your Apple Music tracks: the "
                                 "comparison is anchored on release day. Dates come from "
                                 "Spotify for Artists — link your tracks in **🔗 Mapping "
                                 "cross-plateforme**.",
    "apple_music.launch_a": "Release (latest by default)",
    "apple_music.launch_b": "Compare with",
    "apple_music.launches_no_reading": "No Apple Music reading covers these tracks since "
                                       "their release: drop an \"all time\" export to see "
                                       "them here.",
    "apple_music.launches_caption": "J0 = each track's release day, so two releases from "
                                    "different years read side by side. Each point is a "
                                    "CUMULATIVE reading: the track's Shazams since release. "
                                    "The hollow point at J0 is 0 by construction (no "
                                    "Shazam before release). Between two readings the line "
                                    "joins two measures — it is not a daily rate. This "
                                    "chart does not follow the period selector below.",
    "apple_music.launches_single": "Only one dated release: two are needed to compare.",
    "apple_music.launch_hover": "D+%{x} · %{y:,.0f} Shazam(s) since release<extra></extra>",
    "apple_music.launch_x": "Days since release (D0)",
    "apple_music.launch_y": "Cumulative Shazams since D0",
}
