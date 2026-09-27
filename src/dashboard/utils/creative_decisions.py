"""Which creative to cut — the decision rule of the Creatives page, pure.

Type: Utility
Uses: pandas
Triggers: views/meta_creatives.py (_render_decision_banner)
Persists in: nothing

Moved out of `views/meta_creatives.py` on 2026-09-27 (R233): the view crossed its frozen
size ceiling (`tests/test_a_file_only_gets_shorter.py`), and a decision rule that a test
calls directly (`tests/test_a_creative_name_yields_its_hook.py`) belongs outside a view.
"""
from __future__ import annotations

import pandas as pd


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

    ⚠️ Correction du 2026-09-26 : ces **0,130 €** (reproduits : 0,1296 € =
    3 006,77 € / 23 206 résultats, 55 couples créative × campagne à objectif de
    conversion, artiste 1, spotify_etl_review) ont un dénominateur DOUBLÉ — le
    collecteur comptait l'évènement sortant d'Hypeddit sous deux action_type. Le coût
    par clic sortant à la maille campagne, mesuré le même jour, est **0,2627 €**
    (Σdépense / Σcustom_conversions, 196 jours). Le chiffre à la maille créative
    n'existe qu'après la re-collecte `full_history` (migration 138) ; les 220 € /
    0,19 € / 70 € ci-dessous sont du même régime doublé et restent à re-mesurer.

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


def by_creative(df: pd.DataFrame) -> pd.DataFrame:
    """One row per creative NAME — the rows of each (creative, campaign) pair summed. Pure.

    R241 (2026-09-27, fiches 29 and 33). The page's query is at (creative, campaign) grain;
    a creative run in two campaigns (« Début » in JNPPTBFR and CATEDERPAS Remix) drew TWO
    bars on ONE label, their values printed over each other. Rates are recomputed from the
    summed counts, never averaged: CTR = 100·Σclicks/Σimpressions (`_CTR_SQL`), CPR =
    Σspend/Σresults over the rows whose goal gives a CPR at all (the SQL leaves it NULL
    otherwise — a video-view goal has no « result » to price)."""
    if df is None or df.empty or "creative_name" not in df:
        return df
    d = df.copy()
    # `reach` is people, not additive across campaigns: it is left out, never summed.
    num = ["total_spend", "total_results", "total_impressions", "total_clicks"]
    for c in [*num, "cpr"]:
        if c in d:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    priced = d["cpr"].notna() if "cpr" in d else pd.Series(False, index=d.index)
    d["_ps"] = d["total_spend"].where(priced)
    d["_pr"] = d["total_results"].where(priced)
    g = d.groupby("creative_name", sort=False)
    out = g[[c for c in num if c in d] + ["_ps", "_pr"]].sum(min_count=1).reset_index()
    for c in ("total_link_clicks", "total_outbound"):
        if c in d:     # a partial sum is not a measure: NULL as soon as one row is unmeasured
            v = pd.to_numeric(d[c], errors="coerce")
            out[c] = g[c].apply(lambda s, v=v: v.loc[s.index].sum() if v.loc[s.index].notna().all()
                                else None).values
    out["cpr"] = (out["_ps"] / out["_pr"].where(out["_pr"] > 0)).round(3)
    if {"total_clicks", "total_impressions"} <= set(out):
        out["avg_ctr"] = (100 * out["total_clicks"]
                          / out["total_impressions"].where(out["total_impressions"] > 0)).round(2)
    out["campaigns"] = g["campaign_name"].nunique().values if "campaign_name" in d else 1
    return out.drop(columns=["_ps", "_pr"])


def add_quadrants(fig, d: pd.DataFrame) -> None:
    """Median lines and the two quadrants that call for a decision (R246, fiche 32).

    Owner, 2026-09-27: « je ne comprends pas quelle décision on peut prendre ». Above the
    median spend, a creative is either CHEAP per result (push it) or EXPENSIVE (cut it);
    below the median spend there is too little money behind it to judge either way."""
    from src.dashboard.utils.i18n import t
    ms, mc = float(d['total_spend'].median()), float(d['cpr'].median())
    fig.add_vline(x=ms, line_dash="dot", line_color="rgba(120,120,120,0.6)")
    fig.add_hline(y=mc, line_dash="dot", line_color="rgba(120,120,120,0.6)")
    for text, y, colour in ((t("meta_creatives.q_push", "▶ À pousser : beaucoup dépensé, résultat pas cher"), 0.02, "#1e8b7a"),
                            (t("meta_creatives.q_cut", "✂ À couper : beaucoup dépensé, résultat cher"), 0.98, "#ce0700")):
        fig.add_annotation(xref="paper", yref="paper", x=0.99, y=y, xanchor="right",
                           yanchor="bottom" if y < 0.5 else "top", showarrow=False,
                           text=text, font=dict(size=11, color=colour))


def render_creative_gain(creative: str, gains: dict) -> None:
    """Streams gained by ONE creative, beside its funnel — or why it cannot be said (R246)."""
    import streamlit as st

    from src.dashboard.utils.i18n import t
    g = gains.get(creative)
    if not g or g.get("gained") is None or g["gained"] != g["gained"]:
        st.caption(t("meta_creatives.gain_unknown",
                     "Écoutes gagnées : non séparables — cette créa a tourné avec d'autres dans "
                     "sa campagne, ou sans titre lié confirmé. Pour la mesurer, lance-la seule."))
        return
    gained, spend = float(g["gained"]), float(g.get("spend") or 0)
    cost = f"{spend / gained:.3f} €".replace(".", ",") if gained > 0 else "—"
    st.metric(t("meta_creatives.gain_metric", "Écoutes gagnées (créa seule dans sa campagne)"),
              f"{gained:,.0f}".replace(",", " "),
              help=t("meta_creatives.gain_help",
                     "Écoutes du titre pendant la campagne au-dessus de son niveau des 28 jours "
                     "d'avant. Coût par écoute gagnée : {c}.").format(c=cost))
