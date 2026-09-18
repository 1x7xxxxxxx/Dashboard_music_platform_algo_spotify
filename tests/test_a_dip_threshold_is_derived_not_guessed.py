"""Un seuil du détecteur de creux porte sa DÉRIVATION, ou il n'entre pas.

Type: Test
Uses: tools/dev/calibrate_dip_thresholds
Depends on: airflow/dags/alert_monitor.py (DIP_TENANT_COLUMN, lu à l'AST)
Persists in: nothing

Pourquoi ce garde existe
------------------------
Le précédent est mesuré, pas prudentiel : un plancher de **30 lignes/jour écrit
d'instinct** rendait le détecteur de creux aveugle à **2 locataires sur 3**. Un seuil est
une affirmation sur une distribution ; l'écrire sans regarder la distribution, c'est
affirmer sans mesurer — et rien n'empêchait de recommencer.

R134 demande d'étendre `DIP_TENANT_COLUMN` de 5 à ~13 tables. C'est exactement le moment
où huit seuils seraient écrits à vue, d'un coup, parce qu'on est en train de faire autre
chose. Ce fichier rend ce geste impossible : une table ajoutée doit être accompagnée de
sa dérivation dans le commentaire d'allowlist, avec la DATE de la mesure.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.dev.calibrate_dip_thresholds import (  # noqa: E402
    COUVERTURE_MINIMALE, N_MINIMUM,
)

_DAG = ROOT / "airflow" / "dags" / "alert_monitor.py"

#: Les cinq tables présentes AVANT R134, vérifiées en base le 2026-08-23 (commentaire
#: d'allowlist en place). Toute table ajoutée après doit porter sa dérivation.
_HISTORIQUES = frozenset({
    "youtube_video_stats", "soundcloud_tracks_daily", "meta_insights_performance_day",
    "ml_song_predictions", "s4a_song_timeline",
})


def _tables_surveillees() -> set[str]:
    """Les clés de `DIP_TENANT_COLUMN`, lues à l'AST et non par une expression régulière.

    Un prédicat textuel compterait la table nommée dans un commentaire — y compris dans
    le commentaire qui explique pourquoi elle n'y est PAS.
    """
    arbre = ast.parse(_DAG.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Assign)
                and any(getattr(t, "id", "") == "DIP_TENANT_COLUMN" for t in noeud.targets)
                and isinstance(noeud.value, ast.Dict)):
            return {k.value for k in noeud.value.keys if isinstance(k, ast.Constant)}
    raise AssertionError(
        "`DIP_TENANT_COLUMN` n'est plus une affectation de dictionnaire littéral dans "
        f"{_DAG.name}. Le garde ne peut plus lire la liste des tables surveillées — il "
        "faut le réécrire, pas le contourner.")


def test_the_allowlist_is_still_readable() -> None:
    """Anti-vacuité : sans tables lues, tout ce qui suit serait vert pour rien."""
    tables = _tables_surveillees()
    assert len(tables) >= 5, (
        f"seulement {len(tables)} table(s) lues dans `DIP_TENANT_COLUMN` — le détecteur "
        "a rétréci, ou le garde ne le lit plus.")


def test_a_table_added_to_the_dip_detector_carries_its_derivation() -> None:
    """LE GARDE. Une table neuve ⇒ sa dérivation, datée, dans le commentaire voisin."""
    neuves = sorted(_tables_surveillees() - _HISTORIQUES)
    if not neuves:
        pytest.skip("aucune table ajoutée depuis le 2026-08-23")
    texte = _DAG.read_text(encoding="utf-8")
    sans_derivation = []
    for table in neuves:
        # La dérivation nomme la table, un `n=`, et une date ISO.
        motif = re.compile(
            rf"#[^\n]*\b{re.escape(table)}\b[^\n]*(?:\n#[^\n]*)*", re.M)
        blocs = motif.findall(texte)
        if not any(re.search(r"\bn\s*=\s*\d+", b) and re.search(r"\d{4}-\d{2}-\d{2}", b)
                   for b in blocs):
            sans_derivation.append(table)
    assert not sans_derivation, (
        "table(s) ajoutée(s) au détecteur de creux sans dérivation de seuil : "
        f"{sans_derivation}.\n"
        "Un seuil est une affirmation sur une distribution. Écrit d'instinct, un "
        "plancher de 30 lignes/jour a déjà rendu ce détecteur aveugle à 2 locataires "
        "sur 3.\nMesurer : `python3 tools/dev/calibrate_dip_thresholds.py --tables "
        "<table>`, puis reporter le résultat en commentaire avec `n=<observations>` et "
        "la date de la mesure.")


# ── Le calibrateur lui-même, muté dans les deux sens ──────────────────────────

def _lignes(par_jour: list[int], depart: str = "2026-01-01"):
    """Fabrique le résultat de la requête d'agrégation, sans base."""
    import datetime
    d0 = datetime.date.fromisoformat(depart)
    return [(1, d0 + datetime.timedelta(days=i), n) for i, n in enumerate(par_jour)]


