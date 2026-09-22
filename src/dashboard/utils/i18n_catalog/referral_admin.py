"""EN catalog for the referral_admin view."""

EN = {
    "referral_admin.owed_header": "🧾 Rewards to apply BY HAND",
    "referral_admin.owed_none": (
        "No pending reward. Nothing to apply today."),
    "referral_admin.owed_why": (
        "This panel exists because `referral_free_months` and "
        "`first_month_discount_pct` are consumed by NO code: the Stripe payment "
        "link is static and carries no per-customer discount. The two pages that "
        "display them now say so to the artist."),
    "referral_admin.owed_summary": (
        "{n} artist(s) concerned · **{v} €** to honour at their current plan's rate."),
    "referral_admin.owed_months": "Free months owed",
    "referral_admin.owed_dormant": (
        "⏳ **{n} of these artists have no paid subscription**: their free months "
        "cost nothing until they subscribe, so the value above counts them as "
        "zero. It will jump the day they do — this is a debt, not an absence."),
    "referral_admin.col_months": "Free months",
    "referral_admin.col_discount": "1st-month discount (%)",
    "referral_admin.col_plan": "Plan",
    "referral_admin.col_price": "Price (€)",
    "referral_admin.col_status": "Status",
    "referral_admin.col_next": "Next payment",
    "referral_admin.col_value": "Value (€)",
    "referral_admin.owed_howto": (
        "Action: Stripe portal → the artist's subscription → **add a coupon** "
        "(100% for N months, or {pct}% on the first) → reset their column in the "
        "database. Until this is automated, this list IS the programme."),
    "referral_admin.admin_only": "⛔ Admin access only.",
    "referral_admin.title": "📊 Referral Program — KPIs",
    "referral_admin.metric_total_referrals": "Total referrals",
    "referral_admin.metric_converted": "Converted to paid",
    "referral_admin.metric_conversion_rate": "Conversion rate",
    "referral_admin.metric_free_months": "Free months granted",
    "referral_admin.top_referrers": "Top referrers",
    "referral_admin.col_artist": "Artist",
    "referral_admin.col_referrals_made": "Referrals made",
    "referral_admin.col_free_months_earned": "Free months earned",
    "referral_admin.col_code_uses": "Code uses",
    "referral_admin.col_code": "Code",
    "referral_admin.no_referrals": "No referrals recorded yet.",
    "referral_admin.all_events": "All referral events",
    "referral_admin.col_referrer": "Referrer",
    "referral_admin.col_referred": "Referred",
    "referral_admin.col_code_used": "Code used",
    "referral_admin.col_date": "Date",
    "referral_admin.col_referred_plan": "Referred's plan",
    "referral_admin.no_events": "No referral events yet.",
}
