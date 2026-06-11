"""EN strings for the CPR Optimizer view."""

EN = {
    "meta_cpr_optimizer.subtitle": (
        "Composite ML × CPR score for each campaign. "
        "Based on `campaign_track_mapping` + `ml_song_predictions` + `meta_insights_performance`."
    ),
    "meta_cpr_optimizer.no_mapping": (
        "No campaign → track mapping found. "
        "Create mappings first in **🔗 Meta Mapping**, then re-run the Meta Ads DAG."
    ),
    "meta_cpr_optimizer.account_median": "Account median CPR: **{v}€**",
    "meta_cpr_optimizer.tab_cards": "🃏 Detailed recommendations",
    "meta_cpr_optimizer.tab_table": "📋 Table",
    "meta_cpr_optimizer.disclaimer": (
        "⚠️ These recommendations are indicative. "
        "The score is computed on the available data — "
        "the more collection days, the more reliable the score."
    ),
    # Recommendations
    "meta_cpr_optimizer.rec.increase_strong": "🟢 Increase",
    "meta_cpr_optimizer.rec.increase_light": "🟡 Increase",
    "meta_cpr_optimizer.rec.hold": "⚪ Hold",
    "meta_cpr_optimizer.rec.reduce": "🔴 Reduce",
    # Summary KPIs
    "meta_cpr_optimizer.kpi_analyzed": "Campaigns analysed",
    "meta_cpr_optimizer.kpi_no_cpr": "No CPR data",
    "meta_cpr_optimizer.kpi_no_cpr_help": "Mapped campaigns without Meta spend",
    "meta_cpr_optimizer.kpi_increase": "Increase recommended",
    "meta_cpr_optimizer.kpi_reduce": "Reduction recommended",
    # Table columns
    "meta_cpr_optimizer.col_action": "Action",
    "meta_cpr_optimizer.col_campaign": "Campaign",
    "meta_cpr_optimizer.col_track": "Linked track",
    "meta_cpr_optimizer.col_budget": "Suggested budget",
    "meta_cpr_optimizer.col_score": "Score",
    "meta_cpr_optimizer.col_current_cpr": "Current CPR",
    "meta_cpr_optimizer.col_spend": "Spend",
    "meta_cpr_optimizer.col_results": "Results",
    "meta_cpr_optimizer.col_ml_max": "ML max",
    # Detail cards
    "meta_cpr_optimizer.unknown": "unknown",
    "meta_cpr_optimizer.composite_score": "Composite score",
    "meta_cpr_optimizer.ml_prob": (
        "**Max ML probability**: {ml_max} (DW: {dw} | RR: {rr} | Radio: {radio})"
    ),
    "meta_cpr_optimizer.warn_no_cpr": (
        "No CPR data for this campaign — "
        "check that the Meta Ads campaign has results and that the CSV is imported."
    ),
    "meta_cpr_optimizer.msg_performing": (
        "✅ **Performing campaign**: low CPR ({cpr}) + strong ML potential ({ml}). "
        "Increase the budget by 30% to maximise the algo window."
    ),
    "meta_cpr_optimizer.msg_good": (
        "🟡 **Good ratio**: increase slightly (+10%) and monitor the CPR trend over 7 days."
    ),
    "meta_cpr_optimizer.msg_average": (
        "⚪ **Average performance**: keep the current budget and wait for more data."
    ),
    "meta_cpr_optimizer.msg_under": (
        "🔴 **Underperforming**: high CPR ({cpr}) and/or weak ML potential ({ml}). "
        "Reduce the budget by 30% or rework the creative and targeting."
    ),
}
