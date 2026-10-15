"""EN strings for the « meilleurs réglages » tool (src/dashboard/utils/best_settings.py)."""

EN = {
    "best_settings.hover": "%{y}<br>CPR: %{x:.3f} €<br>Spend: %{customdata[0]:,.0f} €"
                           "<br>Outbound clicks: %{customdata[1]:,.0f}<extra></extra>",
    "best_settings.caption": 'Each bar: the cost of one outbound click (CPR) for that setting, **one colour per campaign** — ★ the one to keep in that campaign. Pale with ⚠️: under {dep} € or {res} outbound clicks, too little to conclude; it can never be « the best ». Country, placement, platform and age cover the whole history (Meta does not date them). Interests are not here: Meta returns no figure per interest. Button and objective: per click on the ad (Meta does not attach outbound clicks to them).',
    "best_settings.not_enough": "not enough data",
    "best_settings.unset": "not set",
    "best_settings.photo_text": "{cpr:.2f} € · {f}× cheaper than « {e} »",
    "best_settings.photo_axis": "Cost per click of the value to keep (€)",
}
