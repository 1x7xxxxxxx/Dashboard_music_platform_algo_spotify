"""EN catalog for the revenue_forecast view."""

EN = {
    # ── Mon argent : flux, cumul, point mort (2026-09-21) ────────────────────
    "revenue_forecast.artist_forecast_header":
        "My money: what comes in, what goes out, and when I break even",
    "revenue_forecast.artist_forecast_caption": (
        "All your money on one chart: distributors (iMusician, DistroKid), SACEM "
        "royalties, Meta advertising and your release costs. The lower curve "
        "crosses zero the day you break even."),
    "revenue_forecast.artist_caption":
        "Revenue, spend and break-even — all on one chart.",
    "revenue_forecast.no_money_yet": (
        "No money movement on record. Import a sales report from **CSV import**, "
        "or connect Meta in **🔑 API Credentials**."),
    "revenue_forecast.frame_flows": "What comes in and goes out, each month (€)",
    "revenue_forecast.frame_cumul":
        "Where I stand overall (€) — break-even is at zero",
    "revenue_forecast.line_cumul": "Net cumulative",
    "revenue_forecast.line_proj": "Projection",
    "revenue_forecast.breakeven_line": "break-even",
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
    "revenue_forecast.col_in": "In (€)",
    "revenue_forecast.col_out": "Out (€)",
    "revenue_forecast.col_net": "Net (€)",
    "revenue_forecast.col_cumul": "Cumulative (€)",
    "revenue_forecast.ml_expander":
        "🤖 Which of my tracks is closest — ML scores",
    # Entry point
    "revenue_forecast.title": "📈 Revenue forecast",
    "revenue_forecast.tab_mrr": "📊 Current MRR",
    "revenue_forecast.tab_projection": "🔮 MRR projection",
    "revenue_forecast.tab_ltv": "💎 LTV & churn",
    "revenue_forecast.tab_artist": "🎵 Artist projection",
    # Tab 1 — Current MRR
    "revenue_forecast.mrr_header": "Current MRR",
    "revenue_forecast.no_subscriptions": "No subscription found in the database. Connect Stripe to feed this data.",
    "revenue_forecast.mrr_total": "Total MRR",
    "revenue_forecast.paying_artists": "Paying artists",
    "revenue_forecast.pending_cancellations": "Pending cancellations",
    "revenue_forecast.subs_detail": "Subscription details",
    "revenue_forecast.col_price": "Price (€/month)",
    "revenue_forecast.col_status": "Status",
    "revenue_forecast.col_cancel": "Cancel at period end",
    "revenue_forecast.col_period_end": "Period end",
    # Tab 2 — MRR projection
    "revenue_forecast.growth_header": "MRR growth simulation",
    "revenue_forecast.mrr_start": "Starting MRR (actual): **{mrr:,.2f} €**",
    "revenue_forecast.growth_rate": "Monthly growth rate (%)",
    "revenue_forecast.months_to_project": "Months to project",
    "revenue_forecast.premium_price": "Premium price (€/month)",
    "revenue_forecast.enterprise_toggle": "Enable an Enterprise plan",
    "revenue_forecast.enterprise_price": "Enterprise price (€/month)",
    "revenue_forecast.enterprise_new_artists": "New Enterprise artists / month",
    "revenue_forecast.mrr_target": "Target MRR (€) — reference line",
    "revenue_forecast.mrr_final": "Final MRR",
    "revenue_forecast.arr_final": "Final ARR",
    "revenue_forecast.months_to_target": "Months to reach target",
    "revenue_forecast.target_not_reached": "Target MRR {target:,.0f} € not reached within {months} months",
    "revenue_forecast.projection_table": "Detailed projection table",
    # Tab 3 — LTV & churn
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
    "revenue_forecast.col_month": "Month",
    # Meta Ads ROI
    # ML predictions
    "revenue_forecast.no_ml": (
        'No prediction yet. They are recomputed every day, late morning, from the data already collected.'),
    "revenue_forecast.ml_caption": (
        "🛡️ The *floor* columns are **worst-case estimates**: the volume model "
        "underestimates hits, the real potential is often higher. "
        "Release Radar has no volume column: its throughput depends on the notification "
        "open rate (not predictable) — we rely on its "
        "classification (AUC 0.94, validated per song)."
    ),
    "revenue_forecast.col_track": "Track",
    "revenue_forecast.col_last_prediction": "Last prediction",
    "revenue_forecast.col_dw_prob": "Discovery Weekly (%)",
    "revenue_forecast.col_rr_prob": "Release Radar (%)",
    "revenue_forecast.col_radio_prob": "Radio (%)",
    "revenue_forecast.col_dw_streams": "DW streams 7d (floor ≥)",
    "revenue_forecast.col_rr_streams": "RR streams 7d (floor ≥)",
    "revenue_forecast.col_radio_streams": "Radio streams 7d (floor ≥)",
    "revenue_forecast.col_streams_7d": "Streams 7d (actual)",
    "revenue_forecast.col_streams_28d": "Streams 28d (actual)",
    # Net margin
}
