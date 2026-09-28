"""Debug script pour le DAG ml_outcome_labeling.

Exécute la labellisation des outcomes localement sans Airflow.
Usage:
    python airflow/debug_dag/debug_ml_outcome_labeling.py
    python airflow/debug_dag/debug_ml_outcome_labeling.py --artist-id 2
    python airflow/debug_dag/debug_ml_outcome_labeling.py --write   # upsert réel
"""
import argparse
import logging
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s — %(message)s')
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Debug ML outcome labelling')
    parser.add_argument('--artist-id', type=int, default=None,
                        help='ID artiste spécifique (défaut: tous les artistes actifs)')
    parser.add_argument('--write', action='store_true',
                        help='Écrit réellement dans ml_prediction_outcomes (sinon dry-run)')
    args = parser.parse_args()

    from src.database.postgres_handler import PostgresHandler
    from src.utils.config_loader import config_loader
    from src.utils.ml_outcome_labeling import _outcomes_by_song, label_predictions, match_outcome

    print("=" * 70)
    print("ML OUTCOME LABELLING — DEBUG", "(WRITE)" if args.write else "(dry-run)")
    print("=" * 70)

    db = PostgresHandler(**config_loader.load()['database'])
    try:
        if args.artist_id:
            artists = [(args.artist_id, f'Artist {args.artist_id}')]
        else:
            rows = db.fetch_query("SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id")
            artists = [(r[0], r[1]) for r in rows]
        if not artists:
            print("Aucun artiste actif trouvé.")
            return

        for artist_id, name in artists:
            print(f"\n{'─'*60}\nArtiste: {name!r} (id={artist_id})\n{'─'*60}")

            preds = db.fetch_df(
                """SELECT p.id, p.song, p.prediction_date, p.model_version
                   FROM ml_song_predictions p
                   LEFT JOIN ml_prediction_outcomes o ON o.prediction_id = p.id
                   WHERE p.artist_id = %s AND o.id IS NULL
                     AND p.prediction_date <= CURRENT_DATE - 28
                     AND p.song NOT ILIKE %s
                   ORDER BY p.prediction_date""",
                (artist_id, "%1x7xxxxxxx%"))
            n_preds = 0 if preds is None or preds.empty else len(preds)
            by_song = _outcomes_by_song(db, artist_id)
            print(f"  Prédictions non-labellisées & ≥28j : {n_preds}")
            print(f"  Titres avec outcomes saisis        : {len(by_song)}")

            matchable = 0
            if n_preds:
                for p in preds.to_dict("records"):
                    if match_outcome(p["prediction_date"], by_song.get(p["song"], []), 28):
                        matchable += 1
            print(f"  Prédictions labellisables (match)  : {matchable}")

            if args.write:
                written = label_predictions(db, artist_id)
                print(f"  ✅ {written} label(s) écrit(s) dans ml_prediction_outcomes")
            else:
                print("  (dry-run — relance avec --write pour persister)")
    finally:
        db.close()

    print("\n" + "=" * 70)
    print("DEBUG TERMINÉ")
    print("=" * 70)


if __name__ == '__main__':
    main()
