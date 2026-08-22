"""Envoi d'alertes email depuis les DAGs Airflow et le monitor de fraîcheur."""
import os
import smtplib
import logging
from email import encoders
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.utils.safe_error import safe_error

logger = logging.getLogger(__name__)


class AlertDeliveryError(RuntimeError):
    """The one alert whose silence IS the incident could not be delivered."""


class EmailAlert:
    def __init__(self):
        # Why the last failure happened, not just that it did. `send_alert` returns a
        # bare False for two situations with entirely different fixes — "this
        # container has no SMTP env" (the 2026-08-16→18 outage, class
        # `env-not-wired-to-service`) and "SMTP is configured and the send failed".
        # An operator woken by a red task needs to know which.
        self.last_error: str | None = None
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.alert_email = os.getenv('ALERT_EMAIL')

    def send_alert(self, subject: str, body: str) -> bool:
        """Envoie une alerte par email. Retourne True si succès."""
        self.last_error = None
        if not self.smtp_user or not self.smtp_password or not self.alert_email:
            missing = [n for n, v in (("SMTP_USER", self.smtp_user),
                                      ("SMTP_PASSWORD", self.smtp_password),
                                      ("ALERT_EMAIL", self.alert_email)) if not v]
            self.last_error = (
                f"SMTP not configured in this container: {', '.join(missing)} absent")
            logger.warning("⚠️ Email alerts non configurées (%s manquant(s))",
                           ", ".join(missing))
            return False
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = self.alert_email
            msg['Subject'] = f"🚨 Dashboard Alert: {subject}"
            msg.attach(MIMEText(body, 'html'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"✅ Alerte envoyée : {subject}")
            return True
        except Exception as e:
            self.last_error = f"SMTP configured, send failed: {safe_error(e)}"
            logger.error(f"❌ Échec envoi email : {safe_error(e)}")
            return False

    def send_email(self, to_email: str, subject: str, html: str,
                   attachment_bytes: bytes | None = None,
                   attachment_name: str = "rapport.pdf") -> bool:
        """Send one HTML email to a specific recipient, optional PDF attachment.

        Env-var SMTP (DAG context). Unlike send_alert (admin-only ALERT_EMAIL,
        no attachment), this targets a client address and can attach a PDF.
        Non-raising — returns False (and logs) when SMTP creds are missing or send fails.
        """
        if not self.smtp_user or not self.smtp_password or not to_email:
            logger.warning("⚠️ SMTP non configuré ou destinataire manquant — email '%s' ignoré.",
                           subject)
            return False
        try:
            msg = MIMEMultipart('mixed')
            msg['From'] = self.smtp_user
            msg['To'] = to_email
            msg['Subject'] = subject
            body = MIMEMultipart('alternative')
            body.attach(MIMEText(html, 'html'))
            msg.attach(body)
            if attachment_bytes:
                part = MIMEBase('application', 'pdf')
                part.set_payload(attachment_bytes)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment', filename=attachment_name)
                msg.attach(part)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info("✅ Email '%s' envoyé à %s", subject, to_email)
            return True
        except Exception as e:
            logger.error("❌ Échec envoi email '%s' à %s : %s", subject, to_email, e)
            return False


def deliver_or_raise(subject: str, body: str) -> None:
    """Send, or raise naming WHY. For the one path whose silence is the incident.

    `send_alert` stays non-raising on purpose — six callers depend on that, including
    `dag_failure_callback` below, which runs inside a failure callback where a raise
    is swallowed anyway. This wrapper exists for the consolidated nightly alert, and
    only for it.

    Measured, 2026-08-22. `alert_monitor.py` called `send_alert(...)` and threw the
    result away, then logged "Consolidated alert sent" on the next line
    unconditionally. Production logs show three consecutive nights — 16, 17 and 18
    August — writing that sentence immediately after this module warned "Email alerts
    non configurées". Three nights of findings evaporated while the task reported
    success. The findings themselves were correct and complete; nobody read them,
    because nobody received them.

    A monitor that cannot prove its own output left the building is not a monitor.
    """
    alert = EmailAlert()
    if alert.send_alert(subject, body):
        return
    raise AlertDeliveryError(
        f"the nightly alert was NOT delivered — {alert.last_error or 'unknown reason'}. "
        f"Subject was: {subject!r}"
    )


def dag_failure_callback(context):
    """
    Callback Airflow à brancher sur on_failure_callback.

    Usage dans default_args :
        from src.utils.email_alerts import dag_failure_callback
        default_args = { ..., 'on_failure_callback': dag_failure_callback }
    """
    dag_id = context.get('dag').dag_id
    task_instance = context.get('task_instance')
    task_id = task_instance.task_id if task_instance else 'N/A'
    run_id = context.get('run_id', 'N/A')
    exception = context.get('exception', 'N/A')
    log_url = task_instance.log_url if task_instance else 'N/A'

    subject = f"DAG {dag_id} — task {task_id} FAILED"
    body = f"""
    <h3>❌ Échec DAG : <b>{dag_id}</b></h3>
    <ul>
        <li><b>Task :</b> {task_id}</li>
        <li><b>Run ID :</b> {run_id}</li>
        <li><b>Erreur :</b> {exception}</li>
        <li><b>Logs :</b> <a href="{log_url}">{log_url}</a></li>
    </ul>
    <p style="color:#888;font-size:0.85em;">Généré automatiquement par le dashboard Music Platform.</p>
    """
    try:
        EmailAlert().send_alert(subject, body)
    except Exception as e:
        logger.error(f"dag_failure_callback : envoi email échoué ({safe_error(e)})")
