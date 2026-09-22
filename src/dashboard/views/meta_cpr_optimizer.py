"""Vue CPR Optimizer — Score ML × CPR + recommandations de budget.

Type: Feature
Uses: get_db_connection, get_artist_id, require_plan
Depends on: meta_insights_performance, campaign_track_mapping, ml_song_predictions
Score: max(dw_prob, rr_prob, radio_prob) × (cpr_median / cpr_campaign)
       → normalisé 0-10. Seuils: ≥7 → +30%, 5-7 → +10%, 3-5 → neutre, <3 → -30%.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils import view_session
from src.dashboard.utils.meta_accounts import account_clause, account_scope
from src.dashboard.utils.i18n import t
from src.dashboard.utils.proxy_disclosure import disclosure_caption
from src.dashboard.utils.meta_confidence import K_DEFAUT, confidence_factor
from src.dashboard.auth import require_plan
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
    COALESCE(ml.dw_probability,    0) AS dw_prob,
    COALESCE(ml.rr_probability,    0) AS rr_prob,
    COALESCE(ml.radio_probability, 0) AS radio_prob
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
    """
    def _score_row(row) -> float:
        if pd.isna(row['cpr']) or row['cpr'] <= 0 or cpr_median <= 0:
            return 0.0
        ml_prob = max(row['dw_prob'], row['rr_prob'], row['radio_prob'])
        efficacite = cpr_median / float(row['cpr'])
        confiance = _facteur_confiance(row.get('total_results'), k_confiance)
        age = 1.0
        if affinite_age:
            age = float(affinite_age.get(row['campaign_name'], 1.0))
        return float(ml_prob) * efficacite * confiance * age

    df = df.copy()
    df['score_raw'] = df.apply(_score_row, axis=1)
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


def _render_table(df: pd.DataFrame) -> None:
    display = df.copy()

    display['Score'] = display['score_10'].apply(lambda x: f"{x:.1f} / 10")
    display['CPR actuel'] = display['cpr'].apply(
        lambda x: f"{x:.2f}€" if pd.notna(x) else "—"
    )
    display['Dépense'] = display['total_spend'].apply(lambda x: f"{x:.2f}€")
    display['Résultats'] = display['total_results'].astype(int)
    display['ML max'] = display[['dw_prob', 'rr_prob', 'radio_prob']].max(axis=1).apply(
        lambda x: f"{x:.0%}"
    )

    st.dataframe(
        display[[
            'rec_label', 'campaign_name', 'track_name',
            'Score', 'CPR actuel', 'budget_delta',
            'Dépense', 'Résultats', 'ML max',
        ]].rename(columns={
            'rec_label':     t("meta_cpr_optimizer.col_action", "Action"),
            'campaign_name': t("meta_cpr_optimizer.col_campaign", "Campagne"),
            'track_name':    t("meta_cpr_optimizer.col_track", "Track liée"),
            'budget_delta':  t("meta_cpr_optimizer.col_budget", "Budget suggéré"),
            'Score':         t("meta_cpr_optimizer.col_score", "Score"),
            'CPR actuel':    t("meta_cpr_optimizer.col_current_cpr", "CPR actuel"),
            'Dépense':       t("meta_cpr_optimizer.col_spend", "Dépense"),
            'Résultats':     t("meta_cpr_optimizer.col_results", "Résultats"),
            'ML max':        t("meta_cpr_optimizer.col_ml_max", "ML max"),
        }),
        width="stretch",
        hide_index=True,
    )


def _render_detail_cards(df: pd.DataFrame) -> None:
    """Expandable cards per campaign with full explanation."""
    for _, row in df.iterrows():
        ml_max = max(row['dw_prob'], row['rr_prob'], row['radio_prob'])
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
            ).format(ml_max=f"{ml_max:.0%}", dw=f"{row['dw_prob']:.0%}",
                     rr=f"{row['rr_prob']:.0%}", radio=f"{row['radio_prob']:.0%}"))

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
                ).format(cpr=cpr_str, ml=f"{ml_max:.0%}"))
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
                ).format(cpr=cpr_str, ml=f"{ml_max:.0%}"))


