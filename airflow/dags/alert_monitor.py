"""DAG Alert Monitor — consolidated monitoring with root cause detection.

Runs daily at 23:00 UTC (after all collectors and data_quality_check).

Tasks:
  1. check_credentials_all  — detect missing credentials per artist/platform
  2. check_dag_failures      — query Airflow DB for recent failures + root cause
  3. check_data_freshness    — run freshness check on all sources
  4. check_billing_sync      — Stripe subscriptions stuck / lapsed without sync
  5. check_row_anomalies     — daily-insert spike vs trailing baseline (data poison)
  5b. check_row_dips         — per-tenant daily-insert DIP (partial collection, R39)
  6. send_consolidated_alert — build and send one email with all findings

Implements bricks:
  A — consolidated alert_monitor DAG
  B — scheduled freshness alerting
  D — credential pre-check (cross-DAG, global view)
"""
import sys
sys.path.insert(0, '/opt/airflow')

# Redact credentials out of any exception this module logs: an HTTP
# exception message embeds the prepared URL, and several upstream APIs take
# their credential as a QUERY PARAMETER. stdlib-only, safe at DAG parse time.
from src.utils.diagnosis_text import as_html
from src.utils.dag_timeouts import dagrun_timeout_for
from src.utils.safe_error import redact, safe_error

import os
import logging
from html import escape
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

def _monitored_platforms() -> list:
    """The platforms the credential audit asks about — DERIVED, never retyped.

    This was `['spotify', 'youtube', 'soundcloud', 'meta']`, four names typed by
    hand, and **Instagram was missing**. So the nightly audit never once asked
    whether a tenant had declared an `ig_user_id`, while `instagram_daily` collected
    for them or skipped them in silence.

    `PLATFORM_IDENTITIES` is the single registry (5 entries) that
    `tenant_identity.py` exists to be. Deriving from it means adding a platform is
    one edit, not five — the `guard-scope-is-a-hand-written-list` lesson.

    Called lazily rather than evaluated at import: this module is parsed by the
    Airflow DagBag in containers where `src/` may not be importable, and a failure
    here would take the whole DAG file down rather than one task.
    """
    from src.utils.tenant_identity import PLATFORM_IDENTITIES
    return sorted(PLATFORM_IDENTITIES)

MONITORED_DAGS = [
    'spotify_api_daily',
    'youtube_daily',
    'soundcloud_daily',
    'instagram_daily',
    'meta_ads_api_daily',
    'ml_scoring_daily',
    'data_quality_check',
]


def _on_failure_callback(context):
    try:
        from src.utils.email_alerts import dag_failure_callback
        dag_failure_callback(context)
    except Exception as e:
        logger.error(f"Failure callback error: {safe_error(e)}")


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

def _mirrored_identities(artist_id: int) -> dict:
    """{logical_platform: value} for the identities also kept on `saas_artists`.

    Derived from `IDENTITY_MIRRORS` rather than naming `spotify_artist_id` here: the
    registry already declares which platforms mirror and onto which column, and a
    sixth hand-written copy of that fact is what `declared_identities` was missing.
    """
    from src.database.postgres_handler import PostgresHandler
    from src.utils.tenant_identity import IDENTITY_MIRRORS

    if not IDENTITY_MIRRORS:
        return {}
    cols = sorted(set(IDENTITY_MIRRORS.values()))
    # Column names come from the registry, never from user input — but they are
    # interpolated, so they are checked against the table's own allowlist first
    # (cross-cutting rule #8).
    allowed = frozenset({"spotify_artist_id"})
    unknown = [c for c in cols if c not in allowed]
    if unknown:
        logger.error("unknown mirror column(s) %s — not querying", unknown)
        return {}
    # `PostgresHandler()` takes five required arguments; the zero-argument form shipped
    # on 2026-08-26 and raised TypeError on the first nightly run, two nights running.
    # `from_env_or_config()` is the door that works inside Airflow — the scheduler gets
    # DATABASE_HOST and no DATABASE_URL, which is exactly the case its middle step
    # was added for. Guard: tests/test_a_handler_is_built_with_its_arguments.py
    db = PostgresHandler.from_env_or_config()
    try:
        row = db.fetch_query(
            f"SELECT {', '.join(cols)} FROM saas_artists WHERE id = %s", (artist_id,))
    except Exception as e:  # noqa: BLE001 — an unreadable mirror is not a verdict
        logger.error("mirror read failed for artist %s: %s", artist_id, type(e).__name__)
        return {}
    finally:
        db.close()
    if not row:
        return {}
    by_col = dict(zip(cols, row[0]))
    return {logical: by_col.get(col) for logical, col in IDENTITY_MIRRORS.items()}


