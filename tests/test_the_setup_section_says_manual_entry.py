"""R588 (owner, 2026-10-15) — the setup section is also where figures are typed by hand.

Type: Hook
Uses: src/dashboard/utils/nav_sections.py, src/dashboard/utils/i18n.py
"""
from src.dashboard.utils import i18n
from src.dashboard.utils.nav_sections import NAV_SECTIONS


def test_the_setup_section_names_manual_entry() -> None:
    label = {sid: lab for sid, lab, _ in NAV_SECTIONS}["data"]
    assert label == "⚙️ Configuration et saisie manuelle de streaMLytics"
    assert "manual entry" in i18n._TR["en"]["nav.section.data"]
