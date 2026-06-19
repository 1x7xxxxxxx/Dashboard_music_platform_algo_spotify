"""DAG Alert Monitor — consolidated monitoring with root cause detection.

Runs daily at 23:00 UTC (after all collectors and data_quality_check).

Tasks:
  1. check_credentials_all  — detect missing credentials per artist/platform
  2. check_dag_failures      — query Airflow DB for recent failures + root cause
  3. check_data_freshness    — run freshness check on all sources
  4. check_billing_sync      — Stripe subscriptions stuck / lapsed without sync
  5. check_row_anomalies     — daily-insert spike vs trailing baseline (data poison)
  6. send_consolidated_alert — build and send one email with all findings

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
    'meta_ads_api_daily',
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

            # Consecutive-failure escalation — a 7-day TOTAL count can't tell 2 isolated
            # failures from "failing every single day" (youtube/soundcloud/instagram in the
            # Benken week failed daily, unnoticed). Pull every recent run by date + state.
            from src.utils.monitoring_checks import consecutive_failure_days
            all_runs = [
                (r.dag_id, r.execution_date, r.state)
                for r in session.query(DagRun)
                .filter(DagRun.dag_id.in_(MONITORED_DAGS),
                        DagRun.execution_date >= cutoff).all()
            ]
            for dag_id, streak in consecutive_failure_days(all_runs, min_days=3).items():
                if dag_id in failing_dags:
                    failing_dags[dag_id]['consecutive_days'] = streak
                    logger.warning(f"🚨 DAG {dag_id} FAILING {streak} consecutive days")

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
        # Per-tenant freshness — the GLOBAL check above masks a configured tenant with no
        # data on platform Y whenever ANOTHER tenant has recent data (the Benken gap: his
        # SoundCloud/YouTube were dead while artist 1's were fresh). Loop active artists.
        from src.utils.credential_loader import get_active_artists
        from src.utils.monitoring_checks import tenant_freshness_gaps
        per_tenant = [(aid, name, check_freshness(db, aid))
                      for aid, name in get_active_artists()]
        tenant_gaps = tenant_freshness_gaps(per_tenant)
    finally:
        db.close()

    stale = [r for r in results if r['stale']]
    logger.info(f"Freshness check: {len(stale)} stale / {len(results)} sources; "
                f"{len(tenant_gaps)} tenant(s) with a per-tenant gap")

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
    context['task_instance'].xcom_push(key='tenant_freshness_gaps', value=tenant_gaps)
    return serializable


def check_resurrection_sparks(**context):
    """Detect long-tail songs with a sudden saves spike across all active artists.

    Dormant until ~2 weeks of daily saves history accumulate (s4a_song_saves_daily,
    written by ml_scoring_daily). Sparks are opportunities (re-ignite with a small
    ad budget), not failures — surfaced as a green section in the consolidated email.
    """
    from src.database.postgres_handler import PostgresHandler
    from src.utils.saves_history import detect_saves_resurrection

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD'),
    )
    sparks = []
    try:
        artists = db.fetch_query(
            "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id"
        )
        for artist_id, name in (artists or []):
            # Per-artist isolation: one tenant's bad saves history must not abort the
            # resurrection scan for the others (it would lose all alerting data).
            try:
                for s in detect_saves_resurrection(db, artist_id):
                    sparks.append({
                        'artist_id': artist_id, 'artist_name': name, 'song': s['song'],
                        'age_days': s['age_days'], 'recent_gain': s['recent_gain'],
                    })
            except Exception as e:
                logger.error(f"Resurrection scan failed for {name} (id={artist_id}): {e}")
                continue
    finally:
        db.close()

    logger.info(f"Resurrection check: {len(sparks)} spark(s) detected")
    context['task_instance'].xcom_push(key='resurrection_sparks', value=sparks)
    return sparks


def check_drift_anomalies(**context):
    """Flag SYSTEMIC ML input drift: a feature out-of-distribution across most of the
    latest predictions usually means a data-pipeline break (the model extrapolates
    blindly). Reuses ml_inference.check_drift; a feature drifting in >50% of songs
    is surfaced in the consolidated email.
    """
    import json as _json
    from collections import Counter

    from src.database.postgres_handler import PostgresHandler
    from src.utils.ml_inference import check_drift

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD'),
    )
    counter, total = Counter(), 0
    try:
        rows = db.fetch_query(
            """SELECT features_json FROM ml_song_predictions
               WHERE prediction_date = (SELECT MAX(prediction_date) FROM ml_song_predictions)
                 AND features_json IS NOT NULL"""
        )
        for (fj,) in (rows or []):
            try:
                feats = _json.loads(fj) if isinstance(fj, str) else fj
            except (ValueError, TypeError):
                continue
            total += 1
            for f in check_drift(feats):
                counter[f] += 1
    finally:
        db.close()

    systemic = [{'feature': f, 'count': c, 'total': total}
                for f, c in counter.items() if total and c / total > 0.5]
    logger.info(f"Drift check: {len(systemic)} systemic drift(s) over {total} predictions")
    context['task_instance'].xcom_push(key='drift_anomalies', value=systemic)
    return systemic


# Daily-insert anomaly watch: (table, date_column). Hardcoded allowlist — never user
# input, so the f-string interpolation below is safe (CLAUDE.md rule #8).
ANOMALY_TABLES = [
    ('youtube_video_stats', 'collected_at'),
    ('soundcloud_tracks_daily', 'collected_at'),
    ('meta_insights_performance_day', 'day_date'),
    ('ml_song_predictions', 'prediction_date'),
    ('s4a_song_timeline', 'date'),
]


def check_billing_sync(**context):
    """Flag Stripe subscriptions stuck in a bad state or whose period lapsed without a
    sync. Complements the external webhook-reachability probe: that one catches the edge
    being blocked, this catches subscription drift that already slipped through.
    """
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD'),
    )
    issues = []
    try:
        rows = db.fetch_query(
            """SELECT s.artist_id, COALESCE(a.name, '?') AS name, s.status,
                      s.current_period_end
               FROM artist_subscriptions s
               LEFT JOIN saas_artists a ON a.id = s.artist_id
               WHERE s.status IN ('past_due', 'incomplete', 'unpaid')
                  OR (s.status = 'active' AND s.current_period_end IS NOT NULL
                      AND s.current_period_end < NOW() - INTERVAL '3 days')
               ORDER BY s.artist_id"""
        )
        for artist_id, name, status, period_end in (rows or []):
            reason = (
                f"statut '{status}'" if status != 'active'
                else f"période expirée le {str(period_end)[:10]} sans sync (webhook manqué ?)"
            )
            issues.append({'artist_id': artist_id, 'artist_name': name,
                           'status': status, 'reason': reason})
            logger.warning(f"Billing sync issue: artist={name} (id={artist_id}) — {reason}")
    finally:
        db.close()

    logger.info(f"Billing sync check: {len(issues)} issue(s)")
    context['task_instance'].xcom_push(key='billing_issues', value=issues)
    return issues


def check_row_anomalies(**context):
    """Flag a daily-insert SPIKE: the most recent day's row count > 10x the trailing
    7-day average (with a meaningful absolute floor). A sudden 10x jump is usually a
    double-run or data poison; freshness already covers the opposite (no recent data),
    so this watches only the spike direction.
    """
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD'),
    )
    anomalies = []
    try:
        for table, col in ANOMALY_TABLES:
            rows = db.fetch_query(
                f"""WITH d AS (
                        SELECT {col}::date AS day, count(*)::float AS c
                        FROM {table} GROUP BY 1
                    )
                    SELECT (SELECT c FROM d ORDER BY day DESC LIMIT 1),
                           (SELECT avg(c) FROM (SELECT c FROM d ORDER BY day DESC OFFSET 1 LIMIT 7) x),
                           (SELECT max(day)::text FROM d)"""
            )
            if not rows or rows[0][0] is None:
                continue
            recent, baseline, day = rows[0]
            if baseline and recent >= 100 and recent > 10 * baseline:
                anomalies.append({'table': table, 'recent': int(recent),
                                  'baseline': round(baseline, 1), 'day': day})
                logger.warning(f"Row spike: {table} {int(recent)} on {day} vs ~{baseline:.0f}/day")
    finally:
        db.close()

    logger.info(f"Row-anomaly check: {len(anomalies)} spike(s)")
    context['task_instance'].xcom_push(key='row_anomalies', value=anomalies)
    return anomalies


def check_onboarding_readiness(**context):
    """Flag any active artist CONNECTED to a platform but receiving NO data (the silent gap).

    The per-artist closed loop: an artist who provided an identifier (channel_id, account_id…)
    but whose platform produces 0 rows — Benken's empty YouTube channel, a not-shared Meta
    account — becomes a RED flag with the exact next action, instead of staying invisible.
    """
    from src.database.postgres_handler import PostgresHandler
    from src.utils.credential_loader import get_active_artists
    from src.utils.artist_readiness import readiness_red_flags

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD'),
    )
    flags = []
    try:
        for aid, name in get_active_artists():
            try:
                for m in readiness_red_flags(db, aid):
                    flags.append({'artist_id': aid, 'artist_name': name,
                                  'platform': m['label'], 'next_action': m['next_action']})
            except Exception as e:  # per-artist isolation
                logger.error(f"Readiness check failed for {name} (id={aid}): {e}")
                continue
    finally:
        db.close()

    logger.info(f"Onboarding readiness: {len(flags)} connected-but-no-data flag(s)")
    context['task_instance'].xcom_push(key='onboarding_red_flags', value=flags)
    return flags


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
    sparks = ti.xcom_pull(task_ids='check_resurrection_sparks', key='resurrection_sparks') or []
    drift = ti.xcom_pull(task_ids='check_drift_anomalies', key='drift_anomalies') or []
    billing_issues = ti.xcom_pull(task_ids='check_billing_sync', key='billing_issues') or []
    row_anomalies = ti.xcom_pull(task_ids='check_row_anomalies', key='row_anomalies') or []
    tenant_gaps = ti.xcom_pull(task_ids='check_data_freshness', key='tenant_freshness_gaps') or []
    readiness_flags = ti.xcom_pull(task_ids='check_onboarding_readiness', key='onboarding_red_flags') or []

    stale_sources = [r for r in freshness if r['stale']]
    has_issues = (failing_dags or stale_sources or missing_creds or sparks or drift
                  or billing_issues or row_anomalies or tenant_gaps or readiness_flags)

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
            # Escalate a DAG that has failed every scheduled day for ≥3 days.
            escalation = (
                f" <b style='color:#c0392b'>🚨 {info['consecutive_days']}j consécutifs</b>"
                if info.get('consecutive_days') else ""
            )
            rows += f"""
            <tr>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">
                <b>{dag_id}</b>{escalation}<br>
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

    # Section: per-tenant freshness gaps (a configured artist with no/stale data on a
    # platform — masked by the global freshness check above)
    if tenant_gaps:
        rows = ''
        for g in tenant_gaps:
            rows += (
                f"<tr><td style='padding:6px 12px;border-bottom:1px solid #eee'>"
                f"<b>{g['artist_name']}</b> (id={g['artist_id']})</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee;color:#c0392b'>"
                f"{', '.join(g['stale_sources'])}</td></tr>"
            )
        sections.append(f"""
        <h2 style="color:#c0392b;border-left:4px solid #c0392b;padding-left:10px">
          👤 Sources stale par artiste ({len(tenant_gaps)})
        </h2>
        <table style="border-collapse:collapse;width:100%;font-size:0.9em">
          <thead><tr style="background:#fdf3f2">
            <th style="padding:8px 12px;text-align:left">Artiste</th>
            <th style="padding:8px 12px;text-align:left">Sources stale</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>""")

    # Section: onboarding readiness — connected to a platform but receiving NO data
    if readiness_flags:
        rows = ''
        for f in readiness_flags:
            rows += (
                f"<tr><td style='padding:6px 12px;border-bottom:1px solid #eee'>"
                f"<b>{f['artist_name']}</b> (id={f['artist_id']})</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{f['platform']}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee;color:#2980b9'>"
                f"{f['next_action']}</td></tr>"
            )
        sections.append(f"""
        <h2 style="color:#c0392b;border-left:4px solid #c0392b;padding-left:10px">
          🔴 Connecté mais sans données ({len(readiness_flags)})
        </h2>
        <table style="border-collapse:collapse;width:100%;font-size:0.9em">
          <thead><tr style="background:#fdf3f2">
            <th style="padding:8px 12px;text-align:left">Artiste</th>
            <th style="padding:8px 12px;text-align:left">Plateforme</th>
            <th style="padding:8px 12px;text-align:left">Action</th>
          </tr></thead>
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

    # Section: resurrection sparks (opportunities, not failures)
    if sparks:
        rows = ''
        for s in sparks:
            rows += f"""
            <tr>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">
                {s['artist_name']} <span style="color:#888">(id={s['artist_id']})</span>
              </td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee"><b>{s['song']}</b>
                <span style="color:#888;font-size:0.85em"> — {s['age_days']} j</span></td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#27ae60">
                +{s['recent_gain']} saves récents → injecter un petit budget Ads pour réveiller le Discover Weekly
              </td>
            </tr>"""

        sections.append(f"""
        <h2 style="color:#27ae60;border-left:4px solid #27ae60;padding-left:10px">
          ✨ Résurrection longue traîne ({len(sparks)})
        </h2>
        <table style="border-collapse:collapse;width:100%;font-size:0.9em">
          <thead>
            <tr style="background:#f3fbf5">
              <th style="padding:8px 12px;text-align:left">Artiste</th>
              <th style="padding:8px 12px;text-align:left">Titre</th>
              <th style="padding:8px 12px;text-align:left">Opportunité</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>""")

    # Section: systemic ML input drift (data-pipeline health)
    if drift:
        items = ''.join(
            f"<li><b>{d['feature']}</b> — hors distribution sur "
            f"{d['count']}/{d['total']} prédictions</li>" for d in drift
        )
        sections.append(f"""
        <h2 style="color:#e67e22;border-left:4px solid #e67e22;padding-left:10px">
          📉 Drift d'entrée ML ({len(drift)})
        </h2>
        <p style="color:#888;font-size:0.9em">Variable(s) hors de l'enveloppe d'entraînement
          sur la majorité des prédictions — vérifier le pipeline de features S4A.</p>
        <ul style="font-size:0.9em">{items}</ul>""")

    # Section: billing sync issues (revenue-critical)
    if billing_issues:
        rows = ''
        for b in billing_issues:
            rows += f"""
            <tr>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">
                {b['artist_name']} <span style="color:#888">(id={b['artist_id']})</span>
              </td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#c0392b">{b['reason']}</td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#2980b9">
                Stripe → Subscriptions + vérifier les webhooks récents
              </td>
            </tr>"""

        sections.append(f"""
        <h2 style="color:#c0392b;border-left:4px solid #c0392b;padding-left:10px">
          💳 Abonnements à vérifier ({len(billing_issues)})
        </h2>
        <table style="border-collapse:collapse;width:100%;font-size:0.9em">
          <thead>
            <tr style="background:#fdf3f3">
              <th style="padding:8px 12px;text-align:left">Artiste</th>
              <th style="padding:8px 12px;text-align:left">Problème</th>
              <th style="padding:8px 12px;text-align:left">Action</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>""")

    # Section: daily-insert spikes (data-poison / double-run)
    if row_anomalies:
        items = ''.join(
            f"<li><b>{a['table']}</b> — {a['recent']} lignes le {a['day']} "
            f"vs ~{a['baseline']:.0f}/j (×{a['recent'] / max(a['baseline'], 1):.0f})</li>"
            for a in row_anomalies
        )
        sections.append(f"""
        <h2 style="color:#e67e22;border-left:4px solid #e67e22;padding-left:10px">
          📈 Pic d'insertion ({len(row_anomalies)})
        </h2>
        <p style="color:#888;font-size:0.9em">Volume journalier anormalement haut —
          double run d'un DAG ou données corrompues ? Vérifier la collecte du jour.</p>
        <ul style="font-size:0.9em">{items}</ul>""")

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
    if sparks:
        subject_parts.append(f"✨ {len(sparks)} résurrection(s)")
    if drift:
        subject_parts.append(f"📉 {len(drift)} drift(s)")
    if billing_issues:
        subject_parts.append(f"💳 {len(billing_issues)} abonnement(s)")
    if row_anomalies:
        subject_parts.append(f"📈 {len(row_anomalies)} pic(s)")

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

    t_resurrection = PythonOperator(
        task_id='check_resurrection_sparks',
        python_callable=check_resurrection_sparks,
    )

    t_drift = PythonOperator(
        task_id='check_drift_anomalies',
        python_callable=check_drift_anomalies,
    )

    t_billing = PythonOperator(
        task_id='check_billing_sync',
        python_callable=check_billing_sync,
    )

    t_anomalies = PythonOperator(
        task_id='check_row_anomalies',
        python_callable=check_row_anomalies,
    )

    t_readiness = PythonOperator(
        task_id='check_onboarding_readiness',
        python_callable=check_onboarding_readiness,
    )

    t_alert = PythonOperator(
        task_id='send_consolidated_alert',
        python_callable=send_consolidated_alert,
        trigger_rule='all_done',
    )

    [t_creds, t_failures, t_freshness, t_resurrection, t_drift,
     t_billing, t_anomalies, t_readiness] >> t_alert