def check_credentials_all(**context):
    """Check which artist×platform combinations have no credentials in DB."""
    from src.utils.credential_loader import get_active_artists, load_platform_credentials

    # Onboarding-oriented: the canary is excluded on purpose. Its permanent
    # 'no SoundCloud/Meta/Instagram' state is normal, and reporting it nightly
    # would be a daily alert that calls for no action. check_canary_health asks
    # the only question that matters about it.
    artists = get_active_artists(exclude_canaries=True)
    if not artists:
        logger.info("No active artists — skipping credential check.")
        context['task_instance'].xcom_push(key='missing_credentials', value=[])
        return

    from src.utils.tenant_identity import declared_identities, storage_platform

    platforms = _monitored_platforms()
    missing = []
    for artist_id, artist_name in artists:
        # Read each STORAGE row once, then ask the registry which LOGICAL identities
        # it actually carries. The previous test was `if not creds` — dict emptiness,
        # not identity presence — so Benken's `meta` row, which holds an `account_id`
        # and nothing else, counted as "credentials present" for a platform that has
        # never produced a single row. And because the row is shared, it counted for
        # Instagram too, had Instagram been asked about at all.
        extra_by_platform = {}
        for platform in {storage_platform(p) for p in platforms}:
            try:
                extra_by_platform[platform] = load_platform_credentials(
                    artist_id, platform) or {}
            except Exception as e:  # noqa: BLE001 — one unreadable row, not the fleet
                logger.error("credential read failed for %s / %s: %s",
                             artist_name, platform, type(e).__name__)
        # The mirrored identities too. `artist_readiness` has always honoured
        # `saas_artists.spotify_artist_id`; this check did not, so the owner — whose
        # Spotify id lives ONLY on the mirror — was reported as missing a credential
        # he has. Two readers of one question must not answer differently.
        declared = declared_identities(extra_by_platform, _mirrored_identities(artist_id))

        for platform in platforms:
            if platform in declared:
                continue
            missing.append({
                'artist_id': artist_id,
                'artist_name': artist_name,
                'platform': platform,
            })
            logger.warning(
                f"No declared identity: artist={artist_name} (id={artist_id}), "
                f"platform={platform}"
            )

    logger.info(
        f"Credential audit done: {len(missing)} missing out of "
        f"{len(artists) * len(platforms)} combinations."
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
        logger.error(f"check_dag_failures: Airflow DB query failed — {safe_error(e)}")
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
        # A statement loop with per-tenant isolation, not a comprehension. It WAS a
        # comprehension until 2026-08-22, and a comprehension cannot contain a try:
        # one tenant raising failed the whole task, and `send_consolidated_alert` has
        # `trigger_rule='all_done'`, so the mail still went out with the entire
        # per-tenant section silently missing. That is the failure mode this check
        # exists to detect, in the check itself.
        from src.utils.credential_loader import load_platform_credentials
        from src.utils.tenant_identity import (PLATFORM_IDENTITIES,
                                               declared_identities,
                                               storage_platform)

        per_tenant = []
        declared_by_artist = {}
        # exclude_canaries=True, like every other onboarding-shaped check. The canary
        # will never declare SoundCloud/Meta/Instagram and its Spotify indicator reads a
        # CSV it will never have, so it was a guaranteed finding every single night —
        # for a tenant in its NORMAL state. This was the only such check that did not
        # pass the flag.
        for aid, name in get_active_artists(exclude_canaries=True):
            try:
                per_tenant.append((aid, name, check_freshness(db, aid)))
            except Exception as e:  # noqa: BLE001 — one bad tenant must not blind the rest
                logger.error("freshness unavailable for tenant %s (%s): %s",
                             aid, name, safe_error(e))
            # What this tenant has actually DECLARED — the measured input that lets
            # tenant_freshness_gaps stop reporting platforms they do not use. Read per
            # tenant and isolated: an unreadable row must leave the map WITHOUT an
            # entry for that tenant, so nothing is suppressed on a doubt.
            try:
                extra = {}
                for storage in {storage_platform(p) for p in PLATFORM_IDENTITIES}:
                    extra[storage] = load_platform_credentials(aid, storage) or {}
                declared_by_artist[aid] = declared_identities(extra)
            except Exception as e:  # noqa: BLE001
                logger.error("declared identities unreadable for tenant %s: %s",
                             aid, safe_error(e))
        tenant_gaps = tenant_freshness_gaps(per_tenant, declared_by_artist)
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
            # Carried because the footer READS it. Without a reader, a suppressed
            # source lands in the "✅ Sources OK" list of the nightly email with a
            # two-year-old date behind it.
            'expected_silence': r.get('expected_silence'),
            # `error` and `measured_on` were dropped at this hop, and the drop had a
            # cost. check_freshness sets `error` precisely so "the probe itself failed"
            # can be told apart from "there is no data" — artist_readiness reads it and
            # renders BROKEN, which asks the artist for nothing. The email lost the
            # distinction here and rendered a dead probe as "🟡 stale · relancer le
            # DAG": broken-probe-rendered-as-user-fault, one layer up. `measured_on`
            # matters for the same reason — "written this morning" and "describes a
            # recent day" are different claims, and confusing them hid Meta Ads for
            # months.
            'error': r.get('error'),
            'measured_on': r.get('measured_on'),
            # Third field this hop has to carry for the email to name a real action.
            # The two before it were dropped here and each cost a wrong instruction.
            'fed_by': r.get('fed_by'),
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
                logger.error(f"Resurrection scan failed for {name} (id={artist_id}): {safe_error(e)}")
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


def check_central_apps(**context):
    """Do the SHARED, admin-owned apps still authenticate?

    Every other check here is per-tenant: has this artist declared credentials,
    is their data fresh, is their light green. None of them asks the question one
    level up — whether the app the whole fleet borrows still works.

    That question had no scheduled asker, and the cost is measured: the Meta
    System User token has been malformed since 2026-08 (code-190 on every REST
    call), Meta and Instagram have collected nothing since, and no alert fired.
    `tools/check_central_apps.py` detects it exactly and was wired into nothing.
    Same shape as the 672 silent CSV-watcher failures of 2026-08-20: a detector
    exists, a schedule does not.

    A broken shared app is worse than a broken tenant credential — it takes the
    whole fleet down at once — so it reports per platform, with the reason.
    """
    import sys
    sys.path.insert(0, '/opt/airflow')

    broken = []
    try:
        # `src.utils`, not `tools`: tools/ is NOT on the import path inside the
        # Airflow containers. Measured in production on 2026-08-21 — this task's
        # first real run reported "No module named 'tools'" instead of the broken
        # Meta token it exists to find. The ImportError branch below did its job
        # (it said so rather than reporting success), which is how we know.
        from src.utils.central_apps import (check_meta, check_soundcloud,
                                            check_spotify, missing_central_env,
                                            check_youtube)
        probes = {
            'Spotify': check_spotify,
            'YouTube': check_youtube,
            'SoundCloud': check_soundcloud,
            'Meta': check_meta,
        }
    except ImportError as e:
        # The tools/ package is not on the image path in every deployment. Say so
        # rather than reporting "all apps fine" — an unrunnable check must never
        # look like a passing one.
        logger.error(f"central-app check unavailable: {safe_error(e)}")
        context['task_instance'].xcom_push(
            key='central_apps_broken',
            value=[{'platform': 'ALL', 'reason': f'check could not run: {safe_error(e)}'}])
        return

    # ABSENT is red here, before any probe runs. The probes deliberately return True
    # when a platform's env vars are missing — "not configured" is not "broken", which
    # is right for a partial deployment. But this task runs nightly against
    # production, and the shared app simply not being wired into the container is the
    # literal cause of "all credentials failed" for the first beta artist. Until
    # 2026-08-22 only a HUMAN running `tools/check_central_apps.py --require` could
    # see it; the automatic path was blind to the one thing it most needed to catch.
    for platform, variables in missing_central_env().items():
        broken.append({'platform': platform,
                       'reason': f"central app NOT configured — missing "
                                 f"{', '.join(variables)} in this container"})
        logger.error(f"Central app NOT CONFIGURED: {platform} — missing {variables}")

    for label, probe in probes.items():
        try:
            if not probe():
                broken.append({'platform': label,
                               'reason': 'authentication failed — see task log'})
                logger.error(f"Central app DOWN: {label}")
        except Exception as e:  # per-platform isolation, like every check here
            broken.append({'platform': label, 'reason': safe_error(e)[:200]})
            logger.error(f"Central app check raised for {label}: {safe_error(e)}")

    logger.info(f"Central apps: {len(broken)} broken out of {len(probes)}.")
    context['task_instance'].xcom_push(key='central_apps_broken', value=broken)


def check_canary_health(**context):
    """Is the canary tenant still collecting? Nothing else asks this.

    Every other freshness check looks at a SOURCE across the fleet. A source stays
    fresh as long as ONE tenant collects — and the admin's own tenant almost always
    does. So a break in the per-tenant path (a lost identity mirror, a DAG that
    stops honouring dag_run.conf, an isolation regression) leaves every global
    signal green while every real artist collects nothing.

    That is precisely the failure the canary exists to make visible, and a canary
    nobody reads is decoration. This is the reader.

    It reports per platform the tenant declared. A platform it never declared is
    not a FRESHNESS problem — but it is a hole in the net, and until 2026-08-22 this
    function was silent about it. That silence is how the roadmap came to describe a
    canary covering three platforms out of five as "vert de bout en bout": every
    signal about it was green, and the two it did not cover produced no signal at
    all. `coverage` below is the missing sentence, pushed as information rather than
    as a daily alert — a platform nobody can canary must not become the noise this
    watchdog exists to prevent (`watchdog-becomes-the-noise`).
    """
    import sys
    sys.path.insert(0, '/opt/airflow')

    STALE_HOURS = 36  # one nightly cycle plus margin — a single missed run is noise

    problems = []
    db = None
    try:
        from src.database.postgres_handler import PostgresHandler
        db = PostgresHandler.from_env_or_config()

        rows = db.fetch_query(
            "SELECT id, name FROM saas_artists "
            "WHERE is_canary = TRUE AND active = TRUE ORDER BY id")
        if not rows:
            # Absence is a finding: without a canary this whole detector is off.
            problems.append({'platform': 'canary', 'reason':
                             'no canary tenant exists — the per-tenant pipeline has '
                             'no watchdog (roadmap R20)'})
            context['task_instance'].xcom_push(key='canary_problems', value=problems)
            return

        artist_id, name = rows[0]

        # (platform, table, timestamp column). DERIVED from the freshness registry,
        # not restated: this list used to name two tables by hand, and its Spotify
        # table (`track_popularity_history`) was not the one the artist-facing
        # readiness matrix read (`s4a_song_timeline`). The watchdog and the artist's
        # screen disagreed about what "Spotify is collecting" means, so one could be
        # green while the other was red, both truthfully.
        from src.utils.freshness_monitor import SOURCES_FOR_PLATFORM, tables_for_platform

        # Identifier allowlist (cross-cutting rule #8), gated against the
        # INDEPENDENTLY derived frozenset in freshness_monitor — not against this
        # loop's own output.
        #
        # The first version built `allowed` by calling the same function, over the
        # same keys, that produces the value being tested. The membership check was
        # true by construction: a comment wearing the shape of a control. It gates
        # nothing today (the registry is a module literal) and would gate nothing
        # the day an entry came from config or the database, which is the only day
        # it would matter.
        from src.utils.freshness_monitor import _ALLOWED_TABLES as allowed
        declared = {p for (p,) in db.fetch_query(
            "SELECT platform FROM artist_credentials WHERE artist_id = %s", (artist_id,))}
        # The canary's Instagram identity rides the `meta` credentials row, so the
        # logical platform is not always the row it is stored under.
        from src.utils.tenant_identity import storage_platform

        col = 'collected_at'
        for platform in sorted(SOURCES_FOR_PLATFORM):
            if storage_platform(platform) not in declared:
                continue
            # A platform is healthy if AT LEAST ONE of the tables that prove it is
            # fresh — the same best-of-sources rule the artist's own matrix uses.
            # Spotify can be proven by the API table OR by the S4A CSV; demanding
            # BOTH reports a canary that collects perfectly as mute, which is how a
            # watchdog becomes the noise it exists to prevent.
            ages = []
            for table in sorted(tables_for_platform(platform)):
                if table not in allowed:
                    continue
                ages.append((table, db.fetch_query(
                    f"SELECT EXTRACT(EPOCH FROM (now() - MAX({col})))/3600 "  # noqa: S608
                    f"FROM {table} WHERE artist_id = %s", (artist_id,))[0][0]))
            fresh = [(t, a) for t, a in ages if a is not None and a <= STALE_HOURS]
            if fresh or not ages:
                continue
            seen = [(t, a) for t, a in ages if a is not None]
            if not seen:
                problems.append({'platform': platform, 'reason':
                                 f'canary "{name}" has NEVER collected into '
                                 f'{" or ".join(t for t, _ in ages)}'})
            else:
                t_best, a_best = min(seen, key=lambda x: x[1])
                problems.append({'platform': platform, 'reason':
                                 f'canary "{name}" last collected into {t_best} '
                                 f'{int(a_best)}h ago (> {STALE_HOURS}h)'})

        # Coverage, stated once and explicitly: which platforms this canary can
        # prove, and which it cannot. NOT appended to `problems` — Meta and
        # Instagram cannot be canaried at all without a second real business asset
        # (there is no public ad account, and no public IG Business Account), so
        # alerting on them daily would report a fact that no action changes.
        uncovered = sorted(p for p in SOURCES_FOR_PLATFORM
                           if storage_platform(p) not in declared)
        covered = sorted(p for p in SOURCES_FOR_PLATFORM
                         if storage_platform(p) in declared)
        context['task_instance'].xcom_push(
            key='canary_coverage',
            value={'artist_id': artist_id, 'name': name,
                   'covered': covered, 'uncovered': uncovered})
        if uncovered:
            logger.warning(
                "Canary %s (%s) proves %s and CANNOT prove %s — read any green "
                "verdict about it as covering only the first list.",
                artist_id, name, ", ".join(covered) or "nothing",
                ", ".join(uncovered))

        logger.info(f"Canary {artist_id} ({name}): {len(problems)} problem(s).")
    except Exception as e:  # noqa: BLE001 — an unrunnable check must say so
        logger.error(f"canary health check unavailable: {safe_error(e)}")
        problems.append({'platform': 'canary',
                         'reason': f'check could not run: {safe_error(e)[:180]}'})
    finally:
        if db is not None:
            db.close()

    context['task_instance'].xcom_push(key='canary_problems', value=problems)


# Colonne de locataire des tables surveillées. Allowlist explicite (règle transverse #8) :
# ces noms sont interpolés dans une f-string SQL, donc ils ne peuvent pas venir d'ailleurs
# que d'ici. Vérifié en base le 2026-08-23 : les cinq portent `artist_id` INTEGER.
DIP_TENANT_COLUMN = {
    'youtube_video_stats': 'artist_id',
    'soundcloud_tracks_daily': 'artist_id',
    'meta_insights_performance_day': 'artist_id',
    'ml_song_predictions': 'artist_id',
    's4a_song_timeline': 'artist_id',
}
_DIP_TABLES = frozenset(DIP_TENANT_COLUMN)
_DIP_DATE_COLUMNS = frozenset(col for _t, col in ANOMALY_TABLES)


def check_row_dips(**context):
    """Flag a per-tenant daily-insert DIP: far fewer rows than usual, but not zero.

    R39. `check_row_anomalies` watches only the spike direction, and says so: "freshness
    already covers the opposite (no recent data)". That is true of ZERO rows and false of
    TOO FEW. A recent, partial collection — 3 tracks where 40 usually land — triggers
    neither: freshness sees data from today, the spike check sees no spike. This repo has
    lived that hole twice (SoundCloud "✅ on 0 titles" at the GRiNCH test, Benken's empty
    YouTube channel) and found it by hand both times.

    Moses/Gavish/Vorwerck, *Data Quality Fundamentals* p.144, name it: **Volume — "Has
    all the data arrived?"** is a pillar of its own, distinct from Freshness.

    Two deliberate differences from the spike check:

    * **Per tenant.** A fleet-wide count hides exactly the case that matters: one artist's
      collection collapsing while the others carry the total. This is the whole point.
    * **On the last COMPLETE day** (`day < CURRENT_DATE`). The spike check reads the most
      recent day, which is legitimate for a spike — a double run shows up immediately.
      For a dip it would compare a day still in progress against full days and fire every
      single morning. A detector that cries every day is one nobody reads; the neighbour
      check keeps its own semantics, this one takes the day that is over.

    Le seuil vit dans `src.utils.volume_monitor` — testable sans Airflow, qu'aucun
    DAG de ce dépôt ne permet d'importer hors conteneur.

    Le plancher est MESURÉ sur la prod du 2026-08-23, pas choisi : les volumes réels par
    locataire y sont 1498/j (canari 14), 19/j (admin 1) et **7/j (Benken 12)**. Un
    plancher à 30 — la première valeur écrite ici — aurait rendu le détecteur aveugle à
    deux locataires sur trois, dont précisément celui qui a une panne de collecte vivante.
    À 5, il couvre les trois et ne déclenche sur aucun : la prod est stable. Le seul creux
    trouvé à l'écriture est sur la base LOCALE — SoundCloud y est passé de 19 titres/jour
    à 1 depuis le 2026-08-21 — et c'est exactement la forme que R39 vise.
    """
    from src.database.postgres_handler import PostgresHandler
    from src.utils.volume_monitor import dip_finding, is_partial_collection

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD'),
    )
    dips = []
    try:
        for table, date_col in ANOMALY_TABLES:
            tenant_col = DIP_TENANT_COLUMN.get(table)
            if tenant_col is None:
                continue
            # Règle #8 : allowlist AVANT l'interpolation, jamais après.
            if table not in _DIP_TABLES or date_col not in _DIP_DATE_COLUMNS:
                logger.warning(f"Row-dip: identifiant hors allowlist, table ignorée: {table}")
                continue
            # Filtre S4A obligatoire (CLAUDE.md) : la ligne « Total » du CSV écraserait
            # la référence de chaque locataire et rendrait tout creux invisible.
            extra = ("AND song NOT ILIKE '%1x7xxxxxxx%'"
                     if table == 's4a_song_timeline' else "")
            rows = db.fetch_query(
                f"""WITH d AS (
                        SELECT {tenant_col} AS tenant, {date_col}::date AS day,
                               count(*)::float AS c
                        FROM {table}
                        WHERE {tenant_col} IS NOT NULL
                          AND {date_col}::date < CURRENT_DATE
                          {extra}
                        GROUP BY 1, 2
                    ),
                    last_day AS (
                        SELECT tenant, max(day) AS day FROM d GROUP BY 1
                    )
                    SELECT l.tenant,
                           (SELECT c FROM d WHERE d.tenant = l.tenant AND d.day = l.day),
                           (SELECT avg(c) FROM (
                                SELECT c FROM d
                                WHERE d.tenant = l.tenant AND d.day < l.day
                                ORDER BY d.day DESC LIMIT 7) x),
                           l.day::text
                    FROM last_day l"""
            )
            for tenant, recent, baseline, day in rows or []:
                if is_partial_collection(recent, baseline):
                    dips.append(dip_finding(table, tenant, recent, baseline, day))
                    logger.warning(
                        f"Row dip: {table} tenant={tenant} {int(recent)} on {day} "
                        f"vs ~{baseline:.0f}/day"
                    )
    finally:
        db.close()

    logger.info(f"Row-dip check: {len(dips)} partial collection(s)")
    context['task_instance'].xcom_push(key='row_dips', value=dips)
    return dips


