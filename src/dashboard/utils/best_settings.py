"""The « meilleurs réglages » tool — every setting an artist can change, ranked by CPR (R557).

Type: Utility
Uses: pandas, plotly, src.dashboard.utils.meta_confidence, src.dashboard.utils.ratios,
      src.dashboard.utils.semantic_colors, src.dashboard.utils.i18n
Triggers: views/trigger_algo/_settings.py (`show_settings`, R598)
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

R597 (owner, 2026-10-15) — « les couleurs = les campagnes, avec leur légende ; deux
campagnes à comparer ». Given `colours`, each panel draws one bar per (value, campaign) in
the campaign's colour, named in the legend; ★ marks each campaign's value to keep.
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


def rank_by(frame: pd.DataFrame, label_col: str, by: str, spend_col: str = "spend",
            results_col: str = "results") -> pd.DataFrame:
    """`rank` once per value of `by`, stacked, the group in `campagne` (R597). Pure."""
    parts = ([rank(g, label_col, spend_col, results_col).assign(campagne=k)
              for k, g in frame.groupby(by, sort=False)]
             if frame is not None and not frame.empty and by in frame else [])
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame(columns=["valeur", "depense", "resultats", "cpr", "fiable",
                                     "campagne"])
    return pd.concat(parts, ignore_index=True)


def _order(r: pd.DataFrame) -> list[str]:
    """Values best first: reliable before thin, then the cheapest CPR any campaign got."""
    g = r.groupby("valeur").agg(fiable=("fiable", "max"), cpr=("cpr", "min"))
    return g.sort_values(["fiable", "cpr"], ascending=[False, True]).index.tolist()


def _campaign_bars(fig: go.Figure, r: pd.DataFrame, colours: dict[str, str], shown: set,
                   row: int, col: int) -> list[str]:
    """One bar per (value, campaign), the campaign's colour; ★ on each campaign's best,
    a thin value pale with ⚠️. Returns the panel's category order."""
    order = _order(r)
    for camp, colour in colours.items():
        mine = r[r["campagne"] == camp]
        if mine.empty:
            continue
        keep = (best(mine) or {}).get("valeur")
        text = [f"{c:.2f} €".replace(".", ",") + (" ★" if v == keep else "")
                + ("" if f else " ⚠️") for v, c, f in zip(mine["valeur"], mine["cpr"],
                                                         mine["fiable"])]
        fig.add_trace(go.Bar(
            x=mine["cpr"], y=mine["valeur"], orientation="h", name=camp[:30],
            legendgroup=camp, showlegend=camp not in shown, cliponaxis=False,
            marker={"color": colour, "opacity": [1.0 if f else 0.35 for f in mine["fiable"]]},
            text=text, textposition="outside",
            customdata=mine[["depense", "resultats"]].values,
            hovertemplate=_hover().replace("<extra></extra>", f"<extra>{camp[:30]}</extra>")),
            row=row, col=col)
        shown.add(camp)
    return order


def _hover() -> str:
    return t("best_settings.hover",
             "%{y}<br>CPR : %{x:.3f} €<br>Dépense : %{customdata[0]:,.0f} €"
             "<br>Clics sortants : %{customdata[1]:,.0f}<extra></extra>")


def _green_bars(fig: go.Figure, r: pd.DataFrame, row: int, col: int) -> list[str]:
    """One bar per value, the value to keep in green. Returns the panel's category order."""
    keep = (best(r) or {}).get("valeur")
    labels = [v if f else f"{v} ⚠️" for v, f in zip(r["valeur"], r["fiable"])]
    fig.add_trace(go.Bar(
        x=r["cpr"], y=labels,
        orientation="h", showlegend=False, cliponaxis=False,
        marker_color=[BON if v == keep else (ATTENTION if f else NEUTRE)
                      for v, f in zip(r["valeur"], r["fiable"])],
        text=[f"{c:.2f} €".replace(".", ",") for c in r["cpr"]], textposition="outside",
        customdata=r[["depense", "resultats"]].values, hovertemplate=_hover()),
        row=row, col=col)
    return labels


