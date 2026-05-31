"""Unit tests for the pure helpers in algo_knowledge (Discover Weekly domain rules)."""
import math

import pytest

from src.dashboard.utils import algo_knowledge as ak


def test_zone_for_value_streams_peage():
    assert ak.zone_for_value("DW", "StreamsLast7Days", 1800) == "malus"
    assert ak.zone_for_value("DW", "StreamsLast7Days", 2000) == "bonus"
    assert ak.zone_for_value("DW", "StreamsLast7Days", 6000) == "bonus"


def test_zone_for_value_days_since_release_golden_age():
    assert ak.zone_for_value("DW", "DaysSinceRelease", 10) == "malus"
    assert ak.zone_for_value("DW", "DaysSinceRelease", 120) == "bonus"
    assert ak.zone_for_value("DW", "DaysSinceRelease", 500) == "neutral"


def test_zone_for_value_velocity_rejects_buzz():
    # Recalibrated from data (2026-05-31): 1.2-2.0 is healthy (neutral); penalty
    # only at the suspect peak (>3.5).
    assert ak.zone_for_value("DW", "Velocity_Streams", 1.5) == "neutral"
    assert ak.zone_for_value("DW", "Velocity_Streams", 4.0) == "malus"


def test_zone_for_value_handles_none_and_unknown():
    assert ak.zone_for_value("DW", "StreamsLast7Days", None) is None
    assert ak.zone_for_value("DW", "NopeFeature", 1) is None
    assert ak.zone_for_value("RR", "NopeFeature", 1) is None  # unknown feature


def test_nearest_target_gap_and_reached():
    res = ak.nearest_target("DW", "StreamsLast7Days", 1800)
    assert res["target"] == 2000 and res["gap"] == pytest.approx(200) and res["reached"] is False
    res2 = ak.nearest_target("DW", "StreamsLast7Days", 2500)
    assert res2["reached"] is True
    # feature with no target → None
    assert ak.nearest_target("DW", "HowManySongsHasThisArtistEverReleased", 10) is None


def test_decode_feature_value_log_and_identity():
    feats = {
        "StreamsLast7Days_log": math.log1p(3000),
        "DaysSinceRelease": 42.0,
    }
    assert ak.decode_feature_value("DW", "StreamsLast7Days", feats) == pytest.approx(3000, rel=1e-6)
    assert ak.decode_feature_value("DW", "DaysSinceRelease", feats) == 42.0
    # absent key / empty
    assert ak.decode_feature_value("DW", "Velocity_Streams", feats) is None
    assert ak.decode_feature_value("DW", "StreamsLast7Days", {}) is None


def test_calibration_note_zones():
    assert "0%" in ak.calibration_note("DW", 0.05)
    assert ak.calibration_note("DW", 0.30) is not None
    assert "~50%" in ak.calibration_note("DW", 0.85)
    assert ak.calibration_note("RR", 0.85) is None  # no RR calibration curve exists
    assert ak.calibration_note("DW", None) is None


def test_feature_ids_covers_all_13_inference_features():
    # Every DW feature id must map to a real ml_inference FEATURE_COLUMNS entry.
    from src.utils.ml_inference import FEATURE_COLUMNS
    json_keys = {ak.DW_FEATURE_ZONES[f]["json_key"] for f in ak.feature_ids("DW")}
    assert json_keys == set(FEATURE_COLUMNS)


# ─────────────────────────────────────────────────────────────────────
# Radio — distinct zone shapes (esp. inverted DaysSinceRelease)
# ─────────────────────────────────────────────────────────────────────

def test_populated_algos_order():
    assert ak.populated_algos() == ["DW", "RR", "RADIO"]


def test_radio_feature_keys_are_valid_inference_columns():
    from src.utils.ml_inference import FEATURE_COLUMNS
    json_keys = {ak.RADIO_FEATURE_ZONES[f]["json_key"] for f in ak.feature_ids("RADIO")}
    assert json_keys <= set(FEATURE_COLUMNS)  # subset (Radio covers fewer features)


