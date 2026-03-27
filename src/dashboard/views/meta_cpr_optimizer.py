"""Vue CPR Optimizer — Score ML × CPR + recommandations de budget.

Type: Feature
Uses: get_db_connection, get_artist_id, require_plan
Depends on: meta_insights_performance, campaign_track_mapping, ml_song_predictions
Score: max(dw_prob, rr_prob, radio_prob) × (cpr_median / cpr_campaign)
       → normalisé 0-10. Seuils: ≥7 → +30%, 5-7 → +10%, 3-5 → neutre, <3 → -30%.
"""
import streamlit as st
import pandas as pd

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, require_plan


# ── Seuils score ─────────────────────────────────────────────────────────────
_SCORE_THRESHOLDS = [
    (7.0,  "🟢 Augmenter",  "+30%",  "+30%",  "#28a745"),
    (5.0,  "🟡 Augmenter",  "+10%",  "+10%",  "#ffc107"),
    (3.0,  "⚪ Maintenir",  "=",     "=",     "#6c757d"),
    (0.0,  "🔴 Réduire",    "-30%",  "-30%",  "#dc3545"),
]


def _get_recommendation(score: float) -> tuple[str, str, str]:
    """Return (label, budget_delta, color) for a given score."""
    for threshold, label, delta, _, color in _SCORE_THRESHOLDS:
        if score >= threshold:
            return label, delta, color
    return "🔴 Réduire", "-30%", "#dc3545"


_QUERY_OPTIMIZER = """
SELECT
    ctm.campaign_name,
    ctm.track_name,
    COALESCE(mip.total_spend, 0)    AS total_spend,
    COALESCE(mip.total_results, 0)  AS total_results,
    mip.cpr,
    COALESCE(ml.dw_probability,    0) AS dw_prob,
    COALESCE(ml.rr_probability,    0) AS rr_prob,
    COALESCE(ml.radio_probability, 0) AS radio_prob
FROM campaign_track_mapping ctm
LEFT JOIN (
    SELECT
        campaign_name,
        SUM(spend)                                                         AS total_spend,
        SUM(results)                                                       AS total_results,
        CASE WHEN SUM(results) > 0
             THEN ROUND(SUM(spend)::numeric / SUM(results), 4)
             ELSE NULL END                                                 AS cpr
    FROM meta_insights_performance
    WHERE artist_id = %s
    GROUP BY campaign_name
) mip ON LOWER(mip.campaign_name) = LOWER(ctm.campaign_name)
LEFT JOIN (
    SELECT DISTINCT ON (song)
        song,
        dw_probability,
        rr_probability,
        radio_probability
    FROM ml_song_predictions
    WHERE artist_id = %s
    ORDER BY song, prediction_date DESC
) ml ON LOWER(ml.song) = LOWER(ctm.track_name)
WHERE ctm.artist_id = %s
ORDER BY mip.cpr ASC NULLS LAST
"""

_QUERY_ALL_CAMPAIGN_CPR = """
SELECT
    campaign_name,
    CASE WHEN SUM(results) > 0
         THEN SUM(spend)::numeric / SUM(results)
         ELSE NULL END AS cpr
FROM meta_insights_performance
WHERE artist_id = %s AND results > 0
GROUP BY campaign_name
"""


def _compute_scores(df: pd.DataFrame, cpr_median: float) -> pd.DataFrame:
    """Add score_raw, score_10, recommendation, budget_delta columns."""
    def _score_row(row) -> float:
        if pd.isna(row['cpr']) or row['cpr'] <= 0 or cpr_median <= 0:
            return 0.0
        ml_prob = max(row['dw_prob'], row['rr_prob'], row['radio_prob'])
        # Higher ML prob + lower CPR → higher score
        return float(ml_prob) * (cpr_median / row['cpr'])

    df = df.copy()
    df['score_raw'] = df.apply(_score_row, axis=1)
    # Normalize to 0-10 (cap at 10)
    max_raw = df['score_raw'].max()
    if max_raw > 0:
        df['score_10'] = (df['score_raw'] / max_raw * 10).clip(0, 10).round(1)
    else:
        df['score_10'] = 0.0

    recs = df['score_10'].apply(_get_recommendation)
    df['rec_label']  = recs.apply(lambda x: x[0])
    df['budget_delta'] = recs.apply(lambda x: x[1])
    df['rec_color']  = recs.apply(lambda x: x[2])
    return df


def _render_summary_kpi(df: pd.DataFrame) -> None:
    mapped = df[df['cpr'].notna()]
    unmapped = df[df['cpr'].isna()]
    n_increase = (df['budget_delta'].isin(['+30%', '+10%'])).sum()
    n_reduce = (df['budget_delta'] == '-30%').sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Campagnes analysées", len(mapped))
    col2.metric("Sans données CPR", len(unmapped), help="Campagnes mappées mais sans spend Meta")
    col3.metric("Recommandation hausse", int(n_increase))
    col4.metric("Recommandation réduction", int(n_reduce))


