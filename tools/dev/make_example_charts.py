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
* **one dual axis at most, and only in `meta_x_s4a`** (R438, 2026-10-07): counts on
  the left, euros on the right, both from zero. It was two stacked panels until the
  owner read them as incomprehensible;
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
# Repris de `platform_chart._PALETTE_LIGHT` le 2026-09-12 : les couleurs suivent
# désormais les familles de marque (Spotify vert, YouTube rouge, SoundCloud
# orange, Apple magenta). Les noms restent positionnels — c'est la 1ʳᵉ, la 2ᵉ,
# la 3ᵉ et la 4ᵉ série — parce que ce fichier ne connaît pas les plateformes.
BLUE, ORANGE, AQUA, YELLOW = "#3acf84", "#bd354b", "#e0631b", "#bd00a4"
# Shazam et Hypeddit : hors de la pile des quatre plateformes, donc hors de ses
# quatre teintes — un bleu et un violet que rien d'autre ne porte sur ces figures.
SHAZAM, HYPEDDIT = "#0a84ff", "#6b4fd8"

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


# Largeur des vignettes, en pixels RÉELS. Affichées à la moitié (180 px) dans
# l'e-mail, donc nettes sur un écran à densité double sans peser comme la figure
# pleine taille.
_THUMB_WIDTH = 360


def _thumbnail(path: Path) -> Path | None:
    """Une vignette à côté de la figure, ou None si Pillow n'est pas là.

    Le mot de bienvenue montre les trois promesses côte à côte (demandé le
    2026-09-04) et un e-mail se juge aussi au poids : trois figures pleines font
    ~240 Ko, trois vignettes ~40. L'objection écrite dans `verification_email.py` —
    « une image, pas trois, le poids pèse sur la délivrabilité » — reste vraie ; ce
    sont les images qui changent, pas le raisonnement.

    Absente, elle ne casse rien : `_welcome_images` retombe sur la figure pleine.
    """
    try:
        from PIL import Image
    except ImportError:
        print("⚠️  Pillow absent — pas de vignette (l'e-mail utilisera la figure entière)")
        return None
    with Image.open(path) as im:
        ratio = _THUMB_WIDTH / im.width
        small = im.convert("RGB").resize(
            (_THUMB_WIDTH, max(1, round(im.height * ratio))), Image.LANCZOS)
        out = path.with_name(path.stem + "-thumb.png")
        small.save(out, optimize=True)
    print(f"   ↳ {out.name}  ({out.stat().st_size // 1024} Ko)")
    return out


