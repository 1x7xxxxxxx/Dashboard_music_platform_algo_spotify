"""EN strings for « Comparer mes campagnes » (tab of `meta_x_spotify`, R234)."""

EN = {
    "campaign_compare.funnel_head": "**The whole journey, track by track** — from the ad impression to the click to the platforms, comparing up to {n} tracks.",
    "campaign_compare.funnel_pick": "Tracks to compare",
    "campaign_compare.funnel_chains": "Two tools, two chains: a smart-link visit does not always come from an ad click (bio link, shares), so the two sides do not follow each other — each reads top to bottom.",
    "campaign_compare.funnel_dropped": "Step(s) removed: {s} — not measured for one of the tracks, or bigger than the step before.",
    "campaign_compare.funnel_gained": "Streams gained during the track's campaigns (above the 28 days before, outside the journey since a stream does not always come from a click): {g}",
    "campaign_compare.stage_impressions": "Ad impressions",
    "campaign_compare.stage_link_clicks": "Ad clicks",
    "campaign_compare.stage_visits": "Smart-link visits",
    "campaign_compare.stage_store_clicks": "Clicks to the platforms",
    "campaign_compare.chain_meta": "Ad side (Meta)",
    "campaign_compare.chain_hypeddit": "Smart-link side (Hypeddit)",
    "campaign_compare.log_axis": "Volume (log scale: each mark ×10)",
    "campaign_compare.empty": "No campaign to compare on this account.",
    "campaign_compare.head": "**Which campaign bought the cheapest stream?** — streams of "
                             "the linked track during the campaign, above its level over "
                             "the {n} days before.",
    "campaign_compare.c_campaign": "Campaign",
    "campaign_compare.c_track": "Linked track",
    "campaign_compare.c_family": "Objective",
    "campaign_compare.c_spend": "Spend (€)",
    "campaign_compare.c_gained": "Streams gained",
    "campaign_compare.c_cost": "€ / stream gained",
    "campaign_compare.c_lag": "Ad → stream delay",
    "campaign_compare.c_overlap": "Overlaps another",
    "campaign_compare.c_clicks": "Clicks to platforms",
    "campaign_compare.c_per_click": "Streams gained / click",
    "campaign_compare.lag_days": "{n} d",
    "campaign_compare.cohort": "Your **{a}** campaigns bought a gained stream cheaper than "
                               "your **{b}** campaigns: {x} € against {y} € (medians).",
    "campaign_compare.cohort_thin": "Engagement against traffic: comparing needs at least "
                                    "{n} measured campaigns of each kind — you have {e} "
                                    "engagement and {tr} traffic.",
    "campaign_compare.biases": "Two limits, written so they are not forgotten. ⚠️ = another "
                               "campaign pushed the same track during this one or its {n} "
                               "days before: both claim the same streams, and the « before » "
                               "level already contains ads. « — » = no confirmed linked "
                               "track, fewer than 14 measured days before, or no stream "
                               "gained. The delay shows only if spend AND streams varied "
                               "over at least 14 days: a flat-budget campaign has none, and "
                               "that is expected.",
    "campaign_compare.countries": "The country that converts best: **🌍 By country** tab, "
                                  "campaign by campaign.",
    "campaign_compare.tracks_head": "**Which track turns clicks into streams best?** — "
                                    "clicks to platforms (Hypeddit) and streams gained "
                                    "during its campaigns.",
    "campaign_compare.crea_head": "**Which creative brought streams?** — measured when the "
                                  "creative ran ALONE in its campaign: its streams gained "
                                  "are then its own, with no assumed split.",
    "campaign_compare.c_crea": "Creative",
    "campaign_compare.crea_split": "{n} campaign(s) ran several creatives together: their "
                                   "streams cannot be separated by creative. To measure a "
                                   "creative, run it alone in its campaign, or give it its "
                                   "own Hypeddit link.",
    "campaign_compare.tracks_empty": "No Hypeddit link attached to a Spotify track: attach "
                                     "them in **🔗 Cross-platform mapping**.",
}
