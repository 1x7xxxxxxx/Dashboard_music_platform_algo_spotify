"""Vue Créatives Meta Ads — Classement des créatives par CPR.

Type: Feature
Uses: get_db_connection, get_artist_id
Depends on: meta_ads, meta_insights, meta_campaigns tables (API-based)
Persists in: read-only
"""
import re

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.dashboard.utils import charts
from src.dashboard.utils.formats import num
from src.dashboard.utils.i18n import t
from src.dashboard.utils.campaign_pair import pair_colors
from src.dashboard.utils.creative_decisions import _a_couper, by_creative, render_creative_gain  # noqa: F401 — R233: moved out, still importable from here
from src.dashboard.utils.proxy_disclosure import disclosure_caption
from src.dashboard.utils.meta_confidence import K_DEFAUT, confidence_factor
from src.dashboard.auth import is_admin

# R557 — the two settings the ad set holds and the breakdowns do not: button and objective.
# Moved from the algo page's settings tab. `v_meta_ad_daily` carries no conversions, so these
# are priced per AD click (said in the caption). Two literals, not one template:
# `tools/dev/gold_coverage.py` reads the view name from each query's text.
# Classe : `a-join-that-multiplies-the-grain` (the view names its tenant, migration 138).
_Q_AXE = {
    "cta": """
        SELECT call_to_action AS valeur, COUNT(DISTINCT ad_id) AS ads,
               SUM(spend) AS depense, SUM(clicks) AS clics,
               SUM(impressions) AS impressions, campaign_name
          FROM v_meta_ad_daily
         WHERE artist_id = %s GROUP BY 1, campaign_name
    """,
    "objectif": """
        SELECT objective AS valeur, COUNT(DISTINCT ad_id) AS ads,
               SUM(spend) AS depense, SUM(clicks) AS clics,
               SUM(impressions) AS impressions, campaign_name
          FROM v_meta_ad_daily
         WHERE artist_id = %s GROUP BY 1, campaign_name
    """,
}


# Each metric gets its own Y-axis (scales differ wildly: € vs thousands of impressions).
# (label, column, weekly-resample aggregation, colour, visible-by-default, derived)
# Non-default metrics start as 'legendonly' → the chart opens readable; click the
# legend to toggle any metric (and its axis) on/off. `derived` metrics (CTR, CPR) are
# NOT fetched/resampled directly — they are recomputed from aggregated columns afterwards.
# Labels are FR sources, translated at render time via t(f"meta_creatives.metric.{col}").
_TIMELINE_METRICS = [
    ("Dépense (€)", "spend",       "sum",  "#ff6b35", True,  False),
    ("Impressions", "impressions", "sum",  "#1f77b4", True,  False),
    ("Clics",       "clicks",      "sum",  "#2ca02c", False, False),
    ("Reach",       "reach",       "sum",  "#9467bd", False, False),
    ("Résultats",   "conversions", "sum",  "#d62728", False, False),
    # R209 — CTR visible by default: hidden, it left the « Taux (%) » panel EMPTY.
    ("CTR (%)",     "ctr",         None,   "#e6b800", True,  True),
    ("CPR (€)",     "cpr",         None,   "#17becf", True,  True),
]


# total_results = the ad set goal's native result (mi.conversions, objective-aware).
# CPR is shown ONLY for conversion goals (cost-per-result on an engagement/traffic ad
# would imply a conversion that didn't happen — see collector _CONVERSION_GOALS).
from src.dashboard.utils.campaign_compare import _CONVERSION_GOALS_SQL  # noqa: E402 — R590: one definition

