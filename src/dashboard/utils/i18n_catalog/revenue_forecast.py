"""EN catalog for the revenue_forecast view."""

EN = {
    # ── Mon argent : flux, cumul, point mort (2026-09-21) ────────────────────
    "revenue_forecast.cost_track": "Track concerned (optional)",
    "revenue_forecast.treasury_moved": "The treasury chart (sales, SACEM, spend, cumulated) is on the 💰 Distributors page.",
    "revenue_forecast.artist_forecast_header":
        "My money: what comes in, what goes out, and when I break even",
    "revenue_forecast.artist_forecast_caption": (
        "All your money on one chart: distributors (iMusician, DistroKid), SACEM "
        "royalties, Meta advertising and your release costs. The lower curve "
        "crosses zero the day you break even."),
    "revenue_forecast.no_money_yet": (
        "No money movement on record. Import a sales report from **CSV import**, "
        "or connect Meta in **🔑 API Credentials**."),
    "revenue_forecast.kpi_cumul": "💰 Where I stand overall",
    "revenue_forecast.kpi_cumul_delta": "{r:+,.0f} € in · {d:,.0f} € out",
    "revenue_forecast.kpi_rythme": "📆 My current pace",
    "revenue_forecast.kpi_rythme_delta": "average of the last {n} months",
    "revenue_forecast.kpi_breakeven": "⏳ Break-even",
    "revenue_forecast.be_no_date": "out of reach",
    "revenue_forecast.be_done": (
        "✅ You have broken even<br>cumulative: {c:+,.0f} €"),
    "revenue_forecast.be_unknown": "No history yet",
    "revenue_forecast.be_never": (
        "⚠️ Break-even NEVER reached at this pace<br>"
        "{c:,.0f} € short, and the pace is {r:+.2f} €/month"),
    "revenue_forecast.be_reached": (
        "⏳ Break-even in <b>{d}</b>{q}<br>"
        "{c:,.0f} € short at a pace of {r:+.2f} €/month"),
    "revenue_forecast.be_months": "{n} months",
    "revenue_forecast.be_years": "{n:,.0f} months — {a:,.0f} years",
    "revenue_forecast.be_short_done": "reached",
    "revenue_forecast.be_short_never": "never at this pace",
    "revenue_forecast.be_short_months": "{n} months",
    "revenue_forecast.be_short_years": "{a:,.0f} years",
    # ── Les coûts que seul l'artiste connaît ─────────────────────────────────
    "revenue_forecast.costs_expander":
        "💳 My costs (distribution, mastering, artwork…) — enter them",
    "revenue_forecast.costs_caption": (
        "What you pay to release your music comes through no API: your "
        "distributor does not return it in its sales reports. Enter it here and "
        "it joins the chart and the break-even date."),
    "revenue_forecast.costs_spread": (
        "**{tot:,.2f} €** in total, spread over {n} months — that is "
        "**{moy:,.2f} €/month** in the chart and in the break-even date."),
    "revenue_forecast.cost_category": "Cost type",
    "revenue_forecast.cost_amount": "Amount (€)",
    "revenue_forecast.cost_period": "Frequency",
    "revenue_forecast.cost_start": "Starting from",
    "revenue_forecast.cost_label": "Label (optional)",
    "revenue_forecast.cost_end": "Until",
    "revenue_forecast.cost_ongoing": "Still active",
    "revenue_forecast.cost_once": "One-off spend: it lands on its single month.",
    "revenue_forecast.cost_yearly_warning": (
        "⚠️ **{m:.2f} € PER YEAR**, not in total: while the subscription is "
        "active it renews and accumulates in the break-even date."),
    "revenue_forecast.cost_monthly_warning": "⚠️ **{m:.2f} € PER MONTH**, not in total.",
    "revenue_forecast.cost_save": "💾 Save",
    "revenue_forecast.cost_zero": "A zero amount changes nothing on the chart.",
    "revenue_forecast.cost_saved": (
        "✅ {m:.2f} € recorded — the chart and the break-even date account for it."),
    "revenue_forecast.no_cost": (
        "No cost entered. The break-even date above therefore only counts your "
        "advertising — it is OPTIMISTIC by everything you paid to put your music "
        "online."),
    "revenue_forecast.cat.distribution": "Distribution",
    "revenue_forecast.cat.mastering": "Mastering",
    "revenue_forecast.cat.visuel": "Artwork",
    "revenue_forecast.cat.promo": "Promo",
    "revenue_forecast.cat.materiel": "Gear",
    "revenue_forecast.cat.autre": "Other",
    "revenue_forecast.period.one_off": "One off",
    "revenue_forecast.period.yearly": "Per year",
    "revenue_forecast.period.monthly": "Per month",
    # ── Les sources de la figure ─────────────────────────────────────────────
    "revenue_forecast.source.imusician": "iMusician",
    "revenue_forecast.source.distrokid": "DistroKid",
    "revenue_forecast.source.sacem": "SACEM",
    "revenue_forecast.source.meta_ads": "Meta advertising",
    "revenue_forecast.source.distribution": "Distribution",
    "revenue_forecast.source.mastering": "Mastering",
    "revenue_forecast.source.visuel": "Artwork",
    "revenue_forecast.source.promo": "Promo",
    "revenue_forecast.source.materiel": "Gear",
    "revenue_forecast.source.autre": "Other",
    # ── Ce que vaut un déclenchement d'algorithme ────────────────────────────
    "revenue_forecast.trigger_header": "🚀 What if a track triggered the algorithms?",
    "revenue_forecast.no_rate": (
        "At least one distributor sales report is needed to know what a stream "
        "earns you. Import a CSV from **CSV import**."),
    "revenue_forecast.no_benchmark":
        "The reference cohort is not loaded on this database.",
    "revenue_forecast.own_median": "your median track: {e:,.2f} €",
    "revenue_forecast.bar_value": "What one trigger is worth",
    "revenue_forecast.bar_expect": "Expected value on your catalogue",
    "revenue_forecast.pred_dated": " (predictions from {d})",
    "revenue_forecast.trigger_gap": (
        "\n\nYour catalogue of **{k} tracks** expects **{e} €** in total, that "
        "is **{u} € per track**. To close the **{c} €** between you and "
        "break-even, it would take about **{n}** more, at the same level."),
    "revenue_forecast.trigger_plain": (
        "A **trigger** is an algorithm (Discover Weekly, Release Radar, Radio) starting to "
        "push your track. Pale bar: what a track that triggers usually earns (its median "
        "streams × what one stream pays you). Green bar: what your tracks can expect from "
        "it, given their real chance."),
    "revenue_forecast.trigger_small": (
        "**The decision**: it would take about **{n}** triggers at {v} € to cover your costs. "
        "The algorithms bring you listeners, not enough to pay back your ads — judge your "
        "ads on the streams they buy, and your costs on what they bring."),
    "revenue_forecast.trigger_worth": (
        "**The decision**: a trigger brings up to {v} €, on the scale of what you are "
        "missing — push the track closest to a gate (Road to Algo)."),
    "revenue_forecast.trigger_caption": (
        "At **{tx} € per stream** — your real rate, measured over {s} streams "
        "paid {r} € by your distributor.\n\n"
        "⚠️ **This is not the gain from triggering.** The reference cohort "
        "contains only tracks that DID trigger: with no control track, we cannot "
        "say what the algorithm added. It is an order of magnitude — this is "
        "where the tracks that get there end up. The expected value multiplies "
        "it by the CALIBRATED chance of each of your tracks{d}."),
    # ── Les tiroirs ──────────────────────────────────────────────────────────
    "revenue_forecast.detail_expander":
        "🔎 Per-source and per-month detail — exact figures",
    "revenue_forecast.by_source_net": (
        "NET amounts — charges and VAT deducted, same as the chart and the "
        "break-even date."),
    # Entry point
    # Tab 1 — Current MRR
    # Tab 2 — MRR projection
    "revenue_forecast.ltv_header": "LTV & churn",
    "revenue_forecast.ltv_classic_header": "#### Classic LTV (ARPU ÷ monthly churn)",
    "revenue_forecast.churn_low": "Detected churn rate < 0.5% (few pending cancellations). Adjust manually:",
    "revenue_forecast.churn_estimated": "Estimated monthly churn rate (%)",
    "revenue_forecast.churn_monthly": "Monthly churn rate (%)",
    "revenue_forecast.churn_help": "Value estimated from pending cancellations: {churn:.1f}%",
    "revenue_forecast.churn_monthly_metric": "Monthly churn",
    "revenue_forecast.ltv_global": "Global LTV",
    "revenue_forecast.ltv_scenario_header": "#### LTV by retention-duration scenario",
    "revenue_forecast.ltv_artistic_header": "#### Artistic LTV (music revenue × duration)",
    "revenue_forecast.ltv_artistic_caption": "Proxy: average musical value of an artist, based on distributor + SACEM history.",
    "revenue_forecast.retention_hypothetical": "Hypothetical retention duration (months)",
    "revenue_forecast.avg_music_revenue": "Average music revenue / month / artist",
    "revenue_forecast.ltv_artistic_metric": "Artistic LTV over {months} months",
    # Tab 4 — Artist projection
    "revenue_forecast.no_active_artist": "No active artist.",
    "revenue_forecast.no_artist_id": "Unable to determine your artist identifier.",
    "revenue_forecast.horizon": "Projection horizon (months)",
    # Meta Ads ROI
    # ML predictions
    # Net margin
    "revenue_forecast.ledger_head": "| Revenue | Spend | of which ads | Financial result | Streams (all platforms) | Ads per stream |",
    "revenue_forecast.ledger_caption": "Since the start. « Ads per stream » divides ad spend by ALL streams, organic included: it is a ceiling, not what a gained stream cost — that one is in « Meta Ads › My whole funnel », campaign by campaign.",
    "revenue_forecast.be_short_too_short": "too early to date",
    "revenue_forecast.be_too_short": ("⏳ {c:,.0f} € to go — only {n} month(s) known:<br>"
                                      "too early to date the break-even point"),
    # R405 (V73)
    "revenue_forecast.position_caption": ("The « everything in against everything out » curve "
                                          "is in [↑ Budget & ROI](#budget): the gap between the "
                                          "two cumuls is what is left to recover, and they "
                                          "cross at break-even."),
    # R488
    "revenue_forecast.rev_cumul": "Cumulative revenue (sales + SACEM)",
    "revenue_forecast.spend_cumul": "Cumulative spend (Meta + costs)",
    "revenue_forecast.breakeven_title": "Revenue {r} against spend {s} · ROI {roi} — break-even where they cross",
}
