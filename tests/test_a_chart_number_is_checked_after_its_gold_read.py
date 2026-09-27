"""R241 — a chart's number is checked on what it DRAWS, not only on what it reads.

Owner, 2026-09-27: « vérifie tout, que les chiffres ne sont pas faux ». Reading the gold
layer is necessary, not sufficient (code-critic): a correct read can still be summed as a
cumul, multiplied by 100 twice, or drawn as two bars under one label — fiches 29 and 33,
where « Début » ran in two campaigns and two bars overlapped on one row.
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd

from src.dashboard.utils.creative_decisions import by_creative

ROOT = Path(__file__).resolve().parents[1]
_D = ROOT / "tools/dev/charts_dossier"
sys.path.insert(0, str(_D))
_spec = importlib.util.spec_from_file_location("numbers_check", _D / "numbers_check.py")
numbers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(numbers)
_cap = importlib.util.spec_from_file_location("capture_dossier", _D / "capture.py")
capture = importlib.util.module_from_spec(_cap)
_cap.loader.exec_module(capture)


def test_the_detector_sees_the_defect_it_is_written_for():
    """Each failure shape is named; the same chart without it is « vérifié »."""
    ok = [{"name": "Dépense", "type": "bar", "unit": "€", "n": 3, "min": 1, "max": 9,
           "sum": 12, "decreases": True, "dup_labels": 0}]
    assert numbers.verdict(ok, "or", ["v_meta_creative_daily"], [])[0] == "verifie"
    dup = [{**ok[0], "dup_labels": 1}]
    assert numbers.verdict(dup, "or", ["v_meta_creative_daily"], [])[0] == "ecart"
    rate = [{**ok[0], "name": "CTR (%)", "max": 1111}]
    assert numbers.verdict(rate, "or", ["v"], [])[0] == "ecart"
    cumul = [{**ok[0], "type": "scatter", "name": "Dépense cumulée", "max_drop": 1.0}]
    assert numbers.verdict(cumul, "or", ["v"], [])[0] == "ecart"
    # Both false positives of the first predicate (rule 20): a signed balance, a small dip.
    net = [{**cumul[0], "name": "Cumul net"}]
    assert numbers.verdict(net, "or", ["v"], [])[0] == "verifie"
    dip = [{**cumul[0], "name": "Cumul Revenue iMusician", "max_drop": 0.03}]
    assert numbers.verdict(dip, "or", ["v"], [])[0] == "verifie"
    finding = ["artiste 1 — meta_spend_two_grains : v_meta_daily = 1 mais v_meta_campaign_daily = 2"]
    assert numbers.verdict(ok, "or", ["v_meta_daily"], finding)[0] == "ecart"
    assert numbers.verdict(ok, "brut", ["meta_insights"], [])[0] == "non-garanti"
    assert numbers.verdict(None, "or", ["v"], [])[0] == "non-rendu"


def test_the_capture_measures_the_fall_from_the_peak():
    assert capture._max_drop([1, 5, 5, 0, 6]) == 1.0
    assert capture._max_drop([100, 97, 120]) == 0.03


def test_the_capture_counts_two_bars_on_one_label():
    fig = {"data": [{"type": "bar", "orientation": "h", "x": [0.29, 1.1], "y": ["Début", "Début"]}],
           "layout": {}}
    assert capture.trace_shapes(fig)[0]["dup_labels"] == 1


def test_one_creative_in_two_campaigns_is_one_bar_with_recomputed_rates():
    df = pd.DataFrame({
        "creative_name": ["Début", "Début", "X"], "campaign_name": ["A", "B", "A"],
        "total_spend": [400.0, 30.0, 10.0], "total_results": [1000, 8, 0],
        "cpr": [0.4, None, None], "total_clicks": [100, 5, 1],
        "total_impressions": [1000, 500, 10]})
    out = by_creative(df).set_index("creative_name")
    assert out.index.is_unique
    assert out.loc["Début", "total_spend"] == 430.0
    assert out.loc["Début", "cpr"] == 0.4, "CPR is priced on the rows whose goal HAS a result"
    assert out.loc["Début", "avg_ctr"] == 7.0, "CTR = 100·Σclicks/Σimpressions, not a mean"
