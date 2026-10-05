"""Exception kinds that decide whether a failure is retried — no dependency at all.

Type: Utility
Uses: nothing (stdlib only)
Triggers: `src.utils.retry.retry` reads `PermanentFailure` in its NON_RETRIABLE tuple
Depends on: nothing
Persists in: nothing

Kept apart from `retry.py` on purpose: `retry.py` imports `safe_error`, and a module that
imports `safe_error` enters the HTTP-redaction guard (`test_credentials_security.py`).
`credential_loader` subclasses this kind without becoming an HTTP module.
"""


class PermanentFailure(Exception):
    """A failure that a second attempt cannot repair and could make worse — never retried.

    R398 (c): a SoundCloud refresh_token that was rotated but not stored. The collector
    keeps the new token in memory, so a retry SUCCEEDS on it, the task goes green, and
    the token is lost with the old one already revoked.
    """
