"""Vue Créatives Meta Ads — Classement des créatives par CPR.

Type: Feature
Uses: get_db_connection, get_artist_id, require_plan
Depends on: meta_ads, meta_insights, meta_campaigns tables (API-based)
Persists in: read-only
"""
import re

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.dashboard.utils import view_session
from src.dashboard.utils.meta_accounts import account_clause, account_scope
from src.dashboard.utils.ui import smart_date_range
from src.dashboard.utils.i18n import t
from src.dashboard.utils.proxy_disclosure import disclosure_caption
from src.dashboard.utils.meta_confidence import K_DEFAUT, confidence_factor
from src.dashboard.utils.ui import secondary_analyses
from src.dashboard.auth import require_plan, is_admin

# All-creatives daily series (for the heatmap + cumulative-budget charts).
# La jointure `meta_insights` x `meta_ads` vivait ici et dans deux autres requetes
# de ce fichier. `v_meta_creative_daily` (migration 106) la porte — y compris son
# `artist_id`, qu'il suffit d'oublier une fois pour melanger deux locataires.
_QUERY_TS_ALL = """
SELECT creative_name, day AS date, SUM(spend) AS spend
FROM v_meta_creative_daily
WHERE artist_id = %s{acct}
GROUP BY creative_name, day
ORDER BY day
"""


# Each metric gets its own Y-axis (scales differ wildly: € vs thousands of impressions).
# (label, column, weekly-resample aggregation, colour, visible-by-default, derived)
# Non-default metrics start as 'legendonly' → the chart opens readable; click the
# legend to toggle any metric (and its axis) on/off. `derived` metrics (CPR) are NOT
# fetched/resampled directly — they are recomputed from aggregated columns afterwards.
# Labels are FR sources, translated at render time via t(f"meta_creatives.metric.{col}").
_TIMELINE_METRICS = [
    ("Dépense (€)", "spend",       "sum",  "#ff6b35", True,  False),
    ("Impressions", "impressions", "sum",  "#1f77b4", True,  False),
    ("Clics",       "clicks",      "sum",  "#2ca02c", False, False),
    ("Reach",       "reach",       "sum",  "#9467bd", False, False),
    ("Résultats",   "conversions", "sum",  "#d62728", False, False),
    ("CTR (%)",     "ctr",         "mean", "#e6b800", False, False),
    ("CPR (€)",     "cpr",         None,   "#17becf", True,  True),
]


# total_results = the ad set goal's native result (mi.conversions, objective-aware).
# CPR is shown ONLY for conversion goals (cost-per-result on an engagement/traffic ad
# would imply a conversion that didn't happen — see collector _CONVERSION_GOALS).
_CONVERSION_GOALS_SQL = "('OFFSITE_CONVERSIONS','ONSITE_CONVERSIONS','LEAD_GENERATION','QUALITY_LEAD')"

# La quadruple jointure a disparu dans `v_meta_creative_daily` (migrations 106 et
# 108). Elle ne nommait le locataire que sur `ma`, et son filtre de compte
# publicitaire était AMBIGU — `meta_ads`, `meta_adsets` et `meta_campaigns`
# portent toutes `ad_account_id`, donc choisir un compte faisait tomber la page
# avec `column reference "ad_account_id" is ambiguous`. Une vue n'a qu'une colonne
# de ce nom : le défaut ne peut plus se poser.
#
# `SUM(ctr_sum) / SUM(ctr_n)` et pas `AVG(ctr)` : la vue porte la moyenne du JOUR,
# et un nom de créative couvre plusieurs `ad_id` en nombre variable. Re-moyenner
# des moyennes donnait 163,41 % là où les lignes brutes donnent 168,68 %.
_QUERY_CREATIVES = f"""
SELECT
    creative_name,
    campaign_name,
    SUM(spend)                                                          AS total_spend,
    SUM(conversions)                                                    AS total_results,
    CASE WHEN BOOL_OR(optimization_goal IN {_CONVERSION_GOALS_SQL})
              AND SUM(conversions) > 0
         THEN ROUND(SUM(spend)::numeric / SUM(conversions), 2)
         ELSE NULL END                                                  AS cpr,
    ROUND((SUM(ctr_sum) / NULLIF(SUM(ctr_n), 0)) * 100, 2)              AS avg_ctr,
    SUM(reach)                                                          AS total_reach,
    SUM(impressions)                                                    AS total_impressions,
    SUM(clicks)                                                         AS total_clicks,
    MAX(campaign_start)                                                 AS campaign_start,
    MAX(creative_created)                                               AS creative_created
FROM v_meta_creative_daily
WHERE artist_id = %s{{acct}} AND campaign_name IS NOT NULL
GROUP BY creative_name, campaign_name
HAVING SUM(spend) > 0
ORDER BY cpr ASC NULLS LAST, total_results DESC
"""

# Campaigns whose ads exist in meta_ads but have NO ad-level insights — absent
# from the CPR ranking above. `campaign_spend` is the CAMPAIGN-level spend from
# meta_insights_performance_day: when > 0 the campaign DID deliver and was
# collected at campaign level, but the per-creative (ad-level) breakdown is
# missing (incremental window passed, or ads archived/deleted on Meta) and needs
# a full-history backfill. When 0, the campaign simply never spent.
_QUERY_UNCOLLECTED = """
SELECT mc.campaign_name,
       COUNT(DISTINCT ma.ad_id)        AS ads,
       COALESCE(cl.campaign_spend, 0)  AS campaign_spend
FROM meta_campaigns mc
JOIN meta_ads ma ON ma.campaign_id = mc.campaign_id
LEFT JOIN meta_insights mi ON mi.ad_id = ma.ad_id
LEFT JOIN (
    -- La dépense par campagne vient de la couche or (`v_meta_daily`, migration 106)
    -- et non de la table brute : c'est la même question que celle de l'onglet
    -- Breakdowns, et deux façons d'y répondre finissent par donner deux nombres.
    SELECT campaign_name, SUM(spend) AS campaign_spend
    FROM v_meta_daily
    WHERE artist_id = %s{acct}
    GROUP BY campaign_name
) cl ON cl.campaign_name = mc.campaign_name
WHERE mc.artist_id = %s{acct_mc}
GROUP BY mc.campaign_name, cl.campaign_spend
HAVING COALESCE(SUM(mi.spend), 0) = 0
ORDER BY cl.campaign_spend DESC NULLS LAST, mc.campaign_name
"""


