"""R249 (fiche 72) — « détecter les anomalies d'ingestion : lignes attendues par artiste ×
artistes contre lignes reçues, alerte au-delà d'un seuil ».

Type: Test
Uses: src/dashboard/views/db_health.py::ingestion_gaps, src/utils/volume_monitor.py

The page reuses the nightly check's rule (`is_partial_collection`: under a third of usual,
zero excluded) so that the chart and the 23:00 mail never disagree about a dip. A zero is
only « muet » on a DAILY feed — a weekly CSV import is silent six days out of seven.
"""
import datetime as dt

import pandas as pd

from src.dashboard.views.db_health import ingestion_gaps

YESTERDAY = dt.date(2026, 9, 26)


def _daily(dataset, tenant, per_day: dict) -> list[dict]:
    return [{"dataset": dataset, "tenant": tenant,
             "day": YESTERDAY - dt.timedelta(days=k), "n_rows": n}
            for k, n in per_day.items() if n]


def _verdicts(rows) -> dict:
    g = ingestion_gaps(pd.DataFrame(rows), YESTERDAY)
    return {(r.dataset, r.tenant): r.verdict for r in g.itertuples()}


def test_a_collection_under_a_third_of_usual_is_a_dip():
    rows = _daily("S4A", 1, {0: 5, **{k: 40 for k in range(1, 8)}})
    assert _verdicts(rows) == {("S4A", 1): "creux"}


def test_a_normal_day_is_ok_and_each_tenant_is_judged_alone():
    rows = (_daily("S4A", 1, {k: 40 for k in range(0, 8)})
            + _daily("S4A", 14, {0: 100, **{k: 1500 for k in range(1, 8)}}))
    assert _verdicts(rows) == {("S4A", 1): "ok", ("S4A", 14): "creux"}


def test_nothing_from_a_daily_feed_is_silent_but_a_weekly_import_is_not():
    daily = _daily("YouTube", 1, {k: 20 for k in range(1, 8)})
    weekly = _daily("iMusician", 1, {3: 60})
    assert _verdicts(daily + weekly) == {("YouTube", 1): "muet", ("iMusician", 1): "ok"}


def test_a_tiny_feed_is_below_the_measured_floor():
    # 7 rows/day was Benken's real volume (2026-08-23): the floor of 5 keeps it watched.
    assert _verdicts(_daily("SC", 12, {0: 1, **{k: 7 for k in range(1, 8)}})) == {
        ("SC", 12): "creux"}
    assert _verdicts(_daily("SC", 12, {0: 0, **{k: 2 for k in range(1, 8)}})) == {
        ("SC", 12): "ok"}


def test_expected_and_received_are_the_numbers_drawn():
    g = ingestion_gaps(pd.DataFrame(_daily("S4A", 1, {0: 35, **{k: 42 for k in range(1, 8)}})),
                       YESTERDAY)
    assert g.loc[0, "expected"] == 42 and g.loc[0, "received"] == 35


def test_no_data_gives_an_empty_frame_not_a_crash():
    assert ingestion_gaps(pd.DataFrame(), YESTERDAY).empty


def test_an_irregular_feed_is_judged_on_its_seven_day_mean_zeros_included():
    # 40 rows on 4 of the 7 days: the usual DAY is 22.9, not 40. Yesterday's 10 is under
    # a third of 40 but over a third of 22.9 — averaging only the days with rows would
    # raise a dip on a feed that simply does not write every day.
    rows = _daily("Meta", 1, {0: 10, 1: 40, 3: 40, 5: 40, 7: 40})
    assert _verdicts(rows) == {("Meta", 1): "ok"}