# La quadruple jointure a disparu dans `v_meta_creative_daily` (migrations 106 et
# 108). Elle ne nommait le locataire que sur `ma`, et son filtre de compte
# publicitaire était AMBIGU — `meta_ads`, `meta_adsets` et `meta_campaigns`
# portent toutes `ad_account_id`, donc choisir un compte faisait tomber la page
# avec `column reference "ad_account_id" is ambiguous`. Une vue n'a qu'une colonne
# de ce nom : le défaut ne peut plus se poser.
#
# THE CTR IS RECOMPUTED FROM ITS COUNTS, NEVER AVERAGED OR RESCALED.
#
# Meta's `ctr` field is ALREADY a percent (0-100): the collector stores it unchanged
# (`_meta_parsers.py`) and the validator bounds it at `le=100`. Measured on
# `meta_insights` of `spotify_etl_review` on 2026-09-26: 2 023 rows, 2 015 with
# impressions > 0 (the N the formula below actually uses), and on those
# corr(ctr, 100*clicks/impressions) = 0.99999999999, same mean (1.6967) on both sides.
#
# This page used to read `SUM(ctr_sum) / SUM(ctr_n) * 100` here, `AVG(ctr) * 100` in
# the fatigue chart and `ctr * 100` in the timeline. Two defects stacked: a second
# x100, and a mean of per-ad rates in which a 1-impression / 1-click ad weighs as much
# as a 1 000-impression one. On artist 1: 32 of 61 creatives displayed above 100 %
# (max 1 111 %), while the ratio of sums peaks at 10.25 %. The "163,41 % / 168,68 %"
# this comment used to quote as the right figures were both products of that defect.
#
# One definition for the three reads: 100 * Sum(clicks) / Sum(impressions). `clicks` is
# the all-clicks numerator Meta uses for its own `ctr`.
# Guard: tests/test_a_rate_is_recomputed_from_its_counts.py
_CTR_SQL = "ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 2)"

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
    {_CTR_SQL}              AS avg_ctr,
    SUM(reach)                                                          AS total_reach,
    SUM(impressions)                                                    AS total_impressions,
    SUM(clicks)                                                         AS total_clicks,
    -- Migration 138. NULL tant qu'une seule ligne du groupe a été collectée avant
    -- elle : une somme partielle se lirait comme une mesure complète.
    CASE WHEN SUM(measured_n) = SUM(rows_n) THEN SUM(link_clicks) END   AS total_link_clicks,
    CASE WHEN SUM(measured_n) = SUM(rows_n) THEN SUM(custom_conversions) END AS total_outbound,
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
-- The tenant is named at EVERY join (2026-09-26): on `ad_id` alone, a sandbox
-- tenant's copy of the same ad gave it spend and hid the campaign from this list.
JOIN meta_ads ma ON ma.campaign_id = mc.campaign_id AND ma.artist_id = mc.artist_id
LEFT JOIN meta_insights mi ON mi.ad_id = ma.ad_id AND mi.artist_id = ma.artist_id
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
        # R568 — a list, not a table: the cross view carries no `st.dataframe`.
        st.markdown("\n".join(t(
            "meta_creatives.uncollected_row", "- **{c}** — {ads} publicité(s) · {spend} €").format(
            c=r.campaign_name, ads=int(r.ads), spend=num(float(r.campaign_spend or 0), 2))
            for r in df.itertuples()))


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
    from src.dashboard.utils.ratios import per_series      # R258 — one definition
    g['cpr'] = per_series(g['total_spend'], g['total_results'])
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


# Le classement, en figures. (label, colonne, format, couleur, sens)
# `plus_bas_est_mieux` n'est vrai que pour un COÛT : c'est ce qui décide du sens
# du tri et de la couleur du meilleur.
_RANG_PANNEAUX = [
    # R569 — CPR and spend left: « Tes meilleurs réglages » draws creative × CPR and the
    # spend Pareto creative × spend. One datum, one chart.
    ("Résultats",     'total_results', "{:.0f}", "#2ca02c", False),
    ("CTR (%)",       'avg_ctr',       "{:.2f}", "#e6b800", False),
    # R299 — CPM and CPC came from « Efficacité par créative », a second chart of the same
    # 15 creatives whose CTR repeated the frame above; merged here, lower is better.
    ("CPM (€)",       'cpm',           "{:.2f}", "#9467bd", True),
    ("CPC (€)",       'cpc',           "{:.2f}", "#17becf", True),
]
_RANG_MAX = 15


