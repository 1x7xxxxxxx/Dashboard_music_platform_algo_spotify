"""Une lecture tronquée ne s'enregistre pas comme une lecture complète.

Type: Test
Uses: pytest, ast
Depends on: src/collectors/instagram_api_collector.py, airflow/dags/instagram_daily.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
`fetch_media` plafonne à 10 pages. Au-delà, les publications les plus anciennes ne
sont **pas** relues cette nuit — et le seul signal était un `logger.warning` dans le
journal d'un conteneur. Le run s'enregistrait `success`, donc un historique amputé
était indiscernable d'un historique complet, sur toutes les surfaces qui lisent
`etl_run_log`.

Le dépôt a déjà payé cette classe : 672 échecs de surveillance de CSV en une semaine,
tous journalisés, aucun rapporté. Un fait sur les DONNÉES ne se dit pas dans un log.

Ce qui n'est PAS fait ici
-------------------------
On ne lève pas : un plafond n'est pas une erreur, c'est une lecture bornée, et le
collecteur a raison de rendre ce qu'il a lu. On ne relève pas non plus le plafond —
ce serait échanger une troncature mesurée contre un quota d'API inconnu. On rend la
troncature VISIBLE, avec le statut qui la décrit : `partial`, celui que la tâche
d'alerte remonte déjà.

Contexte, vérifié au passage : R81 supposait que ces collecteurs « relisent tout
chaque nuit sans repère de progression » et qu'un repère les accélérerait. C'est
FAUX, et le vérifier a évité une régression. Ces API rendent des compteurs CUMULÉS
par entité (`playback_count`, `view_count`, `like_count`) : relire chaque entité
chaque nuit n'est pas du gaspillage, c'est la MESURE — tout `platform_timeseries`
(max déjà vu · jours consécutifs · par entité) en dépend. Un repère de progression
aurait figé le compteur de tout titre cessant d'être récent.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=8)
def _read(rel: str) -> str:
    """Lu à l'APPEL, pas à l'import — voir `test_a_test_file_is_collectable_without_what_it_watches`."""
    return (ROOT / rel).read_text(encoding="utf-8")


def COLLECTOR() -> str:
    return _read("src/collectors/instagram_api_collector.py")


def DAG() -> str:
    return _read("airflow/dags/instagram_daily.py")


def test_the_collector_carries_the_truncation_beyond_the_log() -> None:
    """Un `logger.warning` ne sort pas du conteneur ; un attribut, si."""
    tree = ast.parse(COLLECTOR())
    sets_true = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "media_truncated"
                for t in n.targets)
        and isinstance(n.value, ast.Constant) and n.value.value is True]
    assert sets_true, (
        "le plafond de pagination n'est plus porté par `media_truncated` : la "
        "troncature redevient une ligne de journal que personne ne lit")


def test_the_flag_is_reset_before_each_read() -> None:
    """Sinon un locataire tronqué contamine tous les suivants du même processus."""
    tree = ast.parse(COLLECTOR())
    fetch = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "fetch_media")
    resets = [n for n in fetch.body
              if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Attribute) and t.attr == "media_truncated"
                      for t in n.targets)
              and isinstance(n.value, ast.Constant) and n.value.value is False]
    assert resets, (
        "`media_truncated` n'est pas remis à faux en tête de `fetch_media` : le "
        "premier locataire tronqué marquerait tous les suivants de la même nuit")


def test_the_dag_records_partial_rather_than_success() -> None:
    tree = ast.parse(DAG())
    guarded = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if "media_truncated" not in ast.dump(node.test):
            continue
        body = ast.dump(ast.Module(body=node.body, type_ignores=[]))
        guarded.append("'partial'" in body or '"partial"' in body)
    assert guarded, (
        "le DAG Instagram n'examine plus `media_truncated` : une nuit tronquée "
        "s'enregistre de nouveau `success`, et l'historique amputé de l'artiste "
        "devient indiscernable d'un historique complet")
    assert all(guarded), (
        "le DAG voit la troncature mais n'enregistre pas `partial` — or c'est le "
        "seul statut que la tâche d'alerte remonte pour ce cas")


def test_partial_is_a_status_the_alert_actually_reports() -> None:
    """Un statut que personne ne remonte serait un garde muet.

    Lu par l'AST et non par une recherche de chaîne : le dépôt a mesuré quatre gardes
    passés au vert sur leur PROPRE commentaire. Ici c'est la comparaison réelle qu'on
    cherche — `status not in ('failed', 'partial')` — pas ses lettres.
    """
    tree = ast.parse(_read("airflow/dags/alert_monitor.py"))
    reported = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
            continue
        for comparator in node.comparators:
            if isinstance(comparator, (ast.Tuple, ast.List, ast.Set)):
                reported |= {e.value for e in comparator.elts
                             if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    assert {"failed", "partial"} <= reported, (
        "la tâche d'alerte ne compare plus un statut à un ensemble contenant "
        "`failed` ET `partial` : enregistrer `partial` ne produirait plus aucun "
        f"signal, et la troncature redeviendrait invisible. Vu : {sorted(reported)}")
