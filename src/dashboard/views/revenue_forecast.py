"""Revenue Forecast — SaaS projections + artistic revenue forecast.

Type: Feature
Depends on: artist_subscriptions, subscription_plans, imusician_monthly_revenue, saas_artists
Persists in: read-only (no writes)

Admin : 4 tabs (MRR actuel, Projection MRR, LTV & Churn, Projection Artistique)
Artist: 1 tab (Projection Artistique — own data only)
"""
import sys
from pathlib import Path
from dateutil.relativedelta import relativedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.utils import algo_knowledge as ak
from src.dashboard.utils.i18n import t
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.revenue_forecast import (
    load_subscriptions as _load_subscriptions,
    load_artist_revenues as _load_artist_revenues,
    load_artist_revenue_by_source as _load_artist_revenue_by_source,
    load_artists as _load_artists,
    project_mrr,
    ltv_global,
    ltv_scenarios,
)
from src.database.stripe_schema import PLAN_CATALOG as _CAT


# DB loaders + forecast math now live in src/dashboard/utils/revenue_forecast.py
# (refactor R6 — calc/UI split). Imported above; call sites unchanged via aliases.


# ─────────────────────────────────────────────
# Tab 1 — MRR Actuel
# ─────────────────────────────────────────────

def _tab_mrr(db) -> None:
    st.subheader(t("revenue_forecast.mrr_header", "MRR actuel"))

    df = _load_subscriptions(db)
    if df.empty:
        st.info(t("revenue_forecast.no_subscriptions",
                  "Aucun abonnement trouvé dans la base. Connectez Stripe pour alimenter ces données."))
        return

    active = df[df['status'].isin(['active', 'trialing'])]
    paying = active[active['price'] > 0]

    total_mrr = float(paying['price'].sum())
    nb_paying  = len(paying)
    arpu       = total_mrr / nb_paying if nb_paying else 0.0
    nb_cancel  = int(active['cancel_at_period_end'].sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("revenue_forecast.mrr_total", "MRR total"), f"{total_mrr:,.2f} €")
    c2.metric("ARPU", f"{arpu:,.2f} €")
    c3.metric(t("revenue_forecast.paying_artists", "Artistes payants"), nb_paying)
    c4.metric(t("revenue_forecast.pending_cancellations", "Annulations en attente"),
              nb_cancel, delta=f"-{nb_cancel}" if nb_cancel else None,
              delta_color="inverse")

    st.markdown("---")

    # MRR par plan
    mrr_by_plan = (
        paying.groupby('plan')['price']
        .agg(['sum', 'count'])
        .reset_index()
        .rename(columns={'sum': 'mrr', 'count': 'artistes'})
    )
    if not mrr_by_plan.empty:
        fig = px.bar(
            mrr_by_plan, x='plan', y='mrr',
            text='mrr', color='plan',
            labels={'plan': 'Plan', 'mrr': 'MRR (€)'},
            color_discrete_sequence=['#1DB954', '#FF6B35', '#A855F7'],
        )
        fig.update_traces(texttemplate='%{text:.2f} €', textposition='outside')
        fig.update_layout(showlegend=False, yaxis_title='MRR (€)')
        st.plotly_chart(fig, width='stretch')

    st.markdown("---")
    st.subheader(t("revenue_forecast.subs_detail", "Détail des abonnements"))
    display = active[['artist_name', 'plan', 'price', 'status', 'cancel_at_period_end',
                       'current_period_end']].copy()
    display['current_period_end'] = pd.to_datetime(display['current_period_end']).dt.strftime('%Y-%m-%d')
    st.dataframe(
        display.rename(columns={
            'artist_name': t("common.artist", "Artiste"),
            'plan': 'Plan',
            'price': t("revenue_forecast.col_price", "Prix (€/mois)"),
            'status': t("revenue_forecast.col_status", "Statut"),
            'cancel_at_period_end': t("revenue_forecast.col_cancel", "Annulation fin période"),
            'current_period_end': t("revenue_forecast.col_period_end", "Fin de période"),
        }),
        width='stretch', hide_index=True,
    )