def _render_ranking(df: pd.DataFrame, pair: tuple | None = None) -> None:
    """Le classement des créatives — QUATRE cadres (résultats, CTR, CPM, CPC — R569), un par unité, noms en Y.

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

    d = _numerise(by_creative(df))   # R241 — one bar per creative, never per (creative, campaign)
    d = d[d['total_spend'].notna() & (d['total_spend'] > 0)]
    from src.dashboard.utils.ratios import per_series   # R258 — one ratio definition
    d['cpm'] = per_series(d['total_spend'], d['total_impressions'], 1000)
    d['cpc'] = per_series(d['total_spend'], d['total_clicks'])
    if d.empty:
        st.info(t("meta_creatives.no_ranking", "Aucune créative avec de la dépense."))
        return
    d = d.nlargest(_RANG_MAX, 'total_spend')
    # R243 (fiche 29) : trié par l'étape choisie, le MEILLEUR EN HAUT (Plotly empile du bas).
    tri = st.segmented_control(t("meta_creatives.rank_sort", "Trier par"), [c[1] for c in _RANG_PANNEAUX], format_func=dict((c[1], c[0]) for c in _RANG_PANNEAUX).get, default='total_results', key="rank_sort") or 'total_results'
    d = d.sort_values(tri, ascending=not dict((c[1], c[4]) for c in _RANG_PANNEAUX)[tri], na_position='first')
    noms = d['creative_name'].tolist()

    fig = make_subplots(
        rows=1, cols=len(_RANG_PANNEAUX), shared_yaxes=True, horizontal_spacing=0.035,
        subplot_titles=[t(f"meta_creatives.rank.{col}", lab)
                        for lab, col, _, _, _ in _RANG_PANNEAUX])
    for i, (lab, col, fmt, couleur, _bas) in enumerate(_RANG_PANNEAUX, start=1):
        vals = d[col] if col in d.columns else pd.Series([float("nan")] * len(d))
        fig.add_trace(go.Bar(
            x=vals, y=noms, orientation='h',
            marker={'color': couleur if pair is None else pair_colors(noms, df, *pair)},
            name=lab, showlegend=False,
            text=[fmt.format(v) if pd.notna(v) else "—" for v in vals],
            textposition='auto', cliponaxis=False,   # inside a long bar: never spills
            hovertemplate=f"%{{y}}<br>{lab} : %{{x}}<extra></extra>",
        ), row=1, col=i)
        fig.update_xaxes(showticklabels=False, row=1, col=i)
    fig.update_layout(height=max(320, 34 * len(noms) + 120),
                      margin={'l': 10, 'r': 40, 't': 60, 'b': 20},
                      bargap=0.25)
    fig.update_yaxes(automargin=True)
    charts.plotly_chart(fig, width="stretch")
    if pair is not None:   # R568 — the colour key only; the prose went
        st.caption(t("meta_creatives.pair_caption",
                     "Bleu : « {a} » · orange : « {b} » · gris : une créative des deux "
                     "campagnes.").format(a=pair[0], b=pair[1]))


# The timeline of ONE creative: counts only. CTR and CPR are not fetched — they are
# derived by `_prepare_timeline()` from these sums, after any weekly resample.
_QUERY_TIMELINE = """
SELECT day AS date,
       SUM(spend)       AS spend,
       SUM(impressions) AS impressions,
       SUM(clicks)      AS clicks,
       SUM(reach)       AS reach,
       SUM(conversions) AS conversions
FROM v_meta_creative_daily
WHERE artist_id = %s{acct} AND creative_name = %s{campaign_clause}
GROUP BY day ORDER BY day
"""

# R568 — what the timeline is annotated with: the campaign(s) the creative ran in, each with
# its optimisation goal, most spent first.
_QUERY_CREATIVE_CONTEXT = """
SELECT campaign_name, STRING_AGG(DISTINCT optimization_goal, ', ') AS goal
FROM v_meta_creative_daily
WHERE artist_id = %s{acct} AND creative_name = %s{campaign_clause}
GROUP BY campaign_name ORDER BY SUM(spend) DESC NULLS LAST
"""


def _creative_context(db, artist_id: int, creative: str, selected_campaign: str,
                      acct: str, acct_params: tuple) -> str:
    """« campagne (objectif) · … » for one creative, inside the bar's campaign."""
    campaign_clause = "" if selected_campaign == "Toutes" else " AND campaign_name = %s"
    ctx = db.fetch_df(
        _QUERY_CREATIVE_CONTEXT.format(acct=acct, campaign_clause=campaign_clause),
        (artist_id, *acct_params, creative) if selected_campaign == "Toutes"
        else (artist_id, *acct_params, creative, selected_campaign))
    unknown = t("meta_creatives.goal_unknown", "objectif inconnu")
    return " · ".join(t("meta_creatives.tl_context", "{campaign} ({goal})").format(
        campaign=r.campaign_name or "—", goal=r.goal or unknown) for r in ctx.itertuples())

