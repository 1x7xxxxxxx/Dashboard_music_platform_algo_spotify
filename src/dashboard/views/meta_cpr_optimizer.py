"""CPR Optimizer — Score ML × CPR + recommandations de budget, section de la page algo.

Type: Sub
Triggers: views/trigger_algo/router.py (section « budget », R477) — no page of its own
Uses: get_db_connection, get_artist_id, require_plan
Depends on: meta_insights_performance, campaign_track_mapping, ml_song_predictions
Score: max(dw_prob, rr_prob, radio_prob) × (cpr_median / cpr_campaign)
       → normalisé 0-10. Seuils: ≥7 → +30%, 5-7 → +10%, 3-5 → neutre, <3 → -30%.
       ⚠️ The ML factor is the max of the OFF-floor probabilities only
       (`algo_preview_data.proba_affichable`); when any scored campaign has no
       off-floor probability, the ML factor is NEUTRAL (1.0) for every campaign —
       see `_ml_factor` / `_compute_scores` (2026-09-26).
"""
import pandas as pd
import streamlit as st

from src.dashboard.utils.algo_preview_data import (
    format_proba, proba_affichable, texte_plancher)
from src.dashboard.utils.filters import account_clause, account_scope
from src.dashboard.utils.i18n import t
from src.dashboard.utils.proxy_disclosure import disclosure_caption
from src.dashboard.utils.meta_confidence import K_DEFAUT, confidence_factor
from src.utils.algo_order import ALGO_ORDER
from src.utils.track_matching import canonical_song_sql


# ── Seuils score ─────────────────────────────────────────────────────────────
_SCORE_THRESHOLDS = [
    (7.0,  "🟢 Augmenter",  "+30%",  "+30%",  "#28a745"),
    (5.0,  "🟡 Augmenter",  "+10%",  "+10%",  "#ffc107"),
    (3.0,  "⚪ Maintenir",  "=",     "=",     "#6c757d"),
    (0.0,  "🔴 Réduire",    "-30%",  "-30%",  "#dc3545"),
]
# FR label → stable i18n slug (labels translated at call time in _get_recommendation).
_REC_SLUGS = {
    "🟢 Augmenter": "increase_strong",
    "🟡 Augmenter": "increase_light",
    "⚪ Maintenir": "hold",
    "🔴 Réduire": "reduce",
}


def _get_recommendation(score: float) -> tuple[str, str, str]:
    """Return (label, budget_delta, color) for a given score."""
    for threshold, label, delta, _, color in _SCORE_THRESHOLDS:
        if score >= threshold:
            return t(f"meta_cpr_optimizer.rec.{_REC_SLUGS[label]}", label), delta, color
    return t("meta_cpr_optimizer.rec.reduce", "🔴 Réduire"), "-30%", "#dc3545"


_QUERY_OPTIMIZER = f"""
SELECT
    ctm.campaign_name,
    ctm.track_name,
    COALESCE(mip.total_spend, 0)    AS total_spend,
    COALESCE(mip.total_results, 0)  AS total_results,
    mip.cpr,
    -- NO COALESCE to 0: an absent prediction is « no estimate », like a floor
    -- value, not a 0 %% that zeroes the score (2026-09-26).
    ml.dw_probability    AS dw_prob,
    ml.rr_probability    AS rr_prob,
    ml.radio_probability AS radio_prob
FROM campaign_track_mapping ctm
LEFT JOIN (
    SELECT
        campaign_name,
        SUM(spend)                                                         AS total_spend,
        SUM(results)                                                       AS total_results,
        CASE WHEN SUM(results) > 0
             THEN ROUND(SUM(spend)::numeric / SUM(results), 4)
             ELSE NULL END                                                 AS cpr
    FROM v_meta_campaign_daily
    -- Le marqueur de compte est doublé : cette constante est une f-string
    -- (elle interpole canonical_song_sql), donc un marqueur simple serait
    -- consommé à la définition et le .format() de l'appelant ne trouverait
    -- plus rien à remplacer.
    WHERE artist_id = %s{{acct}}
    GROUP BY campaign_name
) mip ON LOWER(mip.campaign_name) = LOWER(ctm.campaign_name)
LEFT JOIN (
    SELECT DISTINCT ON (song)
        song,
        dw_probability,
        rr_probability,
        radio_probability
    FROM ml_song_predictions
    WHERE artist_id = %s
    ORDER BY song, prediction_date DESC
) ml ON LOWER(ml.song) = LOWER({canonical_song_sql('ctm.track_name')})
WHERE ctm.artist_id = %s
ORDER BY mip.cpr ASC NULLS LAST
"""

