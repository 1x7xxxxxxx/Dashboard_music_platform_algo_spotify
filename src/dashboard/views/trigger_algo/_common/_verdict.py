"""trigger_algo verdict — move-only split of _common."""
from src.dashboard.utils import algo_knowledge as ak
from src.dashboard.utils import ml_widgets
from src.dashboard.utils.i18n import t
import json
import streamlit as st
from ._loaders import _clean_feat, _load_feature_importance, _load_scored_tracks


from src.utils.ml_outcome_labeling import TARGET_THRESHOLDS  # noqa: E402 — R402, one threshold set

ELBOW_THRESHOLDS_28D = {k.upper(): v for k, v in TARGET_THRESHOLDS.items()}




# `_display_prob_bar` and `_show_ml_section` were DELETED on 2026-09-26: nothing
# called them, and they printed every probability — floor values included — as a
# `{pct:.0f}%` next to a ✅/⚠️/❌ badge. Dead code that prints a floor as a measure is
# the next surface that gets rewired (`feedback_unwired_code_rots`).


def show_no_prediction_yet() -> None:
    """Ce qui remplace les trois barres du « mode heuristique ». SUPPRIMÉ 2026-09-22.

    `_show_heuristic_section` dessinait trois barres de progression quand aucune
    prédiction n'existait. Elle portait trois défauts, et aucun n'était réparable
    sans réinventer une méthode :

    1. **Un zéro codé en dur.** `_tab_global.py` l'appelait avec `current_pop = 0`.
       La barre Discover Weekly valant `(part_streams + part_popularité) / 2`, elle
       affichait donc **toujours** « Popularité : 0 % (obj. 30) » et un pourcentage
       DW **mécaniquement divisé par deux**, pour tout titre, depuis toujours.
    2. **Des cibles que le code désavouait lui-même** : la légende juste en dessous
       écrivait que 1 000 et 10 000 sont des « heuristiques arrondies ».
    3. **Un seuil détourné de son sens.** La barre Radio divisait les streams du
       titre par 639, qui est le volume d'algo-streams que la playlist ÉMET une fois
       déclenchée — un signal de détection, pas un objectif à atteindre. Le reste du
       paquet refuse d'ailleurs de tracer ces seuils comme cibles.

    Trois barres fabriquées donnent l'apparence d'un diagnostic. Une phrase qui dit
    ce qu'on sait vaut mieux — et c'est tout ce qu'on sait.
    """
    st.info(t("trigger_algo.common.heuristic_mode",
              "⚠️ **Pas encore de prédiction pour ce titre.** Le calcul tourne chaque "
              "nuit dès qu'un titre a au moins une écoute sur les 35 derniers jours."))


_VERDICT_LABELS = {"DW": "Discover Weekly", "RR": "Release Radar", "RADIO": "Radio"}


def _verdict_message(ml_pred: dict | None) -> tuple[str, str, str | None, float | None] | None:
    """The banner as data — `(kind, text, algo, prob)`, or `None` with nothing to say. Pure.

    The argmax runs ONLY over probabilities that pass the shared floor door
    (`proba_affichable`). When all three are on the calibration floor there is no
    percentage and no STOP/OPTIMISER/SCALER verdict: kind `"floor"`. Before
    2026-09-26 the max of three floors was always Radio's intercept (~10,7 %), and
    the banner told the artist to STOP their ads on it.
    """
    from src.dashboard.utils.algo_preview_data import proba_affichable

    if not ml_pred:
        return None
    raw = {"DW": ml_pred.get("dw_probability"), "RR": ml_pred.get("rr_probability"),
           "RADIO": ml_pred.get("radio_probability")}
    if all(v is None for v in raw.values()):
        return None
    scored = {k: p for k, v in raw.items()
              if (p := proba_affichable(k.lower(), v)) is not None}
    if not scored:
        return ("floor", t(
            "trigger_algo.common.verdict_floor",
            "⚪ **Pas d'estimation fiable** — pour ce titre, le modèle n'a rien tranché "
            "sur aucun des trois algorithmes (score au plancher de la calibration). "
            "Aucun verdict STOP / SCALER ne peut en être tiré."), None, None)
    best_algo = max(scored, key=scored.get)
    best_prob = scored[best_algo]
    label = _VERDICT_LABELS[best_algo]
    if best_prob < 0.20:
        return ("stop", t(
            "trigger_algo.common.verdict_stop",
            "🔴 **STOP** — signaux algorithmiques faibles (meilleure piste : "
            "{algo} {prob:.0%}). Stoppez vos Meta Ads sur ce titre "
            "pour préserver votre budget."
        ).format(algo=label, prob=best_prob), best_algo, best_prob)
    if best_prob < 0.50:
        return ("optimize", t(
            "trigger_algo.common.verdict_optimize",
            "🟠 **OPTIMISER** — potentiel détecté ({algo} {prob:.0%}), "
            "mais il manque un déclencheur."
        ).format(algo=label, prob=best_prob), best_algo, best_prob)
    return ("scale", t(
        "trigger_algo.common.verdict_scale",
        "🟢 **SCALER** — ADN de hit détecté ({algo} {prob:.0%}). "
        "L'algorithme est prêt à prendre le relais : augmentez votre budget quotidien "
        "de ~20 % pour maximiser l'effet boule de neige."
    ).format(algo=label, prob=best_prob), best_algo, best_prob)


