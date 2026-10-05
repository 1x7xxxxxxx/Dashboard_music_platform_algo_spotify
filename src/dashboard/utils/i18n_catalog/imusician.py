"""EN strings for the Distributor (iMusician/DistroKid) revenue view."""

EN = {
    "imusician.title": "💰 Distributor — Monthly revenue",
    "imusician.distributor": "Distributor",
    # Data tab
    "imusician.evolution_summary": "Total {total} · average {avg} per month · {n} months recorded",
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
    "imusician.roi_caption": (
        "Net revenue (iMusician + DistroKid + SACEM royalties) versus all spend "
        "(Meta Ads + entered costs) over the selected period"
    ),
    "imusician.roi_revenue": "💰 Revenue (distrib. + SACEM)",
    "imusician.roi_spend": "📱 Meta spend",
    # ⚠️ PAS de `:,.2f` ici. `imusician.py:445` passe `fmt_eur(...)`, qui rend une
    # CHAÎNE déjà formatée en euros — appliquer une spécification numérique dessus
    # lève `ValueError: Unknown format code 'f' for object of type 'str'`.
    # Mesuré le 2026-09-18 : le gabarit FR rend « … = 1 234,56 € », l'anglais LÈVE.
    # Un artiste anglophone ouvrant la tuile ROI obtenait donc une exception.
    "imusician.roi_total_help": "ROI on all spend (Meta Ads + entered costs) = {total}",
    "imusician.roi_profitable": "✅ Profitable",
    "imusician.roi_unprofitable": "⚠️ Unprofitable",
    "imusician.roi_no_spend_help": "No promo spend over the period — widen the filter",
    "imusician.roi_effective_window": (
        "Period actually covered: {a} → {b} — revenue is monthly, so the window is "
        "rounded to whole months."),
    "imusician.roi_unavailable_help": (
        "Figures unavailable — the read failed. This is not \u201cno spend\u201d."),
    "imusician.roi_empty_period": "No revenue or spend data over this period.",
    "imusician.trigger_point": "One Discover Weekly trigger is worth",
    # R388 — one page: entry, evolution, break-even
    "imusician.intro": (
        "iMusician and DistroKid exports are imported from the **📂 Add my Spotify for "
        "Artists & Apple figures** page; a month can also be entered by hand here."
    ),
    "imusician.no_revenue": (
        "No revenue recorded for this selection. Import an iMusician or DistroKid "
        "export (**📂 Add my Spotify for Artists & Apple figures** page) or enter a "
        "revenue manually above."
    ),
    "imusician.roi_header": "💹 Break-even",
    "imusician.roi_no_data": (
        "No distributor revenue or Meta Ads spend data for this artist. "
        "Import an iMusician export (CSV Import page), enter a revenue above, "
        "or launch the Meta collection from the home page."
    ),
    "imusician.evolution_header": "📈 Sales over time",
    "imusician.all_years": "All years",
    "imusician.all_months": "All months",
    "imusician.cumulative": "Running total",
    "imusician.monthly_axis": "€ per month",
    "imusician.cumulative_axis": "€ cumulated",
}