def check_onboarding_readiness(**context):
    """Flag any active artist CONNECTED to a platform but receiving NO data (the silent gap).

    The per-artist closed loop: an artist who provided an identifier (channel_id, account_id…)
    but whose platform produces 0 rows — Benken's empty YouTube channel, a not-shared Meta
    account — becomes a RED flag with the exact next action, instead of staying invisible.

    Since 2026-08-22 the "exact next action" is MEASURED, not guessed. Where the
    database says a platform is red, the same probe the credentials form runs is
    called against the platform's API, and its answer replaces the static hint. That
    is the difference between telling GRiNCH "vérifie ton User ID ; l'app partagée
    doit être configurée (admin)" — a guess, and wrong, and blaming two innocent
    parties — and telling him "ce profil n'a aucun titre public", which is the fact.

    Only reds are probed: fresh rows already prove the credential produced data.
    Today that is 2 API calls a night across the fleet.
    """
    from src.database.postgres_handler import PostgresHandler
    from src.utils.credential_loader import get_active_artists
    from src.utils.artist_readiness import readiness_red_flags, readiness_stalled_flags
    from src.utils.platform_probes import make_budgeted_probe

    # A FLEET budget, not a per-tenant one: shared across every tenant in this run so
    # the cap means what it says at 100 tenants. Exhaustion is logged, never silent.
    budget = [int(os.getenv('READINESS_PROBE_BUDGET', '25'))]

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD'),
    )
    flags = []
    stalled = []
    try:
        # The canary is excluded because it has its OWN reader (check_canary_health);
        # two readers for one fact is `watchdog-becomes-the-noise`.
        for aid, name in get_active_artists(exclude_canaries=True):
            try:
                # Remember every verdict this probe produces. The nightly run is
                # the only thing that measures a red platform without anyone asking,
                # and it used to throw the answer away after the email — so the
                # artist's own screen could not show the sentence the alert carried.
                def _remembering(platform, _aid=aid, _p=make_budgeted_probe(db, aid, budget)):
                    result = _p(platform)
                    if result is not None:
                        try:
                            from src.dashboard.utils.status_matrix import save_probe
                            save_probe(db, _aid, platform, result[0], result[1])
                        except Exception as e:  # noqa: BLE001 — memory is a bonus
                            logger.warning("could not remember probe %s/%s: %s",
                                           _aid, platform, type(e).__name__)
                    return result

                for m in readiness_red_flags(db, aid, probe=_remembering):
                    flags.append({'artist_id': aid, 'artist_name': name,
                                  'platform': m['label'], 'status': m['status'],
                                  'next_action': m['next_action'],
                                  # `probe_ran` distinguishes "the API said this" from
                                  # "we did not ask". Rendering an unmeasured red as a
                                  # measured one is how a truncated night reads as
                                  # full coverage.
                                  'probe_ran': m.get('probe_ran', False)})
                # Signed up, never declared anything. `readiness_red_flags` cannot
                # see them: a tenant who declared no identity produces no NO_DATA row,
                # so the "created an account and stopped" state was invisible to every
                # alert. TODO on day one is correct; TODO after a week is a person
                # nobody followed up with.
                for m in readiness_stalled_flags(db, aid):
                    stalled.append({'artist_id': aid, 'artist_name': name,
                                    'platform': m['label'],
                                    # The LOGICAL key too, not only the label. The
                                    # credentials section keys on it to avoid saying
                                    # the same fact twice — see `already_stated`.
                                    'key': m['key'],
                                    'next_action': m['next_action']})
            except Exception as e:  # per-artist isolation
                logger.error(f"Readiness check failed for {name} (id={aid}): {safe_error(e)}")
                continue
    finally:
        db.close()

    probed = sum(1 for f in flags if f.get('probe_ran'))
    logger.info(f"Onboarding readiness: {len(flags)} needs-a-look flag(s) "
                f"({probed} measured live, {len(flags) - probed} not probed), "
                f"{len(stalled)} stalled tenant(s)")
    context['task_instance'].xcom_push(key='onboarding_red_flags', value=flags)
    context['task_instance'].xcom_push(key='onboarding_stalled', value=stalled)
    return flags



