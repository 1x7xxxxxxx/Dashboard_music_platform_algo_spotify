"""Turn an exception into something safe to log or show.

Type: Utility
Uses: nothing (stdlib only — must be importable from collectors, DAGs and views)
Triggers: any `except` that formats an exception from a call carrying a credential
Persists in: nothing

Why this exists — measured 2026-08-22.

`requests` exception messages embed the full prepared URL. Several of our upstream
APIs take their credential as a QUERY PARAMETER:

  * Meta  — `access_token=`, and the token-exchange call also sends `client_secret=`
  * YouTube — `key=` (googleapiclient's HttpError.__repr__ embeds `self.uri`)

So `logger.error(f"failed: {e}")` on a DNS blip wrote the platform's shared System
User token, and its app secret, verbatim into the Airflow task log — persisted on
disk, readable in the Airflow UI, and forwarded into the DAG-failure email. No
attacker action required.

Blanking the message entirely was the wrong answer: the operator loses the one line
that says what broke. `redact()` keeps the shape and removes the values.
"""
from __future__ import annotations

import re

# Query-parameter names whose VALUE must never appear in a message. Matched
# case-insensitively, on the `name=value` pair, wherever it appears in the text.
_SECRET_PARAMS = (
    "access_token", "client_secret", "fb_exchange_token", "input_token",
    "key", "api_key", "apikey", "token", "password", "secret", "refresh_token",
)
_PARAM_RE = re.compile(
    r"(?i)\b(" + "|".join(_SECRET_PARAMS) + r")=([^&\s'\"<>]+)"
)
# Meta's app-credential form: `<app_id>|<app_secret>`.
_PIPE_SECRET_RE = re.compile(r"\b(\d{6,})\|([A-Za-z0-9]{8,})")


def redact(text: object) -> str:
    """Replace credential values with `***`, keeping the surrounding message."""
    out = str(text)
    out = _PARAM_RE.sub(lambda m: f"{m.group(1)}=***", out)
    out = _PIPE_SECRET_RE.sub(lambda m: f"{m.group(1)}|***", out)
    return out


def safe_error(exc: BaseException, limit: int = 300) -> str:
    """`TypeName: redacted message`, truncated.

    The type name is kept because it is the part an operator acts on — a
    `ConnectionError` and a `401` call for different responses, and a message that
    says only "an error occurred" costs a debugging session.
    """
    return f"{type(exc).__name__}: {redact(exc)}"[:limit]
