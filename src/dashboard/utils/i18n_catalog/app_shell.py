"""EN strings — app shell (verify/unsubscribe routes, sidebar panels, shared ui helpers)."""

EN = {
    # Email verification route (?page=verify)
    "app.verify_title": "🎵 Email verification",
    "app.verify_invalid_link": "Invalid verification link.",
    "app.verify_used_link": "This verification link is invalid or has already been used.",
    "app.verify_already": "Account **{u}** is already verified. [Sign in](/)",
    "app.verify_expired": ("This verification link has expired (48 hours). "
                           "Please register again or use the resend option on the "
                           "sign-in page."),
    "app.verify_success": ("✅ Email verified! Welcome, **{u}**. "
                           "We've emailed you a welcome guide. You can now [sign in](/)."),
    "app.sending_welcome": "Sending your welcome guide…",
    # Unsubscribe route (?page=unsubscribe)
    "app.unsub_title": "📧 Unsubscribe",
    "app.unsub_invalid": "Invalid unsubscribe link.",
    "app.unsub_expired": "Invalid or expired unsubscribe link.",
    "app.unsub_success": ("✅ Done — you will no longer receive marketing communications. "
                          "You can re-enable the option anytime in "
                          "\"My account → Communications\"."),
    # DB health
    "app.db_unreachable_short": "Database unreachable.",
    "app.db_unreachable_retry": "Database unreachable. Please try again later.",
    "app.db_health_error": ("❌ **PostgreSQL database unreachable.** "
                            "Make sure Docker is running: `docker-compose up -d`"),
    # Sidebar — Live Activity
    "app.live_header": "### 🟢 Live Activity",
    "app.live_active": "🟢 Active",
    "app.live_active_help": "Artists active within the last 5 minutes",
    "app.live_total": "👥 Total",
    "app.live_total_help": "Total active artist accounts",
    # Sidebar — data collection panel
    "app.run_all_collections": "🚀 Run ALL collections",
    "app.syncing": "Synchronizing...",
    "app.launched": "Launched!",
    # Cookie notice (RGPD Art. 13)
    "app.cookie_notice": ("🍪 This platform uses a single session cookie (`music_dashboard`) "
                          "strictly necessary for authentication. No tracking, no "
                          "third-party cookies. [Privacy Policy](?page=privacy)"),
    # Central view error guard
    "app.view_error": ("❌ An error occurred on this page. Please try again; "
                       "the administrator has been notified if the problem persists."),
    # Shared ui helpers (utils/ui.py)
    "ui.full_history": "Full history",
    "ui.year_n": "Year {y}",
    "ui.custom_range": "Custom range",
    "ui.range": "Range",
}
