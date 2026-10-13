"""EN strings for the « meilleurs réglages » tool (src/dashboard/utils/best_settings.py)."""

EN = {
    "best_settings.hover": "%{y}<br>CPR: %{x:.3f} €<br>Spend: %{customdata[0]:,.0f} €"
                           "<br>Outbound clicks: %{customdata[1]:,.0f}<extra></extra>",
    "best_settings.verdict": "**{crit}**: keep « {keep} » ({cpr} €) rather than « {avoid} » "
                             "({cpr_max} €), ×{f} cheaper",
    "best_settings.caption": 'Each bar: the cost of one outbound click (CPR) for that setting — **in green, the one to keep**. ⚠️ in grey: under {dep} € or {res} outbound clicks, too little to conclude; it can never be « the best ». Country, placement, platform and age cover the whole history (Meta does not date them). Interests are not here: Meta returns no figure per interest. Button and objective: all accounts, per click on the ad (Meta does not attach outbound clicks to them).',
}
