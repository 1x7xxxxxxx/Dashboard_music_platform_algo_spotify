"""Deux aires de la figure peuvent être ATTRIBUÉES, y compris par un daltonien.

Type: Test
Uses: pytest (colorimétrie en stdlib)
Depends on: src/dashboard/utils/platform_chart.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
La palette a été refusée une fois, et la mesure vivait dans un commentaire. Le
2026-09-08, le premier jet prenait les couleurs de MARQUE exactes :

    #1DB954 · #FF0000 · #FF5500
    youtube ↔ soundcloud   ΔE 9.6 (vision normale) · 4.6 (deutan)

Deux aires qu'on ne peut pas attribuer — la définition d'une figure illisible. Le
verdict venait d'un validateur EXTERNE (`node scripts/validate_palette.js`, skill
`dataviz`), absent de ce dépôt : la mesure n'était donc rejouable nulle part, et le
2026-09-12 la palette a changé de nouveau sans que rien ne puisse la vérifier.

Ce fichier porte la mesure elle-même — CIEDE2000 et la simulation dichromate de
Viénot/Brettel, en stdlib. Il ne remplace pas la skill ; il rend son verdict
reproductible ici, ce qui est la différence entre une règle et un souvenir.

⚠️ LES DEUX PLANCHERS NE SONT PAS LES MÊMES, et c'est une borne mesurée, pas un
confort. La bande de clarté du mode sombre (0,48–0,67) laisse 0,19 de latitude pour
séparer trois teintes chaudes — Spotify vert, YouTube rouge, SoundCloud orange,
Apple magenta. Balayage exhaustif le 2026-09-12 : le MAXIMUM atteignable y est
**13,9** (14,6 sans Apple), contre 16,9 en clair. Un plancher de 15 en sombre est
donc un plancher que rien ne peut franchir ; le fixer là rendrait le garde rouge à
vie, donc ignoré. Il est à 13,5, et la marge au-dessus du maximum est de 0,4 : la
palette sombre ne peut pas se dégrader sans que ce fichier le dise.

Mutation — 2026-09-12 : Apple remise à son rouge de marque `#fa243c`, ce garde la
nomme (ΔE 3,0 contre YouTube en deutan) ; remise en magenta, il passe.
"""
from __future__ import annotations

import itertools

import pytest

from src.dashboard.utils.platform_chart import _PALETTE_DARK, _PALETTE_LIGHT

import math

def _srgb_lin(c):
    c /= 255.0
    return c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4

def hex_rgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def lab(h):
    r, g, b = (_srgb_lin(v) for v in hex_rgb(h))
    X = (0.4124*r + 0.3576*g + 0.1805*b) / 0.95047
    Y = (0.2126*r + 0.7152*g + 0.0722*b) / 1.00000
    Z = (0.0193*r + 0.1192*g + 0.9505*b) / 1.08883
    def f(t):
        return t**(1/3) if t > 216/24389 else (841/108)*t + 4/29
    fx, fy, fz = f(X), f(Y), f(Z)
    return (116*fy - 16, 500*(fx-fy), 200*(fy-fz))

def lightness(h):
    return lab(h)[0] / 100.0

def de2000(h1, h2):
    L1,a1,b1 = lab(h1); L2,a2,b2 = lab(h2)
    C1, C2 = math.hypot(a1,b1), math.hypot(a2,b2); Cb = (C1+C2)/2
    G = 0.5*(1-math.sqrt(Cb**7/(Cb**7+25**7))) if Cb else 0.5
    a1p, a2p = (1+G)*a1, (1+G)*a2
    C1p, C2p = math.hypot(a1p,b1), math.hypot(a2p,b2)
    h1p = math.degrees(math.atan2(b1,a1p)) % 360 if (a1p or b1) else 0
    h2p = math.degrees(math.atan2(b2,a2p)) % 360 if (a2p or b2) else 0
    dLp, dCp = L2-L1, C2p-C1p
    dhp = 0 if C1p*C2p == 0 else ((h2p-h1p+180) % 360) - 180
    dHp = 2*math.sqrt(C1p*C2p)*math.sin(math.radians(dhp)/2)
    Lb, Cbp = (L1+L2)/2, (C1p+C2p)/2
    if C1p*C2p == 0: hbp = h1p+h2p
    elif abs(h1p-h2p) <= 180: hbp = (h1p+h2p)/2
    else: hbp = (h1p+h2p+360)/2 if h1p+h2p < 360 else (h1p+h2p-360)/2
    T = (1 - 0.17*math.cos(math.radians(hbp-30)) + 0.24*math.cos(math.radians(2*hbp))
         + 0.32*math.cos(math.radians(3*hbp+6)) - 0.20*math.cos(math.radians(4*hbp-63)))
    SL = 1 + 0.015*(Lb-50)**2/math.sqrt(20+(Lb-50)**2)
    SC, SH = 1+0.045*Cbp, 1+0.015*Cbp*T
    RT = -2*math.sqrt(Cbp**7/(Cbp**7+25**7))*math.sin(math.radians(60*math.exp(-(((hbp-275)/25)**2))))
    return math.sqrt((dLp/SL)**2 + (dCp/SC)**2 + (dHp/SH)**2 + RT*(dCp/SC)*(dHp/SH))

