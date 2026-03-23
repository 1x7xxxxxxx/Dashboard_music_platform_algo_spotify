"""Monitor de fraîcheur des données — alerte si source inactive."""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Seuils de fraîcheur (en heures)
_DEFAULT_STALE_H = 48
_CSV_STALE_H = 7 * 24  # CSV S4A / Apple Music : watcher peu fréquent

# Sources à monitorer : (label, table, colonne, seuil_h)
MONITOR_TARGETS = [
    {"source": "Spotify S4A",  "table": "s4a_song_timeline",       "col": "collected_at", "stale_h": _CSV_STALE_H},
    {"source": "YouTube",      "table": "youtube_channel_history",  "col": "collected_at", "stale_h": _DEFAULT_STALE_H},
    {"source": "SoundCloud",   "table": "soundcloud_tracks_daily",  "col": "collected_at", "stale_h": _DEFAULT_STALE_H},
    {"source": "Instagram",    "table": "instagram_daily_stats",    "col": "collected_at", "stale_h": _DEFAULT_STALE_H},
    {"source": "Apple Music",  "table": "apple_songs_performance",  "col": "collected_at", "stale_h": _CSV_STALE_H},
    {"source": "Meta Ads",     "table": "meta_insights_performance_day", "col": "collected_at", "stale_h": _DEFAULT_STALE_H},
]


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

        try:
            if artist_id is not None:
                row = db.fetch_query(
                    f"SELECT MAX({t['col']}) FROM {t['table']} WHERE artist_id = %s",
                    (artist_id,)
                )
            else:
                row = db.fetch_query(
                    f"SELECT MAX({t['col']}) FROM {t['table']}"
                )

            val = row[0][0] if row and row[0][0] is not None else None

            # Normaliser en datetime (DATE → datetime)
            if val is not None and not isinstance(val, datetime):
                val = datetime(val.year, val.month, val.day, 0, 0, 0)

            if val is not None:
                age_h = (now - val).total_seconds() / 3600
                stale = age_h > t['stale_h']

        except Exception as e:
            logger.warning(f"Freshness check failed for {t['source']}: {e}")

        results.append({
            "source": t["source"],
            "last_dt": val,
            "age_h": age_h,
            "stale": stale,
            "stale_h": t["stale_h"],
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
