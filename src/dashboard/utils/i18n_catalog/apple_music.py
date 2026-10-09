"""EN strings for the Apple Music view."""

EN = {
    "apple_music.top10_title": "Top 10 — cumulative streams · total {n}",
    "apple_music.top_hover": '%{y}<br>Streams: %{x:,.0f}<br>⚡ Shazams: %{customdata[0]:,.0f}<extra></extra>',
    "apple_music.shazams_title": "⚡ Shazams · total {n}",
    "apple_music.shazams_hover": "%{y}<br>⚡ Shazams: %{x:,.0f}<extra></extra>",
    "apple_music.pace_up": "↗ speeding up ({p:+.0%})",
    "apple_music.pace_down": "↘ slowing down ({p:+.0%})",
    "apple_music.pace_start": "↗ taking off",
    "apple_music.pace_flat": "→ steady",
    "apple_music.pace_plays": "Streams / 30 days",
    "apple_music.pace_shazams": "Shazams / 30 days",
    "apple_music.pace_hover": "≈ %{y:,.0f} / 30 d<br>+%{customdata[0]:,.0f} over %{customdata[1]} d<extra></extra>",
    "apple_music.daily_growth": "📈 A title's pace",
    "apple_music.song_select": "🔍 Track (latest release by default)",
    "apple_music.nothing_in_window": "No Apple Music reading for **{song}** over this window. The latest one is from **{last}** — widen the window, or drop a more recent export.",
    "apple_music.not_enough_history": "📉 Only one reading for this track: it takes two export drops to measure a gain.",
    "apple_music.select_prompt": "👈 Select a song — or import Apple Music CSVs several days in a row.",
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
