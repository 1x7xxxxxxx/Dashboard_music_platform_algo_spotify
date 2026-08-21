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
MONITOR_TARGETS = [
    {"source": "Spotify API",  "table": "artists",                  "col": "collected_at", "stale_h": _DEFAULT_STALE_H, "skip_artist_filter": True,
     "tenant_table": "track_popularity_history", "tenant_col": "collected_at"},
    {"source": "Spotify S4A",  "table": "s4a_song_timeline",       "col": "collected_at", "stale_h": _CSV_STALE_H},
    {"source": "YouTube",      "table": "youtube_channel_history",  "col": "collected_at", "stale_h": _DEFAULT_STALE_H},
    {"source": "SoundCloud",   "table": "soundcloud_tracks_daily",  "col": "collected_at", "stale_h": _DEFAULT_STALE_H},
    {"source": "Instagram",    "table": "instagram_daily_stats",    "col": "collected_at", "stale_h": _DEFAULT_STALE_H},
    {"source": "Apple Music",  "table": "apple_songs_performance",  "col": "collected_at", "stale_h": _CSV_STALE_H},
    {"source": "Meta Ads",     "table": "meta_insights_performance_day", "col": "collected_at", "stale_h": _DEFAULT_STALE_H},
]

# Allowlists derived from MONITOR_TARGETS — guards against identifier injection
# if a bad entry is ever introduced into the config list.
_ALLOWED_TABLES = frozenset(
    [t["table"] for t in MONITOR_TARGETS]
    + [t["tenant_table"] for t in MONITOR_TARGETS if t.get("tenant_table")]
)
_ALLOWED_COLS = frozenset(
    [t["col"] for t in MONITOR_TARGETS]
    + [t["tenant_col"] for t in MONITOR_TARGETS if t.get("tenant_col")]
)


def check_freshness(db, artist_id=None):
    """
    Vérifie la fraîcheur de chaque source.
    Retourne une liste de dicts :
        {source, last_dt, age_h, stale, stale_h}
    """
    results = []
    now = datetime.now()

    for t in MONITOR_TARGETS:
        val = None
        age_h = None
        stale = True
        error = None

        try:
            table, col = t["table"], t["col"]
            # A per-tenant question asked of a table that has no tenant column is
            # answered from the tenant-scoped equivalent, not from the whole fleet.
            if artist_id is not None and t.get("tenant_table"):
                table, col = t["tenant_table"], t.get("tenant_col", col)
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

        except Exception as e:
            # `stale=True` alone made a BROKEN check look exactly like "connected
            # but no data" — a missing table, a bad identifier or a dead connection
            # all rendered as 🔴 "aucune donnée". `error` keeps the two apart so a
            # pre-flight can say "the check failed" instead of blaming the artist.
            error = str(e)
            logger.warning(f"Freshness check failed for {t['source']}: {e}")

        results.append({
            "source": t["source"],
            "last_dt": val,
            "age_h": age_h,
            "stale": stale,
            "stale_h": t["stale_h"],
            "error": error,
        })

    return results


def run_freshness_alerts(db, artist_id=None):
    """
    Vérifie toutes les sources et envoie une alerte email groupée pour les sources stale.
    Retourne la liste complète des résultats (stale ou non).
    """
    from src.utils.email_alerts import EmailAlert

    results = check_freshness(db, artist_id)
    stale = [r for r in results if r['stale']]

    if stale:
        lines = ""
        for r in stale:
            age_str = f"{r['age_h']:.0f}h" if r['age_h'] is not None else "jamais collectée"
            lines += (
                f"<li><b>{r['source']}</b> — dernière collecte il y a {age_str} "
                f"(seuil : {r['stale_h']}h)</li>\n"
            )
        subject = f"{len(stale)} source(s) stale — Dashboard Music"
        body = f"""
        <h3>⚠️ Sources de données inactives</h3>
        <ul>{lines}</ul>
        <p>Vérifiez les DAGs Airflow et relancez si nécessaire.</p>
        <p style="color:#888;font-size:0.85em;">Généré automatiquement par freshness_monitor.</p>
        """
        EmailAlert().send_alert(subject, body)
        logger.warning(
            f"⚠️ {len(stale)} source(s) stale : {[r['source'] for r in stale]}"
        )
    else:
        logger.info("✅ Toutes les sources sont fraîches.")

    return results
