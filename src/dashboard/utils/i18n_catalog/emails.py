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
    "email.verify.expiry": "This link expires in 48 hours. "
                           "If you did not create an account, ignore this email.",

    # --- "You already have an account" notice (R23) ---
    # Sent instead of a verification email when the address is already registered.
    # The page renders the same screen either way; this is what stops that identical
    # screen from dead-ending a user who simply forgot they had signed up.
    "email.exists.subject": "Your streaMLytics account already exists",
    "email.exists.title": "You already have a streaMLytics account",
    "email.exists.greeting": "Hi <strong>{username}</strong>,",
    "email.exists.body": "Someone just tried to sign up with this email address. "
                         "An account already exists — log in instead of creating a "
                         "second one.",
    "email.exists.button": "Log in",
    "email.exists.ignore": "If this wasn't you, ignore this email: no account was "
                           "created and nothing changed on yours.",

    # --- Trial expiry reminder (J-3) ---
    "email.trial_end.subject": "Your Premium access ends in 3 days",
    "email.trial_end.title": "Your Premium month ends on {date}",
    "email.trial_end.intro": "Hi {name} — your free full access is coming to an end. "
                             "Nothing happens without you: your account simply returns "
                             "to <strong>Free</strong>.",
    "email.trial_end.keep_header": "What you keep, for ever:",
    "email.trial_end.keep": "Your data, your connections, your per-platform analytics, "
                            "and the CSV export of everything collected. Nothing is "
                            "deleted, nothing is locked.",
    "email.trial_end.lose_header": "What you lose:",
    "email.trial_end.lose": "Discover Weekly prediction, revenue forecasts, the "
                            "ads × streams cross-analysis, and your weekly PDF report.",
    "email.trial_end.cta": "See my options",
    # --- Welcome email ---
    "email.welcome.subject": "🎵 Welcome to streaMLytics — your getting-started guide",
    "email.welcome.title": "🎵 Welcome to streaMLytics, {username}!",
    "email.welcome.trial": "Your account is ready with "
                           "<strong>{trial_days} days of full access (Premium)</strong> "
                           "included. 🎁",
    # Rewritten 2026-09-04: value first, ONE thing to do. The five ordered steps were
    # the assistant's job, already on screen when the artist logged in — read twice,
    # once in a mail one cannot act on, a welcome becomes homework.
    "email.welcome.value_header": "What streaMLytics brings you:",
    "email.welcome.value1": "<strong>All your data in one place</strong>, pulled every "
                            "day automatically and encrypted: Spotify, Spotify for "
                            "Artists, Instagram, Meta Ads, YouTube, SoundCloud, Apple "
                            "Music, distributors.",
    "email.welcome.value2": "<strong>Spotify algorithm predictions</strong> — when a "
                            "track is likely to trigger Discover Weekly or Release "
                            "Radar, from models trained on your own data.",
    "email.welcome.value3": "<strong>Campaign optimisation</strong> (Instagram Ads, "
                            "Meta Ads) — linking what you spend to what it produces "
                            "in streams.",
    "email.welcome.one_thing": "<strong>One thing to get started:</strong> follow the "
                               "<strong>getting-started guide</strong>. It is attached "
                               "to this e-mail, and in the app under "
                               "“📋 Getting started”.",
    "email.welcome.cta": "Open my getting-started guide",
    "email.welcome.guide_note": "📎 The <strong>getting-started PDF guide</strong> is "
                                "attached to this e-mail.",

    # --- Unsubscribe footer ---
    "email.unsub.static": "To stop receiving these emails, untick the option in "
                          "<em>My account → Communications</em>.",
    "email.unsub.notice": "You receive this email because you have a streaMLytics account. ",
    "email.unsub.link": "Unsubscribe from communications",
    "email.unsub.suffix": " (automatically unticks the email option on your account).",
}