def _render_uncollected_notice(uncollected: pd.DataFrame) -> None:
    """Warn about campaigns with ads but no ad-level (per-creative) insights."""
    if uncollected is None or uncollected.empty:
        return
    df = uncollected.dropna(subset=['campaign_name'])
    if df.empty:
        return
    # Split: delivered (campaign-level spend exists, only ad-level missing) vs
    # never-spent (no delivery at all).
    spent = df['campaign_spend'].astype(float) > 0
    n_delivered = int(spent.sum())
    n_total = len(df)

    with st.expander(
        t("meta_creatives.uncollected_title",
          "⚠️ {n} campagne(s) absente(s) du classement par créative").format(n=n_total),
        expanded=False,
    ):
        if n_delivered:
            # Le bloc disait à l'ARTISTE d'ouvrir l'UI Airflow et de relancer un DAG
            # avec une config JSON, ou de lancer un script Python en local. Il ne peut
            # faire ni l'un ni l'autre. Le constat lui appartient — c'est son argent —
            # la manœuvre appartient à l'exploitant.
            st.markdown(t(
                "meta_creatives.uncollected_body",
                "**{n} campagne(s) ont bien dépensé**, mais le détail **par créative** "
                "n'a pas pu être récupéré. Cas courant : une campagne **en pause ou "
                "archivée** — Meta cesse d'en livrer le détail publicité par publicité.\n\n"
                "Le total de la campagne reste juste ; seule la répartition entre "
                "créatives manque. Signale-le à l'administrateur si ces campagnes "
                "comptent pour toi."
            ).format(n=n_delivered))
            if is_admin():
                st.caption(t(
                    "meta_creatives.uncollected_admin",
                    "🛠️ Rechargeable par une collecte full-history (qui re-récupère la "
                    "config des ads, pas seulement les insights) : Airflow → "
                    "`meta_ads_api_daily` → *Trigger DAG w/ config* "
                    "`{{\"full_history\": true}}`. "
                    "Réserves : les publicités doivent exister encore côté Meta, et Meta "
                    "ne conserve les insights que ~37 mois."))
                # La variante locale sortait du texte en Markdown inline, sans son
                # préambule d'activation : le venv est le seul interpréteur qui porte
                # les dépendances, et PowerShell refuse `Activate.ps1` par défaut.
                from src.dashboard.utils.shell_block import command_block
                _lang, _cmd = command_block(
                    "python airflow/debug_dag/debug_meta_ads_api.py "
                    "--full-history --write")
                st.code(_cmd, language=_lang)
        col_spend = t("meta_creatives.col_campaign_spend", "Dépense campagne (€)")
        st.dataframe(
            df.rename(columns={
                'campaign_name': t("meta_creatives.col_campaign", "Campagne"),
                'ads': t("meta_creatives.col_ads", "Publicités"),
                'campaign_spend': col_spend,
            }).style.format({col_spend: '{:,.2f} €'}, na_rep='—'),
            hide_index=True, width="stretch",
        )


def _badge(cpr: float, median: float) -> str:
    if pd.isna(cpr):
        return t("meta_creatives.badge_no_result", "⚫ Pas de résultat")
    # cpr arrives as Decimal (Postgres numeric); median as numpy float from
    # .median() — coerce both to float so the division can't raise on mixed types.
    cpr = float(cpr)
    median = float(median) if pd.notna(median) else 0.0
    ratio = cpr / median if median > 0 else 1.0
    if ratio <= 0.75:
        return t("meta_creatives.badge_top", "🟢 Top créative")
    if ratio <= 1.25:
        return t("meta_creatives.badge_avg", "🟡 Dans la moyenne")
    return t("meta_creatives.badge_under", "🔴 Sous-performante")


# ── Le HOOK, lu dans le nom que l'artiste donne à sa créative ────────────────
#
# Ce n'est pas une donnée de Meta : Meta ne connaît pas la notion de « hook ».
# C'est une CONVENTION DE NOMMAGE que l'artiste tient lui-même, et qu'on retrouve
# dans ses noms de créatives — « Hook 1 début : I missed… », « Drop Hook 2 You
# absolutely », « Sans hook drop ».
#
# ⚠️ Un prédicat qui lit une FORME D'ÉCRITURE ne mesure pas la PROPRIÉTÉ (règle
# transverse 20). Il est donc muté dans les deux sens par
# `tests/test_a_creative_name_yields_its_hook.py`, et surtout : **la part de
# dépense qu'il ne sait pas étiqueter est AFFICHÉE**, jamais tue. Mesuré sur
# l'artiste 1 le 2026-09-21 — 12 créatives sur 56 portent un hook nommé, pour
# **1 500 € des 3 088 € dépensés (49 %)**. Un classement des hooks qui passerait
# sous silence l'autre moitié de l'argent serait un classement faux.
_HOOK_NONE = "Sans hook"


def _hook_family(creative_name) -> str | None:
    """Le hook nommé dans le titre d'une créative, ou None s'il n'y en a pas.

    « Sans hook » EST une réponse — c'est une variante que l'artiste a tournée
    exprès — tandis qu'un nom qui ne parle pas de hook du tout ne dit rien et
    rend None.
    """
    if creative_name is None or pd.isna(creative_name):
        return None
    nom = str(creative_name)
    if re.search(r"sans\s+hook", nom, re.I):
        return _HOOK_NONE
    m = re.search(r"hook\s*(\d+)", nom, re.I)
    return f"Hook {m.group(1)}" if m else None


def _numerise(df: pd.DataFrame) -> pd.DataFrame:
    """Postgres NUMERIC → float. Sans ça Plotly mistype et Altair refuse `decimal`."""
    d = df.copy()
    for c in ('cpr', 'total_spend', 'total_results', 'avg_ctr',
              'total_reach', 'total_impressions', 'total_clicks'):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors='coerce')
    return d


def _par_hook(df: pd.DataFrame) -> pd.DataFrame:
    """Agrège par famille de hook. CPR recalculé sur les TOTAUX, jamais moyenné.

    Moyenner des CPR donne le poids d'une créative à 10 € et celui d'une créative
    à 800 €. Le coût par résultat d'une famille est `Σ dépense / Σ résultats`.
    """
    # ⚠️ La coercition est REFAITE ICI plutôt qu'appelée : la carte de la couche or
    # (`make gold-coverage`) remonte la provenance d'une figure de proche en
    # proche, et `_numerise()` imbriqué dans cette fonction ajoutait un saut de
    # trop — la figure des hooks sortait « indéterminée · profondeur » alors que
    # sa source est la même `v_meta_creative_daily` que le reste de la page.
    # Quatre lignes de redite contre un trou dans la carte : le trou coûte plus cher.
    d = df.copy()
    for _c in ('cpr', 'total_spend', 'total_results'):
        if _c in d.columns:
            d[_c] = pd.to_numeric(d[_c], errors='coerce')
    d['hook'] = d['creative_name'].apply(_hook_family)
    d = d.dropna(subset=['hook'])
    if d.empty:
        return d
    g = d.groupby('hook', as_index=False).agg(
        total_spend=('total_spend', 'sum'),
        total_results=('total_results', 'sum'),
        creatives=('creative_name', 'nunique'))
    g['cpr'] = g['total_spend'] / g['total_results'].where(g['total_results'] > 0)
    g['confiance'] = g['total_results'].apply(lambda n: confidence_factor(n, K_DEFAUT))
    return g.sort_values('cpr', na_position='last')


