"""EN strings for the Distributor (iMusician/DistroKid) revenue view."""

EN = {
    "imusician.title": "💶 Treasury (distributors, SACEM, Meta Ads)",
    "imusician.distributor": "Distributor",
    # R519 — one money-flow figure
    "imusician.treasury_header": "💶 Money, month by month",
    "imusician.balance": "Running balance",
    "imusician.cashflow_title": "Balance {b} — {i} in, {o} out",
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
    "imusician.trigger_point": "If a track entered Discover Weekly",
    # R561
    "imusician.circle_centre": "{i}<br>in",
    # R388 — one page: entry, evolution, break-even
    "imusician.no_revenue": (
        "No revenue recorded for this selection. Import an iMusician or DistroKid "
        "export (**📂 Add my Spotify for Artists & Apple figures** page) or enter a "
        "revenue (**✍️ Manual entry** button)."
    ),
    "imusician.roi_header": "💹 Break-even",
    "imusician.roi_no_data": (
        "No distributor revenue or Meta Ads spend data for this artist. "
        "Import an iMusician export (CSV Import page), enter a revenue (✍️ Manual entry), "
        "or launch the Meta collection from the home page."
    ),
    # R488
    "imusician.import_btn": "📂 Import the export",
    "imusician.manual_btn": "✍️ Manual entry",
    # R585
    "saisie_tresorerie.title": "💰 Treasury entry",
    # R553
    "imusician.money_artist": "Break-even of the artist",
}