_QUERY_ALL_CAMPAIGN_CPR = """
SELECT
    campaign_name,
    CASE WHEN SUM(results) > 0
         THEN SUM(spend)::numeric / SUM(results)
         ELSE NULL END AS cpr
FROM v_meta_campaign_daily
WHERE artist_id = %s{acct} AND results > 0
GROUP BY campaign_name
"""


# LE PRIOR DE CONFIANCE, en RÉSULTATS. Une campagne à 14 résultats ne peut pas
# soutenir une affirmation sur son CPR ; une à 6 932 le peut. `K` est le nombre de
# résultats à partir duquel on croit une campagne à moitié — il vaut la MÉDIANE
# observée, pas une constante ronde, pour que le seuil suive le compte réel.
_K_DEFAUT = K_DEFAUT


def _facteur_confiance(resultats: float, k: float) -> float:
    """Délégué à `utils.meta_confidence` — deux vues posent la même question.

    Le classement des créatives en a eu besoin le 2026-09-21, pour le même motif
    exact (« si j'ai dépensé que 10 € »). Recopier la formule aurait créé deux
    barèmes qui divergent au premier réglage.
    """
    return confidence_factor(resultats, k)


def _ml_factor(dw, rr, radio) -> float | None:
    """The ML part of a campaign's score: max of the OFF-floor probabilities, or None.

    Before 2026-09-26 it was `max(dw, rr, radio)` on raw values. With the three on
    the calibration floor (33 of 33 production values that day) the max is always
    Radio's intercept (~10,7 %) — an artefact of calibration, not a signal about the
    track — and it multiplied a real ad-spend recommendation. Pure.
    """
    vals = {"DW": dw, "RR": rr, "RADIO": radio}
    kept = [p for a in ALGO_ORDER
            if (p := proba_affichable(a.lower(), vals[a])) is not None]
    return max(kept) if kept else None


def _ml_label(dw, rr, radio) -> str:
    """The displayed « ML max » — through the shared door; floor → texte_plancher."""
    m = _ml_factor(dw, rr, radio)
    return f"{m:.0%}" if m is not None else texte_plancher()


