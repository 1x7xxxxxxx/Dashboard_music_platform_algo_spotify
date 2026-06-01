"""trigger_algo — _show_tab_budget_roi (move-only split)."""
from plotly.subplots import make_subplots
from src.dashboard.utils import algo_knowledge as ak
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from ._common import (
    _TRIGGER_STREAM_TARGETS,
    _load_ml_pred,
    _show_budget_pacing_calculator,
    _show_budget_tier_selector,
    _show_pi_breakeven,
    _show_velocity_budget_advice,
)


def _show_tab_budget_roi(db, track: str, artist_id, date_from, date_to):
    _show_budget_tier_selector(db, artist_id)
    st.markdown("---")

    # 1. Budget Meta restant
    st.subheader("💶 Budget Meta Ads")
    try:
        if artist_id:
            budget_row = db.fetch_query(
                "SELECT COALESCE(SUM(lifetime_budget), 0), COALESCE(SUM(daily_budget), 0) FROM meta_campaigns WHERE artist_id = %s AND status = 'ACTIVE'",
                (artist_id,)
            )
            spend_row = db.fetch_query(
                "SELECT COALESCE(SUM(spend), 0) FROM meta_insights_performance_day WHERE artist_id = %s AND day_date BETWEEN %s AND %s",
                (artist_id, date_from, date_to)
            )
            streams_row = db.fetch_query(
                "SELECT COALESCE(SUM(streams), 0) FROM s4a_song_timeline WHERE artist_id = %s AND date BETWEEN %s AND %s",
                (artist_id, date_from, date_to)
            )
        else:
            budget_row = db.fetch_query(
                "SELECT COALESCE(SUM(lifetime_budget), 0), COALESCE(SUM(daily_budget), 0) FROM meta_campaigns WHERE status = 'ACTIVE'"
            )
            spend_row = db.fetch_query(
                "SELECT COALESCE(SUM(spend), 0) FROM meta_insights_performance_day WHERE day_date BETWEEN %s AND %s",
                (date_from, date_to)
            )
            streams_row = db.fetch_query(
                "SELECT COALESCE(SUM(streams), 0) FROM s4a_song_timeline WHERE date BETWEEN %s AND %s",
                (date_from, date_to)
            )

        lifetime_budget = float(budget_row[0][0] or 0)
        total_spend = float(spend_row[0][0] or 0)
        total_streams = int(streams_row[0][0] or 0)
        remaining = max(lifetime_budget - total_spend, 0)

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Budget lifetime alloué", f"{lifetime_budget:,.2f} €")
        b2.metric("Dépensé (période)", f"{total_spend:,.2f} €")
        pct_remaining = f"{remaining / lifetime_budget * 100:.0f}%" if lifetime_budget > 0 else None
        b3.metric("Restant estimé", f"{remaining:,.2f} €", delta=pct_remaining)

        if total_streams > 0 and total_spend > 0:
            cost_per_stream = total_spend / total_streams
            b4.metric("Coût / stream", f"{cost_per_stream:.4f} €")
            st.markdown("**Budget estimé pour déclencher chaque playlist :**")
            est_cols = st.columns(len(_TRIGGER_STREAM_TARGETS))
            for i, (label, seuil) in enumerate(_TRIGGER_STREAM_TARGETS.items()):
                cost_est = cost_per_stream * seuil
                with est_cols[i]:
                    if remaining >= cost_est:
                        st.success(f"**{label}**\n\n~{seuil:,} streams · {cost_est:.2f} €\n\n✅ Budget suffisant")
                    else:
                        st.error(f"**{label}**\n\n~{seuil:,} streams · {cost_est:.2f} €\n\n❌ Manque {cost_est - remaining:.2f} €")
            st.caption("Volumes de déclenchement SHAP (Classe 1) par algo, pas des arrondis 1k/10k.")
        else:
            b4.metric("Coût / stream", "—")
            if lifetime_budget == 0:
                st.info("Aucune campagne Meta active trouvée pour cet artiste.")

        if total_spend > 0:
            _show_velocity_budget_advice(db, track, artist_id, total_spend)
    except Exception as e:
        st.warning(f"Budget Meta indisponible : {e}")

    st.markdown("---")

    # 1bis. Organic scaling threshold (volume) — static target until Phase 2 data.
    st.subheader("🔊 Seuil de scaling organique (volume DW)")
    _scale = ak.volume_scaling_threshold("DW")
    if _scale:
        st.info(
            f"Pour déclencher le **scaling de volume** du Discover Weekly, vise un socle "
            f"d'au moins **~{_scale:,} streams organiques/28j** (recherche, profil — hors "
            f"autoplay). Sous ce seuil, l'impact sur le volume est plat ; au-delà, Spotify "
            f"« ouvre les vannes » et multiplie le débit."
        )
        st.caption(
            "⚠️ La valeur organique live (NonAlgoStreams par source) n'est pas encore "
            "collectée (Phase 2 — split par source S4A) : ce seuil est affiché comme "
            "**cible**, pas comme un écart calculé sur vos données."
        )
    st.markdown("---")

    _show_budget_pacing_calculator(db, artist_id)
    st.markdown("---")

    # 2. Groover / Fluence simulator
    with st.expander("💶 Budget playlist — Groover & Fluence", expanded=False):
        _PLATFORMS = [
            {"Plateforme": "Groover",  "Offre": "Standard",  "Coût/soumission (€)": 2.10},
            {"Plateforme": "Groover",  "Offre": "Premium",   "Coût/soumission (€)": 6.00},
            {"Plateforme": "Fluence",  "Offre": "Standard",  "Coût/soumission (€)": 1.50},
            {"Plateforme": "Fluence",  "Offre": "Premium",   "Coût/soumission (€)": 3.00},
        ]
        st.caption("Tarifs de référence — vérifiez les prix actuels sur les plateformes.")
        st.dataframe(pd.DataFrame(_PLATFORMS), hide_index=True, width='stretch')
        st.markdown("**Simulateur de budget**")
        budget_key = f"budget_{track}"
        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            total_budget = st.number_input(
                "Budget total (€)", min_value=0.0, value=st.session_state.get(budget_key, 50.0),
                step=5.0, format="%.2f", key=f"budget_input_{track}"
            )
            st.session_state[budget_key] = total_budget
        with col_b2:
            platform_choice = st.selectbox(
                "Plateforme",
                ["Groover Standard (2.10€)", "Groover Premium (6€)",
                 "Fluence Standard (1.50€)", "Fluence Premium (3€)"],
                key=f"plat_{track}"
            )
        with col_b3:
            already_spent = st.number_input(
                "Déjà dépensé (€)", min_value=0.0, value=0.0,
                step=1.0, format="%.2f", key=f"spent_{track}"
            )
        rate_map = {
            "Groover Standard (2.10€)": 2.10, "Groover Premium (6€)": 6.00,
            "Fluence Standard (1.50€)": 1.50, "Fluence Premium (3€)": 3.00,
        }
        rate = rate_map[platform_choice]
        rem = max(total_budget - already_spent, 0.0)
        submissions = int(rem / rate) if rate > 0 else 0
        r1, r2, r3 = st.columns(3)
        r1.metric("Budget restant", f"{rem:.2f} €")
        r2.metric("Coût / soumission", f"{rate:.2f} €")
        r3.metric("Soumissions possibles", submissions)
        if submissions == 0:
            st.warning("Budget insuffisant pour une soumission supplémentaire.")
        else:
            st.success(f"Vous pouvez encore soumettre à **{submissions}** curators sur {platform_choice.split(' (')[0]}.")

    st.markdown("---")

    # 3. ROI regression
    st.subheader("📉 ROI — Régression linéaire (mensuel)")
    try:
        from scipy import stats as sp_stats
        from src.dashboard.utils.kpi_helpers import get_monthly_roi_series

        df_roi = get_monthly_roi_series(db, artist_id, date_from, date_to)
        if df_roi is not None and not df_roi.empty:
            df_roi = df_roi.dropna(subset=["meta_spend", "revenue_eur"])
            df_valid = df_roi[(df_roi["meta_spend"] > 0) | (df_roi["revenue_eur"] > 0)]
            if len(df_valid) >= 2:
                x = df_valid["meta_spend"].astype(float).values
                y = df_valid["revenue_eur"].astype(float).values
                slope, intercept, r_value, p_value, _ = sp_stats.linregress(x, y)
                r2 = r_value ** 2
                x_line = np.linspace(x.min(), x.max(), 100)
                y_line = slope * x_line + intercept

                labels = df_valid["period_date"].astype(str).str[:7] if "period_date" in df_valid.columns else None
                fig_roi = go.Figure()
                fig_roi.add_trace(go.Scatter(
                    x=x, y=y, mode="markers+text",
                    text=labels, textposition="top center",
                    name="Mensuel", marker=dict(color="#1DB954", size=10)
                ))
                fig_roi.add_trace(go.Scatter(
                    x=x_line, y=y_line, mode="lines",
                    name=f"Régression (R²={r2:.2f})",
                    line=dict(color="#FF6B6B", width=2, dash="dash")
                ))
                fig_roi.add_annotation(
                    x=x.max(), y=y_line[-1],
                    text=f"y = {slope:.2f}x + {intercept:.2f}<br>R² = {r2:.2f}",
                    showarrow=False, bgcolor="#222", font=dict(color="white"), bordercolor="#555"
                )
                fig_roi.update_layout(
                    title="Revenue iMusician (€) vs Spend Meta Ads (€)",
                    xaxis_title="Dépenses Meta Ads (€)", yaxis_title="Revenus iMusician (€)",
                    height=420, hovermode="closest"
                )
                st.plotly_chart(fig_roi, width='stretch')
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("R²", f"{r2:.3f}", help="1.0 = corrélation parfaite spend↔revenue")
                rc2.metric("Pente", f"{slope:.2f} €/€", help="Revenue généré par € investi en Meta Ads")
                rc3.metric("p-value", f"{p_value:.3f}", help="< 0.05 = corrélation statistiquement significative")
            else:
                st.info("Données insuffisantes (minimum 2 mois avec spend + revenue).")
        else:
            st.info("Pas de données revenue/spend pour calculer la régression ROI.")
    except ImportError:
        st.warning("scipy non disponible — régression désactivée.")
    except Exception as e:
        st.warning(f"Graphique ROI indisponible : {e}")

    st.markdown("---")

    # 4. Breakeven
    st.subheader("⚖️ Breakeven — Cumul spend vs Cumul revenue")
    _show_pi_breakeven(_load_ml_pred(db, track, artist_id))
    try:
        if artist_id:
            df_spend_d = db.fetch_df(
                "SELECT day_date AS date, SUM(spend) AS spend FROM meta_insights_performance_day WHERE artist_id = %s GROUP BY day_date ORDER BY day_date",
                (artist_id,)
            )
            df_rev = db.fetch_df(
                "SELECT make_date(year, month, 1) AS date, revenue_eur FROM imusician_monthly_revenue WHERE artist_id = %s ORDER BY year, month",
                (artist_id,)
            )
            df_pop_be = db.fetch_df(
                "SELECT date, popularity FROM track_popularity_history WHERE track_name = %s AND artist_id = %s ORDER BY date",
                (track, artist_id)
            )
        else:
            df_spend_d = db.fetch_df(
                "SELECT day_date AS date, SUM(spend) AS spend FROM meta_insights_performance_day GROUP BY day_date ORDER BY day_date"
            )
            df_rev = db.fetch_df(
                "SELECT make_date(year, month, 1) AS date, SUM(revenue_eur) AS revenue_eur FROM imusician_monthly_revenue GROUP BY year, month ORDER BY year, month"
            )
            df_pop_be = db.fetch_df(
                "SELECT date, popularity FROM track_popularity_history WHERE track_name = %s ORDER BY date",
                (track,)
            )

        if not df_spend_d.empty and not df_rev.empty:
            df_spend_d["date"] = pd.to_datetime(df_spend_d["date"])
            df_rev["date"] = pd.to_datetime(df_rev["date"])
            all_dates = pd.date_range(
                start=min(df_spend_d["date"].min(), df_rev["date"].min()),
                end=max(df_spend_d["date"].max(), df_rev["date"].max()),
                freq="D"
            )
            df_tl = pd.DataFrame({"date": all_dates})
            df_tl = df_tl.merge(df_spend_d, on="date", how="left")
            df_tl = df_tl.merge(df_rev.rename(columns={"revenue_eur": "revenue"}), on="date", how="left")
            df_tl["spend"] = df_tl["spend"].fillna(0)
            df_tl["revenue"] = df_tl["revenue"].fillna(0)
            df_tl["cumul_spend"] = df_tl["spend"].cumsum()
            df_tl["cumul_revenue"] = df_tl["revenue"].cumsum()

            breakeven_date = None
            for _, row in df_tl.iterrows():
                if row["cumul_spend"] > 0 and row["cumul_revenue"] >= row["cumul_spend"]:
                    breakeven_date = row["date"]
                    break

            fig_be = make_subplots(specs=[[{"secondary_y": True}]])
            fig_be.add_trace(go.Scatter(
                x=df_tl["date"], y=df_tl["cumul_spend"], name="Cumul Spend Meta",
                mode="lines", line=dict(color="#FF6B6B", width=2),
                fill="tozeroy", fillcolor="rgba(255,107,107,0.08)"
            ), secondary_y=False)
            fig_be.add_trace(go.Scatter(
                x=df_tl["date"], y=df_tl["cumul_revenue"], name="Cumul Revenue iMusician",
                mode="lines", line=dict(color="#1DB954", width=2),
                fill="tozeroy", fillcolor="rgba(29,185,84,0.08)"
            ), secondary_y=False)

            if not df_pop_be.empty:
                df_pop_be["date"] = pd.to_datetime(df_pop_be["date"])
                fig_be.add_trace(go.Scatter(
                    x=df_pop_be["date"], y=df_pop_be["popularity"],
                    name="Popularité (0-100)", mode="lines",
                    line=dict(color="#FFE66D", width=1, dash="dot")
                ), secondary_y=True)

            if breakeven_date:
                fig_be.add_vline(
                    x=breakeven_date.timestamp() * 1000,
                    line_dash="dash", line_color="white",
                    annotation_text=f"Breakeven : {breakeven_date.strftime('%d/%m/%Y')}",
                    annotation_position="top right"
                )
                st.success(f"✅ Breakeven atteint le **{breakeven_date.strftime('%d/%m/%Y')}**")
            else:
                st.warning("⚠️ Breakeven non atteint sur la période disponible.")

            fig_be.update_layout(
                title="Cumul spend Meta vs Cumul revenue iMusician",
                hovermode="x unified", height=460,
                legend=dict(orientation="h", y=1.12)
            )
            fig_be.update_yaxes(title_text="Montant cumulé (€)", secondary_y=False)
            fig_be.update_yaxes(title_text="Popularité (0-100)", secondary_y=True, range=[0, 100])
            st.plotly_chart(fig_be, width='stretch')
        else:
            st.info("Données spend ou revenue manquantes pour le graphique breakeven.")
    except Exception as e:
        st.warning(f"Graphique breakeven indisponible : {e}")
