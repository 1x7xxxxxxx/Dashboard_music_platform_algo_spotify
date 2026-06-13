#!/usr/bin/env python3
"""
Send a schema-drift alert email via the Brevo SMTP credentials in `.env`.

Standalone mirror of `src/utils/email_alerts.EmailAlert.send_alert` — the ops cron
script (`schema_drift_cron.sh`) calls this on drift WITHOUT importing the app package,
so a broken app import path can never silence the alert. Reads SMTP_HOST/PORT/USER/
PASSWORD (+ SMTP_FROM, ALERT_EMAIL) straight from the repo `.env`. Body on stdin.

Type: Utility
Uses: smtplib, repo-root .env (SMTP_* + ALERT_EMAIL)
Triggers: schema_drift_cron.sh (on drift)
Persists in: — (sends email; prints status to stdout/stderr)

Exit: 0 sent · 1 not-configured or send failure (caller logs the message).
"""
import argparse
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path


def _load_env(root: Path) -> None:
    """Populate os.environ from <root>/.env (does not override existing vars)."""
    f = root / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Email a schema-drift alert via Brevo SMTP")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--to", default=None, help="recipient (default: $ALERT_EMAIL, then $SMTP_FROM)")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    _load_env(root)

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM") or user
    recipient = args.to or os.getenv("ALERT_EMAIL") or os.getenv("SMTP_FROM")
    body = sys.stdin.read().strip() or "(no body)"

    if not all([host, user, password, recipient]):
        print("email not configured (SMTP_USER/SMTP_PASSWORD/recipient missing) — "
              "drift is logged only", file=sys.stderr)
        return 1

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = args.subject
    msg["From"] = sender
    msg["To"] = recipient

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        print(f"email send failed: {exc}", file=sys.stderr)
        return 1
    print(f"drift alert emailed to {recipient}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
