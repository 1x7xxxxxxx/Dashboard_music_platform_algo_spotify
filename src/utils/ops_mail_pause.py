"""The one switch that pauses the owner's operational mails (R572).

Type: Utility
Uses: nothing (stdlib-free constant — imported by tools/ scripts that avoid the app package)
Triggers: EmailAlert.send_alert / deliver_or_raise / dag_failure_callback,
          tools/dev/mail_red_verdict.send, tools/notify_schema_drift.py
Persists in: nothing

Owner, 2026-10-15: « ils ne me servent à rien maintenant, on pourra les remettre quand
l'app sera en prod ». No artist uses the app yet, so the nightly alert, the CI-break
mail, the nightly recap, the prod-health red and the schema-drift mail are noise.

Paused here, in the code, rather than by an environment variable: the same flag must
reach a GitHub runner, an Airflow container and a host cron, and a constant reaches all
three with one commit — and is re-enabled the same way. What it does NOT pause: mails
addressed to an artist (`send_email`) and the account-deletion request, which a user
sends and expects answered (`essential=True`).

To resume the mails: set `OPS_MAIL_PAUSED = False`, push, deploy.
"""
from __future__ import annotations

OPS_MAIL_PAUSED = True


def paused_reason() -> str | None:
    """Why an operational mail to the owner must not leave, or None."""
    if OPS_MAIL_PAUSED:
        return ("owner ops mails paused (R572, src/utils/ops_mail_pause.py) — "
                "set OPS_MAIL_PAUSED = False to resume")
    return None
