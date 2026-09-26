"""Un filtre dont le défaut ne sélectionne qu'une partie cache une partie du corps.

Type: Test
Uses: ast, streamlit.testing.v1.AppTest, live Postgres (spotify_etl)
Depends on: src/dashboard/views/**/*.py, tests/render_harness.py
Persists in: nothing

Trouvé le 2026-09-17 en triant `object-dtype-numeric-op`, et c'est le garde DÉCLARÉ de
cette classe qui s'est révélé aveugle.

`meta_ads_overview.py:137` pose `default_main = all_campaigns[:1]` : une seule campagne
est sélectionnée à l'ouverture. Le tableau des taux, lui, vit derrière
`if len(df_perf) > 1` (:284). **Aucun rendu de la suite n'a jamais exécuté ce bloc** —
`test_views_render_smoke.py` rend chaque vue dans son état de filtre PAR DÉFAUT, et
s'arrête là.

Mesuré le 2026-09-17, les deux moitiés :

  · en retirant la conversion `pd.to_numeric` de `meta_ads_overview.py:190`,
    `test_views_render_smoke.py::[meta_ads_overview]` reste **VERT** ;
  · le même arbre, la même vue, avec les 21 campagnes sélectionnées au lieu d'une :
    `TypeError: Expected numeric dtype, got object instead.`

`SUM(bigint)` rend `numeric` en PostgreSQL, que psycopg2 rend en `Decimal`, que pandas
range en dtype `object` — donc `.round()` lève. La conversion de :190 est ce qui tient
la page, et rien ne gardait cette conversion.

⚠️ C'est la forme exacte de « le produit cartésien des menus » : 4 737 tests verts et une
vue vide trouvée par l'artiste en une heure. Un état de filtre non-défaut est un état que
l'utilisateur atteint en UN clic et que la suite n'atteint jamais.

Ce que ce garde fait, et pourquoi il ne s'énumère pas
-----------------------------------------------------
Il DÉRIVE sa population : toute `st.multiselect` dont le `default` n'est pas
textuellement ses `options`. Une vue neuve avec un filtre partiel y entre sans qu'on y
pense — une liste écrite à la main aurait figé les cinq d'aujourd'hui.

Ce qu'il ne couvre PAS
----------------------
Les autres widgets de filtrage : `selectbox`, `radio`, `slider`, `date_input`, les
onglets. Un bloc caché derrière un `selectbox` non-défaut reste invisible à toute la
suite. Élargir demanderait de choisir une valeur par widget, ce qui n'est pas dérivable
— c'est un trou DÉCLARÉ, pas un oubli.

Mutation record — 2026-09-17 : avec `pd.to_numeric` retiré de
`meta_ads_overview.py:190`, ce garde échoue sur `meta_ads_overview` (et
`test_views_render_smoke.py` reste vert). Rétabli, il passe.

---
rex: []
---
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from tests.db_gate import db_ready as _db_ready
from tests.render_harness import SCRIPT, VIEWS

_ROOT = Path(__file__).resolve().parents[1]
_VIEWS_DIR = _ROOT / "src" / "dashboard" / "views"

_needs_db = pytest.mark.skipif(
    not _db_ready(),
    reason="No provisioned Postgres on 127.0.0.1:5433 — a widened render needs real rows",
)


def _views_with_a_partial_default() -> list[str]:
    """Les vues portant une `st.multiselect` dont le défaut n'est pas toutes ses options.

    Dérivé, jamais énuméré. Un `default` absent ne compte pas : la sélection est alors
    vide, et le code applique son filtre « aucun » — c'est-à-dire tout.
    """
    found: set[str] = set()
    for path in sorted(_VIEWS_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            partial = has_a_partial_default(path.read_text(encoding="utf-8"))
        except SyntaxError:                              # pragma: no cover
            continue
        if partial:
            # Le module de la vue est celui de son fichier de premier niveau : c'est
            # ce que `SCRIPT` sait importer. Un sous-paquet est signalé, pas ignoré.
            rel = path.relative_to(_VIEWS_DIR)
            found.add(rel.parts[0].removesuffix(".py"))
    return sorted(found)


def has_a_partial_default(source: str) -> bool:
    """Does `source` carry a `st.multiselect` whose default is not all its options?"""
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "attr", "") == "multiselect"):
            continue
        kw = {k.arg: ast.get_source_segment(source, k.value) for k in node.keywords}
        default, options = kw.get("default"), kw.get("options")
        if default is None:
            continue
        if options is not None and options.strip() == default.strip():
            continue
        return True
    return False


def widen_every_filter(at) -> int:
    """Select every option of every multiselect; how many were actually widened."""
    widened = 0
    for widget in at.multiselect:
        options = list(widget.options)
        if len(options) > len(widget.value):
            widget.set_value(options)
            widened += 1
    return widened


@_needs_db
def test_the_population_is_not_empty() -> None:
    """Anti-vacuité : sans vue à rendre, tout ce fichier est vert sur rien."""
    views = _views_with_a_partial_default()
    assert views, (
        "aucune `st.multiselect` à défaut partiel trouvée dans `src/dashboard/views/`. "
        "Il y en avait 5 le 2026-09-17 — le lecteur AST est cassé, ou l'argument "
        "`default` a changé de nom.")
    unknown = [v for v in views if v not in VIEWS]
    assert not unknown, (
        f"{unknown} portent un filtre partiel mais ne sont pas des vues rendables "
        "(`tests/render_harness.VIEWS`). Ce garde ne peut pas les atteindre : soit les "
        "ajouter à la liste rendue, soit rendre le module parent qui les appelle.")


@_needs_db
@pytest.mark.parametrize("view", _views_with_a_partial_default())
def test_widening_every_filter_does_not_raise(view: str) -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(SCRIPT.format(root=os.getcwd(), view=view))
    at.run(timeout=120)
    if at.exception:                                     # pragma: no cover
        detail = getattr(at.exception[0], "value", at.exception[0])
        pytest.fail(f"{view} lève déjà dans son état par DÉFAUT : {detail}")

    widened = widen_every_filter(at)
    if not widened:
        pytest.skip(
            f"{view}: aucun filtre à élargir sur cette base — le défaut porte déjà "
            "toutes les options. Le bloc gardé n'existe pas ici avec ces données.")

    at.run(timeout=120)
    if at.exception:
        detail = getattr(at.exception[0], "value", at.exception[0])
        pytest.fail(
            f"{view}.show() lève quand on élargit son filtre ({widened} widget(s)) "
            f"alors qu'il rend bien avec le défaut : {type(detail).__name__}: {detail}\n"
            "Un état atteint en un clic, qu'aucun autre test de rendu n'atteint.")


_HIDDEN_BODY = """
import pandas as pd
import streamlit as st
chosen = st.multiselect("Plateformes", ["spotify", "apple"], default=["spotify"])
st.write("ok")
if "apple" in chosen:                       # the block only a widened filter reaches
    col = pd.Series(["12", "30"], dtype=object)
    st.metric("Écoutes", col.sum() / 2)     # object dtype: "1230" / 2 -> TypeError
"""


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity, without a database: a body that only a widened filter reaches, and
    that raises there (the object-dtype division of 2026-09-17), renders fine by
    default and raises once `widen_every_filter` has run; the partial default is
    detected by the same reader that selects the real views."""
    from streamlit.testing.v1 import AppTest

    assert has_a_partial_default(_HIDDEN_BODY)
    assert not has_a_partial_default(
        'st.multiselect("x", options=opts, default=opts)\n')
    at = AppTest.from_string(_HIDDEN_BODY)
    at.run(timeout=30)
    assert not at.exception, "the default state must render — the defect is hidden"
    assert widen_every_filter(at) == 1
    at.run(timeout=30)
    assert at.exception, "the widened render must reach the hidden body and raise"