def _le_plus_sur(d: pd.DataFrame, col_cpr: str = 'cpr') -> pd.Series | None:
    """Le meilleur coût par résultat PONDÉRÉ par ce qui le soutient.

    ⚠️ C'est la demande explicite du propriétaire, formulée deux fois le
    2026-09-21 : « je veux le plus gros budget avec le meilleur ratio de CPR,
    mais pas quand j'ai dépensé que 10 € ». Ses propres données lui donnent
    raison — « Sans hook » sort en tête à 0,104 € sur **69 € dépensés**, devant
    « Hook 1 » à 0,113 € sur **846 €**. Couronner le premier conseillerait de
    tout miser sur un essai que rien ne soutient.

    Le classement se fait donc sur `(médian / cpr) × confiance`, où la confiance
    est `n / (n + 300)` — la même que celle du barème de l'optimiseur CPR, dans
    le même module, pour qu'un réglage ne corrige jamais une vue sur deux.
    """
    d = d[d[col_cpr].notna() & (d[col_cpr] > 0)]
    if d.empty:
        return None
    median = float(d[col_cpr].median())
    if median <= 0:
        return None
    score = (median / d[col_cpr]) * d['total_results'].apply(
        lambda n: confidence_factor(n, K_DEFAUT))
    if not (score > 0).any():
        return None
    return d.loc[score.idxmax()]


def _a_couper(d: pd.DataFrame) -> pd.Series | None:
    """Celle qui a coûté le plus d'ARGENT EN TROP — mesuré contre le coût d'ensemble.

    ⚠️ Deux jets corrigés le 2026-09-21, et les deux erreurs sont instructives.

    **1. Le pire RATIO n'est pas le plus gros gaspillage.** La règle était « la
    pire CPR parmi celles au-dessus de la dépense médiane ». Sur les données
    réelles de l'artiste 1 — 61 créatives, dépense médiane **25 €** — elle
    désignait une créative de 25 €. Techniquement juste, et sans intérêt : la
    couper ne libère rien. La question devant cet écran n'est pas « laquelle a le
    pire ratio » mais « où part l'argent que je perds ». Ça se mesure :

        surcoût = dépense × (1 − CPR_référence / CPR)

    soit les euros payés EN PLUS de ce qu'auraient coûté les mêmes résultats au
    coût de référence.

    **2. La référence n'est pas le CPR MÉDIAN.** Le médian se prend sur les
    créatives, une voix chacune : une nuée de petits essais ratés le tire vers le
    haut et fait passer les grosses dépenses pour bonnes. Mesuré le même jour :
    médian **0,310 €** contre coût d'ensemble **0,130 €** — un facteur 2,4, qui
    plafonnait tous les surcoûts sous 20 € et enterrait le vrai.

    La référence est donc le coût d'ENSEMBLE, `Σdépense / Σrésultats` : ce que
    l'artiste paie réellement en moyenne, pondéré par l'argent. Avec elle, la
    carte désigne « Chorus - Kaiber Photo » — 220 € dépensés à 0,19 €, soit **70 €
    au-dessus** de son propre coût d'ensemble — et 462 € au total dépassent la
    référence sur 3 088 €. C'est un constat qu'on peut aller vérifier.
    """
    d = d[d['cpr'].notna() & (d['cpr'] > 0) & (d['total_spend'] > 0)]
    if len(d) < 2:
        return None
    resultats = float(d['total_results'].sum())
    if resultats <= 0:
        return None
    reference = float(d['total_spend'].sum()) / resultats
    if reference <= 0:
        return None
    surcout = d['total_spend'] * (1 - reference / d['cpr'])
    if not (surcout > 0).any():
        return None
    pire = d.loc[surcout.idxmax()].copy()
    pire['surcout'] = float(surcout.max())
    pire['reference'] = reference
    return pire


def _render_decision_banner(df: pd.DataFrame) -> None:
    """Ce qu'il faut faire, nommé — avant toute figure.

    Demandé par le propriétaire le 2026-09-21 : « indique-moi tout en haut les
    meilleures perf avec le nom des hooks et créatives les plus performantes : on
    doit pouvoir prendre des décisions ». La page ouvrait jusque-là sur quatre
    jauges dont deux portaient un nom TRONQUÉ à 30 caractères dans un `delta`,
    c'est-à-dire à l'endroit exact où Streamlit écrit une variation.
    """
    d = _numerise(df)
    meilleure = _le_plus_sur(d)
    couper = _a_couper(d)
    hooks = _par_hook(df)
    meilleur_hook = _le_plus_sur(hooks) if not hooks.empty else None

    depense = float(d['total_spend'].sum())
    st.markdown(t(
        "meta_creatives.banner_intro",
        "**{spend:,.0f} € dépensés sur {n} créative(s).** Voici les trois décisions "
        "que ces chiffres portent."
    ).format(spend=depense, n=len(d)).replace(",", " "))

    c1, c2, c3 = st.columns(3)
    if meilleure is not None:
        c1.metric(
            t("meta_creatives.best_creative", "🏆 Meilleure créative — {nom}").format(
                nom=meilleure['creative_name']),
            f"{float(meilleure['cpr']):.3f} €",
            delta=t("meta_creatives.backed_by",
                    "{spend:.0f} € · {res:,.0f} résultats").format(
                spend=float(meilleure['total_spend']),
                res=float(meilleure['total_results'])).replace(",", " "),
            delta_color="off")
    else:
        c1.info(t("meta_creatives.no_winner",
                  "Aucune créative n'a encore assez de résultats pour être couronnée."))

    if meilleur_hook is not None:
        part = (float(hooks['total_spend'].sum()) / depense * 100) if depense else 0.0
        c2.metric(
            t("meta_creatives.best_hook", "🎣 Meilleur hook — {nom}").format(
                nom=meilleur_hook['hook']),
            f"{float(meilleur_hook['cpr']):.3f} €",
            delta=t("meta_creatives.hook_backed_by",
                    "{spend:.0f} € · {n} créative(s) · {part:.0f} % du budget nommé"
                    ).format(spend=float(meilleur_hook['total_spend']),
                             n=int(meilleur_hook['creatives']), part=part),
            delta_color="off")
    else:
        c2.info(t("meta_creatives.no_hook_named",
                  "Aucun hook nommé dans tes titres de créatives. Nomme-les "
                  "« Hook 1 … », « Hook 2 … », « Sans hook … » et cette carte "
                  "te dira lequel convertit."))

    if couper is not None:
        c3.metric(
            t("meta_creatives.to_cut", "✂️ À couper — {nom}").format(
                nom=couper['creative_name']),
            f"{float(couper['cpr']):.3f} €",
            delta=t("meta_creatives.already_spent",
                    "{spend:.0f} € dépensés · ~{trop:.0f} € de trop vs ton coût "
                    "d'ensemble ({ref:.3f} €)").format(
                spend=float(couper['total_spend']),
                trop=float(couper['surcout']),
                ref=float(couper['reference'])),
            delta_color="off")
    else:
        c3.info(t("meta_creatives.nothing_to_cut",
                  "Aucune créative ne dérape sur un budget qui compte."))


# Le classement, en figures. (label, colonne, format, couleur, sens)
# `plus_bas_est_mieux` n'est vrai que pour un COÛT : c'est ce qui décide du sens
# du tri et de la couleur du meilleur.
_RANG_PANNEAUX = [
    ("CPR (€)",       'cpr',           "{:.3f}", "#ff6b35", True),
    ("Dépense (€)",   'total_spend',   "{:.0f}", "#7f7f7f", False),
    ("Résultats",     'total_results', "{:.0f}", "#2ca02c", False),
    ("CTR (%)",       'avg_ctr',       "{:.2f}", "#e6b800", False),
]
_RANG_MAX = 15


