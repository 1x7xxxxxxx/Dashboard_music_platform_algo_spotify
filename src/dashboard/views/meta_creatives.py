"""Vue Créatives Meta Ads — Classement des créatives par CPR.

Type: Feature
Uses: get_db_connection, get_artist_id, require_plan
Depends on: meta_ads, meta_insights, meta_campaigns tables (API-based)
Persists in: read-only
"""
import streamlit as st
import pandas as pd

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, require_plan


_QUERY_CREATIVES = """
SELECT
    ma.ad_name                                                          AS creative_name,
    mc.campaign_name,
    SUM(mi.spend)                                                       AS total_spend,
    SUM(mi.conversions)                                                 AS total_results,
    CASE WHEN SUM(mi.conversions) > 0
         THEN ROUND(SUM(mi.spend)::numeric / SUM(mi.conversions), 2)
         ELSE NULL END                                                  AS cpr,
    ROUND(AVG(mi.ctr) * 100, 2)                                        AS avg_ctr,
    SUM(mi.reach)                                                       AS total_reach,
    SUM(mi.impressions)                                                 AS total_impressions
FROM meta_ads ma
JOIN meta_insights mi ON mi.ad_id = ma.ad_id
JOIN meta_campaigns mc ON mc.campaign_id = ma.campaign_id
WHERE ma.artist_id = %s
GROUP BY ma.ad_name, mc.campaign_name
HAVING SUM(mi.spend) > 0
ORDER BY
    CASE WHEN SUM(mi.conversions) > 0
         THEN SUM(mi.spend) / SUM(mi.conversions)
         ELSE 999999 END ASC
"""


def _badge(cpr: float, median: float) -> str:
    if pd.isna(cpr):
        return "⚫ Pas de résultat"
    ratio = cpr / median if median > 0 else 1.0
    if ratio <= 0.75:
        return "🟢 Top créative"
    if ratio <= 1.25:
        return "🟡 Dans la moyenne"
    return "🔴 Sous-performante"


def _render_kpi_row(df: pd.DataFrame) -> None:
    top = df[df['cpr'].notna()]
    if top.empty:
        return
    best = top.iloc[0]
    worst = top.iloc[-1]
    median_cpr = top['cpr'].median()
    total_spend = df['total_spend'].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Dépense totale", f"{total_spend:.2f}€")
    col2.metric("Meilleure CPR", f"{best['cpr']:.2f}€", delta=best['creative_name'][:30], delta_color="off")
    col3.metric("CPR médian", f"{median_cpr:.2f}€")
    col4.metric("Pire CPR", f"{worst['cpr']:.2f}€", delta=worst['creative_name'][:30], delta_color="off")


def _render_table(df: pd.DataFrame) -> None:
    median_cpr = df[df['cpr'].notna()]['cpr'].median()

    display = df.copy()
    display['statut'] = display['cpr'].apply(lambda x: _badge(x, median_cpr))
    display['cpr'] = display['cpr'].apply(lambda x: f"{x:.2f}€" if pd.notna(x) else "—")
    display['total_spend'] = display['total_spend'].apply(lambda x: f"{x:.2f}€")
    display['avg_ctr'] = display['avg_ctr'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "—")
    display['total_reach'] = display['total_reach'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "—")

    st.dataframe(
        display[['statut', 'creative_name', 'campaign_name', 'cpr',
                 'total_spend', 'total_results', 'avg_ctr', 'total_reach']].rename(columns={
            'statut': 'Statut',
            'creative_name': 'Créative',
            'campaign_name': 'Campagne',
            'cpr': 'CPR',
            'total_spend': 'Dépense',
            'total_results': 'Résultats',
            'avg_ctr': 'CTR moyen',
            'total_reach': 'Reach',
        }),
        use_container_width=True,
        hide_index=True,
    )


def _render_bar_chart(df: pd.DataFrame) -> None:
    chart_df = df[df['cpr'].notna()].copy()
    if chart_df.empty:
        return
    chart_df = chart_df.set_index('creative_name')[['cpr']].rename(columns={'cpr': 'CPR (€)'})
    st.bar_chart(chart_df, color="#ff6b35")


def show() -> None:
    if not require_plan('premium'):
        return

    st.title("🎨 Créatives Meta Ads")
    st.caption("Classement de vos créatives par CPR — basé sur les données Meta Ads API (meta_ads × meta_insights).")

    artist_id = get_artist_id() or 1
    db = get_db_connection()
    if db is None:
        st.error("Base de données inaccessible.")
        return

    try:
        df = db.fetch_df(_QUERY_CREATIVES, (artist_id,))
    finally:
        db.close()

    if df.empty:
        st.info(
            "Aucune donnée de créative disponible. "
            "Vérifiez que le DAG **meta_insights_dag** a bien collecté des données "
            "via l'API Meta Ads (tables `meta_ads` + `meta_insights`)."
        )
        return

    # Filtres
    campaigns = ["Toutes"] + sorted(df['campaign_name'].dropna().unique().tolist())
    col_filter, _ = st.columns([2, 4])
    selected_campaign = col_filter.selectbox("Filtrer par campagne", campaigns)

    if selected_campaign != "Toutes":
        df = df[df['campaign_name'] == selected_campaign]

    if df.empty:
        st.warning("Aucune créative pour cette campagne.")
        return

    _render_kpi_row(df)
    st.markdown("---")

    tab_table, tab_chart = st.tabs(["📋 Tableau", "📊 Graphique CPR"])

    with tab_table:
        _render_table(df)
        median_cpr = df[df['cpr'].notna()]['cpr'].median()
        st.caption(
            f"🟢 Top créative = CPR ≤ {median_cpr * 0.75:.2f}€ | "
            f"🟡 Moyenne = CPR ≤ {median_cpr * 1.25:.2f}€ | "
            f"🔴 Sous-performante = CPR > {median_cpr * 1.25:.2f}€"
        )

    with tab_chart:
        _render_bar_chart(df)
        st.caption("Créatives triées du meilleur au pire CPR. Barres plus courtes = plus efficaces.")