def figure(panels: list[tuple[str, pd.DataFrame]],
           colours: dict[str, str] | None = None) -> go.Figure | None:
    """One panel per criterion, CPR bars. None if all empty.

    Without `colours`: the value to keep in green. With `colours` (campaign → colour, the
    panels carrying `campagne` from `rank_by`): one bar per campaign, named in the legend."""
    drawn = [(title, r[r["cpr"].notna()]) for title, r in panels]
    drawn = [(title, r) for title, r in drawn if not r.empty]
    if not drawn:
        return None
    rows = math.ceil(len(drawn) / 2)
    fig = make_subplots(rows=rows, cols=2, subplot_titles=[p[0] for p in drawn],
                        horizontal_spacing=0.22, vertical_spacing=0.12)
    shown: set = set()
    for i, (_title, r) in enumerate(drawn):
        cell = {"row": i // 2 + 1, "col": i % 2 + 1}
        labels = (_campaign_bars(fig, r, colours, shown, **cell) if colours
                  else _green_bars(fig, r, **cell))
        # R568 — Pareto, the value to keep on top: `rank`'s order (reliable, then cheapest)
        # pinned per panel. Left to the chart door, a cheap ⚠️ value rose above the green.
        fig.update_yaxes(categoryorder="array", categoryarray=labels, **cell)
    fig.update_yaxes(autorange="reversed", automargin=True)
    fig.update_xaxes(rangemode="tozero", showticklabels=False)
    fig.update_layout(height=260 * rows + 40, margin=dict(t=40, l=10, r=40, b=20),
                      barmode="group", showlegend=bool(colours))
    return fig


def caption() -> str:
    """What a bar is, why pale, and what each panel covers."""
    return t(
        "best_settings.caption",
        "Chaque barre : le coût d'un clic sortant (CPR) pour ce réglage, **une couleur par "
        "campagne** — ★ celui à garder dans cette campagne. Pâle avec ⚠️ : moins de {dep} € "
        "ou de {res} clics sortants, trop peu pour conclure ; il ne peut pas être « le "
        "meilleur ». Pays, placement, plateforme et âge couvrent tout l'historique (Meta ne "
        "les date pas). Les centres d'intérêt n'y sont pas : Meta ne rend aucun chiffre par "
        "intérêt. Bouton et objectif : au clic sur la pub (Meta n'y rattache pas les clics "
        "sortants).").format(
        dep=int(MIN_DEPENSE), res=MIN_RESULTS)


def _named(value: str) -> str:
    """A missing value (« ? », R598) is named, not shown as a question mark."""
    return t("best_settings.unset", "non renseigné") if value in ("?", "", None) else value


def photo_figure(photo: pd.DataFrame) -> go.Figure | None:
    """The pooled photo (R598): one bar per setting — its best value's CPR, named on it,
    and how much dearer the value to avoid is. A setting without a verdict stays, grey and
    empty, saying so: an absent row would read as « nothing to change »."""
    if photo is None or photo.empty:
        return None
    known = photo["cpr"].notna()
    labels = [f"{r.parametre} : {r.meilleure}" for r in photo.itertuples()]
    text = [(t("best_settings.photo_text", "{cpr:.2f} € · {f}× moins cher que « {e} »").format(
                cpr=r.cpr, f=r.facteur, e=_named(r.eviter)) if r.facteur else f"{r.cpr:.2f} €")
            if k else "" for r, k in zip(photo.itertuples(), known)]
    fig = go.Figure(go.Bar(
        x=photo["cpr"].fillna(0.0), y=labels, orientation="h", text=text,
        textposition="outside", cliponaxis=False,
        marker_color=[BON if k else NEUTRE for k in known],
        hovertemplate="%{y}<br>%{text}<extra></extra>"))
    fig.update_yaxes(autorange="reversed", automargin=True)
    fig.update_xaxes(title=t("best_settings.photo_axis", "Coût par clic de la valeur à garder (€)"),
                     range=[0, float(photo["cpr"].max() or 1) * 2.2])
    fig.update_layout(height=80 + 38 * len(photo), showlegend=False, margin={"t": 20})
    return fig
