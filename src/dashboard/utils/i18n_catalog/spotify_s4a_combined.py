"""EN strings for the Spotify & Spotify for Artists view."""

EN = {
    # ── L'ALERTE DE DIVERGENCE (2026-09-23) ────────────────────────────────────
    # La figure ne trace plus QU'UNE courbe d'abonnés, parce que les deux sources se
    # recouvrent sur 32 jours sans jamais s'ecarter de plus d'un abonne. Cette phrase
    # est la CONDITION de cette fusion : elle est muette tant qu'elles s'accordent, et
    # elle parle a l'artiste — seul a pouvoir relancer un import — quand elles derivent.
    "spotify_s4a_combined.followers_diverge": (
        "\u26a0\ufe0f The two follower readings no longer agree: **{e}** apart on "
        "**{j}** (tolerated: {tol}). The curve below shows only one \u2014 check the "
        "CSV import and the API collection before relying on it."),
    # ── La figure d'engagement (2026-09-22) : une seule, trois séries ──────────
    # Les abonnés sont un NIVEAU quotidien, les deux autres des FLUX mensuels : d'où
    # l'axe secondaire, et d'où ces deux libellés d'axe qui nomment la NATURE de ce
    # qu'ils portent plutôt que son unité.
    "spotify_s4a_combined.monthly_flow": "Per month",
    # Le trait distingue les deux sources (plein = API quotidienne, pointillé = CSV qui
    # s'arrête au dernier import) ; le libellé les nomme.

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

    # §3 — momentum
    "spotify_s4a_combined.momentum_header": "🔥 What is moving right now",
    "spotify_s4a_combined.no_recent": "No track measured over the last {n} imported days.",
    "spotify_s4a_combined.lifetime": "Lifetime total",
    "spotify_s4a_combined.recent_window": "last {n} measured days",
    "spotify_s4a_combined.pi_tag": "PI {v}",

    # The drawer
    "spotify_s4a_combined.detail_header": "🎸 The track and your audience",
    "spotify_s4a_combined.song_panel": "The chosen track",
    "spotify_s4a_combined.engagement_panel": "Saves, playlists and followers — whole artist",
    "spotify_s4a_combined.select_song": "Track",
    "spotify_s4a_combined.streams_per_day": "Streams / day",
    "spotify_s4a_combined.pi_series": "Popularity index (0-100)",
    "spotify_s4a_combined.pi_axis": "Popularity index",
    "spotify_s4a_combined.pi_missing": "No popularity index over this period: this track "
                                       "has no confirmed Spotify link, or the API has "
                                       "not read it yet. Linking happens in **🔗 "
                                       "Cross-platform mapping**.",
    "spotify_s4a_combined.saves": "Saves",
    "spotify_s4a_combined.playlist_adds": "Playlist adds",
    "spotify_s4a_combined.followers": "Followers",
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
