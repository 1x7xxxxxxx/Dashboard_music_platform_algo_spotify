"""R430 — the « Faire piloter mes campagnes » request, sent FROM the app.

Type: Utility
Uses: smtplib, src.utils.verification_email (SMTP settings), src.utils.email_identity
Triggers: src/dashboard/views/service.py (the send button)
Persists in: nothing — the owner's inbox IS the record (one mail = one request)

Owner, 2026-10-06: « l'envoyer depuis ma messagerie … j'aime pas trop. Il faudrait que
ça parte direct dès qu'on l'envoie avec l'app » — and the reason given was tracing:
counting requests by counting mails. A mailto link cannot be counted (the artist may
never press send in their own client); a mail the app sends can.

The recipient is FIXED (`SERVICE_CONTACT_EMAIL`), never read from the page: the only
user input is the body and the Reply-To, so this path cannot be turned into a relay to
an arbitrary address. Header values are stripped of CR/LF before use.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import parseaddr

from src.utils.email_identity import from_header
from src.utils.instance_identity import instance_label
from src.utils.safe_error import safe_error
from src.utils.verification_email import _SMTP_TIMEOUT_S, _smtp_config

logger = logging.getLogger(__name__)

#: A stable subject prefix: the owner filters and counts requests on it.
SUBJECT_PREFIX = "🎯 Demande de pilotage"


def _one_line(value: str) -> str:
    return " ".join((value or "").split())


def subject_for(artist: str) -> str:
    who = _one_line(artist)[:80]
    return f"{instance_label()}{SUBJECT_PREFIX}" + (f" — {who}" if who else "")


def send_service_request(to: str, artist: str, reply_to: str, body: str) -> bool:
    """Send the request to the owner. Non-raising: False when SMTP is absent or fails."""
    cfg = _smtp_config()
    if not cfg.get("user") or not cfg.get("password"):
        logger.warning("SMTP not configured — service request not sent.")
        return False
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = from_header()
    msg["To"] = to
    msg["Subject"] = subject_for(artist)
    addr = parseaddr(_one_line(reply_to))[1]
    if "@" in addr:
        msg["Reply-To"] = addr
    try:
        with smtplib.SMTP(cfg.get("host", "smtp.gmail.com"), int(cfg.get("port", 587)),
                          timeout=_SMTP_TIMEOUT_S) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
    except Exception as e:  # noqa: BLE001 — the caller shows a fallback, never a crash
        logger.error("Service request not sent: %s", safe_error(e))
        return False
    logger.info("Service request sent for %s", _one_line(artist) or "?")
    return True
