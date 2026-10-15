"""The « meilleurs réglages » tool — every setting an artist can change, ranked by CPR (R557).

Type: Utility
Uses: pandas, plotly, src.dashboard.utils.meta_confidence, src.dashboard.utils.ratios,
      src.dashboard.utils.semantic_colors, src.dashboard.utils.i18n
Triggers: views/meta_creatives.py (`_render_best_settings`)
Persists in: nothing

Owner's Y2 of 2026-10-13, fiches 36, 38 and 53: « un outil des meilleurs paramètres —
hook, intérêt, placement, âge, tous les critères modifiables ». The answers lived in four
places (the hook bars, the spend × CPR cloud, the settings tab of the algo page, the
breakdowns grid) and each made the artist compare by eye. Here every criterion is one
panel of ONE figure, priced the same way — € per outbound click (CPR) — and the value to
keep is green.

The discipline is the one `trigger_algo/_reglages.py` set on the settings tab: a value
under `MIN_DEPENSE` € or `MIN_RESULTS` outbound clicks is drawn grey with ⚠️ and can
never be « the best »; a criterion needs TWO reliable values for a verdict, because a
best without a measured rival is only the one thing that was tried.

Interests are not here: Meta returns no breakdown by interest, and none is collected.
"""
from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.dashboard.utils.i18n import t
from src.dashboard.utils.meta_confidence import MIN_DEPENSE
from src.dashboard.utils.ratios import per_series
from src.dashboard.utils.semantic_colors import ATTENTION, BON, NEUTRE

#: Under 20 outbound clicks a CPR moves by a third with ONE click more or less.
MIN_RESULTS = 20
#: Values drawn per panel — the most spent; the rest is under a cent of the decision.
TOP_N = 6


def rank(frame: pd.DataFrame, label_col: str, spend_col: str = "spend",
         results_col: str = "results") -> pd.DataFrame:
    """valeur, depense, resultats, cpr, fiable — reliable first, then cheapest. Pure.

    The CPR is Σspend / Σresults over the rows of a value, never a mean of CPRs."""
    cols = ["valeur", "depense", "resultats", "cpr", "fiable"]
    if frame is None or frame.empty or label_col not in frame:
        return pd.DataFrame(columns=cols)
    d = pd.DataFrame({
        "valeur": frame[label_col].fillna("?").astype(str),
        "depense": pd.to_numeric(frame[spend_col], errors="coerce").fillna(0.0),
        "resultats": pd.to_numeric(frame[results_col], errors="coerce").fillna(0.0)})
    d = d.groupby("valeur", as_index=False)[["depense", "resultats"]].sum()
    d = d[d["depense"] > 0].nlargest(TOP_N, "depense")
    d["cpr"] = per_series(d["depense"], d["resultats"])
    d["fiable"] = (d["depense"] >= MIN_DEPENSE) & (d["resultats"] >= MIN_RESULTS)
    return d.sort_values(["fiable", "cpr"], ascending=[False, True],
                         na_position="last").reset_index(drop=True)[cols]


def best(ranked: pd.DataFrame) -> dict | None:
    """The value to keep, or None under two reliable priced values."""
    ok = ranked[ranked["fiable"] & ranked["cpr"].notna()] if not ranked.empty else ranked
    if len(ok) < 2:
        return None
    top, worst = ok.iloc[0], ok.iloc[-1]
    return {"valeur": top["valeur"], "cpr": float(top["cpr"]),
            "eviter": worst["valeur"], "cpr_max": float(worst["cpr"]),
            "facteur": float(worst["cpr"]) / float(top["cpr"]) if top["cpr"] else None}


def figure(panels: list[tuple[str, pd.DataFrame]]) -> go.Figure | None:
    """One panel per criterion, CPR bars, the value to keep in green. None if all empty."""
    drawn = [(title, r[r["cpr"].notna()]) for title, r in panels]
    drawn = [(title, r) for title, r in drawn if not r.empty]
    if not drawn:
        return None
    rows = math.ceil(len(drawn) / 2)
    fig = make_subplots(rows=rows, cols=2, subplot_titles=[p[0] for p in drawn],
                        horizontal_spacing=0.22, vertical_spacing=0.12)
    for i, (_title, r) in enumerate(drawn):
        keep = (best(r) or {}).get("valeur")
        labels = [v if f else f"{v} ⚠️" for v, f in zip(r["valeur"], r["fiable"])]
        fig.add_trace(go.Bar(
            x=r["cpr"], y=labels,
            orientation="h", showlegend=False, cliponaxis=False,
            marker_color=[BON if v == keep else (ATTENTION if f else NEUTRE)
                          for v, f in zip(r["valeur"], r["fiable"])],
            text=[f"{c:.2f} €".replace(".", ",") for c in r["cpr"]], textposition="outside",
            customdata=r[["depense", "resultats"]].values,
            hovertemplate=t("best_settings.hover",
                            "%{y}<br>CPR : %{x:.3f} €<br>Dépense : %{customdata[0]:,.0f} €"
                            "<br>Clics sortants : %{customdata[1]:,.0f}<extra></extra>")),
            row=i // 2 + 1, col=i % 2 + 1)
        # R568 — Pareto, the value to keep on top: `rank`'s order (reliable, then cheapest)
        # pinned per panel. Left to the chart door, a cheap ⚠️ value rose above the green.
        fig.update_yaxes(categoryorder="array", categoryarray=labels,
                         row=i // 2 + 1, col=i % 2 + 1)
    fig.update_yaxes(autorange="reversed", automargin=True)
    fig.update_xaxes(rangemode="tozero", showticklabels=False)
    fig.update_layout(height=260 * rows + 40, margin=dict(t=40, l=10, r=40, b=20))
    return fig


def caption() -> str:
    """What a bar is, why grey, and what each panel covers."""
    return t(
        "best_settings.caption",
        "Chaque barre : le coût d'un clic sortant (CPR) pour ce réglage — **en vert, celui "
        "à garder**. ⚠️ en gris : moins de {dep} € ou de {res} clics sortants, trop peu pour "
        "conclure ; il ne peut pas être « le meilleur ». Pays, placement, plateforme et âge "
        "couvrent tout l'historique (Meta ne les date pas). Les centres d'intérêt n'y sont "
        "pas : Meta ne rend aucun chiffre par intérêt. Bouton et objectif : tous comptes, "
        "au clic sur la pub (Meta n'y rattache pas les clics sortants).").format(
        dep=int(MIN_DEPENSE), res=MIN_RESULTS)
