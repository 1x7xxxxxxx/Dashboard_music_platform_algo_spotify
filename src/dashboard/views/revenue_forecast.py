"""Revenue Forecast — SaaS projections + artistic revenue forecast.

Type: Feature
Depends on: artist_subscriptions, subscription_plans, imusician_monthly_revenue, saas_artists
Persists in: read-only (no writes)

Admin : 4 tabs (MRR actuel, Projection MRR, LTV & Churn, Projection Artistique)
Artist: 1 tab (Projection Artistique — own data only)
"""
import sys
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin


# ─────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────

def _load_subscriptions(db) -> pd.DataFrame:
    return db.fetch_df("""
        SELECT
            sa.name            AS artist_name,
            sp.name            AS plan,
            sp.price_monthly   AS price,
            asub.status,
            asub.cancel_at_period_end,
            asub.current_period_start,
            asub.current_period_end
        FROM artist_subscriptions asub
        JOIN subscription_plans sp  ON sp.id  = asub.plan_id
        JOIN saas_artists        sa  ON sa.id  = asub.artist_id
        ORDER BY sp.price_monthly DESC, sa.name
    """)


def _load_artist_revenues(db, artist_id: int) -> pd.DataFrame:
    return db.fetch_df(
        """
        SELECT year, month, revenue_eur
        FROM imusician_monthly_revenue
        WHERE artist_id = %s
        ORDER BY year ASC, month ASC
        """,
        (artist_id,),
    )


def _load_artists(db) -> pd.DataFrame:
    return db.fetch_df(
        "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY name"
    )


# ─────────────────────────────────────────────
# Tab 1 — MRR Actuel
# ─────────────────────────────────────────────