def _render_ranking(df: pd.DataFrame) -> None:
    """Le classement des créatives — QUATRE cadres, un par unité, noms en Y.

    ⚠️ Remplace un `st.dataframe` de huit colonnes, à la demande du propriétaire
    le 2026-09-21 : « montre-moi le classement par comparaison graphique plutôt
    que par tableau ». Le tableau n'a pas disparu — il est replié plus bas, parce
    qu'il reste le seul endroit où lire une valeur exacte.

    Pourquoi quatre cadres et non quatre séries sur un repère : un coût en euros,
    une dépense en euros, un nombre de résultats et un pourcentage n'ont ni la
    même unité ni le même ordre de grandeur. Superposés, le CTR passe sous le
    pixel. Le cliquet d'axes secondaires de ce dépôt (`_MAX_SECONDARY_AXES = 0`)
    dit la même chose d'une autre façon.
    """
    from plotly.subplots import make_subplots

    d = _numerise(df)
    d = d[d['total_spend'].notna() & (d['total_spend'] > 0)]
    if d.empty:
        st.info(t("meta_creatives.no_ranking", "Aucune créative avec de la dépense."))
        return
    tronque = len(d) > _RANG_MAX
    d = d.nlargest(_RANG_MAX, 'total_spend')
    # Meilleur CPR EN HAUT : Plotly empile les catégories du bas vers le haut, donc
    # on trie en décroissant pour que le meilleur finisse en tête de figure.
    d = d.sort_values('cpr', ascending=False, na_position='first')
    noms = d['creative_name'].tolist()

    fig = make_subplots(
        rows=1, cols=len(_RANG_PANNEAUX), shared_yaxes=True, horizontal_spacing=0.035,
        subplot_titles=[t(f"meta_creatives.rank.{col}", lab)
                        for lab, col, _, _, _ in _RANG_PANNEAUX])
    for i, (lab, col, fmt, couleur, _bas) in enumerate(_RANG_PANNEAUX, start=1):
        vals = d[col] if col in d.columns else pd.Series([float("nan")] * len(d))
        fig.add_trace(go.Bar(
            x=vals, y=noms, orientation='h', marker={'color': couleur},
            name=lab, showlegend=False,
            text=[fmt.format(v) if pd.notna(v) else "—" for v in vals],
            textposition='outside', cliponaxis=False,
            hovertemplate=f"%{{y}}<br>{lab} : %{{x}}<extra></extra>",
        ), row=1, col=i)
        fig.update_xaxes(showticklabels=False, row=1, col=i)
    fig.update_layout(height=max(320, 34 * len(noms) + 120),
                      margin={'l': 10, 'r': 40, 't': 60, 'b': 20},
                      bargap=0.25)
    fig.update_yaxes(automargin=True)
    st.plotly_chart(fig, width="stretch")
    st.caption(t(
        "meta_creatives.ranking_caption",
        "Meilleur coût par résultat en haut. Une barre absente = pas de résultat "
        "mesuré, donc pas de CPR — ce n'est pas un zéro.") + (
        " " + t("meta_creatives.ranking_truncated",
                "Seules les {n} créatives qui ont le plus dépensé sont tracées ; "
                "le tableau replié plus bas les porte toutes.").format(n=_RANG_MAX)
        if tronque else ""))


def _render_hooks(df: pd.DataFrame) -> None:
    """Quel hook convertit — et sur combien d'argent il a été jugé.

    DEUX cadres, et le second n'est pas décoratif : il porte la dépense qui
    soutient chaque coût. Sans lui, « Sans hook » gagnerait à l'œil (0,104 €)
    alors qu'il a été jugé sur 69 € contre 846 € pour « Hook 1 ».
    """
    from plotly.subplots import make_subplots

    depense_totale = float(_numerise(df)['total_spend'].sum())
    hooks = _par_hook(df)
    if hooks.empty or len(hooks) < 2:
        st.info(t(
            "meta_creatives.hooks_absent",
            "Tes titres de créatives ne nomment pas (encore) de hook. Nomme-les "
            "« Hook 1 — … », « Hook 2 — … », « Sans hook — … » : cette figure "
            "comparera alors le coût par résultat de chaque accroche."))
        return
    h = hooks.sort_values('cpr', ascending=False, na_position='first')
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.06,
                        subplot_titles=[t("meta_creatives.hook_cpr", "Coût par résultat (€)"),
                                        t("meta_creatives.hook_spend", "Dépense jugée (€)")])
    fig.add_trace(go.Bar(x=h['cpr'], y=h['hook'], orientation='h',
                         marker={'color': "#ff6b35"}, showlegend=False,
                         text=[f"{v:.3f}" if pd.notna(v) else "—" for v in h['cpr']],
                         textposition='outside', cliponaxis=False), row=1, col=1)
    fig.add_trace(go.Bar(x=h['total_spend'], y=h['hook'], orientation='h',
                         marker={'color': "#7f7f7f"}, showlegend=False,
                         text=[f"{v:.0f} €" for v in h['total_spend']],
                         textposition='outside', cliponaxis=False), row=1, col=2)
    fig.update_xaxes(showticklabels=False)
    fig.update_layout(height=max(260, 46 * len(h) + 120),
                      margin={'l': 10, 'r': 40, 't': 60, 'b': 20})
    fig.update_yaxes(automargin=True)
    st.plotly_chart(fig, width="stretch")

    part = (float(hooks['total_spend'].sum()) / depense_totale * 100) if depense_totale else 0.0
    st.caption(t(
        "meta_creatives.hooks_caption",
        "Le hook est lu dans le NOM que tu donnes à ta créative — Meta ne le "
        "connaît pas. **{part:.0f} % de ta dépense** porte un hook nommé ; le "
        "reste n'est pas classé ici. Un coût plus bas sur une dépense minuscule "
        "n'est pas un verdict : c'est pourquoi le second cadre existe."
    ).format(part=part))


def _render_table(df: pd.DataFrame) -> None:
    """Le tableau exact — REPLIÉ, sous la figure qui l'a remplacé.

    Il n'a pas été supprimé : c'est le seul endroit où lire une valeur au
    centième, et la figure est le seul endroit où comparer. Les deux servent.
    """
    with secondary_analyses(t("meta_creatives.table_expander",
                              "🔢 Le classement au chiffre près — tableau")):
        median_cpr = df[df['cpr'].notna()]['cpr'].median()

        display = df.copy()
        display['statut'] = display['cpr'].apply(lambda x: _badge(x, median_cpr))
        display['cpr'] = display['cpr'].apply(lambda x: f"{x:.2f}€" if pd.notna(x) else "—")
        display['total_spend'] = display['total_spend'].apply(lambda x: f"{x:.2f}€")
        display['avg_ctr'] = display['avg_ctr'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "—")
        display['total_reach'] = display['total_reach'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "—")

        st.dataframe(
            display[['statut', 'creative_name', 'campaign_name', 'cpr',
                     'total_spend', 'total_results', 'avg_ctr', 'total_reach']].rename(columns={
                'statut': t("meta_creatives.col_status", "Statut"),
                'creative_name': t("meta_creatives.col_creative", "Créative"),
                'campaign_name': t("meta_creatives.col_campaign", "Campagne"),
                'cpr': 'CPR',
                'total_spend': t("meta_creatives.col_spend", "Dépense"),
                'total_results': t("meta_creatives.col_results", "Résultats"),
                'avg_ctr': t("meta_creatives.col_avg_ctr", "CTR moyen"),
                'total_reach': 'Reach',
            }),
            width="stretch",
            hide_index=True,
        )
        if pd.notna(median_cpr):
            st.caption(t(
                "meta_creatives.badge_legend",
                "🟢 Top créative = CPR ≤ {low}€ | "
                "🟡 Moyenne = CPR ≤ {high}€ | "
                "🔴 Sous-performante = CPR > {high}€"
            ).format(low=f"{median_cpr * 0.75:.2f}", high=f"{median_cpr * 1.25:.2f}"))


