"""EN strings — auth module (login, TOTP, bootstrap, lockout, paywall, sidebar)."""

EN = {
    # Rate limit / lockout
    "auth.rate_limited": "Too many failed attempts. Please wait {s} seconds before trying again.",
    "auth.locked": "Account locked after too many failed attempts. Try again in {m} minute(s).",
    "auth.invalid_credentials": "Invalid username or password.",
    # Password policy
    "auth.pw_policy": ("Password must be at least 10 characters and contain at least "
                       "one letter and one digit."),
    "auth.pw_mismatch": "Passwords do not match.",
    # Resend verification
    "auth.resend_ok": "Verification email resent to {email}.",
    "auth.resend_fail": "Failed to send email. Check SMTP config in config/config.yaml.",
    "auth.resend_btn": "Resend verification email",
    "auth.verify_email_first": ("📧 Please verify your email address before signing in. "
                                "Check the inbox you registered with."),
    # TOTP challenge
    "auth.totp_title": "🔐 Two-factor authentication",
    "auth.totp_prompt": ("Signed in as **{u}**. Enter the 6-digit code from your "
                         "authenticator app."),
    "auth.totp_code": "Authentication code",
    "auth.totp_verify": "Verify",
    "auth.totp_invalid": "Invalid authentication code. Please try again.",
    "auth.totp_missing_dep": "pyotp not installed. Run: pip install pyotp",
    # Bootstrap (first-run admin creation)
    "auth.bootstrap_title": "🎵 Music Dashboard — First-time setup",
    "auth.bootstrap_warning": ("No users found in the database. Create the first **admin** "
                               "account to get started."),
    "auth.bootstrap_subheader": "Create admin account",
    "auth.bootstrap_submit": "Create admin",
    "auth.bootstrap_ok": "Admin account '{u}' created. You can now log in.",
    "auth.bootstrap_error": "Error creating admin: {e}",
    "auth.all_fields_required": "All fields are required.",
    # Login form
    "auth.signin_title": "Sign in",
    "auth.signin": "Sign in",
    "auth.username": "Username",
    "auth.username_ph": "artist name",
    "auth.email": "Email",
    "auth.password": "Password",  # pragma: allowlist secret
    "auth.confirm_password": "Confirm password",  # pragma: allowlist secret
    "auth.enter_credentials": "Please enter your username and password.",
    "auth.register_link": "[Don't have an account? **Create one**](?page=register)",
    "auth.pw_encrypted_notice": ("🔒 Your password is encrypted (bcrypt) and never stored "
                                 "in plain text — GDPR compliant."),
    "auth.session_expired": "🔒 Session expired after inactivity. Please sign in again.",
    "auth.db_unreachable": ("❌ Database unreachable. Make sure Docker is running: "
                            "`docker-compose up -d`"),
    # Sidebar user block
    "auth.role_admin": "👑 Admin",
    "auth.role_artist": "🎤 Artist",
    "auth.global_access": "Global access (all artists)",
    "auth.logout": "Logout",
    # Paywall
    "auth.paywall": ("🔒 This feature requires the **{plan}** plan. "
                     "Your current plan: **{current}**."),
    "auth.paywall_btn": "→ See plans and upgrade",
}
