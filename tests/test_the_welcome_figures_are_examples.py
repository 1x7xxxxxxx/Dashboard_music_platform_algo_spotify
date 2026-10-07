"""The welcome block's figures are generic examples, and the algo preview shows the same one (R374).

Type: Guard
Uses: src.dashboard.utils.example_figures, tests/render_harness.py (TENANT_SCRIPT)
Depends on: live Postgres for the render tests (skipped without it)
Persists in: a throwaway sandbox tenant, deleted after the module

V11 · V12 · V55 (owner's screen review, 2026-10-05). R347 had removed the figures from
« 1. streaMLytics en bref » because the first was drawn from the tenant's data. They come
back GENERIC: an overview, then the two promises (algo prediction, campaign) side by side,
same size, in that order — every one labelled « Exemple ». The algo preview, which had no
chart, shows the SAME prediction figure rather than a second illustration.
"""
from __future__ import annotations

import ast
import os
import uuid
from pathlib import Path

import pytest

from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT

_ROOT = Path(__file__).resolve().parents[1]
_ONB = _ROOT / "src" / "dashboard" / "views" / "onboarding.py"


def test_the_three_figures_are_generated_at_the_same_height() -> None:
    """R435: the three sit side by side (owner, 2026-10-07: « de la même taille »)."""
    from PIL import Image

    from src.dashboard.utils.example_figures import EXAMPLES_DIR, OVERVIEW, PROMISES

    ratios = [h / w for w, h in (Image.open(EXAMPLES_DIR / n).size
                                 for n in (OVERVIEW, *PROMISES))]
    assert max(ratios) - min(ratios) < 0.01, (
        f"the three figures sit side by side at different heights: {ratios} — "
        "regenerate with `make example-charts`")


def test_the_preview_row_is_generated_at_one_height() -> None:
    """R456: the algo preview sets its three figures side by side too."""
    from PIL import Image

    from src.dashboard.utils.example_figures import ALGO_PREVIEW, EXAMPLES_DIR

    ratios = [h / w for w, h in (Image.open(EXAMPLES_DIR / n).size for n in ALGO_PREVIEW)]
    assert max(ratios) - min(ratios) < 0.01, (
        f"the preview figures sit side by side at different heights: {ratios} — "
        "regenerate with `make example-charts`")


def test_the_three_figures_share_one_row_of_equal_columns() -> None:
    """R435: « sur chaque colonne, une, deux, trois, équidistant »."""
    fn = next(n for n in ast.walk(ast.parse(_ONB.read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "_step_welcome")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    cols = [c for c in calls if getattr(c.func, "attr", "") == "columns"
            and c.args and getattr(c.args[0], "value", None) == 3]
    assert cols, "the three figures are no longer one row of three equal columns"
    examples = [c for c in calls if getattr(c.func, "id", "") == "render_example"]
    assert len(examples) == 1, (
        f"{len(examples)} render_example calls — one, in the loop over the three columns")


def test_the_welcome_step_reads_no_tenant_series() -> None:
    """A figure drawn from the tenant's data is what R347 removed; it must not return."""
    names = {n.id for n in ast.walk(ast.parse(_ONB.read_text(encoding="utf-8")))
             if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(ast.parse(_ONB.read_text(encoding="utf-8")))
              if isinstance(n, ast.Attribute)}
    back = names & {"render_platform_chart", "_tenant_series", "plotly_chart"}
    assert not back, f"onboarding draws tenant data again: {back}"


@pytest.fixture(scope="module")
def empty_tenant():
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    slug = f"examples-{uuid.uuid4().hex[:10]}"
    artist_id = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active, is_sandbox) "
        "VALUES (%s, %s, 'free', TRUE, TRUE) RETURNING id", (f"Examples {slug}", slug),
    )[0][0]
    db.close()
    yield artist_id
    db = get_db_connection()
    db.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s", (artist_id,))
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
    db.close()


def _images(view: str, artist_id: int) -> list[tuple[str, str]]:
    """(caption, media url) of every image the view renders. The url is a content hash."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view=view,
                                                  artist_id=artist_id))
    at.run(timeout=120)
    assert not at.exception, f"{view} raised: {at.exception}"
    return [(img.caption, img.url) for el in at.get("image") for img in el.proto.imgs]


@pytest.mark.skipif(not db_ready(), reason="renders the welcome step against the live DB")
def test_an_empty_tenant_sees_three_example_figures(empty_tenant) -> None:
    images = _images("onboarding", empty_tenant)
    assert len(images) == 3, f"expected overview + two promises, got {len(images)}"
    unlabelled = [url for caption, url in images if "Exemple" not in caption]
    assert not unlabelled, f"an example figure does not say it is one: {unlabelled}"
    assert len({url for _c, url in images}) == 3, "the same figure is shown twice"


@pytest.mark.skipif(not db_ready(), reason="renders the algo preview against the live DB")
def test_the_algo_preview_shows_the_welcome_figures_then_shap(empty_tenant) -> None:
    """R456 (C8, C10): the two welcome promises, then the SHAP overview — all examples."""
    welcome = _images("onboarding", empty_tenant)
    preview = _images("algo_preview", empty_tenant)
    assert len(preview) == 3 and all("Exemple" in c for c, _u in preview), preview
    assert [u for _c, u in preview[:2]] == [u for _c, u in welcome[1:]], (
        "the algo preview shows other figures than the welcome step's two promises")
    assert len({u for _c, u in preview}) == 3, "the SHAP overview repeats a promise"