@st.fragment
def _tab_creative_timeline(selected_campaign: str, acct: str = "", acct_params: tuple = ()) -> None:
    """La chronologie d'une créative — rejoué SEUL quand son sélecteur change.

    @st.fragment (R118, 2026-09-16). Bouger le sélecteur rejouait tout le script : les
    SIX onglets, dont `st.tabs` exécute tous les corps, plus la barre latérale.

    ⚠️ Il rouvre une session avec `view_session()`, et ce n'est pas un style : son
    sélecteur pilote une REQUÊTE, donc il doit relire la base — alors que la session de
    `show()` est refermée dès la fin du rendu complet. `view_session()` ferme par
    construction, ce qui est la seule forme acceptée par
    `tests/test_a_fragment_never_captures_a_connection.py` pour un fragment qui ouvre.
    """
    from src.dashboard.utils.fragment_db import fragment_db

    with fragment_db() as (db, artist_id):
        _render_creative_timeline(db, artist_id, selected_campaign, acct, acct_params)


def _render_creative_timeline(db, artist_id: int, selected_campaign: str,
                              acct: str = "", acct_params: tuple = ()) -> None:
    """Per-creative multi-metric timeline (one Y-axis per metric, legend toggle).

    The creative list honours the page's campaign filter. The period filter is
    data-bounded (smart_date_range). Each metric has its own Y-axis; non-default
    metrics start collapsed and are toggled via the legend.
    """
    st.markdown("---")
    st.subheader(t("meta_creatives.timeline_title", "📈 Évolution d'une créative dans le temps"))

    # Honour the page-level campaign filter for the creative dropdown.
    campaign_clause = "" if selected_campaign == "Toutes" else " AND campaign_name = %s"
    name_params = ((artist_id, *acct_params) if selected_campaign == "Toutes"
                   else (artist_id, *acct_params, selected_campaign))
    names = db.fetch_df(
        # Même vue or, pour la même raison : la triple jointure portait un
        # `ad_account_id` ambigu entre `meta_ads` et `meta_campaigns`.
        f"""SELECT creative_name AS ad_name, MAX(creative_created) AS last_created
            FROM v_meta_creative_daily
            WHERE artist_id = %s{acct} AND creative_name IS NOT NULL
              AND campaign_name IS NOT NULL{campaign_clause}
            GROUP BY creative_name
            ORDER BY last_created DESC NULLS LAST, creative_name""",
        name_params,
    )
    if names.empty:
        st.info(t("meta_creatives.no_adlevel_insights",
                  "Aucune créative avec des insights ad-level pour cette sélection."))
        return

    creative = st.selectbox(t("meta_creatives.creative", "Créative"),
                            names['ad_name'].tolist(), key="tl_creative")

    ts = db.fetch_df(
        f"""SELECT day AS date,
                   SUM(spend)       AS spend,
                   SUM(impressions) AS impressions,
                   SUM(clicks)      AS clicks,
                   SUM(reach)       AS reach,
                   SUM(conversions) AS conversions,
                   AVG(ctr)         AS ctr
            FROM v_meta_creative_daily
            WHERE artist_id = %s{acct} AND creative_name = %s{campaign_clause}
            GROUP BY day ORDER BY day""",
        (artist_id, *acct_params, creative) if selected_campaign == "Toutes"
        else (artist_id, *acct_params, creative, selected_campaign),
    )
    if ts.empty:
        st.info(t("meta_creatives.no_timeseries", "Pas de séries temporelles pour cette créative."))
        return
    ts['date'] = pd.to_datetime(ts['date'])

    d_from, d_to = smart_date_range(t("common.period", "Période"),
                                    ts['date'].min(), ts['date'].max(), key="tl")
    mask = (ts['date'] >= pd.Timestamp(d_from)) & (ts['date'] <= pd.Timestamp(d_to))
    tsf = ts.loc[mask].copy()
    if tsf.empty:
        st.info(t("meta_creatives.no_data_period", "Aucune donnée sur la période sélectionnée."))
        return

    # Decimal (Postgres NUMERIC) → float, else Plotly mis-types the columns.
    for _, col, _, _, _, derived in _TIMELINE_METRICS:
        if not derived:
            tsf[col] = pd.to_numeric(tsf[col], errors='coerce').astype(float)
    tsf['ctr'] = tsf['ctr'] * 100  # match the ranking table's CTR % convention

    # Smart granularity: weekly down-sampling past ~120 days keeps the lines readable.
    span_days = int((tsf['date'].max() - tsf['date'].min()).days)
    partial_weeks = 0
    if span_days > 120:
        agg_map = {col: agg for _, col, agg, _, _, derived in _TIMELINE_METRICS if not derived}
        _idx = tsf.set_index('date')
        _measured = _idx.resample('W').size()
        tsf = _idx.resample('W').agg(agg_map)

        # UNE SEMAINE MESURÉE 3 JOURS SUR 7 N'EST PAS UNE SEMAINE.
        #
        # `resample('W').sum()` additionne ce qui EXISTE dans la semaine et le trace à
        # pleine hauteur. Une semaine mesurée trois jours sur sept sous-dessine donc
        # d'environ moitié, et rien ne le dit — la courbe se lit comme un effondrement
        # de la campagne.
        #
        # Mesuré sur l'artiste 1 le 2026-09-10 : **37 semaines sur 59 (63 %)** ont
        # moins de sept jours mesurés, avec une MÉDIANE de trois. C'est la vue par
        # défaut au-delà de 120 jours, donc celle que l'artiste voit en premier.
        #
        # Même règle que la figure d'accueil (`_BUCKET_FLOOR`) : sous la moitié des
        # jours, le seau est rendu INCONNU plutôt que faux. La courbe s'y interrompt,
        # ce qui est la lecture juste — on ne sait pas.
        _floor = _measured.reindex(tsf.index).fillna(0) >= 3.5
        partial_weeks = int((~_floor).sum())
        tsf = tsf.where(_floor, other=float("nan"))
        tsf = tsf.reset_index()
        granularity = t("meta_creatives.granularity_weekly", "hebdomadaire")
    else:
        granularity = t("meta_creatives.granularity_daily", "journalière")

    # CPR derived from AGGREGATED spend/results (never an average of daily CPRs).
    # NaN where no result on the period → the line simply gaps there.
    tsf['cpr'] = (tsf['spend'] / tsf['conversions'].where(tsf['conversions'] != 0)).astype(float)

    # TROIS PANNEAUX, UN PAR UNITÉ — et non sept axes superposés.
    #
    # Cette figure empilait SEPT axes Y sur un même repère : des euros, des
    # impressions, des clics, une portée, des résultats, un pourcentage et un coût.
    # Rien n'y est comparable, et `autoshift` ne rend pas comparable ce qui ne l'est
    # pas — il range seulement les graduations pour qu'elles ne se chevauchent plus.
    #
    # Elle a survécu au cliquet des axes secondaires posé le 2026-09-10 parce qu'elle
    # les CONSTRUIT : `f"yaxis{i + 1}"` ne contient aucune des chaînes que le prédicat
    # cherchait. Troisième forme aveugle du même garde, trouvée le même jour.
    #
    # Les petits multiples sont la seule alternative admise par ce dépôt. Le
    # regroupement se fait par UNITÉ : à l'intérieur d'un panneau les courbes se
    # comparent vraiment, entre panneaux elles ne prétendent pas le faire. Le
    # basculement par la légende reste possible dans chaque panneau.
    from plotly.subplots import make_subplots

    _UNIT_ROWS = [
        (t("meta_creatives.unit_money", "Euros"), ("spend", "cpr")),
        (t("meta_creatives.unit_counts", "Volumes"),
         ("impressions", "clicks", "reach", "conversions")),
        (t("meta_creatives.unit_rate", "Taux (%)"), ("ctr",)),
    ]
    _by_col = {col: (label, color, visible)
               for label, col, _, color, visible, _ in _TIMELINE_METRICS}

    fig = make_subplots(rows=len(_UNIT_ROWS), cols=1, shared_xaxes=True,
                        vertical_spacing=0.07,
                        subplot_titles=[r[0] for r in _UNIT_ROWS])
    for row, (_unit, cols) in enumerate(_UNIT_ROWS, start=1):
        for col in cols:
            if col not in tsf.columns:
                continue
            label, color, visible = _by_col[col]
            fig.add_trace(go.Scatter(
                x=tsf['date'], y=tsf[col],
                name=t(f"meta_creatives.metric.{col}", label),
                mode="lines+markers", line={"color": color}, marker={"color": color},
                visible=True if visible else "legendonly",
                # Les trous laissés par les semaines partielles restent des TROUS.
                connectgaps=False,
            ), row=row, col=1)
        fig.update_yaxes(rangemode="tozero", row=row, col=1)
    fig.update_layout(
        hovermode="x unified", height=190 * len(_UNIT_ROWS) + 60,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.04,
                "xanchor": "right", "x": 1},
        margin={"t": 70})
    st.plotly_chart(fig, width="stretch")
    if partial_weeks:
        st.caption(t(
            "meta_creatives.partial_weeks",
            "{n} semaine(s) ne sont pas tracées : moins de la moitié de leurs jours "
            "ont été mesurés, et les additionner à pleine hauteur ferait lire une "
            "chute qui n'a pas eu lieu. La courbe s'y interrompt — on ne sait pas."
        ).format(n=partial_weeks))
    st.caption(t(
        "meta_creatives.timeline_caption",
        "Créative **{creative}** · granularité {granularity} · {d_from} → {d_to}. "
        "Cliquez une métrique dans la légende pour l'afficher/masquer (double-clic = isoler)."
    ).format(creative=creative, granularity=granularity,
             d_from=f"{d_from:%d/%m/%Y}", d_to=f"{d_to:%d/%m/%Y}"))


