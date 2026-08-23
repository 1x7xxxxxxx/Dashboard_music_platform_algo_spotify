"""Pressing the buttons on the two views nothing else presses.

Installed 2026-08-21, as the stated prerequisite to roadmap item R9's last two
views. `admin.py` and `hypeddit.py` each open five connections per render, and
those connections live inside button handlers — `admin` carries GDPR erasure and
token rotation, `hypeddit` writes campaign stats from a form callback.

`test_views_render_smoke` renders `show()` and presses nothing, so every one of
those handlers is invisible to it: it would stay green on a button that raises.
Refactoring a GDPR erasure path with only that behind it is not a change worth
shipping — so this comes first.

What it asserts, beyond "does not raise":

  * clicking `🗑️ Lancer l'effacement` with an **empty reason** must erase nothing
    and say why. The flow is two-step by design (reason → a second explicit
    confirmation button), and that design is worth pinning: it is the only thing
    between a mis-click and an irreversible deletion.
  * every button renders and survives a click against a schema-complete database.

These run against whatever `DATABASE_URL` points at, which for local runs is a
throwaway container. Nothing here targets production.
"""
from __future__ import annotations

import os

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()

_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "admin"
st.session_state["artist_id"] = 1
st.session_state["user_id"] = 1
st.session_state["email"] = "admin@test"
st.session_state["username"] = "admin"
st.session_state["authenticated"] = True
from src.dashboard.views.{view} import show
show()
"""


@pytest.fixture(autouse=True)
def _stub_verification_send(monkeypatch):
    """`📧 Renvoyer vérification` (admin.py:685) really sends.

    This test presses EVERY button, and that one calls `send_verification_email` with
    an address read from the database the run points at — locally, the migrated copy of
    production. Until 2026-08-23 it delivered real mail to real people on every suite
    run, carrying a `http://localhost:8501` link because no local process sets
    APP_BASE_URL. Pressing a button must exercise the handler, not the relay.

    Patched on the module the handler imports from, because `_resend_verification`
    imports the symbol INSIDE the function — there is no module-level name on
    `views.admin` to patch.
    """
    import src.utils.verification_email as ve

    monkeypatch.setattr(ve, "send_verification_email", lambda *a, **k: True)


def _app(view: str):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT.format(root=os.getcwd(), view=view))
    at.run(timeout=120)
    return at


# AppTest cannot re-run a page that renders a single-mode `st.segmented_control`:
# `streamlit/testing/v1/element_tree.py` iterates the widget's scalar value as if it
# were a sequence of options, so `format_func` receives one character and raises.
# That is the harness, not the app — the failing frame is inside
# `streamlit/testing/`, which the runtime never enters. `smart_period_filter` uses
# exactly that widget, so any view carrying it cannot be click-driven here.
# Recorded rather than swallowed: the skip names the file, so the day AppTest fixes
# it, these tests start covering more without anyone editing them.
_HARNESS_FRAME = "streamlit/testing/v1/element_tree.py"


def _harness_limitation(exc: BaseException) -> bool:
    """Did this come out of AppTest's own machinery rather than the app?

    The exception propagates out of `.run()` itself — it is never captured into
    `at.exception` — so it has to be caught around the click and classified by
    where its traceback lives.
    """
    import traceback
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return _HARNESS_FRAME in tb.replace("\\", "/")


def _no_exception(at, view: str, when: str):
    if at.exception:
        ex = at.exception[0]
        detail = getattr(ex, "value", ex)
        pytest.fail(f"{view} raised {type(detail).__name__} {when}: {detail}")


def _click(at, index: int, view: str, label: str):
    """Click, and tell a harness limitation apart from a broken button."""
    try:
        at.button[index].click().run(timeout=120)
    except Exception as exc:  # noqa: BLE001 — classified immediately below
        if _harness_limitation(exc):
            pytest.skip(
                f"{view}: AppTest cannot re-run a single-mode segmented_control "
                f"({_HARNESS_FRAME}) — harness limitation, not the view"
            )
        pytest.fail(f"{view} raised {type(exc).__name__} clicking {label!r}: {exc}")


def _labels(at) -> list[str]:
    return [(getattr(b, "label", "") or "").strip() for b in (at.button or [])]


@pytest.mark.parametrize("view", ["admin", "hypeddit"])
def test_the_view_renders_and_exposes_buttons(view):
    at = _app(view)
    _no_exception(at, view, "on first render")
    assert at.button, (
        f"{view} rendered no button — either the session fixture is wrong or the "
        "view changed shape, and every click test below became vacuous."
    )


@pytest.mark.parametrize("view", ["admin", "hypeddit"])
def test_every_button_survives_a_click(view):
    """One fresh render per click, so no button inherits another's session state."""
    labels = _labels(_app(view))
    assert labels, f"{view}: nothing to click"

    for i, label in enumerate(labels):
        at = _app(view)
        _no_exception(at, view, f"before clicking {label!r}")
        if i >= len(at.button):
            continue  # the render is not deterministic in count — skip, do not fail
        _click(at, i, view, label)
        _no_exception(at, view, f"after clicking {label!r} (index {i})")


def test_gdpr_erasure_refuses_without_a_reason():
    """The only thing between a mis-click and an irreversible deletion.

    Clicking the erasure button with an empty reason must not delete, and must
    say what is missing. The second confirmation button is a separate step and is
    deliberately not pressed here.
    """
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    try:
        before = db.fetch_query("SELECT count(*) FROM saas_artists")[0][0]
    finally:
        db.close()

    at = _app("admin")
    _no_exception(at, "admin", "on first render")

    erase = [b for b in at.button
             if "effacement" in (getattr(b, "label", "") or "").lower()]
    if not erase:
        pytest.skip("no artist to erase in this database — the GDPR tab renders nothing")

    idx = next(i for i, lbl in enumerate(_labels(at)) if "effacement" in lbl.lower())
    _click(at, idx, "admin", "🗑️ Lancer l'effacement")
    _no_exception(at, "admin", "after clicking erase with no reason")

    db = get_db_connection()
    try:
        after = db.fetch_query("SELECT count(*) FROM saas_artists")[0][0]
    finally:
        db.close()

    assert after == before, (
        f"saas_artists went from {before} to {after} rows after clicking the "
        "erasure button with an EMPTY reason. The two-step guard is gone."
    )
    said_so = any("motif" in (getattr(e, "value", "") or "").lower()
                  for e in (at.error or []))
    assert said_so, (
        "nothing erased — but the view did not say the reason is required either, "
        "so the admin sees a button that silently does nothing."
    )
