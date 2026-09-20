"""Une action qui réussit le DIT, même quand un rerun suit immédiatement.

Type: Test
Uses: ast
Depends on: src/dashboard/**, src/dashboard/utils/ui.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Signalé par le propriétaire le 2026-09-20, en faisant R125 :

  > « j'ai appuyé sur enregistrer les outcomes 7j + 28j mais rien n'a fonctionné ou rien
  >   ne m'a communiqué que ça avait été enregistré »

**L'écriture avait réussi** — 33 lignes vérifiées en production (11 titres × 3 fenêtres).
Le code faisait :

    st.success("… enregistrés …")
    st.rerun()

`st.rerun()` JETTE le rendu en cours : le message n'est jamais peint. L'écran se recharge
sans un mot, ce qui se lit exactement comme un échec — et la réaction naturelle est de
recommencer, ou de conclure que la fonctionnalité est cassée.

⚠️ **Ce n'était pas un oubli isolé : 23 sites** portaient ce motif dans
`src/dashboard/`, dont les QUATRE boutons de « Saisie S4A ». Un motif qu'on recopie.

⚠️ Le remède a sa propre façon d'échouer, et elle est gardée plus bas : déposer un
message que PERSONNE ne ramasse est un silence différent, pas un silence corrigé.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_DASHBOARD = ROOT / "src" / "dashboard"


def _fichiers() -> list[Path]:
    return [f for f in sorted(_DASHBOARD.rglob("*.py")) if "__pycache__" not in str(f)]


def _appel(noeud, nom: str) -> bool:
    return (isinstance(noeud, ast.Expr) and isinstance(noeud.value, ast.Call)
            and getattr(noeud.value.func, "attr", "") == nom)


def _sites_perdus(arbre: ast.Module) -> list[int]:
    """Les `st.<niveau>(…)` suivis IMMÉDIATEMENT d'un `st.rerun()`.

    Les quatre niveaux, pas seulement `success` : un `st.error` avalé par un rerun est
    pire encore — l'utilisateur ne sait même pas que quelque chose a échoué.
    """
    perdus = []
    for n in ast.walk(arbre):
        corps = getattr(n, "body", None)
        if not isinstance(corps, list):
            continue
        for i, x in enumerate(corps[:-1]):
            if _appel(corps[i + 1], "rerun") and any(
                    _appel(x, niveau) for niveau in ("success", "info", "warning", "error")):
                perdus.append(x.lineno)
    return perdus


@pytest.mark.parametrize("rel", [str(f.relative_to(ROOT)) for f in _fichiers()],
                         ids=lambda r: Path(r).name)
def test_no_message_is_thrown_away_by_the_rerun_that_follows(rel: str) -> None:
    """LE GARDE. Un message affiché juste avant un rerun n'est jamais vu."""
    perdus = _sites_perdus(ast.parse((ROOT / rel).read_text(encoding="utf-8")))
    assert not perdus, (
        f"{rel} : message(s) affiché(s) juste avant `st.rerun()`, ligne(s) {perdus}.\n"
        "Le rerun jette le rendu en cours — l'utilisateur voit la page se recharger sans "
        "un mot, ce qui se lit comme un échec. Utiliser `flash(...)` de "
        "`src/dashboard/utils/ui.py` : il dépose le message, et le rendu suivant "
        "l'affiche.")


def test_something_actually_deposits_a_flash() -> None:
    """ANTI-VACUITÉ nº1 : si plus personne n'appelle `flash`, le test ci-dessus est vide."""
    deposes = sum(
        1 for f in _fichiers()
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8")))
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "flash")
    assert deposes >= 15, (
        f"seulement {deposes} appel(s) à `flash(...)` — 23 sites en portaient un le "
        "2026-09-20. Soit ils sont revenus à `st.success` + `st.rerun`, soit le motif de "
        "détection a raté sa cible.")


def test_the_flash_is_actually_consumed() -> None:
    """ANTI-VACUITÉ nº2, et c'est la façon dont le REMÈDE échoue.

    Déposer un message que personne ne ramasse est un silence différent, pas un silence
    corrigé — et il serait plus difficile à diagnostiquer que l'original, parce que le
    code aurait l'air correct de part et d'autre.
    """
    app = ast.parse((_DASHBOARD / "app.py").read_text(encoding="utf-8"))
    appelle = any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "show_flash"
                  for n in ast.walk(app))
    assert appelle, (
        "`app.py` n'appelle pas `show_flash()`. Les 23 `flash(...)` déposent alors un "
        "message que personne n'affiche — l'utilisateur reste devant le même silence, "
        "et le code a l'air correct des deux côtés.")


def test_the_flash_is_consumed_not_just_read() -> None:
    """Sans le `pop`, le message resterait à chaque rendu et deviendrait du bruit."""
    from src.dashboard.utils import ui
    src = ast.parse(Path(ui.__file__).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(src)
              if isinstance(n, ast.FunctionDef) and n.name == "show_flash")
    assert any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "pop"
               for n in ast.walk(fn)), (
        "`show_flash` ne CONSOMME pas le message : il resterait affiché à chaque rendu "
        "suivant, et un message permanent est un message qu'on apprend à ignorer.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuité : sur le code EXACT du défaut, le détecteur doit mordre.

    Les DEUX moitiés comptent. Sans la seconde, corriger le défaut ferait rougir son
    propre garde — et la seule façon de garder la CI verte serait d'arrêter de corriger.
    """
    defaut = ast.parse(
        "def enregistrer():\n"
        "    ecrire()\n"
        "    st.success('Enregistré.')\n"
        "    st.rerun()\n")
    assert _sites_perdus(defaut) == [3], "le défaut n'est pas vu"

    corrige = ast.parse(
        "def enregistrer():\n"
        "    ecrire()\n"
        "    flash('Enregistré.')\n"
        "    st.rerun()\n")
    assert _sites_perdus(corrige) == [], "un correctif ferait rougir le garde"


@pytest.mark.parametrize("niveau", ["success", "info", "warning", "error"])
def test_the_detector_sees_all_four_levels_not_only_success(niveau: str) -> None:
    """Un `st.error` avalé par un rerun est PIRE : l'échec devient invisible.

    Le garde a été écrit sur le symptôme signalé — un `st.success` — et la portée est
    la famille de geste, pas le verbe. Sans cette paramétrisation, un garde ancré sur
    `success` laisserait les trois autres niveaux vivants.
    """
    arbre = ast.parse(f"def f():\n    st.{niveau}('x')\n    st.rerun()\n")
    assert _sites_perdus(arbre) == [2], f"st.{niveau} avalé par le rerun n'est pas vu"


def test_the_detector_does_not_fire_on_a_message_that_is_not_followed_by_a_rerun() -> None:
    """Le faux positif fabriqué (règle 20) : un message SANS rerun derrière est correct."""
    arbre = ast.parse("def f():\n    st.success('x')\n    return None\n")
    assert _sites_perdus(arbre) == [], "un message qui survit à son rendu est signalé à tort"
