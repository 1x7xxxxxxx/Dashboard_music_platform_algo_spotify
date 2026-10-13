"""trigger_algo — _show_tab_budget_roi (move-only split)."""
from src.dashboard.utils import algo_knowledge as ak, charts
from src.dashboard.utils.semantic_colors import ATTENTION, NEUTRE
from src.dashboard.utils.i18n import t
import plotly.graph_objects as go
import streamlit as st
from ._common._budget_roi import ACTIVE_LIFETIME_SPEND_SQL, remaining_lifetime_budget
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

    # ── LE PANNEAU DE RÉGLAGES EN TÊTE — 2026-09-22 ─────────────────────────
    # Les réglages d'une campagne vivaient éparpillés sur quatre surfaces. Ils sont
    # désormais mesurés sur la même base, à la même maille, et classés par leur
    # effet réel. Il vient AVANT le budget : on décide quoi régler avant de décider
    # combien mettre.
    from ._tab_reglages import _show_reglages
    _show_reglages(db, artist_id, track)

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
            lifetime_spend_row = db.fetch_query(
                ACTIVE_LIFETIME_SPEND_SQL + " WHERE d.artist_id = %s", (artist_id,))
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
            lifetime_spend_row = db.fetch_query(ACTIVE_LIFETIME_SPEND_SQL)
            streams_row = db.fetch_query(
                "SELECT COALESCE(SUM(streams), 0) FROM v_s4a_song_daily "
                "WHERE day BETWEEN %s AND %s",
                (date_from, date_to)
            )

        lifetime_budget = float(budget_row[0][0] or 0)
        total_spend = float(spend_row[0][0] or 0)
        total_streams = int(streams_row[0][0] or 0)
        lifetime_spend = float(lifetime_spend_row[0][0] or 0)
        # R526 — a lifetime budget minus the spend of the SELECTED window was wrong for
        # any window shorter than the campaigns' life, and `max(…, 0)` hid overspend.
        remaining = remaining_lifetime_budget(lifetime_budget, lifetime_spend)

        b1, b2, b3, b4 = st.columns(4)
        b1.metric(t("trigger_algo.roi.lifetime_budget_metric", "Budget lifetime alloué"),
                  f"{lifetime_budget:,.2f} €")
        b2.metric(t("trigger_algo.roi.spent_metric", "Dépensé (période)"), f"{total_spend:,.2f} €")
        if remaining < 0:
            b3_label = t("trigger_algo.roi.overspent_metric", "Budget dépassé de")
            b3_delta = f"{remaining:,.2f} €"
        else:
            b3_label = t("trigger_algo.roi.remaining_metric", "Restant estimé")
            b3_delta = (f"{remaining / lifetime_budget * 100:.0f}%"
                        if lifetime_budget > 0 else None)
        b3.metric(b3_label, f"{abs(remaining):,.2f} €", delta=b3_delta,
                  help=t("trigger_algo.roi.remaining_help",
                         "Budget à vie des campagnes actives moins tout ce qu'elles ont "
                         "déjà dépensé — indépendant de la période choisie."))

        if total_streams > 0 and total_spend > 0:
            cost_per_stream = total_spend / total_streams
            b4.metric(t("trigger_algo.roi.cost_per_stream_metric", "Coût / stream"),
                      f"{cost_per_stream:.4f} €")
        else:
            b4.metric(t("trigger_algo.roi.cost_per_stream_metric", "Coût / stream"), "—")
            if lifetime_budget == 0:
                st.info(t("trigger_algo.roi.no_active_campaign",
                          "Aucune campagne Meta active trouvée pour cet artiste."))

        if lifetime_budget > 0:
            # R404 (V68): the allotted budget as ONE bar — spent, then what is left.
            fig_b = go.Figure()
            fig_b.add_trace(go.Bar(
                x=[min(lifetime_spend, lifetime_budget)], y=[""], orientation="h",
                marker_color=ATTENTION,
                name=t("trigger_algo.roi.lifetime_spent_label", "Dépensé (depuis le lancement)")))
            fig_b.add_trace(go.Bar(
                x=[max(remaining, 0)], y=[""], orientation="h", marker_color=NEUTRE,
                name=t("trigger_algo.roi.remaining_metric", "Restant estimé")))
            fig_b.update_layout(barmode="stack", height=140, margin=dict(l=0, r=0, t=10, b=0),
                                xaxis_title="€")
            charts.plotly_chart(fig_b, width="stretch")

        if total_spend > 0:
            _show_velocity_budget_advice(db, track, artist_id, total_spend)
    except Exception as e:
        st.warning(t("trigger_algo.roi.meta_budget_unavailable",
                     "Budget Meta indisponible : {err}").format(err=e))


    # 1bis. Organic scaling threshold (volume) — the gap reads the Saisie S4A entry.
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
        st.caption(organic_gap_caption(_latest_track_nonalgo(db, artist_id, track), _scale))

    _show_budget_pacing_calculator(db, artist_id)

    # 2. Groover / Fluence simulator
    with st.expander(t("trigger_algo.roi.playlist_budget_expander",
                       "💶 Budget playlist — Groover & Fluence"), expanded=False):
        # R404 (V68): the rate table is gone — each rate is in the platform selector.
        st.caption(t("trigger_algo.roi.reference_rates",
                     "Tarifs de référence — vérifiez les prix actuels sur les plateformes."))
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


    # R553 (owner Y1, fiches 50 and 51): « revenue against Meta spend » and « when will
    # the ads be paid back » moved to « 💶 Trésorerie », the one money page. The PI
    # gates stay: they are this track's algo question, not money.
    _show_pi_breakeven(ml_pred)


def _latest_track_nonalgo(db, artist_id, track: str):
    """(streams_28d, recorded_at) of the latest manual Saisie S4A entry for this track, or None."""
    rows = db.fetch_query(
        """SELECT streams_28d, recorded_at FROM s4a_song_nonalgo_streams
           WHERE artist_id = %s AND song = %s ORDER BY recorded_at DESC LIMIT 1""",
        (artist_id, track)) if artist_id and track else []
    return (int(rows[0][0]), rows[0][1]) if rows else None


def organic_gap_caption(entry, scale: int) -> str:
    """R510 — the gap to the DW volume threshold, computed from the MANUAL entry (mig. 052).

    The caption used to say the value was « not yet collected (Phase 2) » while the
    Saisie S4A page had been collecting it since mig. 052."""
    if entry is None:
        return t("trigger_algo.roi.organic_gap_none",
                 "Saisis les streams non-algo (28 j) de ce titre dans « 📝 Saisie S4A » "
                 "pour voir l'écart à ce seuil.")
    streams, day = entry
    if streams >= scale:
        return t("trigger_algo.roi.organic_gap_reached",
                 "✅ Ta saisie du {day} : {n:,} streams non-algo sur 28 j — seuil atteint."
                 ).format(day=format_date(day), n=streams)
    return t("trigger_algo.roi.organic_gap_missing",
             "Ta saisie du {day} : {n:,} streams non-algo sur 28 j — il en manque "
             "**{gap:,}**.").format(day=format_date(day), n=streams, gap=scale - streams)
