"""R569 — the cross view draws each datum once, and shows no table.

Type: Guard
Uses: tools/dev/charts_dossier/cross_view.py (walk, load_registry, duplicates)
Depends on: tools/dev/charts_dossier/cross_view.yaml, src/dashboard/views/meta_ads_overview.py
Persists in: nothing (no database)

Owner, 2026-10-15: « une donnée = un graphique », no table, the chart alone. R567 and
R568 removed what a reading found (R569 three more: the hooks fold, the CPR and spend
frames of the creative ranking, the CPR line by country). This keeps them removed:

- every figure reachable from the five sections is declared, and every declaration is
  reachable — the registry can neither miss a figure nor describe a gone one;
- no (dimension · metric) pair is drawn by two figures that render together;
- no `st.dataframe` / `st.table` / `st.data_editor` / markdown table is reachable.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dev" / "charts_dossier"))

import cross_view  # noqa: E402

WALK = cross_view.walk()
REGISTRY = cross_view.load_registry()


def test_the_walk_reaches_every_section() -> None:
    from src.dashboard.views.meta_ads_overview import SECTIONS
    assert set(cross_view.SECTION_FUNCS) == set(SECTIONS)
    for key, section in SECTIONS.items():
        assert section.render.__name__ == cross_view.SECTION_FUNCS[key], key
    assert set(WALK.figures.values()) == set(SECTIONS), (
        "a section with no figure found — the walk lost its trail")


def test_every_reachable_figure_is_declared() -> None:
    missing = sorted(set(WALK.figures) - set(REGISTRY))
    assert not missing, (
        f"figures with no declaration in cross_view.yaml: {missing} — name what each one "
        "draws as « dimension · metric », so a second chart of the same datum is caught")


def test_no_declaration_describes_a_gone_figure() -> None:
    stale = sorted(set(REGISTRY) - set(WALK.figures))
    assert not stale, f"cross_view.yaml describes figures no section reaches: {stale}"


def test_no_datum_is_drawn_twice() -> None:
    dup = cross_view.duplicates(REGISTRY)
    assert not dup, ("one datum, two charts — keep the one that answers its section's "
                     "question, move the other to a hover or remove it:\n" + "\n".join(dup))


def test_instead_of_names_a_declared_site() -> None:
    for site, entry in REGISTRY.items():
        if entry.get("instead_of"):
            assert entry["instead_of"] in REGISTRY, site


def test_the_cross_view_shows_no_table() -> None:
    assert not WALK.tables, f"a table in the cross view: {WALK.tables}"


def test_the_detectors_see_what_they_are_written_for() -> None:
    """Planted: a duplicate, its `instead_of` pardon, and a markdown table."""
    reg = {"a": {"draws": ["pays · CPR"]}, "b": {"draws": ["pays · CPR", "jour · x"]}}
    assert len(cross_view.duplicates(reg)) == 1
    reg["b"]["instead_of"] = "a"
    assert cross_view.duplicates(reg) == []
    call = ast.parse('st.markdown("| a | b |\\n|---|---|\\n| 1 | 2 |")').body[0].value
    assert cross_view._md_table(call)
    assert not cross_view._md_table(ast.parse('st.markdown("a --- b")').body[0].value)
