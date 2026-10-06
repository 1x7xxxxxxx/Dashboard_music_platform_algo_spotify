"""The home page stops at the numbers; the four blocks it shed each live somewhere (R373).

Type: Guard
Uses: tests/render_harness.py (TENANT_SCRIPT), tests/db_gate.py
Persists in: nothing

V6 (owner's screen review, 2026-10-05): « Ce que ta publicité a appris », the PDF button,
« Statut des pipelines » and « Ce qui alimente tes chiffres » left the home page. A
removal is only half of the change: the freshness grid had NO other artist-facing home
(Alertes, which reads the same freshness, is admin-only), so deleting it would have
taken information away rather than moving it. Each block is therefore checked twice —
gone from home, present where it went.

  freshness grid → Santé onboarding (`utils/source_freshness.py`, artist view)
  Meta advice    → Publicité Meta Ads, until the cross view (R378) takes it
  DAG status     → Monitoring ETL (`airflow_kpi`, admin) — already there
  PDF button     → the « Rapport PDF » menu entry — already there
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT

_ROOT = Path(__file__).resolve().parents[1]
_VIEWS = _ROOT / "src" / "dashboard" / "views"

_GONE = ("Ce que ta publicité a appris", "Statut des pipelines",
         "Ce qui alimente tes chiffres", "Générer mon rapport PDF")


def _calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.func.id if isinstance(n.func, ast.Name) else n.func.attr
            for n in ast.walk(tree) if isinstance(n, ast.Call)
            and isinstance(n.func, (ast.Name, ast.Attribute))}


def test_the_home_module_no_longer_calls_the_four_blocks() -> None:
    called = _calls(_VIEWS / "home.py")
    for name in ("render_meta_advice", "render_source_freshness", "get_dag_list",
                 "bouton_vers"):
        assert name not in called, f"home.py calls {name} again — V6 took it off the home"


def test_each_shed_block_is_called_by_its_destination() -> None:
    assert "render_source_freshness" in _calls(_VIEWS / "onboarding_health.py")
    assert "render_meta_advice" in _calls(_VIEWS / "meta_ads_overview.py")
    assert "get_dag_list" in _calls(_VIEWS / "airflow_kpi.py")
    from src.dashboard.utils.nav_sections import NAV_SECTIONS

    keys = {key for *_head, entries in NAV_SECTIONS for _label, key in entries}
    assert "export_pdf" in keys, "the PDF report lost its menu entry"


def _render(view: str):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(TENANT_SCRIPT.format(root=str(_ROOT), view=view, artist_id=1))
    at.run(timeout=120)
    assert not at.exception, f"{view} raised: {at.exception}"
    texts = [e.value for kind in ("subheader", "markdown", "caption", "button")
             for e in at.get(kind) if isinstance(getattr(e, "value", None), str)]
    texts += [b.label for b in at.button]
    return " ".join(texts)


@pytest.mark.skipif(not db_ready(), reason="renders the home page against the live DB")
def test_the_rendered_home_shows_none_of_the_four_titles() -> None:
    page = _render("home")
    shown = [title for title in _GONE if title in page]
    assert not shown, f"the home page still renders {shown}"


@pytest.mark.skipif(not db_ready(), reason="renders Santé onboarding against the live DB")
def test_the_freshness_grid_renders_on_sante_onboarding_for_the_artist() -> None:
    assert "Ce qui alimente tes chiffres" in _render("onboarding_health")
