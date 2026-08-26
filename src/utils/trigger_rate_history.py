"""Le taux de trigger d'UN titre, au début et aujourd'hui.

Type: Utility
Uses: statistics (stdlib) — reçoit un handle de base, n'en ouvre jamais
Triggers: pdf_exporter (_collectors), trigger_algo
Depends on: ml_song_predictions
Persists in: rien

R55, tranché le 2026-08-26 par l'auteur du produit, et la définition compte parce que
trois lectures étaient possibles : **le taux de trigger est le pourcentage de chance
d'intégrer L'ALGORITHME en question, et il porte sur UN SEUL titre.** Ce n'est donc
pas une part de catalogue ni une moyenne de portefeuille — c'est la sortie calibrée du
modèle pour ce titre-là, sur cette porte-là, à une date.

La section demandée compare la même grandeur à deux moments : les **30 premiers jours**
après la sortie, et **maintenant**. `ml_song_predictions` porte exactement ça —
`(artist_id, song, prediction_date, days_since_release, model_version)` et les trois
probabilités.

Trois pièges, tous capables de produire une phrase fausse et lisible :

1. **Comparer deux versions de modèle, c'est changer de règle en cours de mesure.**
   Une probabilité v1 et une probabilité v3 ne sont pas la même grandeur : la v3 a été
   reconstruite en group-CV avec une calibration OOF (`models/v3`, 2026-06-05). Un
   écart entre les deux dates serait alors en partie le MODÈLE qui a bougé, pas le
   titre. On le dit au lieu de le taire — `comparable` est faux et porte sa raison.
2. **Une absence n'est pas un zéro.** Un titre sorti avant la mise en service du
   scoring n'a aucune ligne dans sa fenêtre initiale. Rendre « 0 % » y serait l'inverse
   de « on ne sait pas » — le défaut exact corrigé le 2026-08-24 sur le graphique des
   portes (`pdf_charts.pi_gate`, panier n=0 dessiné à hauteur zéro).
3. **Un seul jour est bruité.** La fenêtre initiale prend la MÉDIANE de ses points, et
   l'effectif voyage avec la valeur — une barre reste une barre quel que soit ce qui la
   porte, l'autre leçon du même graphique.
"""
from __future__ import annotations

import logging
from statistics import median

logger = logging.getLogger(__name__)

# Les trois portes, dans l'ordre où le PDF les présente déjà.
GATES = (
    ("dw_probability", "Discover Weekly"),
    ("rr_probability", "Release Radar"),
    ("radio_probability", "Radio"),
)

EARLY_DAYS = 30


class _Window(dict):
    """Un point de comparaison : les trois probabilités, sa date, son effectif."""


def _window(rows) -> _Window | None:
    """Agrège des lignes de prédiction en un point, ou None si elles n'existent pas."""
    if not rows:
        return None
    out = _Window(n=len(rows),
                  as_of=max(r["prediction_date"] for r in rows),
                  model_version=rows[-1]["model_version"])
    for col, _label in GATES:
        vals = [float(r[col]) for r in rows if r.get(col) is not None]
        # `None` et non 0.0 : une porte que le modèle n'a pas prédite n'a pas une
        # chance nulle, elle n'a pas de valeur.
        out[col] = median(vals) if vals else None
    return out


def trigger_rate_then_and_now(db, artist_id: int, song: str,
                              early_days: int = EARLY_DAYS) -> dict:
    """Le taux de trigger de CE titre dans ses `early_days` premiers jours, et aujourd'hui.

    Ne lève jamais : une base indisponible rend une absence NOMMÉE, pas un zéro.
    """
    try:
        rows = db.fetch_query(
            "SELECT prediction_date, days_since_release, model_version, "
            "       dw_probability, rr_probability, radio_probability "
            "FROM ml_song_predictions "
            "WHERE artist_id = %s AND song = %s "
            "ORDER BY prediction_date ASC",
            (artist_id, song))
    except Exception as e:  # noqa: BLE001 — une lecture qui échoue le DIT
        logger.error("trigger history unreadable for artist %s / %r: %s",
                     artist_id, song, type(e).__name__)
        return {"song": song, "early": None, "now": None, "comparable": False,
                "reason": f"historique illisible ({type(e).__name__})"}

    cols = ("prediction_date", "days_since_release", "model_version",
            "dw_probability", "rr_probability", "radio_probability")
    recs = [dict(zip(cols, r)) for r in (rows or [])]
    if not recs:
        return {"song": song, "early": None, "now": None, "comparable": False,
                "reason": "aucune prédiction enregistrée pour ce titre"}

    early = _window([r for r in recs
                     if r["days_since_release"] is not None
                     and r["days_since_release"] <= early_days])
    now = _window(recs[-1:])

    if early is None:
        return {"song": song, "early": None, "now": now, "comparable": False,
                "reason": (f"aucune mesure dans les {early_days} premiers jours — "
                           "le titre est sorti avant la mise en service du scoring")}

    if early["model_version"] != now["model_version"]:
        return {"song": song, "early": early, "now": now, "comparable": False,
                "reason": (f"modèles différents ({early['model_version']} → "
                           f"{now['model_version']}) : l'écart mêlerait le titre et "
                           "le modèle, il n'est pas lisible comme une évolution")}

    return {"song": song, "early": early, "now": now, "comparable": True,
            "reason": None}


def as_points(comparison: dict) -> list[dict]:
    """Une ligne par porte, prête à rendre : {label, early, now, delta}.

    `early`/`now`/`delta` valent `None` quand la mesure manque — jamais 0.0. Le rendu
    doit écrire « non mesuré », et c'est la seule façon de l'y obliger.
    """
    early, now = comparison.get("early"), comparison.get("now")
    points = []
    for col, label in GATES:
        a = early.get(col) if early else None
        b = now.get(col) if now else None
        points.append({
            "gate": label,
            "early": a,
            "now": b,
            "delta": (b - a) if (a is not None and b is not None
                                 and comparison.get("comparable")) else None,
        })
    return points
