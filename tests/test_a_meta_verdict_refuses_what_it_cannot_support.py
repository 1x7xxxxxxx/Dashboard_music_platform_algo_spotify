"""The Meta-campaign verdict on the Spotify page refuses to conclude when the data cannot support it.

Type: Sub
Uses: src/dashboard/utils/meta_impact.py (campaigns, verdict)
Depends on: nothing
Persists in: nothing

R187 (2026-09-26). The number is read by an artist as « the ad worked / did not ». code-critic
refused the first formula: it called listener-days « people », ignored running and overlapping
campaigns, and averaged over the gaps of episodic S4A imports. Each refusal is pinned here.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from src.dashboard.utils import meta_impact as mi

_D0 = dt.date(2026, 5, 1)


def _days(start: dt.date, n: int, value: float, noise: float = 0.0) -> dict:
    return {start + dt.timedelta(days=i): value + (noise if i % 2 else -noise)
            for i in range(n)}


def _camp(name: str, start: dt.date, end: dt.date, spend: float = 100.0, acct: str = "a1"):
    return mi.Campaign(acct, name, start, end, spend)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """A real lift is concluded and priced in listener-DAYS; every unsupported case is
    « non concluant » or « tourne encore »."""
    start, end = _D0 + dt.timedelta(days=28), _D0 + dt.timedelta(days=41)
    series = pd.Series({**_days(_D0, 28, 100, 5), **_days(start, 14, 160, 5)})
    v = mi.verdict(series, [_camp("launch", start, end, spend=280)], dt.date(2026, 7, 1))
    assert v.conclusive and v.lift_per_day == 60
    assert "auditeurs-jour" in v.text and v.eur_per_listener_day == 280 / (60 * 14)

    running = mi.verdict(series, [_camp("launch", start, dt.date(2026, 7, 1))], dt.date(2026, 7, 1))
    assert not running.conclusive and "tourne encore" in running.text

    gappy = pd.Series({**_days(_D0 + dt.timedelta(days=20), 8, 100, 5), **_days(start, 14, 160)})
    assert "Non concluant" in mi.verdict(gappy, [_camp("launch", start, end)], dt.date(2026, 7, 1)).text

    no_s4a = pd.Series(_days(_D0, 28, 100, 5))
    assert "importe le CSV" in mi.verdict(no_s4a, [_camp("launch", start, end)], dt.date(2026, 7, 1)).text

    overlap = [_camp("other", start - dt.timedelta(days=5), start + dt.timedelta(days=2), acct="a2"),
               _camp("launch", start, end)]
    assert "impossible de les séparer" in mi.verdict(series, overlap, dt.date(2026, 7, 1)).text

    flat = pd.Series({**_days(_D0, 28, 100, 20), **_days(start, 14, 110, 20)})
    v = mi.verdict(flat, [_camp("launch", start, end)], dt.date(2026, 7, 1))
    assert v.conclusive and v.eur_per_listener_day is None and "variation normale" in v.text


def test_campaigns_are_split_by_account_and_ignore_zero_spend() -> None:
    df = pd.DataFrame({
        "ad_account_id": ["a1", "a1", "a2", "a1"],
        "campaign_name": ["c", "c", "c", "d"],
        "day": [_D0, _D0 + dt.timedelta(days=3), _D0, _D0],
        "spend": [10.0, 5.0, 7.0, 0.0],
    })
    got = mi.campaigns(df)
    assert sorted((c.account, c.name, c.spend) for c in got) == [("a1", "c", 15.0), ("a2", "c", 7.0)]
    assert all(c.name != "d" for c in got)
