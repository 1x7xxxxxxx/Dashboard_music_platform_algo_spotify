"""Vue Créatives Meta Ads — Classement des créatives par CPR.

Type: Feature
Uses: get_db_connection, get_artist_id, require_plan
Depends on: meta_ads, meta_insights, meta_campaigns tables (API-based)
Persists in: read-only
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.dashboard.utils import view_session
from src.dashboard.utils.ui import smart_date_range
from src.dashboard.utils.i18n import t
from src.dashboard.auth import require_plan

# All-creatives daily series (for the heatmap + cumulative-budget charts).
_QUERY_TS_ALL = """
SELECT ma.ad_name AS creative_name, mi.date::date AS date,
       SUM(mi.spend) AS spend
FROM meta_insights mi
JOIN meta_ads ma ON ma.ad_id = mi.ad_id
WHERE ma.artist_id = %s
GROUP BY ma.ad_name, mi.date
ORDER BY mi.date
"""


# Each metric gets its own Y-axis (scales differ wildly: € vs thousands of impressions).
# (label, column, weekly-resample aggregation, colour, visible-by-default, derived)
# Non-default metrics start as 'legendonly' → the chart opens readable; click the
# legend to toggle any metric (and its axis) on/off. `derived` metrics (CPR) are NOT
# fetched/resampled directly — they are recomputed from aggregated columns afterwards.
# Labels are FR sources, translated at render time via t(f"meta_creatives.metric.{col}").
_TIMELINE_METRICS = [
    ("Dépense (€)", "spend",       "sum",  "#ff6b35", True,  False),
    ("Impressions", "impressions", "sum",  "#1f77b4", True,  False),
    ("Clics",       "clicks",      "sum",  "#2ca02c", False, False),
    ("Reach",       "reach",       "sum",  "#9467bd", False, False),
    ("Résultats",   "conversions", "sum",  "#d62728", False, False),
    ("CTR (%)",     "ctr",         "mean", "#e6b800", False, False),
    ("CPR (€)",     "cpr",         None,   "#17becf", True,  True),
]


# total_results = the ad set goal's native result (mi.conversions, objective-aware).
# CPR is shown ONLY for conversion goals (cost-per-result on an engagement/traffic ad
# would imply a conversion that didn't happen — see collector _CONVERSION_GOALS).
_CONVERSION_GOALS_SQL = "('OFFSITE_CONVERSIONS','ONSITE_CONVERSIONS','LEAD_GENERATION','QUALITY_LEAD')"

_QUERY_CREATIVES = f"""
SELECT
    ma.ad_name                                                          AS creative_name,
    mc.campaign_name,
    SUM(mi.spend)                                                       AS total_spend,
    SUM(mi.conversions)                                                 AS total_results,
    CASE WHEN BOOL_OR(ads.optimization_goal IN {_CONVERSION_GOALS_SQL})
              AND SUM(mi.conversions) > 0
         THEN ROUND(SUM(mi.spend)::numeric / SUM(mi.conversions), 2)
         ELSE NULL END                                                  AS cpr,
    ROUND(AVG(mi.ctr) * 100, 2)                                        AS avg_ctr,
    SUM(mi.reach)                                                       AS total_reach,
    SUM(mi.impressions)                                                 AS total_impressions,
    SUM(mi.clicks)                                                      AS total_clicks,
    MAX(mc.start_time)                                                  AS campaign_start,
    MAX(ma.created_time)                                                AS creative_created
FROM meta_ads ma
JOIN meta_insights mi ON mi.ad_id = ma.ad_id
JOIN meta_campaigns mc ON mc.campaign_id = ma.campaign_id
LEFT JOIN meta_adsets ads ON ads.adset_id = ma.adset_id
WHERE ma.artist_id = %s
GROUP BY ma.ad_name, mc.campaign_name
HAVING SUM(mi.spend) > 0
ORDER BY cpr ASC NULLS LAST, total_results DESC
"""

# Campaigns whose ads exist in meta_ads but have NO ad-level insights — absent
# from the CPR ranking above. `campaign_spend` is the CAMPAIGN-level spend from
# meta_insights_performance_day: when > 0 the campaign DID deliver and was
# collected at campaign level, but the per-creative (ad-level) breakdown is
# missing (incremental window passed, or ads archived/deleted on Meta) and needs
# a full-history backfill. When 0, the campaign simply never spent.
_QUERY_UNCOLLECTED = """
SELECT mc.campaign_name,
       COUNT(DISTINCT ma.ad_id)        AS ads,
       COALESCE(cl.campaign_spend, 0)  AS campaign_spend
