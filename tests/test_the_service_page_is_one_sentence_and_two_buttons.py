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

R430 (owner, 2026-10-06): pre-filled (300 à 1 000 €, under two weeks, Meta ads: yes),
countries / creatives / smart link gone, and the mail leaves FROM the app — « nous on
trace en fonction du nombre de mails » — the mailto only as the fallback of a failed send.
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


def _render(link: str, sends: bool = True):
    from streamlit.testing.v1 import AppTest

    script = TENANT_SCRIPT.format(root=os.getcwd(), view="service", artist_id=1).replace(
        "from src.dashboard.views.service import show\nshow()",
        "import src.utils.service_request_mail as _m\n"
        "import src.dashboard.utils.throttle as _th\n"
        "_send0, _limit0 = _m.send_service_request, _th.service_mail_consume\n"
        "_th.service_mail_consume = lambda *a: None\n"
        "st.session_state.setdefault('name', 'artiste@example.com')\n"
        "_m.send_service_request = lambda *a: (st.session_state.setdefault("
        f"'_sent', []).append(a), {sends!r})[1]\n"
        "import src.dashboard.utils.app_settings as _s\n"
        "_original = _s.get_setting\n"
        f"_s.get_setting = lambda db, key, default=None: {link!r} "
        "if key == 'service_calendly_url' else default\n"
        "from src.dashboard.views.service import show\n"
        "try:\n    show()\nfinally:\n    _s.get_setting = _original\n"
        "    _m.send_service_request = _send0\n"
        "    _th.service_mail_consume = _limit0")
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
    for part in ("déclenchement des algos Spotify", "- Optimisation des campagnes Meta Ads",
                 "- Optimisation des streams Spotify", "- Génération de créatives",
                 "- Bilan quotidien"):
        assert part in text, part
    found = _PRICE_OR_DURATION.findall(text)
    assert not found, f"the page states a price or a duration again: {found}"


def test_the_booking_button_hides_while_its_link_is_empty() -> None:
    at = _render("")
    assert _buttons(at) == [] and _mail_button(at) is not None


def _open(at):
    _mail_button(at).click().run(timeout=120)
    assert not at.exception, at.exception
    return at


def test_the_questionnaire_opens_pre_filled_and_without_the_dropped_questions() -> None:
    at = _render("")
    assert not at.code, "the mail shows before anyone asked for it"
    body = _open(at).code[0].value
    assert "300 à 1 000 €" in body and "moins de 2 semaines" in body
    assert "pub Meta ? : Oui" in body, "« déjà fait de la pub Meta » is not pre-ticked yes"
    ads = next(r for r in at.radio if "pub Meta" in r.label)
    assert list(ads.options) == ["Oui", "Non"], "a yes/no, not a list to open"
    for gone in ("pays", "créatives", "smart link", "concert", "titre concerné"):
        assert gone not in body.lower(), f"{gone!r} was dropped by the owner"
    assert "Shazam" in " ".join(next(m for m in at.multiselect).options)


def test_send_mails_the_owner_from_the_app_with_the_answers() -> None:
    at = _open(_render(""))
    next(s for s in at.selectbox if "Budget" in s.label).set_value("gt3000").run(timeout=120)
    assert not _buttons(at), "the mail app is a fallback, not the way to send"
    next(b for b in at.button if b.label == "📨 Envoyer").click().run(timeout=120)
    assert not at.exception, at.exception
    (to, _artist, reply_to, body), = at.session_state["_sent"]
    assert to == "1x7xxxxxxx@gmail.com" and reply_to == "artiste@example.com"
    assert "Plus de 3 000 €" in body and "Release Radar" in body
    assert any("C'est parti" in x.value for x in at.success)


def test_a_failed_send_offers_the_mail_app_with_the_same_mail() -> None:
    at = _open(_render("", sends=False))
    next(b for b in at.button if b.label == "📨 Envoyer").click().run(timeout=120)
    assert at.error, "a failed send is silent"
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


def test_the_mail_budget_is_per_account_and_capped_for_the_instance() -> None:
    """Security review R430: an IP in the key let a new network buy a new budget."""
    from src.dashboard.utils import throttle

    assert throttle.service_mail_consume(None) is not None, "no account still sends"
    def clear() -> None:  # the store is the shared Postgres one: leave nothing behind
        throttle._MAIL_LIMITERS["account"].reset("service_mail:r430-test")
        throttle._MAIL_LIMITERS["instance"].reset("service_mail:*")

    clear()
    seen = [throttle.service_mail_consume("r430-test")
            for _ in range(throttle.SERVICE_MAIL_PER_ACCOUNT + 1)]
    clear()
    assert seen[:-1] == [None] * throttle.SERVICE_MAIL_PER_ACCOUNT and seen[-1]
