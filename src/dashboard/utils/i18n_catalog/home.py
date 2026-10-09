"""EN catalog for the home view."""

EN = {
    # First day: four zeros say "nothing", not "not yet"
    "home.no_data_yet": (
        "🕐 **Your first numbers are not here yet — that is normal.**\n\n"
        "Automatic collection runs **every morning between 5 and 11 am** (Paris time) "
        "and fills this page on its own. You have nothing to do.\n\n"
        "It also starts by itself as soon as you save credentials."
    ),
    "home.no_data_hint": (
        "If nothing arrives after a collection, the **🚦 Onboarding health** page says "
        "which source is not answering, and why."
    ),
    "home.launching": "Launching collections…",
    "home.next_step": "Your next step",
    "home.collection_running": "🔄 {label} — collection running, each platform's state "
                               "is in the sidebar.",
    "home.launched": "🚀 Collection launched — your first numbers arrive in "
                     "~2 minutes. Reload the page to see them.",
    "home.launch_refused": "❌ {n} collection(s) refused: {why}",
    "home.launch_unavailable": "⚠️ Launching is not available here. Collection also "
                               "starts by itself as soon as you save credentials.",
    "home.freshness_header": "📡 Data freshness",
    "home.freshness_api": "🔄 Collected automatically",
    "home.freshness_csv": "📂 You upload these",
    "home.freshness_every_day": "every day at {h}",
    "home.freshness_on_upload": "on every upload",
    "home.streams_header": "🎧 Total streams",
    "platform_chart.counter_arrival": "{p}: {v} lifetime at first reading — not a rise",
    "platform_chart.too_thin": (
        "{label} is not drawn: only **{measured} reading(s)**, and an area needs two. "
        "Its figures stay in the table below."),
    "platform_chart.coarsened": (
        "**{asked}** gives a single point over this period — an area needs at least "
        "two. Showing **{used}**. 🎎 Apple Music only exists at the Yearly step: widen "
        "the period to see it again."),
    "platform_chart.too_coarse": (
        "{label} does not appear at this step: none of its {unit} is measured on "
        "enough days to make an honest total. Pick a finer step to see it."),
    "home.mode_cumulative": "Cumulative",
    "home.mode_absolute": "Per period",
    "home.mode_share": "Share of each platform",
    "home.trend_apple_hint": (
        "🎎 **Apple Music** only appears at the **Yearly** step: its exports are period "
        "totals, not daily figures. Spreading one over 365 days would invent a value "
        "nobody measured."),
    "platform_chart.unmeasured": "▨ No measurement",
    "platform_chart.no_data_hover": "No data collected for this period",
    "platform_chart.recap_metrics": "Indicators",
    # Les trois métriques dérivées ajoutées le 2026-09-12, et les unités de pas
    # qu'elles nomment. « Periods measured » garde le mot « periods » et non
    # « days » : la ligne compte des SEAUX au grain affiché, pas des journées.
    "home.metric_measured": "📅 Periods measured",
    "home.metric_measured_help": (
        "📅 how many {unit} had at least one platform collected, out of the whole "
        "window — the rest are the hatched bands on the chart"),
    "home.step_days": "days",
    "home.step_weeks": "weeks",
    "home.step_months": "months",
    "home.step_years": "years",
    # Les boîtes du 2026-09-12 : Meta Ads dans la rangée des plateformes, et la
    # date du dernier relevé pour une boîte vide.
    "home.tile_meta": "📊 Meta Ads",
    "home.tile_meta_help": (
        "Ad spend over the displayed period, and the campaign with the LOWEST cost "
        "per result along with the budget it consumed."),
    "home.tile_best_cpr": "🎯 CPR {cpr}{budget}",
    # Les trois portes algorithmiques de la dernière sortie. Depuis R421 le chiffre
    # est affiché même au plancher : l'aide dit que c'est une PRÉDICTION, et qu'au
    # plancher elle ne distingue aucun titre.
    "home.gate_dw": "🎯 Discover Weekly",
    "home.gate_radio": "📻 Radio",
    "home.gate_rr": "🆕 Release Radar",
    "home.gate_28d_met": "✅ 28-day target reached",
    "home.gate_28d_gap": "📈 {n} streams / 28 d",
    "home.gate_rr_gap": "📈 {n} streams in {d} d",
    "home.gate_rr_closed": "⛔ first-28-day window over",
    "home.gate_28d_help": ("Below: the streams missing over 28 days to reach the model's "
                           "threshold, and their cost at the best CPR, counting one "
                           "click as one stream. Release Radar only counts the "
                           "release's first 28 days."),
    "home.gates_caption": ("« {song} », your latest release: the highest predicted chance "
                           "to enter each Spotify algorithmic playlist. ⬇️"),
    "home.gate_help_max": ("HIGHEST probability PREDICTED that « {song} », your latest "
                           "release, enters this algorithmic playlist. It is not an "
                           "observed rate. At the model's floor, this figure is the same "
                           "for every track."),
    # L'interrupteur du cumulé (2026-09-13), qui remplace la barre de modes.
    "home.trend_cumulative": "Cumulative",
    "home.trend_cumulative_help": (
        "On: the curve only rises and its last point is the period total. Off: each "
        "point is what was gained over that step, on a logarithmic scale so the "
        "smaller platforms stay readable next to Spotify."),
    # Tuiles + métriques dérivées du récapitulatif (2026-09-12)
    # Shazam sur l'accueil (R106, 2026-09-13) — ADR-025 le met dans le cœur du
    # produit ; il n'était sur aucun écran.
    "home.tile_shazam": "🎧 Shazam",
    # Hypeddit sur l'accueil (2026-09-13) — le maillon « on clique » de la chaîne.
    "home.tile_hypeddit": "📱 Hypeddit",
    "home.tile_hypeddit_volume": "👁️ {v} · 🖱️ {c}",
    "home.tile_hypeddit_help": (
        "Best click-through rate obtained by a Hypeddit link for the latest release: "
        "clicks divided by visits. It covers the whole campaign, not the displayed "
        "period — this figure does not move with the filter."),
    "home.tile_hypeddit_campaign": "Campaign: \u201c{name}\u201d.",
    "home.tile_hypeddit_unlinked": (
        "\u201c{song}\u201d is not attached to any confirmed Hypeddit campaign. The "
        "**🔗 Track mapping** page creates the link."),
    "home.tile_shazam_release": "🆕 Latest release · {n}",
    "home.tile_shazam_help": (
        "Shazams **since the beginning**, read from the Apple Music export. It is a "
        "deposit reading, not a daily quantity: it cannot be split by period, so "
        "this figure does not move with the filter."),
    "home.tile_shazam_release_help": "The second line is the latest release, \u201c{song}\u201d.",
    "home.tile_shazam_unlinked": (
        "\u201c{song}\u201d is not yet matched to an Apple track, so its Shazam count "
        "cannot be isolated. The **🔗 Track mapping** page creates the link."),
    "home.total_all_platforms": "🎧 Total streams, all platforms",
    # Ce que le chiffre-titre additionne réellement (2026-09-13).
    "home.total_composition": (
        "Sum of every measured platform. {parts} are LIFETIME COUNTERS: they carry "
        "everything that precedes our first collection, and that part has no date. "
        "Spotify plays, by contrast, are counted day by day."),
    "home.ig_is_a_headcount": (
        "A follower HEADCOUNT, not a play count: it cannot be split by period and "
        "is not part of the total above. The change over the period is in the table."),
    "platform_chart.not_yet_collected": "not collected yet — from {since}",
    "platform_chart.collected_since": "{label} measured since {since}",
    # Pourquoi ces courbes ne peuvent pas commencer plus tôt (2026-09-13, ADR-024).
    "platform_chart.counter_has_no_prior_history": (
        "{names} — **{counts}** plays precede our first measurement. These platforms "
        "only return a **lifetime counter**: we know how many, never on which day. No "
        "API and no export gives that detail back, so the curve cannot start earlier."),
    "platform_chart.week_of": "the week of {d}",
    "platform_chart.day_of": "{d}",
    "home.trend_discarded": (
        "⏸️ Plays measured but **not chartable**: {parts}. They happened between two "
        "collections more than a day apart — we know how many, never on which day. "
        "Pinning them to a date would invent a spike."),
    "home.trend_nothing_in_window": (
        "No measurement over this period. The latest one is from **{last}** — upload "
        "a recent export, or widen the window to see the history again."),
    "home.trend_no_series": (
        "Not enough history yet to draw a trend: it takes at least two consecutive "
        "days of collection on one platform."),
    # Onboarding tracker
    "home.matrix_caption": "Per platform — hover a box for the detail:",
    "home.onboarding_creds": "🔑 Set up the APIs",
    "home.onboarding_csv": "📂 Upload my files",
    "home.onboarding_mapping": "🔗 Confirm the cross-platform mapping",
    "home.onboarding_playlists": "📝 Enter my playlist adds (S4A)",
    "home.onboarding_playlists_why": (
        "Sharpens the predictive models for Spotify playlist pickups "
        "(Discover Weekly, Radio, Release Radar)."),
    "home.onboarding_pdf": "📄 Generate my first PDF report",
    "home.onboarding_done_header": "#### ✅ Getting started — setup complete",
    "home.onboarding_done": "All getting-started steps are complete. 🎉",
    "home.onboarding_ticks_on_action": "A step is ticked when the action is **done**, not when the page is opened.",
    "home.onboarding_progress": "#### 🚀 Getting started — {done}/{total} steps completed",
    "home.display_error": "Display error: {err}",
    # ── Les sources non branchées (2026-09-22) ─────────────────────────────
    "home.absence_intro": (
        "These sources are not connected yet — each one adds a piece to your "
        "numbers:"),
    "home.absence_repli": "See the {n} sources to connect, one by one",
    # ── Ce que la publicité a appris (`views/home_meta_advice.py`, 2026-09-22) ──
    # R157 : la tuile montre la date de MESURE ; quand la date d'ÉCRITURE rend un
    # verdict DIFFÉRENT sur le même barème, on nomme l'écart. Aucun seuil neuf.
    "home.freshness_written": "collected {d}",
    # Les libellés d'âge de `freshness_status`. Ils étaient en dur, donc ils
    # sortaient en français dans un PDF anglais envoyé par mail (R157).
    "freshness.no_data": "No data",
    "freshness.hours_ago": "{n}h ago",
    "freshness.days_ago": "{n}d ago",
    "alerts.freshness_unreadable": (
        "\u26a0\ufe0f Could not read source freshness \u2014 this is not \u00ab all good \u00bb, it is \u00ab we do not know \u00bb."),
    "home.advice_header": "\U0001F4F1 What your advertising has learned",
    # Les deux états d'un compte qui ne dépense plus. Ils ne se confondent pas : le
    # premier SAIT qu'aucune campagne ne tourne (`meta_campaigns` porte des lignes,
    # aucune ACTIVE), le second ne sait pas (la liste est vide). Affirmer « none is
    # active » sans la liste serait une phrase qu'aucune donnée ne soutient.
    "home.advice_no_active": (
        "\u2705 Your Meta data came through \u2014 and **no campaign is running "
        "today**. The last spending was on **{jour}**, **{depuis} days** ago. So the "
        "figures above describe that campaign, not what is running right now."),
    "home.advice_last_spend_only": (
        "\u2705 Your Meta data came through: the last spending was on **{jour}**, "
        "**{depuis} days** ago. We do not have your campaign list yet, so we cannot "
        "say whether one is still running."),
    "home.advice_no_campaign": (
        "No campaign carries a usable cost per result yet."),
    "home.advice_too_thin": (
        "\u26a0\ufe0f That is measured on too little to make a rule of it \u2014 let it "
        "run, or compare your campaigns in detail."),
    "home.advice_solid": (
        "That is measured on **{depense} \u20ac** of this campaign: enough to rely on."),
    "home.advice_cta": "\U0001F4CA Compare all my campaigns",
    "home.advice_cta_locked": "Compare all my campaigns",
    "home.advice_cta_help": (
        "The per-campaign score, the cheapest age bracket, and which budgets to "
        "raise or cut."),
    "home.advice_cta_locked_help": (
        "The detailed comparison of your campaigns is included in the subscription."),
    "home.money_caveat": (
        "Since the beginning, outside the selected period. The revenue is what you "
        "imported \u2014 distributors and SACEM. The break-even point is computed on "
        "\U0001F4C8 Revenue forecast."),
    "home.money_no_revenue": (
        "You have not uploaded a distributor statement yet: there is no way to say "
        "what this spending brought you."),
    # ── Les trois axes de la publicité (2026-09-22) ────────────────────────
    "home.axe_age": "age bracket",
    "home.axe_pays": "country",
    "home.axe_placement": "ad placement",
    "home.axe_phrase": (
        "On **{axe}**, your best result is **{meilleur}** at {cpr_min} \u20ac per "
        "outbound click, and your worst **{pire}** at {cpr_max} \u20ac. About "
        "**{perte} \u20ac** went above the cheapest cost."),
    # ── R346 : the ad block as metric boxes (2026-10-04) ──────────────────
    "home.box_spend": "Spent on ads",
    "home.box_spend_help": "Over the selected period.",
    "home.box_spend_total": "since the beginning: {v} \u20ac",
    "home.box_back": "Earned back",
    "home.box_back_none": "no statement uploaded",
    "home.box_back_total": "Earned back since the beginning",
    "home.box_back_split": "distributors {d} \u20ac \u00b7 SACEM {s} \u20ac",
    "home.box_cpr": "Best cost / outbound click",
    "home.box_cpr_until": " \u00b7 up to {jour}",
    "home.box_waste": "Paid above the cheapest cost",
    "home.box_waste_sub": "{axe} \u2014 cheapest: {meilleur}",
    "home.axes_detail": "Detail per axis ({n})",
}
