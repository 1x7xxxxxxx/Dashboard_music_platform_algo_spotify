"""EN strings for the Meta Ads overview view."""

EN = {
    "meta_ads_overview.one_campaign": "Only one campaign spent over the chosen period: widen the period to compare your campaigns.",
    "meta_ads_overview.scope_period": "**{spend} €** across **{campaigns}** "
                                      "campaign(s), from {start} to {end}.",
    "meta_ads_overview.scope_linked": " **{linked}** campaign(s) are linked to a track: "
                                      "cost per track is readable for those, and only "
                                      "those.",
    "meta_ads_overview.scope_unlinked": " No campaign is linked to a track — so this "
                                        "section answers \"how much did I spend, and who "
                                        "did it reach\", not \"what did this track cost "
                                        "me\". A campaign named like a song is not a link.",
    # Comptes d'agence — déplacés de Credentials vers cette page le 2026-09-05.
    "meta.extra_accounts_title": "➕ Extra ad accounts - for agencies (optional)",
    "meta.extra_accounts_help": (
        "Main account: **{main}** — change it in 🔑 API Credentials. Add the other "
        "accounts to track here, **one per line**."
    ),
    "meta.extra_accounts_field": "Extra accounts",
    "meta.extra_accounts_save": "💾 Save these accounts",
    "meta.extra_accounts_malformed": (
        "❌ Badly formatted account(s): {bad}. Digits only, optionally prefixed with "
        "`act_`, one per line."
    ),
    "meta.extra_accounts_failed": "Could not save — try again in a moment.",
    "meta.extra_accounts_taken": "❌ One of these accounts is already linked to another artist. If this is a mistake, contact the administrator.",
    "meta.extra_accounts_saved": "✅ {n} account(s) tracked.",
    "meta_ads_overview.section": "View",
    # R554 (ADR-033 decision 2) — five sections, read top to bottom.
    "meta_ads_overview.section_chrono": "📈 Timeline",
    "meta_ads_overview.section_funnel": "🛤️ Funnel",
    "meta_ads_overview.section_creas": "🎨 Creatives & settings",
    "meta_ads_overview.section_audiences": "🌍 Audiences",
    "meta_ads_overview.glossary": "📖 The words on this page",
    "meta_ads_overview.unknown": "Unknown",
    "meta_ads_overview.goal_pareto": "🎯 Optimisation goal — spend and cost per outbound click",
    "meta_ads_overview.gloss.clic_sortant": "**Outbound click** — the click that leaves your Hypeddit smart link for a platform (Spotify, Apple…). Hypeddit sends it back to Meta through its CAPI: it is the « result » of the CPR.",
    "meta_ads_overview.gloss.frequence": "**Frequency** — impressions ÷ people reached: how many times, on average, one person saw the ad.",
    "meta_ads_overview.gloss.engagement": "**Engagement** — reactions + comments + shares + saves on the ad.",
    "meta_ads_overview.gloss.etape": "**% of the previous step** — the share of the people at the previous step who reached this one (1.1 % = 11 out of 1,000).",
    "meta_ads_overview.gloss.cout_unitaire": "**Cost per unit** — spend divided by the number at this step (€0.127 per unit = €1 for ~8 clicks).",
    "meta_ads_overview.gloss.cpr": "**CPR** — cost per result: spend ÷ outbound clicks.",
    "meta_ads_overview.section_instagram": "📸 Instagram",
    "meta_ads_overview.title_cross": "🔀 Cross view — Meta × Hypeddit × Spotify × Insta × Shazam × Revenue",
    "meta_ads_overview.global_perf": "### 🚀 Overall Performance",
    "meta_ads_overview.capi_required": (
        "CPR empty: it requires CAPI (server-side events) — no custom "
        "conversion is reported here."),
    # Les six cadres de la performance globale, construits par
    # `t(f"meta_ads_overview.perf.{i}", libellé)`. `_PERF_PANNEAUX` les énumère et
    # `test_the_global_perf_names_every_panel_it_draws` vérifie que chacun a sa clé.
    "meta_ads_overview.perf.0": "Spend (€)",
    "meta_ads_overview.perf.1": "Impressions",
    "meta_ads_overview.perf.2": "Link clicks",
    "meta_ads_overview.perf.3": "CPM (€)",
    "meta_ads_overview.perf.4": "CPC (€)",
    "meta_ads_overview.perf.5": "CPR (€)",
    "meta_ads_overview.engagement": "##### ❤️ Engagement",
    "meta_ads_overview.total_interactions": "⚡ Total Interactions",
    "meta_ads_overview.no_time_data": "No time-series data.",
    "meta_ads_overview.summary_table": "🗃️ Summary Table",
    # La figure fusionnée et la comparaison lisible (2026-09-21).
    # R146 — la série nomme le clic sortant.
    # R301 — the curve around each wave (R282 B).
    # R350 — two campaigns on the day-0 clock.
    "meta_ads_overview.pair_head": "##### ⏱️ The two campaigns on the same clock",
    "meta_ads_overview.pair_caption": (
        "Day 0 = the first day each campaign spent. The whole life of each campaign, "
        "whatever the date filter; a pause day counts 0. The CPC is the cumulative spend "
        "divided by the cumulative clicks."),
    # R555 — the one chronology and the effect of each campaign.
    "meta_ads_overview.timeline_header": "📈 Everything on one clock — ads, streams, audience",
    "meta_ads_overview.timeline_caption": (
        "Click a series in the legend to show or hide it. The orange area is the Meta budget "
        "spent each day (€ axis on the right): where it is, the ads were running. An "
        "**outbound click** is a click on a button of your Hypeddit smart link towards a "
        "streaming platform — the « result » Meta counts — and the **CPR** is the budget "
        "divided by those clicks. Spotify flows are 7-day means; a day not imported stays a "
        "gap."),
    "meta_ads_overview.effect_header": "⏱️ How long the effect of each campaign lasts",
    "meta_ads_overview.effect_caption": (
        "One curve per campaign, set on its first euro (day 0). 100 = the average Spotify "
        "streams of the 28 days before it; the curve tells how many days it stays above. A "
        "curve that rises BEFORE day 0 is a release, not the ads. Two campaigns running at "
        "the same time share the same streams: an association, not proof that each caused "
        "them. {d} campaign(s) with no measured baseline (under 10 streams a day before it) "
        "are not drawn."),
    "meta_ads_overview.effect_x": "days since the campaign's first euro",
    "meta_ads_overview.effect_y": "streams / day (100 = the 28 days before)",
}
