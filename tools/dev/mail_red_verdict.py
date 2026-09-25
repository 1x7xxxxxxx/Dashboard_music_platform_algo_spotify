#!/usr/bin/env python3
"""Mail a red workflow verdict to the owner — the channel GitHub notifications are not.

Type: Utility
Uses: smtplib, email.message, os, sys
Triggers: .github/workflows/prod-health.yml (step `if: failure()`)
Depends on: repo secrets SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM,
            PROD_HEALTH_MAIL_TO — copied from the production SMTP relay (Brevo)
Persists in: nothing — one outbound mail, exit 0 or 1

On 2026-09-24 production was down from 11:45 to 20:51 UTC and `prod-health.yml` saw it
at 11:45. Its red went to GitHub notifications on an address nobody reads, and the
outage was found that evening by a failed `make deploy`. A red that reaches nobody is
not an alert (R166).

It must run from OUTSIDE the server: the evening mail of the `alert_monitor` DAG lives
on the machine that was down, so it could not have said so. Missing configuration exits
1 and names what is missing — a mailer that skips in silence is the defect it replaces.
"""
from __future__ import annotations

import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.utils.email_identity import from_header  # noqa: E402 — stdlib-only module

_REQUIRED = ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "PROD_HEALTH_MAIL_TO")


def build_message(env: dict, detail: str | None = None) -> EmailMessage:
    """The mail for a red run, from the Actions environment.

    `detail` replaces the prod-down hint with what actually failed — the nightly security
    workflow reuses this sender (tools/dev/nightly_verdict.py) and its red is not an outage.
    """
    run_url = (f"{env.get('GITHUB_SERVER_URL', 'https://github.com')}/"
               f"{env.get('GITHUB_REPOSITORY', '?')}/actions/runs/{env.get('GITHUB_RUN_ID', '?')}")
    workflow = env.get("GITHUB_WORKFLOW", "workflow")
    msg = EmailMessage()
    msg["Subject"] = f"🔴 streaMLytics — {workflow} a échoué"
    msg["From"] = from_header()
    msg["To"] = env["PROD_HEALTH_MAIL_TO"]
    hint = (detail if detail is not None else
            "Si l'app ne répond plus, vérifier d'abord le compte Hetzner (impayé, blocage "
            "d'IP) avant de chercher sur le serveur — c'était la cause le 2026-09-24.")
    msg.set_content(f"Le contrôle « {workflow} » est ROUGE.\n\n{hint}\n\n"
                    f"Détail du run : {run_url}\n")
    return msg


def send(env: dict, msg: EmailMessage) -> None:
    with smtplib.SMTP(env["SMTP_HOST"], int(env.get("SMTP_PORT") or 587), timeout=30) as s:
        s.starttls()
        s.login(env["SMTP_USER"], env["SMTP_PASSWORD"])
        s.send_message(msg)


def main() -> int:
    missing = [k for k in _REQUIRED if not os.environ.get(k)]
    if missing:
        print(f"❌ cannot mail the red verdict: {', '.join(missing)} absent from the "
              "workflow env. Set them as repo secrets (`gh secret set <NAME>`).")
        return 1
    env = dict(os.environ)
    send(env, build_message(env))
    print(f"✅ red verdict mailed ({env.get('GITHUB_WORKFLOW', 'workflow')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
