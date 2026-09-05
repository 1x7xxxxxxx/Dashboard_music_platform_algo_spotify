"""L'état montré dans un onglet est CELUI de la matrice, pas une seconde opinion.

Type: Test
Uses: status_matrix (AST + fonctions pures), credentials/_render
Depends on: src/dashboard/utils/status_matrix.py,
    src/dashboard/views/credentials/_render.py
Persists in: nothing

Ce que remplacent les pastilles
--------------------------------
« Valeur enregistrée le 05/09/2026 03:49 — enregistrée ne veut pas dire vérifiée :
c'est le test ci-dessous qui le dit. » La phrase disait la bonne chose et la disait
mal : une ligne de prose pour une nuance que la couleur montre, répétée sous chaque
onglet. Demandé le 2026-09-05 : « mets uniquement des états vert orange rouge très
petit que pour l'onglet sélectionné, copié de l'onglet état de tes plateformes ».

« Copié de » au pied de la lettre
----------------------------------
Le risque de cette demande est d'en écrire une deuxième version. Deux surfaces qui
décrivent le même état avec deux codes couleur produisent un désaccord qu'AUCUNE des
deux ne peut voir — le dépôt l'a payé sur la fraîcheur, sur les compteurs publics, et
sur la durée de mise en route. Ce fichier vérifie que ce sont les MÊMES fonctions.
"""
from __future__ import annotations

import ast
import re as _re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_MATRIX = _ROOT / "src" / "dashboard" / "utils" / "status_matrix.py"
_RENDER = _ROOT / "src" / "dashboard" / "views" / "credentials" / "_render.py"


def _fn(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(f for f in ast.walk(tree)
                if isinstance(f, ast.FunctionDef) and f.name == name)


def test_the_tab_state_reuses_the_matrix_cells():
    """`_box` et `_responds_cell`, pas des jumelles."""
    fn = _fn(_MATRIX, "render_platform_state")
    called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(fn) if isinstance(n, ast.Call)}
    for helper in ("_box", "_responds_cell", "_shape_cell", "artist_readiness"):
        assert helper in called, (
            f"`render_platform_state` n'appelle plus `{helper}` : il porterait sa "
            "propre idée de l'état, et deux surfaces diraient deux choses du même "
            "fait sans qu'aucune puisse le voir")


def test_the_colours_are_defined_once():
    """Un seul jeu de couleurs dans le dépôt pour cet état."""
    src = _MATRIX.read_text(encoding="utf-8")
    tree = ast.parse(src)
    # `_GREEN, _RED, _GREY, _AMBER = …` est une affectation par TUPLE : la cible
    # n'est pas un `Name` mais un `Tuple` de `Name`. Chercher `_GREEN` parmi les
    # cibles directes rendait 0 — un garde qui compte zéro et exige un est rouge sur
    # du code juste, ce qui est la façon la plus rapide de se faire désarmer.
    palettes = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and any(getattr(x, "id", "") == "_GREEN"
                        for t in n.targets for x in ast.walk(t))]
    assert len(palettes) == 1, (
        "la palette est définie plusieurs fois : deux verts qui divergent d'un ton "
        "sont deux verdicts qui divergent")

    # Les CHAÎNES de l'arbre, pas le texte : le cliquet
    # `test_a_guard_reads_structure_not_text` a refusé la version textuelle — pour la
    # cinquième fois de la journée, et il a raison : un code couleur cité dans un
    # commentaire (« la matrice utilise #28a745 ») rendrait ce garde rouge sur du code
    # juste.
    literals = {n.value for n in ast.walk(ast.parse(_RENDER.read_text(encoding="utf-8")))
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    # Un vrai code hexadécimal, pas « ### » : la première version comptait la
    # longueur et le `#` initial, et accusait un titre markdown. Un prédicat qui
    # hurle sur ce qu'il ne vise pas se fait désarmer — troisième fois de la journée.
    hard = {x for x in literals
            if _re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", x)}
    assert not hard, (
        f"la page de saisie code des couleurs en dur ({sorted(hard)}) au lieu de "
        "passer par la matrice")


def test_the_tab_shows_the_state_and_not_the_sentence():
    """La phrase est partie ; l'état la remplace, dans le même onglet."""
    fn = _fn(_RENDER, "_render_platform_tab")
    called = {getattr(n.func, "id", "") for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "render_platform_state" in called, (
        "l'onglet ne montre plus l'état de sa plateforme")

    literals = [n.value for n in ast.walk(fn)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not any("ne veut pas dire vérifiée" in x for x in literals), (
        "la phrase est revenue : elle explique en prose ce que la couleur montre")


def test_it_shows_only_the_platforms_of_that_tab():
    """Un onglet peut porter DEUX lignes — Meta et Instagram — et c'est voulu.

    Elles se saisissent au même endroit et échouent séparément : Instagram peut être
    muet pendant que Meta Ads répond. Filtrer sur la clé d'onglet, et non sur la clé
    logique, est donc obligatoire — c'est la traduction qui a déjà produit deux
    défauts dans ce dépôt quand on l'a oubliée d'un côté.
    """
    fn = _fn(_MATRIX, "render_platform_state")
    called = {getattr(n.func, "id", "") for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "platform_destination" in called, (
        "le filtre ne passe plus par `platform_destination` : un onglet montrerait "
        "l'état d'une plateforme qui ne s'y saisit pas, ou raterait Instagram")


def test_a_broken_read_shows_nothing_instead_of_raising():
    """Décoratif : une pastille absente ne doit jamais fermer la page de saisie."""
    class _Boom:
        def fetch_df(self, *a, **k):
            raise RuntimeError("db down")

        def fetch_query(self, *a, **k):
            raise RuntimeError("db down")

    from src.dashboard.utils.status_matrix import render_platform_state

    render_platform_state(_Boom(), 1, "spotify")     # ne doit pas lever
