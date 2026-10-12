"""The weekly model-error SQL, played on the live schema (R527).

Type: Guard
Uses: src.dashboard.views.trigger_algo._tab_model (_WEEKLY_SQL, error_by_prediction_week)
Depends on: live Postgres (skipped without it)
Persists in: nothing (the seeded rows are rolled back)

The code-critic of R297 (2026-10-12) found that its only test fed a frozen frame to a
`_FakeDB`: dropping `p.artist_id = o.artist_id` from the join stayed green. This plays
the SQL itself on three seeded facts — another tenant's prediction, a prediction made
inside the reading's 28-day window, and a title predicted twice in one week.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.dashboard.views.trigger_algo._tab_model import _WEEKLY_SQL, error_by_prediction_week


def _dsn():
    from tests.db_gate import dsn

    return dsn()


@pytest.mark.skipif(_dsn() is None, reason="No Postgres — the SQL needs the live schema")
def test_the_weekly_sql_keeps_its_tenant_and_its_horizon() -> None:
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**_dsn())
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM saas_artists ORDER BY id LIMIT 2")
            ids = [r[0] for r in cur.fetchall()]
            if len(ids) < 2:
                pytest.skip("two tenants are needed")
            mine, other = ids
            song, read = "r527-song", dt.date(2026, 9, 30)
            cur.execute(
                "INSERT INTO s4a_song_algo_outcomes (artist_id, song, recorded_at, "
                "time_window, radio_streams) VALUES (%s,%s,%s,'28d',10)", (mine, song, read))
            for artist, day, version, forecast in (
                (mine, read - dt.timedelta(days=40), "v1", 30),   # judged
                (mine, read - dt.timedelta(days=39), "v1", 20),   # same week: latest kept
                (mine, read - dt.timedelta(days=10), "v1", 11),   # inside the window: out
                (other, read - dt.timedelta(days=40), "v1", 999),  # other tenant: out
            ):
                cur.execute(
                    "INSERT INTO ml_song_predictions (artist_id, song, prediction_date, "
                    "model_version, radio_streams_forecast_7d) VALUES (%s,%s,%s,%s,%s)",
                    (artist, song, day, version, forecast))
            cur.execute(_WEEKLY_SQL, (mine,))
            cols = [c.name for c in cur.description]
            rows = pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        conn.rollback()
        conn.close()

    mine_rows = rows[rows["song"] == song]
    assert 999 not in set(mine_rows["predicted_radio"]), "another tenant's forecast joined"
    assert 11 not in set(mine_rows["predicted_radio"]), "a forecast inside the window was judged"
    got = error_by_prediction_week(mine_rows, "RADIO")
    assert list(got["error"]) == [10.0], got       # |20 − 10|, the week's latest forecast