def _compute_scores(df: pd.DataFrame, cpr_median: float,
                    affinite_age: dict | None = None,
                    k_confiance: float = _K_DEFAUT) -> pd.DataFrame:
    """Score = probabilité ML × efficacité × CONFIANCE × affinité d'âge.

    ⚠️ BARÈME REFAIT le 2026-09-21, sur deux demandes et une mesure qui en
    contredit une.

    **1. « si j'ai dépensé que 10 € en CPR… »** — le score valait
    `ml_prob × (cpr_médian / cpr)`. Rien n'y bornait la CONFIANCE : une campagne
    à 14 résultats et au CPR chanceux sortait devant une campagne à 6 932. Mesuré
    sur ce compte : les campagnes vont de **14 à 6 932 résultats**, médiane
    **1 244** — deux ordres de grandeur, et le barème les traitait à égalité.
    Le facteur `n / (n + k)` corrige ça sans exclure personne.

    **2. « il faut prendre en compte l'âge »** — fait, mais MESURÉ, pas supposé.
    Et la mesure dit l'inverse de la prémisse :

        18-24   564,80 €   4 081 résultats   CPR **0,1384**
        25-34 1 397,61 €   9 503 résultats   CPR **0,1471**
        35-44   166,93 €   1 891 résultats   CPR **0,0883**  ← le meilleur
        45-54   122,75 €   1 342 résultats   CPR **0,0915**

    Les **35-44 convertissent 57 % moins cher que les 18-24**, et **78 % du budget
    part sur les deux tranches les plus chères**. Coder « les jeunes cliquent
    plus » aurait inscrit dans le barème une croyance que les données de ce compte
    réfutent. L'affinité est donc calculée à partir du CPR OBSERVÉ par tranche :
    une campagne est récompensée d'avoir touché les tranches qui convertissent
    bien CHEZ CET ARTISTE, quelles qu'elles soient.

    ⚠️ **LE FACTEUR ML EST NEUTRE QUAND IL N'EST PAS UNE MESURE** — 2026-09-26.
    `_ml_factor` ne garde que les probabilités hors plancher. Si UNE campagne
    scorée n'en a aucune, le facteur ML vaut 1,0 pour TOUTES (`ml_in_score` =
    False) : mélanger des campagnes pondérées par une vraie probabilité et
    d'autres par un neutre classerait les secondes devant les premières.
    """
    df = df.copy()
    ml = [_ml_factor(a, b, c) for a, b, c in zip(
        df.get('dw_prob', []), df.get('rr_prob', []), df.get('radio_prob', []))]
    # dtype=object: a float column would turn None into NaN, and `is not None`
    # would then count « no estimate » as a measure (seen red 2026-09-26).
    df['ml_factor'] = pd.Series(ml if len(ml) == len(df) else [None] * len(df),
                                index=df.index, dtype=object)
    scored = df['cpr'].notna() & (df['cpr'] > 0)
    ml_in_score = bool(scored.any()) and all(
        m is not None and pd.notna(m) for m, ok in zip(df['ml_factor'], scored) if ok)
    df.attrs['ml_in_score'] = ml_in_score

    def _score_row(row) -> float:
        if pd.isna(row['cpr']) or row['cpr'] <= 0 or cpr_median <= 0:
            return 0.0
        ml_prob = row['ml_factor'] if ml_in_score else 1.0
        efficacite = cpr_median / float(row['cpr'])
        confiance = _facteur_confiance(row.get('total_results'), k_confiance)
        age = 1.0
        if affinite_age:
            age = float(affinite_age.get(row['campaign_name'], 1.0))
        return float(ml_prob) * efficacite * confiance * age

    df['score_raw'] = (df.apply(_score_row, axis=1) if len(df)
                       else pd.Series(dtype=float))
    df['confiance'] = (df['total_results'].apply(
        lambda n: _facteur_confiance(n, k_confiance))
        if 'total_results' in df.columns else 0.0)
    # Normalize to 0-10 (cap at 10)
    max_raw = df['score_raw'].max()
    if max_raw > 0:
        df['score_10'] = (df['score_raw'] / max_raw * 10).clip(0, 10).round(1)
    else:
        df['score_10'] = 0.0

    recs = df['score_10'].apply(_get_recommendation)
    df['rec_label']  = recs.apply(lambda x: x[0])
    df['budget_delta'] = recs.apply(lambda x: x[1])
    df['rec_color']  = recs.apply(lambda x: x[2])
    return df


def _render_summary_kpi(df: pd.DataFrame) -> None:
    mapped = df[df['cpr'].notna()]
    unmapped = df[df['cpr'].isna()]
    n_increase = (df['budget_delta'].isin(['+30%', '+10%'])).sum()
    n_reduce = (df['budget_delta'] == '-30%').sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("meta_cpr_optimizer.kpi_analyzed", "Campagnes analysées"), len(mapped))
    col2.metric(t("meta_cpr_optimizer.kpi_no_cpr", "Sans données CPR"), len(unmapped),
                help=t("meta_cpr_optimizer.kpi_no_cpr_help", "Campagnes mappées mais sans spend Meta"))
    col3.metric(t("meta_cpr_optimizer.kpi_increase", "Recommandation hausse"), int(n_increase))
    col4.metric(t("meta_cpr_optimizer.kpi_reduce", "Recommandation réduction"), int(n_reduce))


