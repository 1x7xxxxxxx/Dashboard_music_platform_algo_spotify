"""Billing: Free and Premium side by side, the inactive one struck, the active one marked (R391).

Type: Guard
Uses: src.dashboard.views.billing, src.dashboard.utils.nav_sections
Depends on: live Postgres for the render (skipped without)
Persists in: nothing

V84-V86 (owner's screen review, 2026-10-05): the menu reads « 💳 Facturation /
Abonnement »; the page opens on the two plans side by side — the one not subscribed
struck through, the running one marked by a green arrow, price and status under each —
then the « Faire piloter mes campagnes » button, then « Nos offres ».
"""
from __future__ import annotations

import os

import pytest

from tests.db_gate import db_ready

_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "artist"
st.session_state["artist_id"] = 1
st.session_state["email"] = "artist@test"
st.session_state["authenticated"] = True
import src.dashboard.views.billing as v
_original = v.get_artist_plan
v.get_artist_plan = lambda: {plan!r}
try:
    v.show()
finally:
    v.get_artist_plan = _original
"""


def test_the_card_header_strikes_the_inactive_plan_and_marks_the_active_one() -> None:
    from src.dashboard.views.billing import card_header

    assert card_header("💎 Premium", False) == "### ~~💎 Premium~~"
    active = card_header("🆓 Free", True)
    assert "~~" not in active and ":green[" in active and "🆓 Free" in active


def test_the_menu_names_billing_and_subscription() -> None:
    from src.dashboard.utils.nav_sections import page_label

    assert page_label("billing") == "💳 Facturation / Abonnement"


def _render(plan: str):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT.format(root=os.getcwd(), plan=plan))
    at.run(timeout=90)
    assert not at.exception, at.exception
    return at


@pytest.mark.skipif(not db_ready(), reason="renders the billing page against the live DB")
@pytest.mark.parametrize(("plan", "struck", "marked"), [
    ("free", "💎 Premium", "🆓 Free"),
    ("premium", "🆓 Free", "💎 Premium"),
])
def test_the_right_card_is_struck(plan: str, struck: str, marked: str) -> None:
    at = _render(plan)
    heads = [m.value for m in at.markdown if m.value.startswith("### ")]
    assert f"### ~~{struck}~~" in heads[:2], f"the inactive plan is not struck: {heads}"
    assert any(marked in h and ":green[" in h for h in heads[:2]), (
        f"the active plan is not marked by the green arrow: {heads}")
    assert at.caption[0].value != "", "no status under the cards"


@pytest.mark.skipif(not db_ready(), reason="renders the billing page against the live DB")
def test_the_service_button_sits_between_the_plans_and_the_offers() -> None:
    at = _render("free")
    service = next(i for i, b in enumerate(at.button)
                   if "Faire piloter mes campagnes" in b.label)
    assert service == 0, [b.label for b in at.button]
    offers = [s.value for s in at.subheader]
    assert offers and offers[0] == "Nos offres", offers
    first_card = next(m for m in at.markdown if m.value.startswith("### "))
    tree = [n for n in _walk(at._tree)]
    assert (tree.index(first_card) < tree.index(at.button[service])
            < tree.index(at.subheader[0])), "the order is not plans → button → offers"


def _walk(node):
    for c in getattr(node, "children", {}).values():
        yield c
        yield from _walk(c)