def _prepare_timeline(tsf: pd.DataFrame) -> tuple[pd.DataFrame, int, bool]:
    """Numeric coercion, weekly resample past 120 days, then the derived rates.

    Returns (frame, number of masked partial weeks, whether it was resampled).
    """
    tsf = tsf.copy()
    # Decimal (Postgres NUMERIC) → float, else Plotly mis-types the columns.
    for _, col, _, _, _, derived in _TIMELINE_METRICS:
        if not derived:
            tsf[col] = pd.to_numeric(tsf[col], errors='coerce').astype(float)

    # Smart granularity: weekly down-sampling past ~120 days keeps the lines readable.
    span_days = int((tsf['date'].max() - tsf['date'].min()).days)
    partial_weeks = 0
    weekly = span_days > 120
    if weekly:
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

    # ⚠️ ORDER MATTERS — keep the two derived rates HERE, after the weekly resample and
    # after the partial-week floor mask. Derived from the masked counts, a masked week
    # yields NaN and the line gaps. Derived before the resample, they would have to be
    # re-aggregated per week, i.e. a mean of daily ratios — the defect this replaced.
    # Derived anywhere that skips the mask (e.g. from pre-mask sums), a 3-day week
    # would draw a full-height point. The guard checks values on fixed inputs, not
    # this position: a partial-week case would only catch it if its fixture has one.
    # CPR derived from AGGREGATED spend/results (never an average of daily CPRs).
    # NaN where no result on the period → the line simply gaps there.
    from src.dashboard.utils.ratios import per_series      # R258 — one definition
    tsf['cpr'] = per_series(tsf['spend'], tsf['conversions'])
    # CTR the same way: 100 * Σclicks / Σimpressions, never a mean of daily rates.
    tsf['ctr'] = per_series(tsf['clicks'], tsf['impressions'], 100.0)
    return tsf, partial_weeks, weekly


@st.fragment
def _tab_creative_timeline(selected_campaign: str, acct: str = "", acct_params: tuple = (),
                           window=None) -> None:
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
        _render_creative_timeline(db, artist_id, selected_campaign, acct, acct_params, window)


