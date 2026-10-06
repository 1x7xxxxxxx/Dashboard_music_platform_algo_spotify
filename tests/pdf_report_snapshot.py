"""R428 — the « Rapport PDF » page rendered on FIXED answers, reduced to a photo.

Type: Utility (test helper + CLI)
Uses: tests/home_snapshot.py (the photo reducer), tests/fixtures/pdf_report_snapshot.json
Triggers: tests/test_pdf_report_is_frozen.py, `make pdf-report-snapshot`
Persists in: tests/fixtures/pdf_report_snapshot.json

The owner, 2026-10-06: « vérrouille la view de rapport de carrière pdf ». Same lock as
Home (R425): the page is drawn on data that never moves, any change of its photo turns
`tests/test_pdf_report_is_frozen.py` red, and approving a new photo is refused by the
commit-msg hook unless the cited roadmap row carries `<!-- rapport_pdf: oui -->`.

The page is a form: its readers answer a handful of lists and names, so the answers are
written HERE rather than recorded — nothing to re-record when the database moves. Every
reader the page uses is in `REPLAYED`; the database handle raises on any other use.

Usage:
    python3 -m tests.pdf_report_snapshot write
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHOTO = ROOT / "tests/fixtures/pdf_report_snapshot.json"

# scenario → the plan the artist is on: free locks the Premium sections.
SCENARIOS = {"premium": "premium", "free": "free"}

SONGS = ["Titre A", "Titre B", "Titre C"]

# (name in views.export_pdf, its fixed answer) — patched where the view looks them up.
REPLAYED = (
    ("is_admin", lambda: False),
    ("tenant_scope", lambda: 1),
    ("_get_artist_name", lambda db, artist_id: "Artiste test"),
    ("account_scope", lambda db, artist_id, key=None: None),
    ("get_available_songs", lambda db, artist_id: list(SONGS)),
    ("_latest_release", lambda db, artist_id: SONGS[-1]),
)

SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "artist"
st.session_state["artist_id"] = 1
st.session_state["authenticated"] = True
st.session_state["lang"] = "fr"
import tests.pdf_report_snapshot as snap
with snap.patched({plan!r}):
    from src.dashboard.views.export_pdf import show
    show()
"""


class _NoDatabase:
    """Any use names the reader that escaped REPLAYED."""

    def close(self) -> None:
        pass

    def __getattr__(self, name: str):
        raise AssertionError(
            f"the PDF report reached the database through `db.{name}` — a reader missing "
            "from tests/pdf_report_snapshot.py::REPLAYED")


@contextlib.contextmanager
def patched(plan: str):
    from src.dashboard import auth
    from src.dashboard.views import export_pdf

    saved = [(export_pdf, name, getattr(export_pdf, name)) for name, _ in REPLAYED]
    saved += [(export_pdf, "get_db_connection", export_pdf.get_db_connection),
              (auth, "get_artist_plan", auth.get_artist_plan)]
    for name, answer in REPLAYED:
        setattr(export_pdf, name, answer)
    export_pdf.get_db_connection = _NoDatabase
    auth.get_artist_plan = lambda *a, **k: plan
    try:
        yield
    finally:
        for mod, name, real in reversed(saved):
            setattr(mod, name, real)


def render(scenario: str) -> dict:
    from streamlit.testing.v1 import AppTest

    from tests.home_snapshot import photo

    at = AppTest.from_string(SCRIPT.format(root=str(ROOT), plan=SCENARIOS[scenario]))
    at.run(timeout=120)
    if at.exception:
        raise AssertionError(f"rapport PDF ({scenario}) raised: {at.exception[0].value}")
    errors = [e.value for e in at.error]
    if errors:
        raise AssertionError(f"rapport PDF ({scenario}) showed an error: {errors}")
    return json.loads(json.dumps(photo(at._tree), ensure_ascii=False, sort_keys=True))


def write_photo() -> None:
    shot = {s: render(s) for s in SCENARIOS}
    PHOTO.write_text(json.dumps(shot, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                     encoding="utf-8")
    print(f"✅ {PHOTO.relative_to(ROOT)} written — commit it under a roadmap row "
          "carrying `<!-- rapport_pdf: oui -->`")


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    {"write": write_photo}[sys.argv[1]]()