FROM meta_campaigns mc
JOIN meta_ads ma ON ma.campaign_id = mc.campaign_id
LEFT JOIN meta_insights mi ON mi.ad_id = ma.ad_id
LEFT JOIN (
    SELECT campaign_name, SUM(spend) AS campaign_spend
    FROM meta_insights_performance_day
    WHERE artist_id = %s
    GROUP BY campaign_name
) cl ON cl.campaign_name = mc.campaign_name
WHERE mc.artist_id = %s
GROUP BY mc.campaign_name, cl.campaign_spend
HAVING COALESCE(SUM(mi.spend), 0) = 0
ORDER BY cl.campaign_spend DESC NULLS LAST, mc.campaign_name
"""


def _render_uncollected_notice(uncollected: pd.DataFrame) -> None:
    """Warn about campaigns with ads but no ad-level (per-creative) insights."""
    if uncollected is None or uncollected.empty:
        return
    df = uncollected.dropna(subset=['campaign_name'])
    if df.empty:
        return
    # Split: delivered (campaign-level spend exists, only ad-level missing) vs
    # never-spent (no delivery at all).
    spent = df['campaign_spend'].astype(float) > 0
    n_delivered = int(spent.sum())
    n_total = len(df)

    with st.expander(
        t("meta_creatives.uncollected_title",
          "⚠️ {n} campagne(s) absente(s) du classement par créative").format(n=n_total),
        expanded=False,
    ):
        if n_delivered:
            st.markdown(t(
                "meta_creatives.uncollected_body",
                "**{n} campagne(s) ont bien dépensé** (collectées au niveau "
                "campagne) mais **leur détail par créative (ad-level) n'a pas été "
                "collecté**. Cas typique : campagne **en pause ou archivée** — ses "
                "publicités passent en statut `CAMPAIGN_PAUSED`/`ARCHIVED` et ne sont "
                "rechargées que par une collecte **full-history complète** (qui re-fetche "
                "la config ads, pas seulement les insights) :\n"
                "- Airflow → DAG `meta_ads_api_daily` → *Trigger DAG w/ config* "
                "`{{\"full_history\": true}}` (run **non** `insights_only`), ou\n"
                "- en local : `python airflow/debug_dag/debug_meta_ads_api.py --full-history --write`\n\n"
                "_Réserves :_ (1) le détail par créative n'est récupérable que si les "
                "publicités existent encore côté Meta (non supprimées) ; (2) Meta ne "
                "conserve les insights que **~37 mois** — au-delà, seul le total campagne "
                "reste disponible."
            ).format(n=n_delivered))
        col_spend = t("meta_creatives.col_campaign_spend", "Dépense campagne (€)")
        st.dataframe(
            df.rename(columns={
                'campaign_name': t("meta_creatives.col_campaign", "Campagne"),
                'ads': t("meta_creatives.col_ads", "Publicités"),
                'campaign_spend': col_spend,
            }).style.format({col_spend: '{:,.2f} €'}, na_rep='—'),
            hide_index=True, width="stretch",
        )


def _badge(cpr: float, median: float) -> str:
    if pd.isna(cpr):
        return t("meta_creatives.badge_no_result", "⚫ Pas de résultat")
    # cpr arrives as Decimal (Postgres numeric); median as numpy float from
    # .median() — coerce both to float so the division can't raise on mixed types.
    cpr = float(cpr)
    median = float(median) if pd.notna(median) else 0.0
    ratio = cpr / median if median > 0 else 1.0
    if ratio <= 0.75:
        return t("meta_creatives.badge_top", "🟢 Top créative")
    if ratio <= 1.25:
        return t("meta_creatives.badge_avg", "🟡 Dans la moyenne")
    return t("meta_creatives.badge_under", "🔴 Sous-performante")


def _render_kpi_row(df: pd.DataFrame) -> None:
    top = df[df['cpr'].notna()]
    if top.empty:
        return
    best = top.iloc[0]
    worst = top.iloc[-1]
    median_cpr = top['cpr'].median()
    total_spend = df['total_spend'].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("meta_creatives.total_spend", "Dépense totale"), f"{total_spend:.2f}€")
    col2.metric(t("meta_creatives.best_cpr", "Meilleure CPR"), f"{best['cpr']:.2f}€", delta=best['creative_name'][:30], delta_color="off")
    col3.metric(t("meta_creatives.median_cpr", "CPR médian"), f"{median_cpr:.2f}€")
    col4.metric(t("meta_creatives.worst_cpr", "Pire CPR"), f"{worst['cpr']:.2f}€", delta=worst['creative_name'][:30], delta_color="off")


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
            'statut': t("meta_creatives.col_status", "Statut"),
            'creative_name': t("meta_creatives.col_creative", "Créative"),
            'campaign_name': t("meta_creatives.col_campaign", "Campagne"),
            'cpr': 'CPR',
            'total_spend': t("meta_creatives.col_spend", "Dépense"),
            'total_results': t("meta_creatives.col_results", "Résultats"),
            'avg_ctr': t("meta_creatives.col_avg_ctr", "CTR moyen"),
            'total_reach': 'Reach',
        }),
        width="stretch",
        hide_index=True,
    )


def _render_bar_chart(df: pd.DataFrame) -> None:
    chart_df = df[df['cpr'].notna()].copy()
    if chart_df.empty:
        return
    # cpr is Postgres NUMERIC → Decimal; Altair can't infer its vegalite type and
    # warns "I don't know how to infer vegalite type from 'decimal'". Coerce to float.
    chart_df['cpr'] = pd.to_numeric(chart_df['cpr'], errors='coerce').astype(float)
    chart_df = chart_df.set_index('creative_name')[['cpr']].rename(columns={'cpr': 'CPR (€)'})
    st.bar_chart(chart_df, color="#ff6b35")


def _render_creative_timeline(db, artist_id: int, selected_campaign: str) -> None:
    """Per-creative multi-metric timeline (one Y-axis per metric, legend toggle).

    The creative list honours the page's campaign filter. The period filter is
    data-bounded (smart_date_range). Each metric has its own Y-axis; non-default
    metrics start collapsed and are toggled via the legend.
    """
    st.markdown("---")
    st.subheader(t("meta_creatives.timeline_title", "📈 Évolution d'une créative dans le temps"))

    # Honour the page-level campaign filter for the creative dropdown.
    campaign_clause = "" if selected_campaign == "Toutes" else " AND mc.campaign_name = %s"
    name_params = (artist_id,) if selected_campaign == "Toutes" else (artist_id, selected_campaign)
    names = db.fetch_df(
        f"""SELECT ma.ad_name, MAX(ma.created_time) AS last_created
            FROM meta_ads ma
            JOIN meta_insights mi ON mi.ad_id = ma.ad_id
            JOIN meta_campaigns mc ON mc.campaign_id = ma.campaign_id
            WHERE ma.artist_id = %s AND ma.ad_name IS NOT NULL{campaign_clause}
            GROUP BY ma.ad_name
            ORDER BY last_created DESC NULLS LAST, ma.ad_name""",
        name_params,
    )
    if names.empty:
        st.info(t("meta_creatives.no_adlevel_insights",
                  "Aucune créative avec des insights ad-level pour cette sélection."))
        return

    creative = st.selectbox(t("meta_creatives.creative", "Créative"),
                            names['ad_name'].tolist(), key="tl_creative")

    ts = db.fetch_df(
        f"""SELECT mi.date::date AS date,
                   SUM(mi.spend)       AS spend,
                   SUM(mi.impressions) AS impressions,
                   SUM(mi.clicks)      AS clicks,
                   SUM(mi.reach)       AS reach,
                   SUM(mi.conversions) AS conversions,
                   AVG(mi.ctr)         AS ctr
            FROM meta_insights mi
            JOIN meta_ads ma ON ma.ad_id = mi.ad_id
            JOIN meta_campaigns mc ON mc.campaign_id = ma.campaign_id
            WHERE ma.artist_id = %s AND ma.ad_name = %s{campaign_clause}
            GROUP BY mi.date ORDER BY mi.date""",
        (artist_id, creative) if selected_campaign == "Toutes"
        else (artist_id, creative, selected_campaign),
    )
    if ts.empty:
        st.info(t("meta_creatives.no_timeseries", "Pas de séries temporelles pour cette créative."))
        return
    ts['date'] = pd.to_datetime(ts['date'])

    d_from, d_to = smart_date_range(t("common.period", "Période"),
                                    ts['date'].min(), ts['date'].max(), key="tl")
    mask = (ts['date'] >= pd.Timestamp(d_from)) & (ts['date'] <= pd.Timestamp(d_to))
    tsf = ts.loc[mask].copy()
    if tsf.empty:
        st.info(t("meta_creatives.no_data_period", "Aucune donnée sur la période sélectionnée."))
        return

    # Decimal (Postgres NUMERIC) → float, else Plotly mis-types the columns.
    for _, col, _, _, _, derived in _TIMELINE_METRICS:
        if not derived:
            tsf[col] = pd.to_numeric(tsf[col], errors='coerce').astype(float)
    tsf['ctr'] = tsf['ctr'] * 100  # match the ranking table's CTR % convention

    # Smart granularity: weekly down-sampling past ~120 days keeps the lines readable.
    span_days = int((tsf['date'].max() - tsf['date'].min()).days)
    if span_days > 120:
        agg_map = {col: agg for _, col, agg, _, _, derived in _TIMELINE_METRICS if not derived}
        tsf = tsf.set_index('date').resample('W').agg(agg_map).reset_index()
        granularity = t("meta_creatives.granularity_weekly", "hebdomadaire")
    else:
        granularity = t("meta_creatives.granularity_daily", "journalière")

    # CPR derived from AGGREGATED spend/results (never an average of daily CPRs).
    # NaN where no result on the period → the line simply gaps there.
    tsf['cpr'] = (tsf['spend'] / tsf['conversions'].where(tsf['conversions'] != 0)).astype(float)

    # One Y-axis per metric (autoshift spreads them so they don't overlap). Legend
    # click toggles a metric and its axis; non-default metrics open as 'legendonly'.
    fig = go.Figure()
    layout = {"hovermode": "x unified", "xaxis": {"title": ""},
              "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02,
                         "xanchor": "right", "x": 1},
              "margin": {"t": 40}}
    for i, (label, col, _, color, visible, _) in enumerate(_TIMELINE_METRICS):
        label_t = t(f"meta_creatives.metric.{col}", label)
        axis_id = "y" if i == 0 else f"y{i + 1}"
        fig.add_trace(go.Scatter(
            x=tsf['date'], y=tsf[col], name=label_t, mode="lines+markers",
            line={"color": color}, marker={"color": color},
            yaxis=axis_id, visible=True if visible else "legendonly",
        ))
        axis_key = "yaxis" if i == 0 else f"yaxis{i + 1}"
        axis_cfg = {"title": {"text": label_t, "font": {"color": color}},
                    "tickfont": {"color": color}}
        if i > 0:
            axis_cfg.update({"overlaying": "y", "side": "right" if i % 2 else "left",
                             "anchor": "free", "autoshift": True})
        layout[axis_key] = axis_cfg
    fig.update_layout(**layout)
    st.plotly_chart(fig, width="stretch")
    st.caption(t(
        "meta_creatives.timeline_caption",
        "Créative **{creative}** · granularité {granularity} · {d_from} → {d_to}. "
        "Cliquez une métrique dans la légende pour l'afficher/masquer (double-clic = isoler)."
    ).format(creative=creative, granularity=granularity,
             d_from=f"{d_from:%d/%m/%Y}", d_to=f"{d_to:%d/%m/%Y}"))


def _render_scatter(df: pd.DataFrame) -> None:
    """#1 — bubble comparison: spend × CPR, size=impressions, color=CTR."""
    d = df.copy()
    for c in ('total_spend', 'cpr', 'total_impressions', 'avg_ctr'):
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d.dropna(subset=['total_spend', 'cpr'])
    if d.empty:
        st.info(t("meta_creatives.no_scatter", "Aucune créative avec un CPR (résultats) pour ce scatter."))
        return
    fig = px.scatter(
        d, x='total_spend', y='cpr', size='total_impressions', color='avg_ctr',
        hover_name='creative_name', color_continuous_scale='Viridis', size_max=40,
        labels={'total_spend': t("meta_creatives.spend_eur", "Dépense (€)"), 'cpr': 'CPR (€)',
                'avg_ctr': t("meta_creatives.avg_ctr_pct", "CTR moyen (%)"),
                'total_impressions': t("meta_creatives.impressions", "Impressions")},
    )
    fig.update_layout(height=460)
    st.plotly_chart(fig, width="stretch")
    st.caption(t("meta_creatives.scatter_caption",
                 "Une bulle = une créative. Bas = CPR efficace ; taille = impressions, couleur = CTR. "
                 "Les créatives sans résultat (CPR absent) ne sont pas tracées."))


