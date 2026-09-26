"""The PDF's per-song ML block reads columns that exist, and a failed read says so.

Type: Test
Uses: pytest, psycopg2, tests/db_gate.py
Depends on: src/dashboard/utils/pdf_exporter/_collectors.py (_read_ml_prediction),
            src/dashboard/utils/pdf_exporter/_renderers.py (_render_songs_focus),
            src/database/ml_schema.py, src/dashboard/utils/algo_knowledge.py
Persists in: nothing (the live test runs inside a transaction that is rolled back)

What was measured (2026-09-26, on the prod snapshot `spotify_etl_review`)
-------------------------------------------------------------------------
`_collect_songs_focus` selected `dw_prob, rr_prob, radio_prob, dw_forecast_7d,
rr_forecast_7d`. None of them exists; executed, the query raised
`UndefinedColumn: column "dw_prob" does not exist`. A bare `except Exception` turned
that into a warning, `entry['ml']` stayed None, and EVERY client PDF printed « Pas de
prédiction ML disponible. » for every song. Had it worked, it would have printed
« Forecast RR 7j », the one volume the product suppresses everywhere else.

Three things are checked, from the strongest to the weakest:
  1. LIVE: the read binds on the provisioned schema and returns the seeded row
     (only execution proves a column list binds; a name match proves it is drawn);
  2. a database error is reported as UNREADABLE, never as « no prediction », and a
     non-database error propagates;
  3. no forecast the reliability gate suppresses is read or rendered.
"""
from __future__ import annotations

import re

import psycopg2
import pytest

from src.dashboard.utils import algo_knowledge as ak
from src.dashboard.utils.pdf_exporter import _collectors, _renderers
from src.database.ml_schema import ML_SCHEMA
from tests import db_gate

SONG = "__pdf_ml_block_guard__"


@pytest.fixture(autouse=True)
def _french_report(monkeypatch: pytest.MonkeyPatch) -> None:
    """The PDF language is module state another test may leave on "en"."""
    from src.dashboard.utils.pdf_exporter import _config
    monkeypatch.setitem(_config._LANG, "cur", "fr")


class _CursorDB:
    """The `fetch_query` contract of PostgresHandler, on a caller-owned cursor."""

    def __init__(self, cur):
        self.cur = cur
        self.queries: list[str] = []

    def fetch_query(self, query, params=None):
        self.queries.append(query)
        self.cur.execute(query, params)
        return self.cur.fetchall()


class _RaisingDB:
    def __init__(self, exc: Exception):
        self.exc = exc
        self.queries: list[str] = []

    def fetch_query(self, query, params=None):
        self.queries.append(query)
        raise self.exc


def _selected_columns(sql: str) -> list[str]:
    m = re.search(r"SELECT\s+(.*?)\s+FROM", sql, re.S | re.I)
    assert m, sql
    return [c.strip() for c in m.group(1).split(",")]


def _schema_columns() -> set[str]:
    ddl = ML_SCHEMA["ml_song_predictions"]
    return set(re.findall(r"^\s+([a-z_0-9]+)\s+[A-Z]", ddl, re.M))


# ── 1. live: the read binds ────────────────────────────────────────────────────

@db_gate.requires_live_db()
def test_the_read_binds_on_the_live_schema_and_returns_the_row() -> None:
    conn = psycopg2.connect(**db_gate.dsn())
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM saas_artists ORDER BY id LIMIT 1")
        row = cur.fetchone()
        if row is None:
            pytest.skip("no saas_artists row to own the seeded prediction")
        artist_id = row[0]
        cur.execute(
            """INSERT INTO ml_song_predictions
                 (artist_id, song, prediction_date, dw_probability, rr_probability,
                  radio_probability, dw_streams_forecast_7d, rr_streams_forecast_7d,
                  radio_streams_forecast_7d, model_version)
               VALUES (%s, %s, '2026-09-20', 0.61, 0.32, 0.13, 5400, 1200, 240,
                       '__guard__')""",
            (artist_id, SONG),
        )
        ml, unreadable = _collectors._read_ml_prediction(_CursorDB(cur), SONG, artist_id)
    finally:
        conn.rollback()
        conn.close()

    assert not unreadable, "the ML read FAILED on the live schema — a column does not bind"
    assert ml is not None, "a seeded prediction row was not returned"
    assert (ml["dw_prob"], ml["rr_prob"], ml["radio_prob"]) == (0.61, 0.32, 0.13)
    assert ml["prediction_date"] == "2026-09-20"
    expected = {a: v for a, v in {"DW": 5400.0, "RR": 1200.0, "RADIO": 240.0}.items()
                if ak.volume_forecast_reliable(a)}
    assert ml["forecast"] == expected


