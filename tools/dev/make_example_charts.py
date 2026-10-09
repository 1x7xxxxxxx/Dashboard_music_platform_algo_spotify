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
# Meta Ads : la DÉPENSE, en rouge (R480, W3 « Meta € en rouge »). Jamais empilée
# avec des écoutes — des euros n'ont pas la même unité.
META = "#d93025"
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

    fig, (ax, axm) = plt.subplots(2, 1, figsize=(9, 4.62), sharex=True,
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
    _series_tag(axm, 1.02, 0.5, "Meta Ads (€)", META)

    listens = int(sum(s.sum() for k, s in series.items() if k in _LISTEN_SOURCES))
    n_shazam = int(series["Shazam"].sum())
    n_clicks = int(series["Hypeddit (clics)"].sum())
    ax.set_title("Toutes tes données, un seul écran", fontsize=14,
                 fontweight="700", color=INK, loc="left", pad=18)
    ax.text(0, 1.035, f"{_n(listens)} écoutes · {_n(n_shazam)} Shazams · "
            f"{_n(n_clicks)} clics Hypeddit · {_n(int(spend.sum()))} € Meta sur 90 jours",
            transform=ax.transAxes, fontsize=10, color=INK_MUTED)
    ax.set_xlim(0, days[-1])
    ax.set_ylim(0, ymax * 1.04)
    axm.set_xlabel("jours", fontsize=9)
    return _save(fig, "dashboard-global.png")


def discover_weekly_prediction() -> Path:
    """Trois probabilités de déclenchement — Release Radar, DW, Radio — et le palier 100 %.

    R455 (2026-10-07, C2) : trois courbes de probabilité, en prévision seule.
    R480 (2026-10-09, W3) : « identifier le palier de 100 % par playlist (RR 100 %
    atteint, DW 64 % pas encore, Radio 41 %) ». Le palier est une ligne : la marque
    d'un NIVEAU, pas d'une série. Release Radar l'atteint — un point plein à l'endroit
    où il le touche ; les deux autres finissent dessous, et leur étiquette dit ce qui
    leur manque. Tout est pointillé : rien n'y est mesuré.
    """
    ahead = np.linspace(0, 28, 113)   # fine grid: a steep start must stay a curve
    reach = ahead / ahead[-1]
    curves = {   # nom: (niveau atteint à J+28, couleur, vitesse)
        "Release Radar":   (1.00, BLUE, 0.45),
        "Discover Weekly": (0.64, AQUA, 0.9),
        "Radio":           (0.41, YELLOW, 1.4),
    }
    fig, ax = plt.subplots(figsize=(9, 4.86))
    ax.axhline(100, color=INK_MUTED, linewidth=1, linestyle=(0, (5, 4)))
    ax.text(0.4, 98, "palier 100 % : la playlist est déclenchée", fontsize=9,
            color=INK_MUTED, va="top")
    for name, (top, colour, speed) in curves.items():
        # Release Radar reaches the floor near J+19, then holds: once triggered, it is.
        if top >= 1.0:
            p = np.minimum(100, 100 * (0.08 + 0.92 * 1.19 * reach ** speed))
        else:
            p = 100 * (0.08 + (top - 0.08) * reach ** speed)
        ax.plot(ahead, p, color=colour, linewidth=2.2, linestyle=(0, (4, 2.5)))
        # Once on the floor, no more doubt: the band closes where the curve holds.
        spread = np.where(p >= 100, 0, 9 * reach)
        ax.fill_between(ahead, np.clip(p - spread, 0, 100), np.clip(p + spread, 0, 100),
                        color=colour, alpha=0.10, linewidth=0)
        if p[-1] >= 100:
            hit = int(np.argmax(p >= 100))
            ax.plot([ahead[hit]], [100], marker="o", markersize=9, color=colour, clip_on=False)
            tag = f"{name}  100 % ✓"
        else:
            tag = f"{name}  {p[-1]:.0f} %"
        ax.annotate(tag, xy=(ahead[-1], p[-1]), xytext=(ahead[-1] + 0.8, p[-1]),
                    va="center", fontsize=10, color=INK, fontweight="600",
                    annotation_clip=False)
        ax.plot([ahead[-1] + 0.35], [p[-1]], marker="s", markersize=7, color=colour,
                clip_on=False)
    _frame(ax)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:.0f} %"))
    ax.set_ylim(0, 100)
    ax.set_xlim(0, ahead[-1])
    ax.set_xlabel("jours à partir d'aujourd'hui", fontsize=9)
    ax.set_title("Tes chances d'entrer dans les playlists algorithmiques",
                 fontsize=14, fontweight="700", color=INK, loc="left", pad=26)
    ax.text(0, 1.035, "Probabilité prévue, jour par jour — la zone claire est l'incertitude",
            transform=ax.transAxes, fontsize=10, color=INK_MUTED)
    return _save(fig, "prediction-discover-weekly.png")