def _render_creative_timeline(db, artist_id: int, selected_campaign: str,
                              acct: str = "", acct_params: tuple = (), window=None) -> None:
    """Per-creative multi-metric timeline (one Y-axis per metric, legend toggle).

    The creative list honours the page's campaign filter. The period filter is
    data-bounded (filters.span, R259). Each metric has its own Y-axis; non-default
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

    # R557 (fiche 37) — two creatives side by side, each with its spend, its mean CPR and
    # the streams it gained: « laquelle a mieux marché » is read across, not remembered.
    # R599 — the reference ABOVE « comparer avec », as every pair of filters in the app.
    choices = names['ad_name'].tolist()
    creative = st.selectbox(t("meta_creatives.creative", "Créative"), choices,
                            key="tl_creative")
    none = t("meta_creatives.compare_none", "— aucune —")
    second = st.selectbox(t("meta_creatives.compare_with", "Comparer avec"),
                          [none, *[c for c in choices if c != creative]], key="tl_creative_b")
    from src.dashboard.utils.campaign_compare import creative_gains
    gains = creative_gains(db, artist_id, acct, acct_params)
    if second == none:
        _render_one_creative(db, artist_id, creative, selected_campaign, acct, acct_params,
                             window, gains)
        return
    for col, name in zip(st.columns(2), (creative, second)):
        with col:
            _render_one_creative(db, artist_id, name, selected_campaign, acct, acct_params,
                                 window, gains)


def _creative_totals(tsf: pd.DataFrame, creative: str, gains: dict) -> None:
    """The three numbers of fiche 37: spend, mean CPR (Σspend/Σresults), streams gained."""
    from src.dashboard.utils.ratios import per
    spend = float(pd.to_numeric(tsf['spend'], errors='coerce').sum())
    res = float(pd.to_numeric(tsf['conversions'], errors='coerce').sum())
    cpr = per(spend, res)
    # One line, not two tiles: the timeline above is the figure, these are its totals.
    st.markdown(t("meta_creatives.tl_totals",
                  "**Dépense totale** {spend} € · **CPR moyen** {cpr}").format(
        spend=num(spend, 2), cpr=f"{num(cpr, 3)} €" if cpr is not None else "—"))
    render_creative_gain(creative, gains)


def _render_one_creative(db, artist_id: int, creative: str, selected_campaign: str,
                         acct: str, acct_params: tuple, window, gains: dict) -> None:
    """The timeline of ONE creative and its totals — drawn once, or twice side by side."""
    campaign_clause = "" if selected_campaign == "Toutes" else " AND campaign_name = %s"
    ts = db.fetch_df(
        _QUERY_TIMELINE.format(acct=acct, campaign_clause=campaign_clause),
        (artist_id, *acct_params, creative) if selected_campaign == "Toutes"
        else (artist_id, *acct_params, creative, selected_campaign),
    )
    if ts.empty:
        st.info(t("meta_creatives.no_timeseries", "Pas de séries temporelles pour cette créative."))
        return
    ts['date'] = pd.to_datetime(ts['date'])

    # R399 — the page's period (the filter bar), not a second one drawn here.
    d_from, d_to = ((window.start, window.end) if window is not None
                    else (ts['date'].min().date(), ts['date'].max().date()))
    mask = (ts['date'] >= pd.Timestamp(d_from)) & (ts['date'] <= pd.Timestamp(d_to))
    tsf = ts.loc[mask].copy()
    if tsf.empty:
        st.info(t("meta_creatives.no_data_period", "Aucune donnée sur la période sélectionnée."))
        return

    tsf, partial_weeks, _weekly = _prepare_timeline(tsf)
    # R568 — the creative named with the campaign(s) it ran in and their optimisation goal.
    st.markdown(f"**{creative}** — "
                f"{_creative_context(db, artist_id, creative, selected_campaign, acct, acct_params)}")
    _creative_totals(tsf, creative, gains)

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

    # R209 — the cost per result (~0.1 €) has its OWN panel: on the spend's euro axis
    # (0-40 €) it lay flat on zero and read as « free » (dossier fiche 40).
    _UNIT_ROWS = [
        (t("meta_creatives.unit_money", "Euros"), ("spend",)),
        (t("meta_creatives.unit_cpr", "Coût par résultat (€)"), ("cpr",)),
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
        margin={"t": 70})
    charts.plotly_chart(charts.to_base100(fig)[0], width="stretch")   # R244 fiche 31 : UN repère
    if partial_weeks:
        st.caption(t(
            "meta_creatives.partial_weeks",
            "{n} semaine(s) ne sont pas tracées : moins de la moitié de leurs jours "
            "ont été mesurés, et les additionner à pleine hauteur ferait lire une "
            "chute qui n'a pas eu lieu. La courbe s'y interrompt — on ne sait pas."
        ).format(n=partial_weeks))


def _render_best_settings(db, artist_id: int, bar, df: pd.DataFrame) -> None:
    """R557 (owner Y2, fiches 36, 38, 53) — every setting the artist can change, one CPR panel
    each. Replaces the spend × CPR cloud and the settings tab of the algo page: the same
    question was answered three times, by eye each time.

    R597 (owner, 2026-10-15) — the colours are the campaigns, named in the legend: the two
    of the filter bar, or the two most recently launched when it says « Toutes ». The ad
    set's optimisation panel left (owner: « supprime-le »).

    The creative and hook panels follow the bar's period; country, placement, platform and
    age come from Meta's breakdowns, which have no date (said in the caption)."""
    from src.dashboard.utils import best_settings
    from src.dashboard.utils.campaign_pair import PAIR_COLORS

    compared = list(bar.scope or bar.campaigns[:2])
    fig = best_settings.figure(_settings_panels(db, artist_id, bar, df, compared),
                               colours=dict(zip(compared, PAIR_COLORS)))
    if fig is None:
        st.info(t("meta_creatives.bs_empty", "Pas encore assez de dépense mesurée pour "
                  "comparer tes réglages."))
        return
    charts.plotly_chart(fig, width="stretch")
    # R568 — the verdict lines went (the ★ says it); the caption stays as the chart's key.
    st.caption(best_settings.caption())


