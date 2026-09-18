"""Les deux seuils de R87 sont comparés chaque nuit, là où leurs grandeurs sont écrites.

Type: Test
Uses: src.utils.daily_ops_metrics
Depends on: src/utils/nightly_maintenance.py
Persists in: rien

Ce qui a été mesuré (2026-09-18)
--------------------------------
`tools/scale_check.sh` porte les deux déclencheurs de réouverture de R87 depuis le
2026-09-11 — pic de sessions humaines par minute, et p50 de rendu serveur. Il exige un
accès `PROD_SSH`, donc il ne peut être **ni** un cron sur la machine (elle devrait se
connecter à elle-même) **ni** une étape de CI (pas d'identifiants de prod).

Conséquence : **aucun automate ne l'a jamais lancé.** `Makefile:196` n'est cité nulle
part, et `tools/dev/reopen_check.py::_r114` ne part que lorsqu'un humain tape la
commande avec la variable. Une décision qu'on ne sait pas relire se périme en silence —
c'est ce que le script dit de lui-même dans son propre en-tête.

Or ses deux grandeurs sont **écrites chaque nuit** dans `daily_ops_metrics`
(`peak_sessions`, `p50_render_ms`) par le DAG de 23 h. Il ne manquait que la
comparaison. Ce n'est pas une seconde instrumentation — c'est la même mesure, relue au
seul endroit où elle est déjà persistée.

Ce que ce fichier tient
-----------------------
1. les deux seuils déclenchent quand ils sont franchis, et pas avant ;
2. **un `None` n'est pas « sous le seuil »** — une grandeur absente veut dire que
   Prometheus n'a pas répondu, ou que personne ne s'est connecté. Deux choses très
   différentes de « il y a peu de charge », et aucune ne permet de conclure ;
3. la comparaison est bien CÂBLÉE dans la maintenance nocturne — un prédicat juste
   branché nulle part est la forme que ce dépôt a payée six fois.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dom():
    import sys
    sys.path.insert(0, str(ROOT))
    from src.utils import daily_ops_metrics
    return daily_ops_metrics


def test_a_crossed_threshold_names_which_one_and_why(dom) -> None:
    """Un déclencheur muet sur SA raison envoie chercher au mauvais endroit."""
    sous = dom.reopening_triggers({"peak_sessions": 3, "p50_render_ms": 40})
    assert sous == [], f"déclenché sous les deux seuils : {sous}"

    sessions = dom.reopening_triggers(
        {"peak_sessions": dom.SEUIL_SESSIONS + 1, "p50_render_ms": 40})
    assert len(sessions) == 1 and "R87 §1" in sessions[0], (
        f"le seuil de sessions ne déclenche pas, ou ne dit pas lequel : {sessions}")
    assert "test_in_memory_limits_forbid_replicas" in sessions[0], (
        "le message ne nomme pas l'inventaire de ce qui casse à N>1 — un déclencheur "
        "qui dit « ça se rouvre » sans dire où lire est la moitié d'un déclencheur.")

    rendu = dom.reopening_triggers(
        {"peak_sessions": 1, "p50_render_ms": dom.SEUIL_P50_MS + 1})
    assert len(rendu) == 1 and "R87 §2" in rendu[0], (
        f"le seuil de rendu ne déclenche pas : {rendu}")
    assert "authentifiées" in rendu[0], (
        "le message ne rappelle pas que ce p50 ne compte QUE les pages authentifiées. "
        "Ce dépôt a publié puis rétracté une conclusion sur ce zéro-là.")

    deux = dom.reopening_triggers(
        {"peak_sessions": 99, "p50_render_ms": 9999})
    assert len(deux) == 2, "les deux seuils franchis ne rendent pas deux raisons"


def test_an_absent_value_is_not_below_the_threshold(dom) -> None:
    """La moitié qui compte : `None` ne se lit pas « peu de charge ».

    Une grandeur absente veut dire que Prometheus n'a pas répondu ou que personne ne
    s'est connecté. Traiter `None` comme un petit nombre ferait dire « sous le seuil »
    à une mesure qui n'a pas eu lieu — le zéro d'instrument que ce module passe son
    en-tête à distinguer d'un zéro d'évènement.
    """
    assert dom.reopening_triggers({"peak_sessions": None, "p50_render_ms": None}) == []
    assert dom.reopening_triggers({}) == []
    # …et surtout : un `None` ne doit pas non plus DÉCLENCHER par comparaison fautive.
    for valeurs in ({"peak_sessions": None, "p50_render_ms": 9999},
                    {"peak_sessions": 99, "p50_render_ms": None}):
        out = dom.reopening_triggers(valeurs)
        assert len(out) == 1, (
            f"{valeurs} rend {len(out)} raison(s) : une grandeur absente a été "
            "comparée comme si elle valait quelque chose.")


def test_the_comparison_is_wired_into_the_nightly_run() -> None:
    """Un prédicat juste branché nulle part ne garde rien — six fois payé ici."""
    src = (ROOT / "src" / "utils" / "nightly_maintenance.py").read_text(encoding="utf-8")
    import ast
    arbre = ast.parse(src)
    appels = {ast.unparse(n.func) for n in ast.walk(arbre) if isinstance(n, ast.Call)}
    assert "reopening_triggers" in appels, (
        "`nightly_maintenance` n'APPELLE pas `reopening_triggers`. Les deux seuils de "
        "R87 redeviennent invisibles jusqu'à ce qu'un humain tape `make scale-check` "
        "avec PROD_SSH — c'est-à-dire jamais, mesuré.")


def test_the_thresholds_match_the_script_that_defined_them() -> None:
    """Deux définitions d'un même seuil divergent ; celle-ci est adossée à l'autre."""
    sh = (ROOT / "tools" / "scale_check.sh").read_text(encoding="utf-8")
    import re
    import sys
    sys.path.insert(0, str(ROOT))
    from src.utils import daily_ops_metrics as d
    for nom, attendu in (("SEUIL_SESSIONS", d.SEUIL_SESSIONS),
                         ("SEUIL_P50", d.SEUIL_P50_MS)):
        # ⚠️ DEUX FORMES, et la première version n'en lisait qu'une.
        #
        # `SEUIL_SESSIONS` est déclaré en tête (`NOM="${NOM:-20}"`), `SEUIL_P50` ne l'est
        # pas : il n'apparaît que dans son défaut en ligne, `"${SEUIL_P50:-200}"`. Le
        # test a donc rougi sur un seuil parfaitement correct — un garde trop étroit
        # accuse le code au lieu de se corriger, et c'est la façon la plus sûre de se
        # faire désarmer. On cherche le DÉFAUT, qui est la forme commune aux deux.
        valeurs = {int(x) for x in re.findall(rf'\$\{{{nom}:-(\d+)\}}', sh)}
        assert valeurs, f"`{nom}` n'est plus lisible dans scale_check.sh"
        assert len(valeurs) == 1, (
            f"`{nom}` porte {len(valeurs)} défauts différents dans scale_check.sh : "
            f"{sorted(valeurs)}. Un seuil écrit deux fois diverge.")
        assert valeurs.pop() == attendu, (
            f"{nom} diffère entre `scale_check.sh` et Python (attendu {attendu}). "
            "Deux définitions du même seuil divergent en silence, et personne ne sait "
            "laquelle a décidé.")
