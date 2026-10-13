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
    "meta_x_spotify.tile_spend": "💸 Spend",
    "meta_x_spotify.tile_streams": "🎵 Streams over the window",
    "meta_x_spotify.tile_cost_per_stream": "🎯 Cost per stream",
    "meta_x_spotify.tile_cps_help": "Spend ÷ streams on the **days the campaign paid** — "
                                    "not on the displayed window: dividing 31 days of "
                                    "spend by two years of listening would give a price "
                                    "that describes nothing. Not to be confused with "
                                    "Meta's CPR, which is the price of a RESULT (a click, "
                                    "a landing-page view) and never of a listen.",
    "meta_x_spotify.tile_conversion": "🔁 Streams per result",
    "meta_x_spotify.tile_conv_help": "Streams ÷ results, over the paid days. How many "
                                     "listens for one billed click.",
    "meta_x_spotify.insta_line": "📸 **Instagram**: {f} follower(s) ({d} over the "
                                 "window) — of the **whole account**, not of this "
                                 "campaign: everything you post feeds it. Context, not "
                                 "a result.",
    "meta_x_spotify.insta_none": "📸 **Instagram**: no follower reading over this window.",

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
    "meta_x_spotify.funnel_caption": "**% of the step before**: out of 100 people at the step above, how many reach this one. **€ each**: the budget divided by the step's volume — what ONE click, ONE visit cost. The arrival on the smart link is measured by « {src} », the most complete source available.",
    "meta_x_spotify.funnel_lp_note": '⚠️ The Meta pixel counts only **{lp}** page views for **{capi}** events returned by the CAPI: the pixel UNDERCOUNTS, it does not measure a later step.',
    "meta_x_spotify.countries_header": "🌍 Where the euro buys the most listens",
    "meta_x_spotify.countries_none": "No country breakdown on this ad account.",
    "meta_x_spotify.c_cost": "€ per listen",
    "meta_x_spotify.best_country": "🏆 **{pays}** is your best ratio: **{c:.3f} € per "
                                   "listen** ({s:,.0f} € spent, {e:,.0f} listens). The "
                                   "worst is **{pp}** at **{cc:.3f} €** — **{ratio:.0f}×** "
                                   "more expensive for the same listen. Only countries "
                                   "above **{plancher:.0f} €** of spend enter this "
                                   "ranking: below that, a good ratio proves nothing.",
    "meta_x_spotify.countries_caption": "⚠️ **The listens do not come from Spotify.** The "
                                        "Spotify for Artists export gives no country "
                                        "breakdown: the only count in the product is the "
                                        "**distributor's** (iMusician), which aggregates "
                                        "every platform and arrives with an accounting "
                                        "statement's delay. The spend comes from Meta. "
                                        "Bars: the cost of one listen, cheapest on the "
                                        "left; line: the CPR. ⚠️ in grey: under 50 € "
                                        "spent, too little to conclude.",
    # R195 — the listener verdict, moved from the Spotify page
    "meta_x_spotify.funnel_gain_note": '🎧 The **streams gained** are compared with the average of the {n} days before ({b} streams/day): a rise that would have happened without the ad is counted too, and one visitor streams many times — hence « streams per click », not a %.',
    "meta_x_spotify.funnel_no_gain": "No « streams gained » step: it needs at least {n} days of streams recorded before the campaign, and a measurable rise.",
    "meta_x_spotify.abs_apple_none": "🎎 **Apple Music / Shazam** — no Apple reading for this track (or no confirmed Apple link in **🔗 Cross-platform mapping**).",
    "meta_x_spotify.abs_apple_late": "🎎 **Apple Music / Shazam** — this track's Apple readings start on **{d}**, after this window.",
    "meta_x_spotify.abs_apple_sparse": "🎎 **Apple Music / Shazam** — readings exist over this window, but more than a day apart: a gap between two readings is not a daily quantity. Import the Apple export every campaign day for it to be drawn here.",
    "meta_x_spotify.eng_header": "| Engagement (artist) | {n} days before, per day | During, per day | Change |",
    "meta_x_spotify.eng_title": "**📣 Beyond streams — what the campaign moved**",
    "meta_x_spotify.eng_caption": "« — » = not measured over the period (at least {n} days recorded before the campaign). Before / during comparison: a rise that would have happened without the ad is counted too.",
    "meta_x_spotify.eng_listeners": "Listeners / day",
    "meta_x_spotify.eng_saves": "Saves / day",
    "meta_x_spotify.eng_playlist_adds": "Playlist adds / day",
    "meta_x_spotify.eng_followers_level": "Spotify followers gained / day",
    "meta_x_spotify.eng_ig_followers": "Instagram followers gained / day",
    "meta_x_spotify.funnel_treasury": "💶 Over this campaign's months ({a} → {b}): **{rev}** of net revenue (all tracks, paid with a delay), **{tot}** of spend in total, of which **{sp}** for this campaign over the window.",
    "meta_x_spotify.shazam_lag_thin": "🎎 Shazam → streams: not enough days measured together ({n} needed). Export « yesterday » from Apple Music for Artists every day of the campaign.",
    "meta_x_spotify.shazam_lag": "🎎 Shazam → streams: a day's Shazams best match the streams **{lag} day(s) later** (correlation {c}, over {n} days). A correlation is not a cause: a release or a playlist lifts both.",
    "meta_x_spotify.funnel_rate_note": "💶 Revenue = streams gained × **{r} €**, your revenue per stream measured on the distributor's sales.",
    "meta_x_spotify.pair_header": "⚖️ Two campaigns, two funnels",
    "meta_x_spotify.pair_none": "No spend recorded.",
    "meta_x_spotify.pair_caption": "Each campaign over its own dates, from the first to the last euro spent. CPM = cost of 1,000 impressions, CPC = cost of one click on the ad, CPR = cost of one outbound click to the platforms.",
    "meta_x_spotify.c_cpr": "CPR (€/outbound click)",
    "meta_x_spotify.c_hover": "%{x}<br>%{y:.4f} € per listen<br>%{customdata[0]:,.0f} € spent · %{customdata[1]:,.0f} listens<extra></extra>",
}
