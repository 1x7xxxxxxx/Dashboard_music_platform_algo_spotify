#!/usr/bin/env python3
"""Build the example charts shown before an artist has any data of their own.

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

Every number below is synthetic. Until R480 each image carried « Exemple — données
fictives » drawn into its pixels, and the caption repeated it. The owner removed both
(2026-10-09, W3 : « retirer "(exemple données fictives…)" ») : these figures are only
ever shown on the welcome step and the algo preview, whose sentence beside them already
presents them as what the tool WILL show, never as the tenant's numbers.

Design rules applied (from the `dataviz` skill, validated not eyeballed)
-----------------------------------------------------------------------
* palette = slots 1-4 of the reference categorical theme, run through
  `validate_palette.js` on the light surface: all checks PASS, worst adjacent CVD
  ΔE 9.1, normal-vision ΔE 22.9. The contrast WARN on aqua/yellow obliges the
  **relief rule** — hence a visible direct label on every series, always;
* **one dual axis at most, and only in `meta_x_s4a`** (R438, 2026-10-07) and in the
  Meta band of `dashboard_global` for the CPR (R515): both from zero. In `meta_x_s4a`,
  counts on the left, euros on the right. It was two stacked panels until the
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
# Meta Ads : la DÉPENSE. Rouge depuis R480 (W3), bleu marine depuis R533 (2026-10-12 :
# le rouge est déjà celui de YouTube, deux séries d'une même figure ne partagent pas une
# teinte). Jamais empilée avec des écoutes — des euros n'ont pas la même unité.
META = "#1e3a8a"
_LISTEN_SOURCES = ("Spotify", "YouTube", "SoundCloud", "Instagram")

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


def _n(v: int) -> str:
    """12345 → « 12 345 »."""
    return f"{v:,}".replace(",", " ")


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
    """Toutes les sources sur un seul écran — 6 bandes empilées, et la dépense Meta dessous.

    R455 (2026-10-07, C1) : Shazam devient la 5ᵉ bande. R480 (2026-10-09, W3) :
    « ajouter Hypeddit (clics) et budget Meta Ads en € — faire comprendre qu'on aura
    tout, pas forcément réaliste ». Hypeddit est un COMPTE par jour, il entre dans la
    pile comme 6ᵉ bande ; Meta est en EUROS, une autre unité : il ne s'empile pas sur
    des écoutes, il a sa bande à lui, sous la pile, sur le même axe des jours. Le
    sous-titre compte écoutes, Shazams, clics et euros séparément — la hauteur de la
    pile n'est jamais écrite comme un nombre d'écoutes.
    """
    rng = np.random.default_rng(20260904)
    days = np.arange(90)
    base = {
        "Spotify":    900 + days * 26 + rng.normal(0, 90, 90).cumsum() * 0.5,
        "YouTube":    420 + days * 11 + rng.normal(0, 60, 90).cumsum() * 0.4,
        "SoundCloud": 260 + days * 5 + rng.normal(0, 40, 90).cumsum() * 0.3,
        "Instagram":  180 + days * 4 + rng.normal(0, 30, 90).cumsum() * 0.25,
        "Shazam":     110 + days * 3 + rng.normal(0, 20, 90).cumsum() * 0.2,
        "Hypeddit (clics)": 90 + days * 2 + rng.normal(0, 15, 90).cumsum() * 0.2,
    }
    series = {k: np.clip(v, 40, None) for k, v in base.items()}
    colours = [BLUE, ORANGE, AQUA, YELLOW, SHAZAM, HYPEDDIT]
    spend = np.clip(12 + 18 * np.sin(days / 9) ** 2 + rng.normal(0, 3, 90), 0, None)

    fig, (ax, axm) = plt.subplots(2, 1, figsize=(9, 4.77), sharex=True,
                                  gridspec_kw={"height_ratios": [4, 1], "hspace": 0.12})
    ax.stackplot(days, *series.values(), colors=colours,
                 # 2 px surface gap between stacked fills — the segments must not
                 # touch, or two adjacent hues read as one shape.
                 edgecolor=SURFACE, linewidth=1.6)
    _frame(ax)

    # Direct labels at the right end: required by the relief rule (aqua and yellow
    # sit under 3:1 on this surface) AND better than a legend box for 6 series.
    tops = np.cumsum([s[-1] for s in series.values()])
    ymax = tops[-1]
    prev = 0.0
    for (name, colour, top) in zip(series, colours, tops):
        _series_tag(ax, 1.02, ((prev + top) / 2) / ymax, name, colour)
        prev = top

    axm.bar(days, spend, color=META, width=0.8, linewidth=0)
    _frame(axm)
    axm.set_ylim(0, spend.max() * 1.15)
    axm.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:.0f} €"))
    axm.yaxis.set_major_locator(plt.MaxNLocator(2))
    _series_tag(axm, 1.02, 0.72, "Meta Ads (€)", META)
    # R515 (X3 II) : le CPR, sur SON axe à droite de la bande Meta — un ratio en €
    # par clic, jamais sur l'axe des dépenses. R533 (2026-10-12) : il DESCEND, « nos
    # performances de CPR s'optimisent de jour en jour » — 0,32 → ~0,16 € sur 90 jours.
    cpr = (0.32 - 0.16 * (days / days[-1]) ** 0.7 + 0.006 * np.sin(days / 5)
           + rng.normal(0, 0.003, 90))
    axc = axm.twinx()
    axc.plot(days, cpr, color=INK, linewidth=1.3)
    axc.set_ylim(0, 0.36)   # from zero, like every dual axis here
    # No tick labels: they would sit on the series tags. The scale is in the tag.
    axc.set_yticks([])
    for side in ("top", "left", "bottom", "right"):
        axc.spines[side].set_visible(False)
    axc.tick_params(length=0, labelsize=8, colors=INK_MUTED)
    axc.grid(False)
    # The numbers live in the subtitle: a long tag here widens the PNG and breaks the
    # equal heights of the three welcome columns.
    _series_tag(axm, 1.02, 0.22, "CPR (€ par clic) ↘", INK)

    listens = int(sum(s.sum() for k, s in series.items() if k in _LISTEN_SOURCES))
    n_shazam = int(series["Shazam"].sum())
    n_clicks = int(series["Hypeddit (clics)"].sum())
    ax.set_title("Toutes tes données, un seul écran", fontsize=14,
                 fontweight="700", color=INK, loc="left", pad=18)
    ax.text(0, 1.035, f"{_n(listens)} écoutes · {_n(n_shazam)} Shazams · "
            f"{_n(n_clicks)} clics Hypeddit · {_n(int(spend.sum()))} € Meta · "
            f"CPR {cpr[:7].mean():.2f} → {cpr[-7:].mean():.2f} € en 90 jours".replace(".", ","),
            transform=ax.transAxes, fontsize=10, color=INK_MUTED)
    ax.set_xlim(0, days[-1])
    ax.set_ylim(0, ymax * 1.04)
    axm.set_xlabel("jours", fontsize=9)
    return _save(fig, "dashboard-global.png")


def discover_weekly_prediction() -> Path:
    """Trois probabilités de déclenchement — Release Radar, DW, Radio — mesurées puis prévues.

    R455 (2026-10-07, C2) : trois courbes de probabilité. R480 (2026-10-09, W3) : le
    palier 100 % par playlist, une ligne — la marque d'un NIVEAU, pas d'une série.
    R515 (2026-10-11, X3 II) : à gauche du trait « aujourd'hui », ce qui a été MESURÉ
    (plein) ; à droite, la prévision (pointillé, avec sa zone d'incertitude). Release
    Radar a touché le palier — un point plein — puis redescend à la sortie de sa fenêtre.
    R533 (2026-10-12) : Discover Weekly et Radio ont chacune une DATE prévue — la courbe
    s'arrête au palier, un point creux le marque, « prévu J+n » le nomme.
    """
    past = np.linspace(-21, 0, 85)
    ahead = np.linspace(0, 56, 225)   # fine grid: a steep start must stay a curve
    span = np.concatenate([past, ahead[1:]])

    def _rr(x: np.ndarray) -> np.ndarray:
        rise = 100 * (0.10 + 0.95 * np.clip((x + 21) / 15, 0, 1) ** 0.8)
        fall = np.where(x > 9, 100 * np.exp(-((x - 9) / 11) ** 2), 100)
        return np.minimum(np.minimum(rise, 100), fall)

    def _climb(x: np.ndarray, start: float, hit_day: float, power: float) -> np.ndarray:
        """From `start` % at J-21 to the 100 % floor exactly at `hit_day`."""
        u = np.clip((x + 21) / (hit_day + 21), 0, 1)
        return 100 * (start + (1 - start) * u ** power)

    curves = {   # nom: (courbe sur toute la période, couleur)
        "Release Radar":   (_rr(span), BLUE),
        "Discover Weekly": (_climb(span, 0.06, 20, 1.6), AQUA),
        "Radio":           (_climb(span, 0.04, 44, 2.2), YELLOW),
    }
    cut = len(past)
    fig, ax = plt.subplots(figsize=(9, 5.38))
    ax.axhline(100, color=INK_MUTED, linewidth=1, linestyle=(0, (5, 4)))
    ax.text(-20, 97, "palier 100 % = déclenchée", fontsize=9,
            color=INK_MUTED, va="top", ha="left")
    ax.axvline(0, color=GRID, linewidth=1.2)
    ax.text(0.5, 4, "aujourd'hui", fontsize=9, color=INK_MUTED, ha="left")
    ax.text(-0.5, 4, "mesuré", fontsize=9, color=INK_MUTED, ha="right")
    for name, (p, colour) in curves.items():
        ax.plot(span[:cut], p[:cut], color=colour, linewidth=2.2)
        fut = p[cut - 1:]
        triggered = bool((p[:cut] >= 100).any())
        reached = fut >= 100 - 1e-9
        # A forecast that reaches the floor stops there: past it, it would only draw
        # a flat line over the floor and hide it. A playlist already triggered keeps
        # its whole forecast — that is where it leaves its window.
        end = len(ahead) if triggered or not reached.any() else int(np.argmax(reached)) + 1
        x, y = ahead[:end], fut[:end]
        ax.plot(x, y, color=colour, linewidth=2.2, linestyle=(0, (4, 2.5)))
        spread = 9 * x / ahead[-1]
        ax.fill_between(x, np.clip(y - spread, 0, 100), np.clip(y + spread, 0, 100),
                        color=colour, alpha=0.10, linewidth=0)
        if triggered:                       # triggered in the measured part
            hit = int(np.argmax(p >= 100))
            ax.plot([span[hit]], [100], marker="o", markersize=9, color=colour, clip_on=False)
            tag = f"{name}  déclenché ✓ → {fut[-1]:.0f} %"
            ax.annotate(tag, xy=(ahead[-1], fut[-1]), xytext=(ahead[-1] + 0.8, fut[-1]),
                        va="center", fontsize=10, color=INK, fontweight="600",
                        annotation_clip=False)
            ax.plot([ahead[-1] + 0.35], [fut[-1]], marker="s", markersize=7, color=colour,
                    clip_on=False)
        elif end < len(ahead):              # the forecast reaches the floor: a date
            day = x[-1]
            ax.plot([day], [100], marker="o", markersize=10, markerfacecolor=SURFACE,
                    markeredgecolor=colour, markeredgewidth=2.4, clip_on=False)
            ax.annotate(f"{name}\nprévu J+{day:.0f}", xy=(day, 100),
                        xytext=(day + 1.6, 92), va="top", ha="left", fontsize=10,
                        color=INK, fontweight="600")
    _frame(ax)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:.0f} %"))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"J{v:+.0f}".replace("J+0", "J0")))
    ax.set_ylim(0, 100)
    ax.set_xlim(span[0], ahead[-1])
    ax.set_xlabel("jours (avant et après aujourd'hui)", fontsize=9)
    ax.set_title("Tes chances d'entrer dans les playlists algorithmiques",
                 fontsize=14, fontweight="700", color=INK, loc="left", pad=26)
    ax.text(0, 1.035, "Trait plein : mesuré · pointillé : prévu, la zone claire est "
            "l'incertitude · ○ date prévue",
            transform=ax.transAxes, fontsize=10, color=INK_MUTED)
    return _save(fig, "prediction-discover-weekly.png")


# Les fenêtres du modèle (`trigger_algo/_common/_verdict.py`, `_PHASES`) : Release
# Radar 0-35 j, Discover Weekly 35-90 j, Radio après 90 j. Les conseils de la figure de
# campagne se placent sur ces bornes ; un test vérifie qu'elles restent celles du modèle.
DW_WINDOW = (35, 90)


def meta_x_s4a() -> Path:
    """La campagne au lancement, puis Discover Weekly et Radio — UN graphique.

    R438 : un seul graphique, un axe € à droite, les deux axes depuis zéro.
    R480 (2026-10-09, W3) : Meta € en rouge, CPR, Hypeddit clics, streams Spotify avec
    prédiction et déclenchement des algos. Le CPR est un RATIO : il est écrit, pas tracé.
    R515 (2026-10-11, X3 II) : les barres hachurées « conseillé » sont retirées. À leur
    place, deux conseils posés sur les fenêtres du modèle (`DW_WINDOW`) : « couper à
    l'entrée en Discover Weekly » (le jour où DW déclenche, dans 35-90 j) et
    « relancer avant la fenêtre Radio » (avant 90 j, dans la prévision).
    """
    rng = np.random.default_rng(7)
    today, horizon = 62, 50
    days = np.arange(today + 1)
    dw_day, radio_day = 42, 96         # DW dans sa fenêtre, Radio juste après 90 j
    relaunch = DW_WINDOW[1] - 10
    assert DW_WINDOW[0] <= dw_day < DW_WINDOW[1] <= radio_day
    spend = np.zeros(len(days))
    spend[:dw_day] = np.linspace(38, 24, dw_day) + rng.normal(0, 3, dw_day)
    camp = spend > 0
    clicks = np.clip(np.where(camp, spend * 4.5, 4) + rng.normal(0, 4, len(days)), 0, None)
    cpr = spend[camp].sum() / clicks[camp].sum()

    def _peak(x: np.ndarray, day: int, height: float, settle: float) -> np.ndarray:
        d = x - day
        return np.where(d < 0, 0, height * np.exp(-d / 3.0) + settle * (1 - np.exp(-d / 2.0)))

    streams = (180 + 420 * (1 - np.exp(-days / 4.0)) * np.where(camp, 1, 0.82)
               + _peak(days, dw_day, 900, 380) + rng.normal(0, 18, len(days)))
    streams = np.clip(streams, 0, None)
    future = np.arange(today, today + horizon + 1)
    forecast = (streams[-1] * (1 + 0.15 * (future - today) / horizon)
                + _peak(future, radio_day, 700, 320))

    fig, ax = plt.subplots(figsize=(9, 3.82))
    axe = ax.twinx()
    ax.set_zorder(axe.get_zorder() + 1)
    ax.patch.set_visible(False)
    axe.bar(days, spend, color=META, width=0.75, alpha=0.55, linewidth=0)
    axe.set_ylim(0, spend.max() * 2.4)
    axe.set_ylabel("€ Meta / jour", fontsize=9, color=INK_MUTED)
    for side in ("top", "left", "bottom", "right"):
        axe.spines[side].set_visible(False)
    axe.tick_params(length=0, labelsize=8.5, colors=INK_MUTED)
    axe.grid(False)

    ax.plot(days, streams, color=BLUE, linewidth=2.2)
    ax.plot(future, forecast, color=BLUE, linewidth=1.6, linestyle=(0, (3, 3)))
    ax.fill_between(future, forecast * 0.86, forecast * 1.14,
                    color=BLUE, alpha=0.10, linewidth=0)
    ax.plot(days, clicks, color=HYPEDDIT, linewidth=1.6)
    _frame(ax)
    top = max(streams.max(), (forecast * 1.14).max())
    ax.set_ylim(0, top * 1.3)
    ax.set_ylabel("par jour", fontsize=9)
    ax.set_xlabel("jours depuis la sortie", fontsize=9)
    ax.set_xlim(0, future[-1])
    axe.set_xlim(0, future[-1])
    ax.axvline(today, color=GRID, linewidth=1)
    for edge in DW_WINDOW:
        ax.axvline(edge, color=INK_MUTED, linewidth=0.8, linestyle=(0, (2, 3)))
    ax.text(DW_WINDOW[0] + 1, top * 1.24, "fenêtre Discover Weekly →",
            fontsize=8.5, color=INK_MUTED, ha="left", va="center")
    ax.text(radio_day + 2, forecast[radio_day - today] * 1.16, "Radio (prévu)",
            fontsize=9, color=INK_MUTED, ha="left")

    advice = ((dw_day, streams[dw_day + 1], "couper à l'entrée\nen Discover Weekly"),
              (relaunch, forecast[relaunch - today], "relancer avant\nla fenêtre Radio"))
    for day, y, text in advice:
        ax.annotate(text, xy=(day, y), xytext=(day - 9, y + top * 0.14),
                    fontsize=9.5, color=INK, fontweight="600", ha="center",
                    arrowprops=dict(arrowstyle="->", color=INK_MUTED, linewidth=1))

    _series_tag(ax, 0.02, 0.93, "Spotify (écoutes)", BLUE)
    _series_tag(ax, 0.02, 0.84, "Meta Ads (€, à droite)", META)
    _series_tag(ax, 0.02, 0.75, "Hypeddit (clics)", HYPEDDIT)
    ax.text(0.14, 0.53, f"CPR {cpr:.2f} € par clic".replace(".", ","),
            transform=ax.transAxes, fontsize=10, color=INK, fontweight="600", ha="center")

    ax.set_title("Optimiser ton budget Meta Ads pour maximiser tes streams",
                 fontsize=14, fontweight="700", color=INK, loc="left", pad=26)
    ax.text(0, 1.035,
            "La campagne au lancement, puis les algorithmes — à droite du trait, la prévision",
            transform=ax.transAxes, fontsize=10, color=INK_MUTED)
    return _save(fig, "meta-x-s4a.png")


def meta_x_algo() -> Path:
    """Le budget Meta ET les chances de déclencher DW et Radio — une proposition, jour par jour.

    R533 (2026-10-12, retour vocal) : « une 4ᵉ figure qui fusionne les chances de
    déclenchement et le budget Meta … j'ai besoin d'une proposition ». Les barres sont
    le budget : plein = dépensé, clair = conseillé. Les courbes sont les chances, sur
    l'axe de gauche, avec en fin trait la même courbe SANS pub — l'écart est ce que le
    budget achète. Les dates prévues suivent `discover_weekly_prediction` : un point
    plein quand c'est mesuré, un point creux quand c'est prévu.
    """
    rng = np.random.default_rng(533)
    today, end = 62, 120
    days = np.arange(end + 1)
    dw_day, radio_day = 42, 96
    relaunch = (radio_day - 18, radio_day - 2)          # avant la fenêtre Radio
    assert DW_WINDOW[0] <= dw_day < DW_WINDOW[1] <= radio_day
    spend = np.zeros(len(days))
    spend[:dw_day] = np.clip(np.linspace(36, 22, dw_day) + rng.normal(0, 3, dw_day), 0, None)
    planned = np.zeros(len(days))
    planned[relaunch[0]:relaunch[1] + 1] = 18
    past, fut = days <= today, days >= today

    def _climb(start: float, hit: int, power: float, cap: float = 100) -> np.ndarray:
        u = np.clip(days / hit, 0, 1)
        return np.minimum(100 * (start + (1 - start) * u ** power), cap)

    fig, ax = plt.subplots(figsize=(12, 3.8))
    axe = ax.twinx()
    ax.set_zorder(axe.get_zorder() + 1)
    ax.patch.set_visible(False)
    axe.bar(days[past], spend[past], color=META, width=0.75, alpha=0.8, linewidth=0)
    axe.bar(days, planned, color=META, width=0.75, alpha=0.25, linewidth=0)
    axe.set_ylim(0, max(spend.max(), planned.max()) * 2.2)
    axe.set_ylabel("€ Meta / jour", fontsize=9, color=INK_MUTED)
    axe.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:.0f} €"))
    for side in ("top", "left", "bottom", "right"):
        axe.spines[side].set_visible(False)
    axe.tick_params(length=0, labelsize=8.5, colors=INK_MUTED)
    axe.grid(False)

    ax.axhline(100, color=INK_MUTED, linewidth=1, linestyle=(0, (5, 4)))
    ax.axvline(today, color=GRID, linewidth=1.2)
    ax.text(today + 1, 4, "aujourd'hui", fontsize=9, color=INK_MUTED, ha="left")
    series = (("Discover Weekly", _climb(0.05, dw_day, 1.5), _climb(0.05, 150, 1.5, 70), AQUA),
              ("Radio", _climb(0.03, radio_day, 2.0), _climb(0.03, 190, 2.0, 70), YELLOW))
    for name, with_ads, without, colour in series:
        hit = int(np.argmax(with_ads >= 100))
        ax.plot(days[past & (days <= hit)], with_ads[past & (days <= hit)],
                color=colour, linewidth=2.2)
        ahead = fut & (days <= hit)
        if ahead.sum() > 1:
            ax.plot(days[ahead], with_ads[ahead], color=colour, linewidth=2.2,
                    linestyle=(0, (4, 2.5)))
        ax.plot(days, without, color=colour, linewidth=1.2, alpha=0.6, linestyle=(0, (1, 2)))
        measured = hit <= today
        ax.plot([hit], [100], marker="o", markersize=9, clip_on=False,
                markerfacecolor=colour if measured else SURFACE, markeredgecolor=colour,
                markeredgewidth=2.2)
        label = f"{name}\n{'déclenché' if measured else 'prévu'} jour {hit}"
        ax.annotate(label, xy=(hit, 100), xytext=(hit + 1.5, 92), va="top", ha="left",
                    fontsize=9.5, color=INK, fontweight="600")
    ax.annotate("relancer ici", xy=(relaunch[0] + 1, 4), xytext=(relaunch[0] - 9, 22),
                fontsize=9.5, color=INK, fontweight="600", ha="center",
                arrowprops=dict(arrowstyle="->", color=INK_MUTED, linewidth=1))
    _frame(ax)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:.0f} %"))
    ax.set_ylim(0, 100)
    ax.set_xlim(0, end)
    axe.set_xlim(0, end)
    ax.set_xlabel("jours depuis la sortie", fontsize=9)

    _series_tag(ax, 1.075, 0.86, "Meta dépensé (€, à droite)", META)
    ax.plot([1.075], [0.72], marker="s", markersize=8, color=META, alpha=0.25,
            transform=ax.transAxes, clip_on=False)
    ax.text(1.089, 0.72, "Meta conseillé", transform=ax.transAxes, fontsize=10.5,
            fontweight="700", color=INK, ha="left", va="center")
    _series_tag(ax, 1.075, 0.52, "Discover Weekly (%)", AQUA)
    _series_tag(ax, 1.075, 0.38, "Radio (%)", YELLOW)
    ax.plot([1.068, 1.082], [0.20, 0.20], color=INK_MUTED, linewidth=1.2,
            linestyle=(0, (1, 2)), transform=ax.transAxes, clip_on=False)
    ax.text(1.089, 0.20, "même courbe sans pub", transform=ax.transAxes, fontsize=10,
            color=INK_MUTED, ha="left", va="center")

    ax.set_title("Ton budget Meta, jour par jour, pour déclencher Discover Weekly puis Radio",
                 fontsize=14, fontweight="700", color=INK, loc="left", pad=26)
    ax.text(0, 1.035, "Barres : budget Meta (plein = dépensé, clair = conseillé) · courbes : "
            "tes chances de déclenchement, à gauche · ○ date prévue",
            transform=ax.transAxes, fontsize=10, color=INK_MUTED)
    return _save(fig, "meta-x-algo.png")


def shap_overview() -> Path:
    """Ce qui pèse le plus sur chaque playlist, et où en est TA track — un aperçu SHAP, factice.

    R456 (2026-10-07, commentaire vocal C10) : « un aperçu des algorithmes de SHAP qui
    liste l'impact de chaque paramètre sur ce qui va déclencher en priorité Discover
    Weekly, Radio et Release Radar, avec des données factices ». Un critère par ligne,
    rangé du plus influent au moins influent ; trois barres par critère, une par
    playlist, aux couleurs de la figure de prévision. Une barre vers la gauche FREINE
    le déclenchement : le signe d'une contribution SHAP est la moitié de sa lecture.

    R487 (2026-10-09, W10) : « ajouter NOTRE track, sa position sur chaque critère avec
    un score et la dépense Meta associée ». Second panneau sur les MÊMES lignes : le score
    de la track sur 100 par critère, et la dépense Meta qui l'y a portée — « — » sur un
    critère qu'aucune publicité ne fait bouger (l'âge de la sortie).
    """
    params = (   # (critère, Release Radar, Discover Weekly, Radio, score /100, € Meta)
        ("Streams des 7 derniers jours", 0.21, 0.17, 0.12, 64, 120),
        ("Taux de sauvegarde", 0.08, 0.15, 0.10, 41, 60),
        ("Ajouts en playlist d'auditeurs", 0.05, 0.12, 0.14, 28, 45),
        ("Abonnés qui écoutent la sortie", 0.16, 0.04, 0.03, 72, 30),
        ("Taux de skip", -0.04, -0.11, -0.09, 58, None),
        ("Jours depuis la sortie", -0.12, -0.03, 0.02, 80, None),
    )
    playlists = (("Release Radar", BLUE), ("Discover Weekly", AQUA), ("Radio", YELLOW))
    order = sorted(params, key=lambda r: sum(abs(v) for v in r[1:4]))
    fig, (ax, mine) = plt.subplots(1, 2, figsize=(11, 6.72), sharey=True,
                                   gridspec_kw={"width_ratios": [2.1, 1], "wspace": 0.06})
    y = np.arange(len(order))
    h = 0.26
    for i, (name, colour) in enumerate(playlists):
        ax.barh(y + (1 - i) * h, [r[i + 1] for r in order], height=h * 0.9,
                color=colour, linewidth=0)
    ax.axvline(0, color=INK_MUTED, linewidth=1)
    _frame(ax)
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:+.0%}".replace("+0%", "0")))
    ax.set_xlabel("effet sur la chance de déclencher", fontsize=9)
    for i, (name, colour) in enumerate(playlists):
        # In the one empty corner: row « Taux de skip » only reaches left of zero.
        _series_tag(ax, 0.62, 0.475 - i * 0.06, name, colour)
    ax.set_title("Ce qui pèse le plus sur chaque playlist", fontsize=14,
                 fontweight="700", color=INK, loc="left", pad=18)

    scores = [r[4] for r in order]
    mine.barh(y, [100] * len(order), height=0.55, color=GRID, linewidth=0)
    mine.barh(y, scores, height=0.55, color=META, linewidth=0)
    for yi, r in zip(y, order):
        spend = f"{r[5]} € Meta" if r[5] is not None else "—"
        mine.text(102, yi, f"{r[4]}/100 · {spend}", va="center", ha="left",
                  fontsize=9.5, color=INK)
    _frame(mine)
    mine.set_xlim(0, 100)
    mine.set_xticks([0, 50, 100])
    mine.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:.0f}"))
    mine.grid(axis="y", visible=False)
    mine.tick_params(axis="y", left=False, labelleft=False)
    # After BOTH `_frame` calls: each puts a thousands formatter on the SHARED y axis,
    # which would print the row indexes instead of the criteria.
    ax.set_yticks(y, [r[0] for r in order], fontsize=10, color=INK)
    ax.yaxis.set_major_formatter(plt.FixedFormatter([r[0] for r in order]))
    mine.set_xlabel("score de ta track", fontsize=9)
    mine.set_title("Ta track", fontsize=14, fontweight="700", color=INK, loc="left", pad=18)
    return _save(fig, "shap-overview.png")


def main() -> int:
    dashboard_global()
    discover_weekly_prediction()
    meta_x_s4a()
    meta_x_algo()
    shap_overview()
    return 0

if __name__ == "__main__":
    sys.exit(main())