class _FausseBase:
    def __init__(self, cols, lignes):
        self._cols, self._lignes = cols, lignes

    def fetch_query(self, sql, params=None):
        return [(c,) for c in self._cols] if "information_schema" in sql else self._lignes


def test_the_calibrator_refuses_a_sample_too_small_to_be_a_distribution() -> None:
    """FAUX POSITIF fabriqué : peu d'observations ⇒ AUCUN seuil.

    C'est la fonction principale de l'outil. Rendre un chiffre ici serait le défaut même
    qu'il existe pour empêcher — et c'est le cas RÉEL sur cette machine, où 7 des 8
    tables candidates ont moins de 30 observations.
    """
    from tools.dev.calibrate_dip_thresholds import calibrer
    db = _FausseBase({"artist_id", "date"}, _lignes([40] * (N_MINIMUM - 1)))
    r = calibrer(db, "t")
    assert r["seuil"] is None, (
        f"seuil rendu sur {N_MINIMUM - 1} observations : {r['seuil']}. Sous "
        f"{N_MINIMUM}, un quantile empirique ne veut rien dire.")
    assert "trop petit" in r["verdict"]


def test_the_calibrator_refuses_a_table_that_is_not_a_daily_fact() -> None:
    """FAUX POSITIF nº2 : une table de DIMENSION passe « locataire + date » et n'est pas un fait.

    `hypeddit_campaigns` est le cas réel : il porte `artist_id`, `created_at` et
    `updated_at`, donc il satisfait le critère « par locataire ET daté » que le balayage
    avait utilisé pour compter 84 tables éligibles. Mais des campagnes sont créées de
    temps en temps, pas chaque jour : un « creux » y est le fonctionnement normal, et
    l'y brancher produirait une alerte quotidienne que personne ne lirait.
    """
    from tools.dev.calibrate_dip_thresholds import calibrer
    # 40 observations, mais étalées : une tous les dix jours.
    import datetime
    d0 = datetime.date(2026, 1, 1)
    lignes = [(1, d0 + datetime.timedelta(days=10 * i), 3) for i in range(40)]
    r = calibrer(_FausseBase({"artist_id", "date"}, lignes), "t")
    assert r["seuil"] is None, (
        f"seuil rendu sur une table à {r.get('couverture', '?'):.0%} de couverture. Le "
        f"minimum est {COUVERTURE_MINIMALE:.0%} : sous ce taux, la table ne reçoit pas "
        "de lignes chaque jour et l'absence n'y est pas un défaut.")
    assert "quotidien" in r["verdict"]


def test_the_calibrator_does_return_a_threshold_on_a_real_distribution() -> None:
    """FAUX NÉGATIF fabriqué : un vrai fait quotidien DOIT être calibrable.

    Sans ce test, un calibrateur qui refuse TOUT passerait les deux assertions
    ci-dessus — et c'est précisément ce que rend l'outil sur cette machine aujourd'hui.
    Un refus universel se lit comme une prudence ; c'est une panne.
    """
    from tools.dev.calibrate_dip_thresholds import calibrer
    import random
    rng = random.Random(7)
    par_jour = [max(1, int(rng.gauss(40, 8))) for _ in range(120)]
    r = calibrer(_FausseBase({"artist_id", "date"}, _lignes(par_jour)), "t")
    assert r["seuil"] is not None, (
        f"aucun seuil sur 120 jours consécutifs d'une distribution normale : "
        f"{r['verdict']}. L'outil refuse tout, donc il ne mesure rien.")
    assert 0 < r["seuil"]["plancher"] <= r["mediane"], (
        "le plancher dérivé dépasse la médiane — il déclencherait sur une journée "
        "parfaitement ordinaire")
