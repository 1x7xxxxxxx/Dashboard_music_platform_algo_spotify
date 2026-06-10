"""EN catalog for the register view."""

EN = {
    "register.title": "🎵 Create your account",
    "register.subtitle": "Join the Music Dashboard. Free plan — upgrade anytime.",
    "register.live_activity": "{n} artists use streaMLytics",
    # Validation errors
    "register.err_artist_name": "Artist name is required.",
    "register.err_slug": "Slug: lowercase letters, digits, hyphens and underscores only.",
    "register.err_username": "Username: 3–50 characters, letters/digits/underscores only.",
    "register.err_email": "A valid email address is required.",
    "register.err_pw_mismatch": "Passwords do not match.",
    "register.err_terms": "You must accept the Privacy Policy and Terms of Use to register.",
    # Form fields
    "register.artist_name": "Artist name *",
    "register.artist_name_ph": "e.g. 1x7xxxxxxx",
    "register.artist_name_help": "Your public artist name.",
    "register.slug": "Slug *",
    "register.slug_ph": "e.g. 1x7xxxxxxx",
    "register.slug_help": "Unique identifier — lowercase, no spaces. Auto-filled from artist name.",
    "register.username": "Username *",
    "register.username_ph": "e.g. john_artist",
    "register.username_help": "Used to log in. 3–50 characters.",
    "register.email": "Email *",
    "register.email_ph": "you@example.com",
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
    "register.slug_taken": "Slug '{slug}' is already taken. Choose a different one.",
    "register.username_taken": "Username '{u}' is already taken.",
    "register.email_taken": "Email '{e}' is already registered.",
    "register.code_invalid": "Code '{code}' is not valid or has expired.",
    # Success / outcome
    "register.promo_active": " Your **{plan} plan** is active for **{days} days**.",
    "register.welcome_trial": " You get **{days} days of free Premium access**.",
    "register.referral_discount": " A **20% discount** will be applied to your first paid month.",
    "register.success": "✅ Account created for **{name}**!{msg} "
                        "A verification email has been sent to **{email}**. "
                        "Click the link in the email to activate your account.",
    "register.email_failed": "✅ Account created for **{name}**,{msg} but the verification email "
                             "could not be sent (SMTP not configured). "
                             "Ask an admin to manually verify your account.",
    "register.onboarding_btn": "→ Set up your dashboard (2 min)",
    "register.failed": "Registration failed: {err}",
}
