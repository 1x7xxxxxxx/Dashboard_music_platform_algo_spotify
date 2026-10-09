"""EN strings for the Distributor (iMusician/DistroKid) revenue view."""

EN = {
    "imusician.title": "💰 Distributor iMusician DistroKid + SACEM",
    "imusician.distributor": "Distributor",
    # Data tab
    "imusician.delete_expander": "🗑️ Delete an entry",
    "imusician.entry_deleted": "Entry deleted: {distributor} — {month} {year}",
    # Manual entry form
    "imusician.entry_header": "✍️ Manual entry",
    "imusician.no_active_artist": "No active artist.",
    "imusician.save_btn": "💾 Save",
    "imusician.entry_saved": "{distributor} — {month} {year}: {revenue:,.2f} € saved.",
    # ROI tab
    # ⚠️ PAS de `:,.2f` ici. `imusician.py:445` passe `fmt_eur(...)`, qui rend une
    # CHAÎNE déjà formatée en euros — appliquer une spécification numérique dessus
    # lève `ValueError: Unknown format code 'f' for object of type 'str'`.
    # Mesuré le 2026-09-18 : le gabarit FR rend « … = 1 234,56 € », l'anglais LÈVE.
    # Un artiste anglophone ouvrant la tuile ROI obtenait donc une exception.
    "imusician.roi_empty_period": "No revenue or spend data over this period.",
    "imusician.trigger_point": "One Discover Weekly trigger is worth",
    # R388 — one page: entry, evolution, break-even
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
    "imusician.cumulative": "Running total",
    # R488
    "imusician.import_btn": "📂 Import an iMusician / DistroKid export",
    "imusician.monthly_of": "{d} — € per month",
    "imusician.forecast": "forecast ({n} months at the recent pace)",
    "imusician.evolution_title": "Sales: {total} in total · {avg} per month · {n} months",
}