def _settings_panels(db, artist_id: int, bar, df: pd.DataFrame,
                     compared: list[str]) -> list[tuple[str, pd.DataFrame]]:
    """Every panel, ranked once per compared campaign (`best_settings.rank_by`)."""
    from src.dashboard.utils.best_settings import rank_by
    from src.dashboard.views.meta_breakdowns import _breakdown_frame, _panel

    d = df[df["campaign_name"].isin(compared)]
    hooks = pd.concat([_par_hook(g).assign(campaign_name=k)
                       for k, g in d.groupby("campaign_name", sort=False)] or [pd.DataFrame()])
    panels = [(t("meta_creatives.bs_creative", "Créative"),
               rank_by(d, "creative_name", "campaign_name", "total_spend", "total_results")),
              (t("meta_creatives.bs_hook", "Accroche"),
               rank_by(hooks, "hook", "campaign_name", "total_spend", "total_results"))]
    acct, acct_params = bar.acct()
    frames = []
    for c in compared:
        bd = _breakdown_frame(db, artist_id, "performance", "campaign", "campaign_name", c,
                              acct, acct_params)
        # psycopg2 returns SUM() as Decimal (object dtype): `_panel` keeps only numeric
        # columns when it folds placements into platforms, and would drop the spend.
        for col in ("spend", "results"):
            if col in bd:
                bd[col] = pd.to_numeric(bd[col], errors="coerce")
        frames.append((c, bd))
    for panel, label in (("country", t("meta_creatives.bs_country", "Pays")),
                         ("placement", t("meta_creatives.bs_placement", "Placement")),
                         ("platform", t("meta_creatives.bs_platform", "Plateforme")),
                         ("age", t("meta_creatives.bs_age", "Âge"))):
        parts = [_panel(bd, panel).assign(campaign_name=c) for c, bd in frames if not bd.empty]
        panels.append((label, rank_by(pd.concat(parts) if parts else pd.DataFrame(),
                                      "dim_label", "campaign_name")))
    return panels + _ad_setting_panels(db, artist_id, compared)


def _ad_setting_panels(db, artist_id: int, compared: list[str]) -> list[tuple[str, pd.DataFrame]]:
    """The settings chosen per ad: CTA and campaign objective, per compared campaign."""
    from src.dashboard.utils.best_settings import rank_by
    out = []
    for axe, label in (("cta", t("meta_creatives.bs_cta", "Bouton d'action (€/clic)")),
                       ("objectif", t("meta_creatives.bs_objective", "Objectif (€/clic)"))):
        f = db.fetch_df(_Q_AXE[axe], (artist_id,))
        f = f[f["campaign_name"].isin(compared)] if not f.empty else f
        out.append((label, rank_by(f, "valeur", "campaign_name", "depense", "clics")))
    return out


# R568 — the ad set each creative ran in. Only the raw catalogue names it:
# `v_meta_creative_daily` stops at the campaign. The tenant is named at every join.
_QUERY_ADSETS = """
SELECT d.ad_name AS creative_name, c.campaign_name, s.adset_name
FROM meta_ads d
JOIN meta_adsets s ON s.adset_id = d.adset_id AND s.artist_id = d.artist_id
JOIN meta_campaigns c ON c.campaign_id = d.campaign_id AND c.artist_id = d.artist_id
WHERE d.artist_id = %s{acct_d} AND d.ad_name IS NOT NULL
"""
_PARETO_KEY = "crea_pareto_campaigns"
_PARETO_MAX = 25


def _pareto_frame(df: pd.DataFrame, adsets: pd.DataFrame) -> pd.DataFrame:
    """One row per (creative, campaign), labelled « campagne › ad set › pub », most spent first."""
    d = _numerise(df)[['creative_name', 'campaign_name', 'total_spend', 'cpr']]
    keys = ['creative_name', 'campaign_name']
    names = (adsets.dropna(subset=['adset_name']).groupby(keys)['adset_name']
             .agg(lambda s: " / ".join(sorted(set(s)))).reset_index()
             if not adsets.empty else pd.DataFrame(columns=[*keys, 'adset_name']))
    d = d.merge(names, on=keys, how='left', validate='many_to_one')
    # R578 — the hierarchy read left to right, as in Ads Manager: campaign › ad set › ad.
    d['label'] = [f"{k} › {a if isinstance(a, str) else '—'} › {c}"
                  for c, a, k in zip(d['creative_name'], d['adset_name'], d['campaign_name'])]
    return d.sort_values('total_spend', ascending=False).reset_index(drop=True)


