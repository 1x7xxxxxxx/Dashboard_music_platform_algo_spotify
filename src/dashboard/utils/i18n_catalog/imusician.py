"""EN strings for the Distributor (iMusician/DistroKid) revenue view."""

EN = {
    "imusician.title": "💰 Distributor — Monthly revenue",
    "imusician.intro": (
        "Visualisation of the revenue generated through your distributors "
        "(iMusician, DistroKid). Imports (iMusician CSV, DistroKid TSV/CSV) are "
        "done from the **📂 CSV Import** page; a manual monthly entry is also "
        "possible below."
    ),
    "imusician.tab_data": "📊 Data",
    "imusician.tab_roi": "💹 ROI Breakheaven",
    "imusician.distributor": "Distributor",
    # Data tab
    "imusician.no_revenue": (
        "No revenue recorded for this selection. Import an iMusician or DistroKid "
        "export (**📂 CSV Import** page) or enter a revenue manually below."
    ),
    "imusician.select_year_month": "Select at least one year and one month.",
    "imusician.kpi_total": "Cumulative total",
    "imusician.kpi_avg": "Monthly average",
    "imusician.kpi_months": "Months recorded",
    "imusician.detail_header": "Detail",
    "imusician.delete_expander": "🗑️ Delete an entry",
    "imusician.entry_deleted": "Entry deleted: {distributor} — {month} {year}",
    # Manual entry form
    "imusician.entry_header": "✍️ Manual entry",
    "imusician.entry_caption": (
        "Enter a month's revenue from your distributor statement (amount in €). "
        "An entry for an already-recorded month replaces it."
    ),
    "imusician.no_active_artist": "No active artist.",
    "imusician.notes_optional": "Notes (optional)",
    "imusician.save_btn": "💾 Save",
    "imusician.entry_saved": "{distributor} — {month} {year}: {revenue:,.2f} € saved.",
    # ROI tab
    "imusician.roi_header": "💹 ROI Breakheaven",
    "imusician.roi_caption": (
        "Revenue (iMusician + DistroKid + SACEM royalties) vs total promo spend "
        "(Meta Ads + Hypeddit) over the selected period"
    ),
    "imusician.roi_no_data": (
        "No distributor revenue or Meta Ads spend data for this artist. "
        "Import an iMusician export (CSV Import page), enter a revenue in the "
        "Data tab, or launch the Meta collection from the home page."
    ),
    "imusician.roi_revenue": "💰 Revenue (distrib. + SACEM)",
    "imusician.roi_spend": "📱 Meta spend",
    "imusician.roi_spend_hypeddit": "🎁 Hypeddit spend",
    "imusician.roi_total_help": "ROI on total promo spend (Meta + Hypeddit) = {total:,.2f} €",
    "imusician.roi_profitable": "✅ Profitable",
    "imusician.roi_unprofitable": "⚠️ Unprofitable",
    "imusician.roi_no_spend_help": "No promo spend over the period — widen the filter",
    "imusician.meta_spend_eur": "Meta spend (€)",
    "imusician.hypeddit_spend_eur": "Hypeddit spend (€)",
    "imusician.euros_axis": "Euros (€)",
    "imusician.roi_empty_period": "No revenue or spend data over this period.",
}
