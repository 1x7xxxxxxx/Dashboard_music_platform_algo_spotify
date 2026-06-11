"""EN catalog for the revenue_forecast view."""

EN = {
    # Entry point
    "revenue_forecast.title": "📈 Revenue forecast",
    "revenue_forecast.tab_mrr": "📊 Current MRR",
    "revenue_forecast.tab_projection": "🔮 MRR projection",
    "revenue_forecast.tab_ltv": "💎 LTV & churn",
    "revenue_forecast.tab_artist": "🎵 Artist projection",
    "revenue_forecast.artist_caption": "Projection of your music revenue based on your iMusician history.",
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
    "revenue_forecast.artist_forecast_header": "Music revenue projection (iMusician + DistroKid + SACEM)",
    "revenue_forecast.artist_forecast_caption": "Consolidated monthly music revenue: "
                                                "distributors (iMusician + DistroKid) + gross SACEM royalties.",
    "revenue_forecast.by_source_header": "**Cumulative revenue by source**",
    "revenue_forecast.line_total": "Total (all distributors)",
    "revenue_forecast.line_sacem": "🎼 SACEM royalties",
    "revenue_forecast.no_active_artist": "No active artist.",
    "revenue_forecast.no_artist_id": "Unable to determine your artist identifier.",
    "revenue_forecast.insufficient_data": (
        "Insufficient data for a projection (minimum 3 months of distributor/SACEM history "
        "required). Import your CSVs/XLSX from the **CSV Import** page."
    ),
    "revenue_forecast.horizon": "Projection horizon (months)",
    "revenue_forecast.avg_monthly_revenue": "Average monthly revenue",
    "revenue_forecast.trend": "Trend",
    "revenue_forecast.projection_metric": "Projection M+{horizon}",
    "revenue_forecast.vs_average": "{delta:+.2f} € vs average",
    "revenue_forecast.historical_data": "Historical data",
    "revenue_forecast.col_month": "Month",
    "revenue_forecast.col_revenue": "Revenue (€)",
    # Meta Ads ROI
    "revenue_forecast.meta_roi_header": "### 💸 Meta Ads — historical ROI",
    "revenue_forecast.no_meta_spend": (
        "No Meta Ads spend found for this artist over the period. "
        "Connect Meta via **API Credentials** and trigger the Meta Insights DAG."
    ),
    "revenue_forecast.total_meta_spend": "Total Meta spend",
    "revenue_forecast.total_imusician_revenue": "Total iMusician revenue",
    "revenue_forecast.global_roi": "Global ROI",
    "revenue_forecast.profitable": "profitable",
    "revenue_forecast.loss_making": "loss-making",
    # ML predictions
    "revenue_forecast.ml_header": "### 🤖 ML predictions — scores per track",
    "revenue_forecast.no_ml": (
        "No ML prediction available. Trigger the **ml_scoring_daily** DAG "
        "from **ETL Monitoring** or the Airflow UI."
    ),
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
    "revenue_forecast.margin_header": "### 📊 Projected net margin",
    "revenue_forecast.margin_caption": "Over the selected projection horizon: **{horizon} months**",
    "revenue_forecast.vps_cost": "VPS infra cost (€/month)",
    "revenue_forecast.vps_cost_help": "Monthly server cost (VPS, Railway, Docker host…)",
    "revenue_forecast.meta_spend_est": "Estimated Meta spend (€/month)",
    "revenue_forecast.meta_spend_est_help": "Pre-filled with the historical average. Adjustable.",
    "revenue_forecast.projected_revenue": "Projected revenue",
    "revenue_forecast.meta_spend_metric": "Meta spend",
    "revenue_forecast.vps_infra": "VPS infra",
    "revenue_forecast.net_margin": "Net margin",
}
