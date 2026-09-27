"""R247 step 4 — fiches 44, 45, 51, 57, 58, 64: each chart the owner « did not understand »
now ends on a written decision, computed by a pure function. These tests pin the
thresholds that choose the sentence, on both sides of each.

Type: Test
Uses: the verdict helpers of _common/_lifecycle.py, roi_verdicts.py, _tab_model.py,
      ml_widgets.py, s4a_entry_insight.py, artist_cashflow.py
"""
from src.dashboard.utils.artist_cashflow import trigger_decision
from src.dashboard.utils.ml_widgets import sensitivity_verdict
from src.dashboard.utils.roi_verdicts import fit_decision
from src.dashboard.utils.s4a_entry_insight import bet_decision
from src.dashboard.views.trigger_algo._common._lifecycle import cohort_verdict
from src.dashboard.views.trigger_algo._tab_model import volume_verdict


def test_fiche_44_the_cohort_verdict_turns_on_half_and_on_the_median():
    assert "relancer" in cohort_verdict(0.49)
    assert "surveiller" in cohort_verdict(0.5)
    assert "surveiller" in cohort_verdict(0.99)
    assert "laisse-le tourner" in cohort_verdict(1.0)


def test_fiche_45_an_unsignificant_fit_decides_nothing_about_money():
    # Artist 1 on 2026-09-26: 12 months, p = 0.177 — the honest verdict is « no link ».
    assert fit_decision({"p_value": 0.177, "slope": 0.4}) == ("none", None)
    assert fit_decision({"p_value": 0.01, "slope": -0.3}) == ("none", None)
    assert fit_decision({"p_value": 0.01, "slope": 1.2}) == ("pays", 1.2)
    assert fit_decision({"p_value": 0.049, "slope": 0.3}) == ("short", 0.3)


def test_fiche_51_the_volume_verdict_reads_the_snapshot_as_an_overestimate():
    # Snapshot 2026-09-27: Radio forecast 1-11 streams per title, S4A recorded 0 on all 11.
    assert volume_verdict([7, 7, 6, 11, 5, 7, 5, 7, 9, 1, 11], [0] * 11) == "over"
    assert volume_verdict([10, 10], [25, 25]) == "under"
    assert volume_verdict([10, 10], [10, 15]) == "close"


def test_fiche_57_a_flat_curve_is_said_flat():
    assert "Courbe plate" in sensitivity_verdict([15.0, 15.4, 16.9], "Saves")
    assert "compte" in sensitivity_verdict([15.0, 30.0], "Saves")


def test_fiche_58_no_verdict_on_the_model_below_ten_titles():
    assert "Trop tôt" in bet_decision(0, 1.2, 9)
    assert "aucun n'est arrivé" in bet_decision(0, 1.2, 11)
    assert "reste dans ce que" in bet_decision(1, 1.2, 11)
    assert "reste dans ce que" in bet_decision(0, 0.6, 11)


def test_fiche_64_a_trigger_is_small_against_a_large_gap():
    kind, n = trigger_decision(23.38, 2839.0)
    assert kind == "small" and round(n) == 121
    assert trigger_decision(23.38, 200.0) == ("worth", None)
    assert trigger_decision(23.38, None) == ("worth", None)
    assert trigger_decision(23.38, -50.0) == ("worth", None)