# Brettel/Viénot — simulation LMS des dichromatismes
_M = ((17.8824,43.5161,4.11935),(3.45565,27.1554,3.86714),(0.0299566,0.184309,1.46709))
_Mi = ((0.0809445,-0.130504,0.116721),(-0.0102485,0.0540193,-0.113615),(-0.000365294,-0.00412163,0.693513))
_SIM = {"deutan": ((1,0,0),(0.494207,0,1.24827),(0,0,1)),
        "protan": ((0,2.02344,-2.52581),(0,1,0),(0,0,1))}
def simulate(h, kind):
    v = [_srgb_lin(c)*255 for c in hex_rgb(h)]
    def mul(M, x):
        return [sum(M[i][j]*x[j] for j in range(3)) for i in range(3)]

    def enc(c):
        u = max(c, 0) / 255
        v = 1.055*u**(1/2.4) - 0.055 if u > 0.0031308 else 12.92*u
        return max(0, min(255, round(255*v)))

    out = mul(_Mi, mul(_SIM[kind], mul(_M, v)))
    return "#%02x%02x%02x" % tuple(enc(c) for c in out)

def report(pal, band, floor_normal=15.0, floor_cvd=15.0):
    ks = list(pal); bad = []
    for a, b in itertools.combinations(ks, 2):
        d = de2000(pal[a], pal[b])
        if d < floor_normal: bad.append(f"  normal  {a}↔{b}  ΔE {d:4.1f}  < {floor_normal}")
        for kind in ("deutan", "protan"):
            dc = de2000(simulate(pal[a],kind), simulate(pal[b],kind))
            if dc < floor_cvd: bad.append(f"  {kind:<7} {a}↔{b}  ΔE {dc:4.1f}  < {floor_cvd}")
    for k, h in pal.items():
        L = lightness(h)
        if not (band[0] <= L <= band[1]):
            bad.append(f"  clarté  {k} {h} L={L:.2f} hors bande {band}")
    return bad


# Planchers, et le pourquoi de leur écart est dans le docstring.
_FLOOR_LIGHT = 15.0
_FLOOR_DARK = 13.5
_BAND_LIGHT = (0.43, 0.77)
_BAND_DARK = (0.48, 0.67)


@pytest.mark.parametrize("theme,pal,floor,band", [
    ("clair", _PALETTE_LIGHT, _FLOOR_LIGHT, _BAND_LIGHT),
    ("sombre", _PALETTE_DARK, _FLOOR_DARK, _BAND_DARK),
])
def test_every_pair_of_areas_can_be_told_apart(theme, pal, floor, band) -> None:
    """Chaque paire, en vision normale ET dichromate. Une seule suffit à casser."""
    bad = []
    for a, b in itertools.combinations(sorted(pal), 2):
        for vision, ca, cb in (("normale", pal[a], pal[b]),
                               ("deutan", simulate(pal[a], "deutan"), simulate(pal[b], "deutan")),
                               ("protan", simulate(pal[a], "protan"), simulate(pal[b], "protan"))):
            d = de2000(ca, cb)
            if d < floor:
                bad.append(f"  {theme}/{vision:<8} {a} ↔ {b}  ΔE {d:4.1f}  < {floor}")
    assert not bad, (
        f"deux aires de la figure ne peuvent pas être attribuées en thème {theme} :\n"
        + "\n".join(bad)
        + "\n\nC'est le défaut du 2026-09-08 — les couleurs de marque exactes, "
          "refusées à ΔE 4,6. Chercher la meilleure position DANS la famille de "
          "marque, jamais la teinte exacte.")


@pytest.mark.parametrize("theme,pal,band", [
    ("clair", _PALETTE_LIGHT, _BAND_LIGHT), ("sombre", _PALETTE_DARK, _BAND_DARK),
])
def test_every_colour_sits_in_its_theme_lightness_band(theme, pal, band) -> None:
    """Hors bande, l'aire disparaît dans le fond ou brûle l'écran."""
    out = [f"  {k} {v} L={lightness(v):.2f} hors {band}"
           for k, v in sorted(pal.items()) if not band[0] <= lightness(v) <= band[1]]
    assert not out, f"thème {theme} :\n" + "\n".join(out)


def test_the_measurement_reproduces_the_refusal_that_created_this_rule() -> None:
    """NON-VACUITÉ : le validateur doit REFUSER ce qui a été refusé le 2026-09-08.

    Sans ce test, une erreur de formule rendrait tout vert et le fichier entier
    serait un garde qui ne garde rien — la forme que ce dépôt a payée le plus
    souvent. Les couleurs de marque exactes sont donc rejouées ici : leur ΔE deutan
    mesuré à l'époque était 4,5 ; on exige seulement qu'il reste très en dessous du
    plancher, pas un chiffre au dixième près.
    """
    d = de2000(simulate("#FF0000", "deutan"), simulate("#FF5500", "deutan"))
    assert d < 8.0, (
        f"le rouge YouTube et l'orange SoundCloud mesurent ΔE {d:.1f} en deutan — "
        "le validateur ne reproduit plus le refus du 2026-09-08, donc il ne mesure "
        "plus ce qu'il prétend mesurer")
