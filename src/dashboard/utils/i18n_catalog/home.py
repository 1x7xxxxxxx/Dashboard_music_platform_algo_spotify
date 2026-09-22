"""EN catalog for the home view."""

EN = {
    # First day: four zeros say "nothing", not "not yet"
    "home.no_data_yet": (
        "🕐 **Your first numbers are not here yet — that is normal.**\n\n"
        "Collection runs **every morning between 9 and 10 am** (Paris time) and fills "
        "this page on its own. You have nothing to do.\n\n"
        "Do not want to wait for tomorrow? The **🚀 Run ALL collections** button in the "
        "sidebar brings your numbers back in ~2 minutes."
    ),
    "home.no_data_hint": (
        "If nothing arrives after a collection, the **🚦 Onboarding health** page says "
        "which source is not answering, and why."
    ),
    "home.launching": "Launching collections…",
    "home.launched": "🚀 Collection launched — your first numbers arrive in "
                     "~2 minutes. Reload the page to see them.",
    "home.launch_refused": "❌ {n} collection(s) refused: {why}",
    "home.launch_unavailable": "⚠️ Launching is not available here. Use the "
                               "**🚀 Run ALL collections** button in the sidebar.",
    "home.freshness_header": "📡 Data freshness",
    "home.freshness_api": "🔄 Collected automatically",
    "home.freshness_csv": "📂 You upload these",
    "home.freshness_every_day": "every day at {h}",
    "home.freshness_on_upload": "on every upload",
    "home.streams_header": "🎧 Total streams",
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
    "home.mode_facets": "Each on its own scale",
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
    "home.tile_last_seen": "Last reading: {d}",
    # Pourquoi la courbe « par période » montre moins que le compteur de la boîte :
    # le compteur est à VIE, nous ne le relevons que depuis une date donnée.
    "home.tile_counter_history": (
        "Lifetime counter. We have been reading this platform since {since}: "
        "**{seen}** since that date. The rest predates our first reading and no date "
        "can carry it — which is why the « per period » curve shows less."),
    # Les trois portes algorithmiques de la dernière sortie (2026-09-12). « Predicted »
    # est porté par le bandeau ET par l'aide : c'est une PRÉDICTION, jamais un taux
    # observé — aucune issue n'a encore été saisie.
    "home.gates_for": "🔮 **Maximum predicted** probabilities for **{song}**",
    "home.gates_age": " · released {n} days ago",
    "home.gate_dw": "🎯 Discover Weekly",
    "home.gate_radio": "📻 Radio",
    "home.gate_rr": "🆕 Release Radar",
    # L'interrupteur du cumulé (2026-09-13), qui remplace la barre de modes.
    "home.trend_cumulative": "Cumulative",
    "home.trend_cumulative_help": (
        "On: the curve only rises and its last point is the period total. Off: each "
        "point is what was gained over that step — useful on a short window, hard to "
        "read over several years where one platform dwarfs the others."),
    "home.gate_help": ("Probability PREDICTED by the model that this track enters "
                       "this algorithmic playlist. It is not an observed rate: no "
                       "outcome has been recorded yet."),
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
    "home.apple_no_window": (
        "Apple Music only reports a total per CSV upload: it cannot be split by "
        "period. Pick « Since the beginning » for its total."),
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
    # Pipeline status
    "home.dag_header": "🚦 Pipeline status",
    "home.airflow_unreachable": "Airflow API unreachable — start Docker.",
    "home.no_dags": "No DAGs found. Check that Airflow is running.",
    "home.never_run": "never run",
    "home.dag.data_quality_check": "Data quality",
    "home.display_error": "Display error: {err}",
    # Le raccourci vers le rapport PDF, remis le 2026-09-22.
    "home.pdf_cta": "📄 Generate my PDF report",
    "home.pdf_help": "Your current numbers, laid out and ready to send.",
    # Sans cadenas : `plan_gate.bouton_vers` le pose lui-même depuis le
    # 2026-09-22. Le laisser ici en afficherait DEUX.
    "home.pdf_locked": "PDF report — included in Premium",
    "home.pdf_locked_help": (
        "Laying out the report is part of the subscription; exporting your raw data "
        "stays free (⬇️ Export CSV)."),
    # ── Les sources non branchées (2026-09-22) ─────────────────────────────
    "home.absence_intro": (
        "These sources are not connected yet — each one adds a piece to your "
        "numbers:"),
    "home.absence_repli": "See the {n} sources to connect, one by one",
}
