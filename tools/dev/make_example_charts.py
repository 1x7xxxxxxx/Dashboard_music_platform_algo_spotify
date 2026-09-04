#!/usr/bin/env python3
"""Build the three example charts shown before an artist has any data of their own.

Type: Utility
Uses: matplotlib (kaleido is absent everywhere — Plotly cannot export a PNG here)
Triggers: `make example-charts`, by hand, when the visual language changes
Depends on: nothing at runtime
Persists in: src/dashboard/assets/examples/*.png

Why PNGs built once, and not charts rendered live
-------------------------------------------------
The welcome step is shown to an account that has **no data at all**, so there is
nothing to plot from. Whatever is displayed is an ILLUSTRATION, and the honest way to
ship an illustration is to build it once, look at it, and commit it:

* **it renders identically everywhere** — app, e-mail, PDF — with no runtime charting
  cost on a page whose whole job is to be quick;
* **the e-mail can carry it** without fetching anything from a third party. `kaleido`
  is absent from every image (measured 2026-09-04), so a Plotly figure could not be
  turned into a PNG at send time even if we wanted to;
* **it is reviewable**: a committed file can be looked at before it reaches anyone.

Every number below is synthetic and the figures say so, in the figure itself. The
repo has already been bitten by a demo value read as real (the public artist counter
that counted our own canaries, `tests/test_public_counters_count_humans.py`): an
example that does not announce itself is a lie with a chart around it.

Design rules applied (from the `dataviz` skill, validated not eyeballed)
-----------------------------------------------------------------------
* palette = slots 1-4 of the reference categorical theme, run through
  `validate_palette.js` on the light surface: all checks PASS, worst adjacent CVD
  ΔE 9.1, normal-vision ΔE 22.9. The contrast WARN on aqua/yellow obliges the
  **relief rule** — hence a visible direct label on every series, always;
* **never a dual axis**: spend and streams are two stacked panels sharing one x, not
  two y-scales on one plot. That is the single most common chart mistake and the one
  this pair invites;
* text wears text tokens (ink), never the series colour; grid recessive; thin marks;
  2 px surface gap between stacked fills.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                        # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "src" / "dashboard" / "assets" / "examples"

# ── Design tokens ────────────────────────────────────────────────────────────
SURFACE = "#fcfcfb"
INK = "#1a1a19"
INK_MUTED = "#6b6b68"
GRID = "#e6e6e3"
# Categorical slots 1-4 (light). Order is fixed and never cycled.
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 10,
    "text.color": INK, "axes.labelcolor": INK_MUTED,
    "xtick.color": INK_MUTED, "ytick.color": INK_MUTED,
    "axes.edgecolor": GRID, "axes.linewidth": 0.8,
    "grid.color": GRID, "grid.linewidth": 0.8,
})


def _thousands(v, _pos):
    """1 200 → « 1,2k ». Sans la décimale sous 10k, 1 200 / 1 400 / 1 600 rendaient
    TROIS graduations « 1k » à trois hauteurs différentes — un axe qui se contredit."""
    if v >= 10000:
        return f"{v/1000:.0f}k"
    if v >= 1000:
        return f"{v/1000:.1f}".replace(".", ",") + "k"
    return f"{v:.0f}"


def _frame(ax) -> None:
    """Recessive axes: no box, a horizontal grid only, ticks outward and thin."""
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.yaxis.grid(True)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    ax.yaxis.set_major_formatter(FuncFormatter(_thousands))


def _example_badge(fig) -> None:
    """Says it is an example, in the image, so it cannot be quoted out of context."""
    fig.text(0.995, 0.012,
             "Exemple — données fictives, à titre d'illustration",
             ha="right", va="bottom", fontsize=8, color=INK_MUTED)


def _series_tag(ax, x: float, y: float, label: str, colour: str,
                va: str = "center") -> None:
    """Un nom en encre + une pastille de la couleur de la série.

    Règle du skill : le TEXTE porte des jetons de texte, jamais la couleur de la
    série ; c'est une marque colorée à côté de lui qui porte l'identité. Un nom écrit
    dans la couleur perd en contraste et fait dépendre la lecture de la couleur seule.
    """
    ax.plot([x], [y], marker="s", markersize=8, color=colour,
            transform=ax.transAxes, clip_on=False)
    ax.text(x + 0.014, y, label, transform=ax.transAxes, fontsize=10.5,
            fontweight="700", color=INK, ha="left", va=va)


def _save(fig, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    fig.savefig(path, dpi=144, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"✅ {path.relative_to(ROOT)}  ({path.stat().st_size // 1024} Ko)")
    return path


def dashboard_global() -> Path:
    """Toutes les plateformes sur un seul écran — aire empilée, 4 séries."""
    rng = np.random.default_rng(20260904)
    days = np.arange(90)
    base = {
        "Spotify":    900 + days * 26 + rng.normal(0, 90, 90).cumsum() * 0.5,
        "YouTube":    420 + days * 11 + rng.normal(0, 60, 90).cumsum() * 0.4,
        "SoundCloud": 260 + days * 5 + rng.normal(0, 40, 90).cumsum() * 0.3,
        "Instagram":  180 + days * 4 + rng.normal(0, 30, 90).cumsum() * 0.25,
    }
    series = {k: np.clip(v, 40, None) for k, v in base.items()}
    colours = [BLUE, ORANGE, AQUA, YELLOW]

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.stackplot(days, *series.values(), colors=colours,
                 # 2 px surface gap between stacked fills — the segments must not
                 # touch, or two adjacent hues read as one shape.
                 edgecolor=SURFACE, linewidth=1.6)
    _frame(ax)

    # Direct labels at the right end: required by the relief rule (aqua and yellow
    # sit under 3:1 on this surface) AND better than a legend box for 4 series.
    tops = np.cumsum([s[-1] for s in series.values()])
    ymax = tops[-1]
    prev = 0.0
    for (name, colour, top) in zip(series, colours, tops):
        _series_tag(ax, 1.02, ((prev + top) / 2) / ymax, name, colour)
        prev = top

    total = int(sum(s.sum() for s in series.values()))
    ax.set_title("Toutes tes plateformes, un seul écran", fontsize=14,
                 fontweight="700", color=INK, loc="left", pad=18)
    ax.text(0, 1.035, f"{total:,}".replace(",", " ") + " écoutes sur 90 jours",
            transform=ax.transAxes, fontsize=10, color=INK_MUTED)
    ax.set_xlabel("jours", fontsize=9)
    ax.set_xlim(0, days[-1])
    _example_badge(fig)
    return _save(fig, "dashboard-global.png")


def discover_weekly_prediction() -> Path:
    """Le déclenchement prédit, puis observé — une seule série, donc pas de légende."""
    rng = np.random.default_rng(11)
    days = np.arange(60)
    trigger = 34
    streams = 320 + rng.normal(0, 25, 60).cumsum() * 0.4
    streams[trigger:] += np.linspace(0, 2600, 60 - trigger) ** 0.92
    streams = np.clip(streams, 120, None)

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(days, streams, color=BLUE, linewidth=2)
    ax.fill_between(days[:trigger + 1],
                    streams[:trigger + 1] * 0.82, streams[:trigger + 1] * 1.18,
                    color=BLUE, alpha=0.12, linewidth=0)
    _frame(ax)

    ax.axvline(trigger, color=INK_MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.annotate("Discover Weekly\ndéclenché", xy=(trigger, streams[trigger]),
                xytext=(trigger - 21, streams.max() * 0.62),
                fontsize=10, color=INK, fontweight="600",
                arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=1))
    ax.annotate(f"{int(streams[-1]):,}".replace(",", " ") + " / jour",
                xy=(days[-1], streams[-1]), xytext=(days[-1] + 1.5, streams[-1]),
                va="center", fontsize=10, color=INK, fontweight="600",
                annotation_clip=False)

    ax.set_title("Prédire le déclenchement, avant de dépenser en promo",
                 fontsize=14, fontweight="700", color=INK, loc="left", pad=18)
    ax.text(0, 1.035,
            "La zone claire est la prévision ; le trait, ce qui s'est passé",
            transform=ax.transAxes, fontsize=10, color=INK_MUTED)
    ax.set_xlabel("jours", fontsize=9)
    ax.set_xlim(0, days[-1])
    _example_badge(fig)
    return _save(fig, "prediction-discover-weekly.png")


def meta_x_s4a() -> Path:
    """Dépense et écoutes — DEUX panneaux, un axe chacun. Jamais deux échelles.

    C'est l'erreur que cette paire de mesures appelle : un axe à gauche pour les
    euros, un à droite pour les écoutes, et une corrélation qu'on croit lire parce
    que les deux courbes se croisent là où l'échelle a été choisie. Deux panneaux qui
    partagent l'axe du temps disent la même chose sans mentir.
    """
    rng = np.random.default_rng(7)
    days = np.arange(45)
    spend = np.zeros(45)
    spend[8:26] = np.linspace(18, 46, 18) + rng.normal(0, 3, 18)
    streams = 260 + rng.normal(0, 18, 45).cumsum() * 0.35
    streams[11:] += np.concatenate([np.linspace(0, 900, 20),
                                    np.linspace(900, 640, 14)])

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9, 5.0), sharex=True,
        gridspec_kw={"height_ratios": [1, 1.5], "hspace": 0.28})

    ax1.bar(days, spend, color=ORANGE, width=0.75)
    _frame(ax1)
    ax1.set_ylabel("€ dépensés / jour", fontsize=9)
    # Étiquettes DANS le panneau : hors-cadre, `bbox_inches="tight"` élargissait
    # l'image d'une bande vide où les deux noms flottaient loin de leur courbe.
    _series_tag(ax1, 0.86, 0.88, "Meta Ads", ORANGE)

    ax2.plot(days, streams, color=BLUE, linewidth=2)
    _frame(ax2)
    ax2.set_ylabel("écoutes / jour", fontsize=9)
    ax2.set_xlabel("jours", fontsize=9)
    _series_tag(ax2, 0.88, 0.12, "Spotify", BLUE)

    for ax in (ax1, ax2):
        ax.axvspan(8, 26, color=ORANGE, alpha=0.07, linewidth=0)
        ax.set_xlim(0, days[-1])

    ax1.set_title("Quel euro de pub a produit quelles écoutes",
                  fontsize=14, fontweight="700", color=INK, loc="left", pad=40)
    ax1.text(0, 1.09, "La campagne est la zone teintée — l'effet lui survit 12 jours",
             transform=ax1.transAxes, fontsize=10, color=INK_MUTED, va="bottom")
    _example_badge(fig)
    return _save(fig, "meta-x-s4a.png")


def main() -> int:
    dashboard_global()
    discover_weekly_prediction()
    meta_x_s4a()
    return 0


if __name__ == "__main__":
    sys.exit(main())
