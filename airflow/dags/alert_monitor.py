"""DAG Alert Monitor — consolidated monitoring with root cause detection.

Runs daily at 23:00 UTC (after all collectors and data_quality_check).

Tasks:
  1. check_credentials_all  — detect missing credentials per artist/platform
  2. check_dag_failures      — query Airflow DB for recent failures + root cause
  3. check_data_freshness    — run freshness check on all sources
  4. send_consolidated_alert — build and send one email with all findings

Implements bricks:
  A — consolidated alert_monitor DAG
  B — scheduled freshness alerting
  D — credential pre-check (cross-DAG, global view)
"""
import sys
sys.path.insert(0, '/opt/airflow')

import os
import logging
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

MONITORED_PLATFORMS = ['spotify', 'youtube', 'soundcloud', 'meta']

MONITORED_DAGS = [
    'spotify_api_daily',
    'youtube_daily',
    'soundcloud_daily',
    'instagram_daily',
    'meta_insights_dag',
    'meta_config_dag',
    'apple_music_csv_watcher',
    's4a_csv_watcher',
    'ml_scoring_daily',
    'data_quality_check',
]


def _on_failure_callback(context):
    try:
        from src.utils.email_alerts import dag_failure_callback
        dag_failure_callback(context)
    except Exception as e:
        logger.error(f"Failure callback error: {e}")


default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
    'on_failure_callback': _on_failure_callback,
}


# ─────────────────────────────────────────────────────────────────
# Task 1 — Credential audit across all active artists
# ─────────────────────────────────────────────────────────────────

def check_credentials_all(**context):
    """Check which artist×platform combinations have no credentials in DB."""
    from src.utils.credential_loader import get_active_artists, load_platform_credentials

    artists = get_active_artists()
    if not artists:
        logger.info("No active artists — skipping credential check.")
        context['task_instance'].xcom_push(key='missing_credentials', value=[])
        return

    missing = []
    for artist_id, artist_name in artists:
        for platform in MONITORED_PLATFORMS:
            creds = load_platform_credentials(artist_id, platform)
            if not creds:
                missing.append({
                    'artist_id': artist_id,
                    'artist_name': artist_name,
                    'platform': platform,
                })
                logger.warning(
                    f"Missing credentials: artist={artist_name} (id={artist_id}), platform={platform}"
                )

    logger.info(
        f"Credential audit done: {len(missing)} missing out of "
        f"{len(artists) * len(MONITORED_PLATFORMS)} combinations."
    )
    context['task_instance'].xcom_push(key='missing_credentials', value=missing)


# ─────────────────────────────────────────────────────────────────
# Task 2 — DAG failure audit from Airflow metadata DB
# ─────────────────────────────────────────────────────────────────

def check_dag_failures(**context):
    """Query Airflow DagRun table for failures over the last 7 days."""
    from src.utils.alert_root_cause import detect_root_cause

    try:
        from airflow.models import DagRun, TaskInstance
        from airflow.utils.session import create_session
        from airflow.utils.state import DagRunState

        cutoff = datetime.now() - timedelta(days=7)
        failing_dags = {}

        with create_session() as session:
            for dag_id in MONITORED_DAGS:
                runs = (
                    session.query(DagRun)
                    .filter(
                        DagRun.dag_id == dag_id,
                        DagRun.state == DagRunState.FAILED,
                        DagRun.execution_date >= cutoff,
                    )
                    .order_by(DagRun.execution_date.desc())
                    .all()
                )

                if not runs:
                    continue

                last_run = runs[0]
                failure_count = len(runs)

                # Try to get exception from the most recent failed task instance
                failed_ti = (
                    session.query(TaskInstance)
                    .filter(
                        TaskInstance.dag_id == dag_id,
                        TaskInstance.run_id == last_run.run_id,
                        TaskInstance.state == 'failed',
                    )
                    .first()
                )

                exception_str = ''
                if failed_ti:
                    exception_str = str(getattr(failed_ti, 'exception', '') or '')

                cause, action = detect_root_cause(exception_str, dag_id)

                # Compute first failure date (oldest in window)
                first_failure = runs[-1].execution_date

                failing_dags[dag_id] = {
                    'failure_count': failure_count,
                    'last_failure': str(last_run.execution_date)[:16],
                    'first_failure': str(first_failure)[:16],
                    'cause': cause,
                    'action': action,
                }

                logger.warning(
                    f"DAG {dag_id}: {failure_count} failures in 7d — {cause}"
                )

    except Exception as e:
        logger.error(f"check_dag_failures: Airflow DB query failed — {e}")
        failing_dags = {}

    context['task_instance'].xcom_push(key='failing_dags', value=failing_dags)
    return failing_dags


