"""trigger_algo — _show_tab_budget_roi (move-only split)."""
from datetime import date
from plotly.subplots import make_subplots
from src.dashboard.utils import algo_knowledge as ak
from src.dashboard.utils import ml_widgets
from src.dashboard.utils.i18n import t
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


# Maps the cost-target labels to (ml_pred probability key, calibration-band algo key).
_EV_ALGO_KEYS = {
    "Release Radar": ("rr_probability", "RR"),
    "Discover Weekly": ("dw_probability", "DW"),
    "Radio": ("radio_probability", "RADIO"),
}


def _render_expected_value(ml_pred: dict, cost_per_stream: float) -> None:
    """Risk-adjusted cost-per-trigger = nominal cost / P(trigger).

    The nominal cost-to-trigger assumes the push always converts. It does not: the model
    gives P(trigger). Dividing the cost by P yields the honest effective € per trigger
    actually obtained, and ranks where a euro is most likely to convert. Expected value,
    never a promise — gated by the calibration caveat per algo.
    """
    st.markdown(t("trigger_algo.roi.risk_adjusted_header",
                  "**Coût ajusté au risque (coût ÷ probabilité de déclenchement) :**"))
    rows = []
    for label, seuil in _TRIGGER_STREAM_TARGETS.items():
        key, algo = _EV_ALGO_KEYS[label]
        p = ml_pred.get(key)
        if p is None or p <= 0:
            continue
        cost_est = cost_per_stream * seuil
        rows.append((label, algo, float(p), cost_est, cost_est / float(p)))
    if not rows:
        st.caption(t("trigger_algo.roi.ml_proba_unavailable",
                     "Probabilités ML indisponibles pour ce titre (lancez `ml_scoring_daily`)."))
        return
    cols = st.columns(len(rows))
    for col, (label, algo, p, cost_est, adj) in zip(cols, rows):
        with col:
            st.metric(label, f"{adj:,.2f} €",
                      help=t("trigger_algo.roi.adj_cost_help",
                             "Coût nominal {cost:,.2f} € ÷ P={p:.0f}% de déclenchement.")
                      .format(cost=cost_est, p=p * 100))
            st.caption(t("trigger_algo.roi.p_nominal_caption", "P={p:.0f}% · nominal {cost:,.0f} €")
                       .format(p=p * 100, cost=cost_est))
    best = min(rows, key=lambda r: r[4])
    st.success(t("trigger_algo.roi.best_bet",
                 "🎯 Meilleur pari : **{label}** — chaque euro y a le plus de chances "
                 "de convertir en déclenchement (coût ajusté {cost:,.0f} €).")
               .format(label=best[0], cost=best[4]))
    note = ml_widgets.calibration_note_text(best[1], best[2])
    if note:
        st.caption(t("trigger_algo.roi.score_reliability", "🎯 Fiabilité du score : {note}")
                   .format(note=note))