def _pareto_figure(d: pd.DataFrame) -> go.Figure:
    """Horizontal Pareto: most spent on top, each bar COLOURED by its CPR (R596).

    Owner, 2026-10-15: « dépense ET CPR d'un coup d'œil » — the length is the money, the
    colour is what it cost per result (green = cheap, red = dear), the CPR still written
    on the bar. A bar with no CPR (no conversion goal) is grey, in its own trace."""
    up = d.iloc[::-1]
    cpr = pd.to_numeric(up['cpr'], errors='coerce')
    text = [f"{num(s, 0)} € · CPR {num(c, 3) + ' €' if pd.notna(c) else '—'}"
            for s, c in zip(up['total_spend'], cpr)]
    fig = go.Figure()
    known = cpr.notna().to_numpy()
    if known.any():
        fig.add_trace(go.Bar(
            x=up['total_spend'][known], y=up['label'][known], orientation='h',
            showlegend=False, text=[x for x, k in zip(text, known) if k],
            textposition='auto', cliponaxis=False,
            # One dear outlier would wash every other bar green: the scale stops at the 9th
            # decile, the bar past it simply reads as the reddest.
            marker={'color': cpr[known], 'colorscale': 'RdYlGn_r', 'showscale': True,
                    'cmin': 0, 'cmax': float(cpr[known].quantile(0.9)) or None,
                    'colorbar': {'title': {'text': t("meta_creatives.pareto_cpr_scale",
                                                     "CPR (€)")}, 'thickness': 12,
                                 'x': 1.0, 'xanchor': 'left', 'xpad': 150}},
            hovertemplate="%{y}<br>%{x:,.2f} € · CPR %{marker.color:,.3f} €<extra></extra>"))
    if (~known).any():
        fig.add_trace(go.Bar(
            x=up['total_spend'][~known], y=up['label'][~known], orientation='h',
            showlegend=False, text=[x for x, k in zip(text, known) if not k],
            textposition='auto', cliponaxis=False, marker={'color': '#9E9E9E'},
            hovertemplate="%{y}<br>%{x:,.2f} €<extra></extra>"))
    # The full « campagne › ad set › pub » stays the category (unique) and the hover; the
    # tick keeps its two ends, so a long ad set name no longer squeezes the bars away.
    labels = up['label'].tolist()
    fig.update_yaxes(categoryorder="array", categoryarray=labels, automargin=True,
                     tickvals=labels, ticktext=[_short(x) for x in labels])
    fig.update_xaxes(title_text=t("meta_creatives.pareto_x", "Dépense (€)"), rangemode="tozero")
    fig.update_layout(height=max(320, 30 * len(d) + 120), barmode='overlay',
                      margin={'l': 10, 'r': 200, 't': 30, 'b': 40})
    return fig


def _short(label: str, keep: int = 28) -> str:
    """Both ends of a long label: the campaign it starts with, the ad it ends with."""
    return label if len(label) <= 2 * keep + 1 else f"{label[:keep]}…{label[-keep:]}"


def _render_spend_pareto(db, artist_id: int, bar, df: pd.DataFrame) -> None:
    """R568 — where the money went: every creative of the bar's scope, coloured by campaign.

    Replaces R557's folded dual-axis Pareto (spend bars, CPR line): the CPR is written on
    each bar, and a campaign filter narrows the bars without touching the page's bar."""
    acct_d, acct_params = bar.acct("d.")
    adsets = db.fetch_df(_QUERY_ADSETS.format(acct_d=acct_d), (artist_id, *acct_params))
    d = _pareto_frame(df, adsets)
    camps = list(dict.fromkeys(d['campaign_name']))
    keep = st.multiselect(t("meta_creatives.pareto_campaigns", "Campagnes"), camps,
                          default=camps, key=_PARETO_KEY)
    d = d[d['campaign_name'].isin(keep)].head(_PARETO_MAX)
    if d.empty:
        st.info(t("meta_creatives.pareto_empty", "Aucune campagne choisie."))
        return
    charts.plotly_chart(_pareto_figure(d), width="stretch")