# ─────────────────────────────────────────────────────────────────
# Task 3 — Data freshness check
# ─────────────────────────────────────────────────────────────────

def check_data_freshness(**context):
    """Run freshness check on all monitored data sources."""
    import os
    from src.database.postgres_handler import PostgresHandler
    from src.utils.freshness_monitor import check_freshness

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD'),
    )

    try:
        results = check_freshness(db)
    finally:
        db.close()

    stale = [r for r in results if r['stale']]
    logger.info(f"Freshness check: {len(stale)} stale / {len(results)} sources")

    serializable = []
    for r in results:
        serializable.append({
            'source': r['source'],
            'last_dt': str(r['last_dt']) if r['last_dt'] else None,
            'age_h': round(r['age_h'], 1) if r['age_h'] is not None else None,
            'stale': r['stale'],
            'stale_h': r['stale_h'],
        })

    context['task_instance'].xcom_push(key='freshness_results', value=serializable)
    return serializable


# ─────────────────────────────────────────────────────────────────
# Task 4 — Build and send consolidated alert email
# ─────────────────────────────────────────────────────────────────

def send_consolidated_alert(**context):
    """Assemble one email with all findings: failures, freshness, missing creds."""
    from src.utils.email_alerts import EmailAlert

    ti = context['task_instance']
    failing_dags = ti.xcom_pull(task_ids='check_dag_failures', key='failing_dags') or {}
    freshness = ti.xcom_pull(task_ids='check_data_freshness', key='freshness_results') or []
    missing_creds = ti.xcom_pull(task_ids='check_credentials_all', key='missing_credentials') or []

    stale_sources = [r for r in freshness if r['stale']]
    has_issues = failing_dags or stale_sources or missing_creds

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    if not has_issues:
        logger.info(f"✅ All systems OK at {now_str} — no alert sent.")
        return

    # ── Build HTML body ──────────────────────────────────────────

    sections = []

    # Section: DAG failures
    if failing_dags:
        rows = ''
        for dag_id, info in failing_dags.items():
            duration_label = (
                f"depuis {info['first_failure']}"
                if info['first_failure'] != info['last_failure']
                else info['last_failure']
            )
            rows += f"""
            <tr>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">
                <b>{dag_id}</b><br>
                <span style="color:#888;font-size:0.85em">{info['failure_count']} échec(s) {duration_label}</span>
              </td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#c0392b">{info['cause']}</td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#2980b9">{info['action']}</td>
            </tr>"""

        sections.append(f"""
        <h2 style="color:#c0392b;border-left:4px solid #c0392b;padding-left:10px">
          🔴 DAGs en échec ({len(failing_dags)})
        </h2>
        <table style="border-collapse:collapse;width:100%;font-size:0.9em">
          <thead>
            <tr style="background:#fdf3f3">
              <th style="padding:8px 12px;text-align:left">DAG</th>
              <th style="padding:8px 12px;text-align:left">Root cause</th>
              <th style="padding:8px 12px;text-align:left">Action</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>""")

    # Section: stale sources
    if stale_sources:
        rows = ''
        for r in stale_sources:
            age_label = f"{r['age_h']:.0f}h" if r['age_h'] is not None else 'jamais collectée'
            rows += f"""
            <tr>
              <td style="padding:6px 12px;border-bottom:1px solid #eee"><b>{r['source']}</b></td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#e67e22">{age_label}</td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">{r['stale_h']}h</td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#888">
                Airflow UI → relancer le DAG correspondant
              </td>
            </tr>"""

        sections.append(f"""
        <h2 style="color:#e67e22;border-left:4px solid #e67e22;padding-left:10px">
          🟡 Données stale ({len(stale_sources)})
        </h2>
        <table style="border-collapse:collapse;width:100%;font-size:0.9em">
          <thead>
            <tr style="background:#fef9f0">
              <th style="padding:8px 12px;text-align:left">Source</th>
              <th style="padding:8px 12px;text-align:left">Âge</th>
              <th style="padding:8px 12px;text-align:left">Seuil</th>
              <th style="padding:8px 12px;text-align:left">Action</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>""")

    # Section: missing credentials
    if missing_creds:
        rows = ''
        for m in missing_creds:
            rows += f"""
            <tr>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">
                {m['artist_name']} <span style="color:#888">(id={m['artist_id']})</span>
              </td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">{m['platform']}</td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#2980b9">
                Dashboard → Credentials → onglet {m['platform'].capitalize()}
              </td>
            </tr>"""

        sections.append(f"""
        <h2 style="color:#8e44ad;border-left:4px solid #8e44ad;padding-left:10px">
          🔑 Credentials manquants ({len(missing_creds)})
        </h2>
        <table style="border-collapse:collapse;width:100%;font-size:0.9em">
          <thead>
            <tr style="background:#faf5ff">
              <th style="padding:8px 12px;text-align:left">Artiste</th>
              <th style="padding:8px 12px;text-align:left">Plateforme</th>
              <th style="padding:8px 12px;text-align:left">Action</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>""")

    # OK sources footer
    ok_sources = [r['source'] for r in freshness if not r['stale']]
    ok_line = ''
    if ok_sources:
        ok_line = (
            f"<p style='color:#27ae60'>✅ Sources OK : {', '.join(ok_sources)}</p>"
        )

    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto">
      <h1 style="color:#2c3e50">📊 Monitoring Music Platform — {now_str}</h1>
      {''.join(sections)}
      {ok_line}
      <hr style="border:none;border-top:1px solid #eee;margin-top:24px">
      <p style="color:#aaa;font-size:0.8em">
        Généré par alert_monitor DAG — Airflow : <a href="http://localhost:8080">http://localhost:8080</a>
      </p>
    </div>
    """

    subject_parts = []
    if failing_dags:
        subject_parts.append(f"{len(failing_dags)} DAG(s) en échec")
    if stale_sources:
        subject_parts.append(f"{len(stale_sources)} source(s) stale")
    if missing_creds:
        subject_parts.append(f"{len(missing_creds)} credential(s) manquant(s)")

    subject = ' | '.join(subject_parts)
    EmailAlert().send_alert(subject, body)
    logger.info(f"Consolidated alert sent: {subject}")


# ─────────────────────────────────────────────────────────────────
# DAG definition
# ─────────────────────────────────────────────────────────────────

with DAG(
    dag_id='alert_monitor',
    default_args=default_args,
    description='Monitoring consolidé : failures, freshness, credentials — envoi email quotidien',
    schedule_interval='0 23 * * *',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['monitoring', 'alerting', 'production'],
    max_active_runs=1,
) as dag:

    t_creds = PythonOperator(
        task_id='check_credentials_all',
        python_callable=check_credentials_all,
    )

    t_failures = PythonOperator(
        task_id='check_dag_failures',
        python_callable=check_dag_failures,
    )

    t_freshness = PythonOperator(
        task_id='check_data_freshness',
        python_callable=check_data_freshness,
    )

    t_alert = PythonOperator(
        task_id='send_consolidated_alert',
        python_callable=send_consolidated_alert,
        trigger_rule='all_done',
    )

    [t_creds, t_failures, t_freshness] >> t_alert
