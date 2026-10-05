"""Mon compte: the deletion button SENDS the request; the connected-accounts block is gone (R390).

Type: Guard
Uses: src.dashboard.views.account, streamlit AppTest
Depends on: nothing (no DB — the sections are rendered with a stub user)
Persists in: nothing

Owner's screen review, 2026-10-05 (V81-V83): « Mes comptes branchés » leaves the account
page (it lives in Credentials); under « Supprimer mon compte » a button mails the request
to the admin directly — no address to copy, no `mailto` — and says what happens next.
The send is counted at `EmailAlert.send_alert`; nothing reaches SMTP (conftest boundary).
"""
from __future__ import annotations

import os

from streamlit.testing.v1 import AppTest

_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
from src.utils import email_alerts
from src.dashboard.views import account

_original = email_alerts.EmailAlert.send_alert

def _record(self, subject, body):
    st.session_state.setdefault("_sent", []).append(subject)
    return {ok}

email_alerts.EmailAlert.send_alert = _record
try:
    user = {{"username": "artiste_x", "email": "x@test", "role": "artist",
             "email_verified": True, "created_at": None}}
    account._section_profile(None, user)
    account._section_delete_account(user)
finally:
    email_alerts.EmailAlert.send_alert = _original
"""


def _app(ok: bool = True) -> AppTest:
    at = AppTest.from_string(_SCRIPT.format(root=os.getcwd(), ok=ok))
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _texts(at: AppTest) -> str:
    return " ".join(str(e.value) for kind in (at.markdown, at.caption, at.info, at.subheader)
                    for e in kind)


def test_the_connected_accounts_block_is_gone() -> None:
    import src.dashboard.views.account as account

    at = _app()
    assert "branchés" not in _texts(at), "« Mes comptes branchés » is back on the account page"
    assert not hasattr(account, "_section_connected")


def test_the_button_sends_the_request_once_and_says_so() -> None:
    at = _app()
    assert "_sent" not in at.session_state, "the request left before any click"
    assert "@" not in " ".join(m.value for m in at.markdown), "an address to copy is back"
    at.button(key="account_delete_request_artiste_x").click().run(timeout=60)
    assert at.session_state["_sent"] == ["Demande de suppression de compte — artiste_x"]
    assert at.success and not at.error
    at.run(timeout=60)
    assert len(at.session_state["_sent"]) == 1, "a rerun sent the request again"


def test_a_failed_send_is_said_not_hidden() -> None:
    at = _app(ok=False)
    at.button(key="account_delete_request_artiste_x").click().run(timeout=60)
    assert at.error and not at.success, "a send that failed displays as sent"
