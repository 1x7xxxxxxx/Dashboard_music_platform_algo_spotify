"""« Faire piloter mes campagnes »: one sentence, two buttons, no price, no duration (R387).

Type: Guard
Uses: src.dashboard.views.service, tests/render_harness.py (TENANT_SCRIPT), AppTest
Depends on: live Postgres for app_settings (skipped without it)
Persists in: nothing — the booking link is set in session through a patched getter

Owner's screen review, 2026-10-05 (V52-V54): « je gère tes campagnes de A à Z selon ton
budget et tes objectifs », two buttons — write to me, book a call — and nothing that
reads as a quote. The booking URL comes later: its button is hidden while it is empty.
"""
from __future__ import annotations

import os
import re

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


def test_two_buttons_and_no_price_or_duration() -> None:
    at = _render("https://calendly.example/rdv")
    urls = _buttons(at)
    assert len(urls) == 2, f"expected write-to-me and book-a-call, got {urls}"
    assert any(u.startswith("mailto:") for u in urls)
    assert "https://calendly.example/rdv" in urls
    text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "A à Z" in text, "the one-sentence pitch is gone"
    found = _PRICE_OR_DURATION.findall(text)
    assert not found, f"the page states a price or a duration again: {found}"


def test_the_booking_button_hides_while_its_link_is_empty() -> None:
    urls = _buttons(_render(""))
    assert len(urls) == 1 and urls[0].startswith("mailto:"), urls