def _show_verdict_banner(ml_pred: dict | None) -> None:
    """Consolidated kill / optimize / scale decision at the top of the algos tab.

    Headline verdict on the best algorithmic opportunity (max of the 3 probs).

    ⚠️ CETTE DOCSTRING DISAIT L'INVERSE DU CODE — corrigé le 2026-09-22.

    Elle affirmait « Probabilities are NOT calibrated », pendant que la légende
    rendue trois lignes plus bas affirmait « calibrées (Platt) ». Quatre surfaces du
    paquet se contredisaient sur ce point. Le code tranche :
    `machine_learning/models/v3/calibration.json` existe et `ml_inference._calibrate`
    l'applique à chaque inférence. **Les probabilités SONT calibrées.**

    Mais le fait utile n'est pas « c'est calibré » — c'est le PLANCHER que la
    calibration introduit, et que personne n'avait écrit. Les intercepts étant
    négatifs, un score brut NUL ne rend pas 0 % :

        DW 6,53 %  ·  RR 6,51 %  ·  Radio 10,72 %

    Une probabilité posée sur ces valeurs ne dit donc pas « le modèle hésite » : elle
    dit **« le modèle a rendu zéro »**. Mesuré sur les dix titres de l'artiste 1 le
    2026-09-22 — RR y va de 0,0654 à 0,0656, soit un écart de score brut de 0,0007.
    Garde : `tests/test_a_calibrated_floor_is_not_a_ranking.py`.
    """
    verdict = _verdict_message(ml_pred)
    if verdict is None:
        return
    kind, text, best_algo, best_prob = verdict
    if kind == "floor":
        st.info(text)
        return

    try:
        feats = json.loads(ml_pred.get("features_json") or "{}")
    except (ValueError, TypeError):
        feats = {}

    if kind == "stop":
        st.error(text)
    elif kind == "optimize":
        st.warning(text)
        actions = ak.build_coach_actions(best_algo, feats)
        if actions:
            a = actions[0]
            _lever = ml_widgets.lever_text(best_algo, a['feature'], a)
            _label = ml_widgets.label_text(a['feature'], a)
            st.caption(t("trigger_algo.common.verdict_lever1", "🎯 Levier #1 — {label} : {lever}")
                       .format(label=_label, lever=_lever))
    else:
        st.success(text)
    note = ml_widgets.calibration_note_text(best_algo, best_prob)
    if note:
        st.caption(t("trigger_algo.common.verdict_reliability", "ℹ️ Fiabilité du score : {note}")
                   .format(note=note))
    st.caption(t(
        "trigger_algo.common.verdict_platt",
        "Probabilités calibrées (Platt) — les seuils 20 %/50 % correspondent à de vraies "
        "probabilités de déclenchement. ⚠️ Une valeur proche de **6,5 % (DW/RR)** ou de "
        "**10,7 % (Radio)** est le PLANCHER de la calibration : elle signifie que le "
        "modèle a rendu zéro, pas qu'il hésite. Deux titres posés dessus ne se "
        "comparent pas."
    ))


def _show_radio_snowball(db, artist_id) -> None:
    """Snowball radar — count catalogue songs the model rates as radio-active.

    Proxy via radio_probability >= 0.5 (NOT the imputed-to-0 feature
    HowManySongsDoYouHaveInRadioRightNow). 3+ active songs is the "trusted artist"
    signal: a new release is then more likely to get an algorithmic free pass.
    """
    df = _load_scored_tracks(db, artist_id)
    if df is None or "radio_probability" not in df:
        return
    n = int((df["radio_probability"].fillna(0) >= 0.5).sum())
    if n >= 3:
        st.success(t(
            "trigger_algo.common.snowball_safe",
            "🏆 **Statut « Valeur Sûre »** — {n} titres en radio algorithmique active. "
            "Moment idéal pour sortir un nouveau single : il sera poussé plus facilement."
        ).format(n=n))
    elif n >= 1:
        st.info(t(
            "trigger_algo.common.snowball_warming",
            "🔥 **En chauffe** — {n} titre(s) en radio active. Atteignez 3 titres pour "
            "débloquer le « passe-droit » algorithmique sur vos prochaines sorties."
        ).format(n=n))
    else:
        st.caption(t(
            "trigger_algo.common.snowball_cold",
            "❄️ Aucun titre en radio algorithmique active (estimation modèle). "
            "Concentrez les efforts pour percer un premier titre."
        ))
    st.caption(t(
        "trigger_algo.common.snowball_caption",
        "Effet boule de neige — estimation modèle (radio_probability ≥ 0,5), pas le "
        "décompte radio réel (donnée non collectée à l'inférence)."
    ))