def check_collection_outcomes(**context):
    """Per-tenant collection failures, read from the run ledger.

    This is the check that answers the question no other surface can: **did collection
    run for THIS tenant, and what did the platform actually say?**

    Why it is not redundant with freshness. Freshness reads `MAX(date)` on a table, so
    it can only notice a stopped tenant once the data has aged past a 48h threshold —
    and only for the 7 sources it monitors. The ledger sees the failure the same night,
    carries the LITERAL cause the API returned, and covers a tenant who has never had a
    single row (freshness has nothing to measure there).

    Measured 2026-08-23, and this is the shape it exists for: `youtube_daily` reported
    SUCCESS while Benken failed inside its per-tenant try/except. The only witness was a
    WARNING line, and the task's return value listed the tenants that WORKED — so the
    failing one was absent rather than named.

    `skipped` is deliberately NOT a finding: a tenant who declared no identity is in a
    correct state. It is recorded so the ledger is complete, not so somebody is woken.
    """
    import sys
    sys.path.insert(0, '/opt/airflow')

    WINDOW_H = 36  # one nightly cycle plus margin — a single missed run is not news

    problems = []
    db = None
    try:
        from src.database.postgres_handler import PostgresHandler
        db = PostgresHandler.from_env_or_config()

        # The LAST outcome per (tenant, platform) inside the window. A tenant that
        # failed at 03:00 and succeeded on a manual re-run at 09:00 is not a problem;
        # taking the latest row is what makes that true.
        rows = db.fetch_query(
            """
            SELECT DISTINCT ON (e.artist_id, e.platform)
                   e.artist_id, a.name, e.platform, e.dag_id,
                   e.status, e.error_message, e.started_at
            FROM etl_run_log e
            JOIN saas_artists a ON a.id = e.artist_id
            WHERE e.started_at > now() - make_interval(hours => %s)
              AND e.artist_id IS NOT NULL
            ORDER BY e.artist_id, e.platform, e.started_at DESC
            """,
            (WINDOW_H,),
        )

        for artist_id, name, platform, dag_id, status, error_message, started_at in rows:
            if status not in ('failed', 'partial'):
                continue
            problems.append({
                'artist_id': artist_id,
                'artist_name': name,
                'platform': platform,
                'dag_id': dag_id,
                'status': status,
                # The literal cause, already redacted at write time by safe_error.
                'reason': (error_message or 'no cause recorded')[:300],
                'when': str(started_at),
            })
    except Exception as e:  # noqa: BLE001
        # Same contract as check_central_apps: a check that could not run says so
        # rather than looking like a passing one.
        logger.error(f"collection outcomes unavailable: {safe_error(e)}")
        problems = [{'artist_id': None, 'artist_name': '—', 'platform': 'ALL',
                     'dag_id': '—', 'status': 'unknown',
                     'reason': f'check could not run: {safe_error(e)}', 'when': ''}]
    finally:
        if db:
            db.close()

    logger.info(f"collection outcomes: {len(problems)} tenant/platform failure(s)")
    context['task_instance'].xcom_push(key='collection_failures', value=problems)