# ─────────────────────────────────────────────
# Tab 2 — Projection MRR
# ─────────────────────────────────────────────

def _tab_projection(db) -> None:
    st.subheader(t("revenue_forecast.growth_header", "Simulation de croissance MRR"))

    df = _load_subscriptions(db)
    active_paying = df[df['status'].isin(['active', 'trialing']) & (df['price'] > 0)]
    mrr_0 = float(active_paying['price'].sum()) if not active_paying.empty else 0.0

    st.caption(t("revenue_forecast.mrr_start",
                 "MRR de départ (réel) : **{mrr:,.2f} €**").format(mrr=mrr_0))
    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        growth_rate = st.slider(
            t("revenue_forecast.growth_rate", "Taux de croissance mensuel (%)"), 0, 30, 5)
        months      = st.select_slider(
            t("revenue_forecast.months_to_project", "Mois à projeter"),
            options=[6, 12, 24, 36], value=12)
    with c2:
        price_premium = st.number_input(
            t("revenue_forecast.premium_price", "Prix Premium (€/mois)"),
            value=float(_CAT['premium']['price_eur']), step=0.10, format="%.2f")

    # Recalc MRR0 avec prix custom (un seul plan payant : Premium)
    _p_premium = _CAT['premium']['price_eur']
    if not active_paying.empty:
        mrr_0_custom = float(
            active_paying['price'].map(
                lambda p: price_premium if abs(p - _p_premium) < 0.01 else p
            ).sum()
        )
    else:
        mrr_0_custom = mrr_0

    enterprise_on = st.toggle(t("revenue_forecast.enterprise_toggle", "Activer un plan Enterprise"))
    ent_price = ent_per_month = 0.0
    if enterprise_on:
        ec1, ec2 = st.columns(2)
        ent_price     = ec1.number_input(
            t("revenue_forecast.enterprise_price", "Prix Enterprise (€/mois)"),
            value=99.0, step=1.0)
        ent_per_month = ec2.number_input(
            t("revenue_forecast.enterprise_new_artists", "Nouveaux artistes Enterprise / mois"),
            value=1.0, step=0.5)

    mrr_target = st.number_input(
        t("revenue_forecast.mrr_target", "MRR cible (€) — ligne de référence"),
        value=500.0, step=50.0)

    # Build projection (pure math extracted to utils.revenue_forecast.project_mrr)
    proj = project_mrr(
        mrr_0_custom, growth_rate, months,
        enterprise_on=enterprise_on, ent_price=ent_price,
        ent_per_month=ent_per_month, mrr_target=mrr_target,
    )
    months_list, mrr_vals, arr_vals, target_month = (
        proj['months'], proj['mrr'], proj['arr'], proj['target_month'])

    proj_df = pd.DataFrame({'Mois': months_list, 'MRR (€)': mrr_vals, 'ARR (€)': arr_vals})

    r1, r2, r3 = st.columns(3)
    r1.metric(t("revenue_forecast.mrr_final", "MRR final"), f"{mrr_vals[-1]:,.2f} €")
    r2.metric(t("revenue_forecast.arr_final", "ARR final"), f"{arr_vals[-1]:,.2f} €")
    if target_month is not None:
        r3.metric(t("revenue_forecast.months_to_target", "Mois pour atteindre la cible"), f"M+{target_month}")
    else:
        r3.metric(t("revenue_forecast.months_to_target", "Mois pour atteindre la cible"), "—",
                  help=t("revenue_forecast.target_not_reached",
                         "MRR cible {target:,.0f} € non atteint sur {months} mois").format(target=mrr_target, months=months))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=months_list, y=mrr_vals, mode='lines+markers',
        name='MRR projeté', line=dict(color='#1DB954', width=2),
    ))
    fig.add_hline(
        y=mrr_target, line_dash='dot', line_color='orange',
        annotation_text=f"Cible : {mrr_target:,.0f} €",
        annotation_position='top left',
    )
    if target_month is not None:
        fig.add_vline(
            x=months_list[target_month], line_dash='dash', line_color='orange',
            annotation_text=f"M+{target_month}",
        )
    fig.update_layout(xaxis_title='Mois', yaxis_title='MRR (€)', hovermode='x unified')
    st.plotly_chart(fig, width='stretch')

    with st.expander(t("revenue_forecast.projection_table", "Tableau de projection détaillé")):
        st.dataframe(proj_df, width='stretch', hide_index=True)