def _tab_mrr(db) -> None:
    st.subheader("MRR actuel")

    df = _load_subscriptions(db)
    if df.empty:
        st.info("Aucun abonnement trouvé dans la base. Connectez Stripe pour alimenter ces données.")
        return

    active = df[df['status'].isin(['active', 'trialing'])]
    paying = active[active['price'] > 0]

    total_mrr = float(paying['price'].sum())
    nb_paying  = len(paying)
    arpu       = total_mrr / nb_paying if nb_paying else 0.0
    nb_cancel  = int(active['cancel_at_period_end'].sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MRR total", f"{total_mrr:,.2f} €")
    c2.metric("ARPU", f"{arpu:,.2f} €")
    c3.metric("Artistes payants", nb_paying)
    c4.metric("Annulations en attente", nb_cancel, delta=f"-{nb_cancel}" if nb_cancel else None,
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
    st.subheader("Détail des abonnements")
    display = active[['artist_name', 'plan', 'price', 'status', 'cancel_at_period_end',
                       'current_period_end']].copy()
    display['current_period_end'] = pd.to_datetime(display['current_period_end']).dt.strftime('%Y-%m-%d')
    st.dataframe(
        display.rename(columns={
            'artist_name': 'Artiste', 'plan': 'Plan', 'price': 'Prix (€/mois)',
            'status': 'Statut', 'cancel_at_period_end': 'Annulation fin période',
            'current_period_end': 'Fin de période',
        }),
        width='stretch', hide_index=True,
    )


# ─────────────────────────────────────────────
# Tab 2 — Projection MRR
# ─────────────────────────────────────────────

def _tab_projection(db) -> None:
    st.subheader("Simulation de croissance MRR")

    df = _load_subscriptions(db)
    active_paying = df[df['status'].isin(['active', 'trialing']) & (df['price'] > 0)]
    mrr_0 = float(active_paying['price'].sum()) if not active_paying.empty else 0.0

    st.caption(f"MRR de départ (réel) : **{mrr_0:,.2f} €**")
    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        growth_rate = st.slider("Taux de croissance mensuel (%)", 0, 30, 5)
        months      = st.select_slider("Mois à projeter", options=[6, 12, 24, 36], value=12)
    with c2:
        price_basic   = st.number_input("Prix Basic (€/mois)", value=9.90, step=0.10, format="%.2f")
        price_premium = st.number_input("Prix Premium (€/mois)", value=29.90, step=0.10, format="%.2f")

    # Recalc MRR0 avec prix custom
    if not active_paying.empty:
        mrr_0_custom = float(
            active_paying['price'].map(
                lambda p: price_basic if abs(p - 9.90) < 0.01 else
                          price_premium if abs(p - 29.90) < 0.01 else p
            ).sum()
        )
    else:
        mrr_0_custom = mrr_0

    enterprise_on = st.toggle("Activer un plan Enterprise")
    ent_price = ent_per_month = 0.0
    if enterprise_on:
        ec1, ec2 = st.columns(2)
        ent_price     = ec1.number_input("Prix Enterprise (€/mois)", value=99.0, step=1.0)
        ent_per_month = ec2.number_input("Nouveaux artistes Enterprise / mois", value=1.0, step=0.5)

    mrr_target = st.number_input("MRR cible (€) — ligne de référence", value=500.0, step=50.0)

    # Build projection
    mrr_vals, arr_vals, months_list = [], [], []
    target_month = None
    for t in range(months + 1):
        mrr_t = mrr_0_custom * ((1 + growth_rate / 100) ** t)
        if enterprise_on:
            mrr_t += ent_price * min(t * ent_per_month, t * ent_per_month)
        arr_t = mrr_t * 12
        mrr_vals.append(round(mrr_t, 2))
        arr_vals.append(round(arr_t, 2))
        label = (datetime.today().replace(day=1) + relativedelta(months=t)).strftime('%Y-%m')
        months_list.append(label)
        if target_month is None and mrr_t >= mrr_target:
            target_month = t

    proj_df = pd.DataFrame({'Mois': months_list, 'MRR (€)': mrr_vals, 'ARR (€)': arr_vals})

    r1, r2, r3 = st.columns(3)
    r1.metric("MRR final", f"{mrr_vals[-1]:,.2f} €")
    r2.metric("ARR final", f"{arr_vals[-1]:,.2f} €")
    if target_month is not None:
        r3.metric("Mois pour atteindre la cible", f"M+{target_month}")
    else:
        r3.metric("Mois pour atteindre la cible", "—", help=f"MRR cible {mrr_target:,.0f} € non atteint sur {months} mois")

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

    with st.expander("Tableau de projection détaillé"):
        st.dataframe(proj_df, width='stretch', hide_index=True)


# ─────────────────────────────────────────────
# Tab 3 — LTV & Churn
# ─────────────────────────────────────────────

def _tab_ltv(db) -> None:
    st.subheader("LTV & Churn")

    df = _load_subscriptions(db)
    active = df[df['status'].isin(['active', 'trialing'])]
    paying = active[active['price'] > 0]

    total_mrr = float(paying['price'].sum()) if not paying.empty else 0.0
    nb_paying  = len(paying)
    arpu       = total_mrr / nb_paying if nb_paying else 0.0
    nb_cancel  = int(active['cancel_at_period_end'].sum()) if not active.empty else 0
    nb_total   = len(active)
    churn_from_db = (nb_cancel / nb_total * 100) if nb_total > 0 else 0.0

    st.markdown("#### LTV classique (ARPU ÷ churn mensuel)")

    if churn_from_db < 0.5:
        st.info("Taux de churn détecté < 0.5% (peu d'annulations en attente). Ajustez manuellement :")
        churn_rate = st.slider("Taux de churn mensuel estimé (%)", 1.0, 20.0, 5.0, step=0.5)
    else:
        churn_rate = st.slider(
            "Taux de churn mensuel (%)",
            1.0, 20.0, round(churn_from_db, 1), step=0.5,
            help=f"Valeur estimée depuis les annulations en attente : {churn_from_db:.1f}%",
        )

    ltv_global = arpu / (churn_rate / 100) if churn_rate > 0 else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("ARPU", f"{arpu:,.2f} €")
    c2.metric("Churn mensuel", f"{churn_rate:.1f}%")
    c3.metric("LTV globale", f"{ltv_global:,.2f} €")

    st.markdown("---")
    st.markdown("#### LTV par scénario de durée de rétention")

    plans = [('basic', 9.90), ('premium', 29.90)]
    durations = [6, 12, 24, 36]
    ltv_rows = []
    for plan_name, default_price in plans:
        for d in durations:
            ltv_rows.append({
                'Plan': plan_name,
                'Durée (mois)': d,
                'LTV (€)': round(default_price * d, 2),
            })
    ltv_df = pd.DataFrame(ltv_rows)

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
    st.markdown("#### LTV artistique (revenus musicaux × durée)")
    st.caption("Proxy : valeur musicale moyenne d'un artiste sur la plateforme, basée sur l'historique iMusician.")

    avg_row = db.fetch_query("""
        SELECT AVG(monthly_avg) FROM (
            SELECT artist_id, AVG(revenue_eur) AS monthly_avg
            FROM imusician_monthly_revenue
            GROUP BY artist_id
        ) t
    """)
    avg_music = float(avg_row[0][0]) if avg_row and avg_row[0][0] else 0.0

    retention = st.select_slider(
        "Durée de rétention hypothétique (mois)",
        options=[6, 12, 24, 36], value=12, key='ltv_retention',
    )
    ltv_music = avg_music * retention

    mc1, mc2 = st.columns(2)
    mc1.metric("Revenu musical moyen / mois / artiste", f"{avg_music:,.2f} €")
    mc2.metric(f"LTV artistique sur {retention} mois", f"{ltv_music:,.2f} €")


# ─────────────────────────────────────────────
# Tab 4 — Projection Artistique
# ─────────────────────────────────────────────

def _tab_artist_forecast(db, artist_id: int | None) -> None:
    st.subheader("Projection des revenus musicaux")

    if is_admin():
        artists_df = _load_artists(db)
        if artists_df.empty:
            st.warning("Aucun artiste actif.")
            return
        opts = {row['name']: row['id'] for _, row in artists_df.iterrows()}
        sel  = st.selectbox("Artiste", list(opts.keys()), key='forecast_artist')
        target_id = opts[sel]
    else:
        target_id = artist_id
        if target_id is None:
            st.error("Impossible de déterminer votre identifiant artiste.")
            return

    df = _load_artist_revenues(db, target_id)

    if df.empty or len(df) < 3:
        st.info(
            "Données insuffisantes pour une projection (minimum 3 mois d'historique iMusician requis). "
            "Importez vos CSV depuis la page **Distributeur → Import CSV**."
        )
        return

    df['date'] = pd.to_datetime(
        df.apply(lambda r: f"{int(r['year'])}-{int(r['month']):02d}-01", axis=1)
    )
    df = df.sort_values('date').reset_index(drop=True)
    df['revenue_eur'] = df['revenue_eur'].astype(float)

    # Regression
    X = np.arange(len(df))
    Y = df['revenue_eur'].values
    slope, intercept = np.polyfit(X, Y, 1)
    y_fit = slope * X + intercept
    residuals = Y - y_fit
    std_res = float(np.std(residuals))

    horizon = st.select_slider("Horizon de projection (mois)", options=[3, 6, 12], value=6)

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
    k1.metric("Revenu moyen mensuel", f"{avg_revenue:,.2f} €")
    k2.metric("Tendance", f"{slope:+.2f} €/mois")
    k3.metric(f"Projection M+{horizon}", f"{final_forecast:,.2f} €",
              delta=f"{final_forecast - avg_revenue:+.2f} € vs moyenne")

    # Chart
    fig = go.Figure()

    # Historical
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['revenue_eur'],
        mode='lines+markers', name='Historique',
        line=dict(color='#1DB954', width=2),
        marker=dict(size=6),
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

    with st.expander("Données historiques"):
        display = df[['date', 'revenue_eur']].copy()
        display['date'] = display['date'].dt.strftime('%Y-%m')
        st.dataframe(
            display.rename(columns={'date': 'Mois', 'revenue_eur': 'Revenus (€)'}),
            width='stretch', hide_index=True,
        )

    # ── Meta Ads ROI historique ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💸 Meta Ads — ROI historique")

    from src.dashboard.utils.kpi_helpers import get_monthly_roi_series
    from_date = df['date'].iloc[0].date()
    to_date   = df['date'].iloc[-1].date()

    roi_df = get_monthly_roi_series(db, target_id, from_date, to_date)

    if roi_df.empty or roi_df['meta_spend'].sum() == 0:
        st.info("Aucune dépense Meta Ads trouvée pour cet artiste sur la période. "
                "Connectez Meta via **Credentials API** et déclenchez le DAG Meta Insights.")
    else:
        roi_df = roi_df.sort_values('period_date')
        roi_df['roi_pct'] = roi_df.apply(
            lambda r: round(r['revenue_eur'] / r['meta_spend'] * 100, 1)
            if r['meta_spend'] > 0 else None,
            axis=1,
        )
        total_rev   = float(roi_df['revenue_eur'].sum())
        total_spend = float(roi_df['meta_spend'].sum())
        global_roi  = round(total_rev / total_spend * 100, 1) if total_spend > 0 else 0.0
        avg_spend   = float(roi_df['meta_spend'].mean())

        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("Dépense Meta totale", f"{total_spend:,.2f} €")
        rc2.metric("Revenu iMusician total", f"{total_rev:,.2f} €")
        rc3.metric("ROI global", f"{global_roi:.1f}%",
                   delta="rentable" if global_roi >= 100 else "déficitaire",
                   delta_color="normal" if global_roi >= 100 else "inverse")

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
    st.markdown("### 🤖 Prédictions ML — scores par track")

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
                streams_7d,
                streams_28d
            FROM ml_song_predictions
            WHERE artist_id = %s
            ORDER BY song, prediction_date DESC
            """,
            (target_id,),
        )
    except Exception:
        ml_df = pd.DataFrame()

    if ml_df.empty:
        st.info("Aucune prédiction ML disponible. Déclenchez le DAG **ml_scoring_daily** "
                "depuis **Monitoring ETL** ou l'UI Airflow.")
    else:
        ml_df = ml_df.sort_values('dw_probability', ascending=False).reset_index(drop=True)
        ml_df['prediction_date'] = pd.to_datetime(ml_df['prediction_date']).dt.strftime('%Y-%m-%d')

        for col in ['dw_probability', 'rr_probability', 'radio_probability']:
            ml_df[col] = (ml_df[col] * 100).round(1).astype(str) + '%'

        st.dataframe(
            ml_df.rename(columns={
                'song': 'Track',
                'prediction_date': 'Dernière prédiction',
                'dw_probability': 'Discovery Weekly (%)',
                'rr_probability': 'Release Radar (%)',
                'radio_probability': 'Radio (%)',
                'dw_streams_forecast_7d': 'Streams DW 7j (prédit)',
                'rr_streams_forecast_7d': 'Streams RR 7j (prédit)',
                'streams_7d': 'Streams 7j (réels)',
                'streams_28d': 'Streams 28j (réels)',
            }),
            width='stretch', hide_index=True,
        )

    # ── Marge nette projetée ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 Marge nette projetée")
    st.caption(f"Sur l'horizon de projection sélectionné : **{horizon} mois**")

    nc1, nc2 = st.columns(2)
    vps_cost_monthly = nc1.number_input(
        "Coût infra VPS (€/mois)", min_value=0.0, value=20.0, step=1.0,
        help="Coût mensuel du serveur (VPS, Railway, Docker host…)",
    )
    meta_spend_monthly_est = nc2.number_input(
        "Dépense Meta estimée (€/mois)",
        min_value=0.0,
        value=round(avg_spend, 2) if not roi_df.empty and roi_df['meta_spend'].sum() > 0 else 50.0,
        step=10.0,
        help="Pré-rempli avec la moyenne historique. Ajustable.",
    )

    proj_revenue_total = float(sum(
        max(0.0, slope * (last_idx + 1 + i) + intercept)
        for i in range(1, horizon + 1)
    ))
    proj_meta_total = meta_spend_monthly_est * horizon
    proj_vps_total  = vps_cost_monthly * horizon
    proj_margin     = proj_revenue_total - proj_meta_total - proj_vps_total

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Revenus projetés", f"{proj_revenue_total:,.2f} €")
    m2.metric("Dépense Meta", f"-{proj_meta_total:,.2f} €")
    m3.metric("Infra VPS", f"-{proj_vps_total:,.2f} €")
    m4.metric("Marge nette", f"{proj_margin:,.2f} €",
              delta="rentable" if proj_margin >= 0 else "déficitaire",
              delta_color="normal" if proj_margin >= 0 else "inverse")

    fig_margin = go.Figure(go.Waterfall(
        orientation='v',
        measure=['absolute', 'relative', 'relative', 'total'],
        x=['Revenus projetés', 'Dépense Meta', 'Infra VPS', 'Marge nette'],
        y=[proj_revenue_total, -proj_meta_total, -proj_vps_total, proj_margin],
        connector=dict(line=dict(color='rgb(63, 63, 63)')),
        decreasing=dict(marker=dict(color='#FF6B35')),
        increasing=dict(marker=dict(color='#1DB954')),
        totals=dict(marker=dict(color='#A855F7')),
        text=[f"{proj_revenue_total:,.0f} €", f"-{proj_meta_total:,.0f} €",
              f"-{proj_vps_total:,.0f} €", f"{proj_margin:,.0f} €"],
        textposition='outside',
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
    st.title("📈 Prévisions revenus")

    db = get_db_connection()
    try:
        if is_admin():
            tab_mrr, tab_proj, tab_ltv, tab_artist = st.tabs([
                "📊 MRR Actuel",
                "🔮 Projection MRR",
                "💎 LTV & Churn",
                "🎵 Projection Artistique",
            ])
            with tab_mrr:
                _tab_mrr(db)
            with tab_proj:
                _tab_projection(db)
            with tab_ltv:
                _tab_ltv(db)
            with tab_artist:
                _tab_artist_forecast(db, artist_id=None)
        else:
            st.caption("Projection de vos revenus musicaux basée sur votre historique iMusician.")
            _tab_artist_forecast(db, artist_id=get_artist_id())
    finally:
        db.close()