def check_offsite_backup(**context):
    """Is there a copy of the database somewhere other than the disk it lives on?

    Measured 2026-09-03: 21 daily archives, all under `/opt/streamlytics/backups` on
    `/dev/sda1` — **the same disk as the database** — and no `rsync`, `s3` or `rclone`
    anywhere in the crontab. A backup that dies with what it protects is a copy, not a
    backup.

    This check is what makes the absence impossible to ignore. `tools/db_backup.sh`
    deliberately still exits 0 when `R2_REMOTE` is unset — turning a working local
    backup red would make it indistinguishable from a broken `pg_dump`. The refusal to
    be silent lives HERE instead: every night, until an offsite copy exists.

    Freshness IS the proof, as everywhere else in this monitor: the question is not
    "is the script installed" but "is there a remote archive younger than 48 h". A
    configured push that quietly stopped working answers the first and fails the second.
    """
    import json
    import os
    import subprocess

    ti = context['ti']
    remote = os.getenv('R2_REMOTE', '').strip()

    if not remote:
        ti.xcom_push(key='offsite_backup', value=[{
            'state': 'absent',
            'detail': "Aucune copie hors-site : R2_REMOTE n'est pas défini. Les "
                      "sauvegardes vivent sur le disque de la base — si ce disque "
                      "meurt, elles meurent avec.",
            'action': "Créer le bucket R2, `rclone config`, puis poser R2_REMOTE "
                      "dans .env et recréer airflow-scheduler.",
        }])
        logger.warning("Offsite backup: NOT CONFIGURED (R2_REMOTE unset)")
        return

    try:
        out = subprocess.run(
            ['rclone', 'lsjson', remote, '--include', '*.sql.gz'],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        ti.xcom_push(key='offsite_backup', value=[{
            'state': 'unreadable',
            'detail': f"Impossible d'interroger {remote} : {type(exc).__name__}.",
            'action': "Vérifier que rclone est installé et que le remote répond.",
        }])
        logger.error("Offsite backup: probe failed (%s)", type(exc).__name__)
        return

    if out.returncode != 0:
        ti.xcom_push(key='offsite_backup', value=[{
            'state': 'unreadable',
            'detail': f"rclone a répondu {out.returncode} sur {remote}.",
            'action': "Vérifier les credentials R2 et le nom du bucket.",
        }])
        logger.error("Offsite backup: rclone rc=%s", out.returncode)
        return

    try:
        entries = json.loads(out.stdout or '[]')
    except ValueError:
        entries = []

    if not entries:
        ti.xcom_push(key='offsite_backup', value=[{
            'state': 'empty',
            'detail': f"{remote} est vide — aucune archive n'y est jamais arrivée.",
            'action': "Lancer `bash tools/db_backup.sh` à la main et lire sa sortie.",
        }])
        logger.error("Offsite backup: remote is EMPTY")
        return

    newest = max(e.get('ModTime', '') for e in entries)
    age_h = None
    try:
        from datetime import datetime, timezone
        parsed = datetime.fromisoformat(newest.replace('Z', '+00:00'))
        age_h = (datetime.now(timezone.utc) - parsed).total_seconds() / 3600
    except (ValueError, TypeError):
        pass

    # 48 h and not 24: the cron runs daily at 03:00, so a single missed night is a
    # blip, two is a pattern. Same reasoning as `check_data_freshness`, which this
    # deliberately mirrors rather than inventing its own cadence.
    if age_h is not None and age_h > 48:
        ti.xcom_push(key='offsite_backup', value=[{
            'state': 'stale',
            'detail': f"La dernière archive distante a {age_h:.0f} h "
                      f"({len(entries)} au total sur {remote}).",
            'action': "Lire /var/log/streamlytics-backup.log : la copie a cessé.",
        }])
        logger.error("Offsite backup: STALE (%.0f h)", age_h)
        return

    logger.info("Offsite backup: %d archive(s), newest %.0f h old",
                len(entries), age_h if age_h is not None else -1)


def check_tenant_contamination(**context):
    """Rows sitting under a tenant they cannot belong to, across the whole fleet.

    This is the only class this repository has actually been bitten by — every tenant's
    Spotify popularity history filed under `artist_id = 1` for months, in production,
    undetected — and until now it was the only one with **no watchdog**. The scan was
    reachable from `make tenant-check` and from step 5 of `artist_preflight`, i.e. only
    when a human typed a command; `check_canary_preflight` runs steps 2-4 only.

    Why the other checks cannot see it: rows ARE arriving, so freshness is green,
    readiness is green, and the canary is green. They just belong to somebody else.

    `scan(db)` never writes. Three finding kinds: ORPHAN (rows for a platform this
    tenant never declared — they were fetched under someone else's identity), MISMATCH
    (the row carries a platform id that is not the tenant's) and MISATTRIBUTED (a
    join disagrees about the owner).
    """
    import sys
    sys.path.insert(0, '/opt/airflow')

    problems = []
    db = None
    try:
        from src.database.postgres_handler import PostgresHandler
        # `tools/` is a PEP 420 namespace package under /opt/airflow, mounted read-only
        # by every Airflow service. The mount does NOT travel with `git pull` (the
        # production compose is gitignored) — check_prod_ledger.sh verifies it, so this
        # task only has to fail LOUDLY when the import does not resolve.
        from tools.tenant_contamination_check import scan
    except ImportError as e:
        # Same contract as check_central_apps and check_canary_preflight: a check that
        # could not run says so, instead of looking like a passing one.
        logger.error(f"contamination scan unavailable: {safe_error(e)}")
        context['task_instance'].xcom_push(
            key='contamination',
            value=[{'artist_id': None, 'artist': '—', 'platform': 'ALL', 'table': '—',
                    'kind': 'UNAVAILABLE', 'rows': 0,
                    'detail': f'check could not run: {safe_error(e)}'}])
        return

    try:
        db = PostgresHandler.from_env_or_config()
        problems = scan(db) or []
    except Exception as e:  # noqa: BLE001
        logger.error(f"contamination scan failed: {safe_error(e)}")
        problems = [{'artist_id': None, 'artist': '—', 'platform': 'ALL', 'table': '—',
                     'kind': 'UNAVAILABLE', 'rows': 0,
                     'detail': f'check could not run: {safe_error(e)}'}]
    finally:
        if db:
            db.close()

    logger.info(f"contamination scan: {len(problems)} finding(s)")
    context['task_instance'].xcom_push(key='contamination', value=problems)


def check_canary_preflight(**context):
    """Run the artist-session gate against the canary, on a schedule.

    `tools/artist_preflight.py` is what the runbook trusts — "on n'invite personne
    tant que `make artist-preflight` n'est pas vert" — and until 2026-08-22 nothing
    ran it but a human who remembered to. No CI job, no cron, no record that it was
    ever green. A gate whose execution depends on somebody's memory is a gate that
    reports on the days you did not need it.

    Steps 2-4 only: step 1 is already covered by `check_central_apps` above, and
    step 5 overlaps `check_canary_health` plus the contamination scan. Scoped to the
    platforms the canary actually DECLARES, computed rather than hardcoded — the
    documented production invocation is `--platforms youtube`, which proves one
    platform out of five.
    """
    problems = []
    try:
        import io
        import json
        from contextlib import redirect_stdout

        from src.database.postgres_handler import PostgresHandler
        from src.utils.tenant_identity import declared_identities
        from tools.artist_preflight import (step_connection_tests, step_data_landed,
                                            step_identity)
    except ImportError as e:
        # Same contract as check_central_apps: an unrunnable check says so rather
        # than looking like a passing one.
        logger.error(f"canary preflight unavailable: {safe_error(e)}")
        context['task_instance'].xcom_push(
            key='canary_preflight',
            value=[{'step': 'ALL', 'reason': f'check could not run: {safe_error(e)}'}])
        return

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD'),
    )
    try:
        rows = db.fetch_query(
            "SELECT id, name FROM saas_artists WHERE is_canary = TRUE AND active = TRUE "
            "ORDER BY id LIMIT 1")
        if not rows:
            # Handled by check_canary_health, which already reports the absence.
            logger.info("no canary tenant — preflight skipped (canary health reports it)")
            context['task_instance'].xcom_push(key='canary_preflight', value=[])
            return
        artist_id, name = rows[0]

        extra = {}
        for platform, cfg in db.fetch_query(
                "SELECT platform, extra_config FROM artist_credentials "
                "WHERE artist_id = %s", (artist_id,)):
            if isinstance(cfg, str):
                try:
                    cfg = json.loads(cfg)
                except ValueError:
                    cfg = {}
            extra[platform] = cfg or {}
        scope = declared_identities(extra)
        if not scope:
            context['task_instance'].xcom_push(
                key='canary_preflight',
                value=[{'step': 'identity',
                        'reason': f'canary "{name}" declares no platform identity — '
                                  f'it can prove nothing'}])
            return

        buf = io.StringIO()
        for label, fn_step in (("identity", step_identity),
                               ("connection tests", step_connection_tests),
                               ("data landed", step_data_landed)):
            try:
                with redirect_stdout(buf):
                    ok = fn_step(db, artist_id, scope)
            except Exception as e:  # per-step isolation
                ok, e_msg = False, safe_error(e)[:200]
                problems.append({'step': label,
                                 'reason': f'step raised: {e_msg}'})
                continue
            if not ok:
                problems.append({
                    'step': label,
                    'reason': f'canary "{name}" fails preflight step "{label}" '
                              f'for {", ".join(sorted(scope))}'})
        logger.info(buf.getvalue())
    except Exception as e:
        problems.append({'step': 'ALL', 'reason': f'check could not run: {safe_error(e)}'})
        logger.error(f"canary preflight raised: {safe_error(e)}")
    finally:
        db.close()

    logger.info(f"Canary preflight: {len(problems)} problem(s)")
    context['task_instance'].xcom_push(key='canary_preflight', value=problems)


# ─────────────────────────────────────────────────────────────────
# Task 4 — Build and send consolidated alert email
# ─────────────────────────────────────────────────────────────────

def _record_quiet_run():
    """A run that found nothing. `delivery_expected = FALSE` — no mail is owed."""
    try:
        from src.database.postgres_handler import PostgresHandler
        db = PostgresHandler.from_env_or_config()
        try:
            return db.fetch_query(
                "INSERT INTO monitoring_run (subject, issues_count, delivery_expected) "
                "VALUES (%s, 0, FALSE) RETURNING id", ("(rien à signaler)",))[0][0]
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.error("could not record the quiet run: %s", safe_error(e))
        return None


def _record_alert_attempt(subject: str, issues_count: int, digest: str = None):
    """Open a `monitoring_run` row before attempting delivery. Never raises.

    Bookkeeping must not be able to block the alert: if this fails we log and return
    None, and the send still happens. A blind external reader is a finding, a
    suppressed alert is an incident.
    """
    try:
        from src.database.postgres_handler import PostgresHandler
        db = PostgresHandler.from_env_or_config()
        try:
            rows = db.fetch_query(
                "INSERT INTO monitoring_run (subject, issues_count, delivery_expected, "
                "findings_digest) VALUES (%s, %s, TRUE, %s) RETURNING id",
                (subject, issues_count, digest))
            return rows[0][0]
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001 — see docstring
        logger.error("could not open the alert-delivery ledger row: %s", safe_error(e))
        return None


def _last_delivered_digest():
    """(findings_digest, run_at) of the last alert that actually LEFT, or (None, None).

    `WHERE delivered` is load-bearing twice over. A suppressed night must not become
    the comparison point — the silence window would re-arm itself every night and
    never close again — and neither must a FAILED delivery, whose findings nobody
    ever read.

    Any failure here returns (None, None), which makes the caller send. Bookkeeping
    that cannot be read is a reason to mail, never a reason to stay quiet.
    """
    try:
        from src.database.postgres_handler import PostgresHandler
        db = PostgresHandler.from_env_or_config()
        try:
            rows = db.fetch_query(
                "SELECT findings_digest, run_at FROM monitoring_run "
                "WHERE delivered AND findings_digest IS NOT NULL "
                "ORDER BY run_at DESC LIMIT 1")
            return (rows[0][0], rows[0][1]) if rows else (None, None)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001 — see docstring
        logger.error("could not read the last delivered digest: %s", safe_error(e))
        return (None, None)