# ── the static edge (no DB): every selected column is declared ─────────────────

def test_every_selected_column_is_declared_in_the_schema() -> None:
    """Weaker than the live test: proves the edge is drawn, not that it binds."""
    db = _RaisingDB(psycopg2.errors.UndefinedColumn("x"))
    _collectors._read_ml_prediction(db, SONG, 1)
    declared = _schema_columns()
    assert {"dw_probability", "radio_streams_forecast_7d"} <= declared  # parser sanity
    unknown = [c for c in _selected_columns(db.queries[0]) if c not in declared]
    assert not unknown, f"PDF ML read selects columns ml_song_predictions lacks: {unknown}"


# ── 2. a failed read is not an absence ─────────────────────────────────────────

def test_a_database_error_is_reported_as_unreadable_not_absent() -> None:
    db = _RaisingDB(psycopg2.errors.UndefinedColumn('column "dw_prob" does not exist'))
    ml, unreadable = _collectors._read_ml_prediction(db, SONG, 1)
    assert ml is None and unreadable is True
    html = _renderers._render_songs_focus([{
        "song": SONG, "total_streams": 0, "last7d_streams": 0,
        "ml": ml, "ml_unreadable": unreadable,
    }])
    assert "illisible" in html
    assert "Pas de prédiction ML disponible." not in html, (
        "a failed ML read renders exactly like 'no prediction yet'")


def test_a_code_error_is_not_swallowed() -> None:
    with pytest.raises(TypeError):
        _collectors._read_ml_prediction(_RaisingDB(TypeError("bug")), SONG, 1)


# ── 3. a suppressed forecast is neither read nor rendered ──────────────────────

@pytest.mark.parametrize("algo", ["DW", "RR", "RADIO"])
def test_a_suppressed_forecast_is_not_read(algo: str,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    flipped = dict(ak.ALGO_REGRESSOR_METRICS.get(algo, {}), volume_reliable=False)
    monkeypatch.setitem(ak.ALGO_REGRESSOR_METRICS, algo, flipped)
    db = _RaisingDB(psycopg2.errors.UndefinedColumn("x"))
    _collectors._read_ml_prediction(db, SONG, 1)
    col = _collectors._ML_FORECAST_COLUMNS[algo]
    assert col not in _selected_columns(db.queries[0]), (
        f"{col} is read although volume_forecast_reliable({algo!r}) is False")


def test_a_suppressed_forecast_is_not_rendered_even_if_handed_over() -> None:
    ml = {"dw_prob": 0.6, "rr_prob": 0.3, "radio_prob": 0.1,
          "prediction_date": "2026-09-20",
          "forecast": {"DW": 5400.0, "RR": 1200.0, "RADIO": 240.0}}
    html = _renderers._render_songs_focus([{
        "song": SONG, "total_streams": 0, "last7d_streams": 0, "ml": ml}])
    for algo, shown in (("DW", "5,400"), ("RR", "1,200"), ("RADIO", "240")):
        if ak.volume_forecast_reliable(algo):
            assert f"<b>{shown}</b>" in html, f"{algo} forecast is reliable but missing"
        else:
            assert f"<b>{shown}</b>" not in html, (
                f"{algo} forecast is rendered in the PDF although the gate suppresses it")
