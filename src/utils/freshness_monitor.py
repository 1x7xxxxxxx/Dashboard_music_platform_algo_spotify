"""Monitor de fraîcheur des données — alerte si source inactive."""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Seuils de fraîcheur (en heures)
_DEFAULT_STALE_H = 48
_CSV_STALE_H = 7 * 24  # CSV S4A / Apple Music : watcher peu fréquent

# Sources à monitorer : (label, table, colonne, seuil_h)
# `tenant_table`/`tenant_col`: where to look when the question is asked about ONE
# artist. `artists` is keyed by the SPOTIFY artist id, not the tenant, so a
# per-tenant call used to silently return the whole fleet's freshness — a green
# light for a tenant that had never collected anything.
# `metric_col` — the day the data DESCRIBES, when the table records it separately
# from the day it was written. Measured in production on 2026-08-21:
# `meta_insights_performance_day` had `MAX(collected_at)` = that morning and
# `MAX(day_date)` = **2024-09-30**, with zero rows in the last seven days. The DAG
# was running, re-upserting the same two-year-old rows, and every freshness probe
# read the write timestamp and called it fresh. Meta Ads had been dead since
# early August behind a green light.
#
# Where a table has no separate metric date (a snapshot: followers today, tracks
# today), `collected_at` IS the measurement time and there is nothing to add.
MONITOR_TARGETS = [
    {"source": "Spotify API",  "table": "artists",                  "col": "collected_at", "stale_h": _DEFAULT_STALE_H, "skip_artist_filter": True,
     "tenant_table": "track_popularity_history", "tenant_col": "collected_at",
     "tenant_metric_col": "date"},
    {"source": "Spotify S4A",  "table": "s4a_song_timeline",       "col": "collected_at", "stale_h": _CSV_STALE_H,
     "metric_col": "date"},
    {"source": "YouTube",      "table": "youtube_channel_history",  "col": "collected_at", "stale_h": _DEFAULT_STALE_H},
    {"source": "SoundCloud",   "table": "soundcloud_tracks_daily",  "col": "collected_at", "stale_h": _DEFAULT_STALE_H},
    {"source": "Instagram",    "table": "instagram_daily_stats",    "col": "collected_at", "stale_h": _DEFAULT_STALE_H},
    {"source": "Apple Music",  "table": "apple_songs_performance",  "col": "collected_at", "stale_h": _CSV_STALE_H},
    {"source": "Meta Ads",     "table": "meta_insights_performance_day", "col": "collected_at", "stale_h": _DEFAULT_STALE_H,
     # Ads insights only exist while ads run. Measured 2026-08-21: the admin
     # account holds 19 ARCHIVED + 15 PAUSED campaigns, zero ACTIVE, and the
     # API confirms amount_spent=0 with no insight row in 90 days. Reporting
     # that as "stale" is true and useless — it would fire every night forever
     # for a correct pipeline, which is how a reader learns to skip the alert.
     "silence_expected": "meta_no_active_campaign",
     "metric_col": "day_date"},
]

# Logical platform -> the freshness sources that can PROVE it is collecting.
#
# Spotify carries two, and that is the whole point. `artist_readiness` used to bind
# it to "Spotify S4A" alone -- the CSV upload table. An artist who entered their
# Spotify artist id, passed the connection test (which names the artist back to
# them) and whose `spotify_api_daily` was filling `track_popularity_history` still
# read 🔴 "Connecte -- aucune donnee" until they uploaded a CSV. Spotify is the
# platform onboarding recommends first, so that was most artists' first impression.
#
# Declared HERE, next to MONITOR_TARGETS, because four surfaces judged Spotify on
# four different tables: readiness on `s4a_song_timeline`, the canary watchdog on
# `track_popularity_history`, the KPI panel on `artists`, and this module on both.
# One tenant could be green on one screen and red on another, truthfully.
SOURCES_FOR_PLATFORM = {
    "soundcloud": ("SoundCloud",),
    "spotify": ("Spotify API", "Spotify S4A"),
    "youtube": ("YouTube",),
    "meta": ("Meta Ads",),
    "instagram": ("Instagram",),
}