def _render_scatter(df: pd.DataFrame) -> None:
    """#1 — bubble comparison: spend × CPR, size=impressions, color=CTR."""
    with secondary_analyses(t("meta_creatives.scatter_expander",
                              "🔬 Nuage CPR × dépense — détail")):
        d = df.copy()
        for c in ('total_spend', 'cpr', 'total_impressions', 'avg_ctr'):
            d[c] = pd.to_numeric(d[c], errors='coerce')
        d = d.dropna(subset=['total_spend', 'cpr'])
        if d.empty:
            st.info(t("meta_creatives.no_scatter", "Aucune créative avec un CPR (résultats) pour ce scatter."))
            return
        fig = px.scatter(
            d, x='total_spend', y='cpr', size='total_impressions', color='avg_ctr',
            hover_name='creative_name', color_continuous_scale='Viridis', size_max=40,
            labels={'total_spend': t("meta_creatives.spend_eur", "Dépense (€)"), 'cpr': 'CPR (€)',
                    'avg_ctr': t("meta_creatives.avg_ctr_pct", "CTR moyen (%)"),
                    'total_impressions': t("meta_creatives.impressions", "Impressions")},
        )
        fig.update_layout(height=460)
        st.plotly_chart(fig, width="stretch")
        st.caption(t("meta_creatives.scatter_caption",
                     "Une bulle = une créative. Bas = CPR efficace ; taille = impressions, couleur = CTR. "
                     "Les créatives sans résultat (CPR absent) ne sont pas tracées."))


@st.fragment
def _render_efficiency(df: pd.DataFrame) -> None:
    """Le comparateur d'indicateurs — rejoué SEUL quand on change de métrique.

    @st.fragment (R118, 2026-09-16) : bouger ce filtre ne rejoue QUE ce corps. Avant, il
    rejouait tout le script — les SIX onglets, dont `st.tabs` exécute tous les corps, plus
    la barre latérale. La mesure serveur du 2026-09-16 a montré que c'est la VUE qui pèse
    (11-13 ms de chrome contre 50 à 777 ms de vue), donc c'est bien ici que le levier agit.

    ⚠️ Cette fonction ne reçoit qu'un **DataFrame**, jamais la connexion : `show()` ferme
    la sienne dès la fin du rendu complet, et un fragment se rejoue après. Garde :
    `tests/test_a_fragment_never_captures_a_connection.py`.

    (Docstring d'origine : #4 — CTR / CPM / CPC per creative (top 15 by spend).)
    """
    with secondary_analyses(t("meta_creatives.efficiency_expander",
                              "🔬 Efficacité par créative — détail")):
        d = df.copy()
        d['total_spend'] = pd.to_numeric(d['total_spend'], errors='coerce').fillna(0.0)
        d['total_impressions'] = pd.to_numeric(d['total_impressions'], errors='coerce').fillna(0)
        d['total_clicks'] = pd.to_numeric(d['total_clicks'], errors='coerce').fillna(0)
        d['CTR (%)'] = pd.to_numeric(d['avg_ctr'], errors='coerce')
        d['CPM (€)'] = (d['total_spend'] / d['total_impressions'].where(d['total_impressions'] != 0) * 1000).astype(float)
        d['CPC (€)'] = (d['total_spend'] / d['total_clicks'].where(d['total_clicks'] != 0)).astype(float)
        d = d.sort_values('total_spend', ascending=False).head(15)
        metric = st.radio(t("meta_creatives.indicator", "Indicateur"), ["CTR (%)", "CPM (€)", "CPC (€)"], horizontal=True, key="eff_metric")
        fig = px.bar(d, x='creative_name', y=metric, color=metric,
                     color_continuous_scale='Tealrose', labels={'creative_name': ''})
        fig.update_layout(height=420, coloraxis_showscale=False)
        st.plotly_chart(fig, width="stretch")


