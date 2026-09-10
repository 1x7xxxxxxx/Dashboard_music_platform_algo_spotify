"""Les deux chemins de calcul d'un même nombre doivent rendre la même valeur.

Type: Test
Uses: pytest
Depends on: src/utils/metric_bounds.py, airflow/dags/alert_monitor.py
Persists in: nothing

Ce qui manquait
---------------
Quatre des cinq piliers de Moses/Gavish/Vorwerck sont instrumentés ici, et **tous
regardent les tables brutes**. Aucun ne regarde les nombres que le produit calcule.
Densmore (*Data Pipelines Pocket Reference*, p. 218) : valider les modèles construits
en FIN de pipeline, pas seulement la source.

Mesuré le 2026-09-10 : la figure de l'accueil dessinait 23 251 écoutes là où la fenêtre
en contenait 8 490 — ×2,7. Une métrique hors bornes, qu'aucun contrôle ne pouvait voir.

L'invariant retenu n'a pas de seuil, donc pas de calibrage qui vieillit : pour une
source QUOTIDIENNE, le compteur « depuis le début » et la somme de la série lisent la
même table et doivent être égaux. Mesuré sur l'artiste 1 : 163 088 des deux côtés.
"""
from __future__ import annotations

import ast
from pathlib import Path

from src.utils.metric_bounds import CUMULATIVE, DAILY, KINDS, disagreement, report

REPO = Path(__file__).resolve().parent.parent
DAG = REPO / "airflow" / "dags" / "alert_monitor.py"


# ── Le prédicat ─────────────────────────────────────────────────────────────

def test_a_daily_source_must_balance_exactly() -> None:
    assert disagreement("spotify", 163088, 163088) is None
    msg = disagreement("spotify", 163088, 23397)
    assert msg and "163,088" in msg and "23,397" in msg, msg


def test_a_cumulative_counter_may_legitimately_exceed_what_we_measured() -> None:
    """Le compteur porte tout ce qui précède notre première collecte : ce n'est pas
    un désaccord, c'est la définition."""
    assert disagreement("youtube", 120987, 44) is None


def test_a_measured_sum_can_never_exceed_a_cumulative_counter() -> None:
    """L'autre sens EST impossible : un cumul ne redescend pas."""
    assert disagreement("youtube", 100, 500) is not None


def test_nothing_measured_raises_nothing() -> None:
    """On ne juge pas ce qu'on n'a pas lu — la règle de toute cette séance."""
    assert disagreement("spotify", None, 5) is None
    assert disagreement("spotify", 5, None) is None


def test_every_charted_platform_declares_its_nature() -> None:
    """Une plateforme sans nature déclarée serait contrôlée par défaut, donc mal."""
    from src.dashboard.utils.platform_timeseries import daily_streams_by_platform
    import inspect
    src = inspect.getsource(daily_streams_by_platform)
    for key in ("spotify", "youtube", "soundcloud"):
        assert f'"{key}"' in src, f"{key} n'est plus produite par le helper"
        assert key in KINDS, f"{key} n'a pas de nature déclarée dans metric_bounds"
    assert set(KINDS.values()) <= {DAILY, CUMULATIVE}


def test_the_report_names_the_tenant_free_symptom() -> None:
    out = report([("spotify", 100, 90), ("youtube", 100, 5)])
    assert len(out) == 1 and "spotify" in out[0]


# ── Le constat atteint le message, pas seulement le sujet ───────────────────

def test_the_finding_reaches_the_body_of_the_alert_not_only_its_subject() -> None:
    """Trois nuits d'alertes se sont évaporées parce qu'un constat s'arrêtait avant
    l'envoi. On vérifie donc la chaîne entière, structurellement.
    """
    tree = ast.parse(DAG.read_text(encoding="utf-8"))
    names = {n.name for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "check_metric_bounds" in names, "le contrôle a disparu du DAG"

    send = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "send_consolidated_alert"), None)
    assert send is not None, "send_consolidated_alert a disparu"
    body = ast.unparse(send)
    assert "check_metric_bounds" in body, "le constat n'est jamais RELU par l'envoi"

    # LES DEUX SURFACES, nommées séparément. Un simple compte d'occurrences était trop
    # permissif : mutation faite le 2026-09-10, section HTML et ligne de sujet retirées
    # toutes les deux, le garde est resté VERT parce que le `pull`, la condition et le
    # passage en kwargs suffisaient à atteindre le seuil. On regarde donc À QUOI la
    # variable sert, pas combien de fois son nom apparaît.
    appended_to: dict[str, bool] = {"sections": False, "subject_parts": False}
    for node in ast.walk(send):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "append"):
            continue
        target = getattr(node.func.value, "id", None)
        if target not in appended_to:
            continue
        if "metric_bounds" in ast.unparse(node):
            appended_to[target] = True

    assert appended_to["sections"], (
        "aucune section du corps de l'e-mail ne porte le constat : il n'existera que "
        "dans le sujet, et trois nuits d'alertes se sont déjà évaporées ainsi")
    assert appended_to["subject_parts"], (
        "le sujet ne nomme pas le constat : un e-mail dont le sujet ne dit rien de "
        "neuf ne se lit pas")


def test_the_task_is_wired_into_the_dag() -> None:
    """Une fonction que rien n'ordonnance ne tourne jamais."""
    src = DAG.read_text(encoding="utf-8")
    tree = ast.parse(src)
    task_ids = {
        kw.value.value
        for node in ast.walk(tree) if isinstance(node, ast.Call)
        for kw in node.keywords
        if kw.arg == "task_id" and isinstance(kw.value, ast.Constant)
    }
    assert "check_metric_bounds" in task_ids, (
        "aucun opérateur ne porte `check_metric_bounds` : le contrôle est écrit et "
        "rien ne l'exécute — la classe `un détecteur écrit que rien n'appelle`")
    assert "t_metric_bounds" in src.split(">> t_alert")[0].rsplit("[", 1)[-1], (
        "la tâche n'est pas dans la liste qui précède l'envoi : son constat "
        "n'atteindra jamais l'e-mail")