def _render_detail_cards(df: pd.DataFrame) -> None:
    """Expandable cards per campaign with full explanation."""
    for _, row in df.iterrows():
        ml_txt = _ml_label(row['dw_prob'], row['rr_prob'], row['radio_prob'])
        cpr_str = (f"{row['cpr']:.2f}€" if pd.notna(row['cpr'])
                   else t("meta_cpr_optimizer.unknown", "inconnu"))
        score = row['score_10']
        label, delta, color = _get_recommendation(score)

        with st.expander(f"{label} — **{row['campaign_name']}** → {row['track_name']}"):
            col_a, col_b, col_c = st.columns(3)
            col_a.metric(t("meta_cpr_optimizer.composite_score", "Score composite"), f"{score:.1f}/10")
            col_b.metric(t("meta_cpr_optimizer.col_current_cpr", "CPR actuel"), cpr_str)
            col_c.metric(t("meta_cpr_optimizer.col_budget", "Budget suggéré"), delta)

            st.markdown(t(
                "meta_cpr_optimizer.ml_prob",
                "**Probabilité ML max** : {ml_max} "
                "(DW: {dw} | RR: {rr} | Radio: {radio})"
            ).format(ml_max=ml_txt, dw=format_proba("dw", row['dw_prob']),
                     rr=format_proba("rr", row['rr_prob']),
                     radio=format_proba("radio", row['radio_prob'])))

            if pd.isna(row['cpr']):
                st.warning(t(
                    "meta_cpr_optimizer.warn_no_cpr",
                    "Pas de données CPR pour cette campagne — "
                    "vérifiez que la campagne Meta Ads a des résultats et que le CSV est importé."
                ))
            elif score >= 7:
                st.success(t(
                    "meta_cpr_optimizer.msg_performing",
                    "✅ **Campagne performante** : CPR bas ({cpr}) + fort potentiel ML ({ml}). "
                    "Augmenter le budget de 30% pour maximiser la fenêtre algo."
                ).format(cpr=cpr_str, ml=ml_txt))
            elif score >= 5:
                st.info(t(
                    "meta_cpr_optimizer.msg_good",
                    "🟡 **Bon rapport** : augmenter légèrement (+10%) et surveiller l'évolution du CPR sur 7 jours."
                ))
            elif score >= 3:
                st.info(t("meta_cpr_optimizer.msg_average",
                          "⚪ **Performance moyenne** : maintenir le budget actuel et attendre plus de données."))
            else:
                st.error(t(
                    "meta_cpr_optimizer.msg_under",
                    "🔴 **Sous-performante** : CPR élevé ({cpr}) et/ou faible potentiel ML ({ml}). "
                    "Réduire le budget de 30% ou revoir la créative et le ciblage."
                ).format(cpr=cpr_str, ml=ml_txt))


def render(db, artist_id) -> None:
    """The CPR Optimizer as a section of the algo page (R477, owner W14 II).

    « Déplacer la vue CPR Optimizer dans cette vue » : the page left the menu and its
    key is an alias that opens the algo page's budget section. What it showed is kept
    minus its table tab (« pas de tableaux ») and the explanatory captions under it —
    the cards ARE the recommendations, and the CPR disclosure is the section's own.
    Reads on the caller's connection (rule #9).
    """
    # Un nom de campagne peut exister dans DEUX comptes publicitaires : sans ce
    # filtre, la sous-requête `mip` additionnerait leurs dépenses (R53 / ADR-013).
    df = recommendations(db, artist_id, account_scope(db, artist_id, key="meta_cpr_acct"))
    st.subheader(t("meta_cpr_optimizer.section", "📊 Que faire du budget de chaque campagne"))
    if df.empty:
        st.info(t(
            "meta_cpr_optimizer.no_mapping",
            "Aucun mapping campagne → titre. "
            "Crée-les dans **🔗 Mapping cross-plateforme** : la collecte tourne chaque "
            "matin et redémarre dès que tu enregistres un identifiant."
        ))
        return
    # R146 — this section RECOMMENDS raising or cutting a budget on a cost per CLICK:
    # the limit is stated where one acts on the number.
    st.caption(disclosure_caption())
    _render_summary_kpi(df)
    render_cards(df)


