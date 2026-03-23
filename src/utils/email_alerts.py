"""Envoi d'alertes email depuis les DAGs Airflow et le monitor de fraîcheur."""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class EmailAlert:
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.alert_email = os.getenv('ALERT_EMAIL')

    def send_alert(self, subject: str, body: str) -> bool:
        """Envoie une alerte par email. Retourne True si succès."""
        if not self.smtp_user or not self.smtp_password or not self.alert_email:
            logger.warning(
                "⚠️ Email alerts non configurées (SMTP_USER/SMTP_PASSWORD/ALERT_EMAIL manquants)"
            )
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
            logger.error(f"❌ Échec envoi email : {e}")
            return False


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
        logger.error(f"dag_failure_callback : envoi email échoué ({e})")
