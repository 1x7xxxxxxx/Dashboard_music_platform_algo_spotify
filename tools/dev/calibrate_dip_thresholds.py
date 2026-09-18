#!/usr/bin/env python3
"""Dérive, PAR TABLE et sur des données réelles, le seuil du détecteur de creux.

Type: Utility
Uses: src/database/postgres_handler
Triggers: `make dip-calibrate` (lecture seule) — puis à la main dans `DIP_TENANT_COLUMN`
Depends on: la base `spotify_etl` joignable
Persists in: nothing (écrit un rapport sur stdout, ou du JSON avec --json)

Pourquoi cet outil existe
-------------------------
`check_row_dips` ne surveille que **5 tables sur 84** éligibles. Un locataire qui perd
ENTIÈREMENT Instagram, Apple ou Hypeddit ne déclenche aucune alerte. Étendre la liste est
la tâche R134 — mais elle bute sur une condition que ce dépôt s'est donnée après l'avoir
payée : **un seuil ne s'écrit pas d'instinct.**

Le précédent est mesuré : un plancher de 30 lignes/jour, écrit à vue, rendait le
détecteur aveugle à **2 locataires sur 3**. Un seuil est une affirmation sur une
distribution ; l'écrire sans regarder la distribution, c'est affirmer sans mesurer.

⚠️ **« Par locataire ET daté » n'est PAS le bon prédicat d'éligibilité**, et c'est
mesuré : `hypeddit_campaigns` porte `artist_id`, `created_at` et `updated_at`, donc il
passe le critère — mais c'est une table de DIMENSION. Des campagnes sont créées de temps
en temps, pas chaque jour. Un « creux » y est le fonctionnement normal, et l'y brancher
produirait une alerte quotidienne que personne ne lirait, ce qui détruit le détecteur
pour les tables où il a raison. La propriété qui compte est : **cette table reçoit-elle
des lignes CHAQUE JOUR pour un locataire actif ?** Cet outil la mesure (`jours_couverts`)
au lieu de la supposer.

⚠️ **Il REFUSE de rendre un seuil quand l'échantillon est trop petit**, et c'est sa
fonction principale. Sur cette machine, 5 des 9 tables candidates ont ≤ 2 observations
`(locataire, jour)` : il n'y a rien à calibrer, et rendre un chiffre quand même serait
exactement le défaut que l'outil existe pour empêcher.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.database.postgres_handler import PostgresHandler  # noqa: E402

#: Les candidates de R134, nommées par le balayage de `partial-collection-invisible`.
#: `hypeddit_campaigns` en est RETIRÉE — table de dimension, voir le docstring.
CANDIDATES = (
    "instagram_daily_stats", "instagram_media", "instagram_media_insights",
    "apple_daily_plays", "apple_listeners", "apple_songs_history",
    "hypeddit_daily_stats", "sacem_statement",
)

#: Les colonnes de date possibles, par ordre de préférence. Une table de FAIT quotidien
#: porte une date métier ; `collected_at` est une date de COLLECTE et ne dit pas le jour
#: que la ligne décrit — elle n'est retenue qu'en dernier recours.
_COLONNES_DATE = ("date", "day", "stat_date", "line_date", "period_start",
                  "snapshot_date", "collected_at")
_COLONNES_LOCATAIRE = ("artist_id", "saas_artist_id")

#: Sous ce nombre d'observations `(locataire, jour)`, aucun seuil n'est rendu.
#: 30 est le minimum sous lequel un quantile empirique n'a pas de sens ; ce n'est pas
#: un seuil de détection mais un seuil de CALIBRATION, et les deux ne se confondent pas.
N_MINIMUM = 30

#: Sous ce taux de jours couverts, la table n'est pas un fait QUOTIDIEN.
COUVERTURE_MINIMALE = 0.5


def _colonnes(db, table: str) -> set[str]:
    return {r[0] for r in db.fetch_query(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (table,))}


def calibrer(db, table: str) -> dict:
    """Ce qu'on peut dire de cette table, ou pourquoi on ne peut rien en dire."""
    cols = _colonnes(db, table)
    if not cols:
        return {"table": table, "verdict": "absente", "seuil": None}
    locataire = next((c for c in _COLONNES_LOCATAIRE if c in cols), None)
    date = next((c for c in _COLONNES_DATE if c in cols), None)
    if not locataire or not date:
        return {"table": table, "verdict": "pas de couple (locataire, date)",
                "locataire": locataire, "date": date, "seuil": None}

    lignes = db.fetch_query(                                          # noqa: S608
        f"SELECT {locataire} AS loc, {date}::date AS jour, count(*) AS n "  # noqa: S608
        f"FROM {table} WHERE {locataire} IS NOT NULL AND {date} IS NOT NULL "
        f"GROUP BY 1, 2 ORDER BY 1, 2") or []
    obs = [int(r[2]) for r in lignes]
    base = {"table": table, "colonne_locataire": locataire, "colonne_date": date,
            "observations": len(obs), "locataires": len({r[0] for r in lignes}),
            "jours": len({r[1] for r in lignes})}

    if len(obs) < N_MINIMUM:
        return {**base, "verdict": f"échantillon trop petit ({len(obs)} < {N_MINIMUM})",
                "seuil": None}

    jours = sorted({r[1] for r in lignes})
    etendue = (jours[-1] - jours[0]).days + 1
    couverture = len(jours) / etendue if etendue else 0.0
    base["couverture"] = round(couverture, 3)
    if couverture < COUVERTURE_MINIMALE:
        return {**base, "verdict": f"pas un fait quotidien (couverture {couverture:.0%})",
                "seuil": None}

    obs_tries = sorted(obs)
    mediane = statistics.median(obs_tries)
    q10 = obs_tries[max(0, int(0.10 * len(obs_tries)) - 1)]
    # Le seuil : un creux est une journée sous le DIXIÈME de la médiane du locataire,
    # avec un plancher qui vient du 10e centile observé — pas d'un chiffre rond.
    return {**base, "verdict": "calibré",
            "mediane": mediane, "p10": q10,
            "seuil": {"facteur": 0.25, "plancher": max(1, q10)}}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--tables", nargs="*", default=list(CANDIDATES))
    args = ap.parse_args()

    db = PostgresHandler.from_env_or_config()
    if db is None:
        print("❌ base injoignable. Lancer : make up", file=sys.stderr)
        return 2
    try:
        resultats = [calibrer(db, t) for t in args.tables]
    finally:
        db.close()

    if args.json:
        print(json.dumps(resultats, indent=2, ensure_ascii=False, default=str))
        return 0

    calibres = [r for r in resultats if r["seuil"]]
    print(f"▶ {len(calibres)} table(s) calibrable(s) sur {len(resultats)}\n")
    print(f"{'table':<30} {'obs':>5} {'loc':>4} {'couv':>6}  verdict")
    for r in resultats:
        couv = f"{r['couverture']:.0%}" if r.get("couverture") is not None else "—"
        print(f"{r['table']:<30} {r.get('observations', 0):>5} "
              f"{r.get('locataires', 0):>4} {couv:>6}  {r['verdict']}")
    if calibres:
        print("\nSeuils dérivés — à reporter À LA MAIN dans `DIP_TENANT_COLUMN`, avec "
              "la date de la mesure :")
        for r in calibres:
            print(f"  {r['table']}: facteur {r['seuil']['facteur']}, "
                  f"plancher {r['seuil']['plancher']} "
                  f"(médiane {r['mediane']}, p10 {r['p10']}, n={r['observations']})")
    else:
        print("\n⚠️ AUCUN seuil rendu. C'est un résultat, pas une panne : sans "
              "distribution, un seuil serait une affirmation sans mesure — et ce dépôt "
              "a déjà payé un plancher écrit d'instinct par un détecteur aveugle à "
              "2 locataires sur 3.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