# ─────────────────────────────────────────────
# Tab 3 — LTV & Churn
# ─────────────────────────────────────────────

def _tab_ltv(db) -> None:
    st.subheader(t("revenue_forecast.ltv_header", "LTV & Churn"))

    df = _load_subscriptions(db)
    active = df[df['status'].isin(['active', 'trialing'])]
    paying = active[active['price'] > 0]

    total_mrr = float(paying['price'].sum()) if not paying.empty else 0.0
    nb_paying  = len(paying)
    arpu       = total_mrr / nb_paying if nb_paying else 0.0
    nb_cancel  = int(active['cancel_at_period_end'].sum()) if not active.empty else 0
    nb_total   = len(active)
    churn_from_db = (nb_cancel / nb_total * 100) if nb_total > 0 else 0.0

    st.markdown(t("revenue_forecast.ltv_classic_header", "#### LTV classique (ARPU ÷ churn mensuel)"))

    if churn_from_db < 0.5:
        st.info(t("revenue_forecast.churn_low",
                  "Taux de churn détecté < 0.5% (peu d'annulations en attente). Ajustez manuellement :"))
        churn_rate = st.slider(t("revenue_forecast.churn_estimated", "Taux de churn mensuel estimé (%)"),
                               1.0, 20.0, 5.0, step=0.5)
    else:
        churn_rate = st.slider(
            t("revenue_forecast.churn_monthly", "Taux de churn mensuel (%)"),
            1.0, 20.0, round(churn_from_db, 1), step=0.5,
            help=t("revenue_forecast.churn_help",
                   "Valeur estimée depuis les annulations en attente : {churn:.1f}%").format(churn=churn_from_db),
        )

    ltv_val = ltv_global(arpu, churn_rate)

    c1, c2, c3 = st.columns(3)
    c1.metric("ARPU", f"{arpu:,.2f} €")
    c2.metric(t("revenue_forecast.churn_monthly_metric", "Churn mensuel"), f"{churn_rate:.1f}%")
    c3.metric(t("revenue_forecast.ltv_global", "LTV globale"), f"{ltv_val:,.2f} €")

    st.markdown("---")
    st.markdown(t("revenue_forecast.ltv_scenario_header", "#### LTV par scénario de durée de rétention"))

    plans = [('premium', _CAT['premium']['price_eur'])]
    durations = [6, 12, 24, 36]
    ltv_df = pd.DataFrame(ltv_scenarios(plans, durations))

    fig = px.bar(
        ltv_df, x='LTV (€)', y='Durée (mois)', color='Plan',
        orientation='h', barmode='group',
        color_discrete_sequence=['#1DB954', '#A855F7'],
        labels={'LTV (€)': 'LTV estimée (€)', 'Durée (mois)': 'Rétention'},
        text='LTV (€)',
    )
    fig.update_traces(texttemplate='%{text:.0f} €', textposition='outside')
    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, width='stretch')

    st.markdown("---")
    st.markdown(t("revenue_forecast.ltv_artistic_header", "#### LTV artistique (revenus musicaux × durée)"))
    st.caption(t("revenue_forecast.ltv_artistic_caption",
                 "Proxy : valeur musicale moyenne d'un artiste, basée sur l'historique distributeurs + SACEM."))

    avg_row = db.fetch_query("""
        SELECT AVG(monthly_avg) FROM (
            SELECT artist_id, AVG(month_total) AS monthly_avg FROM (
                SELECT artist_id, year, month, SUM(revenue_eur) AS month_total
                FROM v_artist_monthly_revenue GROUP BY artist_id, year, month
            ) m GROUP BY artist_id
        ) t
    """)
    avg_music = float(avg_row[0][0]) if avg_row and avg_row[0][0] else 0.0

    retention = st.select_slider(
        t("revenue_forecast.retention_hypothetical", "Durée de rétention hypothétique (mois)"),
        options=[6, 12, 24, 36], value=12, key='ltv_retention',
    )
    ltv_music = avg_music * retention

    mc1, mc2 = st.columns(2)
    mc1.metric(t("revenue_forecast.avg_music_revenue", "Revenu musical moyen / mois / artiste"), f"{avg_music:,.2f} €")
    mc2.metric(t("revenue_forecast.ltv_artistic_metric", "LTV artistique sur {months} mois").format(months=retention),
               f"{ltv_music:,.2f} €")