def meta_x_s4a() -> Path:
    """La campagne au lancement, puis Discover Weekly et Radio qui déclenchent — UN graphique.

    R438 : un seul graphique, un axe € à droite, les deux axes depuis zéro.
    R480 (2026-10-09, W3) : « Meta € en rouge, CPR, Hypeddit clics (supprimer Hypeddit
    visites), streams Spotify avec prédiction et déclenchement DW et Radio (deux pics),
    prévisions qui montent ; montrer l'impact de la campagne au début de la release,
    puis le déclenchement des algos et les prédictions ». L'histoire se lit de gauche
    à droite : la dépense (barres rouges) pousse les écoutes dès la sortie, Discover
    Weekly puis Radio les font bondir, et à droite du trait la projection monte avec
    le budget conseillé (hachuré). Le CPR est un RATIO : il est écrit, pas tracé.
    """
    rng = np.random.default_rng(7)
    days = np.arange(42)
    spend = np.zeros(42)
    spend[0:16] = np.linspace(40, 22, 16) + rng.normal(0, 3, 16)
    camp = spend > 0
    clicks = np.clip(np.where(camp, spend * 8.5, 6) + rng.normal(0, 4, 42), 0, None)
    cpr = spend[camp].sum() / clicks[camp].sum()

    # Écoutes : la campagne lève le niveau dès la sortie, puis deux pics — Discover
    # Weekly à J+18, Radio à J+31 — chacun suivi d'un plateau plus haut que l'avant.
    dw_day, radio_day = 18, 31

    def _peak(day: int, height: float, settle: float) -> np.ndarray:
        d = days - day
        return np.where(d < 0, 0, height * np.exp(-d / 3.0) + settle * (1 - np.exp(-d / 2.0)))

    streams = (180 + 420 * (1 - np.exp(-days / 4.0)) * np.where(camp, 1, 0.82)
               + _peak(dw_day, 900, 380) + _peak(radio_day, 700, 320)
               + rng.normal(0, 18, 42))
    streams = np.clip(streams, 0, None)

    horizon = 14
    future = np.arange(days[-1], days[-1] + horizon + 1)
    reach = (future - days[-1]) / horizon
    forecast = streams[-1] * (1 + 0.45 * reach ** 0.9)

    fig, ax = plt.subplots(figsize=(9, 3.82))
    axe = ax.twinx()
    ax.set_zorder(axe.get_zorder() + 1)
    ax.patch.set_visible(False)

    axe.bar(days, spend, color=META, width=0.75, alpha=0.55, linewidth=0)
    # Le budget CONSEILLÉ, à droite du trait, hachuré : une recommandation, jamais
    # une dépense mesurée (R455).
    advised = 25.0
    axe.bar(future[1:], np.full(horizon, advised), color="none", width=0.75,
            edgecolor=META, hatch="////", linewidth=0.6, alpha=0.7)
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
    ax.set_ylim(0, top * 1.22)
    ax.set_ylabel("par jour", fontsize=9)
    ax.set_xlabel("jours depuis la sortie", fontsize=9)
    ax.set_xlim(0, future[-1])
    axe.set_xlim(0, future[-1])
    ax.axvline(days[-1], color=GRID, linewidth=1)

    for day, name in ((dw_day, "Discover Weekly\ndéclenché"), (radio_day, "Radio\ndéclenché")):
        y = streams[day + 1]
        ax.annotate(name, xy=(day + 1, y), xytext=(day + 1, y + top * 0.12),
                    fontsize=9.5, color=INK, fontweight="600", ha="center",
                    arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=1))

    _series_tag(ax, 0.02, 0.93, "Spotify (écoutes)", BLUE)
    _series_tag(ax, 0.02, 0.84, "Meta Ads (€, à droite)", META)
    _series_tag(ax, 0.02, 0.75, "Hypeddit (clics)", HYPEDDIT)
    ax.text(0.14, 0.53, f"CPR {cpr:.2f} € par clic".replace(".", ","),
            transform=ax.transAxes, fontsize=10, color=INK, fontweight="600", ha="center")
    ax.text(0.765, 0.34, f"conseillé : {advised:.0f} €/j\n→ prévision en hausse",
            transform=ax.transAxes, fontsize=9.5, color=INK, fontweight="600", ha="left")

    ax.set_title("Optimiser ton budget Meta Ads pour maximiser tes streams",
                 fontsize=14, fontweight="700", color=INK, loc="left", pad=26)
    ax.text(0, 1.035,
            "La campagne au lancement, puis les algorithmes — à droite du trait, la prévision",
            transform=ax.transAxes, fontsize=10, color=INK_MUTED)
    return _save(fig, "meta-x-s4a.png")


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
    shap_overview()
    return 0

if __name__ == "__main__":
    sys.exit(main())