def sources_for(platform: str) -> tuple:
    """The freshness source labels that can prove `platform` is collecting."""
    return SOURCES_FOR_PLATFORM.get(platform, ())


def tables_for_platform(platform: str) -> frozenset:
    """Tables a PER-TENANT reader may query with `WHERE artist_id = <int>`.

    Returns the `tenant_table` when a target declares one, otherwise the table
    itself. It never returns both, and it never returns a table that is not
    tenant-scopable.

    That distinction is not cosmetic. `MONITOR_TARGETS` lists `artists` for
    "Spotify API" with `skip_artist_filter: True` and a separate
    `tenant_table: track_popularity_history` — because on `artists` the column
    called `artist_id` is the SPOTIFY id (VARCHAR), not the tenant (the tenant
    there is `saas_artist_id`). Handing `artists` to a per-tenant reader produces
    `operator does not exist: character varying = integer`.

    Measured 2026-08-22, in production: an earlier version of this function
    returned both tables, the canary watchdog queried `artists` with an integer,
    and the check reported "could not run" — correctly conservative, and still a
    false CANARI MUET in the subject line. This is the catalogued class
    `column-name-is-not-its-meaning`: reason on the TYPE, never on the name.
    """
    wanted = set(sources_for(platform))
    out = set()
    for t in MONITOR_TARGETS:
        if t["source"] not in wanted:
            continue
        out.add(t.get("tenant_table") or t["table"])
    return frozenset(out)


# Allowlists derived from MONITOR_TARGETS — guards against identifier injection
# if a bad entry is ever introduced into the config list.
_ALLOWED_TABLES = frozenset(
    [t["table"] for t in MONITOR_TARGETS]
    + [t["tenant_table"] for t in MONITOR_TARGETS if t.get("tenant_table")]
)
_ALLOWED_COLS = frozenset(
    [t["col"] for t in MONITOR_TARGETS]
    + [t["tenant_col"] for t in MONITOR_TARGETS if t.get("tenant_col")]
    + [t["metric_col"] for t in MONITOR_TARGETS if t.get("metric_col")]
    + [t["tenant_metric_col"] for t in MONITOR_TARGETS if t.get("tenant_metric_col")]
)


def _silence_reason(db, rule: str, artist_id=None) -> str | None:
    """Return why a source is legitimately silent, or None if its silence is a fault.

    Deliberately conservative: any doubt — an unknown rule, a failed query, no
    campaign row at all — returns None, i.e. keeps the alert. Suppressing an alert
    on a guess is strictly worse than one noisy line, because it removes the only
    signal that a real outage would produce.
    """
    if rule != "meta_no_active_campaign":
        return None
    try:
        sql = ("SELECT count(*) FILTER (WHERE status = 'ACTIVE'), count(*) "
               "FROM meta_campaigns")
        params = ()
        if artist_id is not None:
            sql += " WHERE artist_id = %s"
            params = (artist_id,)
        active, total = db.fetch_query(sql, params)[0]
    except Exception as e:  # noqa: BLE001 — a failed probe must not silence anything
        logger.warning("silence probe failed (%s); keeping the alert: %s", rule, e)
        return None
    if not total:
        return None          # nothing known about campaigns → do not suppress
    if active:
        return None          # ads ARE running, so silence is a real problem
    return (f"no ACTIVE campaign ({total} known, none running) — Meta Ads insights "
            "only exist while ads run, so this silence is expected")


