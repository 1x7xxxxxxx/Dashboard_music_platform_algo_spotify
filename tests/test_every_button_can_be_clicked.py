"""R271 (owner note L164 : « valider tous les boutons de l'app ») — every button of every
view is clicked once, and the page it leads to renders without an exception.

Type: Test
Uses: tests/render_harness.py (SCRIPT, VIEWS) — an admin session on the development base

The render smoke test proved each view DRAWS; a button's branch only runs when it is
pressed, so a crash behind a click was invisible to it. Each button is pressed on a FRESH
render (a click can change the session a second click would read), then the view re-runs.

Bounded: `_MAX_PER_VIEW` buttons per view — the rest are named in the failure message if
the bound ever hides one, never silently skipped.

Mutation record (2026-09-28) : a `raise` put behind the recap page's button → red.
"""
from __future__ import annotations

import os

import pytest

from tests.render_harness import SCRIPT, VIEWS

pytest.importorskip("streamlit.testing.v1")

# 20, not 12 (2026-09-28): on the CI base the home page draws 15 buttons — every setup
# step pending, plus « Y aller → » per platform — where the local base draws fewer.
_MAX_PER_VIEW = 20


def _db_up() -> bool:
    try:
        from src.database.postgres_handler import PostgresHandler
        db = PostgresHandler.from_env_or_config()
        db.close()
        return True
    except Exception:      # noqa: BLE001 — no base, the render tests skip the same way
        return False


def _app(view: str):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(SCRIPT.format(root=os.getcwd(), view=view))
    at.run(timeout=180)
    return at


@pytest.fixture()
def offline(monkeypatch):
    """A click on « Vérifier maintenant » calls Meta, Google, SoundCloud… The transport is
    stubbed to refuse: the click then walks the view's OFFLINE path — which must not
    crash either — and nothing leaves this machine (the HTTP boundary of conftest)."""
    import requests

    def refuse(self, request, **kwargs):
        raise requests.exceptions.ConnectionError("offline in test (R271)")
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", refuse)


@pytest.mark.xdist_group("buttons")
@pytest.mark.parametrize("view", VIEWS)
def test_every_button_of_the_view_can_be_clicked(view, offline):
    if not _db_up():
        pytest.skip("no development base (localhost:5433) — `make up`")
    first = _app(view)
    if first.exception:
        pytest.skip(f"{view} does not render — test_views_render_smoke owns that")
    labels = [b.label for b in first.button]
    broken = []
    for i, label in enumerate(labels[:_MAX_PER_VIEW]):
        at = _app(view)
        if i >= len(at.button) or at.button[i].disabled:
            continue      # fewer buttons this run, or disabled — a person cannot press it
        at.button[i].click().run(timeout=180)
        if at.exception:
            ex = at.exception[0]
            broken.append(f"« {label} » → {getattr(ex, 'value', ex)}"[:200])
    assert not broken, f"{view} : {broken}"
    assert len(labels) <= _MAX_PER_VIEW, (
        f"{view} draws {len(labels)} buttons, only {_MAX_PER_VIEW} were clicked: "
        f"{labels[_MAX_PER_VIEW:]} — raise the bound")


def test_the_click_harness_sees_buttons_not_vacuous(offline):
    """The recap page draws one button per chart: a harness that sees none clicks nothing."""
    if not _db_up():
        pytest.skip("no development base (localhost:5433) — `make up`")
    at = _app("recap")
    assert not at.exception and len(at.button) >= 5
    assert len(at.button) <= _MAX_PER_VIEW, "the bound would already cut the recap"
