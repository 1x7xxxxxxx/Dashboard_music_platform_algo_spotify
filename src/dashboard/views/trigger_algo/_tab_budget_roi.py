"""trigger_algo — _show_tab_budget_roi (move-only split)."""
from datetime import date
from plotly.subplots import make_subplots
from src.dashboard.utils import algo_knowledge as ak, charts
from src.dashboard.utils.semantic_colors import BON
from src.dashboard.utils.i18n import t
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from ._common import (
    _show_budget_pacing_calculator,
    _show_pi_breakeven,
    _show_velocity_budget_advice,
)
from src.dashboard.utils.date_format import format_date
from src.dashboard.utils.algo_preview_data import cout_par_stream as _cout_par_stream  # noqa: F401,E402 — moved (R193)


# ⚠️ « Budget estimé pour déclencher chaque playlist » and the risk-adjusted cost
# (cost ÷ P) were REMOVED on 2026-10-05 (R402). Both bought streams up to 417/1333/8423 —
# the volume a playlist PRODUCES once installed (`pdf_exporter/_report.py`: « pas un
# objectif de streams à atteindre soi-même ») — under a caption naming a SHAP source
# that does not exist. The euro figures rested on a diverted threshold. The honest
# cost is the coach's 7-day streams GAP × cost per stream (`algo_preview_data`).