def check_freshness(db, artist_id=None):
    """
    Vérifie la fraîcheur de chaque source.
    Retourne une liste de dicts :
        {source, measured_on, expected_silence, last_dt, age_h, stale, stale_h, error}

    `stale` alone answers "should this fire?"; it does NOT answer "is this healthy?".
    A reader that renders `not stale` as OK will call an expected silence green —
    see `expected_silence`, which every display surface is expected to honour.
    """
    results = []
    now = datetime.now()

    for t in MONITOR_TARGETS:
        val = None
        age_h = None
        stale = True
        error = None
        expected_silence = None

        try:
            table, col = t["table"], t["col"]
            # A per-tenant question asked of a table that has no tenant column is
            # answered from the tenant-scoped equivalent, not from the whole fleet.
            metric_col = t.get("metric_col")
            if artist_id is not None and t.get("tenant_table"):
                table, col = t["tenant_table"], t.get("tenant_col", col)
                metric_col = t.get("tenant_metric_col")
            # The day the data describes beats the day it was written: a collector
            # that re-upserts old rows keeps the write time moving forever.
            if metric_col:
                col = metric_col
            scoped = artist_id is not None and not (
                t.get("skip_artist_filter") and not t.get("tenant_table"))

            if table not in _ALLOWED_TABLES or col not in _ALLOWED_COLS:
                raise ValueError(f"Identifier not in allowlist: {table}.{col}")
            if scoped:
                row = db.fetch_query(
                    f"SELECT MAX({col}) FROM {table} WHERE artist_id = %s",
                    (artist_id,)
                )
            else:
                row = db.fetch_query(
                    f"SELECT MAX({col}) FROM {table}"
                )

            val = row[0][0] if row and row[0][0] is not None else None

            # Normaliser en datetime (DATE → datetime)
            if val is not None and not isinstance(val, datetime):
                val = datetime(val.year, val.month, val.day, 0, 0, 0)

            if val is not None:
                age_h = (now - val).total_seconds() / 3600
                stale = age_h > t['stale_h']

            # "Nothing arrived" and "nothing was supposed to arrive" are different
            # statements, and only the first is a problem. Keeping them apart is
            # what stops a correct pipeline from alerting nightly forever.
            if stale and t.get("silence_expected"):
                reason = _silence_reason(db, t["silence_expected"], artist_id)
                if reason:
                    stale = False
                    expected_silence = reason

        except Exception as e:
            # `stale=True` alone made a BROKEN check look exactly like "connected
            # but no data" — a missing table, a bad identifier or a dead connection
            # all rendered as 🔴 "aucune donnée". `error` keeps the two apart so a
            # pre-flight can say "the check failed" instead of blaming the artist.
            error = str(e)
            logger.warning(f"Freshness check failed for {t['source']}: {e}")

        results.append({
            "source": t["source"],
            # Which column answered — a reader needs to know whether "fresh" means
            # "written recently" or "describes a recent day". They are not the same
            # claim, and conflating them is what hid Meta Ads for weeks.
            "measured_on": "metric" if t.get("metric_col") or t.get("tenant_metric_col") else "write",
            # Set when the source is old AND that is the correct state. A reader must
            # be able to tell "no data because broken" from "no data because there is
            # none to collect" — the second is not an incident.
            "expected_silence": expected_silence,
            "last_dt": val,
            "age_h": age_h,
            "stale": stale,
            "stale_h": t["stale_h"],
            "error": error,
        })

    return results


# `run_freshness_alerts()` lived here until 2026-08-22. Removed, not wired.
#
# It had ZERO callers anywhere in the repo, and it sent its OWN email with its own
# subject. The freshness alerting that actually reaches you is the one in
# `alert_monitor.check_data_freshness`, folded into the single consolidated digest.
# Connecting this one would have produced a second email for the same fact — the
# catalogued `watchdog-becomes-the-noise`, where the fix makes the alert less read,
# not more.
#
# It also carried a defect the rest of the module no longer has: it filtered on
# `r['stale']` alone and never looked at `error`, so a probe that FAILED would have
# been reported as a stale source — `broken-probe-rendered-as-user-fault`. Dead code
# does not just sit there; it preserves the bugs the live path has already fixed,
# and it reads as a feature to whoever finds it next.