def _render_table(df: pd.DataFrame) -> None:
    display = df.copy()

    display['Score'] = display['score_10'].apply(lambda x: f"{x:.1f} / 10")
    display['CPR actuel'] = display['cpr'].apply(
        lambda x: f"{x:.2f}€" if pd.notna(x) else "—"
    )
    display['Dépense'] = display['total_spend'].apply(lambda x: f"{x:.2f}€")
    display['Résultats'] = display['total_results'].astype(int)
    display['ML max'] = display[['dw_prob', 'rr_prob', 'radio_prob']].max(axis=1).apply(
        lambda x: f"{x:.0%}"
    )

    st.dataframe(
        display[[
            'rec_label', 'campaign_name', 'track_name',
            'Score', 'CPR actuel', 'budget_delta',
            'Dépense', 'Résultats', 'ML max',
        ]].rename(columns={
            'rec_label':     'Action',
            'campaign_name': 'Campagne',
            'track_name':    'Track liée',
            'budget_delta':  'Budget suggéré',
        }),
        use_container_width=True,
        hide_index=True,
    )


def _render_detail_cards(df: pd.DataFrame) -> None:
    """Expandable cards per campaign with full explanation."""
    for _, row in df.iterrows():
        ml_max = max(row['dw_prob'], row['rr_prob'], row['radio_prob'])
        cpr_str = f"{row['cpr']:.2f}€" if pd.notna(row['cpr']) else "inconnu"
        score = row['score_10']
        label, delta, color = _get_recommendation(score)

        with st.expander(f"{label} — **{row['campaign_name']}** → {row['track_name']}"):
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Score composite", f"{score:.1f}/10")
            col_b.metric("CPR actuel", cpr_str)
            col_c.metric("Budget suggéré", delta)

            st.markdown(
                f"**Probabilité ML max** : {ml_max:.0%} "
                f"(DW: {row['dw_prob']:.0%} | RR: {row['rr_prob']:.0%} | Radio: {row['radio_prob']:.0%})"
            )

            if pd.isna(row['cpr']):
                st.warning(
                    "Pas de données CPR pour cette campagne — "
                    "vérifiez que la campagne Meta Ads a des résultats et que le CSV est importé."
                )
            elif score >= 7:
                st.success(
                    f"✅ **Campagne performante** : CPR bas ({cpr_str}) + fort potentiel ML ({ml_max:.0%}). "
                    "Augmenter le budget de 30% pour maximiser la fenêtre algo."
                )
            elif score >= 5:
                st.info(
                    f"🟡 **Bon rapport** : augmenter légèrement (+10%) et surveiller l'évolution du CPR sur 7 jours."
                )
            elif score >= 3:
                st.info("⚪ **Performance moyenne** : maintenir le budget actuel et attendre plus de données.")
            else:
                st.error(
                    f"🔴 **Sous-performante** : CPR élevé ({cpr_str}) et/ou faible potentiel ML ({ml_max:.0%}). "
                    "Réduire le budget de 30% ou revoir la créative et le ciblage."
                )


def show() -> None:
    if not require_plan('premium'):
        return

    st.title("📊 CPR Optimizer")
    st.caption(
        "Score composite ML × CPR pour chaque campagne. "
        "Basé sur `campaign_track_mapping` + `ml_song_predictions` + `meta_insights_performance`."
    )

    artist_id = get_artist_id() or 1
    db = get_db_connection()
    if db is None:
        st.error("Base de données inaccessible.")
        return

    try:
        df = db.fetch_df(_QUERY_OPTIMIZER, (artist_id, artist_id, artist_id))
        cpr_all = db.fetch_df(_QUERY_ALL_CAMPAIGN_CPR, (artist_id,))
    finally:
        db.close()

    if df.empty:
        st.info(
            "Aucun mapping campagne → track trouvé. "
            "Créez d'abord des mappings dans **🔗 Meta Mapping**, "
            "puis relancez le DAG Meta Ads."
        )
        return

    # CPR médian global (toutes campagnes avec données)
    cpr_median = float(cpr_all['cpr'].median()) if not cpr_all.empty else 1.0

    df = _compute_scores(df, cpr_median)

    st.markdown(f"CPR médian du compte : **{cpr_median:.2f}€**")
    st.markdown("---")

    _render_summary_kpi(df)
    st.markdown("---")

    tab_cards, tab_table = st.tabs(["🃏 Recommandations détaillées", "📋 Tableau"])

    with tab_cards:
        # Sort: increase first, then neutral, then reduce
        order = {'+30%': 0, '+10%': 1, '=': 2, '-30%': 3}
        df_sorted = df.assign(
            _order=df['budget_delta'].map(order)
        ).sort_values('_order').drop(columns='_order')
        _render_detail_cards(df_sorted)

    with tab_table:
        _render_table(df.sort_values('score_10', ascending=False))

    st.markdown("---")
    st.caption(
        "⚠️ Ces recommandations sont indicatives. "
        "Le score est calculé sur les données disponibles — "
        "plus il y a de jours de collecte, plus le score est fiable."
    )