def _show_tab_budget_roi(db, track: str, artist_id, date_from, date_to, ml_pred=None):
    """⚠️ `ml_pred` est REÇU, plus rechargé — 2026-09-22.

    Le routeur charge déjà la prédiction du titre (`router.py`) et la passe aux
    autres onglets. Celui-ci ne la recevait pas et rappelait `_load_ml_pred` **deux
    fois** : une fois pour la valeur attendue, une fois pour les portes PI. Trois
    exécutions de la même requête, avec les mêmes paramètres, par rendu de page.

    `tests/test_a_page_asks_the_same_question_once.py` plafonne les allers-retours
    par rendu et interdit la même requête deux fois avec les mêmes paramètres ; ce
    site en était la principale source dans ce paquet.
    """
    st.caption(t(
        "trigger_algo.roi.caption",
        "💰 **Décision budget** — quels titres pousser en priorité (top-N% par score), ton "
        "budget Meta Ads restant et le rythme de dépense."
    ))
    st.markdown("---")

    # ── LE PANNEAU DE RÉGLAGES EN TÊTE — 2026-09-22 ─────────────────────────
    # Les réglages d'une campagne vivaient éparpillés sur quatre surfaces. Ils sont
    # désormais mesurés sur la même base, à la même maille, et classés par leur
    # effet réel. Il vient AVANT le budget : on décide quoi régler avant de décider
    # combien mettre.
    from ._tab_reglages import _show_reglages
    _show_reglages(db, artist_id, track)
    st.markdown("---")

    # 1. Budget Meta restant
    st.subheader(t("trigger_algo.roi.meta_budget_header", "💶 Budget Meta Ads"))
    try:
        if artist_id:
            budget_row = db.fetch_query(
                # `v_meta_active_budget` (migration 110) — le prédicat `status =
                # 'ACTIVE'` était recopié ici et dans `_common/_budget_roi.py`.
                "SELECT COALESCE(SUM(lifetime_budget), 0), COALESCE(SUM(daily_budget), 0) "
                "FROM v_meta_active_budget WHERE artist_id = %s",
                (artist_id,)
            )
            spend_row = db.fetch_query(
                "SELECT COALESCE(SUM(spend), 0) FROM v_meta_daily WHERE artist_id = %s AND day BETWEEN %s AND %s",
                (artist_id, date_from, date_to)
            )
            streams_row = db.fetch_query(
                "SELECT COALESCE(SUM(streams), 0) FROM v_s4a_song_daily "
                "WHERE artist_id = %s AND day BETWEEN %s AND %s",
                (artist_id, date_from, date_to)
            )
        else:
            budget_row = db.fetch_query(
                "SELECT COALESCE(SUM(lifetime_budget), 0), COALESCE(SUM(daily_budget), 0) "
                "FROM v_meta_active_budget"
            )
            spend_row = db.fetch_query(
                "SELECT COALESCE(SUM(spend), 0) FROM v_meta_daily WHERE day BETWEEN %s AND %s",
                (date_from, date_to)
            )
            streams_row = db.fetch_query(
                "SELECT COALESCE(SUM(streams), 0) FROM v_s4a_song_daily "
                "WHERE day BETWEEN %s AND %s",
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

    _show_roi_regression(db, artist_id)
    st.markdown("---")
    _show_breakeven(db, track, artist_id, ml_pred)


def _show_roi_regression(db, artist_id) -> None:
    """Monthly spend→revenue fit — refused below `MIN_FIT_POINTS` months (2026-09-26).

    It used to fit from 2 points: a line through two points is exact, so the page printed
    R² = 1.000 and p = 0.000 as an artefact of n. `n` is now shown next to R² and p.
    """
    from src.dashboard.utils.roi_verdicts import MIN_FIT_POINTS, fit_spend_revenue

    st.subheader(t("trigger_algo.roi.regression_header", "📉 ROI — Régression linéaire (mensuel)"))
    st.caption(t(
        "trigger_algo.roi.regression_caption",
        "Sur **tout l'historique mensuel** disponible (revenue iMusician × spend Meta Ads), "
        "indépendamment de la période choisie en haut : une régression mensuelle a besoin de "
        "plusieurs mois, qu'une fenêtre J+28 ne peut pas fournir."
    ))
    try:
        from src.dashboard.utils.kpi_helpers import get_monthly_roi_series

        # All-time window on purpose — monthly ROI is a long-horizon analysis, decoupled
        # from the J+28 period selector (date_from/date_to) which captures ≤ 1 month.
        df_roi = get_monthly_roi_series(db, artist_id, date(2000, 1, 1), date.today())
        if df_roi is None or df_roi.empty:
            st.info(t("trigger_algo.roi.no_revenue_spend",
                      "Pas de données revenue/spend pour calculer la régression ROI "
                      "(aucun mois avec spend Meta Ads + revenue iMusician dans l'historique)."))
            return
        fit = fit_spend_revenue(df_roi)
        if fit is None:
            st.info(t("trigger_algo.roi.insufficient_data",
                      "Données insuffisantes : il faut au moins {n} mois où coexistent un "
                      "spend Meta Ads ET un revenu distributeur. En dessous, une droite "
                      "passe presque exactement par les points et le R² ne mesure rien."
                      ).format(n=MIN_FIT_POINTS))
            return
        _render_fit(fit)
    except ImportError:
        st.warning(t("trigger_algo.roi.scipy_unavailable", "scipy non disponible — régression désactivée."))
    except Exception as e:
        st.warning(t("trigger_algo.roi.regression_unavailable",
                     "Graphique ROI indisponible : {err}").format(err=e))


def _render_fit(fit: dict) -> None:
    """R247 (fiche 45) — the months and the trend, then the DECISION in words. The
    equation, R² and p-value are gone from the page (owner : « sans équation ni R² ») :
    they decide the verdict below, they are not what the artist acts on."""
    from src.dashboard.utils.roi_verdicts import fit_decision
    x, y = fit["x"], fit["y"]
    x_line = np.linspace(x.min(), x.max(), 100)
    fig_roi = go.Figure()
    fig_roi.add_trace(go.Scatter(
        x=x, y=y, mode="markers+text", text=fit["labels"], textposition="top center",
        name=t("trigger_algo.roi.trace_monthly", "Mensuel"),
        marker=dict(color=BON, size=10)))
    fig_roi.add_trace(go.Scatter(
        x=x_line, y=fit["slope"] * x_line + fit["intercept"], mode="lines",
        name=t("trigger_algo.roi.trace_trend", "Tendance"),
        line=dict(color="#FF6B6B", width=2, dash="dash")))
    fig_roi.update_layout(
        title=t("trigger_algo.roi.regression_chart_title",
                "Revenue iMusician (€) vs Spend Meta Ads (€)"),
        xaxis_title=t("trigger_algo.roi.axis_meta_spend", "Dépenses Meta Ads (€)"),
        yaxis_title=t("trigger_algo.roi.axis_imusician_revenue", "Revenus iMusician (€)"),
        height=420, hovermode="closest")
    charts.plotly_chart(fig_roi, width='stretch')
    kind, slope = fit_decision(fit)
    text = {
        "none": t("trigger_algo.roi.decision_none",
                  "**Sur {n} mois, tes revenus ne suivent pas ta pub** — les mois où tu as "
                  "plus dépensé n'ont pas rapporté plus. Juge ta pub sur les écoutes qu'elle "
                  "apporte (onglets Meta), pas sur tes ventes."),
        "pays": t("trigger_algo.roi.decision_pays",
                  "**Sur {n} mois, chaque euro de pub a ramené environ {k} € de revenus** — "
                  "la pub se rembourse en ventes : tu peux l'augmenter prudemment."),
        "short": t("trigger_algo.roi.decision_short",
                   "**Sur {n} mois, chaque euro de pub n'a ramené qu'environ {k} € de "
                   "revenus** — elle ne se rembourse pas en ventes : garde-la pour ce "
                   "qu'elle apporte en écoutes, ou baisse-la."),
    }[kind]
    st.markdown(text.format(n=fit["n"], k=f"{slope:.2f}".replace(".", ",") if slope else ""))


def _load_breakeven_frames(db, track: str, artist_id):
    """(spend per day, revenue per month) — EVERY euro in and out, not Meta vs iMusician.

    R248 (fiche 46, owner 2026-09-27 : « ajouter la SACEM, tous nos revenus, et nos charges
    comme le coût de distribution »). Revenue is the NET income of the gold ledger
    (`v_artist_monthly_cashflow`: distributors + SACEM); spend is Meta per day plus the
    costs the artist entered (distribution, mastering…), placed on their month.
    « All artists » (admin) goes through the HUMAN tenants only — the sandbox mirrors
    artist 1 and doubled this very sum once (R220); this branch had been missed.
    The popularity panel is gone: « aucune valeur ajoutée » next to two cumuls in euros.
    """
    from src.utils.fleet_money import FLEET_CASHFLOW_SQL
    from src.utils.tenant_kind import NON_HUMAN_TENANT
    if artist_id:
        cf = db.fetch_df("SELECT year, month, flux, source, amount_eur "
                         "FROM v_artist_monthly_cashflow WHERE artist_id = %s", (artist_id,))
        meta = db.fetch_df("SELECT day AS date, SUM(spend) AS spend FROM v_meta_daily "
                           "WHERE artist_id = %s GROUP BY day ORDER BY day", (artist_id,))
    else:
        cf = db.fetch_df(FLEET_CASHFLOW_SQL)
        meta = db.fetch_df(
            "SELECT day AS date, SUM(spend) AS spend FROM v_meta_daily WHERE artist_id IN "
            f"(SELECT id FROM saas_artists WHERE NOT {NON_HUMAN_TENANT}) GROUP BY day ORDER BY day")
    return split_ledger(cf, meta)


def split_ledger(cf: pd.DataFrame, meta: pd.DataFrame) -> tuple:
    """(spend per day: Meta + entered costs, revenue per month: every source). Pure."""
    if cf is None or cf.empty:
        return (meta if meta is not None else pd.DataFrame(columns=["date", "spend"])), \
            pd.DataFrame(columns=["date", "revenue_eur"])
    d = cf.copy()
    d["date"] = pd.to_datetime(d["year"].astype(int).astype(str) + "-"
                               + d["month"].astype(int).astype(str).str.zfill(2) + "-01")
    d["amount_eur"] = pd.to_numeric(d["amount_eur"], errors="coerce")
    rev = (d[d["flux"] == "revenu"].groupby("date", as_index=False)["amount_eur"].sum()
           .rename(columns={"amount_eur": "revenue_eur"}))
    costs = (d[(d["flux"] == "depense") & (d["source"] != "meta_ads")]
             .groupby("date", as_index=False)["amount_eur"].sum()
             .rename(columns={"amount_eur": "spend"}))
    # R294 — Postgres NUMERIC arrives as decimal.Decimal (dtype object) and the entered costs
    # as float: summed together they raise « Decimal + float », which broke this chart for
    # every track the day the first cost was entered (2026-09-28). Both sides are floats.
    if meta is not None and not meta.empty:
        meta = meta.assign(spend=pd.to_numeric(meta["spend"], errors="coerce"))
    parts = [x for x in (meta, costs) if x is not None and not x.empty]
    spend = (pd.concat(parts).assign(date=lambda x: pd.to_datetime(x["date"]))
             .groupby("date", as_index=False)["spend"].sum()) if parts \
        else pd.DataFrame(columns=["date", "spend"])
    return spend, rev


def _show_breakeven(db, track: str, artist_id, ml_pred) -> None:
    """Cumulative spend vs cumulative revenue, judged on the OVERLAP only.

    Two bounds, both computed by `roi_verdicts.cumulative_breakeven`:
    * the END (2026-09-10): past `covered_end` only one series is reported, and a flat
      cumul there guarantees a crossing that says nothing;
    * the START (2026-09-26): revenue began 7 months before the first ad euro for artist
      1, so a level test fired on the first spend day (0.48 € spent, 3.75 € earned) and
      the page said "breakeven reached" while spend led 3 087.82 € to 172.62 € at the end.
      Both cumuls now start at `covered_start`, and the date is a crossing from below
      that HOLDS up to `covered_end`.
    """
    from src.dashboard.utils.roi_verdicts import cumulative_breakeven

    st.subheader(t("trigger_algo.roi.breakeven_header", "⚖️ Breakeven — Cumul spend vs Cumul revenue"))
    _show_pi_breakeven(ml_pred)
    try:
        df_spend_d, df_rev = _load_breakeven_frames(db, track, artist_id)
        if df_spend_d.empty or df_rev.empty:
            st.info(t("trigger_algo.roi.breakeven_missing_data",
                      "Données spend ou revenue manquantes pour le graphique breakeven."))
            return
        be = cumulative_breakeven(df_spend_d, df_rev)
        if be["etat"] == "aucun_recouvrement":
            st.info(t(
                "trigger_algo.roi.breakeven_no_overlap",
                "Pas de verdict de breakeven : la dépense Meta et le revenu ne couvrent "
                "aucune période commune (dépense du {spend_start} au {spend_end}, revenu "
                "du {rev_start} au {rev_end}). Comparer deux cumuls qui ne se recouvrent "
                "pas ne dit rien."
            ).format(spend_start=format_date(pd.to_datetime(df_spend_d["date"]).min()),
                     spend_end=format_date(pd.to_datetime(df_spend_d["date"]).max()),
                     rev_start=format_date(pd.to_datetime(df_rev["date"]).min()),
                     rev_end=format_date(pd.to_datetime(df_rev["date"]).max())))
            return
        _render_breakeven(be, df_spend_d, df_rev)
    except Exception as e:
        st.warning(t("trigger_algo.roi.breakeven_unavailable",
                     "Graphique breakeven indisponible : {err}").format(err=e))


def _shade(fig_be, x0, x1) -> None:
    """La zone que le verdict ne couvre pas, ombrée : le lecteur voit où la comparaison
    cesse d'être une comparaison."""
    fig_be.add_vrect(
        x0=x0.timestamp() * 1000, x1=x1.timestamp() * 1000,
        fillcolor="rgba(120,120,120,0.10)", line_width=0,
        annotation_text=t("trigger_algo.roi.one_series_only", "une seule série renseignée"),
        annotation_position="top left", row="all", col=1)


def _render_breakeven(be: dict, df_spend_d, df_rev) -> None:
    df_tl = be["timeline"]
    covered_start, covered_end = be["covered_start"], be["covered_end"]
    _spend_end = pd.to_datetime(df_spend_d["date"]).max()
    _rev_end = pd.to_datetime(df_rev["date"]).max()
    _first = df_tl["date"].min()
    _tail_days = int((max(_spend_end, _rev_end) - covered_end).days)
    _tail_side = ("le revenu" if _rev_end > _spend_end else "la dépense")
    _head_days = int((covered_start - _first).days)

    # Les deux séries en euros PARTAGENT un axe — c'est précisément la comparaison qu'on
    # demande au lecteur de faire. R248 : plus de panneau de popularité.
    fig_be = make_subplots(rows=1, cols=1)
    fig_be.add_trace(go.Scatter(
        x=df_tl["date"], y=df_tl["cumul_spend"],
        name=t("trigger_algo.roi.trace_cumul_costs", "Cumul dépenses (pub + frais)"),
        mode="lines", line=dict(color="#FF6B6B", width=2),
        fill="tozeroy", fillcolor="rgba(255,107,107,0.08)"), row=1, col=1)
    fig_be.add_trace(go.Scatter(
        x=df_tl["date"], y=df_tl["cumul_revenue"],
        name=t("trigger_algo.roi.trace_cumul_income", "Cumul revenus (ventes + SACEM)"),
        mode="lines", line=dict(color=BON, width=2),
        fill="tozeroy", fillcolor="rgba(29,185,84,0.08)"), row=1, col=1)
    if _head_days > 0:
        _shade(fig_be, _first, covered_start)
    if _tail_days > 0:
        _shade(fig_be, covered_end, max(_spend_end, _rev_end))

    if be["etat"] == "croise":
        fig_be.add_vline(
            x=be["date"].timestamp() * 1000, line_dash="dash", line_color="white",
            annotation_text=t("trigger_algo.roi.breakeven_annotation", "Breakeven : {date}")
            .format(date=format_date(be["date"])),
            annotation_position="top right", row="all", col=1)
        st.success(t("trigger_algo.roi.breakeven_reached", "✅ Breakeven atteint le **{date}**")
                   .format(date=format_date(be["date"])))
    else:
        st.warning(t("trigger_algo.roi.breakeven_not_reached",
                     "⚠️ Breakeven non atteint sur la période disponible."))
    _caption_window(covered_start, covered_end, _head_days, _tail_days, _tail_side)

    fig_be.update_layout(
        title=t("trigger_algo.roi.breakeven_chart_title_all",
                "Tout ce qui rentre contre tout ce qui sort, cumulé"),
        hovermode="x unified", height=460, legend=dict(orientation="h", y=1.12))
    fig_be.update_yaxes(title_text=t("trigger_algo.roi.axis_cumul_amount", "Montant cumulé (€)"),
                        row=1, col=1)
    charts.plotly_chart(fig_be, width='stretch')


def _caption_window(covered_start, covered_end, head_days: int, tail_days: int,
                    tail_side: str) -> None:
    """Les DEUX bornes du verdict, dites plutôt que sous-entendues.

    Sans elles, un « non atteint » se lit comme un constat définitif, et un cumul remis à
    zéro au début du recouvrement se lit comme un revenu plus faible qu'avant.
    """
    if head_days > 0:
        st.caption(t(
            "trigger_algo.roi.breakeven_start",
            "Les deux cumuls partent de zéro le {date}, premier jour où dépense et revenu "
            "sont tous deux renseignés. Ce qui a été gagné ou dépensé avant ({days} jours) "
            "n'entre pas dans la comparaison : une avance prise avant le premier euro de "
            "pub n'est pas un retour sur cette pub."
        ).format(date=format_date(covered_start), days=head_days))
    if tail_days > 0:
        st.caption(t(
            "trigger_algo.roi.breakeven_window",
            "Verdict arrêté au {date} — au-delà, seul {side} est renseigné "
            "({days} jours). Comparer un cumul à une courbe que personne n'a "
            "encore rapportée ferait dire au croisement ce qu'il ne dit pas."
        ).format(date=format_date(covered_end), side=tail_side, days=tail_days))
