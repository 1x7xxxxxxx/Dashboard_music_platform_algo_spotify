#!/usr/bin/env python3
"""The nightly recap that reaches the inbox the owner reads — sent from GitHub Actions.

Type: Utility
Uses: src/utils/nightly_recap.py (GitHub verdicts, public Actions API),
      tools/dev/mail_red_verdict.py (send, SMTP env), urllib (production /health)
Triggers: .github/workflows/nightly-recap.yml (every night, 06:47 UTC)
Persists in: nothing — one mail, every night

R181 (2026-09-26). The production recap (`alert_monitor`) is mailed to `ALERT_EMAIL`, an
inbox nobody reads — measured the day it was deployed. Changing it is an edit of the
production `.env`, the owner's gesture. GitHub-side mails DO reach the read inbox (the CI
break mails arrive there), so this recap travels that road: the three workflows' verdicts
(cancelled ≠ red, unreadable ≠ green) and a probe of production's public `/health`
(unreachable ⇒ red, never « unknown »). Sent EVERY night, calm or not: its absence must
mean « the recap itself stopped », never « nothing to say ».
"""
from __future__ import annotations

import html
import os
import sys
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.utils import nightly_recap  # noqa: E402
from src.utils.email_identity import from_header  # noqa: E402
from src.utils.safe_error import safe_error  # noqa: E402
import mail_red_verdict as mail  # noqa: E402

HEALTH_URL = os.environ.get("PROD_API_URL", "https://api.streamlytics.fr") + "/health"


def probe_prod(url: str = HEALTH_URL, opener=urllib.request.urlopen) -> dict:
    """{state, detail}: 2xx ⇒ green; any other status or no answer ⇒ red."""
    # A named User-Agent: Cloudflare answers 403 to Python's default `Python-urllib/…`
    # (measured 2026-09-26 — the first recap reported a healthy production as red).
    req = urllib.request.Request(url, headers={"User-Agent": "streamlytics-nightly-recap/1.0"})
    try:
        with opener(req, timeout=20) as resp:
            code = resp.status
    except Exception as exc:  # noqa: BLE001 — an unreachable production is RED
        return {"state": "red", "detail": safe_error(exc, limit=160)}
    return {"state": "green" if 200 <= code < 300 else "red", "detail": f"HTTP {code}"}


def discipline_section(report: dict | None) -> tuple[str, bool]:
    """R197 — the roadmap discipline of the last 14 days, in the mail the owner reads."""
    if report is None:
        return "<p>❔ <b>Roadmap</b> — sonde illisible cette nuit.</p>", False
    import roadmap_discipline
    bad = roadmap_discipline.failing(report)
    g = report["git"]
    icon = "🔴" if bad else "✅"
    text = (f"{g['ok']}/{g['product']} commits de code inscrits AVANT dans la roadmap "
            f"(14 j) · contournements : {g['bypass']} · lignes ouvertes : "
            f"{len(report['open_rows_age_days'])}")
    more = "".join(f"<br>{html.escape(b)}" for b in bad)
    return f"<p>{icon} <b>Roadmap</b> — {html.escape(text)}{more}</p>", bool(bad)


def build(verdicts: dict, prod: dict, now: datetime,
          discipline: dict | None | str = "absent") -> tuple[str, str, bool]:
    """(subject, HTML body, any red). Pure."""
    section, gh_red = nightly_recap.github_section(verdicts)
    red = gh_red or prod["state"] != "green"
    if discipline != "absent":
        extra, d_red = discipline_section(discipline)
        section, red = section + extra, red or d_red
    headline = "🔴 quelque chose demande ton attention" if red else "nuit calme, rien à signaler"
    icon = "✅" if prod["state"] == "green" else "🔴"
    prod_html = (f"<p>{icon} <b>Production</b> (<code>/health</code>) — "
                 f"{html.escape(prod['detail'])}</p>")
    subject, body = nightly_recap.short_recap(now.strftime("%Y-%m-%d %H:%M UTC"), headline,
                                              prod_html + section)
    return subject, body, red


def main() -> int:
    env = dict(os.environ)
    missing = [k for k in mail._REQUIRED if not env.get(k)]
    if missing:
        print(f"❌ recap not sent — missing: {', '.join(missing)}")
        return 1
    try:
        verdicts = nightly_recap.github_verdicts()
    except Exception as exc:  # noqa: BLE001 — the recap still leaves, saying it could not read
        verdicts = {"GitHub": {"state": "unreadable", "since": None, "url": None,
                               "error": safe_error(exc)}}
    try:
        import roadmap_discipline
        discipline = roadmap_discipline.measure(days=14, calls=None)
    except Exception as exc:  # noqa: BLE001 — the recap still leaves, saying it could not read
        print(f"⚠️ roadmap discipline unreadable: {safe_error(exc)}")
        discipline = None
    subject, body, red = build(verdicts, probe_prod(), datetime.now(timezone.utc), discipline)
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, from_header(), env["PROD_HEALTH_MAIL_TO"]
    msg.set_content("Récap de la nuit — version HTML jointe.")
    msg.add_alternative(body, subtype="html")
    mail.send(env, msg)
    print(f"✅ recap sent ({'red' if red else 'calm'}): {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
