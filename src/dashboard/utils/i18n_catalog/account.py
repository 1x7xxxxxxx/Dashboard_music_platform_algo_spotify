"""EN catalog for the account view."""

EN = {
    "account.title": "👤 My Account",
    "account.session_expired": "Session expired. Please log in again.",
    "account.user_not_found": "User not found.",
    "account.tab_profile": "👤 Profile",
    "account.tab_password": "🔒 Password",
    "account.tab_2fa": "🔐 2FA",
    "account.tab_consent": "📧 Communications",
    # Profile
    "account.profile_header": "👤 My account",
    "account.username": "Username",
    "account.role": "Role",
    "account.email_verified": "Email verified",
    "account.yes": "✅ Yes",
    "account.pending": "⏳ Pending",
    "account.email_caption": "Email: **{email}**",
    "account.artist_caption": "Artist: **{name}** — slug `{slug}` — tier `{tier}`",
    "account.member_since": "Member since: {date}",
    # Change password
    "account.change_pw_header": "🔒 Change password",
    "account.current_pw": "Current password",
    "account.new_pw": "New password",
    "account.pw_help": "Minimum 8 characters.",
    "account.confirm_new_pw": "Confirm new password",
    "account.update_pw_btn": "Update password",
    "account.pw_all_required": "All three fields are required.",
    "account.pw_incorrect": "Current password is incorrect.",
    "account.pw_mismatch": "Passwords do not match.",
    "account.pw_same": "New password is identical to the current one.",
    "account.pw_updated": "✅ Password updated successfully.",
    # Consent
    "account.consent_header": "📧 Communication preferences",
    "account.opted_in": "You are currently **opted in** to marketing communications.",
    "account.opted_out": "You are currently **opted out** of marketing communications "
                         "(newsletters, platform news).",
    "account.consent_updated": "Last updated: {date}",
    "account.consent_toggle": "Receive email alerts & communications",
    "account.consent_on": "✅ You have opted in to marketing communications.",
    "account.consent_off": "✅ You have opted out. You will no longer receive marketing emails.",
    # TOTP / 2FA
    "account.totp_header": "🔐 Two-factor authentication (2FA)",
    "account.totp_enabled": "✅ Two-factor authentication is **enabled** on your account.",
    "account.totp_required_caption": "Your authenticator app is required at each sign-in.",
    "account.totp_disable_title": "**Disable 2FA**",
    "account.totp_confirm_pw": "Confirm your password to disable 2FA",
    "account.totp_disable_btn": "Disable 2FA",
    "account.totp_pw_incorrect": "Incorrect password.",
    "account.totp_disabled": "✅ 2FA disabled. You can re-enable it at any time.",
    "account.totp_intro": "Protect your account with a time-based one-time password (TOTP). "
                          "Compatible with Google Authenticator, Authy, and similar apps.",
    "account.totp_pkg_missing": "Required packages not installed: `pip install pyotp qrcode[pil]`",
    "account.totp_scan_caption": "Scan with your authenticator app",
    "account.totp_manual_key": "**Manual entry key:**",
    "account.totp_manual_caption": "Enter this key manually in your app if you cannot scan the QR code.",
    "account.totp_verify_title": "**Verify and activate**",
    "account.totp_code_input": "Enter the 6-digit code from your app",
    "account.totp_activate_btn": "Activate 2FA",
    "account.totp_active": "✅ Two-factor authentication is now active on your account.",
    "account.totp_invalid_code": "Invalid code. Make sure your device clock is correct and try again.",
    # Account deletion
    "account.delete_header": "🗑️ Delete my account (GDPR Art. 17)",
    "account.delete_warning": "Account deletion is handled by the administrator. "
                              "Send a request to **1x7xxxxxxx@gmail.com** with the subject "
                              "**'Delete my account — [your username]'**. "
                              "Your data will be deleted within 30 days.",
}