@st.fragment
def _render_funnel(df: pd.DataFrame) -> None:
    """L'entonnoir d'une créative — rejoué SEUL quand on en choisit une autre.

    @st.fragment (R118, 2026-09-16) : bouger ce filtre ne rejoue QUE ce corps. Avant, il
    rejouait tout le script — les SIX onglets, dont `st.tabs` exécute tous les corps, plus
    la barre latérale. La mesure serveur du 2026-09-16 a montré que c'est la VUE qui pèse
    (11-13 ms de chrome contre 50 à 777 ms de vue), donc c'est bien ici que le levier agit.

    ⚠️ Cette fonction ne reçoit qu'un **DataFrame**, jamais la connexion : `show()` ferme
    la sienne dès la fin du rendu complet, et un fragment se rejoue après. Garde :
    `tests/test_a_fragment_never_captures_a_connection.py`.

    (Docstring d'origine : #3 — Impressions → Clics → Résultats funnel for one creative.)
    """
    with secondary_analyses(t("meta_creatives.funnel_expander",
                              "🔻 Le parcours d'une créative — détail")):
        names = (df.dropna(subset=['creative_name'])
                   .sort_values('creative_created', ascending=False, na_position='last')
                   ['creative_name'].drop_duplicates().tolist())
        if not names:
            st.info(t("meta_creatives.no_creative", "Aucune créative."))
            return
        sel = st.selectbox(t("meta_creatives.creative", "Créative"), names, key="funnel_creative")
        r = df[df['creative_name'] == sel].iloc[0]
        imp = int(pd.to_numeric(r['total_impressions'], errors='coerce') or 0)
        clk = int(pd.to_numeric(r['total_clicks'], errors='coerce') or 0)
        res = int(pd.to_numeric(r['total_results'], errors='coerce') or 0)
        fig = go.Figure(go.Funnel(
            # R146 — l'étape terminale portait « Résultats », ce qui donnait à un
            # clic sortant l'allure d'un aboutissement. Même anti-motif que le
            # funnel de `meta_x_spotify`, corrigé le 2026-09-21 : le fix n'avait
            # pas balayé ce fichier.
            y=[t("meta_creatives.impressions", "Impressions"),
               t("meta_creatives.clicks", "Clics"),
               t("meta_creatives.results", "Clics sortants")], x=[imp, clk, res],
            textinfo="value+percent initial", marker={'color': ['#1f77b4', '#2ca02c', '#ff6b35']},
        ))
        fig.update_layout(height=400)
        st.plotly_chart(fig, width="stretch")


@st.fragment
def _tab_fatigue(acct: str = "", acct_params: tuple = ()) -> None:
    """Le détecteur de fatigue publicitaire — rejoué SEUL quand son sélecteur change.

    @st.fragment (R118, 2026-09-16). Bouger le sélecteur rejouait tout le script : les
    SIX onglets, dont `st.tabs` exécute tous les corps, plus la barre latérale.

    ⚠️ Il rouvre une session avec `view_session()`, et ce n'est pas un style : son
    sélecteur pilote une REQUÊTE, donc il doit relire la base — alors que la session de
    `show()` est refermée dès la fin du rendu complet. `view_session()` ferme par
    construction, ce qui est la seule forme acceptée par
    `tests/test_a_fragment_never_captures_a_connection.py` pour un fragment qui ouvre.
    """
    from src.dashboard.utils.fragment_db import fragment_db

    with fragment_db() as (db, artist_id):
        _render_fatigue(db, artist_id, acct, acct_params)


def _render_fatigue(db, artist_id: int, acct: str = "",
                    acct_params: tuple = ()) -> None:
    """#2 — frequency (↗) vs CTR (↘) over time: ad-fatigue detector."""
    names = db.fetch_df(
        f"""SELECT creative_name AS ad_name, MAX(creative_created) AS last_created
           FROM v_meta_creative_daily
           WHERE artist_id = %s{acct} AND creative_name IS NOT NULL
           GROUP BY creative_name ORDER BY last_created DESC NULLS LAST, creative_name""",
        (artist_id, *acct_params),
    )
    if names.empty:
        st.info(t("meta_creatives.no_creative", "Aucune créative."))
        return
    sel = st.selectbox(t("meta_creatives.creative", "Créative"), names['ad_name'].tolist(), key="fatigue_creative")
    ts = db.fetch_df(
        f"""SELECT day AS date, AVG(frequency) AS frequency, AVG(ctr) * 100 AS ctr
           FROM v_meta_creative_daily
           WHERE artist_id = %s{acct} AND creative_name = %s
           GROUP BY day ORDER BY day""",
        (artist_id, *acct_params, sel),
    )
    if ts.empty:
        st.info(t("meta_creatives.no_timeseries", "Pas de séries temporelles pour cette créative."))
        return
    ts['date'] = pd.to_datetime(ts['date'])
    ts['frequency'] = pd.to_numeric(ts['frequency'], errors='coerce').astype(float)
    ts['ctr'] = pd.to_numeric(ts['ctr'], errors='coerce').astype(float)
    # DEUX CADRES, PAS DEUX AXES. Une fréquence (autour de 2-3) et un taux de clic
    # (autour de 1 %) n'ont ni la même unité ni le même ordre de grandeur : superposées
    # sur un repère commun, la seconde est sous le pixel ; sur deux axes décalés, leur
    # croisement visuel ne veut rien dire. Partagés en x, les deux cadres disent
    # exactement ce que la légende promet — la fréquence monte PENDANT que le CTR
    # baisse — sans qu'aucune forme soit un artefact d'échelle.
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=[t("meta_creatives.frequency", "Fréquence"),
                                        "CTR (%)"])
    fig.add_trace(go.Scatter(x=ts['date'], y=ts['frequency'],
                             name=t("meta_creatives.frequency", "Fréquence"),
                             mode='lines+markers', line={'color': '#eb6834'}),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=ts['date'], y=ts['ctr'], name='CTR (%)',
                             mode='lines+markers', line={'color': '#2a78d6'}),
                  row=2, col=1)
    fig.update_layout(hovermode="x unified", showlegend=False, height=420)
    st.plotly_chart(fig, width="stretch")
    st.caption(t("meta_creatives.fatigue_caption",
                 "Fréquence qui monte **et** CTR qui baisse = audience saturée (fatigue) → renouveler la créative."))