def test_radio_age_is_inverted_vs_dw():
    # New release: bonus for Radio (honeymoon), malus for DW (purgatory).
    assert ak.zone_for_value("RADIO", "DaysSinceRelease", 20) == "bonus"
    assert ak.zone_for_value("DW", "DaysSinceRelease", 20) == "malus"
    # Old release: malus for Radio (bonus removed), bonus for DW (golden age).
    assert ak.zone_for_value("RADIO", "DaysSinceRelease", 120) == "malus"
    assert ak.zone_for_value("DW", "DaysSinceRelease", 120) == "bonus"


def test_radio_catalog_green_mountain():
    assert ak.zone_for_value("RADIO", "HowManySongsHasThisArtistEverReleased", 15) == "bonus"
    assert ak.zone_for_value("RADIO", "HowManySongsHasThisArtistEverReleased", 5) == "malus"
    assert ak.zone_for_value("RADIO", "HowManySongsHasThisArtistEverReleased", 40) == "malus"


def test_radio_velocity_stricter_than_dw():
    # After the 2026-05-31 recalibration, Radio (malus >1.5) is stricter than DW
    # (malus only >3.5): 2.0 is suspect for Radio but still healthy for DW.
    assert ak.zone_for_value("RADIO", "Velocity_Streams", 2.0) == "malus"
    assert ak.zone_for_value("DW", "Velocity_Streams", 2.0) == "neutral"


def test_velocity_penalty_threshold_matches_zones():
    # Single source of truth for the hyper-growth cutoff used by the budget cross-link.
    assert ak.velocity_penalty_threshold("DW") == 3.5    # recalibrated (was 1.2)
    assert ak.velocity_penalty_threshold("RADIO") == 1.5
    # The threshold is exactly the malus boundary. Below it: DW=neutral, RADIO=bonus.
    assert ak.zone_for_value("DW", "Velocity_Streams", 3.5) == "malus"
    assert ak.zone_for_value("DW", "Velocity_Streams", 3.49) == "neutral"
    assert ak.zone_for_value("RADIO", "Velocity_Streams", 1.5) == "malus"
    assert ak.zone_for_value("RADIO", "Velocity_Streams", 1.49) == "bonus"


def test_radio_has_no_calibration_bands():
    assert ak.calibration_note("RADIO", 0.85) is None


def test_radio_scorecard_balanced_baseline():
    m = ak.ALGO_MODEL_METRICS["RADIO"]
    assert m["confusion"] == {"TN": 47, "FP": 7, "FN": 7, "TP": 41}
    assert m["baseline_accuracy"] < m["accuracy"]  # real lift, unlike DW


# ─────────────────────────────────────────────────────────────────────
# Release Radar — sourced from the rr_classifier SHAP zoom artifacts
# ─────────────────────────────────────────────────────────────────────

def test_rr_feature_keys_are_valid_inference_columns():
    from src.utils.ml_inference import FEATURE_COLUMNS
    json_keys = {ak.RR_FEATURE_ZONES[f]["json_key"] for f in ak.feature_ids("RR")}
    assert json_keys <= set(FEATURE_COLUMNS)  # subset (RR covers 6 features)


def test_rr_age_is_a_firing_window_not_a_cliff():
    # The SHAP zoom shows a "too fresh" dip before the 7-40d sweet window.
    assert ak.zone_for_value("RR", "DaysSinceRelease", 3) == "neutral"   # too fresh
    assert ak.zone_for_value("RR", "DaysSinceRelease", 20) == "bonus"    # window
    assert ak.zone_for_value("RR", "DaysSinceRelease", 90) == "malus"    # window closed


def test_rr_streams_peage_and_followers_vip_pass():
    assert ak.zone_for_value("RR", "StreamsLast7Days", 1000) == "malus"
    assert ak.zone_for_value("RR", "StreamsLast7Days", 3000) == "bonus"
    assert ak.zone_for_value("RR", "CurrentSpotifyFollowers", 500) == "malus"
    assert ak.zone_for_value("RR", "CurrentSpotifyFollowers", 3000) == "bonus"


def test_rr_release_cadence_rewards_spacing():
    # Opposite shape from DW: RR rewards SPACED releases (bonus at ~14 weeks).
    assert ak.zone_for_value("RR", "ReleaseConsistencyNum", 5) == "malus"
    assert ak.zone_for_value("RR", "ReleaseConsistencyNum", 15) == "bonus"


