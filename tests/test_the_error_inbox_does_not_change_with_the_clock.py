"""The generated error inbox is a function of `app_error_log` alone — never of the clock.

Type: Sub
Uses: tools/error_inbox.py (render)
Triggers: pytest
Depends on: —
Persists in: —

R342. Until 2026-10-04 the document carried relative ages ("closed 5 d ago") and a
wall-clock regeneration stamp: `make error-inbox` dirtied the tree at every session
although no defect had moved, and `--check` had to filter a line out to stay green.
Rows here are dated in 2020, so any date the render prints that is NOT one of theirs
can only come from the clock.
"""

import importlib.util
import pathlib
import re
from datetime import datetime, timezone

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("error_inbox", _ROOT / "tools" / "error_inbox.py")
error_inbox = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(error_inbox)


def _at(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(tzinfo=timezone.utc)


_ROWS = [
    # fingerprint, exc_type, message, page, origin, env, occ, first, last, class, resolved, note
    ("a" * 40, "KeyError", "boom", "home", "src/x.py", "local", 3,
     _at("2020-01-02"), _at("2020-01-05"), None, None, None),
    ("b" * 40, "ValueError", "bad", None, "src/y.py", "local", 1,
     _at("2020-01-03"), _at("2020-01-03"), None, _at("2020-01-07"), "fixed"),
]
_ROW_DAYS = {"2020-01-02", "2020-01-03", "2020-01-05", "2020-01-07"}


def test_every_date_in_the_render_comes_from_the_rows():
    text, n_open = error_inbox.render(_ROWS, set())
    printed = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)) - {"2026-09-25"}  # R171 prose
    assert n_open == 1
    assert printed <= _ROW_DAYS, f"dates not taken from the data: {printed - _ROW_DAYS}"
    assert "il y a" not in text, "a relative age changes the file with the clock alone"


def test_the_as_of_line_is_the_latest_event():
    text, _ = error_inbox.render(_ROWS, set())
    assert "État au 2020-01-07" in text
