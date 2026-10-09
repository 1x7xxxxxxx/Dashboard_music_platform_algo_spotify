"""R482 — the Hypeddit entry opens on the latest release, dated today, one call to action.

Type: Test
Uses: src/dashboard/views/hypeddit.py (entry_defaults, _render_entry_form), AppTest

Owner, 2026-10-09 (W5 II) : « Type d'office "nouvelle" si la dernière track sortie n'a pas
encore de données Hypeddit ; présélectionner cette track, date = aujourd'hui » ; « boutons
Enregistrer au milieu, plus gros ; supprimer Réinitialiser ».
"""
from __future__ import annotations

import datetime as dt
import os

import pytest

from src.dashboard.views.hypeddit import entry_defaults

_D = dt.date


def test_the_latest_release_without_a_campaign_is_new():
    rel = {"Old song": _D(2025, 1, 1), "Fresh song": _D(2026, 9, 1)}
    assert entry_defaults(rel, ["Old song campaign"]) == (True, "Fresh song")


def test_the_latest_release_with_a_campaign_preselects_it():
    rel = {"Old song": _D(2025, 1, 1), "Fresh song": _D(2026, 9, 1)}
    assert entry_defaults(rel, ["Old song", "FRESH SONG – smart link"]) == (
        False, "FRESH SONG – smart link")


def test_without_a_release_date_the_newest_campaign_is_kept():
    assert entry_defaults({}, ["newest", "older"]) == (False, "newest")
    assert entry_defaults({}, []) == (True, None)


def test_the_page_opens_today_with_one_centred_save():
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest

    from tests.render_harness import TENANT_SCRIPT
    from src.dashboard.utils import get_db_connection
    if get_db_connection() is None:
        pytest.skip("no database")
    at = AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="hypeddit",
                                                  artist_id=1), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    dates = [d for d in at.date_input if d.key == "h_date"]
    assert dates and dates[0].value == dt.date.today(), "la date ne s'ouvre pas sur aujourd'hui"
    labels = [b.label for b in at.button]
    assert not any("initialiser" in (lbl or "") for lbl in labels), labels
    assert any("Enregistrer" in (lbl or "") for lbl in labels), labels
