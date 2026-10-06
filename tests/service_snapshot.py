"""R434 — the « Faire piloter mes campagnes » page rendered on FIXED answers, as a photo.

Type: Utility (test helper + CLI)
Uses: tests/home_snapshot.py (the photo reducer), tests/fixtures/service_snapshot.json
Triggers: tests/test_service_is_frozen.py, `make service-snapshot`
Persists in: tests/fixtures/service_snapshot.json

The owner, 2026-10-07: « une fois que c'est fait, tu verrouilles la view faire piloter mes
campagnes ». Same lock as Home (R425) and the PDF report (R428): any change of the photo
turns `tests/test_service_is_frozen.py` red, and approving a new photo is refused by the
commit-msg hook unless the cited roadmap row carries `<!-- service: oui -->`.

The page reads one setting (the booking link) and whether the viewer is an admin; both
answers are written HERE. The database handle raises on any use.

Usage:
    python3 -m tests.service_snapshot write
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHOTO = ROOT / "tests/fixtures/service_snapshot.json"

# scenario → (booking link, questionnaire open)
SCENARIOS = {"with_link": ("https://calendly.example/rdv", False),
             "no_link": ("", False),
             "mail_open": ("https://calendly.example/rdv", True)}

SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "artist"
st.session_state["artist_id"] = 1
st.session_state["authenticated"] = True
st.session_state["lang"] = "fr"
st.session_state["name"] = "artiste@example.com"
st.session_state["service_mail_open"] = {open!r}
import tests.service_snapshot as snap
with snap.patched({link!r}):
    from src.dashboard.views.service import show
    show()
"""


class _NoDatabase:
    """Any use names the reader that escaped the patches."""

    def __getattr__(self, name: str):
        raise AssertionError(
            f"the service page reached the database through `db.{name}` — a reader "
            "missing from tests/service_snapshot.py::patched")


@contextlib.contextmanager
def _no_db():
    yield _NoDatabase()


@contextlib.contextmanager
def patched(link: str):
    from src.dashboard import auth, utils
    from src.dashboard.utils import app_settings

    saved = [(auth, "is_admin", auth.is_admin), (utils, "project_db", utils.project_db),
             (app_settings, "get_setting", app_settings.get_setting)]
    auth.is_admin = lambda: False
    utils.project_db = _no_db
    app_settings.get_setting = (lambda db, key, default=None:
                                link if key == "service_calendly_url" else default)
    try:
        yield
    finally:
        for mod, name, real in reversed(saved):
            setattr(mod, name, real)


def render(scenario: str) -> dict:
    from streamlit.testing.v1 import AppTest

    from tests.home_snapshot import photo

    link, is_open = SCENARIOS[scenario]
    at = AppTest.from_string(SCRIPT.format(root=str(ROOT), link=link, open=is_open))
    at.run(timeout=120)
    if at.exception:
        raise AssertionError(f"Faire piloter ({scenario}) raised: {at.exception[0].value}")
    errors = [e.value for e in at.error]
    if errors:
        raise AssertionError(f"Faire piloter ({scenario}) showed an error: {errors}")
    return json.loads(json.dumps(photo(at._tree), ensure_ascii=False, sort_keys=True))


def write_photo() -> None:
    shot = {s: render(s) for s in SCENARIOS}
    PHOTO.write_text(json.dumps(shot, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                     encoding="utf-8")
    print(f"✅ {PHOTO.relative_to(ROOT)} written — commit it under a roadmap row "
          "carrying `<!-- service: oui -->`")


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    {"write": write_photo}[sys.argv[1]]()
