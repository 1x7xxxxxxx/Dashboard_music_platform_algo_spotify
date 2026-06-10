"""trigger_algo shared helpers — package split of the former _common.py (move-only)."""
from ._loaders import (
    _clean_feat, _compute_score_20, _load_feature_importance, _load_lifecycle_benchmark, _load_ml_pred, _load_scored_tracks, _load_threshold_tables, _load_xgb_model,
)
from ._pi_gates import (
    _PI_BINS, _pi_bracket, _show_pi_breakeven, _show_pi_gate_section,
)
from ._lifecycle import (
    _LIFECYCLE_AGE_BINS, _LIFECYCLE_LABELS, _LIFECYCLE_PALETTE, _age_week_order, _compute_age_weeks, _lifecycle_band_fig, _lifecycle_legend, _standardization_block,
)
from ._budget_roi import (
    _GATE_28D, _META_LEVER_QUERY, _TRIGGER_STREAM_TARGETS, _show_28d_gate, _show_budget_pacing_calculator, _show_budget_tier_selector, _show_meta_lever_scoring, _show_velocity_budget_advice,
)
from ._explain import (
    _DM_KEY, _FEATURE_LABELS, _IMPUTED_FEATURES, _MARKETING_ACTIONS, _show_drift_status, _show_imputation_caveat, _show_key_factors, _show_lime_explanation,
)
from ._verdict import (
    ELBOW_THRESHOLDS_28D, HEURISTIC_GOALS, _PHASES, _display_prob_bar, _show_discovery_mode_protocol, _show_feature_importance, _show_heuristic_section, _show_ml_section, _show_phase_strategy, _show_radio_snowball, _show_resurrection_radar, _show_verdict_banner,
)

__all__ = [
    'ELBOW_THRESHOLDS_28D', 'HEURISTIC_GOALS', '_DM_KEY', '_FEATURE_LABELS', '_GATE_28D', '_IMPUTED_FEATURES', '_LIFECYCLE_AGE_BINS', '_LIFECYCLE_LABELS', '_LIFECYCLE_PALETTE', '_MARKETING_ACTIONS', '_META_LEVER_QUERY', '_PHASES', '_PI_BINS', '_TRIGGER_STREAM_TARGETS', '_age_week_order', '_clean_feat', '_compute_age_weeks', '_compute_score_20', '_display_prob_bar', '_lifecycle_band_fig', '_lifecycle_legend', '_load_feature_importance', '_load_lifecycle_benchmark', '_load_ml_pred', '_load_scored_tracks', '_load_threshold_tables', '_load_xgb_model', '_pi_bracket', '_show_28d_gate', '_show_budget_pacing_calculator', '_show_budget_tier_selector', '_show_discovery_mode_protocol', '_show_drift_status', '_show_feature_importance', '_show_heuristic_section', '_show_imputation_caveat', '_show_key_factors', '_show_lime_explanation', '_show_meta_lever_scoring', '_show_ml_section', '_show_phase_strategy', '_show_pi_breakeven', '_show_pi_gate_section', '_show_radio_snowball', '_show_resurrection_radar', '_show_velocity_budget_advice', '_show_verdict_banner', '_standardization_block',
]
