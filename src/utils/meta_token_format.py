"""Reject a Meta token that is malformed BEFORE anything tries to use it.

Type: Utility
Uses: nothing (stdlib)
Triggers: src/utils/central_apps.py::check_meta, .claude/scripts/check_env.py
Persists in: nothing (pure)

Measured 2026-08-21. The production `META_ACCESS_TOKEN` began with `EEAA…`. Meta
tokens begin with `EAA`: the stored value carried ONE stray leading character, a
paste that grabbed a neighbouring letter. Every Graph call answered
`Malformed access token` (code 190), and the natural reading of that message is
"the token expired" — which sends you regenerating instead of looking at the
string. Strip the extra character and Meta answers something entirely different
("the session has been invalidated"), i.e. it recognises a real token.

Cost of not catching it: Meta and Instagram collected nothing for weeks, and the
first diagnosis blamed expiry.

This checks SHAPE only — never validity. A well-formed token can still be revoked,
and a rejected one is certainly wrong. Shape is cheap, offline, and catches the
class of error a human makes with a clipboard.
"""

from __future__ import annotations

# Meta user / System User access tokens are base64url-ish and start with this.
_PREFIX = "EAA"
_MIN_LENGTH = 40


def token_format_problem(token: str | None) -> str | None:
    """Return a human-readable problem, or None when the shape is plausible."""
    if token is None or not token.strip():
        return None  # absence is a different problem, reported elsewhere
    t = token.strip()

    if t != token:
        return "the value has leading or trailing whitespace"
    if t.startswith('"') or t.endswith('"') or t.startswith("'") or t.endswith("'"):
        return "the value is wrapped in quotes — .env needs it bare"
    if not t.startswith(_PREFIX):
        # The stray-character case, named explicitly: it is by far the most likely.
        if _PREFIX in t[:6]:
            extra = t[: t.index(_PREFIX)]
            return (f"there are {len(extra)} extra character(s) ({extra!r}) before the "
                    f"'{_PREFIX}' prefix — the paste grabbed too much")
        return f"it does not start with '{_PREFIX}', which every Meta token does"
    if len(t) < _MIN_LENGTH:
        return f"it is only {len(t)} characters long; a real token is far longer"
    return None
