"""EN catalog for the revenue_forecast view."""

EN = {
    # ── Mon argent : flux, cumul, point mort (2026-09-21) ────────────────────
    "revenue_forecast.cost_track": "Track concerned (optional)",
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
    "revenue_forecast.be_years": "≈ {a:,.0f} years",
    "revenue_forecast.be_not_before": (
        "⏳ Break-even not before <b>{n} years</b><br>"
        "{c:,.0f} € short at a pace of {r:+.2f} €/month"),
    "revenue_forecast.projection_mark": "{n} years",
    "revenue_forecast.projection": "Trend forecast at the pace of the last 12 months",
    # R561
    "revenue_forecast.path": "You, month after month",
    "revenue_forecast.path_hover": (
        "%{customdata}<br>spent since the start: %{x:,.0f} €"
        "<br>earned since the start: %{y:,.0f} €<extra></extra>"),
    "revenue_forecast.projection_hover": (
        "%{customdata} (forecast)<br>spent: %{x:,.0f} €<br>earned: %{y:,.0f} €<extra></extra>"),
    "revenue_forecast.zone_paid": "above: your ads are paid back",
    "revenue_forecast.zone_short": "below: money is missing",
    "revenue_forecast.diagonal": "Break-even: earned = spent",
    "revenue_forecast.axis_spend": "Spent since the start (ads + costs), €",
    "revenue_forecast.axis_revenue": "Earned since the start (sales + SACEM), €",
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
    # ── Les tiroirs ──────────────────────────────────────────────────────────
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
    # Meta Ads ROI
    # ML predictions
    # Net margin
    "revenue_forecast.be_too_short": ("⏳ {c:,.0f} € to go — only {n} month(s) known:<br>"
                                      "too early to date the break-even point"),
    # R405 (V73)
    # R488
    "revenue_forecast.breakeven_title": "Revenue {r} against spend {s} · ROI {roi}",
    # R553
    "revenue_forecast.trigger_locked": "What an algorithm trigger would bring you, and the projection of your break-even: included in Premium",
}
