"""EN catalog for the register view."""

EN = {
    "register.title": "🎵 Create your account",
    "register.subtitle": "Join the streaMLytics. Free plan — upgrade anytime.",
    "register.live_activity": "{n} artists use streaMLytics",
    # Validation errors
    "register.err_artist_name": "Artist name is required.",
    "register.err_email": "A valid email address is required.",
    "register.err_pw_mismatch": "Passwords do not match.",
    "register.err_terms": "You must accept the Privacy Policy and Terms of Use to register.",
    # Form fields
    "register.artist_name": "Artist name *",
    "register.artist_name_ph": "Your artist name",
    "register.artist_name_help": "Your public artist name.",
    "register.email": "Email *",
    "register.email_ph": "you@example.com",
    "register.email_help": "Used as your sign-in identifier.",
    "register.password": "Password *",  # pragma: allowlist secret
    "register.pw_help": "Minimum 8 characters.",
    "register.confirm_password": "Confirm password *",  # pragma: allowlist secret
    "register.referral_code": "Promo or referral code (optional)",
    "register.referral_ph": "e.g. A3F8C1",
    "register.referral_help": "Promo code (free access) or referral code from a friend "
                              "(20% off first month).",
    "register.terms_checkbox": "I accept the [Privacy Policy](?page=privacy) and Terms of Use *",
    "register.terms_help": "Required to create an account.",
    "register.marketing_checkbox": "I agree to receive news, updates and marketing communications "
                                   "by email (optional)",
    "register.marketing_help": "You can withdraw this consent at any time.",
    "register.submit": "Create account",
    "register.already_have": "[Already have an account? **Sign in**](?page=login)",
    # Uniqueness errors
    # register.email_taken / register.code_invalid were retired on 2026-08-22: both
    # answered an anonymous visitor a question only an account holder should be able
    # to ask (R23). Their replacements below say the same thing to the right person.
    "register.code_ignored": "Code '{code}' could not be applied. Your account is "
                             "created; contact us if the code was meant to work.",
    "register.throttled": "Too many sign-up attempts from this connection. "
                          "Try again in {s} second(s).",
    # Success / outcome
    "register.promo_active": " Your **{plan} plan** is active for **{days} days**.",
    "register.welcome_trial": " You get **{days} days of free Premium access**.",
    "register.referral_discount": " A **20% discount** will be applied to your first paid month.",
    "register.next_step": "📬 **Next step: open your mailbox.** The verification link "
                          "activates your account — onboarding opens right after.\n\n"
                          "It leaves **immediately** and usually arrives in under a "
                          "minute. If it is not there: check **spam**, and on Gmail the "
                          "**Promotions** tab.",
    # What to do while the mail travels (2026-09-04). SMTP costs 0.24 s in production;
    # it is DELIVERY that takes a minute, and the screen offered nothing meanwhile.
    "register.sending": "Sending your verification e-mail…",
    "register.meanwhile": "⏳ While the e-mail is on its way",
    "register.download_guide": "📄 Download the getting-started guide (PDF)",
    "register.prepare_header": "**Gather what you will paste in** — that is all the "
                               "setup asks for:",
    "register.prepare_hint": "You do not need all of them: two platforms are enough to "
                             "start, and you can add the rest whenever you like.",
    "register.resend": "✉️ I received nothing — resend the e-mail",
    "register.resend_wait": "You can ask for another send in {s} s.",
    "register.resent": "✅ Sent again to **{email}**.",
    "register.resend_failed": "The send did not go through. Try again in a minute.",
    "register.login_btn": "→ I have verified, sign me in",
    "register.success": "✅ Account created for **{name}**!{msg} "
                        "A verification email has been sent to **{email}**. "
                        "Click the link in the email to activate your account.",
    "register.email_failed": "✅ Account created for **{name}**,{msg} but the verification email "
                             "could not be sent (SMTP not configured). "
                             "Ask an admin to manually verify your account.",
    "register.failed": "Sign-up did not go through. Try again; if the problem persists, contact us quoting reference **{ref}**.",
}
