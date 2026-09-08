"""Garde : une collecte qui écrit des ZÉROS ne passe plus inaperçue.

Type: Test
Uses: src.utils.value_monitor, ast
Depends on: alert_monitor.check_zero_resets
Persists in: rien

Le 2026-06-01, `soundcloud_tracks_daily` a reçu 19 titres dont **19 compteurs cumulés à
zéro**, pour des titres qui portaient plusieurs milliers la veille. Trois contrôles
regardaient et aucun ne pouvait le voir :

* la fraîcheur voyait des lignes du jour — elle compte des lignes, pas des valeurs ;
* `check_row_anomalies` ne surveille que le sens du PIC ;
* `is_partial_collection` (pilier Volume) exclut zéro **en nombre de lignes** — il y en
  avait dix-neuf, toutes fausses.

Le trou n'était donc pas une négligence : c'était un pilier manquant. Ce fichier tient
le prédicat ET le fait qu'une tâche l'appelle — un détecteur que rien n'exécute est la
classe `correct-code-nothing-reaches`, déjà vue six fois dans ce dépôt.
"""
from __future__ import annotations

import ast
import pathlib

from src.utils.value_monitor import (
    MIN_ENTITIES,
    is_reportable,
    is_zero_reset,
    zero_reset_finding,
)

_DAG = pathlib.Path("airflow/dags/alert_monitor.py")


def test_a_counter_that_falls_back_to_zero_is_impossible() -> None:
    """Le cas réel : 3 214 la veille, 0 aujourd'hui."""
    assert is_zero_reset(3214, 0) is True


def test_a_counter_that_was_never_positive_is_not_a_reset() -> None:
    """Une vidéo publiée hier et jamais vue est légitimement à zéro.

    C'est la moitié du prédicat qui empêche d'alerter sur chaque nouveauté du catalogue.
    """
    assert is_zero_reset(0, 0) is False
    assert is_zero_reset(None, 0) is False


def test_a_counter_that_merely_stalls_is_not_a_reset() -> None:
    """Un compteur qui ne bouge pas n'est pas un compteur qui tombe."""
    assert is_zero_reset(3214, 3214) is False
    assert is_zero_reset(3214, 3300) is False


def test_a_single_entity_is_not_a_collection_failure() -> None:
    """Un titre retiré du catalogue n'est pas une panne de collecte."""
    assert is_reportable(1, 19) is False
    assert is_reportable(MIN_ENTITIES, 19) is True


def test_the_real_incident_is_reported() -> None:
    """Les chiffres exacts du 2026-06-01, pas un cas d'école."""
    assert is_reportable(19, 19) is True
    finding = zero_reset_finding("soundcloud_tracks_daily", "playback_count",
                                 1, "2026-06-01", 19, 19)
    assert finding["entities"] == 19 and finding["total"] == 19, finding
    assert finding["table"] == "soundcloud_tracks_daily", finding


def test_the_detector_never_reads_a_daily_quantity() -> None:
    """`s4a_song_timeline` est HORS du périmètre, et c'est mesuré.

    Ses `streams` sont une quantité du JOUR, où zéro veut dire « pas écouté
    aujourd'hui » — 27 à 55 % du catalogue chaque jour. Le patron du livre (taux de
    zéros comparé à la veille, *Data Quality Fundamentals* p. 117) y sonnait **93 fois
    sur 1 254 jours** ; le prédicat retenu sonne **une** fois, sur le seul incident.

    Un détecteur qui crie 93 fois est un détecteur que personne ne lit — la classe
    `watchdog-becomes-the-noise`, déjà au catalogue.
    """
    tree = ast.parse(_DAG.read_text(encoding="utf-8"))
    targets = next((n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Assign)
                    and any(getattr(t, "id", "") == "ZERO_RESET_TARGETS"
                            for t in n.targets)), None)
    assert targets is not None, "ZERO_RESET_TARGETS a disparu du DAG"
    tables = {e.elts[0].value for e in targets.elts}
    assert tables == {"soundcloud_tracks_daily", "youtube_video_stats"}, (
        f"le périmètre a changé : {sorted(tables)}. Une table de quantités du jour y "
        "produirait du bruit quotidien — mesuré à 93 alertes sur 1 254 jours")


def test_a_task_actually_runs_the_detector() -> None:
    """Présence ≠ atteignabilité. Le prédicat doit être APPELÉ par une tâche du DAG.

    Suivi sur la structure : `check_zero_resets` doit exister, appeler `is_reportable`,
    et être le `python_callable` d'un opérateur qui précède l'envoi. Chercher la chaîne
    « zero_reset » dans le fichier rougirait sur un commentaire — c'est la classe
    `a-textual-guard-is-blind`.
    """
    tree = ast.parse(_DAG.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "check_zero_resets"), None)
    assert fn is not None, "la tâche a disparu"
    called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert {"is_reportable", "zero_reset_finding"} <= called, (
        f"la tâche n'appelle pas le prédicat : {sorted(called)}")

    wired = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "PythonOperator"
             and any(k.arg == "python_callable"
                     and getattr(k.value, "id", "") == "check_zero_resets"
                     for k in n.keywords)]
    assert wired, "aucun PythonOperator n'exécute check_zero_resets"


def test_the_detector_only_looks_at_the_last_complete_day() -> None:
    """Sans borne, il redit un fait vieux de trois mois toutes les nuits.

    Lancé en production le 2026-09-08, il a remonté l'incident du **2026-06-01** — juste,
    et qu'il aurait répété chaque nuit indéfiniment. C'est la classe
    `watchdog-becomes-the-noise` : un détecteur qu'on finit par ne plus lire.

    La fenêtre est celle de `check_row_dips`, son voisin immédiat, et pas une troisième
    politique : le dernier jour COMPLET, le jour en cours exclu parce qu'une collecte à
    moitié écrite ressemble à une collecte fautive.
    """
    tree = ast.parse(_DAG.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "check_zero_resets")
    sql = " ".join(n.value for n in ast.walk(fn)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and "FROM flagged" in n.value)
    assert sql, "la requête a disparu"
    assert "CURRENT_DATE" in sql, (
        "le détecteur balaie tout l'historique : il criera un incident de juin chaque "
        "nuit de septembre")
    assert "max(day)" in sql and "day <" in sql, (
        "la borne n'est pas « le dernier jour complet » — le jour en cours ferait "
        "partir une alerte chaque matin sur une collecte à moitié écrite")


def test_the_finding_reaches_the_email_and_the_digest() -> None:
    """Un constat qui n'entre pas dans l'empreinte se tait la nuit où lui seul change.

    C'est le refus explicite de `digest_input`, et la raison pour laquelle la catégorie
    doit être inscrite : sans elle, une nuit portant UNIQUEMENT des compteurs remis à
    zéro serait considérée identique à la précédente, et supprimée.
    """
    from src.utils.alert_repetition import FINDING_CATEGORIES, digest_input

    assert "zero_resets" in FINDING_CATEGORIES
    digest = digest_input(zero_resets=[{"tenant": 1}])
    assert digest["zero_resets"] == [{"tenant": 1}]

    src = _DAG.read_text(encoding="utf-8")
    tree = ast.parse(src)
    send = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "send_consolidated_alert")
    names = {n.id for n in ast.walk(send) if isinstance(n, ast.Name)}
    assert "zero_resets" in names, (
        "l'envoi ne lit pas le constat : il serait calculé chaque nuit et jeté")