def show() -> None:
    if not require_plan('premium'):
        return

    st.title("📊 CPR Optimizer")
    st.caption(t(
        "meta_cpr_optimizer.subtitle",
        "Score composite ML × CPR pour chaque campagne. "
        "Basé sur `campaign_track_mapping` + `ml_song_predictions` + `meta_insights_performance`."
    ))
    # R146 — CETTE PAGE RECOMMANDE D'AUGMENTER OU DE RÉDUIRE UN BUDGET.
    # Toutes ses recommandations sont assises sur le CPR, c'est-à-dire sur un coût
    # par CLIC SORTANT. C'est la surface où la limite compte le plus : ailleurs on
    # lit un chiffre, ici on agit dessus. Elle est donc en tête de page, visible
    # sans survol, et pas dans une info-bulle.
    st.info(disclosure_caption())

    with view_session() as (db, artist_id):
        # Un nom de campagne peut exister dans DEUX comptes publicitaires : sans ce
        # filtre, la sous-requête `mip` additionnerait leurs dépenses et le CPR
        # affiché ne serait celui d'aucun des deux (R53 / ADR-013).
        _acct, _acct_params = account_clause(
            account_scope(db, artist_id, key="meta_cpr_acct"))
        df = db.fetch_df(
            _QUERY_OPTIMIZER.format(acct=_acct),
            (artist_id, *_acct_params, artist_id, artist_id),
        )
        cpr_all = db.fetch_df(
            _QUERY_ALL_CAMPAIGN_CPR.format(acct=_acct), (artist_id, *_acct_params))
        # ⚠️ LA TROISIÈME LECTURE EST **DANS** LE `with`, et c'est une correction.
        #
        # Elle vivait dix lignes plus bas, hors du bloc : `view_session()` avait
        # déjà fermé la connexion, et `PostgresHandler._ensure_connection()` la
        # rouvrait en silence. La page marchait, ouvrait DEUX connexions par
        # rendu contre la règle #9, et rien ne le disait —
        # `test_a_render_opens_one_connection` l'a nommé. C'est mot pour mot le
        # défaut que `hypeddit.py` documente depuis le 2026-08-21.
        affinite, ages = _affinite_age(db, artist_id, _acct, _acct_params)

    if df.empty:
        st.info(t(
            "meta_cpr_optimizer.no_mapping",
            "Aucun mapping campagne → titre. "
            "Crée-les dans **🔗 Mapping cross-plateforme**, puis relance "
            "La collecte tourne chaque matin, et redémarre dès que tu enregistres un identifiant."
        ))
        return

    # CPR médian global (toutes campagnes avec données)
    cpr_median = float(cpr_all['cpr'].median()) if not cpr_all.empty else 1.0

    # L'affinité d'âge est LUE plus haut, dans le bloc de connexion ; elle est
    # APPLIQUÉE ici. Le détail du raisonnement, et les chiffres qui réfutent
    # « les jeunes cliquent plus », sont dans le docstring de `_compute_scores`.
    k_conf = (float(cpr_all['cpr'].notna().sum()) and
              float(df['total_results'].median()) if 'total_results' in df.columns
              else _K_DEFAUT) or _K_DEFAUT
    df = _compute_scores(df, cpr_median, affinite_age=affinite, k_confiance=k_conf)
    _render_age_panel(ages, k_conf)

    st.markdown(t("meta_cpr_optimizer.account_median",
                  "CPR médian du compte : **{v}€**").format(v=f"{cpr_median:.2f}"))
    st.markdown("---")

    _render_summary_kpi(df)
    st.markdown("---")

    tab_cards, tab_table = st.tabs([
        t("meta_cpr_optimizer.tab_cards", "🃏 Recommandations détaillées"),
        t("meta_cpr_optimizer.tab_table", "📋 Tableau"),
    ])

    with tab_cards:
        # Sort: increase first, then neutral, then reduce
        order = {'+30%': 0, '+10%': 1, '=': 2, '-30%': 3}
        df_sorted = df.assign(
            _order=df['budget_delta'].map(order)
        ).sort_values('_order').drop(columns='_order')
        _render_detail_cards(df_sorted)

    with tab_table:
        _render_table(df.sort_values('score_10', ascending=False))

    st.markdown("---")
    st.caption(t(
        "meta_cpr_optimizer.disclaimer",
        "⚠️ Ces recommandations sont indicatives. "
        "Le score est calculé sur les données disponibles — "
        "plus il y a de jours de collecte, plus le score est fiable."
    ))


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

    ages = ages.copy()
    ages['spend'] = pd.to_numeric(ages['spend'], errors='coerce').fillna(0.0)
    ages['results'] = pd.to_numeric(ages['results'], errors='coerce').fillna(0)

    par_tranche = ages.groupby('age_range', as_index=False)[['spend', 'results']].sum()
    # ⚠️ IL FAUT UNE DÉPENSE **ET** DES RÉSULTATS — vu au premier rendu.
    #
    # La tranche « Unknown » porte 0,00 € de dépense et 7 résultats : le rapport
    # vaut 0, et le panneau l'a proclamée « ta tranche la plus efficace : 0,0000 €
    # par résultat ». Un coût nul n'est pas un coût bas, c'est une absence de
    # coût — le même zéro inventé que cette session poursuit partout ailleurs.
    #
    # Une tranche sans dépense mesurée n'a pas de CPR : elle sort du calcul plutôt
    # que d'être proclamée gratuite.
    par_tranche['cpr'] = (par_tranche['spend'].where(par_tranche['spend'] > 0)
                          / par_tranche['results'].where(par_tranche['results'] > 0))
    # ⚠️ Une tranche sans CPR calculable sort du calcul : elle ne vaut ni 0 (« elle
    # convertit gratuitement ») ni 1 (« elle est moyenne »), elle est inconnue.
    mediane = par_tranche['cpr'].median()
    if pd.isna(mediane) or mediane <= 0:
        return {}, par_tranche
    par_tranche['efficacite'] = mediane / par_tranche['cpr']

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


