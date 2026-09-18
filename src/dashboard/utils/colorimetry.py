"""La colorimétrie du dépôt : CIEDE2000 et la simulation dichromate de Viénot/Brettel.

Type: Utility
Uses: stdlib seulement (math, itertools)
Depends on: rien
Persists in: nothing

⚠️ **Ce module vivait dans `tests/` jusqu'au 2026-09-18, et c'est ce qui bloquait R133.**
Une mesure enfermée dans un fichier de test n'est pas disponible pour le CODE : ni pour
l'outil qui rapporte l'état des figures, ni pour la porte qui refuse une figure neuve
illisible, ni pour un futur sélecteur de couleur. `code-critic` a rendu BUILD-MODIFIED
sur R133 avec cette extraction comme première condition, et elle est faite ici — par
déplacement, sans une ligne de logique modifiée, pour que le garde de palette existant
reste exactement le même garde.

La mesure elle-même a son histoire dans `tests/test_the_palette_can_be_attributed.py`,
qui reste le garde de la palette de plateformes : les couleurs de marque EXACTES sont à
ΔE 4,6 en deutan, et le mode sombre plafonne à 13,9 — une borne, pas un confort.
"""
from __future__ import annotations

import itertools
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
