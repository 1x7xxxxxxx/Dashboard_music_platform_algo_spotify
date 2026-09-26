"""Every `starttls()` verifies the server — the SMTP password never crosses an unverified TLS.

Type: Sub
Uses: ast over src/, tools/, airflow/
Depends on: nothing
Persists in: nothing

Found 2026-09-26 by the security review of the nightly recap workflow: `smtplib.starttls()`
without a `context` falls back to `ssl._create_stdlib_context()` — CERT_NONE, no hostname
check. The next line sends SMTP_PASSWORD. Anyone between the sender and the relay could
pose as the relay and collect the credentials. Six call sites shared the form: the GitHub
mailers, the schema-drift notifier, the verification mails and the production alerts.
The fix is `starttls(context=ssl.create_default_context())`.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_TREES = ("src", "tools", "airflow")


def unverified_starttls(source: str) -> list[int]:
    """Lines calling `.starttls(...)` without a verifying context. Pure.

    `context=None` is the unverified default spelled out, and a positional argument does
    not set `context` — both are refused (code-critic, 2026-09-26)."""
    def verified(call: ast.Call) -> bool:
        ctx = next((k.value for k in call.keywords if k.arg == "context"), None)
        return (not call.args and ctx is not None
                and not (isinstance(ctx, ast.Constant) and ctx.value is None))
    return [n.lineno for n in ast.walk(ast.parse(source))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "starttls" and not verified(n)]


def test_every_starttls_verifies_the_server() -> None:
    hits = []
    for tree in _TREES:
        for path in sorted((_ROOT / tree).rglob("*.py")):
            try:
                lines = unverified_starttls(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            hits += [f"{path.relative_to(_ROOT)}:{ln}" for ln in lines]
    assert not hits, (f"{hits} : starttls() without a context does not verify the server — "
                      "write `starttls(context=ssl.create_default_context())`.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """The bare call is caught; the verified call is not."""
    assert unverified_starttls("s.starttls()\n") == [1]
    assert unverified_starttls("s.starttls(context=None)\n") == [1]
    assert unverified_starttls("s.starttls(keyfile)\n") == [1]
    assert unverified_starttls("import ssl\ns.starttls(context=ssl.create_default_context())\n") == []
