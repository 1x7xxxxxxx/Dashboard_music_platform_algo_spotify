"""EN strings for the Meta Ads overview view."""

EN = {
    "meta_ads_overview.one_campaign": "Only one campaign spent over the chosen period: widen the period to compare your campaigns.",
    "meta_ads_overview.streams_day": "Spotify streams / day",
    "meta_ads_overview.streams_axis": "Streams",
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
    "meta_ads_overview.waves_header": "🌊 How long the effect of an ad wave lasts",
    "meta_ads_overview.waves_caption": "A WAVE groups the campaigns that overlap or follow each other within 28 days: separately, they cannot be told apart. A wave often coincides with a release: this is an association, not proof that the ad caused these streams.",
    "meta_ads_overview.engagement": "##### ❤️ Engagement",
    "meta_ads_overview.total_interactions": "⚡ Total Interactions",
    "meta_ads_overview.spotify_clicks": "Hypeddit clicks",
    "meta_ads_overview.spend_eur": "Spend (€)",
    "meta_ads_overview.time_evolution": "⏳ Spend, clicks and cost — on one clock",
    "meta_ads_overview.daily_dynamics": "Daily Dynamics",
    "meta_ads_overview.no_time_data": "No time-series data.",
    "meta_ads_overview.summary_table": "🗃️ Summary Table",
    # La figure fusionnée et la comparaison lisible (2026-09-21).
    "meta_ads_overview.axis_volume": "Spend (€) · clicks",
    # R146 — la série nomme le clic sortant.
    "meta_ads_overview.cpr_series": "CPR (€ per outbound click)",
    # R301 — the curve around each wave (R282 B).
    "meta_ads_overview.curve_title": "Streams around each wave — how long the effect lasts",
    "meta_ads_overview.curve_x": "days since the wave began (0 = first euro)",
    "meta_ads_overview.curve_y": "streams / day (100 = the 28 days before)",
    "meta_ads_overview.curve_caption": (
        "100 = the average of the 28 days before the wave. A curve that rises BEFORE day 0 "
        "is a release, not the ads. {d} wave(s) with no measured baseline (under 10 streams "
        "a day before it) are not drawn: an index there would mean nothing."),
    # R350 — two campaigns on the day-0 clock.
    "meta_ads_overview.pair_head": "##### ⏱️ The two campaigns on the same clock",
    "meta_ads_overview.pair_caption": (
        "Day 0 = the first day each campaign spent. The whole life of each campaign, "
        "whatever the date filter; a pause day counts 0. The CPC is the cumulative spend "
        "divided by the cumulative clicks."),
}
