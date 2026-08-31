"""Envoi d'alertes email depuis les DAGs Airflow et le monitor de fraîcheur."""
import os
import smtplib
import logging
from email import encoders
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.utils.email_identity import from_header
from src.utils.instance_identity import instance_label
from src.utils.safe_error import redact, safe_error

logger = logging.getLogger(__name__)

# Reaching a CLIENT is a decision, never a side effect of a data condition.
# Read at call time, not at import: a DAG process is long-lived, and an operator
# who sets the variable expects the next run to honour it.
_ARTIST_MAIL_OPT_IN = "STREAMLYTICS_ALLOW_ARTIST_EMAIL"
_TRUTHY = {"1", "true", "yes", "on"}


def _artist_mail_opted_in() -> bool:
    """Has someone explicitly decided we may write to tenants?

    Deliberately the same shape as `EmailAlert._OPT_IN`: a vague value is not an
    opt-in. "maybe", "" and "0" all mean no, so a half-configured environment
    stays silent rather than guessing in the direction that mails a stranger.
    """
    return (os.getenv(_ARTIST_MAIL_OPT_IN) or "").strip().lower() in _TRUTHY


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

    # Opt-in escape hatch, for the one legitimate case: deliberately testing the mail
    # itself from a dev box. Explicit, per-run, and never a default.
    _OPT_IN = "STREAMLYTICS_ALLOW_NONPROD_EMAIL"

    def _outbound_blocked(self) -> str | None:
        """Why this instance must not put a message on the wire, or None.

        Added 2026-08-26, after a LOCAL scheduler mailed a real inbox twice in one
        evening — a session had restarted the local Postgres for the test suite, the
        long-idle scheduler got its database back and replayed its scheduled runs.

        The 2026-08-24 fix for the same event added the `[LOCAL]` subject prefix. It
        was a LABELLING fix for a SENDING problem: the mail still arrived, still
        looked like an incident, and still had to be read before it could be
        dismissed. Naming the instance is necessary and it is not sufficient — the
        cost of these alerts is paid on receipt, not on inspection.

        Safe to make silence the default here ONLY because `STREAMLYTICS_ENV` is a
        required variable for `airflow_scheduler` in `tools/check_env_parity.py`,
        which `tools/deploy.sh` runs and fails on. Without that pairing this gate
        would turn a missing variable into a silent production — and the silence of
        an alert IS the incident (`AlertDeliveryError`).
        """
        from src.utils.instance_identity import instance_env, is_production

        if is_production():
            return None
        if str(os.getenv(self._OPT_IN, "")).strip().lower() in {"1", "true", "yes"}:
            return None
        return (f"instance '{instance_env()}' is not production — not sending. "
                f"Set {self._OPT_IN}=1 for this run to send anyway.")

    def send_alert(self, subject: str, body: str) -> bool:
        """Envoie une alerte par email. Retourne True si succès."""
        self.last_error = None
        blocked = self._outbound_blocked()
        if blocked:
            self.last_error = blocked
            logger.info("✉️  suppressed (%s): %s", blocked, subject)
            return False
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
            # PAS `self.smtp_user` : chez un relais, le login est un compte technique
            # (`ae8df8001@smtp-brevo.com` en prod) et non l'adresse d'expédition. Le
            # relais y substitue alors l'expéditeur par défaut du compte — c'est de là
            # que venait le nom « Music Cross Platform Dashboard & Trigger Spotify »
            # sur toutes les alertes (R38, mesuré 2026-08-23).
            msg['From'] = from_header()
            msg['To'] = self.alert_email
            # L'instance se nomme quand ce n'est PAS la production. Le 2026-08-24,
            # un scheduler Airflow local a rejoué un run planifié, échoué sur le
            # credential SoundCloud partagé (que la prod venait de faire tourner
            # 28 min plus tôt) et envoyé deux alertes à une vraie boîte —
            # indiscernables d'une panne de production. Le préfixe est vide en
            # production À DESSEIN : c'est son ABSENCE qui doit vouloir dire
            # « ceci est réel », pas un « [PRODUCTION] » auquel l'œil s'habitue.
            msg['Subject'] = f"{instance_label()}🚨 Dashboard Alert: {subject}"
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
        blocked = self._outbound_blocked()
        if blocked:
            # The tenant-facing path. It matters MORE than send_alert, not less: this
            # one reaches artists, and the suite already shipped three real
            # verification mails to real people on 2026-08-23.
            logger.info("✉️  suppressed (%s): %s → %s", blocked, subject, to_email)
            return False
        if not _artist_mail_opted_in():
            # `_outbound_blocked` gates on the INSTANCE (is this production?). This
            # gates on the AUDIENCE (is the recipient a client of ours?), and the two
            # are independent: a correct production instance mailing a tenant nobody
            # decided to mail is still an unwanted send.
            #
            # Asked on 2026-08-31 — « comment ça les artistes reçoivent des mails ?
            # Je n'ai pas encore validé ». They did not: `onboarding_report`, the only
            # caller, had never fired for an artist, held back by a DATA condition
            # (it needs S4A rows, and one tenant has any). That is a coincidence, not
            # a decision — the first artist to upload a CSV would have been mailed a
            # PDF the next morning at 09:00 with nobody having said yes.
            #
            # Pausing the DAG was the immediate fix and it lives in Airflow's own
            # database: a `--force-recreate`, a restore or one click in the UI undoes
            # it, and nothing anywhere would say so. A default that has to be turned
            # ON to reach a client is the version that survives all three.
            logger.info("✉️  suppressed (artist mail not opted in: set %s=1): %s → %s",
                        _ARTIST_MAIL_OPT_IN, subject, to_email)
            return False
        if not self.smtp_user or not self.smtp_password or not to_email:
            logger.warning("⚠️ SMTP non configuré ou destinataire manquant — email '%s' ignoré.",
                           subject)
            return False
        try:
            msg = MIMEMultipart('mixed')
            msg['From'] = from_header()
            msg['To'] = to_email
            # Le SECOND chemin d'envoi, et celui qui atteint un CLIENT — pas
            # l'admin. C'est lui qui a expédié trois vrais mails de vérification
            # depuis un poste de dev le 2026-08-23, avec un lien `localhost`. Ne
            # nommer que `send_alert` aurait laissé vivant exactement le chemin le
            # plus coûteux : ce dépôt a déjà payé une fois d'avoir lu celui qui
            # marchait (R38, le nom d'expéditeur).
            msg['Subject'] = f"{instance_label()}{subject}"
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
            # `safe_error`, comme `send_alert` douze lignes plus haut : la même
            # classe rédigée dans une méthode et brute dans sa voisine, dans le même
            # fichier. Une exception passée en ARGUMENT de logger échappait au garde,
            # qui ne connaissait que `str(e)` et `f"{e}"` (R38, 2026-08-23).
            logger.error("❌ Échec envoi email '%s' à %s : %s",
                         subject, to_email, safe_error(e))
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
    # A deliberate non-production suppression is NOT a delivery failure, and raising
    # on it would paint every local DAG task red for behaving exactly as designed —
    # then train the eye to ignore a red `send_consolidated_alert`, which is the one
    # task whose redness this function exists to produce. Checked BEFORE sending so
    # the distinction the two branches below carry ("SMTP absent" vs "SMTP configured
    # and the send failed") stays legible; collapsing all three into one message is
    # what `tests/test_alert_delivery_is_proven` caught when this gate was added.
    suppressed = alert._outbound_blocked()
    if suppressed:
        logger.info("✉️  nightly alert suppressed (%s): %r", suppressed, subject)
        return
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
    # `safe_error`, jamais l'exception brute. Ce corps part par SMTP (Brevo, un
    # tiers) et se dépose dans une boîte : un message d'exception `requests`
    # embarque l'URL préparée, donc `key=` (YouTube) ou `access_token=` (Meta),
    # qui voyagent en QUERY STRING. Constaté le 2026-08-24 sur un vrai mail reçu.
    #
    # Le garde `test_an_exception_passed_as_an_argument_is_redacted.py` ne pouvait
    # pas le voir : il cherche une exception reçue en PARAMÈTRE, et celle-ci arrive
    # par une clé de dictionnaire.
    raw_exception = context.get('exception')
    exception = safe_error(raw_exception) if isinstance(raw_exception, BaseException) \
        else redact(raw_exception if raw_exception is not None else 'N/A')
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
