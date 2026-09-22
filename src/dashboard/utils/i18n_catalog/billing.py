"""EN catalog for the billing view."""

EN = {
    # ── Le service d'optimisation (2026-09-21) ───────────────────────────────
    "billing.service_header": "🎯 Have your campaigns run for you (bespoke service)",
    "billing.service_body": (
        "The tool tells you where your money goes. If you want someone to handle "
        "**the campaigns themselves**, that is a separate service, and we talk "
        "before starting."),
    "billing.service_book": "📅 Book a call",
    "billing.service_no_calendly": (
        "⚙️ `SERVICE_CALENDLY_URL` is not set: the booking button is hidden. Set "
        "it in `.env.local` (local) and in the container environment (prod)."),
    "billing.service_credential.0": (
        "🎬 **Dozens of video creatives** produced for your campaign, varied by "
        "hook and by opening"),
    "billing.service_credential.1": (
        "📈 **Real advertising experience** — campaigns actually run, not a "
        "dashboard theory"),
    "billing.service_credential.2": (
        "🎧 **Playlist curator for 2 years** — I know what gets placed and what "
        "does not"),
    "billing.service_credential.3": (
        "🎯 **The full setup** — audiences, placements, budgets, iterations"),
    "billing.title": "💳 Billing & Subscription",
    "billing.price_free": "€0/month",
    "billing.price_monthly": "€{p}/month",
    # Plan cards
    "billing.plan_free_label": "🆓 Free",
    "billing.plan_premium_label": "💎 Premium",
    "billing.one_artist": "1 artist",
    "billing.up_to_10": "Up to 10 artists",
    "billing.feat_everything_free": "Everything in Free",
    # Current plan
    "billing.free_plan_info": "You are on the **Free** plan. Check out the offers below.",
    "billing.trial_active": "🎁 **{plan}** access active (welcome trial). "
                            "See the offers below for what comes next.",
    "billing.metric_plan": "Plan",
    "billing.metric_price": "Monthly price",
    "billing.metric_status": "Status",
    "billing.free_months": (
        "🎁 You have **{n} free month(s)** from referrals. Write to us before "
        "your next payment and we apply them — it is not automatic yet."),
    "billing.discount": (
        "🏷️ A **{pct}% discount** is yours on your first paid month (referral). "
        "Tell us when you subscribe: it is applied by hand."),
    "billing.cancel_warning": "⚠️ Your subscription is set to **cancel on {date}**. "
                              "Reactivate via the Stripe portal below.",
    "billing.next_renewal": "Next renewal: {date}",
    "billing.payment_failed": "❌ Your last payment failed. Update your payment method to restore access.",
    "billing.manage_sub": "Manage subscription (Stripe portal)",
    "billing.portal_unset": "To manage your subscription, contact support or set "
                            "`STRIPE_PORTAL_URL` in your environment.",
    # Upgrade CTA
    "billing.current_plan_badge": "✅ Your current plan",
    "billing.included": "Included in your plan",
    "billing.free_no_action": "Free plan — no action required",
    "billing.upgrade_to": "Upgrade to {plan}",
    "billing.payment_soon": "💳 Online payment is coming soon. In the meantime, "
                            "contact us to activate this plan right away.",
    "billing.offers_header": "Our plans",
    # Admin view
    "billing.admin_header": "All artist subscriptions",
    "billing.no_artists": "No artists found.",
    "billing.col_tier": "Tier",
    "billing.col_plan": "Plan",
    "billing.col_status": "Status",
    "billing.col_period_end": "Period End",
    "billing.col_stripe": "Stripe Customer",
    "billing.col_artists": "Artists",
    "billing.col_mrr": "MRR (€)",
    "billing.mrr_header": "MRR breakdown",
    "billing.total_mrr": "Total MRR",
    "billing.paying_artists": "Paying artists",
    "billing.no_tenant": "Incomplete session: the payment could not be linked to your account. Please sign in again and retry.",
    "billing.service_see": "See the service",
}