def _render_activity(ts_all: pd.DataFrame) -> None:
    """#5 heatmap (creative × week) + #6 cumulative spend area."""
    if ts_all is None or ts_all.empty:
        st.info(t("meta_creatives.no_spend_series", "Aucune série de dépense par créative."))
        return
    d = ts_all.copy()
    d['date'] = pd.to_datetime(d['date'])
    d['spend'] = pd.to_numeric(d['spend'], errors='coerce').fillna(0.0)
    d['week'] = d['date'].dt.to_period('W').dt.start_time

    weekly = d.groupby(['creative_name', 'week'], as_index=False)['spend'].sum()
    top = weekly.groupby('creative_name')['spend'].sum().nlargest(20).index
    hm = weekly[weekly['creative_name'].isin(top)]
    # Heatmap et cumul décrivent OÙ EST PASSÉ l'argent. C'est utile pour comprendre,
    # jamais pour décider quoi faire de la prochaine créative — les graphiques de
    # fatigue et de performance, plus haut, s'en chargent. Repliés ensemble.
    with secondary_analyses(t("meta_creatives.activity_expander",
                              "🗓️ Activité des créatives (dépense par semaine, cumul) — détail")):
        st.markdown(t("meta_creatives.heatmap_title", "**🗓️ Dépense par créative et par semaine**"))
        fig = px.density_heatmap(
            hm, x='week', y='creative_name', z='spend', histfunc='sum',
            color_continuous_scale='Oranges',
            labels={'week': '', 'creative_name': '', 'spend': t("meta_creatives.spend_eur", "Dépense (€)")},
        )
        fig.update_layout(height=520)
        st.plotly_chart(fig, width="stretch")

        st.markdown("---")
        st.markdown(t("meta_creatives.cumulative_title", "**💰 Dépense cumulée par créative**"))
        g = weekly.sort_values('week').copy()
        g['cum'] = g.groupby('creative_name')['spend'].cumsum()
        top12 = g.groupby('creative_name')['cum'].max().nlargest(12).index
        g = g[g['creative_name'].isin(top12)]
        fig2 = px.area(g, x='week', y='cum', color='creative_name',
                       labels={'week': '', 'cum': t("meta_creatives.cumulative_spend_eur", "Dépense cumulée (€)"),
                               'creative_name': t("meta_creatives.creative", "Créative")})
        fig2.update_layout(height=480)
        st.plotly_chart(fig2, width="stretch")


def show() -> None:
    if not require_plan('premium'):
        return

    st.title(t("meta_creatives.title", "🎨 Créatives Meta Ads"))
    st.caption(t("meta_creatives.subtitle",
                 "Classement de vos créatives par CPR — basé sur les données Meta Ads API (meta_ads × meta_insights)."))
    # R146 — toute la page classe des créatives sur un coût par CLIC SORTANT.
    st.caption(disclosure_caption())

    # La connexion vivante est DECLAREE pour les fragments de cette page : dans un
    # rendu complet ils la reutilisent au lieu d'en ouvrir une (~13 ms la poignee
    # SCRAM, mesure) ; lors d'un rerun de fragment la fente est vide et ils rouvrent
    # proprement. Voir `src/dashboard/utils/fragment_db.py`.
    from src.dashboard.utils.fragment_db import page_db_scope

    with view_session() as (db, artist_id), page_db_scope(db, artist_id):
        # Toutes les requêtes de cette page s'ancrent sur `meta_ads` ou
        # `meta_campaigns`, qui portent `ad_account_id` — `meta_insights` est à la
        # maille ad_id, globalement unique, donc filtrer l'ancre suffit.
        _account = account_scope(db, artist_id, key="meta_creatives_acct")
        # PAS d'alias : `_QUERY_CREATIVES` lit `v_meta_creative_daily`, une seule
        # relation. Un fragment ` AND ma.ad_account_id = %s` y lève
        # `missing FROM-clause entry for table "ma"` — j'ai introduit ce défaut le
        # 2026-09-12 en repointant la requête sans regarder l'alias que son appelant
        # lui passait, c'est-à-dire la MÊME erreur que celle que le repointage
        # corrigeait, dans sa troisième forme.
        _acct_ma, _acct_params = account_clause(_account)
        _acct_mc, _ = account_clause(_account, "mc.")
        _acct_bare, _ = account_clause(_account)
        df = db.fetch_df(_QUERY_CREATIVES.format(acct=_acct_ma),
                         (artist_id, *_acct_params))
        uncollected = db.fetch_df(
            _QUERY_UNCOLLECTED.format(acct=_acct_bare, acct_mc=_acct_mc),
            (artist_id, *_acct_params, artist_id, *_acct_params))

        _render_uncollected_notice(uncollected)

        if df.empty:
            st.info(t(
                "meta_creatives.no_data",
                "Aucune donnée de créative. Vérifie que Meta Ads est connecté dans "
                "**🔑 Credentials API** — la collecte démarre toute seule à l'enregistrement, "
                "dans la barre latérale."
            ))
            return

        # Filtres — campagnes les plus récentes en haut (par start_time desc).
        camp_order = (
            df.dropna(subset=['campaign_name'])
              .sort_values('campaign_start', ascending=False, na_position='last')
              ['campaign_name'].drop_duplicates().tolist()
        )
        # "Toutes" stays the internal sentinel value; only its display is translated.
        campaigns = ["Toutes"] + camp_order
        col_filter, _ = st.columns([2, 4])
        selected_campaign = col_filter.selectbox(
            t("meta_creatives.filter_by_campaign", "Filtrer par campagne"), campaigns,
            format_func=lambda c: t("meta_creatives.all_campaigns", "Toutes") if c == "Toutes" else c)

        if selected_campaign != "Toutes":
            df = df[df['campaign_name'] == selected_campaign]

        if df.empty:
            st.warning(t("meta_creatives.no_creative_campaign", "Aucune créative pour cette campagne."))
            return

        # ── UNE SEULE PAGE, et c'est une demande explicite du 2026-09-21 :
        # « regroupe-moi tout en 1 seule page ».
        #
        # ⚠️ Les six onglets n'ont pas été dépliés tels quels. `st.tabs` BORNE un
        # écran — c'est écrit dans `first-screen-ceilings.json` — donc tout aplatir
        # aurait fait passer cette vue de 8 figures de premier écran à quatorze. Le
        # remplacement n'est pas l'onglet, c'est le DÉPLIANT : la page se lit d'un
        # bout à l'autre en scrollant, la décision est en haut, et chaque analyse
        # qui ne fait que raffiner cette décision se replie elle-même.
        #
        # Reste donc à l'écran, dans cet ordre : la décision, le classement, les
        # hooks, la fatigue, l'évolution. Cinq blocs, quatre figures.
        _render_decision_banner(df)
        st.markdown("---")

        st.subheader(t("meta_creatives.section_ranking", "🏁 Le classement de tes créatives"))
        _render_ranking(df)
        _render_table(df)

        st.markdown("---")
        st.subheader(t("meta_creatives.section_hooks", "🎣 Quelle accroche convertit"))
        _render_hooks(df)

        st.markdown("---")
        st.subheader(t("meta_creatives.section_fatigue", "🪫 Une audience saturée ?"))
        _tab_fatigue(_acct_ma, _acct_params)

        _tab_creative_timeline(selected_campaign, _acct_ma, _acct_params)

        st.markdown("---")
        st.subheader(t("meta_creatives.section_details", "🔬 Pour creuser"))
        _render_funnel(df)
        _render_scatter(df)
        _render_efficiency(df)
        ts_all = db.fetch_df(_QUERY_TS_ALL.format(acct=_acct_ma),
                             (artist_id, *_acct_params))
        _render_activity(ts_all)
