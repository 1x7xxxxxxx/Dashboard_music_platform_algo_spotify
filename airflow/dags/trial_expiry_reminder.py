"""J-3 before the welcome trial ends — the day the decision is actually made.

Type: Feature
Uses: PostgresHandler, EmailAlert, verification_email._unsubscribe_footer
Triggers: daily at 09:00 UTC
Depends on: saas_artists.promo_plan_expires_at, saas_users, trial_reminder_sent_at
Persists in: saas_users.trial_reminder_sent_at (one reminder per account, ever)

Why this DAG exists
-------------------
The welcome offer announces that the account returns to Free after a month, on the
onboarding screen — read once, on day one, by someone who has not yet seen a single
chart. Nothing said it again. The moment the decision is made is the last few days,
and by then the only surface that could speak was silent.

Three things this deliberately does NOT do:

* **it does not sell.** It says what is about to be lost and what is kept — the numbers
  the artist has accumulated stay theirs, in CSV, for ever. A reminder that hides the
  Free fallback is a trap, and the artist would find out anyway, worse;
* **it does not repeat.** `trial_reminder_sent_at` is written when the mail leaves, and
  the query excludes anyone who has it. A trial reminder sent twice reads as pressure;
* **it does not decide for the tenant.** It respects the same opt-out as the weekly
  recap (`weekly_digest_optout_at`) and the same audience gate as every artist-facing
  mail (`STREAMLYTICS_ALLOW_ARTIST_EMAIL`) — which is NOT set in production today, so
  this DAG will log its recipients and send nothing until it is. That is the intended
  state; it is logged loudly rather than looking like a quiet success.
"""
import logging
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.insert(0, '/opt/airflow')

from src.utils.dag_timeouts import dagrun_timeout_for      # noqa: E402
from src.utils.email_alerts import dag_failure_callback    # noqa: E402
from src.utils.safe_error import safe_error                # noqa: E402

logger = logging.getLogger(__name__)

# J-3, and not J-1: one day is not enough to decide, and a mail that arrives the day
# before an expiry reads as a countdown rather than as information.
DAYS_BEFORE = 3

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'on_failure_callback': dag_failure_callback,
}


def _due_accounts(db):
    """Accounts whose trial ends in exactly DAYS_BEFORE days and never reminded.

    `::date` on both sides: the trial expiry carries a time-of-day nobody chose (the
    minute of signup), and comparing timestamps would make the reminder land or not
    depending on whether the artist registered before or after 09:00 UTC.
    """
    return db.fetch_query(
        """
        SELECT u.id, u.email, a.name, a.id, a.promo_plan_expires_at::date,
               COALESCE(u.lang, 'fr')
        FROM saas_users u
        JOIN saas_artists a ON a.id = u.artist_id
        WHERE a.promo_plan_expires_at IS NOT NULL
          AND a.promo_plan_expires_at::date = (CURRENT_DATE + %s)
          AND a.tier <> 'premium'
          AND u.active
          AND u.email_verified
          AND u.trial_reminder_sent_at IS NULL
          AND u.weekly_digest_optout_at IS NULL
          AND COALESCE(a.is_canary, FALSE) = FALSE
          AND COALESCE(a.is_sandbox, FALSE) = FALSE
        """,
        (DAYS_BEFORE,),
    )


def _body(artist_name: str, ends_on, lang: str, user_id: int) -> tuple[str, str]:
    from src.utils.verification_email import _base_url, _unsubscribe_footer
    from src.dashboard.utils.i18n import translate as _t

    billing = f"{_base_url()}?page=billing&lang={lang}"
    date_str = ends_on.strftime('%d/%m/%Y')
    subject = _t('email.trial_end.subject',
                 "Ton accès Premium se termine dans 3 jours", lang)
    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
      <h2 style="color:#1DB954;">{_t('email.trial_end.title',
          "Ton mois Premium se termine le {date}", lang).format(date=date_str)}</h2>
      <p>{_t('email.trial_end.intro',
          "Salut {name} — ton accès complet offert arrive à son terme. Rien ne se "
          "passera sans toi : ton compte repassera simplement en <strong>Free</strong>.",
          lang).format(name=artist_name)}</p>
      <p><strong>{_t('email.trial_end.keep_header', "Ce que tu gardes, pour toujours :",
                     lang)}</strong><br>
         {_t('email.trial_end.keep',
             "Tes données, tes connexions, tes analyses par plateforme, l'export CSV "
             "de tout ce qui a été collecté. Rien n'est effacé, rien n'est verrouillé.",
             lang)}</p>
      <p><strong>{_t('email.trial_end.lose_header', "Ce que tu perds :", lang)}</strong><br>
         {_t('email.trial_end.lose',
             "La prédiction Discover Weekly, les prévisions de revenus, le croisement "
             "pub × écoutes, et ton rapport PDF hebdomadaire.", lang)}</p>
      <p style="text-align:center;margin:30px 0;">
        <a href="{billing}" style="display:inline-block;background:#1DB954;color:#fff;
           padding:14px 28px;text-decoration:none;border-radius:6px;font-size:16px;">
          {_t('email.trial_end.cta', "Voir mes options", lang)}
        </a>
      </p>
      {_unsubscribe_footer(user_id, lang, scope='digest')}
    </body></html>
    """
    return subject, html


def send_trial_reminders(**context):
    """One mail per account, once, three days before the trial ends."""
    from src.database.postgres_handler import PostgresHandler
    from src.utils.email_alerts import EmailAlert

    db = PostgresHandler.from_env_or_config()
    client = EmailAlert()
    sent = 0
    try:
        rows = _due_accounts(db)
        logger.info("trial reminder: %d account(s) due in %d day(s)",
                    len(rows), DAYS_BEFORE)
        for user_id, email, artist_name, _artist_id, ends_on, lang in rows:
            try:
                subject, html = _body(artist_name, ends_on, lang, user_id)
            except Exception as e:      # noqa: BLE001 — un locataire ne bloque pas les autres
                logger.error("trial reminder: body failed for %s: %s",
                             artist_name, safe_error(e))
                continue
            if not client.send_email(email, subject, html):
                # `send_email` journalise déjà la RAISON — porte d'audience fermée,
                # SMTP muet. Ne pas marquer comme envoyé : le rappel doit repartir
                # demain si la porte s'ouvre, et J-2 vaut mieux que jamais.
                logger.warning("trial reminder: not delivered for %s", artist_name)
                continue
            db.execute_query(
                "UPDATE saas_users SET trial_reminder_sent_at = NOW() WHERE id = %s",
                (user_id,))
            sent += 1
        logger.info("trial reminder: %d sent", sent)
    finally:
        try:
            db.close()
        except Exception:      # noqa: BLE001
            pass
    context['task_instance'].xcom_push(key='trial_reminders_sent', value=sent)


with DAG(
    dag_id='trial_expiry_reminder',
    default_args=default_args,
    description="J-3 avant la fin de l'essai Premium — une fois, jamais deux",
    schedule='0 9 * * *',          # tous les jours 09:00 UTC (11:00 Paris)
    start_date=datetime(2026, 9, 4),
    catchup=False,
    dagrun_timeout=dagrun_timeout_for('trial_expiry_reminder'),
    tags=['billing', 'email'],
) as dag:
    PythonOperator(
        task_id='send_trial_reminders',
        python_callable=send_trial_reminders,
    )
