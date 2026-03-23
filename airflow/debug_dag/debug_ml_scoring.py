"""Debug script pour le DAG ml_scoring_daily.

Exécute le scoring ML localement sans Airflow.
Usage:
    python airflow/debug_dag/debug_ml_scoring.py
    python airflow/debug_dag/debug_ml_scoring.py --artist-id 2
"""
import sys
import os
import argparse
import logging

# Setup path pour imports locaux
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Debug ML scoring')
    parser.add_argument('--artist-id', type=int, default=None,
                        help='ID artiste spécifique (défaut: tous les artistes actifs)')
    args = parser.parse_args()

    from src.utils.config_loader import config_loader
    from src.database.postgres_handler import PostgresHandler
    from src.utils.ml_inference import score_all_songs, MODEL_VERSION, _MLRUNS_DIR

    print("=" * 70)
    print("ML SCORING — DEBUG")
    print("=" * 70)
    print(f"  Répertoire modèles : {os.path.abspath(_MLRUNS_DIR)}")
    print(f"  Model version      : {MODEL_VERSION}")
    print()

    config = config_loader.load()
    db = PostgresHandler(**config['database'])

    try:
        # Sélectionner les artistes
        if args.artist_id:
            artists = [{'id': args.artist_id, 'name': f'Artist {args.artist_id}'}]
        else:
            artists_rows = db.fetch_query(
                "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id"
            )
            artists = [{'id': r[0], 'name': r[1]} for r in artists_rows]

        if not artists:
            print("Aucun artiste actif trouvé.")
            return

        for artist in artists:
            artist_id = artist['id']
            print(f"\n{'─'*60}")
            print(f"Artiste: {artist['name']!r} (id={artist_id})")
            print(f"{'─'*60}")

            rows = score_all_songs(db, artist_id)

            if not rows:
                print("  Aucune chanson active (pas de streams dans les 35 derniers jours)")
                continue

            print(f"\n  {'Chanson':<35} {'DW%':>6} {'RR%':>6} {'Radio%':>7} {'DW7d':>8} {'RR7d':>8}")
            print("  " + "-" * 75)

            for r in rows:
                dw = f"{r['dw_probability']*100:.1f}" if r['dw_probability'] is not None else " N/A"
                rr = f"{r['rr_probability']*100:.1f}" if r['rr_probability'] is not None else " N/A"
                radio = f"{r['radio_probability']*100:.1f}" if r['radio_probability'] is not None else " N/A"
                dw7 = str(r['dw_streams_forecast_7d']) if r['dw_streams_forecast_7d'] is not None else "N/A"
                rr7 = str(r['rr_streams_forecast_7d']) if r['rr_streams_forecast_7d'] is not None else "N/A"
                song_short = r['song'][:34]
                print(f"  {song_short:<35} {dw:>6} {rr:>6} {radio:>7} {dw7:>8} {rr7:>8}")

            print(f"\n  Upsert dans DB ? (dry-run — pas d'écriture en mode debug)")

    finally:
        db.close()

    print("\n" + "=" * 70)
    print("DEBUG ML SCORING TERMINÉ")
    print("=" * 70)


if __name__ == '__main__':
    main()
