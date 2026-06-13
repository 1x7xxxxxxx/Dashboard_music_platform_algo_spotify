"""EN catalog for transactional emails (verification + welcome + unsubscribe footer).

Keys are consumed by src/utils/verification_email.py via i18n.translate(key, FR, lang).
FR is the inline default at each call site; only EN lives here. HTML fragments are
intentional — the email bodies interpolate these directly.
"""

EN = {
    # --- Verification email ---
    "email.verify.subject": "🎵 Verify your streaMLytics account",
    "email.verify.title": "🎵 Confirm your streaMLytics account",
    "email.verify.greeting": "Hi <strong>{username}</strong>,",
    "email.verify.body": "Click the button below to verify your email address and "
                         "activate your account.",
    "email.verify.button": "Verify my email",
    "email.verify.copy": "Or copy this link: {url}",
    "email.verify.expiry": "This link expires in 24 hours. "
                           "If you did not create an account, ignore this email.",

    # --- Welcome email ---
    "email.welcome.subject": "🎵 Welcome — your first steps on streaMLytics",
    "email.welcome.title": "🎵 Welcome to streaMLytics, {username}!",
    "email.welcome.trial": "Your account is ready with "
                           "<strong>{trial_days} days of full access (Premium)</strong> "
                           "included. 🎁",
    "email.welcome.steps_header": "Your first steps, in order:",
    "email.welcome.step1": "<strong>Enter your API credentials</strong> (Spotify, YouTube, "
                           "SoundCloud, Meta Ads) on the <em>🔑 API Credentials</em> page.",
    "email.welcome.step2": "<strong>Import your CSV files</strong> (Spotify for Artists, "
                           "Apple Music, iMusician) via the <em>📥 CSV Import</em> page — "
                           "follow the <strong>attached PDF guide</strong> to export and "
                           "upload them.",
    "email.welcome.step3": "<strong>Map your Meta Ads campaigns to your Spotify tracks</strong> "
                           "in <em>🔗 Spotify × Meta Ads mapping</em> (do this <em>before</em> "
                           "collection, to link spend and streams from the first run).",
    "email.welcome.step4": "<strong>Start collection</strong> via the "
                           "“🚀 Run ALL collections” button in the sidebar.",
    "email.welcome.step5": "Explore your analytics dashboards and the “Road to Algo” "
                           "ML prediction.",
    "email.welcome.cta": "Set up my dashboard (2 min)",
    "email.welcome.guide_note": "📎 The <strong>getting-started PDF guide (API + CSV import)</strong> "
                                "is attached.<br>Need help? See the “📋 Getting started” page in "
                                "the app.",

    # --- Unsubscribe footer ---
    "email.unsub.static": "To stop receiving these emails, untick the option in "
                          "<em>My account → Communications</em>.",
    "email.unsub.notice": "You receive this email because you have a streaMLytics account. ",
    "email.unsub.link": "Unsubscribe from communications",
    "email.unsub.suffix": " (automatically unticks the email option on your account).",
}
