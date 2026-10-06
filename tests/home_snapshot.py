"""R425 — the home page rendered on FROZEN data, reduced to a comparable photo.

Type: Utility (test helper + CLI)
Uses: tests/fixtures/home_data.pkl (the recorded reader answers),
      tests/fixtures/home_snapshot.json (the approved photo)
Triggers: tests/test_home_is_frozen.py, `make home-snapshot`, `make home-record`
Persists in: tests/fixtures/home_snapshot.json, tests/fixtures/home_data.pkl

Why this exists — the owner, 2026-10-06
---------------------------------------
« beaucoup de fois j'ai eu le cas où je modifiais un truc sur une page et il y avait
l'autre page qui était modifiée ». Home is drawn by helpers it shares with other pages
(`platform_chart`, `charts`, `stat_boxes`, i18n catalogs). A change made for another
page reaches Home without anything saying so.

So Home is rendered here on data that never moves, and the render is reduced to what a
reader sees: element order, texts, column weights, each figure's layout. Any change
of that photo fails `tests/test_home_is_frozen.py`; approving it means regenerating
the photo, and `tools/dev/require_roadmap_id.py` refuses that commit unless the cited
roadmap row carries `<!-- home: oui -->`.

Data is replayed at the READER level, never at SQL: every function Home asks for data
is in `REPLAYED`, its recorded answer is served back, and the database handle is a
stub that raises on any use — a new reader Home starts calling fails loudly instead of
reaching a database CI does not have (its Postgres is an empty schema).

Usage:
    python3 -m tests.home_snapshot write     # photo from the recording (no DB)
    python3 -m tests.home_snapshot record    # re-record from the local DB (5433)
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import importlib
import json
import os
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tests/fixtures/home_data.pkl"
PHOTO = ROOT / "tests/fixtures/home_snapshot.json"

# The day the recording was made: the period selector computes its bounds from it.
FROZEN_DAY = _dt.date(2026, 10, 6)

# (scenario, tenant): a tenant with history, and one on its first day.
SCENARIOS = {"full": 1, "empty": 471}

# Every function through which Home reads data. Patched where it is DEFINED: Home and
# its helpers import them inside functions, so the patch is seen at call time.
REPLAYED = (
    ("src.dashboard.utils.platform_timeseries", "daily_streams_by_platform"),
    ("src.dashboard.utils.platform_timeseries", "apple_yearly_series"),
    ("src.dashboard.utils.platform_timeseries", "platform_totals"),
    ("src.dashboard.utils.platform_timeseries", "cumulative_by_platform"),
    ("src.dashboard.utils.platform_timeseries", "discarded_deltas"),
    ("src.dashboard.utils.period_side_metrics", "period_side_metrics"),
    ("src.dashboard.utils.setup_completion", "read_setup_state"),
    ("src.dashboard.auth", "get_artist_plan"),
    ("src.utils.artist_readiness", "artist_readiness"),
    ("src.dashboard.utils.status_matrix", "read_probes"),
    ("src.dashboard.utils.status_matrix", "read_identities"),
)

SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "artist"
st.session_state["artist_id"] = {artist_id}
st.session_state["email"] = "artist@test"
st.session_state["authenticated"] = True
st.session_state["lang"] = "fr"
from src.dashboard.views.home import show
show()
"""


class _NoDatabase:
    """The handle Home gets in replay: any use names the reader that escaped REPLAYED."""

    def __getattr__(self, name: str):
        raise AssertionError(
            f"Home reached the database through `db.{name}` — a reader missing from "
            "tests/home_snapshot.py::REPLAYED. Add it there, then `make home-record`.")


def _key(name: str, args: tuple, kwargs: dict) -> str:
    return repr((name, args[1:] if args and not isinstance(args[0], (int, str)) else args,
                 sorted(kwargs.items())))