def test_rr_discovery_mode_is_flat():
    # Dead-flat SHAP: neither value moves the RR score.
    assert ak.zone_for_value("RR", "IsThisSongOptedIntoSpotifyDiscoveryMode", 0) == "neutral"
    assert ak.zone_for_value("RR", "IsThisSongOptedIntoSpotifyDiscoveryMode", 1) == "neutral"


def test_rr_playlist_adds_is_divergent_and_never_coached():
    # The negative SHAP is a chronological confound, not a lever: it must be
    # flagged divergent and excluded from prescriptive coach actions.
    spec = ak.RR_FEATURE_ZONES["PlaylistAddsLast28Days"]
    assert spec["divergent"] is True and spec["actionable"] is False
    # Even with a strongly "bad-looking" value, the coach must not raise it.
    feats = {"PlaylistAddsLast28Days_adj": 500.0}
    flagged = {a["feature"] for a in ak.build_coach_actions("RR", feats)}
    assert "PlaylistAddsLast28Days" not in flagged


def test_rr_has_no_calibration_bands():
    assert ak.calibration_note("RR", 0.85) is None


def test_rr_scorecard_matches_artifact():
    m = ak.ALGO_MODEL_METRICS["RR"]
    assert m["confusion"] == {"TN": 76, "FP": 6, "FN": 4, "TP": 16}
    assert m["auc"] == 0.961
    assert m["lift_top10"] == 5.1
    # n must equal the test sample and accuracy must beat the always-fail baseline.
    cm = m["confusion"]
    assert sum(cm.values()) == m["test_n"]
    assert m["baseline_accuracy"] < m["accuracy"]


def test_rr_coach_ranks_actionable_levers():
    # Below-threshold streams + followers are actionable raises; age & discovery
    # mode (actionable:False) and playlist adds (divergent) must be excluded.
    feats = {
        "StreamsLast7Days_log": math.log1p(800),       # below 2000 péage → raise
        "CurrentSpotifyFollowers_log": math.log1p(500),  # below 2300 → raise
        "DaysSinceRelease": 90.0,                        # malus but actionable:False
    }
    actions = ak.build_coach_actions("RR", feats)
    flagged = {a["feature"] for a in actions}
    assert {"StreamsLast7Days", "CurrentSpotifyFollowers"} <= flagged
    assert "DaysSinceRelease" not in flagged


# ─────────────────────────────────────────────────────────────────────
# Coach engine
# ─────────────────────────────────────────────────────────────────────

def test_coach_ranks_velocity_smooth_first():
    feats = {
        "StreamsLast7Days_log": math.log1p(1500),   # below DW péage 2000 → raise
        "Velocity_Streams": 4.0,                     # suspect peak >3.5 → smooth (top)
        "CurrentSpotifyFollowers_log": math.log1p(900),
    }
    actions = ak.build_coach_actions("DW", feats)
    assert actions, "expected at least one action"
    assert actions[0]["kind"] == "smooth" and actions[0]["feature"] == "Velocity_Streams"
    raises = [a for a in actions if a["kind"] == "raise"]
    assert {"StreamsLast7Days", "CurrentSpotifyFollowers"} <= {a["feature"] for a in raises}


def test_coach_excludes_non_actionable_and_unmeasured():
    feats = {"DaysSinceRelease": 10.0, "ReleasePhaseEarly": 1.0,
             "HowManySongsDoYouHaveInRadioRightNow": 0.0}  # all non-actionable/unmeasured
    actions = ak.build_coach_actions("DW", feats)
    feats_flagged = {a["feature"] for a in actions}
    assert "DaysSinceRelease" not in feats_flagged
    assert "ReleasePhaseEarly" not in feats_flagged
    assert "HowManySongsDoYouHaveInRadioRightNow" not in feats_flagged


def test_coach_empty_when_all_good():
    feats = {"StreamsLast7Days_log": math.log1p(8000), "Velocity_Streams": 0.6,
             "CurrentSpotifyFollowers_log": math.log1p(5000)}
    assert ak.build_coach_actions("DW", feats) == []


