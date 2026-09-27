"""The one-line ledger above the treasury adds up (R236, 2026-09-27).

Type: Test
Uses: src.dashboard.utils.treasury_chart (ledger_summary)
Depends on: nothing — pure
Persists in: nothing
"""
from __future__ import annotations

import pandas as pd

from src.dashboard.utils.treasury_chart import ledger_summary


def _cashflow() -> pd.DataFrame:
    return pd.DataFrame([
        {"flux": "revenu", "source": "imusician", "amount_eur": 200.0},
        {"flux": "revenu", "source": "sacem", "amount_eur": 48.0},
        {"flux": "depense", "source": "meta_ads", "amount_eur": 3000.0},
        {"flux": "depense", "source": "mastering", "amount_eur": 88.0},
    ])


def test_in_out_ads_and_the_cost_per_stream() -> None:
    mensuel = pd.DataFrame({"cumul": [-100.0, -2840.0]})
    s = ledger_summary(_cashflow(), mensuel, 300_000)
    assert (s["revenue"], s["spend"], s["ads"], s["other"]) == (248.0, 3088.0, 3000.0, 88.0)
    assert s["result"] == -2840.0
    assert abs(s["cost_per_stream"] - 0.01) < 1e-9


def test_no_streams_measured_gives_no_cost_rather_than_infinity() -> None:
    s = ledger_summary(_cashflow(), pd.DataFrame({"cumul": [0.0]}), None)
    assert s["cost_per_stream"] is None and s["streams"] is None
