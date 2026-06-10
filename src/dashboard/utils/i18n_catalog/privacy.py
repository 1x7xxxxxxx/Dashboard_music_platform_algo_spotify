"""EN catalog for the privacy policy view."""

EN = {
    "privacy.title": "Privacy policy",
    "privacy.last_updated": "Last updated: March 2026",
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
| Password (bcrypt hashed) | Authentication | Performance of contract |
| API credentials (encrypted) | Music data collection | Performance of contract |
| Streaming data (Spotify, YouTube…) | Music performance analysis | Performance of contract |
""",
    "privacy.s3": """
## 3. Use of your email address

Your email is used for:
- **Account verification** (transactional email, mandatory)
- **Marketing communications** (newsletters, updates) — **only if you consented**
  at registration. You can withdraw this consent at any time.
""",
    "privacy.s4": """
## 4. Retention periods

- **Account data**: kept as long as the account is active. Deleted upon request.
- **Streaming data**: kept 3 years for historical analysis purposes.
- **Technical logs**: 30 days.
""",
    "privacy.s5": """
## 5. Security

- Passwords are **irreversibly hashed** (bcrypt) — nobody can read them.
- API tokens are **encrypted** (AES-128 Fernet) before database storage.
- The database is hosted locally or on a secured server.
""",
    "privacy.s6": """
## 6. Your rights (GDPR Art. 15-22)

You have the following rights, exercised by email to **1x7xxxxxxx@gmail.com**:

- **Right of access** (Art. 15) — obtain a copy of your data
- **Right to rectification** (Art. 16) — correct inaccurate data
- **Right to erasure** (Art. 17) — delete your account and your data
- **Right to object** (Art. 21) — object to marketing communications
- **Right to data portability** (Art. 20) — receive your data in a readable format

Response time: 30 days maximum.
""",
    "privacy.s7": """
## 7. Cookies

This platform uses **a single session cookie** (`music_dashboard`) to keep you
signed in. This cookie is strictly necessary for the service to work —
it does not track your browsing and is not shared with third parties.
""",
    "privacy.s8": """
## 8. Data transfers

Your data is **neither sold nor transferred** to third parties.
Third-party APIs (Spotify, YouTube, Meta, SoundCloud) are contacted only with
your own credentials, in accordance with their respective terms of use.
""",
    "privacy.s9": """
## 9. Contact & complaints

**GDPR contact**: 1x7xxxxxxx@gmail.com

You may also lodge a complaint with the **CNIL** (French data protection authority):
[www.cnil.fr](https://www.cnil.fr) — 3 place de Fontenoy, 75007 Paris.
""",
    "privacy.back": "[← Back to home](/)",
}