def show() -> None:
    # R399 — the creatives are a section of the cross view, under its one filter bar.
    from src.dashboard.views.meta_ads_overview import show as show_cross_view
    show_cross_view("creas")


def render(db, artist_id, bar) -> None:
    """The creatives section — connection, fragments' slot and filters held by the page."""
    st.subheader(t("meta_creatives.title", "🎨 Créatives Meta Ads"))
    # R146 — toute la page classe des créatives sur un coût par CLIC SORTANT.
    st.caption(disclosure_caption())
    _render_body(db, artist_id, bar)


def _render_body(db, artist_id, bar) -> None:
    # Toutes les requêtes de cette page s'ancrent sur `meta_ads` ou
    # `meta_campaigns`, qui portent `ad_account_id` — `meta_insights` est à la
    # maille ad_id, globalement unique, donc filtrer l'ancre suffit.
    # PAS d'alias : `_QUERY_CREATIVES` lit `v_meta_creative_daily`, une seule
    # relation. Un fragment ` AND ma.ad_account_id = %s` y lève
    # `missing FROM-clause entry for table "ma"` — j'ai introduit ce défaut le
    # 2026-09-12 en repointant la requête sans regarder l'alias que son appelant
    # lui passait, c'est-à-dire la MÊME erreur que celle que le repointage
    # corrigeait, dans sa troisième forme.
    _acct_ma, _acct_params = bar.acct()
    _acct_mc, _ = bar.acct("mc.")
    _acct_bare, _ = bar.acct()
    # R399 — the period of the bar bounds the ranking, as it bounds « Performance ».
    _win, _win_params = bar.window.sql_between("day")
    df = db.fetch_df(_QUERY_CREATIVES.format(acct=_acct_ma + _win),
                     (artist_id, *_acct_params, *_win_params))
    uncollected = db.fetch_df(
        _QUERY_UNCOLLECTED.format(acct=_acct_bare, acct_mc=_acct_mc),
        (artist_id, *_acct_params, artist_id, *_acct_params))

    _render_uncollected_notice(uncollected)

    if df.empty:
        st.info(t(
            "meta_creatives.no_data",
            "Aucune donnée de créative. Vérifie que Meta Ads est connecté dans "
            "**🔑 Credentials API** — la collecte démarre toute seule à l'enregistrement, "
            "et son état s'affiche dans la barre latérale."
        ))
        return

    selected_campaign = bar.campaign or "Toutes"   # « Toutes » = the fragments' sentinel
    second = bar.second
    pair = (selected_campaign, second) if second else None

    if bar.scope:
        df = df[df['campaign_name'].isin(bar.scope)]

    if df.empty:
        st.warning(t("meta_creatives.no_creative_campaign", "Aucune créative pour cette campagne."))
        return

    # ── UNE SEULE PAGE, et c'est une demande explicite du 2026-09-21 :
    # « regroupe-moi tout en 1 seule page ».
    #
    # ⚠️ Les six onglets n'ont pas été dépliés tels quels. `st.tabs` BORNE un
    # écran — c'est écrit dans `first-screen-ceilings.json` — donc tout aplatir
    # aurait fait passer cette vue de 8 figures de premier écran à quatorze. Le
    # remplacement n'est pas l'onglet, c'est le DÉPLIANT.
    #
    # R568 — the banner, the exact table and « Une audience saturée ? » left; the spend
    # Pareto came out of its fold. On screen, in order: the ranking, the spend Pareto,
    # the best settings, the timeline of one creative — four figures.
    st.subheader(t("meta_creatives.section_ranking", "🏁 Le classement de tes créatives"))
    _render_ranking(df, pair)

    st.markdown("---")
    st.subheader(t("meta_creatives.section_pareto", "💶 Où est passé l'argent"))
    _render_spend_pareto(db, artist_id, bar, df)

    st.markdown("---")
    st.subheader(t("meta_creatives.section_best", "🧪 Tes meilleurs réglages"))
    _render_best_settings(db, artist_id, bar, df)
    # R569 — the hooks fold left: the « Accroche » panel above draws hook × CPR, and its
    # hover carries the spend each hook was judged on (« Sans hook » included).

    _tab_creative_timeline(selected_campaign, _acct_ma, _acct_params, bar.window)
