"""DAG onboarding_report — first analytics PDF report, once per artist.

Type: Feature
Uses: src.dashboard.utils.pdf_exporter.generate_pdf, src.utils.email_alerts.EmailAlert
Depends on: saas_users.onboarding_report_sent_at (migration 046), s4a_song_timeline
Persists in: saas_users.onboarding_report_sent_at (single-send guard)

Runs daily. For each verified + active client whose account has never received the
report (onboarding_report_sent_at IS NULL) and whose first collection has landed
(S4A data present), it builds the full "depuis le début" PDF and emails it with the
PDF attached, then stamps the send timestamp so the report goes out exactly once.

Everything per-artist is wrapped so one artist's failure (missing dep, render error,
SMTP hiccup) is logged and skipped — it never fails the DAG or blocks other artists.
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, date, timedelta
import sys
import os
import logging

sys.path.insert(0, '/opt/airflow')

logger = logging.getLogger(__name__)


def _on_failure_callback(context):
    try:
        from src.utils.email_alerts import dag_failure_callback
        dag_failure_callback(context)
    except Exception as e:
        logger.error(f"Failure callback error: {e}")


default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'on_failure_callback': _on_failure_callback,
}


def _slug(s: str) -> str:
    out = "".join(c if c.isalnum() else "_" for c in (s or "").strip())
    return ("_".join(p for p in out.split("_") if p) or "artiste")[:40]


def _report_email_html(artist_name: str, username: str, user_id: int) -> str:
    try:
        from src.utils.verification_email import _unsubscribe_footer
        unsub = _unsubscribe_footer(user_id)
    except Exception:
        unsub = ""
    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#222;">
        <h2 style="color:#1DB954;">📊 Votre premier rapport streaMLytics est prêt, {username} !</h2>
        <p>Vos données ont bien été collectées pour <strong>{artist_name}</strong>. En pièce
           jointe, votre <strong>rapport analytics complet</strong> (PDF) : streaming, audience,
           pub, et prédiction algorithmique « Road to Algo ».</p>
        <p>Vous pouvez régénérer ce rapport à tout moment (et choisir période + chansons) depuis
           la page <em>📄 Export PDF</em> du dashboard.</p>
        <p style="color:#888;font-size:12px;margin-top:24px;">
            Rapport généré automatiquement après votre première collecte réussie.
        </p>
        {unsub}
    </body></html>
    """


def _artist_has_s4a_data(db, artist_id: int) -> bool:
    rows = db.fetch_query(
        "SELECT 1 FROM s4a_song_timeline "
        "WHERE artist_id = %s AND song NOT ILIKE '%%1x7xxxxxxx%%' LIMIT 1",
        (artist_id,),
    )
    return bool(rows)


def send_onboarding_reports(**context):
    """Build + email the first report to every eligible client, once."""
    from src.database.postgres_handler import PostgresHandler
    from src.utils.email_alerts import EmailAlert

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD'),
    )

    pending = db.fetch_query(
        """
        SELECT u.id, u.email, u.username, u.artist_id, a.name
        FROM saas_users u
        JOIN saas_artists a ON a.id = u.artist_id
        WHERE u.email_verified = TRUE
          AND u.active = TRUE
          AND u.role <> 'admin'
          AND u.artist_id IS NOT NULL
          AND u.onboarding_report_sent_at IS NULL
        """
    )
    if not pending:
        logger.info("No user awaiting an onboarding report.")
        db.close()
        return {'eligible': 0, 'sent': 0}

    email_client = EmailAlert()
    sent = 0
    for uid, email, username, artist_id, artist_name in pending:
        try:
            if not _artist_has_s4a_data(db, artist_id):
                logger.info("Artist %s (id=%s) has no S4A data yet — deferring report.",
                            artist_name, artist_id)
                continue
            pdf_bytes = _build_report(db, artist_id, artist_name)
            if not pdf_bytes:
                logger.warning("Report build returned empty for %s — skipping.", artist_name)
                continue
            run_date = datetime.now().strftime("%Y%m%d")
            filename = f"{_slug(artist_name)}_RAPPORT_{run_date}.pdf"
            ok = email_client.send_email(
                email,
                f"📊 Votre premier rapport streaMLytics — {artist_name}",
                _report_email_html(artist_name, username, uid),
                attachment_bytes=pdf_bytes,
                attachment_name=filename,
            )
            if ok:
                db.execute_query(
                    "UPDATE saas_users SET onboarding_report_sent_at = now() WHERE id = %s",
                    (uid,),
                )
                sent += 1
                logger.info("Onboarding report sent + stamped for %s (id=%s).", artist_name, uid)
            else:
                logger.warning("Email not sent for %s — will retry next run (not stamped).",
                               artist_name)
        except Exception as e:
            logger.error("Onboarding report failed for %s (id=%s): %s", artist_name, uid, e)
            continue

    db.close()
    logger.info("Onboarding report run done — %s/%s sent.", sent, len(pending))
    return {'eligible': len(pending), 'sent': sent}


def _build_report(db, artist_id: int, artist_name: str) -> bytes | None:
    """Generate the full 'depuis le début' PDF. Returns None on import/render failure."""
    try:
        from src.dashboard.utils.pdf_exporter import generate_pdf, ALL_SECTIONS
    except Exception as e:
        logger.error("pdf_exporter import failed (missing dep in Airflow image?): %s", e)
        return None
    return generate_pdf(
        db,
        artist_id=artist_id,
        artist_name=artist_name,
        from_date=date(2015, 1, 1),
        to_date=date.today(),
        sections={k: True for k in ALL_SECTIONS},
    )


with DAG(
    'onboarding_report',
    default_args=default_args,
    description='First analytics PDF report emailed once per artist post first collection',
    schedule_interval='0 9 * * *',  # daily 09:00 UTC, after the collection DAGs
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,  # avoid concurrent runs double-sending before the stamp commits
    tags=['email', 'onboarding', 'report'],
) as dag:

    send_task = PythonOperator(
        task_id='send_onboarding_reports',
        python_callable=send_onboarding_reports,
    )
