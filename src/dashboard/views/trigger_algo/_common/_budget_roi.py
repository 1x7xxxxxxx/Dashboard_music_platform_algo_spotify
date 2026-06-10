"""trigger_algo budget_roi — move-only split of _common."""
from src.dashboard.utils import algo_knowledge as ak
from src.dashboard.utils.i18n import t
import pandas as pd
import streamlit as st
from ._loaders import _load_scored_tracks


_TRIGGER_STREAM_TARGETS = {
    "Release Radar": 417,
    "Discover Weekly": 1333,
    "Radio": 8423,
}


_GATE_28D = {
    "Discover Weekly": {"streams": 9200, "listeners": 4100},
    "Release Radar": {"streams": 1300, "listeners": 600},
    "Radio": {"streams": 8400, "listeners": 4000},
}


def _show_28d_gate(db, track: str, artist_id) -> None:
    """28-day streams/listeners gate per algo — is the track above each trigger threshold?

    Per-song listeners only exist as the 28-day snapshot (s4a_songs_global), not a daily
    series, so this is a gate panel rather than a chart line.
    """
    try:
        row = db.fetch_query(
            """SELECT listeners, streams FROM s4a_songs_global
               WHERE artist_id = %s AND song = %s AND time_window = '28d' LIMIT 1""",
            (artist_id, track),
        )
    except Exception:
        return
    if not row or row[0][0] is None:
        return
    listeners, streams = int(row[0][0] or 0), int(row[0][1] or 0)
    st.markdown(t("trigger_algo.common.gate28_header",
                  "**🚪 Porte 28 jours — streams & listeners vs seuils par algo**"))
    st.caption(t("trigger_algo.common.gate28_caption",
                 "Ce titre (28j) : **{streams:,} streams** · **{listeners:,} listeners**.")
               .format(streams=streams, listeners=listeners))
    cols = st.columns(len(_GATE_28D))
    for col, (algo, g) in zip(cols, _GATE_28D.items()):
        with col:
            st.markdown(f"**{algo}**")
            st.caption(t("trigger_algo.common.gate28_streams", "{mark} streams ≥ {thr:,}")
                       .format(mark='✅' if streams >= g['streams'] else '❌', thr=g['streams']))
            st.caption(t("trigger_algo.common.gate28_listeners", "{mark} listeners ≥ {thr:,}")
                       .format(mark='✅' if listeners >= g['listeners'] else '❌', thr=g['listeners']))
    st.caption(t("trigger_algo.common.gate28_note",
                 "Seuils 28j approximatifs, dérivés de data_anon.csv (knee du taux de succès)."))