# ─────────────────────────────────────────────────────────────────────
# Cross-algo coherence guard — prevents the "reserved-but-empty slot" class
# (an algo wired into dispatch lists but missing zones/labels/valid features).
# ─────────────────────────────────────────────────────────────────────

def test_every_populated_algo_has_a_label():
    # populated_algos() must never surface an algo the UI can't name.
    for algo in ak.populated_algos():
        assert algo in ak.ALGO_LABELS, f"{algo} has feature zones but no ALGO_LABELS entry"


def test_all_feature_json_keys_are_valid_inference_columns():
    # Every feature of every algo must map to a real model input column, else the
    # gauge reads a key the model never sees (silent garbage).
    from src.utils.ml_inference import FEATURE_COLUMNS
    valid = set(FEATURE_COLUMNS)
    for algo, zones in ak.ALGO_FEATURE_ZONES.items():
        for fid, spec in zones.items():
            assert spec["json_key"] in valid, f"{algo}.{fid} → unknown key {spec['json_key']}"


def test_every_scorecard_is_internally_consistent():
    for algo, m in ak.ALGO_MODEL_METRICS.items():
        cm = m["confusion"]
        assert set(cm) == {"TN", "FP", "FN", "TP"}, f"{algo} confusion keys malformed"
        assert sum(cm.values()) == m["test_n"], f"{algo} confusion does not sum to test_n"
        assert 0.0 <= m["auc"] <= 1.0, f"{algo} AUC out of range"


def test_every_feature_zone_is_well_formed():
    # Zones must be ordered, non-overlapping, with valid verdicts — a malformed
    # zone would silently mis-color a gauge or break zone_for_value lookups.
    valid_verdicts = {"malus", "neutral", "bonus"}
    for algo, zones in ak.ALGO_FEATURE_ZONES.items():
        for fid, spec in zones.items():
            prev_high = 0
            for low, high, verdict, _note in spec["zones"]:
                assert verdict in valid_verdicts, f"{algo}.{fid} bad verdict {verdict}"
                assert low == prev_high, f"{algo}.{fid} zone gap/overlap at {low}"
                if high is not None:
                    assert high > low, f"{algo}.{fid} non-increasing zone bound"
                    prev_high = high


# ─────────────────────────────────────────────────────────────────────
# Volume (regressor) zones — distinct from the entry/classification zones
# ─────────────────────────────────────────────────────────────────────

def test_volume_algos_and_feature_ids():
    assert "DW" in ak.volume_algos()
    ids = ak.volume_feature_ids("DW")
    assert "NonAlgoStreams28Days" in ids and "StreamsLast7Days" in ids


def test_volume_zone_via_registry():
    reg = ak.ALGO_VOLUME_ZONES
    assert ak.zone_for_value("DW", "StreamsLast7Days", 3000, registry=reg) == "neutral"
    assert ak.zone_for_value("DW", "StreamsLast7Days", 8000, registry=reg) == "bonus"


def test_entry_and_volume_zones_differ_for_same_value():
    # Same 5500 streams: entry zone says bonus (>5000), volume zone says neutral (<6000).
    assert ak.zone_for_value("DW", "StreamsLast7Days", 5500) == "bonus"
    assert ak.zone_for_value("DW", "StreamsLast7Days", 5500,
                             registry=ak.ALGO_VOLUME_ZONES) == "neutral"


def test_volume_decode_via_registry():
    feats = {"StreamsLast7Days_log": math.log1p(7000)}
    val = ak.decode_feature_value("DW", "StreamsLast7Days", feats, registry=ak.ALGO_VOLUME_ZONES)
    assert val == pytest.approx(7000, rel=1e-6)


def test_volume_paradox_levers_are_flat():
    # Saves & PlaylistAdds buy the entry ticket but are flat for VOLUME.
    for fid in ("SavesLast28Days", "PlaylistAddsLast28Days"):
        spec = ak.ALGO_VOLUME_ZONES["DW"][fid]
        assert spec.get("volume_flat") is True
        assert all(v == "neutral" for _lo, _hi, v, _n in spec["zones"])


