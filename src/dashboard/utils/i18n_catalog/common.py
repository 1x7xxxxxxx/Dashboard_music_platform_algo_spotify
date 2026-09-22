"""Shared EN strings — months, generic UI words reused across views."""

EN = {
    # Months (selectboxes, period labels) — t("common.month.5", "Mai")
    "common.remove": "Remove",
    "common.month.1": "January",
    "common.month.2": "February",
    "common.month.3": "March",
    "common.month.4": "April",
    "common.month.5": "May",
    "common.month.6": "June",
    "common.month.7": "July",
    "common.month.8": "August",
    "common.month.9": "September",
    "common.month.10": "October",
    "common.month.11": "November",
    "common.month.12": "December",
    # Generic UI words
    "common.all": "All",
    "common.period": "Period",
    "common.year": "Year",
    "common.month": "Month",
    "common.date": "Date",
    "common.total": "Total",
    "common.notes": "Notes",
    "common.artist": "Artist",
    "common.song": "Song",
    "common.delete": "🗑️ Delete",
    "common.cancel": "Cancel",
    "common.error": "Error: {err}",
    "common.no_data": "No data for this selection.",
    "common.streams": "Streams",
    "common.count": "Count",
    "common.revenue_eur": "Revenue (€)",
    "common.filter_by_year": "Filter by year",
    "common.filter_by_month": "Filter by month",
    # Guides — OS switch (os_hints.py)
    "guides.os_selector": "💻 Show instructions for my computer:",
    # Views — collapsed container for refine-only charts (ui.secondary_analyses)
    "ui.secondary_analyses": "📊 Detailed analyses",
    # R146 — the one place the outbound-click limit is written, in English.
    # `src/dashboard/utils/proxy_disclosure.py` carries the French defaults and the
    # measurement behind them.
    "proxy.outbound_label": "Outbound clicks",
    "proxy.cpr_label": "CPR (€) — cost per outbound click",
    "proxy.cpr_help": (
        "**A \"result\" here is a click LEAVING the smart link** towards Spotify — "
        "the event Hypeddit reports to Meta. It is not a listen: nobody knows "
        "whether the listener actually played the track. Meta optimises delivery "
        "on that click, so this cost is a cost per outbound click, not a cost per "
        "listen. For the price of a real listen, see the \"Cost per stream\" tile "
        "on the **Meta × Spotify** page."),
    "proxy.outbound_help": (
        "Clicks leaving the smart link towards the platform, reported by "
        "Hypeddit's CAPI. A listen is not guaranteed behind each one."),
    "proxy.caption": (
        "ℹ️ **A \"result\" is an outbound click to the platform**, not a listen. "
        "The cost-per-result figures on this page read as cost per click."),
}