def _save(fig, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    fig.savefig(path, dpi=144, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"✅ {path.relative_to(ROOT)}  ({path.stat().st_size // 1024} Ko)")
    _thumbnail(path)
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

    # Shazam (R437/R438, 2026-10-07 : « intègre-moi uniquement le nombre de
    # Shazam »). Pas une 5ᵉ bande de la pile : un Shazam n'est pas une écoute, et
    # l'empiler gonflerait le total « écoutes » qui titre la figure. À l'échelle
    # des écoutes (~8 000/j) une courbe de ~40/j serait un trait plat : il a donc
    # sa propre bande, fine, sous la pile, sur le MÊME axe du temps.
    shazam = np.clip(18 + days * 0.42 + rng.normal(0, 4, 90).cumsum() * 0.35, 4, None)

    fig, (ax, axs) = plt.subplots(
        2, 1, figsize=(9, 4.38), sharex=True,
        gridspec_kw={"height_ratios": [4.2, 1], "hspace": 0.12})
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
    n_shazam = int(shazam.sum())
    ax.text(0, 1.035, f"{total:,}".replace(",", " ") + " écoutes et "
            + f"{n_shazam:,}".replace(",", " ") + " Shazams sur 90 jours",
            transform=ax.transAxes, fontsize=10, color=INK_MUTED)
    ax.set_xlim(0, days[-1])

    axs.bar(days, shazam, color=SHAZAM, width=0.8)
    _frame(axs)
    axs.set_ylim(0, shazam.max() * 1.25)
    axs.yaxis.set_major_locator(plt.MaxNLocator(2))
    _series_tag(axs, 1.02, 0.5, "Shazam / jour", SHAZAM)
    axs.set_xlabel("jours", fontsize=9)
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
    """Dépense Meta, visites et clics Hypeddit, CPR et écoutes — UN graphique.

    Deux panneaux jusqu'au 2026-10-07, pour ne jamais poser deux échelles sur un
    même tracé. Le propriétaire les a lus comme « incompréhensibles » (R438) : la
    figure passe sur un seul graphique, avec UN axe secondaire en euros, et le
    risque que la règle visait est tenu autrement — les deux axes partent de zéro,
    la dépense est en barres pâles derrière, et l'axe € est nommé. Même arbitrage
    que la figure live de R436.
    """
    rng = np.random.default_rng(7)
    days = np.arange(45)
    spend = np.zeros(45)
    spend[8:26] = np.linspace(18, 46, 18) + rng.normal(0, 3, 18)
    # La campagne pousse les écoutes JUSTE SOUS le seuil, puis elles se tassent sans
    # s'effondrer : c'est l'histoire que la figure doit raconter, parce que c'est
    # celle où la question « faut-il remettre 50 € ? » se pose vraiment.
    streams = 260 + rng.normal(0, 14, 45).cumsum() * 0.30
    streams[11:] += np.concatenate([np.linspace(0, 620, 20),
                                    np.linspace(620, 560, 14)])

    # Le seuil de déclenchement, la probabilité, et la projection. Demandé le
    # 2026-09-04 : « sur graph meta spotify, ajouter un seuil de trigger des algos
    # spotify avec % de chance de trigger et prédiction en pointillés ».
    #
    # C'est la figure où les deux moitiés du produit se rencontrent — la dépense d'un
    # côté, ce que les algorithmes en font de l'autre — et elle ne montrait que la
    # première. Trois marques, trois rôles distincts, et aucune ne doit ressembler à
    # une mesure :
    #   * le SEUIL est une ligne horizontale : un niveau, pas une série ;
    #   * la PROJECTION est pointillée et part du dernier point observé, ce qui est
    #     la convention qui distingue « mesuré » de « calculé » sans légende ;
    #   * le POURCENTAGE est écrit, pas dessiné. Une probabilité rendue en hauteur de
    #     barre se lit comme un volume — le dépôt a déjà corrigé exactement ça sur
    #     les paniers de `threshold_tables.json` (2026-08-24).
    trigger_level = 980.0
    horizon = 14
    future = np.arange(days[-1], days[-1] + horizon + 1)
    # La projection part du dernier point OBSERVÉ — elle ne peut pas commencer
    # ailleurs sans dessiner une marche que rien ne justifie — et s'infléchit vers le
    # seuil sans le dépasser franchement. Une droite qui monte à l'infini
    # promettrait ce qu'aucun modèle ne dit ; une projection qui DESCEND sous le
    # seuil pendant qu'on annonce 78 % de déclenchement dit le contraire du texte
    # qu'elle porte, et c'est ce que la première version faisait.
    reach = (future - days[-1]) / horizon
    forecast = streams[-1] + (trigger_level * 1.04 - streams[-1]) * reach ** 0.8

    # Hypeddit : la page de pré-sauvegarde que la pub vise. Visites, puis clics
    # (pré-saves) — ce que l'euro achète AVANT de devenir une écoute.
    camp = (days >= 8) & (days < 26)
    visits = np.where(camp, spend * 6.2 + rng.normal(0, 10, 45), 8 + rng.normal(0, 2, 45))
    visits = np.clip(visits, 0, None)
    clicks = np.clip(visits * 0.42 + rng.normal(0, 3, 45), 0, None)
    cpr = spend[camp].sum() / clicks[camp].sum()

    # UN SEUL graphique (R438, 2026-10-07 : « tout me mettre sur un seul
    # graphique, parce que là il y en a deux, c'est un peu incompréhensible »).
    # Deux unités seulement : des COMPTES par jour à gauche (écoutes, visites,
    # clics), des EUROS à droite (la dépense, en barres pâles DERRIÈRE). Les deux
    # axes partent de ZÉRO — le seul réglage qui empêche d'inventer une corrélation
    # en choisissant où épingler une échelle. Le CPR est un RATIO : il est ÉCRIT,
    # pas tracé, comme la probabilité.
    fig, ax = plt.subplots(figsize=(9, 4.06))
    axe = ax.twinx()
    ax.set_zorder(axe.get_zorder() + 1)
    ax.patch.set_visible(False)

    axe.bar(days, spend, color=ORANGE, width=0.75, alpha=0.28, linewidth=0)
    axe.set_ylim(0, spend.max() * 2.6)
    axe.set_ylabel("€ Meta / jour", fontsize=9, color=INK_MUTED)
    for side in ("top", "left", "bottom"):
        axe.spines[side].set_visible(False)
    axe.spines["right"].set_visible(False)
    axe.tick_params(length=0, labelsize=8.5, colors=INK_MUTED)
    axe.grid(False)

    ax.plot(days, streams, color=BLUE, linewidth=2.2)
    ax.plot(future, forecast, color=BLUE, linewidth=1.6, linestyle=(0, (3, 3)))
    ax.fill_between(future, forecast * 0.86, forecast * 1.14,
                    color=BLUE, alpha=0.10, linewidth=0)
    ax.plot(days, visits, color=HYPEDDIT, linewidth=1.6)
    ax.plot(days, clicks, color=HYPEDDIT, linewidth=1.4, linestyle=(0, (1, 1.6)))

    ax.axhline(trigger_level, color=INK_MUTED, linewidth=1, linestyle=(0, (5, 4)))
    ax.text(0.015, trigger_level, "seuil de déclenchement Discover Weekly",
            transform=ax.get_yaxis_transform(), fontsize=9, color=INK_MUTED,
            va="bottom", ha="left")
    _frame(ax)
    ax.set_ylim(0, trigger_level * 1.32)
    ax.set_ylabel("par jour", fontsize=9)
    ax.set_xlabel("jours", fontsize=9)
    ax.set_xlim(0, future[-1])
    axe.set_xlim(0, future[-1])
    ax.axvline(days[-1], color=GRID, linewidth=1)

    # Étiquettes directes, au bout de chaque série, plutôt qu'une légende.
    _series_tag(ax, 0.02, 0.50, "Spotify (écoutes)", BLUE)
    # Les trois séries de la campagne : nommées dans le creux d'APRÈS la campagne,
    # le seul endroit du tracé où rien ne passe.
    _series_tag(ax, 0.47, 0.25, "Meta Ads (€, axe de droite)", ORANGE)
    _series_tag(ax, 0.47, 0.165, "Hypeddit — visites", HYPEDDIT)
    _series_tag(ax, 0.47, 0.08, "Hypeddit — clics (pointillés)", HYPEDDIT)

    ax.text(17, trigger_level * 1.2,
            f"CPR {cpr:.2f} € par clic".replace(".", ","),
            fontsize=10, color=INK, fontweight="600", ha="center")
    ax.annotate("78 % de chances\nde déclencher\nd'ici 14 jours",
                xy=(future[-3], forecast[-3]),
                xytext=(days[-1] - 13, trigger_level * 0.5),
                fontsize=10, color=INK, fontweight="600", ha="left",
                arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=1),
                annotation_clip=False)

    ax.set_title("Quel euro de pub a produit quelles écoutes",
                 fontsize=14, fontweight="700", color=INK, loc="left", pad=26)
    ax.text(0, 1.035,
            "Barres : la dépense Meta · à droite du trait, la projection",
            transform=ax.transAxes, fontsize=10, color=INK_MUTED)
    _example_badge(fig)
    return _save(fig, "meta-x-s4a.png")


def main() -> int:
    dashboard_global()
    discover_weekly_prediction()
    meta_x_s4a()
    return 0


if __name__ == "__main__":
    sys.exit(main())