def _show_budget_tier_selector(db, artist_id):
    """A&R portfolio tool: select the top-N% tracks by score (lift/precision tradeoff)."""
    st.subheader(t("trigger_algo.common.ar_selector_header", "🎯 Sélection A&R par budget (top-N%)"))
    df = _load_scored_tracks(db, artist_id)
    if df is None or len(df) < 3:
        st.info(t("trigger_algo.common.ar_selector_min",
                  "Outil disponible dès ≥ 3 titres scorés (échelle catalogue). "
                  "Lancez le DAG `ml_scoring_daily`."))
        return
    m = ak.ALGO_MODEL_METRICS.get("DW", {})
    n = len(df)
    pct = st.slider(t("trigger_algo.common.ar_slider", "Pousser le top N% par score"),
                    10, 100, 20, step=10,
                    help=t("trigger_algo.common.ar_slider_help",
                           "Seuil bas → précision haute (peu de gâchis) ; seuil haut → recall élevé."))
    k = max(1, (n * pct + 99) // 100)
    sel = df.head(k)
    c1, c2, c3 = st.columns(3)
    c1.metric(t("trigger_algo.common.ar_selected_metric", "Titres sélectionnés"), f"{k}/{n}")
    c2.metric(t("trigger_algo.common.ar_precision_metric", "Précision modèle"),
              f"{m.get('precision', 0) * 100:.0f}%")
    if pct <= 10:
        c3.metric(t("trigger_algo.common.ar_lift_metric", "Lift top-10%"),
                  f"×{m.get('lift_top10', 0):.1f}")
    else:
        c3.metric(t("trigger_algo.common.ar_recall_metric", "Recall (rappel)"),
                  f"{m.get('recall', 0) * 100:.0f}%")
    st.caption(t("trigger_algo.common.ar_caption",
                 "Budget serré → vise le top 10% (précision quasi parfaite, peu de gâchis). "
                 "Gros budget → baisse le seuil pour capter plus d'opportunités (recall ↑, précision ↓)."))
    show = sel[["song", "score_20"]].copy()
    show["score_20"] = show["score_20"].fillna(0).round(1)
    show.columns = [t("trigger_algo.common.ar_col_track", "Titre à pousser"),
                    t("trigger_algo.common.ar_col_score", "Score /20")]
    st.dataframe(show, hide_index=True, width="stretch")


def _show_velocity_budget_advice(db, track, artist_id, spent):
    """Concrete spend-smoothing advice when the track's velocity is too high.

    Cross-links the Explainabilité coach's qualitative 'smooth velocity' action to
    a euro amount: hyper-growth gets penalised, so suggest a ~30% spend cut to
    smooth the traffic. Thresholds come from algo_knowledge (no hardcoded cutoff).
    """
    try:
        if artist_id:
            rows = db.fetch_query(
                """SELECT CAST(features_json->>'Velocity_Streams' AS FLOAT)
                   FROM ml_song_predictions WHERE song = %s AND artist_id = %s
                   ORDER BY prediction_date DESC LIMIT 1""",
                (track, artist_id))
        else:
            rows = db.fetch_query(
                """SELECT CAST(features_json->>'Velocity_Streams' AS FLOAT)
                   FROM ml_song_predictions WHERE song = %s
                   ORDER BY prediction_date DESC LIMIT 1""",
                (track,))
        vel = float(rows[0][0]) if rows and rows[0][0] is not None else None
    except Exception:
        return
    # Gate + displayed cutoffs derive from algo_knowledge zones (single source of
    # truth) — the DW malus zone is the stricter/lower trigger.
    if vel is None or ak.zone_for_value("DW", "Velocity_Streams", vel) != "malus":
        return
    dw_thr = ak.velocity_penalty_threshold("DW")
    radio_thr = ak.velocity_penalty_threshold("RADIO")
    reduced = spent * 0.7
    st.warning(t(
        "trigger_algo.common.velocity_advice",
        "⚡ Vélocité élevée ({vel:.2f}) sur « {track} » — la Radio (seuil {radio:g}) "
        "et le DW ({dw:g}) pénalisent l'hyper-croissance (« feu de paille »). Suggestion : "
        "réduire la dépense de ~30 % ({spent:,.0f} € → {reduced:,.0f} €) pour lisser le trafic."
    ).format(vel=vel, track=track, radio=radio_thr, dw=dw_thr, spent=spent, reduced=reduced))


def _show_budget_pacing_calculator(db, artist_id) -> None:
    """Proactive budget-pacing planner: spread spend over the algo eval window to
    avoid the velocity-spike penalty. The euro->velocity mapping is heuristic (no
    model): the deliverable is the smoothing recommendation, not a guaranteed
    target velocity. Complements the reactive _show_velocity_budget_advice.
    """
    st.subheader(t("trigger_algo.common.pacing_header", "📅 Lisseur de budget (Pacing)"))
    default_budget, current_daily = 200.0, 0.0
    try:
        if artist_id:
            row = db.fetch_query(
                "SELECT COALESCE(SUM(lifetime_budget),0), COALESCE(SUM(daily_budget),0) "
                "FROM meta_campaigns WHERE artist_id = %s AND status = 'ACTIVE'", (artist_id,))
        else:
            row = db.fetch_query(
                "SELECT COALESCE(SUM(lifetime_budget),0), COALESCE(SUM(daily_budget),0) "
                "FROM meta_campaigns WHERE status = 'ACTIVE'")
        default_budget = float(row[0][0] or 0) or 200.0
        current_daily = float(row[0][1] or 0)
    except Exception:
        pass

    c1, c2 = st.columns(2)
    budget = c1.number_input(t("trigger_algo.common.pacing_budget_input", "Budget à étaler (€)"),
                             min_value=0.0, value=float(round(default_budget, 2)), step=10.0)
    window = c2.number_input(t("trigger_algo.common.pacing_window_input", "Fenêtre de lissage (jours)"),
                             min_value=7, max_value=90, value=28, step=1,
                             help=t("trigger_algo.common.pacing_window_help",
                                    "28 j = fenêtre d'évaluation des algos."))
    if budget <= 0:
        return
    per_day = budget / window
    st.metric(t("trigger_algo.common.pacing_daily_metric", "Dépense quotidienne recommandée"),
              f"{per_day:,.2f} €/jour")
    vthr = ak.velocity_penalty_threshold("DW")
    vtxt = f"~{vthr:g}" if vthr else t("trigger_algo.common.pacing_penalty_threshold", "le seuil de pénalité")
    st.info(t(
        "trigger_algo.common.pacing_info",
        "Étalez **{budget:,.0f} €** sur **{window} jours** (~{per_day:,.0f} €/jour) pour "
        "maintenir une croissance organique et éviter le « pic suspect » que le Discover "
        "Weekly pénalise (vélocité au-delà de {vtxt})."
    ).format(budget=budget, window=window, per_day=per_day, vtxt=vtxt))
    if current_daily > 0:
        burn_days = budget / current_daily
        if burn_days < 14:
            st.warning(t(
                "trigger_algo.common.pacing_burn_warning",
                "⚠️ Votre budget quotidien actuel (~{daily:,.0f} €/jour) épuiserait "
                "ce budget en ~{burn:.0f} jours → risque de pic de vélocité. "
                "Réduisez à ~{per_day:,.0f} €/jour."
            ).format(daily=current_daily, burn=burn_days, per_day=per_day))
    st.caption(t(
        "trigger_algo.common.pacing_caption",
        "Le lien €→vélocité est une heuristique de lissage (étalement sur la fenêtre "
        "d'éval), pas une vélocité-cible garantie."
    ))


_META_LEVER_QUERY = """
SELECT
    ctm.campaign_name,
    perf.spend, perf.results, perf.cpr, perf.ctr, perf.link_clicks,
    cta.ctas
FROM campaign_track_mapping ctm
LEFT JOIN (
    SELECT campaign_name, SUM(spend) AS spend, SUM(results) AS results,
           CASE WHEN SUM(results) > 0 THEN SUM(spend)::numeric / SUM(results) END AS cpr,
           AVG(NULLIF(ctr, 0)) AS ctr, SUM(link_clicks) AS link_clicks
    FROM meta_insights_performance WHERE artist_id = %s GROUP BY campaign_name
) perf ON LOWER(perf.campaign_name) = LOWER(ctm.campaign_name)
LEFT JOIN (
    SELECT mc.campaign_name, string_agg(DISTINCT a.call_to_action, ', ') AS ctas
    FROM meta_campaigns mc JOIN meta_ads a ON a.campaign_id = mc.campaign_id
    WHERE mc.artist_id = %s AND a.call_to_action IS NOT NULL
    GROUP BY mc.campaign_name
) cta ON LOWER(cta.campaign_name) = LOWER(ctm.campaign_name)
WHERE ctm.artist_id = %s AND LOWER(ctm.track_name) = LOWER(%s)
ORDER BY perf.cpr ASC NULLS LAST
"""


def _show_meta_lever_scoring(db, track: str, artist_id) -> None:
    """Score the marketing levers against REAL Meta Ads performance for this track.

    Joins the track's mapped campaigns (campaign_track_mapping) to their CSV perf
    (meta_insights_performance: CPR/CTR/results) + the ads' call_to_action — so the
    generic SHAP levers become "which campaign/CTA actually performed". Reuses the
    meta_cpr_optimizer join pattern.
    """
    st.markdown("---")
    st.markdown(t("trigger_algo.common.meta_lever_header",
                  "**🎯 Leviers marketing — performance Meta Ads réelle de ce titre**"))
    try:
        df = db.fetch_df(_META_LEVER_QUERY, (artist_id, artist_id, artist_id, track))
    except Exception as e:
        st.caption(t("trigger_algo.common.meta_lever_unavailable",
                     "Données Meta indisponibles : {err}").format(err=e))
        return
    if df is None or df.empty:
        st.caption(t("trigger_algo.common.meta_lever_no_campaign",
                     "Aucune campagne Meta mappée à ce titre — mappe-les dans la vue "
                     "« Meta ↔ Spotify » pour scorer tes leviers sur les perfs réelles."))
        return

    df = df.copy()
    df["cpr"] = pd.to_numeric(df["cpr"], errors="coerce")
    df["ctr"] = pd.to_numeric(df["ctr"], errors="coerce")
    show = df.rename(columns={
        "campaign_name": t("trigger_algo.common.meta_col_campaign", "Campagne"),
        "spend": "Spend €", "results": "Results",
        "cpr": "CPR €", "ctr": "CTR %",
        "link_clicks": t("trigger_algo.common.meta_col_clicks", "Clics"), "ctas": "CTA",
    })
    st.dataframe(show, hide_index=True, width='stretch')

    scored = df.dropna(subset=["cpr"])
    if not scored.empty:
        best = scored.loc[scored["cpr"].idxmin()]
        worst = scored.loc[scored["cpr"].idxmax()]
        st.success(t("trigger_algo.common.meta_best_lever",
                     "✅ Meilleur levier : **{name}** — CPR {cpr:.3f} € ({cta})")
                   .format(name=best['campaign_name'], cpr=best['cpr'],
                           cta=best['ctas'] or t("trigger_algo.common.cta_na", "CTA n/d")))
        if worst["campaign_name"] != best["campaign_name"]:
            st.warning(t("trigger_algo.common.meta_worst_lever",
                         "⚠️ Moins efficace : **{name}** — CPR {cpr:.3f} € "
                         "→ réalloue vers le CTA/audience qui performe.")
                       .format(name=worst['campaign_name'], cpr=worst['cpr']))
    st.caption(t("trigger_algo.common.meta_cpr_caption",
                 "CPR = coût par résultat (plus bas = mieux). Croise avec le levier SHAP "
                 "pénalisé : le CTA « Ajouter en playlist » bat « Écouter » sur le DW."))
