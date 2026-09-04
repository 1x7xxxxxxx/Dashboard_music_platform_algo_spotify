"""Une figure de bienvenue dit toujours de QUI elle parle — R58.

Type: Test
Uses: welcome_figures (pur), views/onboarding (AST)
Depends on: src/dashboard/utils/welcome_figures.py,
    src/dashboard/views/onboarding.py
Persists in: nothing

Ce que R58 attendait, et ce qu'elle n'attendait pas
----------------------------------------------------
La tâche disait attendre « un locataire qui a des données, donc R1 ». C'était vrai
pour la moitié qui part par e-mail — le mot de bienvenue est envoyé à la VÉRIFICATION,
donc avant toute collecte, et `kaleido` est absent de toutes les images, donc une
figure Plotly ne s'exporte pas en PNG côté serveur. Ce sont deux raisons de garder les
exemples dans le mail, et aucune ne s'applique à l'app : elle rend Plotly nativement,
et cette page s'affiche aussi à un artiste qui REVIENT par le menu.

Prouver qu'une tâche est bloquée avant de la parquer : les deux tiers l'étaient, un
tiers ne l'était pas.

Le piège que la tâche nommait d'avance
---------------------------------------
« Un exemple doit continuer à s'annoncer. Le mélange est le vrai piège : une figure
réelle et une figure d'exemple côte à côte, sans que rien ne les distingue, est pire
que trois exemples. »

D'où le point unique de décision : `figure_source()` décide la courbe ET le libellé.
Ce fichier vérifie qu'on ne peut pas les séparer.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.dashboard.utils.welcome_figures import (
    MIN_POINTS, figure_source, tenant_daily_streams,
)

_ONB = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "views" / "onboarding.py"


# ── La décision ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n,expected", [
    (0, "example"),
    (1, "example"),
    (MIN_POINTS - 1, "example"),
    (MIN_POINTS, "tenant"),
    (MIN_POINTS + 50, "tenant"),
])
def test_a_series_too_short_stays_an_example(n, expected):
    """Deux points reliés suggèrent une tendance qui n'existe pas.

    Le seuil n'est pas cosmétique : l'exemple montre une VRAIE courbe, et le
    remplacer par trois points d'un compte neuf échange une promesse contre un
    graphique qui dit « il ne se passe rien ».
    """
    assert figure_source([(i, i) for i in range(n)]) == expected


def test_a_broken_read_falls_back_instead_of_raising():
    """Une page de bienvenue qui plante sur un SELECT coûte plus que trois exemples."""
    class _Boom:
        def fetch_query(self, *a, **k):
            raise RuntimeError("db down")

    assert tenant_daily_streams(_Boom(), 1) == []
    assert figure_source(tenant_daily_streams(_Boom(), 1)) == "example"


def test_no_tenant_no_query():
    assert tenant_daily_streams(None, 1) == []
    assert tenant_daily_streams(object(), None) == []


def test_the_query_carries_the_tenant_and_the_total_row_filter():
    """Deux règles transverses, sur la même requête.

    `WHERE artist_id = %s` (#8 / python.md) et, sur `s4a_song_timeline`, le filtre de
    la ligne « Total » des CSV S4A — sans lui la figure d'un artiste vaudrait le
    double de ses écoutes réelles.
    """
    src = (Path(__file__).resolve().parents[1] / "src" / "dashboard" / "utils"
           / "welcome_figures.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    sql = " ".join(n.value for n in ast.walk(tree)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and "s4a_song_timeline" in n.value)
    assert sql, "la requête a disparu"
    assert sql.count("artist_id = %s") >= 2, (
        "une des deux sources ne porte pas son locataire")
    assert "1x7xxxxxxx" in sql, (
        "le filtre de la ligne « Total » des CSV S4A a sauté — la figure "
        "afficherait le double des écoutes réelles")


# ── Le libellé ne peut pas diverger de la courbe ────────────────────────────

def _welcome_src() -> str:
    tree = ast.parse(_ONB.read_text(encoding="utf-8"))
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "_step_welcome")
    return ast.get_source_segment(_ONB.read_text(encoding="utf-8"), fn) or ""


def test_the_real_figure_and_its_label_share_one_branch():
    """Le libellé « Tes chiffres » et la courbe réelle sortent du MÊME `if`.

    C'est la seule forme qui rend le mélange impossible. Deux conditions séparées
    tiennent tant que personne ne touche à l'une des deux.
    """
    tree = ast.parse(_welcome_src())
    branches = [n for n in ast.walk(tree) if isinstance(n, ast.If)]
    holding = [
        n for n in branches
        if any(isinstance(c, ast.Constant) and c.value == "onboarding.figure_mine"
               for c in ast.walk(n))
        and any(isinstance(c, ast.Call) and getattr(c.func, "attr", "") == "line_chart"
                for c in ast.walk(n))
    ]
    assert holding, (
        "le libellé « Tes chiffres » et la courbe du locataire ne sont plus dans la "
        "même branche : rien n'empêche d'afficher l'un sans l'autre")

    # …et l'exemple est l'AUTRE branche du même `if`, pas un appel indépendant.
    assert any(any(isinstance(c, ast.Call)
                   and getattr(c.func, "id", "") == "_example_chart"
                   for c in ast.walk(ast.Module(body=n.orelse, type_ignores=[])))
               for n in holding), (
        "l'exemple n'est plus le repli de cette branche : les deux figures pourraient "
        "s'afficher ensemble, ou aucune")


def test_only_the_first_figure_can_be_real():
    """Les deux autres sont des promesses, pas des mesures.

    Une prédiction d'algorithme et un croisement Meta × Spotify n'existent pas avant
    d'avoir collecté ; une figure vide y dirait « ça ne marche pas » là où « voilà ce
    que tu auras » est la vérité.
    """
    src = _welcome_src()
    tree = ast.parse(src)
    conds = [n.test for n in ast.walk(tree) if isinstance(n, ast.If)]
    named = {c.value for cond in conds for c in ast.walk(cond)
             if isinstance(c, ast.Constant) and isinstance(c.value, str)
             and c.value.endswith(".png")}
    assert named == {"dashboard-global.png"}, (
        f"la substitution par les vraies données vise {named or 'aucune'} figure(s) — "
        "elle ne doit viser que la première")
