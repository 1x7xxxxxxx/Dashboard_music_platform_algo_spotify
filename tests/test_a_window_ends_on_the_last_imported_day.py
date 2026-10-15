"""R571 — a "last N days" window over a hand-imported source ends on its last imported day.

Type: Test
Uses: src.utils.ml_inference.build_features, src.api.routers.kpis, live Postgres 5433
Depends on: tests.db_gate
Persists in: nothing (transaction rolled back)

Owner, 2026-10-15: a track showed its playlist adds and « 0 écoute sur 7 j ». S4A is a
CSV the artist drops by hand; counting 7 days back from TODAY reads an empty window as
soon as the last import is a week old, and `COALESCE(SUM, 0)` turns that absence into a
zero. The window is anchored on the artist's last imported day instead.
"""
from __future__ import annotations

import ast
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _dsn() -> dict | None:
    from tests.db_gate import dsn

    return dsn()


_CONN = _dsn()
pytestmark = [pytest.mark.xdist_group("a-window-ends-on-the-last-imported-day"),
              pytest.mark.skipif(_CONN is None, reason="No Postgres on 127.0.0.1:5433")]


class _Db:
    def __init__(self, cur):
        self._cur = cur

    def fetch_query(self, sql, params=None):
        self._cur.execute(sql, params)
        return self._cur.fetchall()


@pytest.fixture()
def stale_import():
    """A throw-away tenant whose S4A import stopped 10 days ago — rolled back."""
    psycopg2 = pytest.importorskip("psycopg2")
    sys.path.insert(0, str(ROOT))
    conn = psycopg2.connect(**_CONN)
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO saas_artists (name, slug, tier, active) VALUES "
                        "('Window Rule', 'window-rule-fixture', 'free', TRUE) RETURNING id")
            aid = cur.fetchone()[0]
            last = date.today() - timedelta(days=10)
            for back in range(40):
                cur.execute("INSERT INTO s4a_song_timeline (artist_id, song, date, streams) "
                            "VALUES (%s, 'Fixture', %s, 10)", (aid, last - timedelta(days=back)))
            yield _Db(cur), aid
    finally:
        conn.rollback()
        conn.close()


def test_the_model_counts_the_last_seven_imported_days(stale_import) -> None:
    from src.utils.ml_inference import build_features

    db, aid = stale_import
    feats = build_features(db, aid, "Fixture")
    assert feats, "the track has 40 imported days — the features cannot be empty"
    assert feats["_raw_streams_7d"] == 80, (
        "7 days back from TODAY lands after the last import: the window is empty and "
        "reads 0 while the import holds 10 streams a day")


def test_the_pdf_and_the_api_count_the_last_seven_imported_days(stale_import) -> None:
    from src.dashboard.utils.pdf_exporter._collectors import _collect_songs_focus

    db, aid = stale_import
    last = date.today() - timedelta(days=10)
    entry = _collect_songs_focus(db, aid, ["Fixture"], last - timedelta(days=39), last)[0]
    assert entry["last7d_streams"] == 80, "the PDF printed « 0 » for a track that streams"


# ── The class, everywhere: a today-relative window over the hand-imported S4A tables ──

_WINDOW = re.compile(r"(CURRENT_DATE|now\(\)::date)\s*-\s*(INTERVAL|\d)", re.I)
_S4A = re.compile(r"\b(v_s4a_song_daily|s4a_song_timeline)\b")

# Deliberate: the weekly mail reports THIS calendar week, and a stale import reads as
# « pas de mesure » there (SUM over no row is NULL, never COALESCEd to 0).
_CALENDAR_WEEK = {"src/utils/digest_queries.py", "airflow/dags/weekly_digest.py"}


def _docstrings(tree: ast.AST) -> set[int]:
    return {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and n.body and isinstance(n.body[0], ast.Expr)
            and isinstance(n.body[0].value, ast.Constant)}


def today_relative_s4a_windows(source: str) -> list[int]:
    """Lines of SQL strings that count an S4A window back from today. Pure."""
    tree = ast.parse(source)
    skip = _docstrings(tree)
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip:
            text = n.value
        elif isinstance(n, ast.JoinedStr):
            text = "".join(v.value for v in n.values if isinstance(v, ast.Constant))
        else:
            continue
        if _WINDOW.search(text) and _S4A.search(text):
            hits.append(n.lineno)
    return hits


def test_no_s4a_window_is_counted_back_from_today() -> None:
    found = []
    for path in [*(ROOT / "src").rglob("*.py"), *(ROOT / "airflow/dags").rglob("*.py")]:
        rel = path.relative_to(ROOT).as_posix()
        if rel not in _CALENDAR_WEEK:
            found += [f"{rel}:{ln}" for ln in today_relative_s4a_windows(
                path.read_text(encoding="utf-8"))]
    assert not found, (
        "a window over S4A counted back from TODAY reads 0 once the last import is old — "
        "anchor it with `src.utils.import_window.s4a_last_day`:\n  " + "\n  ".join(found))


def test_the_detector_sees_both_spellings_and_not_the_neighbours() -> None:
    assert today_relative_s4a_windows(
        'q = "SELECT 1 FROM v_s4a_song_daily WHERE day >= now()::date - 7"')
    assert today_relative_s4a_windows(
        "q = f\"SELECT 1 FROM s4a_song_timeline WHERE date >= CURRENT_DATE - INTERVAL '7 days' {x}\"")
    # an age is not a window; another table is not this source
    assert not today_relative_s4a_windows(
        'q = "SELECT CURRENT_DATE - first_streamed FROM v_s4a_song_daily"')
    assert not today_relative_s4a_windows(
        'q = "SELECT 1 FROM v_meta_daily WHERE day >= CURRENT_DATE - 14"')
