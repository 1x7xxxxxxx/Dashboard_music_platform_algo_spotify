"""« Faire piloter mes campagnes »: one sentence, two buttons, no price, no duration (R387).

Type: Guard
Uses: src.dashboard.views.service, tests/render_harness.py (TENANT_SCRIPT), AppTest
Depends on: live Postgres for app_settings (skipped without it)
Persists in: nothing — the booking link is set in session through a patched getter

Owner's screen review, 2026-10-05 (V52-V54): « je gère tes campagnes de A à Z selon ton
budget et tes objectifs », two buttons — write to me, book a call — and nothing that
reads as a quote. The booking URL comes later: its button is hidden while it is empty.

R429 (owner, 2026-10-06): « M'écrire » is short and no longer a bare mailto — it opens,
on the page, a questionnaire (budget, how soon the release is, goals…) and the mail it
makes, readable before it leaves, with a mailto that carries the answers.
"""
from __future__ import annotations

import os
import re
from urllib.parse import unquote

import pytest

from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT

pytestmark = pytest.mark.skipif(not db_ready(), reason="renders the service page")

_PRICE_OR_DURATION = re.compile(r"\d+\s*(€|%|semaine|mois|jour)", re.I)


def _render(link: str):
    from streamlit.testing.v1 import AppTest

    script = TENANT_SCRIPT.format(root=os.getcwd(), view="service", artist_id=1).replace(
        "from src.dashboard.views.service import show\nshow()",
        "import src.dashboard.utils.app_settings as _s\n"
        "_original = _s.get_setting\n"
        f"_s.get_setting = lambda db, key, default=None: {link!r} "
        "if key == 'service_calendly_url' else default\n"
        "from src.dashboard.views.service import show\n"
        "try:\n    show()\nfinally:\n    _s.get_setting = _original")
    at = AppTest.from_string(script)
    at.run(timeout=120)
    assert not at.exception, at.exception
    return at


def _buttons(at) -> list[str]:
    out, stack = [], [at._tree]
    while stack:
        node = stack.pop()
        if getattr(node, "type", None) == "link_button":
            out.append(node.proto.url)
        stack.extend(getattr(node, "children", {}).values())
    return out


def _mail_button(at):
    return next(b for b in at.button if "crire" in b.label)


def test_two_buttons_and_no_price_or_duration() -> None:
    at = _render("https://calendly.example/rdv")
    assert _mail_button(at).label == "✉️ M'écrire"
    assert _buttons(at) == ["https://calendly.example/rdv"], "the mail is not a bare mailto"
    text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "A à Z" in text, "the one-sentence pitch is gone"
    assert "bilans quotidiens" in text and "fichiers quotidiens" not in text
    found = _PRICE_OR_DURATION.findall(text)
    assert not found, f"the page states a price or a duration again: {found}"


def test_the_booking_button_hides_while_its_link_is_empty() -> None:
    at = _render("")
    assert _buttons(at) == [] and _mail_button(at) is not None


def test_write_to_me_opens_the_questionnaire_and_a_mail_that_carries_the_answers() -> None:
    at = _render("")
    assert not at.code, "the mail shows before anyone asked for it"
    _mail_button(at).click().run(timeout=120)
    budget = next(s for s in at.selectbox if "Budget" in s.label)
    budget.set_value("300_1000").run(timeout=120)
    release = next(s for s in at.selectbox if "sortie" in s.label)
    release.set_value("lt2w").run(timeout=120)
    goals = next(m for m in at.multiselect if "objectifs" in m.label)
    goals.set_value(["algos"]).run(timeout=120)
    assert not at.exception, at.exception
    body = at.code[0].value
    assert "300 à 1 000 €" in body and "moins de 2 semaines" in body
    assert "Release Radar" in body, "the algorithm goal does not reach the mail"
    mailto = unquote(_buttons(at)[0])
    assert mailto.startswith("mailto:") and "300 à 1 000 €" in mailto


def test_the_mail_names_every_question_even_unanswered() -> None:
    from src.dashboard.utils.service_offer import QUESTIONS, compose_mail

    body = compose_mail({"budget": "Plus de 3 000 €"}, "Bonjour", "Merci", {})
    assert body.count("\n- ") == len(QUESTIONS)
    assert "Plus de 3 000 €" in body and body.count(": —") == len(QUESTIONS) - 1


def test_every_question_and_option_has_its_english() -> None:
    """The other end of the `service.q.` dynamic prefix in test_i18n_orphans."""
    from src.dashboard.utils.i18n_catalog.service import EN
    from src.dashboard.utils.service_offer import QUESTIONS

    keys = [q.key for q in QUESTIONS] + [f"{q.key}.{s}" for q in QUESTIONS for s, _ in q.options]
    assert [k for k in keys if k not in EN] == []