def _render_age_panel(par_tranche, k_conf: float) -> None:
    """Le panneau d'âge : ce que la donnée dit, y compris quand elle surprend."""
    if par_tranche is None or par_tranche.empty or 'efficacite' not in par_tranche:
        return
    d = par_tranche.dropna(subset=['cpr'])
    d = d[d['cpr'] > 0].sort_values('cpr')
    if len(d) < 2:
        st.caption(t("meta_cpr_optimizer.age_thin",
                     "Pas assez de tranches d'âge mesurées (dépense ET résultats) "
                     "pour comparer."))
        return
    meilleure, pire = d.iloc[0], d.iloc[-1]
    part_chere = (d[d['efficacite'] < 1]['spend'].sum()
                  / d['spend'].sum() * 100) if d['spend'].sum() else 0

    # « convertit vraiment » affirmait une conversion réelle sur un compte de clics
    # sortants — c'était le site le plus trompeur du balayage R146, parce que
    # l'adverbe même prétendait trancher entre le proxy et la chose.
    st.subheader(t("meta_cpr_optimizer.age_header",
                   "🎂 Quelle tranche d'âge clique le moins cher"))
    fig = go.Figure(go.Bar(
        x=d['age_range'], y=d['cpr'], marker_color='#2a78d6', opacity=0.85,
        text=[f"{v:.3f} €" for v in d['cpr']], textposition='outside',
        cliponaxis=False,
        customdata=d['spend'],
        hovertemplate="%{x}<br>CPR %{y:.4f} €<br>%{customdata:,.0f} € dépensés"
                      "<extra></extra>"))
    fig.update_layout(height=360, margin=dict(t=40),
                      yaxis_title=t("meta_cpr_optimizer.age_axis", "CPR (€)"))
    st.plotly_chart(fig, width="stretch")
    st.info(t(
        "meta_cpr_optimizer.age_finding",
        "**{best}** est ta tranche la plus efficace : **{cb:.4f} €** par résultat, "
        "contre **{cw:.4f} €** pour **{worst}** — soit **{ratio:.0f} %** moins "
        "cher. Et **{part:.0f} %** de ta dépense part sur des tranches qui "
        "convertissent MOINS bien que la médiane.\n\n"
        "⚠️ Ce panneau est mesuré, pas supposé. L'intuition courante — « les jeunes "
        "cliquent plus » — n'est pas ce que dit ce compte : c'est le score qui "
        "s'aligne sur la donnée, jamais l'inverse."
    ).format(best=meilleure['age_range'], cb=meilleure['cpr'],
             worst=pire['age_range'], cw=pire['cpr'],
             ratio=(1 - meilleure['cpr'] / pire['cpr']) * 100, part=part_chere))
    st.caption(t("meta_cpr_optimizer.confidence_note",
                 "Le score pondère aussi par la CONFIANCE : une campagne est crue à "
                 "moitié à **{k:.0f} résultats**, et presque pas en dessous de "
                 "quelques dizaines. Un CPR flatteur sur dix euros de dépense ne "
                 "remonte plus le classement.").format(k=k_conf))
