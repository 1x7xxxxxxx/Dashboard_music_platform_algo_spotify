"""EN strings for the cross-platform campaign impact view (route key `meta_x_spotify`)."""

EN = {

    # Campaign + window pickers
    "meta_x_spotify.no_campaign": "No Meta Ads campaign on this account. Connect it "
                                  "from **🔑 API credentials + CSV imports**.",
    "meta_x_spotify.window": "Window",
    "meta_x_spotify.pick_one_campaign": "The funnel reads one campaign at a time: pick one "
                                        "in the filter bar above.",
    "meta_x_spotify.win_tail": "📈 Campaign + {n} d (afterglow)",
    "meta_x_spotify.win_camp": "🎯 The campaign only",
    "meta_x_spotify.win_all": "♾️ Up to today",

    # The linked track
    "meta_x_spotify.linked_track": "🎵 Track linked on Spotify: **{track}**",
    "meta_x_spotify.linked_unconfirmed": "🎵 Track linked on Spotify: **{track}** — but "
                                         "with no CONFIRMED link, so its streams cannot "
                                         "be attached. Confirm it in **🔗 Cross-platform "
                                         "mapping**.",
    "meta_x_spotify.no_linked_track": "⚠️ No track linked on Spotify for this campaign. "
                                      "The association is made in **🔗 Cross-platform "
                                      "mapping**.",

    # The cross-platform tiles — the two middle ones existed nowhere before

    # The figure — one key per plotted column (built as t(f"…series_{col}"))

    # What is NOT on the figure, and why
    "meta_x_spotify.absences_header": "ℹ️ What is not on the figure, and why ({n})",
    "meta_x_spotify.abs_unlinked": "🎵 **Spotify streams** — this campaign has no track "
                                   "attached by a confirmed link. Linking happens in "
                                   "**🔗 Cross-platform mapping**.",
    "meta_x_spotify.abs_streams": "🎵 **Spotify streams** — the track is linked, but no "
                                  "Spotify for Artists import covers this window. The CSV "
                                  "is imported around a release.",
    "meta_x_spotify.abs_pi": "🎵 **Popularity index** — the daily reading starts on "
                             "**{d}**, after this campaign ended ({fin}).",
    "meta_x_spotify.abs_pi_never": "🎵 **Popularity index** — no reading for this account.",
    "meta_x_spotify.abs_hyp": "📱 **Hypeddit** — no statistic for this campaign over this "
                              "window (first reading on record: {d}).",
    "meta_x_spotify.abs_hyp_never": "📱 **Hypeddit** — no statistic for this campaign.",

    # Shared empty state
    "meta_x_spotify.no_data": "No data over this window.",

    # Les onglets, le funnel corrigé et le croisement pays (2026-09-21).
    "meta_x_spotify.funnel_header": '🔽 From budget to revenue — the whole journey',
    "meta_x_spotify.funnel_thin": "Not enough measured steps to draw a journey.",
    "meta_x_spotify.src_capi": "Hypeddit CAPI",
    "meta_x_spotify.src_hyp": "Hypeddit entry",
    "meta_x_spotify.src_pixel": "Meta pixel",
    "meta_x_spotify.countries_header": "🌍 Where the euro buys the most listens",
    "meta_x_spotify.countries_none": "No country breakdown on this ad account.",
    "meta_x_spotify.c_cost_src": "€ per listen (iMusician listens, all platforms)",
    "meta_x_spotify.c_cost": "€ per listen",
    # R195 — the listener verdict, moved from the Spotify page
    "meta_x_spotify.abs_apple_none": "🎎 **Apple Music / Shazam** — no Apple reading for this track (or no confirmed Apple link in **🔗 Cross-platform mapping**).",
    "meta_x_spotify.abs_apple_late": "🎎 **Apple Music / Shazam** — this track's Apple readings start on **{d}**, after this window.",
    "meta_x_spotify.abs_apple_sparse": "🎎 **Apple Music / Shazam** — readings exist over this window, but more than a day apart: a gap between two readings is not a daily quantity. Import the Apple export every campaign day for it to be drawn here.",
    "meta_x_spotify.shazam_lag_thin": "🎎 Shazam → streams: not enough days measured together ({n} needed). Export « yesterday » from Apple Music for Artists every day of the campaign.",
    "meta_x_spotify.shazam_lag": "🎎 Shazam → streams: a day's Shazams best match the streams **{lag} day(s) later** (correlation {c}, over {n} days). A correlation is not a cause: a release or a playlist lifts both.",
    "meta_x_spotify.pair_header": "⚖️ Two campaigns, two funnels",
    "meta_x_spotify.pair_none": "No spend recorded.",
    "meta_x_spotify.c_hover": "%{x}<br>%{y:.4f} € per listen<br>%{customdata[0]:,.0f} € spent · %{customdata[1]:,.0f} listens",
    "meta_x_spotify.c_hover_cpr": "<br>CPR (€/outbound click): %{customdata[2]:.3f} €<extra></extra>",
}
