"""EN strings for the cross-platform campaign impact view (route key `meta_x_spotify`)."""

EN = {
    "meta_x_spotify.title": "🔀 My campaigns' impact — every platform",

    # Campaign + window pickers
    "meta_x_spotify.choose_campaign": "Pick the campaign",
    "meta_x_spotify.no_campaign": "No Meta Ads campaign on this account. Connect it "
                                  "from **🔑 API credentials + CSV imports**.",
    "meta_x_spotify.window": "Window",
    "meta_x_spotify.win_tail": "📈 Campaign + {n} d (afterglow)",
    "meta_x_spotify.win_camp": "🎯 The campaign only",
    "meta_x_spotify.win_all": "♾️ Up to today",
    "meta_x_spotify.window_caption": "{f} — campaign from {a} to {b}, {n} day(s) on air.",

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
    "meta_x_spotify.budget_eur": "Budget (€)",
    "meta_x_spotify.budget_hover": "Budget: %{customdata:,.2f} €<extra></extra>",
    "meta_x_spotify.series_results": "Results",
    "meta_x_spotify.series_impressions": "Impressions",
    "meta_x_spotify.series_reach": "Reach (people)",
    "meta_x_spotify.series_cpr_display": "CPR (€)",
    "meta_x_spotify.series_streams": "Streams / day",
    "meta_x_spotify.series_popularity": "Popularity index",
    "meta_x_spotify.series_hypeddit_visits": "Hypeddit visits",
    "meta_x_spotify.series_hypeddit_clicks": "Clicks to stores",
    "meta_x_spotify.spend_ends": "spend ends",
    "meta_x_spotify.chart_title": "Detailed analysis: {campaign}",
    "meta_x_spotify.index_axis": "Index (base 100 = start of window)",
    "meta_x_spotify.index_caption": "Series indexed (base 100 = first non-zero day of the "
                                    "window): that is what lets €, listens and a 0-100 "
                                    "index share one axis. Absolute values on hover. "
                                    "**Colour says the platform** — Meta blue, Spotify "
                                    "green, Hypeddit cyan — **and the stroke says the "
                                    "series**: a stroke is still telling when the colours "
                                    "are not.",

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
    "meta_x_spotify.abs_apple": "🎎 **Apple Music / Shazam** — not plottable here by "
                                "construction: the Apple export is a **cumulative "
                                "snapshot per track**, not a daily series. Its totals "
                                "live on **🎎 Apple Music**.",

    # Shared empty state
    "meta_x_spotify.no_data": "No data over this window.",

    # Les onglets, le funnel corrigé et le croisement pays (2026-09-21).
    "meta_x_spotify.tab_impact": "📈 Impact over time",
    "meta_x_spotify.tab_funnel": "🔽 The whole journey",
    "meta_x_spotify.tab_countries": "🌍 By country",
    "meta_x_spotify.funnel_header": "🔽 Meta × Spotify × Hypeddit — the whole journey",
    "meta_x_spotify.funnel_none": "No Meta data over this window.",
    "meta_x_spotify.funnel_thin": "Not enough measured steps to draw a journey.",
    "meta_x_spotify.f_impressions": "Impressions",
    "meta_x_spotify.f_clicks": "Clicks on the ad",
    "meta_x_spotify.f_landing": "Arrivals on the smart link",
    "meta_x_spotify.f_store": "Clicks through to platforms",
    "meta_x_spotify.src_capi": "Hypeddit CAPI",
    "meta_x_spotify.src_hyp": "Hypeddit entry",
    "meta_x_spotify.src_pixel": "Meta pixel",
    "meta_x_spotify.funnel_caption": "The first two steps come from **Meta**, the next "
                                     "two from **Hypeddit**. The arrival on the smart "
                                     "link is measured by « {src} »: the most complete of "
                                     "the three sources available.",
    "meta_x_spotify.funnel_lp_note": "⚠️ The Meta pixel counts only **{lp}** page views "
                                     "for **{capi}** events returned by the CAPI. This is "
                                     "not a contradiction: the pixel must fire on load, "
                                     "the server event need not. The pixel UNDERCOUNTS, "
                                     "it does not measure a later step — stacking one "
                                     "under the other asserted a nesting that is false "
                                     "91 days out of 91.",
    "meta_x_spotify.countries_header": "🌍 Where the euro buys the most listens",
    "meta_x_spotify.countries_none": "No country breakdown on this ad account.",
    "meta_x_spotify.c_spend": "Spend (€)",
    "meta_x_spotify.c_streams": "Listens",
    "meta_x_spotify.c_cost": "€ per listen",
    "meta_x_spotify.c_axis_left": "Spend (€) · listens",
    "meta_x_spotify.c_axis_right": "€ per listen",
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
                                        "The left scale is **logarithmic** — without it, "
                                        "a country at 56,000 listens crushes every other.",
}