def _show_tab_budget_roi(db, track: str, artist_id, date_from, date_to):
    st.caption(t(
        "trigger_algo.roi.caption",
        "💰 **Décision budget** — quels titres pousser en priorité (top-N% par score), ton "
        "budget Meta Ads restant, et le coût ajusté au risque (coût ÷ probabilité de "
        "déclenchement) = le vrai € à payer pour espérer ouvrir une porte algorithmique."
    ))
    _show_budget_tier_selector(db, artist_id)
    st.markdown("---")

    # 1. Budget Meta restant
    st.subheader(t("trigger_algo.roi.meta_budget_header", "💶 Budget Meta Ads"))
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
        b1.metric(t("trigger_algo.roi.lifetime_budget_metric", "Budget lifetime alloué"),
                  f"{lifetime_budget:,.2f} €")
        b2.metric(t("trigger_algo.roi.spent_metric", "Dépensé (période)"), f"{total_spend:,.2f} €")
        pct_remaining = f"{remaining / lifetime_budget * 100:.0f}%" if lifetime_budget > 0 else None
        b3.metric(t("trigger_algo.roi.remaining_metric", "Restant estimé"),
                  f"{remaining:,.2f} €", delta=pct_remaining)

        if total_streams > 0 and total_spend > 0:
            cost_per_stream = total_spend / total_streams
            b4.metric(t("trigger_algo.roi.cost_per_stream_metric", "Coût / stream"),
                      f"{cost_per_stream:.4f} €")
            st.markdown(t("trigger_algo.roi.budget_per_playlist_header",
                          "**Budget estimé pour déclencher chaque playlist :**"))
            est_cols = st.columns(len(_TRIGGER_STREAM_TARGETS))
            for i, (label, seuil) in enumerate(_TRIGGER_STREAM_TARGETS.items()):
                cost_est = cost_per_stream * seuil
                with est_cols[i]:
                    if remaining >= cost_est:
                        st.success(t("trigger_algo.roi.budget_sufficient",
                                     "**{label}**\n\n~{seuil:,} streams · {cost:.2f} €\n\n✅ Budget suffisant")
                                   .format(label=label, seuil=seuil, cost=cost_est))
                    else:
                        st.error(t("trigger_algo.roi.budget_short",
                                   "**{label}**\n\n~{seuil:,} streams · {cost:.2f} €\n\n❌ Manque {missing:.2f} €")
                                 .format(label=label, seuil=seuil, cost=cost_est, missing=cost_est - remaining))
            st.caption(t("trigger_algo.roi.shap_volumes_caption",
                         "Volumes de déclenchement SHAP (Classe 1) par algo, pas des arrondis 1k/10k."))
            _ev_pred = _load_ml_pred(db, track, artist_id)
            if _ev_pred:
                _render_expected_value(_ev_pred, cost_per_stream)
        else:
            b4.metric(t("trigger_algo.roi.cost_per_stream_metric", "Coût / stream"), "—")
            if lifetime_budget == 0:
                st.info(t("trigger_algo.roi.no_active_campaign",
                          "Aucune campagne Meta active trouvée pour cet artiste."))

        if total_spend > 0:
            _show_velocity_budget_advice(db, track, artist_id, total_spend)
    except Exception as e:
        st.warning(t("trigger_algo.roi.meta_budget_unavailable",
                     "Budget Meta indisponible : {err}").format(err=e))

    st.markdown("---")

    # 1bis. Organic scaling threshold (volume) — static target until Phase 2 data.
    st.subheader(t("trigger_algo.roi.organic_scaling_header",
                   "🔊 Seuil de scaling organique (volume DW)"))
    _scale = ak.volume_scaling_threshold("DW")
    if _scale:
        st.info(t(
            "trigger_algo.roi.organic_scaling_info",
            "Pour déclencher le **scaling de volume** du Discover Weekly, vise un socle "
            "d'au moins **~{scale:,} streams organiques/28j** (recherche, profil — hors "
            "autoplay). Sous ce seuil, l'impact sur le volume est plat ; au-delà, Spotify "
            "« ouvre les vannes » et multiplie le débit."
        ).format(scale=_scale))
        st.caption(t(
            "trigger_algo.roi.organic_scaling_caption",
            "⚠️ La valeur organique live (NonAlgoStreams par source) n'est pas encore "
            "collectée (Phase 2 — split par source S4A) : ce seuil est affiché comme "
            "**cible**, pas comme un écart calculé sur vos données."
        ))
    st.markdown("---")

    _show_budget_pacing_calculator(db, artist_id)
    st.markdown("---")

    # 2. Groover / Fluence simulator
    with st.expander(t("trigger_algo.roi.playlist_budget_expander",
                       "💶 Budget playlist — Groover & Fluence"), expanded=False):
        _PLATFORMS = [
            {"Plateforme": "Groover",  "Offre": "Standard",  "Coût/soumission (€)": 2.10},
            {"Plateforme": "Groover",  "Offre": "Premium",   "Coût/soumission (€)": 6.00},
            {"Plateforme": "Fluence",  "Offre": "Standard",  "Coût/soumission (€)": 1.50},
            {"Plateforme": "Fluence",  "Offre": "Premium",   "Coût/soumission (€)": 3.00},
        ]
        st.caption(t("trigger_algo.roi.reference_rates",
                     "Tarifs de référence — vérifiez les prix actuels sur les plateformes."))
        st.dataframe(pd.DataFrame(_PLATFORMS), hide_index=True, width='stretch')
        st.markdown(t("trigger_algo.roi.budget_simulator", "**Simulateur de budget**"))
        budget_key = f"budget_{track}"
        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            total_budget = st.number_input(
                t("trigger_algo.roi.total_budget_input", "Budget total (€)"),
                min_value=0.0, value=st.session_state.get(budget_key, 50.0),
                step=5.0, format="%.2f", key=f"budget_input_{track}"
            )
            st.session_state[budget_key] = total_budget
        with col_b2:
            platform_choice = st.selectbox(
                t("trigger_algo.roi.platform_select", "Plateforme"),
                ["Groover Standard (2.10€)", "Groover Premium (6€)",
                 "Fluence Standard (1.50€)", "Fluence Premium (3€)"],
                key=f"plat_{track}"
            )
        with col_b3:
            already_spent = st.number_input(
                t("trigger_algo.roi.already_spent_input", "Déjà dépensé (€)"),
                min_value=0.0, value=0.0,
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
        r1.metric(t("trigger_algo.roi.remaining_budget_metric", "Budget restant"), f"{rem:.2f} €")
        r2.metric(t("trigger_algo.roi.cost_per_submission_metric", "Coût / soumission"), f"{rate:.2f} €")
        r3.metric(t("trigger_algo.roi.possible_submissions_metric", "Soumissions possibles"), submissions)
        if submissions == 0:
            st.warning(t("trigger_algo.roi.budget_insufficient",
                         "Budget insuffisant pour une soumission supplémentaire."))
        else:
            st.success(t("trigger_algo.roi.can_submit",
                         "Vous pouvez encore soumettre à **{n}** curators sur {platform}.")
                       .format(n=submissions, platform=platform_choice.split(' (')[0]))

    st.markdown("---")

    # 3. ROI regression
    st.subheader(t("trigger_algo.roi.regression_header", "📉 ROI — Régression linéaire (mensuel)"))
    st.caption(t(
        "trigger_algo.roi.regression_caption",
        "Sur **tout l'historique mensuel** disponible (revenue iMusician × spend Meta Ads), "
        "indépendamment de la période choisie en haut : une régression mensuelle a besoin de "
        "plusieurs mois, qu'une fenêtre J+28 ne peut pas fournir."
    ))
    try:
        from scipy import stats as sp_stats
        from src.dashboard.utils.kpi_helpers import get_monthly_roi_series

        # All-time window on purpose — monthly ROI is a long-horizon analysis, decoupled
        # from the J+28 period selector (date_from/date_to) which captures ≤ 1 month.
        df_roi = get_monthly_roi_series(db, artist_id, date(2000, 1, 1), date.today())
        if df_roi is not None and not df_roi.empty:
            df_roi = df_roi.dropna(subset=["meta_spend", "revenue_eur"])
            # Both signals must be present in the month — a spend→revenue regression is
            # meaningless on revenue-only months (spend = 0 cloud) or spend-only months.
            df_valid = df_roi[(df_roi["meta_spend"] > 0) & (df_roi["revenue_eur"] > 0)]
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
                    name=t("trigger_algo.roi.trace_monthly", "Mensuel"),
                    marker=dict(color="#1DB954", size=10)
                ))
                fig_roi.add_trace(go.Scatter(
                    x=x_line, y=y_line, mode="lines",
                    name=t("trigger_algo.roi.trace_regression", "Régression (R²={r2:.2f})").format(r2=r2),
                    line=dict(color="#FF6B6B", width=2, dash="dash")
                ))
                fig_roi.add_annotation(
                    x=x.max(), y=y_line[-1],
                    text=f"y = {slope:.2f}x + {intercept:.2f}<br>R² = {r2:.2f}",
                    showarrow=False, bgcolor="#222", font=dict(color="white"), bordercolor="#555"
                )
                fig_roi.update_layout(
                    title=t("trigger_algo.roi.regression_chart_title",
                            "Revenue iMusician (€) vs Spend Meta Ads (€)"),
                    xaxis_title=t("trigger_algo.roi.axis_meta_spend", "Dépenses Meta Ads (€)"),
                    yaxis_title=t("trigger_algo.roi.axis_imusician_revenue", "Revenus iMusician (€)"),
                    height=420, hovermode="closest"
                )
                st.plotly_chart(fig_roi, width='stretch')
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("R²", f"{r2:.3f}",
                           help=t("trigger_algo.roi.r2_help", "1.0 = corrélation parfaite spend↔revenue"))
                rc2.metric(t("trigger_algo.roi.slope_metric", "Pente"), f"{slope:.2f} €/€",
                           help=t("trigger_algo.roi.slope_help", "Revenue généré par € investi en Meta Ads"))
                rc3.metric("p-value", f"{p_value:.3f}",
                           help=t("trigger_algo.roi.pvalue_help",
                                  "< 0.05 = corrélation statistiquement significative"))
            else:
                st.info(t("trigger_algo.roi.insufficient_data",
                          "Données insuffisantes : il faut au moins 2 mois où coexistent un "
                          "spend Meta Ads ET un revenue iMusician."))
        else:
            st.info(t("trigger_algo.roi.no_revenue_spend",
                      "Pas de données revenue/spend pour calculer la régression ROI "
                      "(aucun mois avec spend Meta Ads + revenue iMusician dans l'historique)."))
    except ImportError:
        st.warning(t("trigger_algo.roi.scipy_unavailable", "scipy non disponible — régression désactivée."))
    except Exception as e:
        st.warning(t("trigger_algo.roi.regression_unavailable",
                     "Graphique ROI indisponible : {err}").format(err=e))

    st.markdown("---")

    # 4. Breakeven
    st.subheader(t("trigger_algo.roi.breakeven_header", "⚖️ Breakeven — Cumul spend vs Cumul revenue"))
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
                x=df_tl["date"], y=df_tl["cumul_spend"],
                name=t("trigger_algo.roi.trace_cumul_spend", "Cumul Spend Meta"),
                mode="lines", line=dict(color="#FF6B6B", width=2),
                fill="tozeroy", fillcolor="rgba(255,107,107,0.08)"
            ), secondary_y=False)
            fig_be.add_trace(go.Scatter(
                x=df_tl["date"], y=df_tl["cumul_revenue"],
                name=t("trigger_algo.roi.trace_cumul_revenue", "Cumul Revenue iMusician"),
                mode="lines", line=dict(color="#1DB954", width=2),
                fill="tozeroy", fillcolor="rgba(29,185,84,0.08)"
            ), secondary_y=False)

            if not df_pop_be.empty:
                df_pop_be["date"] = pd.to_datetime(df_pop_be["date"])
                fig_be.add_trace(go.Scatter(
                    x=df_pop_be["date"], y=df_pop_be["popularity"],
                    name=t("trigger_algo.roi.trace_popularity", "Popularité (0-100)"), mode="lines",
                    line=dict(color="#FFE66D", width=1, dash="dot")
                ), secondary_y=True)

            if breakeven_date:
                fig_be.add_vline(
                    x=breakeven_date.timestamp() * 1000,
                    line_dash="dash", line_color="white",
                    annotation_text=t("trigger_algo.roi.breakeven_annotation", "Breakeven : {date}")
                    .format(date=breakeven_date.strftime('%d/%m/%Y')),
                    annotation_position="top right"
                )
                st.success(t("trigger_algo.roi.breakeven_reached", "✅ Breakeven atteint le **{date}**")
                           .format(date=breakeven_date.strftime('%d/%m/%Y')))
            else:
                st.warning(t("trigger_algo.roi.breakeven_not_reached",
                             "⚠️ Breakeven non atteint sur la période disponible."))

            fig_be.update_layout(
                title=t("trigger_algo.roi.breakeven_chart_title",
                        "Cumul spend Meta vs Cumul revenue iMusician"),
                hovermode="x unified", height=460,
                legend=dict(orientation="h", y=1.12)
            )
            fig_be.update_yaxes(title_text=t("trigger_algo.roi.axis_cumul_amount", "Montant cumulé (€)"),
                                secondary_y=False)
            fig_be.update_yaxes(title_text=t("trigger_algo.roi.trace_popularity", "Popularité (0-100)"),
                                secondary_y=True, range=[0, 100])
            st.plotly_chart(fig_be, width='stretch')
        else:
            st.info(t("trigger_algo.roi.breakeven_missing_data",
                      "Données spend ou revenue manquantes pour le graphique breakeven."))
    except Exception as e:
        st.warning(t("trigger_algo.roi.breakeven_unavailable",
                     "Graphique breakeven indisponible : {err}").format(err=e))