def _show_resurrection_radar(db, artist_id) -> None:
    """Long-tail resurrection radar — old songs (>6 mo) with a sudden saves spike.

    Dormant until ~2 weeks of daily saves history accumulate (snapshot written by
    the ml_scoring_daily DAG → src/utils/saves_history.snapshot_saves).
    """
    try:
        from src.utils.saves_history import detect_saves_resurrection
        sparks = detect_saves_resurrection(db, artist_id)
    except Exception:
        return
    st.subheader(t("trigger_algo.common.resurrection_header", "✨ Résurrection longue traîne"))
    if not sparks:
        st.caption(t(
            "trigger_algo.common.resurrection_none",
            "Aucune étincelle détectée sur vos anciens titres (> 6 mois). Le radar "
            "s'active une fois ~2 semaines d'historique de saves accumulées "
            "(collecte quotidienne automatique)."
        ))
        return
    for s in sparks[:5]:
        st.success(t(
            "trigger_algo.common.resurrection_spark",
            "✨ **{song}** ({age} j) — +{gain} saves récents. "
            "Injectez un petit budget Ads aujourd'hui pour réveiller le Discover Weekly."
        ).format(song=s['song'], age=s['age_days'], gain=s['recent_gain']))


_PHASES = [
    (0, 35, "🚀 Phase 1 — Release Radar (0-35 j)",
     "Fenêtre de tir RR. Maximise les **clics/CTR** via Meta Ads sur une audience "
     "high-intent. **N'active PAS le Discovery Mode** (impact nul sur RR, −30 % de "
     "royalties pour rien). Objectif : convertir en followers + ≥ ~2 000 streams récents."),
    (35, 90, "🎧 Phase 2 — Discover Weekly (35-90 j)",
     "Le Release Radar s'arrête : c'est le moment de **réveiller le DW**, ne coupe pas "
     "le budget. Pivote vers l'**engagement qualitatif** — CTA explicite « Ajoutez ce "
     "titre en playlist » (vise ~175 ajouts + ~165 saves/28j), pas « écoutez »."),
    (90, 10_000, "📻 Phase 3 — Radio & longue traîne (90 j+)",
     "Stabilise la rentabilité. **Active le Discovery Mode** pour forcer l'entrée en "
     "Radio, puis applique le **kill-switch royalties** une fois le titre installé "
     "(> 10 000 streams/j en Radio) : l'inertie organique suffit, récupère tes 30 %."),
]


def _show_phase_strategy(ml_pred: dict | None) -> None:
    """Per-song strategic phase (1/2/3 by age) + the action that phase calls for."""
    if not ml_pred:
        return
    try:
        feats = json.loads(ml_pred.get("features_json") or "{}")
        days = float(feats.get("DaysSinceRelease"))
    except (ValueError, TypeError):
        return
    for lo, hi, title, advice in _PHASES:
        if lo <= days < hi:
            st.markdown(t("trigger_algo.common.phase_title", "**{title}** · titre à J+{days}")
                        .format(title=title, days=int(days)))
            st.caption(advice)
            break


def _show_feature_importance() -> None:
    """Ranked variable hierarchy per algorithm (gain XGBoost ≈ SHAP magnitude)."""
    imp = _load_feature_importance()
    if not imp:
        return
    with st.expander(t("trigger_algo.common.feat_imp_expander",
                       "📊 Hiérarchie des 13 variables par algorithme"), expanded=False):
        st.caption(t("trigger_algo.common.feat_imp_caption",
                     "Poids relatif de chaque variable dans la décision du modèle "
                     "(gain XGBoost — proxy de l'importance SHAP globale)."))
        cols = st.columns(3)
        algos = [("dw", "Discover Weekly"), ("rr", "Release Radar"), ("radio", "Radio")]
        for col, (algo, label) in zip(cols, algos):
            with col:
                st.markdown(f"**{label}**")
                rows = imp.get(algo, [])
                total = sum(r["gain"] for r in rows) or 1.0
                for i, r in enumerate(rows[:8], 1):
                    st.caption(f"{i}. {_clean_feat(r['feature'])} — {r['gain'] / total:.0%}")


def _show_discovery_mode_protocol() -> None:
    """Static Discovery Mode activation/kill-switch protocol (the 'pay-to-play' paradox)."""
    with st.expander(t("trigger_algo.common.dm_protocol_expander",
                       "🎚️ Protocole Discovery Mode (activation & kill-switch)"), expanded=False):
        st.markdown(t(
            "trigger_algo.common.dm_protocol_body",
            "- **Release Radar (semaine 1)** : impact **nul** — ne sacrifie pas 30 % de "
            "tes royalties, c'est inefficace.\n"
            "- **Radio (mois 3+)** : **levier d'activation** — il force l'entrée en Radio "
            "(le « videur VIP »), mais ne scale pas le volume.\n"
            "- **Kill-switch** : dès qu'un titre dépasse **~10 000 streams/jour en Radio**, "
            "**désactive** le Discovery Mode — l'inertie organique suffit, tu récupères "
            "ta marge de 30 %."
        ))
        st.caption(t(
            "trigger_algo.common.dm_protocol_caption",
            "Statut Discovery Mode live non collecté (imputé à 0 à l'inférence) — "
            "protocole affiché à titre indicatif."
        ))