def recommendations(db, artist_id, account: str | None = None) -> pd.DataFrame:
    """THE campaign recommendations, without a widget — the CPR page and the algo page.

    R381 (V71): « Recommandations détaillées » are shown on the algo page for the
    latest release. Before, the pipeline lived inside `show()` next to the `st.*`
    calls, so a second surface could only recompute it — and two computations of
    one recommendation diverge. `df.attrs` carries `cpr_median` and `k_conf`, which
    the CPR page displays. Three reads, on the caller's connection.
    """
    acct, acct_p = account_clause(account)
    df = db.fetch_df(_QUERY_OPTIMIZER.format(acct=acct),
                     (artist_id, *acct_p, artist_id, artist_id))
    cpr_all = db.fetch_df(_QUERY_ALL_CAMPAIGN_CPR.format(acct=acct), (artist_id, *acct_p))
    affinite, _ages = _affinite_age(db, artist_id, acct, acct_p)
    if df is None or df.empty:
        out = pd.DataFrame() if df is None else df
        out.attrs.update(cpr_median=None, k_conf=_K_DEFAUT)
        return out
    cpr_median = float(cpr_all['cpr'].median()) if not cpr_all.empty else 1.0
    k_conf = (float(cpr_all['cpr'].notna().sum()) and
              float(df['total_results'].median()) if 'total_results' in df.columns
              else _K_DEFAUT) or _K_DEFAUT
    out = _compute_scores(df, cpr_median, affinite_age=affinite, k_confiance=k_conf)
    out.attrs.update(cpr_median=cpr_median, k_conf=k_conf)
    return out


def for_track(df: pd.DataFrame, song: str | None) -> pd.DataFrame:
    """The recommendations of ONE title (canonical match, as the SQL join does). Pure."""
    from src.utils.track_matching import canonical_song
    if df is None or df.empty or not song:
        return df.iloc[0:0] if df is not None else pd.DataFrame()
    key = canonical_song(song).lower()
    keep = df['track_name'].map(lambda n: canonical_song(str(n)).lower() == key)
    return df[keep]


def render_cards(df: pd.DataFrame) -> None:
    """The detailed cards, increase first — the CPR page and the algo page."""
    order = {'+30%': 0, '+10%': 1, '=': 2, '-30%': 3}
    _render_detail_cards(df.assign(_order=df['budget_delta'].map(order))
                         .sort_values('_order').drop(columns='_order'))

def _affinite_age(db, artist_id, acct: str, acct_p: tuple):
    """(affinité par campagne, table des tranches) — MESURÉE, jamais supposée.

    L'affinité d'une campagne est la moyenne, pondérée par sa dépense, de
    l'efficacité des tranches d'âge qu'elle a touchées. L'efficacité d'une tranche
    est `CPR médian des tranches ÷ CPR de la tranche` : au-dessus de 1 elle
    convertit mieux que la moyenne, en dessous moins bien.

    Une campagne sans ventilation d'âge rend 1,0 — neutre. Elle n'est ni
    récompensée ni punie pour une donnée qu'on n'a pas.
    """
    ages = db.fetch_df(f"""
        SELECT campaign_name, age_range, SUM(spend) AS spend, SUM(results) AS results
          FROM meta_insights_performance_age
         WHERE artist_id = %s{acct}
         GROUP BY campaign_name, age_range
    """, (artist_id, *acct_p))
    if ages is None or ages.empty:
        return {}, pd.DataFrame()
    # R409 — the brackets are computed in ONE place, read by this score and by the
    # free age finding (meta_breakdowns): the bracket called cheapest there is the
    # one rewarded here. A bracket without spend AND results has no CPR.
    from src.dashboard.utils.age_brackets import brackets
    ages = ages.copy()
    ages['spend'] = pd.to_numeric(ages['spend'], errors='coerce').fillna(0.0)
    par_tranche = brackets(ages)
    if 'efficacite' not in par_tranche:
        return {}, par_tranche

    eff = dict(zip(par_tranche['age_range'], par_tranche['efficacite']))
    affinite = {}
    for camp, grp in ages.groupby('campaign_name'):
        poids = grp['spend'].sum()
        if poids <= 0:
            continue
        valeur = sum(row['spend'] * eff.get(row['age_range'], 1.0)
                     for _, row in grp.iterrows()
                     if pd.notna(eff.get(row['age_range'], 1.0)))
        affinite[camp] = valeur / poids
    return affinite, par_tranche
