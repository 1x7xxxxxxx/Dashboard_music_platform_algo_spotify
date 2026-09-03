"""DAG weekly_digest — sends a KPI summary email every Monday at 08:00 UTC.

One email per active artist. Covers:
  - S4A streams delta (last 7 days vs previous 7 days)
  - Top song of the week
  - Meta Ads spend + CTR (last 7 days)
  - Instagram followers delta
  - SoundCloud plays delta
  - ML top prediction (highest dw_probability)
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from html import escape
import sys
import os
import logging

sys.path.insert(0, '/opt/airflow')

# Redact credentials out of any exception this module logs: an HTTP
# exception message embeds the prepared URL, and several upstream APIs take
# their credential as a QUERY PARAMETER. stdlib-only, safe at DAG parse time.
from src.utils.safe_error import safe_error
from src.utils.dag_timeouts import dagrun_timeout_for
from src.utils.digest_queries import SOUNDCLOUD_WEEKLY_DELTA_SQL

logger = logging.getLogger(__name__)


def _on_failure_callback(context):
    try:
        from src.utils.email_alerts import dag_failure_callback
        dag_failure_callback(context)
    except Exception as e:
        logger.error(f"Failure callback error: {safe_error(e)}")


default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'on_failure_callback': _on_failure_callback,
}


def _digest_recipients(db, artist_id: int) -> list[tuple[int, str]]:
    """`(user_id, email)` for everyone entitled to this tenant's recap.

    ALL eligible users, not one canonical: `saas_users.artist_id` carries no UNIQUE
    constraint, so a tenant may have several accounts. Picking one would need an
    arbitrary tie-break (`min(id)`?) that silently drops a co-manager.

    Query shape mirrors `onboarding_report.py:100-111`, the existing precedent for
    per-user eligibility. `weekly_digest_optout_at IS NULL` and not
    `marketing_consent`: a recap of the customer's own numbers, for a feature they
    pay for, is a service e-mail — see migration 081 for the full argument.
    """
    rows = db.fetch_query(
        """
        SELECT id, email
        FROM saas_users
        WHERE artist_id = %s
          AND active
          AND email_verified
          AND role = 'artist'
          AND weekly_digest_optout_at IS NULL
        ORDER BY id
        """,
        (artist_id,),
    )
    return [(r[0], r[1]) for r in (rows or [])]


def _unsubscribe_footer(user_id: int, lang: str = 'fr', scope: str = 'digest') -> str:
    """The existing HMAC unsubscribe mechanism, scoped to this feature.

    Built in `src/utils/verification_email.py` since 2026-06 and used by exactly one
    caller (`onboarding_report`) until now. Imported rather than reimplemented: a
    second token scheme would be a second thing to get wrong.
    """
    from src.utils.verification_email import _unsubscribe_footer as footer
    return footer(user_id, lang=lang, scope=scope)


def send_weekly_digest(**context):
    """Build and send one digest email per active artist."""
    from src.database.postgres_handler import PostgresHandler
    from src.utils.credential_loader import get_active_artists
    from src.utils.email_alerts import EmailAlert

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD'),
    )

    artists = get_active_artists()
    if not artists:
        logger.warning("No active artists — skipping digest")
        db.close()
        return

    email_client = EmailAlert()
    sent = 0
    undelivered: list[str] = []

    for artist_id, artist_name in artists:
        try:
            logger.info(f"Building digest for {artist_name} (id={artist_id})")

            # ── S4A streams: last 7d vs previous 7d ──────────────────────────
            streams_rows = db.fetch_query(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN date >= CURRENT_DATE - 7 THEN streams END), 0) AS last_7d,
                    COALESCE(SUM(CASE WHEN date >= CURRENT_DATE - 14 AND date < CURRENT_DATE - 7 THEN streams END), 0) AS prev_7d
                FROM (
                    SELECT DISTINCT ON (date, song) date, streams
                    FROM s4a_song_timeline
                    WHERE artist_id = %s
                      AND song NOT ILIKE '%%1x7xxxxxxx%%'
                      AND date >= CURRENT_DATE - 14
                    ORDER BY date, song, collected_at DESC
                ) sub
                """,
                (artist_id,)
            )
            last_7d = int(streams_rows[0][0]) if streams_rows else 0
            prev_7d = int(streams_rows[0][1]) if streams_rows else 0
            streams_delta = last_7d - prev_7d
            streams_delta_pct = round((streams_delta / prev_7d * 100), 1) if prev_7d > 0 else None

            # ── Top song this week ────────────────────────────────────────────
            top_song_rows = db.fetch_query(
                """
                SELECT song, SUM(streams) AS total
                FROM (
                    SELECT DISTINCT ON (date, song) date, song, streams
                    FROM s4a_song_timeline
                    WHERE artist_id = %s
                      AND song NOT ILIKE '%%1x7xxxxxxx%%'
                      AND date >= CURRENT_DATE - 7
                    ORDER BY date, song, collected_at DESC
                ) sub
                GROUP BY song
                ORDER BY total DESC
                LIMIT 1
                """,
                (artist_id,)
            )
            # escape(): a song title comes from a CSV the tenant uploaded, and it
            # is interpolated into an HTML email body below. `<img onerror=…>` in a
            # track name is a stored payload that renders in the recipient's mail
            # client — and the recipient is the artist, not the author.
            top_song = escape(str(top_song_rows[0][0])) if top_song_rows else "—"
            top_song_streams = int(top_song_rows[0][1]) if top_song_rows else 0

            # ── Meta Ads spend + CTR ──────────────────────────────────────────
            meta_rows = db.fetch_query(
                """
                SELECT
                    COALESCE(SUM(spend), 0),
                    CASE WHEN SUM(impressions) > 0
                         THEN ROUND((SUM(link_clicks)::numeric / SUM(impressions)::numeric) * 100, 2)
                         ELSE 0 END
                FROM meta_insights_performance
                WHERE artist_id = %s
                  AND date_start >= CURRENT_DATE - 7
                """,
                (artist_id,)
            )
            meta_spend = float(meta_rows[0][0]) if meta_rows else 0.0
            meta_ctr = float(meta_rows[0][1]) if meta_rows else 0.0

            # ── Instagram followers delta ─────────────────────────────────────
            ig_rows = db.fetch_query(
                """
                SELECT
                    (SELECT followers_count FROM instagram_daily_stats
                     WHERE artist_id = %s ORDER BY collected_at DESC LIMIT 1) AS latest,
                    (SELECT followers_count FROM instagram_daily_stats
                     WHERE artist_id = %s AND collected_at::date <= CURRENT_DATE - 7
                     ORDER BY collected_at DESC LIMIT 1) AS week_ago
                """,
                (artist_id, artist_id)
            )
            ig_latest = ig_rows[0][0] if ig_rows and ig_rows[0][0] else None
            ig_week_ago = ig_rows[0][1] if ig_rows and ig_rows[0][1] else None
            ig_delta = (ig_latest - ig_week_ago) if (ig_latest and ig_week_ago) else None

            # ── SoundCloud plays delta ────────────────────────────────────────
            # A snapshot is keyed by the DAY, never by `collected_at` itself: the
            # collector stamps every row of one batch with its own microsecond
            # (measured in prod 2026-08-31 — 19 tracks, 19 distinct timestamps in
            # the same run). `collected_at = MAX(collected_at)` therefore summed a
            # SINGLE track and mailed the artist a -21,324 collapse that never
            # happened (2,229 reported against a real 23,557). The table already
            # declares the grain: UNIQUE (artist_id, track_id, (collected_at::date)).
            # DISTINCT ON keeps that true even if a day ever gets two runs.
            # No COALESCE: an absent snapshot must read "N/A", not a fabricated 0.
            sc_rows = db.fetch_query(
                SOUNDCLOUD_WEEKLY_DELTA_SQL,
                (artist_id, artist_id, artist_id, artist_id)
            )
            sc_latest = int(sc_rows[0][0]) if (sc_rows and sc_rows[0][0] is not None) else None
            sc_week_ago = int(sc_rows[0][1]) if (sc_rows and sc_rows[0][1] is not None) else None
            sc_delta = (sc_latest - sc_week_ago) if (sc_latest is not None and sc_week_ago is not None) else None

            # ── ML top prediction ─────────────────────────────────────────────
            ml_rows = db.fetch_query(
                """
                SELECT song, dw_probability, rr_probability
                FROM ml_song_predictions
                WHERE artist_id = %s
                  AND prediction_date = (SELECT MAX(prediction_date) FROM ml_song_predictions WHERE artist_id = %s)
                ORDER BY dw_probability DESC NULLS LAST
                LIMIT 1
                """,
                (artist_id, artist_id)
            )
            ml_song = escape(str(ml_rows[0][0])) if ml_rows else None
            ml_dw = round(float(ml_rows[0][1]) * 100, 1) if (ml_rows and ml_rows[0][1]) else None

            # ── Build HTML email ──────────────────────────────────────────────
            def _fmt_delta(val, suffix=""):
                if val is None:
                    return "<span style='color:#888'>N/A</span>"
                color = "#27ae60" if val >= 0 else "#e74c3c"
                sign = "+" if val >= 0 else ""
                return f"<span style='color:{color}'>{sign}{val:,}{suffix}</span>"

            streams_delta_str = _fmt_delta(streams_delta)
            streams_pct_str = f" ({_fmt_delta(streams_delta_pct, '%')})" if streams_delta_pct is not None else ""
            ig_delta_str = _fmt_delta(ig_delta)
            sc_delta_str = _fmt_delta(sc_delta)

            run_date = datetime.now().strftime("%Y-%m-%d")

            html = f"""
            <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#222;">
            <h2 style="color:#1DB954;border-bottom:2px solid #1DB954;padding-bottom:8px;">
                Weekly KPI Digest — {artist_name}
            </h2>
            <p style="color:#888;margin-top:0;">Week ending {run_date}</p>

            <h3 style="margin-bottom:4px;">🎵 Spotify for Artists</h3>
            <table style="width:100%;border-collapse:collapse;">
              <tr style="background:#f5f5f5;">
                <td style="padding:8px;">Streams (last 7 days)</td>
                <td style="padding:8px;text-align:right;font-weight:bold;">{last_7d:,}</td>
                <td style="padding:8px;text-align:right;">{streams_delta_str}{streams_pct_str} vs prev week</td>
              </tr>
              <tr>
                <td style="padding:8px;">Top song</td>
                <td style="padding:8px;" colspan="2"><b>{top_song}</b> — {top_song_streams:,} streams</td>
              </tr>
            </table>

            <h3 style="margin-bottom:4px;margin-top:20px;">📱 Meta Ads (last 7 days)</h3>
            <table style="width:100%;border-collapse:collapse;">
              <tr style="background:#f5f5f5;">
                <td style="padding:8px;">Spend</td>
                <td style="padding:8px;text-align:right;font-weight:bold;">{meta_spend:.2f} €</td>
              </tr>
              <tr>
                <td style="padding:8px;">CTR</td>
                <td style="padding:8px;text-align:right;">{meta_ctr:.2f}%</td>
              </tr>
            </table>

            <h3 style="margin-bottom:4px;margin-top:20px;">📸 Instagram</h3>
            <table style="width:100%;border-collapse:collapse;">
              <tr style="background:#f5f5f5;">
                <td style="padding:8px;">Followers delta (7d)</td>
                <td style="padding:8px;text-align:right;">{ig_delta_str}</td>
                <td style="padding:8px;text-align:right;color:#888;">{f"{ig_latest:,}" if ig_latest else "N/A"} total</td>
              </tr>
            </table>

            <h3 style="margin-bottom:4px;margin-top:20px;">☁️ SoundCloud</h3>
            <table style="width:100%;border-collapse:collapse;">
              <tr style="background:#f5f5f5;">
                <td style="padding:8px;">Plays delta (7d)</td>
                <td style="padding:8px;text-align:right;">{sc_delta_str}</td>
                <td style="padding:8px;text-align:right;color:#888;">{f"{sc_latest:,}" if sc_latest is not None else "N/A"} total</td>
              </tr>
            </table>

            {"" if not ml_song else f'''
            <h3 style="margin-bottom:4px;margin-top:20px;">🤖 ML Prediction</h3>
            <table style="width:100%;border-collapse:collapse;">
              <tr style="background:#f5f5f5;">
                <td style="padding:8px;">Top Discovery Weekly candidate</td>
                <td style="padding:8px;" colspan="2"><b>{ml_song}</b> — {f"{ml_dw}% probability" if ml_dw else "N/A"}</td>
              </tr>
            </table>
            '''}

            <p style="color:#aaa;font-size:0.8em;margin-top:32px;border-top:1px solid #eee;padding-top:8px;">
                Generated automatically by Music Platform Dashboard · {run_date}
            </p>
            </body></html>
            """

            # Premium only. Measured 2026-08-31: this loop sent one message PER
            # TENANT and every one of them to `ALERT_EMAIL` — the subject
            # `[Benken] Weekly KPI` NAMED the tenant without addressing them, and
            # the run logged `7/7 emails sent`, all seven in the operator's inbox.
            from src.utils.plan_resolver import has_capability
            if not has_capability(db, artist_id, 'weekly_digest'):
                logger.info(f"  {artist_name}: free plan — no digest")
                continue

            recipients = _digest_recipients(db, artist_id)
            if not recipients:
                # Not an error: a premium tenant may have no verified address yet, or
                # have opted out. Named so the operator can tell it apart from a send
                # that failed.
                logger.info(f"  {artist_name}: premium, but no enrolled recipient")
                continue

            subject = f"[{artist_name}] Weekly KPI — {run_date}"
            delivered = 0
            for user_id, email in recipients:
                body = html + _unsubscribe_footer(user_id, lang='fr', scope='digest')
                if email_client.send_email(email, subject, body):
                    delivered += 1
                else:
                    logger.warning(f"  {artist_name}: send failed for user {user_id}")
            if delivered:
                sent += 1
                logger.info(f"  Digest sent for {artist_name} ({delivered} recipient(s))")
            else:
                # A PAID feature that silently did not ship is an incident, not a
                # statistic. Collected and raised at the end so one tenant's failure
                # still does not stop the others.
                undelivered.append(artist_name)
                logger.error(f"  {artist_name}: premium, {len(recipients)} recipient(s), "
                             f"0 delivered")

        except Exception as e:
            # Per-artist isolation: one tenant's bad data must not block every other
            # artist's digest. Log + continue; the loop sends what it can.
            logger.error(f"Weekly digest failed for {artist_name} (id={artist_id}): {safe_error(e)}")
            continue
    db.close()
    logger.info(f"Weekly digest done — {sent}/{len(artists)} tenant(s) reached")
    if undelivered:
        raise RuntimeError(
            "Weekly digest: paid feature not delivered for "
            f"{len(undelivered)} premium tenant(s) — {', '.join(undelivered)}. "
            "Check SMTP credentials and STREAMLYTICS_ALLOW_ARTIST_EMAIL on the "
            "scheduler. Every other tenant was served."
        )
    return {'artists': len(artists), 'emails_sent': sent}


with DAG(
    'weekly_digest',
    default_args=default_args,
    description='Weekly KPI digest email per active artist',
    schedule='0 8 * * 1',  # Every Monday at 08:00 UTC
    start_date=datetime(2025, 1, 1),
    catchup=False,
    dagrun_timeout=dagrun_timeout_for('weekly_digest'),
    max_active_runs=1,  # avoid concurrent runs sending duplicate digest emails
    tags=['email', 'digest', 'monitoring'],
) as dag:

    send_task = PythonOperator(
        task_id='send_weekly_digest',
        python_callable=send_weekly_digest,
    )
