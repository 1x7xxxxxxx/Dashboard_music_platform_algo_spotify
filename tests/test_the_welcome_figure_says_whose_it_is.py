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


def test_the_figure_has_no_second_query_of_its_own():
    """Elle n'a plus de SQL : elle passe par le convertisseur de formes.

    Son ancienne requête additionnait `s4a_song_timeline.streams` — une quantité du
    JOUR — et `soundcloud_tracks_daily.playback_count` — un compteur CUMULÉ par titre —
    dans un même `UNION ALL`. Le total d'un jour valait donc les écoutes du jour plus le
    cumul de carrière de chaque titre SoundCloud. Inoffensif tant que l'appelant n'en
    lisait que le nombre de points ; c'était le SQL littéral que le catalogue d'erreurs
    cite comme origine de la classe, laissé public et invitant.

    Le garde suit les APPELS, pas le texte : une chaîne « platform_timeseries » dans un
    commentaire rendrait vert un module qui a repris son propre SQL.
    """
    src = (Path(__file__).resolve().parents[1] / "src" / "dashboard" / "utils"
           / "welcome_figures.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "tenant_daily_streams")
    called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert {"combined_daily_streams", "daily_streams_by_platform"} <= called, (
        f"la figure ne passe plus par platform_timeseries : {sorted(called)}")
    assert "fetch_query" not in called, (
        "la figure a repris un SQL à elle — c'est ainsi qu'une deuxième version d'un "
        "calcul apparaît, et qu'elle diverge")

    # Le DOCSTRING est retiré avant de chercher : il contient le mot « SELECT » en
    # expliquant pourquoi cette fonction ne lève pas, et le garde rougissait sur sa
    # propre explication. C'est la classe `a-textual-guard-is-blind` prise à l'envers —
    # un garde qui punit la documentation apprend à ne plus documenter.
    body = fn.body[1:] if ast.get_docstring(fn) else fn.body
    sql = [n.value for stmt in body for n in ast.walk(stmt)
           if isinstance(n, ast.Constant) and isinstance(n.value, str)
           and "SELECT" in n.value.upper() and "FROM" in n.value.upper()]
    assert not sql, f"du SQL est revenu dans la figure : {sql}"


# ── Le libellé ne peut pas diverger de la courbe ────────────────────────────

def _welcome_src() -> str:
    tree = ast.parse(_ONB.read_text(encoding="utf-8"))
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "_step_welcome")
    return ast.get_source_segment(_ONB.read_text(encoding="utf-8"), fn) or ""


# Les façons de DESSINER la courbe du locataire. Une liste, parce que le rendu a déjà
# changé une fois et qu'un garde ancré sur un seul nom rougit à chaque remplacement.
_RENDERERS = {"line_chart", "area_chart", "plotly_chart", "render_platform_chart"}


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
        # Le RENDU, quel qu'il soit — pas un nom d'appel gelé. Le 2026-09-08 la
        # figure est passée de `st.line_chart` (une courbe nue, sans couleurs de
        # plateforme ni distinction entre « zéro » et « pas mesuré ») à
        # `render_platform_chart`, et ce garde a rougi sur le CHANGEMENT au lieu du
        # défaut : il vérifiait le nom de la fonction, pas la question « le libellé
        # et la courbe sortent-ils du même `if` ».
        and any((isinstance(c, ast.Call)
                 and (getattr(c.func, "attr", "") in _RENDERERS
                      or getattr(c.func, "id", "") in _RENDERERS))
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