@contextlib.contextmanager
def _patched(artist_id: int, store: dict, record: bool):
    """Replay (or record) every reader, freeze the clock, hand Home a db stub."""
    from src.dashboard.utils import date_range
    from src.dashboard.views import home

    saved = []

    def wrap(mod, attr):
        real = getattr(mod, attr)

        def reader(*args, **kwargs):
            key = _key(attr, args, kwargs)
            if record:
                store[key] = real(*args, **kwargs)
            if key not in store:
                raise AssertionError(f"no recorded answer for {key} — `make home-record`")
            return store[key]
        return reader

    for modname, attr in REPLAYED:
        mod = importlib.import_module(modname)
        saved.append((mod, attr, getattr(mod, attr)))
        setattr(mod, attr, wrap(mod, attr))
    saved.append((date_range, "_today_in_display_tz", date_range._today_in_display_tz))
    date_range._today_in_display_tz = lambda: FROZEN_DAY
    if not record:
        saved.append((home, "project_db", home.project_db))
        home.project_db = lambda: contextlib.nullcontext(_NoDatabase())
    try:
        yield
    finally:
        for mod, attr, real in reversed(saved):
            setattr(mod, attr, real)


def render(scenario: str, store: dict, record: bool = False):
    from streamlit.testing.v1 import AppTest

    artist_id = SCENARIOS[scenario]
    with _patched(artist_id, store, record):
        at = AppTest.from_string(SCRIPT.format(root=str(ROOT), artist_id=artist_id))
        at.run(timeout=180)
    if at.exception:
        raise AssertionError(f"home ({scenario}) raised: {at.exception[0].value}")
    errors = [e.value for e in at.error]
    if errors:
        raise AssertionError(f"home ({scenario}) showed an error: {errors}")
    return photo(at._tree)


# ── THE PHOTO ────────────────────────────────────────────────────────────────

_VOLATILE = {"id", "formId", "key", "elementId", "fragmentId", "deltaPath"}


def _round(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, dict):
        return {k: _round(v[k]) for k in sorted(v) if k not in _VOLATILE}
    if isinstance(v, list):
        return [_round(x) for x in v]
    return v


def _figure(spec: dict) -> dict:
    """A figure's layout and the look of each trace — never its data arrays."""
    layout = dict(spec.get("layout") or {})
    layout.pop("template", None)
    traces = []
    for tr in spec.get("data") or []:
        traces.append({k: tr[k] for k in ("type", "name", "mode", "showlegend",
                                          "line", "marker", "fill", "stackgroup",
                                          "hole", "textposition", "textinfo", "labels", "text",
                                          "hovertemplate", "orientation")
                       if k in tr})
        traces[-1]["points"] = len(tr.get("x") or tr.get("values") or [])
    return _round({"layout": layout, "traces": traces})


def _node(node) -> dict | None:
    from google.protobuf.json_format import MessageToDict

    kind = getattr(node, "type", None) or type(node).__name__
    kids = list(node.children.values()) if hasattr(node, "children") else []
    out: dict = {"type": kind}
    proto = getattr(node, "proto", None)
    if kind == "plotly_chart":
        out["figure"] = _figure(json.loads(proto.spec))
    elif proto is not None and not kids:
        out.update(_round(MessageToDict(proto)))
    elif kind == "column":
        out["weight"] = round(getattr(node, "weight", 0) or 0, 4)
    if kids:
        out["children"] = [n for n in (_node(k) for k in kids) if n]
    return out


def photo(tree) -> dict:
    return _node(tree)


# ── CLI ──────────────────────────────────────────────────────────────────────

def load_data() -> dict:
    with DATA.open("rb") as fh:
        return pickle.load(fh)


def write_photo() -> None:
    data = load_data()
    shot = {s: render(s, data.get(s, {})) for s in SCENARIOS}
    PHOTO.write_text(json.dumps(shot, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                     encoding="utf-8")
    print(f"✅ {PHOTO.relative_to(ROOT)} written — commit it under a roadmap row "
          "carrying `<!-- home: oui -->`")


def record() -> None:
    data = {}
    for s in SCENARIOS:
        data[s] = {}
        render(s, data[s], record=True)
    DATA.write_bytes(pickle.dumps(data, protocol=4))
    print(f"✅ {DATA.relative_to(ROOT)} recorded from the local database")


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    {"write": write_photo, "record": record}[sys.argv[1]]()