# ─────────────────────────────────────────────
# Tab 4 — Projection Artistique
# ─────────────────────────────────────────────

def _tab_artist_forecast(db, artist_id: int | None, show_infra: bool = False) -> None:
    # show_infra=True only for admin: the VPS/server cost is the platform operator's,
    # not the artist's, so the artist margin = revenue − their own ad spend (no VPS).
    st.subheader(t("revenue_forecast.artist_forecast_header",
                   "Projection des revenus musicaux (iMusician + DistroKid + SACEM)"))
    st.caption(t("revenue_forecast.artist_forecast_caption",
                 "Revenus musicaux mensuels consolidés : distributeurs (iMusician + "
                 "DistroKid) + royalties brutes SACEM."))

    if is_admin():
        artists_df = _load_artists(db)
        if artists_df.empty:
            st.warning(t("revenue_forecast.no_active_artist", "Aucun artiste actif."))
            return
        opts = {row['name']: row['id'] for _, row in artists_df.iterrows()}
        sel  = st.selectbox(t("common.artist", "Artiste"), list(opts.keys()), key='forecast_artist')
        target_id = opts[sel]
    else:
        target_id = artist_id
        if target_id is None:
            st.error(t("revenue_forecast.no_artist_id", "Impossible de déterminer votre identifiant artiste."))
            return

    # ── Revenus cumulés par source (rend SACEM visible, pas juste sommé) ──
    by_src = _load_artist_revenue_by_source(db, target_id)
    if any(v for v in by_src.values()):
        st.markdown(t("revenue_forecast.by_source_header", "**Revenus cumulés par source**"))
        bs1, bs2, bs3 = st.columns(3)
        bs1.metric("💿 iMusician", f"{by_src.get('iMusician', 0):,.2f} €")
        bs2.metric("🟢 DistroKid", f"{by_src.get('DistroKid', 0):,.2f} €")
        bs3.metric("🎼 SACEM", f"{by_src.get('SACEM', 0):,.2f} €")

    df = _load_artist_revenues(db, target_id)

    if df.empty or len(df) < 3:
        st.info(
            t("revenue_forecast.insufficient_data",
              "Données insuffisantes pour une projection (minimum 3 mois d'historique "
              "distributeurs/SACEM requis). Importez vos CSV/XLSX depuis **Import CSV**.")
        )
        return

    df['date'] = pd.to_datetime(
        df.apply(lambda r: f"{int(r['year'])}-{int(r['month']):02d}-01", axis=1)
    )
    df = df.sort_values('date').reset_index(drop=True)
    df['revenue_eur'] = df['revenue_eur'].astype(float)
    if 'sacem_eur' in df.columns:
        df['sacem_eur'] = pd.to_numeric(df['sacem_eur'], errors='coerce').fillna(0.0)

    # Regression
    X = np.arange(len(df))
    Y = df['revenue_eur'].values
    slope, intercept = np.polyfit(X, Y, 1)
    y_fit = slope * X + intercept
    residuals = Y - y_fit
    std_res = float(np.std(residuals))

    horizon = st.select_slider(t("revenue_forecast.horizon", "Horizon de projection (mois)"),
                               options=[3, 6, 12], value=6)

    # Projection dates + values
    last_idx = len(df) - 1
    proj_indices = np.arange(last_idx + 1, last_idx + 1 + horizon)
    proj_values  = slope * proj_indices + intercept
    last_date    = df['date'].iloc[-1]
    proj_dates   = [last_date + relativedelta(months=i) for i in range(1, horizon + 1)]

    # KPIs
    avg_revenue    = float(Y.mean())
    final_forecast = float(proj_values[-1])
    k1, k2, k3 = st.columns(3)
    k1.metric(t("revenue_forecast.avg_monthly_revenue", "Revenu moyen mensuel"), f"{avg_revenue:,.2f} €")
    k2.metric(t("revenue_forecast.trend", "Tendance"), f"{slope:+.2f} €/mois")
    k3.metric(t("revenue_forecast.projection_metric", "Projection M+{horizon}").format(horizon=horizon),
              f"{final_forecast:,.2f} €",
              delta=t("revenue_forecast.vs_average", "{delta:+.2f} € vs moyenne").format(delta=final_forecast - avg_revenue))

    # Chart
    fig = go.Figure()

    # Historical (total revenue)
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['revenue_eur'],
        mode='lines+markers', name=t("revenue_forecast.line_total", "Total (tous distributeurs)"),
        line=dict(color='#1DB954', width=2),
        marker=dict(size=6),
    ))

    # SACEM royalties evolution (distinct line)
    if 'sacem_eur' in df.columns and df['sacem_eur'].sum() > 0:
        fig.add_trace(go.Scatter(
            x=df['date'], y=df['sacem_eur'],
            mode='lines+markers', name=t("revenue_forecast.line_sacem", "🎼 Royalties SACEM"),
            line=dict(color='#8E44AD', width=1.5), marker=dict(size=5),
        ))

    # Fit line over history
    fig.add_trace(go.Scatter(
        x=df['date'], y=y_fit.tolist(),
        mode='lines', name='Tendance',
        line=dict(color='#1DB954', width=1, dash='dot'),
        opacity=0.6,
    ))

    # Projection + confidence band
    upper = [v + std_res for v in proj_values]
    lower = [max(0.0, v - std_res) for v in proj_values]

    fig.add_trace(go.Scatter(
        x=proj_dates + proj_dates[::-1],
        y=upper + lower[::-1],
        fill='toself', fillcolor='rgba(255,107,53,0.15)',
        line=dict(color='rgba(255,107,53,0)'),
        name='Intervalle ±1σ', hoverinfo='skip',
    ))
    fig.add_trace(go.Scatter(
        x=proj_dates, y=proj_values.tolist(),
        mode='lines+markers', name='Projection',
        line=dict(color='#FF6B35', width=2, dash='dash'),
        marker=dict(size=5),
    ))

    fig.update_layout(
        xaxis_title='Mois', yaxis_title='Revenus (€)',
        hovermode='x unified', legend=dict(orientation='h', y=-0.2),
    )
    st.plotly_chart(fig, width='stretch')

    with st.expander(t("revenue_forecast.historical_data", "Données historiques")):
        display = df[['date', 'revenue_eur']].copy()
        display['date'] = display['date'].dt.strftime('%Y-%m')
        st.dataframe(
            display.rename(columns={
                'date': t("revenue_forecast.col_month", "Mois"),
                'revenue_eur': t("revenue_forecast.col_revenue", "Revenus (€)"),
            }),
            width='stretch', hide_index=True,
        )

    # ── Meta Ads ROI historique ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown(t("revenue_forecast.meta_roi_header", "### 💸 Meta Ads — ROI historique"))

    from src.dashboard.utils.kpi_helpers import get_monthly_roi_series
    from_date = df['date'].iloc[0].date()
    to_date   = df['date'].iloc[-1].date()

    roi_df = get_monthly_roi_series(db, target_id, from_date, to_date)

    if roi_df.empty or roi_df['meta_spend'].sum() == 0:
        st.info(t("revenue_forecast.no_meta_spend",
                  "Aucune dépense Meta Ads trouvée pour cet artiste sur la période. "
                  "Connectez Meta via **Credentials API** et déclenchez le DAG Meta Insights."))
    else:
        roi_df = roi_df.sort_values('period_date')
        # VRAI ROI = (revenus − dépenses) / dépenses × 100 (0 % = équilibre).
        roi_df['roi_pct'] = roi_df.apply(
            lambda r: round((r['revenue_eur'] - r['meta_spend']) / r['meta_spend'] * 100, 1)
            if r['meta_spend'] > 0 else None,
            axis=1,
        )
        total_rev   = float(roi_df['revenue_eur'].sum())
        total_spend = float(roi_df['meta_spend'].sum())
        global_roi  = round((total_rev - total_spend) / total_spend * 100, 1) if total_spend > 0 else 0.0
        avg_spend   = float(roi_df['meta_spend'].mean())

        rc1, rc2, rc3 = st.columns(3)
        rc1.metric(t("revenue_forecast.total_meta_spend", "Dépense Meta totale"), f"{total_spend:,.2f} €")
        rc2.metric(t("revenue_forecast.total_imusician_revenue", "Revenu iMusician total"), f"{total_rev:,.2f} €")
        rc3.metric(t("revenue_forecast.global_roi", "ROI global"), f"{global_roi:.1f}%",
                   delta=t("revenue_forecast.profitable", "rentable") if global_roi >= 0
                   else t("revenue_forecast.loss_making", "déficitaire"),
                   delta_color="normal" if global_roi >= 0 else "inverse")

        fig_roi = go.Figure()
        fig_roi.add_trace(go.Bar(
            x=roi_df['period_date'], y=roi_df['revenue_eur'],
            name='Revenus (€)', marker_color='#1DB954',
        ))
        fig_roi.add_trace(go.Bar(
            x=roi_df['period_date'], y=roi_df['meta_spend'],
            name='Dépense Meta (€)', marker_color='#FF6B35',
        ))
        fig_roi.add_trace(go.Scatter(
            x=roi_df['period_date'], y=roi_df['roi_pct'],
            name='ROI (%)', yaxis='y2', mode='lines+markers',
            line=dict(color='#A855F7', width=2), marker=dict(size=5),
        ))
        fig_roi.update_layout(
            barmode='group', hovermode='x unified',
            yaxis=dict(title='€'),
            yaxis2=dict(title='ROI (%)', overlaying='y', side='right'),
            legend=dict(orientation='h', y=-0.2),
        )
        st.plotly_chart(fig_roi, width='stretch')

    # ── ML — scores par track ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(t("revenue_forecast.ml_header", "### 🤖 Prédictions ML — scores par track"))

    try:
        ml_df = db.fetch_df(
            """
            SELECT DISTINCT ON (song)
                song,
                prediction_date,
                dw_probability,
                rr_probability,
                radio_probability,
                dw_streams_forecast_7d,
                rr_streams_forecast_7d,
                radio_streams_forecast_7d,
                streams_7d,
                streams_28d
            FROM ml_song_predictions
            WHERE artist_id = %s
              AND song NOT ILIKE '%%1x7xxxxxxx%%'
            ORDER BY song, prediction_date DESC
            """,
            (target_id,),
        )
    except Exception:
        ml_df = pd.DataFrame()

    if ml_df.empty:
        st.info(t("revenue_forecast.no_ml",
                  "Aucune prédiction ML disponible. Déclenchez le DAG **ml_scoring_daily** "
                  "depuis **Monitoring ETL** ou l'UI Airflow."))
    else:
        ml_df = ml_df.sort_values('dw_probability', ascending=False).reset_index(drop=True)
        ml_df['prediction_date'] = pd.to_datetime(ml_df['prediction_date']).dt.strftime('%Y-%m-%d')

        # Probabilities can be NULL (a model that fails to score writes None →
        # the Series becomes object dtype, and .round() would raise TypeError).
        # Coerce to numeric and render NaN as a dash. Mirrors ml_performance.py.
        for col in ['dw_probability', 'rr_probability', 'radio_probability']:
            if col in ml_df.columns:
                pct = (pd.to_numeric(ml_df[col], errors='coerce') * 100).round(1)
                ml_df[col] = pct.map(lambda v: f"{v}%" if pd.notna(v) else "—")

        # RR volume regressor is unreliable (R²=0.32) — drop its floor column so the ROI
        # table never shows a Release Radar stream forecast (classification-only by design).
        if not ak.volume_forecast_reliable("RR"):
            ml_df = ml_df.drop(columns=['rr_streams_forecast_7d'], errors='ignore')

        st.caption(
            t("revenue_forecast.ml_caption",
              "🛡️ Les colonnes *plancher* sont des **estimations worst-case** : le modèle "
              "de volume sous-estime les hits, le potentiel réel est souvent supérieur. "
              "Le Release Radar n'a pas de colonne volume : son débit dépend du taux "
              "d'ouverture des notifications (non prédictible) — on s'appuie sur sa "
              "classification (AUC 0.94, validée par chanson).")
        )
        st.dataframe(
            ml_df.rename(columns={
                'song': t("revenue_forecast.col_track", "Track"),
                'prediction_date': t("revenue_forecast.col_last_prediction", "Dernière prédiction"),
                'dw_probability': t("revenue_forecast.col_dw_prob", "Discovery Weekly (%)"),
                'rr_probability': t("revenue_forecast.col_rr_prob", "Release Radar (%)"),
                'radio_probability': t("revenue_forecast.col_radio_prob", "Radio (%)"),
                'dw_streams_forecast_7d': t("revenue_forecast.col_dw_streams", "Streams DW 7j (plancher ≥)"),
                'rr_streams_forecast_7d': t("revenue_forecast.col_rr_streams", "Streams RR 7j (plancher ≥)"),
                'radio_streams_forecast_7d': t("revenue_forecast.col_radio_streams", "Streams Radio 7j (plancher ≥)"),
                'streams_7d': t("revenue_forecast.col_streams_7d", "Streams 7j (réels)"),
                'streams_28d': t("revenue_forecast.col_streams_28d", "Streams 28j (réels)"),
            }),
            width='stretch', hide_index=True,
        )

    # ── Marge nette projetée ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(t("revenue_forecast.margin_header", "### 📊 Marge nette projetée"))
    st.caption(t("revenue_forecast.margin_caption",
                 "Sur l'horizon de projection sélectionné : **{horizon} mois**").format(horizon=horizon))

    _meta_default = (round(avg_spend, 2)
                     if not roi_df.empty and roi_df['meta_spend'].sum() > 0 else 50.0)
    if show_infra:
        nc1, nc2 = st.columns(2)
        vps_cost_monthly = nc1.number_input(
            t("revenue_forecast.vps_cost", "Coût infra VPS (€/mois)"), min_value=0.0,
            value=20.0, step=1.0,
            help=t("revenue_forecast.vps_cost_help",
                   "Coût mensuel du serveur (VPS, Railway, Docker host…)"))
        meta_spend_monthly_est = nc2.number_input(
            t("revenue_forecast.meta_spend_est", "Dépense Meta estimée (€/mois)"),
            min_value=0.0, value=_meta_default, step=10.0,
            help=t("revenue_forecast.meta_spend_est_help",
                   "Pré-rempli avec la moyenne historique. Ajustable."))
    else:
        # Artist: only their own ad spend; the VPS/server cost belongs to the operator.
        vps_cost_monthly = 0.0
        meta_spend_monthly_est = st.number_input(
            t("revenue_forecast.meta_spend_est", "Dépense Meta estimée (€/mois)"),
            min_value=0.0, value=_meta_default, step=10.0,
            help=t("revenue_forecast.meta_spend_est_help",
                   "Pré-rempli avec la moyenne historique. Ajustable."))

    proj_revenue_total = float(sum(
        max(0.0, slope * (last_idx + 1 + i) + intercept)
        for i in range(1, horizon + 1)
    ))
    proj_meta_total = meta_spend_monthly_est * horizon
    proj_vps_total  = vps_cost_monthly * horizon
    proj_margin     = proj_revenue_total - proj_meta_total - proj_vps_total

    margin_delta = dict(
        delta=t("revenue_forecast.profitable", "rentable") if proj_margin >= 0
        else t("revenue_forecast.loss_making", "déficitaire"),
        delta_color="normal" if proj_margin >= 0 else "inverse")

    if show_infra:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(t("revenue_forecast.projected_revenue", "Revenus projetés"), f"{proj_revenue_total:,.2f} €")
        m2.metric(t("revenue_forecast.meta_spend_metric", "Dépense Meta"), f"-{proj_meta_total:,.2f} €")
        m3.metric(t("revenue_forecast.vps_infra", "Infra VPS"), f"-{proj_vps_total:,.2f} €")
        m4.metric(t("revenue_forecast.net_margin", "Marge nette"), f"{proj_margin:,.2f} €", **margin_delta)
        wf_x = ['Revenus projetés', 'Dépense Meta', 'Infra VPS', 'Marge nette']
        wf_measure = ['absolute', 'relative', 'relative', 'total']
        wf_y = [proj_revenue_total, -proj_meta_total, -proj_vps_total, proj_margin]
        wf_text = [f"{proj_revenue_total:,.0f} €", f"-{proj_meta_total:,.0f} €",
                   f"-{proj_vps_total:,.0f} €", f"{proj_margin:,.0f} €"]
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric(t("revenue_forecast.projected_revenue", "Revenus projetés"), f"{proj_revenue_total:,.2f} €")
        m2.metric(t("revenue_forecast.meta_spend_metric", "Dépense Meta"), f"-{proj_meta_total:,.2f} €")
        m3.metric(t("revenue_forecast.net_margin", "Marge nette"), f"{proj_margin:,.2f} €", **margin_delta)
        wf_x = ['Revenus projetés', 'Dépense Meta', 'Marge nette']
        wf_measure = ['absolute', 'relative', 'total']
        wf_y = [proj_revenue_total, -proj_meta_total, proj_margin]
        wf_text = [f"{proj_revenue_total:,.0f} €", f"-{proj_meta_total:,.0f} €", f"{proj_margin:,.0f} €"]

    fig_margin = go.Figure(go.Waterfall(
        orientation='v', measure=wf_measure, x=wf_x, y=wf_y,
        connector=dict(line=dict(color='rgb(63, 63, 63)')),
        decreasing=dict(marker=dict(color='#FF6B35')),
        increasing=dict(marker=dict(color='#1DB954')),
        totals=dict(marker=dict(color='#A855F7')),
        text=wf_text, textposition='outside',
    ))
    fig_margin.update_layout(
        title=f"Waterfall marge nette sur {horizon} mois",
        yaxis_title='€', showlegend=False,
    )
    st.plotly_chart(fig_margin, width='stretch')


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def show() -> None:
    from src.dashboard.auth import require_plan
    if not is_admin() and not require_plan('premium'):
        return

    st.title(t("revenue_forecast.title", "📈 Prévisions revenus"))

    db = get_db_connection()
    try:
        if is_admin():
            tab_mrr, tab_proj, tab_ltv, tab_artist = st.tabs([
                t("revenue_forecast.tab_mrr", "📊 MRR Actuel"),
                t("revenue_forecast.tab_projection", "🔮 Projection MRR"),
                t("revenue_forecast.tab_ltv", "💎 LTV & Churn"),
                t("revenue_forecast.tab_artist", "🎵 Projection Artistique"),
            ])
            with tab_mrr:
                _tab_mrr(db)
            with tab_proj:
                _tab_projection(db)
            with tab_ltv:
                _tab_ltv(db)
            with tab_artist:
                _tab_artist_forecast(db, artist_id=None, show_infra=True)
        else:
            st.caption(t("revenue_forecast.artist_caption",
                         "Projection de vos revenus musicaux (iMusician + DistroKid + SACEM)."))
            _tab_artist_forecast(db, artist_id=get_artist_id(), show_infra=False)
    finally:
        db.close()