def _record_suppressed_repeat(subject: str, issues_count: int, digest: str, why: str):
    """Record a night whose findings were identical to the last delivered mail.

    `delivery_expected = FALSE` on purpose, exactly like a quiet night: no mail was
    owed, so `tools/infra_health_cron.sh` — which reads the latest row and escalates
    `expected AND NOT delivered` — must not read a suppression as an alert-channel
    outage. The row still exists, so "nothing changed" and "the scheduler never ran"
    stay distinguishable, which is the whole point of migration 073.
    """
    try:
        from src.database.postgres_handler import PostgresHandler
        db = PostgresHandler.from_env_or_config()
        try:
            db.execute_query(
                "INSERT INTO monitoring_run (subject, issues_count, delivery_expected, "
                "delivered, delivery_error, findings_digest) "
                "VALUES (%s, %s, FALSE, FALSE, %s, %s)",
                (f"(répétition non envoyée) {subject}", issues_count, why, digest))
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.error("could not record the suppressed repeat: %s", safe_error(e))


def _close_alert_attempt(run_id, delivered: bool, error) -> None:
    """Record the outcome. Never raises, for the same reason."""
    if run_id is None:
        return
    try:
        from src.database.postgres_handler import PostgresHandler
        db = PostgresHandler.from_env_or_config()
        try:
            db.execute_query(
                "UPDATE monitoring_run SET delivered = %s, delivery_error = %s "
                "WHERE id = %s", (delivered, error, run_id))
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.error("could not close the alert-delivery ledger row: %s", safe_error(e))


