"""EN catalog for the privacy policy view."""

EN = {
    "privacy.title": "Privacy policy",
    "privacy.last_updated": "Last updated: 23 September 2026",
    "privacy.s1": """
## 1. Data controller

The **Music Cross Platform Dashboard** platform is operated by its administrator.
For any request regarding your personal data, contact:
**1x7xxxxxxx@gmail.com**
""",
    "privacy.s2": """
## 2. Data collected

| Data | Purpose | Legal basis |
|---|---|---|
| Artist name, slug | Account identification | Performance of contract |
| Username | Platform sign-in | Performance of contract |
| Email address | Account verification, communication | Performance of contract + Consent (marketing) |
| Password (bcrypt hashed) — none if you sign in with Google | Authentication | Performance of contract |
| Google account identifier — only if you use Google sign-in | Recognising you on later sign-ins | Performance of contract |
| API credentials (encrypted) | Music data collection | Performance of contract |
| Streaming data (Spotify, YouTube…) | Music performance analysis | Performance of contract |
| Pages viewed and actions in the app (internal log, no cookie) | Understanding usage to improve the service | Legitimate interest |
""",
    "privacy.google": """
## 3. Sign in with Google (optional)

You can sign in with your Google account instead of a password. It is optional:
email-and-password registration remains available.

**What we ask Google for**: only your basic identity — the `openid`, `email` and
`profile` permissions. We have **no access** to your Gmail, Drive, calendar, contacts
or YouTube channel, and Google never sends us your password.

| Data received from Google | What we do with it | Kept? |
|---|---|---|
| Google account identifier | Recognising you on later sign-ins (it never changes, unlike the address) | Yes, as long as the account exists, with the date it was linked |
| Email address, verified by Google | Linking your existing account the first time, or creating yours | Yes — it is your account's address |
| Display name | Pre-filling the registration form, which you can edit | No |

We keep **no Google access token** and never contact Google on your behalf after
sign-in. A Google account bypasses no check: a deactivated account stays deactivated,
and two-factor authentication is still required if you enabled it.

**Revoking access**: from
[myaccount.google.com/connections](https://myaccount.google.com/connections). To
remove the Google identifier from your account, or the account itself, write to us
(section 7).
""",
    "privacy.s3": """
## 4. Use of your email address

Your email is used for:
- **Account verification** (transactional email, mandatory)
- **Marketing communications** (newsletters, updates) — **only if you consented**
  at registration. You can withdraw this consent at any time.
""",
    "privacy.s4": """
## 5. Retention periods

- **Account data**: kept as long as the account is active. Deleted upon request.
- **Streaming data**: kept 3 years for historical analysis purposes.
- **Technical logs**: 30 days.
- **Usage log and Google identifier**: as long as the account is active, erased with it.
""",
    "privacy.s5": """
## 6. Security

- Passwords are **irreversibly hashed** (bcrypt) — nobody can read them.
- An account created with Google **has no password** on our side: a database leak would expose nothing replayable for it.
- API tokens are **encrypted** (AES-128 Fernet) before database storage.
- The database is hosted locally or on a secured server.
""",
    "privacy.s6": """
## 7. Your rights (GDPR Art. 15-22)

You have the following rights, exercised by email to **1x7xxxxxxx@gmail.com**:

- **Right of access** (Art. 15) — obtain a copy of your data
- **Right to rectification** (Art. 16) — correct inaccurate data
- **Right to erasure** (Art. 17) — delete your account and your data
- **Right to object** (Art. 21) — object to marketing communications
- **Right to data portability** (Art. 20) — receive your data in a readable format

Response time: 30 days maximum.
""",
    "privacy.s7": """
## 8. Cookies

This platform only sets **strictly necessary** cookies:

| Cookie | Purpose | Lifetime |
|---|---|---|
| `_streamlit_xsrf` | Protection against request forgery | Session |
| `_streamlit_user` | Keeping your **Google** sign-in (signed, not readable by scripts) — absent if you use a password | 30 days, removed on sign-out |

No advertising, audience-measurement or third-party cookie. The usage log of section 2
is kept server-side and sets no cookie.
""",
    "privacy.s8": """
## 9. Data transfers

Your data is **neither sold nor transferred** to third parties.
Third-party APIs (Spotify, YouTube, Meta, SoundCloud) are contacted only with
your own credentials, in accordance with their respective terms of use.
If you use Google sign-in, Google acts as **identity provider**: it knows you signed
in to streaMLytics, under its own privacy policy.
""",
    "privacy.s9": """
## 10. Contact & complaints

**GDPR contact**: 1x7xxxxxxx@gmail.com

You may also lodge a complaint with the **CNIL** (French data protection authority):
[www.cnil.fr](https://www.cnil.fr) — 3 place de Fontenoy, 75007 Paris.
""",
    "privacy.back": "[← Back to home](/)",
}
