"""Referral: the code reads in clear under the invitation link, and signup takes it (R393).

Type: Guard
Uses: src.dashboard.views.referral, src.dashboard.views.register
Depends on: live Postgres for the referral render (skipped without)
Persists in: referral_codes (the artist's code, created once if absent)

V88 (owner's screen review, 2026-10-05): the code sat folded in an expander — one had
to know it existed to go and find it. No Stripe promo code (decision of 2026-10-05):
the OPTIONAL signup field, prefilled from `?ref=`, binds the referred artist through
the same `_apply_referral` as the link — this guard holds both ends of that path.
"""
from __future__ import annotations

import os

import pytest

from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT

_REGISTER = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.query_params["ref"] = "a3f8c1"
from src.dashboard.views.register import show
show()
"""


def _codes_outside_expanders(node, inside: bool = False):
    for child in getattr(node, "children", {}).values():
        folded = inside or type(child).__name__ == "Expander"
        if getattr(child, "type", "") == "code" and not folded:
            yield child.value
        yield from _codes_outside_expanders(child, folded)


@pytest.mark.skipif(not db_ready(), reason="renders the referral page against the live DB")
def test_the_code_is_visible_without_opening_anything() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="referral",
                                                  artist_id=1))
    at.run(timeout=90)
    assert not at.exception, at.exception
    shown = list(_codes_outside_expanders(at._tree))
    link = next((c for c in shown if "ref=" in c), None)
    assert link is not None, f"the invitation link is not shown: {shown}"
    code = link.rsplit("ref=", 1)[1]
    assert code in shown, f"the code {code} is folded away, not shown in clear: {shown}"
    assert shown.index(code) > shown.index(link), "the code is not under the link"


def test_the_signup_field_is_optional_and_prefilled_from_the_link() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_REGISTER.format(root=os.getcwd()))
    at.run(timeout=90)
    assert not at.exception, at.exception
    field = next((i for i in at.text_input if "parrainage" in i.label), None)
    assert field is not None, [i.label for i in at.text_input]
    assert "optionnel" in field.label, f"the referral field is not optional: {field.label}"
    assert field.value == "A3F8C1", "the link's code does not reach the signup field"