def send_consolidated_alert(**context):
    """Assemble one email with all findings: failures, freshness, missing creds."""
    from src.utils.alert_repetition import (
        digest_input, findings_digest, suppression_reason)
    from src.utils.email_alerts import AlertDeliveryError, deliver_or_raise

    ti = context['task_instance']
    failing_dags = ti.xcom_pull(task_ids='check_dag_failures', key='failing_dags') or {}
    freshness = ti.xcom_pull(task_ids='check_data_freshness', key='freshness_results') or []
    missing_creds = ti.xcom_pull(task_ids='check_credentials_all', key='missing_credentials') or []
    sparks = ti.xcom_pull(task_ids='check_resurrection_sparks', key='resurrection_sparks') or []
    drift = ti.xcom_pull(task_ids='check_drift_anomalies', key='drift_anomalies') or []
    billing_issues = ti.xcom_pull(task_ids='check_billing_sync', key='billing_issues') or []
    row_anomalies = ti.xcom_pull(task_ids='check_row_anomalies', key='row_anomalies') or []
    row_dips = ti.xcom_pull(task_ids='check_row_dips', key='row_dips') or []
    tenant_gaps = ti.xcom_pull(task_ids='check_data_freshness', key='tenant_freshness_gaps') or []
    central_broken = ti.xcom_pull(task_ids='check_central_apps',
                                  key='central_apps_broken') or []
    readiness_flags = ti.xcom_pull(task_ids='check_onboarding_readiness', key='onboarding_red_flags') or []
    stalled_tenants = ti.xcom_pull(task_ids='check_onboarding_readiness', key='onboarding_stalled') or []
    canary_preflight = ti.xcom_pull(task_ids='check_canary_preflight', key='canary_preflight') or []

    canary = ti.xcom_pull(task_ids='check_canary_health', key='canary_problems') or []

    collection_failures = ti.xcom_pull(
        task_ids='check_collection_outcomes', key='collection_failures') or []

    contamination = ti.xcom_pull(
        task_ids='check_tenant_contamination', key='contamination') or []

    offsite = ti.xcom_pull(
        task_ids='check_offsite_backup', key='offsite_backup') or []

    # Both checks ask the SAME question — `readiness_stalled_flags` returns the
    # platforms at TODO, `check_credentials_all` the ones absent from
    # `declared_identities()`, and TODO *is* "no declared identity". So `stalled` is
    # `missing_creds` restricted to accounts older than a week: a strict subset, by
    # construction and not by coincidence. The mail of 2026-08-26 printed the
    # intersection twice — 11 rows of 12 — under two different action wordings for
    # one gesture, and counted them again in the subject.
    #
    # Subtracted rather than deduplicated away: the stalled section is kept because
    # it names the exact field to fill, and what survives here is what it does NOT
    # say — tonight, one line, and that line is the one worth a question.
    already_stated = {(s_['artist_id'], s_.get('key')) for s_ in stalled_tenants}
    _n_before = len(missing_creds)
    missing_creds = [m for m in missing_creds
                     if (m['artist_id'], m['platform']) not in already_stated]
    # Say how many were removed, and never say it silently: a section that shrinks
    # without explaining itself reads as coverage that got smaller.
    _dropped = _n_before - len(missing_creds)
    _stated_note = (f" ({_dropped} ligne(s) déjà dite(s) dans « Inscrits sans rien "
                    f"connecter »)" if _dropped else "")

    stale_sources = [r for r in freshness if r['stale']]
    # `central_broken` and `canary` belong in this decision, not only in the body.
    # They were rendered at the bottom of this function and in the subject line, but
    # were NOT part of has_issues — so a broken shared app, ALONE, produced no email
    # at all: the function returned early just below. Masked today only because Meta
    # is simultaneously broken and stale. The check added to break a silence was
    # itself silent (found 2026-08-21).
    # `offsite` joins for the same reason, and it is the clearest case yet: an
    # absent offsite copy is a state that can persist for months with every other
    # signal green, so it would be the ONLY finding on most nights. Rendered but not
    # decisive, it would have produced exactly the silence it exists to break —
    # caught here by `test_every_pulled_finding_takes_part_in_the_send_decision`
    # before it shipped, which is the guard doing precisely its job.
    has_issues = (failing_dags or stale_sources or missing_creds or sparks or drift
                  or billing_issues or row_anomalies or row_dips or tenant_gaps or readiness_flags
                  or central_broken or canary or stalled_tenants
                  or canary_preflight or collection_failures or contamination
                  or offsite)

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    if not has_issues:
        # Record the quiet night as well. Without a row, "nothing to report" and
        # "the scheduler never ran" look identical to any external reader — and the
        # second is the one that hides everything else.
        _close_alert_attempt(_record_quiet_run(), delivered=True, error=None)
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
            # A source whose CHECK failed is not a stale source, and telling the
            # reader to relaunch a DAG for it sends them to fix the wrong thing.
            # `error` is carried in the xcom for exactly this line.
            probe_error = r.get('error')
            if probe_error:
                age_label = 'non mesurée'
                colour = '#c0392b'
                # Rédigé : ce texte part dans l'e-mail d'alerte, et l'erreur
                # d'une sonde est un message d'exception HTTP — donc `key=`
                # (YouTube) ou `access_token=` (Meta), en query string.
                action = f"⚠️ la sonde elle-même a échoué : {redact(probe_error)}"
            else:
                age_label = (f"{r['age_h']:.0f}h" if r['age_h'] is not None
                             else 'jamais collectée')
                colour = '#e67e22'
                measured = ('date de la métrique' if r.get('measured_on') == 'metric'
                            else "date d'écriture")
                if r.get('fed_by') == 'csv':
                    # Nothing arrives here until a human drops an export. Relaunching
                    # the watcher over an empty dropbox is an action that cannot
                    # change the state — and both stale sources of 2026-08-26 were of
                    # this kind, so the mail named an impossible gesture twice out of
                    # twice. ADR-011: an alert names a symptom AND a workable action.
                    action = (f"Déposer un export {r['source']} — cette source attend "
                              f"un CSV, relancer son DAG ne collecte rien ({measured})")
                else:
                    action = f"Airflow UI → relancer le DAG correspondant ({measured})"
            rows += f"""
            <tr>
              <td style="padding:6px 12px;border-bottom:1px solid #eee"><b>{r['source']}</b></td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:{colour}">{age_label}</td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">{r['stale_h']}h</td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#888">
                {action}
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

    # Section: the artist-session gate, run on a schedule instead of from memory.
    if canary_preflight:
        rows = ''
        for f in canary_preflight:
            rows += (
                f"<tr><td style='padding:6px 12px;border-bottom:1px solid #eee'>"
                f"<b>{f['step']}</b></td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>"
                f"{as_html(f['reason'])}</td></tr>"
            )
        sections.append(f"""
        <h2 style="color:#d35400;border-left:4px solid #d35400;padding-left:10px">
          🐤 Le canari ne passe plus le préflight ({len(canary_preflight)})
        </h2>
        <p style="font-size:0.9em;color:#555">
          C'est le contrôle que le runbook exige avant d'inviter un artiste. Rouge ici
          veut dire qu'une session artiste échouerait aujourd'hui.
        </p>
        <table style="border-collapse:collapse;width:100%;font-size:0.9em">
          <thead><tr style="background:#fdf1e8">
            <th style="padding:8px 12px;text-align:left">Étape</th>
            <th style="padding:8px 12px;text-align:left">Constat</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>""")

    # Section: tenants who signed up and never declared anything.
    #
    # Invisible to every alert until 2026-08-22: `readiness_red_flags` only returns
    # NO_DATA, and a tenant who declared no identity produces no NO_DATA row at all.
    # So "created an account, opened nothing, gave up" — the most likely outcome of a
    # beta invitation — was the one state nobody was told about.
    if stalled_tenants:
        rows = ''
        for f in stalled_tenants:
            rows += (
                f"<tr><td style='padding:6px 12px;border-bottom:1px solid #eee'>"
                f"<b>{escape(f['artist_name'])}</b> (id={f['artist_id']})</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{f['platform']}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee;color:#8e44ad'>"
                f"{as_html(f['next_action'])}</td></tr>"
            )
        sections.append(f"""
        <h2 style="color:#8e44ad;border-left:4px solid #8e44ad;padding-left:10px">
          ⚪ Inscrits sans rien connecter depuis 7 jours ({len(stalled_tenants)})
        </h2>
        <table style="border-collapse:collapse;width:100%;font-size:0.9em">
          <thead><tr style="background:#f6f0fa">
            <th style="padding:8px 12px;text-align:left">Artiste</th>
            <th style="padding:8px 12px;text-align:left">Plateforme</th>
            <th style="padding:8px 12px;text-align:left">Action</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>""")

    # Section: onboarding readiness — connected to a platform but receiving NO data
    if readiness_flags:
        rows = ''
        for f in readiness_flags:
            rows += (
                f"<tr><td style='padding:6px 12px;border-bottom:1px solid #eee'>"
                f"<b>{escape(f['artist_name'])}</b> (id={f['artist_id']})</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{f['platform']}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>"
                f"{'⚠️ sonde en échec' if f.get('status') == 'broken' else '🔴 aucune donnée'}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee;color:#2980b9'>"
                f"{as_html(f['next_action'])}</td></tr>"
            )
        sections.append(f"""
        <h2 style="color:#c0392b;border-left:4px solid #c0392b;padding-left:10px">
          🔴 À regarder ({len(readiness_flags)})
        </h2>
        <table style="border-collapse:collapse;width:100%;font-size:0.9em">
          <thead><tr style="background:#fdf3f2">
            <th style="padding:8px 12px;text-align:left">Artiste</th>
            <th style="padding:8px 12px;text-align:left">Plateforme</th>
            <th style="padding:8px 12px;text-align:left">État</th>
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
        <p style="font-size:0.85em;color:#777;margin:0 0 8px">
          Hors ceux déjà listés ci-dessus{_stated_note} — même fait, même geste.
        </p>
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
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#c0392b">{as_html(b['reason'])}</td>
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

    # Section: per-tenant collection dips (R39 — pilier Volume, l'autre sens).
    if row_dips:
        items = ''.join(
            f"<li>artiste <b>{d['tenant']}</b> — <b>{d['table']}</b> : {d['recent']} "
            f"ligne(s) le {d['day']} vs ~{d['baseline']:.0f}/j "
            f"(−{100 - 100 * d['recent'] / max(d['baseline'], 1):.0f}%)</li>"
            for d in row_dips
        )
        sections.append(f"""
        <h2 style="color:#e67e22;border-left:4px solid #e67e22;padding-left:10px">
          📉 Collecte partielle ({len(row_dips)})
        </h2>
        <p style="color:#888;font-size:0.9em">Des données sont bien arrivées, mais
          beaucoup moins que d'habitude pour CE locataire — la fraîcheur ne voit rien
          (il y a des lignes) et le détecteur de pic non plus. Vérifier les credentials
          et le périmètre collecté de cet artiste.</p>
        <ul style="font-size:0.9em">{items}</ul>""")

    # Section: offsite backup. First, and on purpose. Every other finding here is
    # about data that did not arrive; this one is about the data already held having
    # no copy anywhere else. It is the only line in this mail that describes a way to
    # lose everything at once, and `tools/db_backup.sh` deliberately stays green
    # without it — so if this section is silent, nothing else says it.
    if offsite:
        rows = ''
        for o in offsite:
            rows += f"""
            <tr>
              <td style="padding:6px 12px;border-bottom:1px solid #eee"><b>{o['state']}</b></td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">{o['detail']}</td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#555">
                {o['action']}
              </td>
            </tr>"""
        sections.append(f"""
        <h3 style="color:#b00">💾 Sauvegarde hors-site</h3>
        <table style="border-collapse:collapse;font-size:0.9em">
          <tr><th style="text-align:left;padding:6px 12px">État</th>
              <th style="text-align:left;padding:6px 12px">Constat</th>
              <th style="text-align:left;padding:6px 12px">Geste</th></tr>
          {rows}
        </table>""")

    # Section: tenant contamination. Deliberately assembled before the others: a row
    # sitting under a tenant it cannot belong to is the only finding here that is a
    # data-integrity fault rather than a collection gap, and it is the class this
    # repository has actually been bitten by.
    if contamination:
        rows = ''
        for c in contamination:
            rows += f"""
            <tr>
              <td style="padding:6px 12px;border-bottom:1px solid #eee"><b>{c['kind']}</b></td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">{c['artist']}</td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">{c['table']}</td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">{c['rows']}</td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#555">
                {c['detail']}
              </td>
            </tr>"""

        sections.append(f"""
        <h2 style="color:#8e44ad;border-left:4px solid #8e44ad;padding-left:10px">
          🧬 Contamination locataire ({len(contamination)})
        </h2>
        <p style="color:#888;font-size:0.9em">Des lignes portent un locataire auquel elles
          ne peuvent pas appartenir. Rien d'autre ne le voit : les lignes ARRIVENT, donc
          la fraîcheur, la readiness et le canari sont tous verts.</p>
        <table style="border-collapse:collapse;width:100%;font-size:0.9em">
          <thead>
            <tr style="background:#f6f0fa">
              <th style="padding:8px 12px;text-align:left">Type</th>
              <th style="padding:8px 12px;text-align:left">Locataire</th>
              <th style="padding:8px 12px;text-align:left">Table</th>
              <th style="padding:8px 12px;text-align:left">Lignes</th>
              <th style="padding:8px 12px;text-align:left">Détail</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>""")

    # Section: per-tenant collection failures, read from the run ledger. This is the
    # only section that names the LITERAL cause the platform returned for one tenant,
    # the same night it happened — freshness needs 48h and 7 monitored tables to say
    # anything at all.
    if collection_failures:
        rows = ''
        for f in collection_failures:
            rows += f"""
            <tr>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">
                <b>{f['artist_name']}</b> <span style="color:#888">(id={f['artist_id']})</span>
              </td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee">{f['platform']}</td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#c0392b">
                {f['status']}
              </td>
              <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#555">
                {as_html(f['reason'])}
              </td>
            </tr>"""

        sections.append(f"""
        <h2 style="color:#c0392b;border-left:4px solid #c0392b;padding-left:10px">
          🔴 Collecte en échec par locataire ({len(collection_failures)})
        </h2>
        <p style="color:#888;font-size:0.9em">Le DAG peut être vert : un échec est isolé
          par locataire pour ne pas emporter la flotte. Ceci est le registre
          <code>etl_run_log</code>, et la cause est celle que la plateforme a
          répondue.</p>
        <table style="border-collapse:collapse;width:100%;font-size:0.9em">
          <thead>
            <tr style="background:#fdf2f0">
              <th style="padding:8px 12px;text-align:left">Locataire</th>
              <th style="padding:8px 12px;text-align:left">Plateforme</th>
              <th style="padding:8px 12px;text-align:left">Issue</th>
              <th style="padding:8px 12px;text-align:left">Cause</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>""")

    # OK sources footer. A source whose silence is expected is NOT "OK" — it is
    # quiet, and it has a measured reason. Merging the two would state that Meta Ads
    # collected fine last night while its last insight row is two years old.
    quiet_sources = [r for r in freshness if r.get('expected_silence')]
    ok_sources = [r['source'] for r in freshness
                  if not r['stale'] and not r.get('expected_silence')]
    ok_line = ''
    if ok_sources:
        ok_line = (
            f"<p style='color:#27ae60'>✅ Sources OK : {', '.join(ok_sources)}</p>"
        )
    if quiet_sources:
        items = ''.join(
            f"<li><b>{r['source']}</b> — {r['expected_silence']}</li>"
            for r in quiet_sources
        )
        ok_line += (
            "<p style='color:#888'>⏸️ Sans alerte, car il n'y a rien à collecter :</p>"
            f"<ul style='color:#888;font-size:0.9em'>{items}</ul>"
        )

    # First block in the body, for the same reason it is first in the subject:
    # everything below it may be a consequence of it.
    central_html = ""
    if central_broken:
        rows = ''.join(
            f"<li><b>{c['platform']}</b> — {as_html(c['reason'])}</li>" for c in central_broken)
        central_html = (
            '<div style="background:#fdecea;border-left:4px solid #c0392b;'
            'padding:12px 16px;margin:16px 0">'
            '<h2 style="color:#c0392b;margin:0 0 8px">🚨 App partagée hors service</h2>'
            "<p style=\"margin:0 0 8px\">Une app admin n'authentifie plus : "
            "<b>aucun locataire</b> ne collecte sur cette plateforme, quels que soient "
            "leurs identifiants. Les alertes par locataire ci-dessous en sont "
            "probablement la conséquence.</p>"
            f"<ul style=\"margin:0\">{rows}</ul>"
            '<p style="margin:8px 0 0;font-size:0.9em">Vérifier : '
            "<code>python3 tools/check_central_apps.py --require</code></p></div>"
        )

    if canary:
        # The canary is the only tenant whose silence is a signal about EVERY tenant.
        # Its section sits next to the shared apps because both are fleet-wide.
        sections.append(
            "<h3>🐤 Canari — le locataire témoin ne collecte plus</h3><ul>"
            + "".join(f"<li><b>{c['platform']}</b> — {as_html(c['reason'])}</li>" for c in canary)
            + "</ul><p>Un signal global peut rester vert pendant que la chaîne "
              "<i>par locataire</i> est cassée : une source reste fraîche tant qu'UN "
              "locataire collecte, et c'est presque toujours l'admin. C'est exactement "
              "ce que ce locataire existe pour rendre visible.</p>")

    # Lue à l'appel : ce lien part dans un e-mail, et `localhost` y est mort pour
    # tout destinataire (même classe que `APP_BASE_URL`, fermée le 2026-08-23).
    from src.utils.instance_identity import airflow_base_url

    _airflow_url = airflow_base_url()
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto">
      <h1 style="color:#2c3e50">📊 Monitoring Music Platform — {now_str}</h1>
      {central_html}
      {''.join(sections)}
      {ok_line}
      <hr style="border:none;border-top:1px solid #eee;margin-top:24px">
      <p style="color:#aaa;font-size:0.8em">
        Généré par alert_monitor DAG — Airflow : <a href="{_airflow_url}">{_airflow_url}</a>
      </p>
    </div>
    """

    subject_parts = []
    if central_broken:
        # First in the subject on purpose: a shared app that stops authenticating
        # takes every tenant down at once, so it outranks any per-tenant symptom
        # listed after it — several of which it will itself have caused.
        subject_parts.append(
            "🚨 APP PARTAGÉE HS : " + ', '.join(c['platform'] for c in central_broken))
    if canary:
        subject_parts.append("🐤 CANARI MUET")
    # Third, and the line the two beta failures needed. `readiness_flags` and
    # `tenant_gaps` rendered body sections since they were written and appeared in
    # NO subject: a night whose only findings were "Benken ne collecte pas Meta" and
    # "GRiNCH ne collecte pas SoundCloud" produced an email titled
    # "🚨 Dashboard Alert:" followed by nothing. Named tenants, capped at three so the
    # subject stays a subject.
    if readiness_flags or canary_preflight:
        _names = []
        for f in readiness_flags:
            label = f"{f['artist_name']} ({f['platform']})"
            if label not in _names:
                _names.append(label)
        shown, extra = _names[:3], len(_names) - 3
        if shown:
            subject_parts.append("🔴 NE COLLECTE PAS : " + ", ".join(shown)
                                 + (f" +{extra}" if extra > 0 else ""))
        if canary_preflight:
            subject_parts.append("🐤 PRÉFLIGHT ROUGE")
    if contamination:
        _kinds = sorted({c['kind'] for c in contamination})
        subject_parts.append(f"🧬 CONTAMINATION : {len(contamination)} "
                             f"({', '.join(_kinds)})")
    if collection_failures:
        _cf = []
        for f in collection_failures:
            label = f"{f['artist_name']} ({f['platform']})"
            if label not in _cf:
                _cf.append(label)
        shown, extra = _cf[:3], len(_cf) - 3
        subject_parts.append("🔴 COLLECTE KO : " + ", ".join(shown)
                             + (f" +{extra}" if extra > 0 else ""))
    if failing_dags:
        subject_parts.append(f"{len(failing_dags)} DAG(s) en échec")
    if stale_sources:
        subject_parts.append(f"{len(stale_sources)} source(s) stale")
    if missing_creds:
        subject_parts.append(f"{len(missing_creds)} credential(s) manquant(s)")
    # Opportunities and diagnostics, not failures. They go in the subject only when
    # there is nothing broken to report — otherwise "✨ 2 résurrection(s)" sits beside
    # a tenant collecting nothing, which is alert fatigue in its purest form.
    _nothing_broken = not subject_parts
    if sparks and _nothing_broken:
        subject_parts.append(f"✨ {len(sparks)} résurrection(s)")
    if drift:
        subject_parts.append(f"📉 {len(drift)} drift(s)")
    if billing_issues:
        subject_parts.append(f"💳 {len(billing_issues)} abonnement(s)")
    if row_anomalies:
        subject_parts.append(f"📈 {len(row_anomalies)} pic(s)")
    if row_dips:
        subject_parts.append(f"📉 {len(row_dips)} collecte(s) partielle(s)")

    # An empty subject was reachable: the four tenant-level signals contributed no
    # subject text, so a night carrying only those sent "🚨 Dashboard Alert:" and
    # nothing else. Never send an untitled alert — it is unreadable in a mailbox and
    # indistinguishable from a bug in the mailer.
    subject = ' | '.join(subject_parts) or f"{len(sections)} constat(s) — voir le détail"

    # Record the attempt BEFORE making it, then update. The order is load-bearing:
    # if delivery raises, the row already exists saying `delivered = FALSE`, and the
    # external reader (infra_health_cron.sh, which mails via Brevo and therefore
    # survives exactly the SMTP outage that silenced us) sees the failure. A row
    # written only after a successful send would leave no trace of the one case that
    # matters.
    # Is this the same mail as the last one that actually left? Computed on the
    # findings, not on the subject: the subject truncates to three names and a "+2",
    # so two genuinely different nights can share one. Measured 2026-08-28 — the runs
    # of 25 and 26 August differ only by `age_h` and `when`, both of which move on
    # their own; the findings, the tenants and the gestures were word-for-word equal.
    digest = findings_digest(digest_input(
        failing_dags=failing_dags, stale_sources=stale_sources,
        missing_creds=missing_creds, sparks=sparks, drift=drift,
        billing_issues=billing_issues, row_anomalies=row_anomalies,
        row_dips=row_dips, tenant_gaps=tenant_gaps,
        central_broken=central_broken, canary=canary,
        readiness_flags=readiness_flags, stalled_tenants=stalled_tenants,
        canary_preflight=canary_preflight,
        collection_failures=collection_failures, contamination=contamination,
    ))
    _last_digest, _last_at = _last_delivered_digest()
    suppressed = suppression_reason(digest, _last_digest, _last_at)
    if suppressed:
        _record_suppressed_repeat(subject, len(sections), digest, suppressed)
        logger.info("✉️  not re-sent (%s): %s", suppressed, subject)
        return

    run_id = _record_alert_attempt(subject, len(sections), digest)
    try:
        deliver_or_raise(subject, body)
    except AlertDeliveryError as exc:
        _close_alert_attempt(run_id, delivered=False, error=safe_error(exc))
        # Fail the task. `send_alert` returned False and the next line used to log
        # "Consolidated alert sent" regardless — three nights of findings evaporated
        # that way (16, 17, 18 Aug 2026) while the task stayed green.
        raise
    _close_alert_attempt(run_id, delivered=True, error=None)
    logger.info(f"Consolidated alert delivered: {subject}")


# ─────────────────────────────────────────────────────────────────
# DAG definition
# ─────────────────────────────────────────────────────────────────

with DAG(
    dag_id='alert_monitor',
    default_args=default_args,
    description='Monitoring consolidé : failures, freshness, credentials — envoi email quotidien',
    schedule='0 23 * * *',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    dagrun_timeout=dagrun_timeout_for('alert_monitor'),
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

    t_dips = PythonOperator(
        task_id='check_row_dips',
        python_callable=check_row_dips,
    )

    t_readiness = PythonOperator(
        task_id='check_onboarding_readiness',
        python_callable=check_onboarding_readiness,
    )

    t_central = PythonOperator(
        task_id='check_central_apps',
        python_callable=check_central_apps,
    )

    t_canary = PythonOperator(
        task_id='check_canary_health',
        python_callable=check_canary_health,
    )

    t_preflight = PythonOperator(
        task_id='check_canary_preflight',
        python_callable=check_canary_preflight,
    )

    t_outcomes = PythonOperator(
        task_id='check_collection_outcomes',
        python_callable=check_collection_outcomes,
    )

    t_contamination = PythonOperator(
        task_id='check_tenant_contamination',
        python_callable=check_tenant_contamination,
    )

    t_offsite = PythonOperator(
        task_id='check_offsite_backup',
        python_callable=check_offsite_backup,
    )

    t_alert = PythonOperator(
        task_id='send_consolidated_alert',
        python_callable=send_consolidated_alert,
        trigger_rule='all_done',
    )

    [t_creds, t_failures, t_freshness, t_resurrection, t_drift,
     t_billing, t_anomalies, t_readiness, t_central, t_canary,
     t_preflight, t_outcomes, t_contamination, t_dips, t_offsite] >> t_alert