def _render_efficiency(df: pd.DataFrame) -> None:
    """#4 — CTR / CPM / CPC per creative (top 15 by spend)."""
    d = df.copy()
    d['total_spend'] = pd.to_numeric(d['total_spend'], errors='coerce').fillna(0.0)
    d['total_impressions'] = pd.to_numeric(d['total_impressions'], errors='coerce').fillna(0)
    d['total_clicks'] = pd.to_numeric(d['total_clicks'], errors='coerce').fillna(0)
    d['CTR (%)'] = pd.to_numeric(d['avg_ctr'], errors='coerce')
    d['CPM (€)'] = (d['total_spend'] / d['total_impressions'].where(d['total_impressions'] != 0) * 1000).astype(float)
    d['CPC (€)'] = (d['total_spend'] / d['total_clicks'].where(d['total_clicks'] != 0)).astype(float)
    d = d.sort_values('total_spend', ascending=False).head(15)
    metric = st.radio(t("meta_creatives.indicator", "Indicateur"), ["CTR (%)", "CPM (€)", "CPC (€)"], horizontal=True, key="eff_metric")
    fig = px.bar(d, x='creative_name', y=metric, color=metric,
                 color_continuous_scale='Tealrose', labels={'creative_name': ''})
    fig.update_layout(height=420, coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch")


def _render_funnel(df: pd.DataFrame) -> None:
    """#3 — Impressions → Clics → Résultats funnel for one creative."""
    names = (df.dropna(subset=['creative_name'])
               .sort_values('creative_created', ascending=False, na_position='last')
               ['creative_name'].drop_duplicates().tolist())
    if not names:
        st.info(t("meta_creatives.no_creative", "Aucune créative."))
        return
    sel = st.selectbox(t("meta_creatives.creative", "Créative"), names, key="funnel_creative")
    r = df[df['creative_name'] == sel].iloc[0]
    imp = int(pd.to_numeric(r['total_impressions'], errors='coerce') or 0)
    clk = int(pd.to_numeric(r['total_clicks'], errors='coerce') or 0)
    res = int(pd.to_numeric(r['total_results'], errors='coerce') or 0)
    fig = go.Figure(go.Funnel(
        y=[t("meta_creatives.impressions", "Impressions"),
           t("meta_creatives.clicks", "Clics"),
           t("meta_creatives.results", "Résultats")], x=[imp, clk, res],
        textinfo="value+percent initial", marker={'color': ['#1f77b4', '#2ca02c', '#ff6b35']},
    ))
    fig.update_layout(height=400)
    st.plotly_chart(fig, width="stretch")


def _render_fatigue(db, artist_id: int) -> None:
    """#2 — frequency (↗) vs CTR (↘) over time: ad-fatigue detector."""
    names = db.fetch_df(
        """SELECT ma.ad_name, MAX(ma.created_time) AS last_created
           FROM meta_ads ma JOIN meta_insights mi ON mi.ad_id = ma.ad_id
           WHERE ma.artist_id = %s AND ma.ad_name IS NOT NULL
           GROUP BY ma.ad_name ORDER BY last_created DESC NULLS LAST, ma.ad_name""",
        (artist_id,),
    )
    if names.empty:
        st.info(t("meta_creatives.no_creative", "Aucune créative."))
        return
    sel = st.selectbox(t("meta_creatives.creative", "Créative"), names['ad_name'].tolist(), key="fatigue_creative")
    ts = db.fetch_df(
        """SELECT mi.date::date AS date, AVG(mi.frequency) AS frequency, AVG(mi.ctr) * 100 AS ctr
           FROM meta_insights mi JOIN meta_ads ma ON ma.ad_id = mi.ad_id
           WHERE ma.artist_id = %s AND ma.ad_name = %s GROUP BY mi.date ORDER BY mi.date""",
        (artist_id, sel),
    )
    if ts.empty:
        st.info(t("meta_creatives.no_timeseries", "Pas de séries temporelles pour cette créative."))
        return
    ts['date'] = pd.to_datetime(ts['date'])
    ts['frequency'] = pd.to_numeric(ts['frequency'], errors='coerce').astype(float)
    ts['ctr'] = pd.to_numeric(ts['ctr'], errors='coerce').astype(float)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ts['date'], y=ts['frequency'], name=t("meta_creatives.frequency", "Fréquence"),
                             mode='lines+markers', line={'color': '#d62728'}))
    fig.add_trace(go.Scatter(x=ts['date'], y=ts['ctr'], name='CTR (%)', yaxis='y2',
                             mode='lines+markers', line={'color': '#1f77b4'}))
    fig.update_layout(
        hovermode="x unified",
        yaxis={'title': {'text': t("meta_creatives.frequency", "Fréquence"), 'font': {'color': '#d62728'}}},
        yaxis2={'title': {'text': 'CTR (%)', 'font': {'color': '#1f77b4'}},
                'overlaying': 'y', 'side': 'right'},
        legend={'orientation': 'h', 'y': 1.02, 'x': 1, 'xanchor': 'right'}, height=420,
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(t("meta_creatives.fatigue_caption",
                 "Fréquence qui monte **et** CTR qui baisse = audience saturée (fatigue) → renouveler la créative."))


def _render_activity(ts_all: pd.DataFrame) -> None:
    """#5 heatmap (creative × week) + #6 cumulative spend area."""
    if ts_all is None or ts_all.empty:
        st.info(t("meta_creatives.no_spend_series", "Aucune série de dépense par créative."))
        return
    d = ts_all.copy()
    d['date'] = pd.to_datetime(d['date'])
    d['spend'] = pd.to_numeric(d['spend'], errors='coerce').fillna(0.0)
    d['week'] = d['date'].dt.to_period('W').dt.start_time

    weekly = d.groupby(['creative_name', 'week'], as_index=False)['spend'].sum()
    top = weekly.groupby('creative_name')['spend'].sum().nlargest(20).index
    hm = weekly[weekly['creative_name'].isin(top)]
    st.markdown(t("meta_creatives.heatmap_title", "**🗓️ Dépense par créative et par semaine**"))
    fig = px.density_heatmap(
        hm, x='week', y='creative_name', z='spend', histfunc='sum',
        color_continuous_scale='Oranges',
        labels={'week': '', 'creative_name': '', 'spend': t("meta_creatives.spend_eur", "Dépense (€)")},
    )
    fig.update_layout(height=520)
    st.plotly_chart(fig, width="stretch")

    st.markdown("---")
    st.markdown(t("meta_creatives.cumulative_title", "**💰 Dépense cumulée par créative**"))
    g = weekly.sort_values('week').copy()
    g['cum'] = g.groupby('creative_name')['spend'].cumsum()
    top12 = g.groupby('creative_name')['cum'].max().nlargest(12).index
    g = g[g['creative_name'].isin(top12)]
    fig2 = px.area(g, x='week', y='cum', color='creative_name',
                   labels={'week': '', 'cum': t("meta_creatives.cumulative_spend_eur", "Dépense cumulée (€)"),
                           'creative_name': t("meta_creatives.creative", "Créative")})
    fig2.update_layout(height=480)
    st.plotly_chart(fig2, width="stretch")


def show() -> None:
    if not require_plan('premium'):
        return

    st.title(t("meta_creatives.title", "🎨 Créatives Meta Ads"))
    st.caption(t("meta_creatives.subtitle",
                 "Classement de vos créatives par CPR — basé sur les données Meta Ads API (meta_ads × meta_insights)."))

    with view_session() as (db, artist_id):
        df = db.fetch_df(_QUERY_CREATIVES, (artist_id,))
        uncollected = db.fetch_df(_QUERY_UNCOLLECTED, (artist_id, artist_id))

        _render_uncollected_notice(uncollected)

        if df.empty:
            st.info(t(
                "meta_creatives.no_data",
                "Aucune donnée de créative disponible. "
                "Vérifiez que le DAG **meta_ads_api_daily** a bien collecté des données "
                "via l'API Meta Ads (tables `meta_ads` + `meta_insights`)."
            ))
            return

        # Filtres — campagnes les plus récentes en haut (par start_time desc).
        camp_order = (
            df.dropna(subset=['campaign_name'])
              .sort_values('campaign_start', ascending=False, na_position='last')
              ['campaign_name'].drop_duplicates().tolist()
        )
        # "Toutes" stays the internal sentinel value; only its display is translated.
        campaigns = ["Toutes"] + camp_order
        col_filter, _ = st.columns([2, 4])
        selected_campaign = col_filter.selectbox(
            t("meta_creatives.filter_by_campaign", "Filtrer par campagne"), campaigns,
            format_func=lambda c: t("meta_creatives.all_campaigns", "Toutes") if c == "Toutes" else c)

        if selected_campaign != "Toutes":
            df = df[df['campaign_name'] == selected_campaign]

        if df.empty:
            st.warning(t("meta_creatives.no_creative_campaign", "Aucune créative pour cette campagne."))
            return

        _render_kpi_row(df)
        st.markdown("---")

        t_rank, t_cmp, t_funnel, t_evo, t_fatigue, t_act = st.tabs([
            t("meta_creatives.tab_ranking", "📋 Classement"),
            t("meta_creatives.tab_compare", "🫧 Comparaison"),
            t("meta_creatives.tab_funnel", "🔻 Funnel"),
            t("meta_creatives.tab_evolution", "📈 Évolution"),
            t("meta_creatives.tab_fatigue", "🪫 Fatigue"),
            t("meta_creatives.tab_activity", "🗓️ Activité"),
        ])

        with t_rank:
            _render_table(df)
            median_cpr = df[df['cpr'].notna()]['cpr'].median()
            if pd.notna(median_cpr):
                st.caption(t(
                    "meta_creatives.badge_legend",
                    "🟢 Top créative = CPR ≤ {low}€ | "
                    "🟡 Moyenne = CPR ≤ {high}€ | "
                    "🔴 Sous-performante = CPR > {high}€"
                ).format(low=f"{median_cpr * 0.75:.2f}", high=f"{median_cpr * 1.25:.2f}"))
            st.markdown("---")
            _render_bar_chart(df)

        with t_cmp:
            _render_scatter(df)
            st.markdown("---")
            _render_efficiency(df)

        with t_funnel:
            _render_funnel(df)

        with t_evo:
            _render_creative_timeline(db, artist_id, selected_campaign)

        with t_fatigue:
            _render_fatigue(db, artist_id)

        with t_act:
            ts_all = db.fetch_df(_QUERY_TS_ALL, (artist_id,))
            _render_activity(ts_all)