def test_volume_zones_well_formed():
    valid = {"malus", "neutral", "bonus"}
    for algo, zones in ak.ALGO_VOLUME_ZONES.items():
        for fid, spec in zones.items():
            prev_high = 0
            for low, high, verdict, _note in spec["zones"]:
                assert verdict in valid, f"{algo}.{fid} bad verdict {verdict}"
                assert low == prev_high, f"{algo}.{fid} zone gap/overlap at {low}"
                if high is not None:
                    assert high > low
                    prev_high = high
            assert spec["json_key"]  # must map to a model column key


def test_volume_scaling_threshold():
    assert ak.volume_scaling_threshold("DW") == 6000
    # RADIO has volume zones but no NonAlgoStreams28Days lever → threshold is None.
    assert ak.volume_scaling_threshold("RADIO") is None


def test_regressor_note_and_floor_disclaimer():
    assert ak.regressor_note("DW") is not None
    assert ak.regressor_note("RADIO") is not None
    # RR now carries a note explaining WHY its volume is suppressed (R²=0.32).
    assert ak.regressor_note("RR") is not None
    assert "plancher" in ak.FORECAST_FLOOR_DISCLAIMER.lower()


def test_volume_forecast_reliability_gate():
    # DW + Radio are trustworthy regressors → forecast shown.
    assert ak.volume_forecast_reliable("DW") is True
    assert ak.volume_forecast_reliable("RADIO") is True
    # RR (R²=0.32, notification-CTR noise) → forecast suppressed.
    assert ak.volume_forecast_reliable("RR") is False
    # Unknown algo defaults to reliable (no false suppression).
    assert ak.volume_forecast_reliable("UNKNOWN") is True


def test_volume_suppressed_note():
    # Reliable regressors expose no suppression note.
    assert ak.volume_suppressed_note("DW") is None
    assert ak.volume_suppressed_note("RADIO") is None
    # RR returns the classification-only caption shown instead of a forecast.
    note = ak.volume_suppressed_note("RR")
    assert note is not None and "AUC 0.96" in note


def test_radio_volume_zones_populated():
    assert "RADIO" in ak.volume_algos()
    ids = ak.volume_feature_ids("RADIO")
    assert "StreamsLast7Days" in ids
    # Superstar catalogue effect: the FIRST non-flat catalogue lever for volume.
    superstar = ak.ALGO_VOLUME_ZONES["RADIO"]["HowManySongsDoYouHaveInRadioRightNow"]
    assert superstar.get("volume_flat") is not True
    assert any(v == "bonus" for _lo, _hi, v, _n in superstar["zones"])
    # Imputed-to-0 in prod → must route to the pedagogic expander, not a live gauge.
    assert superstar.get("live_unavailable") is True


def test_radio_volume_paradox_levers_are_flat():
    # Discovery Mode + quality signals: entry tickets, flat for VOLUME.
    for fid in ("IsThisSongOptedIntoSpotifyDiscoveryMode", "SavesLast28Days",
                "PlaylistAddsLast28Days", "ListenersStreamRatio28Days"):
        spec = ak.ALGO_VOLUME_ZONES["RADIO"][fid]
        assert spec.get("volume_flat") is True
        assert all(v == "neutral" for _lo, _hi, v, _n in spec["zones"])


def test_radio_discovery_recovery_note():
    # Below cruising velocity → no advice.
    assert ak.radio_discovery_recovery_note({"StreamsLast7Days_log": math.log1p(5000)}) is None
    # At/above cruising velocity → margin-recovery advice mentioning the 30% royalties.
    note = ak.radio_discovery_recovery_note({"StreamsLast7Days_log": math.log1p(80000)})
    assert note is not None and "30%" in note
    # Missing feature → no advice (no crash).
    assert ak.radio_discovery_recovery_note({}) is None


def test_volume_feature_keys_are_valid_inference_columns():
    from src.utils.ml_inference import FEATURE_COLUMNS
    valid = set(FEATURE_COLUMNS)
    for algo, zones in ak.ALGO_VOLUME_ZONES.items():
        for fid, spec in zones.items():
            assert spec["json_key"] in valid, f"{algo}.{fid} → unknown key {spec['json_key']}"
