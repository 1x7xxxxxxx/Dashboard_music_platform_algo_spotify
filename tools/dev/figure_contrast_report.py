#!/usr/bin/env python3
"""Rapport : quelles figures ne peuvent pas être ATTRIBUÉES par un daltonien.

Type: Utility
Uses: src/dashboard/utils/colorimetry (CIEDE2000 + Viénot/Brettel, stdlib)
Triggers: `make figure-contrast` — RAPPORT SEUL, il ne bloque rien
Depends on: src/dashboard/views/**, src/dashboard/utils/**
Persists in: nothing (écrit sur stdout, ou du JSON avec --json)

⚠️ **Report-only, et c'est une décision, pas une facilité.** `code-critic` a rendu
BUILD-MODIFIED sur R133 : 28 figures sous le plancher, et **migrer les 28 en une passe
est refusé**. Un garde bloquant posé sur un parc de 28 sites déjà rouges n'a que deux
issues — on le désactive, ou on bâcle 28 migrations visuelles sans les regarder. Les
deux détruisent le garde. La porte DURE ne porte donc que sur le DIFF
(`tests/test_a_new_figure_can_be_attributed.py`) : une figure neuve ou touchée doit
passer ; les anciennes sont un plafond qui descend, jamais une barrière qui explose.

⚠️ **28 est un PLAFOND, pas un compte de défauts.** Le plancher de 15 a été calibré sur
des AIRES EMPILÉES, où la teinte est le SEUL canal d'attribution. Une figure qui écrit sa
valeur au bout de chaque barre, ou dont les séries occupent des positions Y distinctes,
reste lisible bien en dessous. `meta_funnel`, `revenue_forecast.py:82` et `ig_engagement`
y tombent sans être des défauts. Le rapport les signale avec la mention `atténué:` quand
il détecte un canal de secours, et NE les retire pas du compte — ce serait décider à la
place de l'œil.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.dashboard.utils.colorimetry import de2000, lab, simulate  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
_ARBRES = ("src/dashboard/views", "src/dashboard/utils")

# Ce qui OUVRE une figure. La segmentation est PAR FIGURE et pas par fonction : un
# `show()` qui dessine trois graphiques distincts mélangeait leurs couleurs, et le
# premier chiffre publié (26, par fonction) était faux pour cette raison — `pi_gate`
# y comptait comme illisible alors que ses trois couleurs vivent sur trois panneaux.
_OUVRE_UNE_FIGURE = re.compile(
    r"\b(?:go\.Figure\(|px\.[a-z_]+\(|plt\.subplots\(|plt\.figure\(|make_subplots\(|_stacked\()")

_HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_RGBA = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")

# Un canal d'attribution AUTRE que la teinte. Sa présence n'excuse pas la figure — elle
# est rapportée pour que l'œil tranche, parce que le plancher a été calibré sur le cas
# où la teinte est seule.
# ⚠️ **La première version de ce motif s'allumait sur 24 des 25 figures — donc elle ne
# disait rien.** Elle acceptait `marker=` et `linestyle=`, qui sont présents dans presque
# chaque trace Plotly ou Matplotlib sans rien ajouter : un marqueur DE LA MÊME COULEUR
# n'est pas un second canal d'attribution, c'est la même teinte avec une autre forme de
# tache. Resserré à ce qui distingue vraiment deux séries sans la teinte :
#   · une VALEUR ÉCRITE sur chaque donnée (`texttemplate`, `text_auto`, `ax.text`…)
#   · une POSITION distincte (barres groupées, barres horizontales, second axe)
#   · un MOTIF de trait ou de remplissage (`dash=`, `pattern_shape`, `hatch=`)
# `marker=` et `linestyle=` seuls sont exclus : ils ne séparent pas deux aires.
_CANAL_DE_SECOURS = re.compile(
    r"\b(?:texttemplate|text_auto|textposition|annotate\(|ax\.text\(|"
    r"barmode\s*=\s*['\"]group|orientation\s*=\s*['\"]h|twinx\(|"
    r"dash\s*=\s*['\"]|pattern_shape|hatch\s*=)")


def _neutre(h: str) -> bool:
    """Un chrome : gris, blanc, noir. La chroma Lab le dit, pas une liste de noms.

    Une liste (`#fff`, `#ffffff`, `white`, `#eee`…) serait exactement le prédicat de
    FORME que la règle 20 interdit ; la chroma est la propriété.
    """
    _, a, b = lab(h)
    return (a * a + b * b) ** 0.5 < 12.0


def _normalise(h: str) -> str:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.lower()


def _couleurs(fragment: str) -> list[str]:
    out = []
    for m in _HEX.finditer(fragment):
        out.append(_normalise(m.group(0)))
    for m in _RGBA.finditer(fragment):
        out.append("#%02x%02x%02x" % tuple(int(m.group(i)) for i in (1, 2, 3)))
    vues, uniques = set(), []
    for h in out:
        if h in vues or _neutre(h):
            continue
        vues.add(h)
        uniques.append(h)
    return uniques


# ── Le PANNEAU, et pas la figure — troisième resserrement de cette mesure ──────
#
# Deux couleurs ne sont confusables que si elles peuvent se retrouver DANS LE MÊME
# panneau. Une figure `make_subplots(rows=2)` porte deux repères distincts : une barre
# verte en `row=1` et une courbe rouge en `row=2` n'ont jamais à être attribuées l'une
# contre l'autre.
#
# ⚠️ **C'est exactement l'erreur qui avait produit le premier chiffre de 26**, mesuré
# PAR FONCTION le 2026-09-17 ; elle a été corrigée en passant PAR FIGURE, et elle
# revient à l'identique un cran plus bas. `_tab_algos.py:90` en est le cas : `#1DB954`
# vit en `row=1`, `#FF6B6B` en `row=2`, et la mesure par figure les opposait à ΔE 3,1.
# Le même défaut à trois granularités successives, et chaque fois invisible sans
# regarder un site.
_TRACE = re.compile(r"\b(?:add_trace\(|go\.[A-Z]\w*\(|ax\d?\.(?:plot|bar|barh|fill_between|scatter|pie)\()")
_PANNEAU = re.compile(r"\brow\s*=\s*(\d+)\s*,\s*col\s*=\s*(\d+)")
# Ce qui FERME une figure : elle est rendue, renvoyée, ou écrite.
_FERME = re.compile(r"\b(?:st\.plotly_chart\(|st\.pyplot\(|write_image\(|savefig\(|return fig\b)")


def _panneaux(fragment: str) -> list[list[str]]:
    """Les couleurs du fragment, GROUPÉES par panneau de la figure.

    Une trace sans `row=`/`col=` appartient au panneau unique. Les couleurs qui ne sont
    dans aucune trace (mise en forme, fond, annotations) sont versées au panneau unique
    elles aussi : les écarter demanderait de décider ce qu'est une « couleur de série »
    sur du texte, et la chroma s'en charge déjà pour les chromes.
    """
    lignes = fragment.splitlines()
    debuts = [i for i, ligne in enumerate(lignes) if _TRACE.search(ligne)]
    if not debuts:
        return [_couleurs(fragment)]
    groupes: dict[str, list[str]] = {}
    hors_trace = "\n".join(lignes[:debuts[0]])
    for n, debut in enumerate(debuts):
        fin = debuts[n + 1] if n + 1 < len(debuts) else len(lignes)
        bloc = "\n".join(lignes[debut:fin])
        m = _PANNEAU.search(bloc)
        cle = f"{m.group(1)},{m.group(2)}" if m else "unique"
        groupes.setdefault(cle, []).extend(_couleurs(bloc))
    if hors_trace.strip():
        groupes.setdefault("unique", []).extend(_couleurs(hors_trace))
    sorties = []
    for couleurs in groupes.values():
        vues, uniques = set(), []
        for h in couleurs:
            if h not in vues:
                vues.add(h)
                uniques.append(h)
        sorties.append(uniques)
    return sorties


def _pire_paire(couleurs: list[str]) -> tuple[float, str, str, str]:
    pire = (999.0, "", "", "")
    for i, a in enumerate(couleurs):
        for b in couleurs[i + 1:]:
            for genre, x, y in (("normal", a, b),
                                ("deutan", simulate(a, "deutan"), simulate(b, "deutan")),
                                ("protan", simulate(a, "protan"), simulate(b, "protan"))):
                d = de2000(x, y)
                if d < pire[0]:
                    pire = (d, genre, a, b)
    return pire


def figures(racine: Path = RACINE) -> list[dict]:
    """Une entrée par FIGURE portant au moins deux couleurs de série non neutres."""
    trouvees: list[dict] = []
    for arbre in _ARBRES:
        for f in sorted((racine / arbre).rglob("*.py")):
            if "__pycache__" in str(f):
                continue
            texte = f.read_text(encoding="utf-8-sig")
            lignes = texte.splitlines()
            debuts = [i for i, ligne in enumerate(lignes) if _OUVRE_UNE_FIGURE.search(ligne)]
            for n, debut in enumerate(debuts):
                fin = debuts[n + 1] if n + 1 < len(debuts) else len(lignes)
                # BORNÉE À SON RENDU. Sans cette borne le « fragment » d'une figure
                # court jusqu'à la figure suivante — 108 lignes pour `_tab_algos.py:90`
                # — et ramasse le code, les couleurs et les canaux de secours de tout
                # ce qui se trouve entre les deux.
                for k in range(debut, fin):
                    if _FERME.search(lignes[k]):
                        fin = k + 1
                        break
                fragment = "\n".join(lignes[debut:fin])
                for couleurs in _panneaux(fragment):
                    if len(couleurs) < 2:
                        continue
                    d, genre, a, b = _pire_paire(couleurs)
                    trouvees.append({
                        "fichier": str(f.relative_to(racine)),
                        "ligne": debut + 1,
                        "couleurs": couleurs,
                        "delta_e": round(d, 1),
                        "sous": genre,
                        "paire": [a, b],
                        "attenue": bool(_CANAL_DE_SECOURS.search(fragment)),
                    })
    return trouvees


PLANCHER = 15.0
_BASELINE = RACINE / ".claude" / "dev-docs" / "figure-contrast-baseline.json"


def cle(f: dict) -> str:
    """L'identité d'une figure, insensible au numéro de ligne.

    ⚠️ Clé sur `fichier + paire de couleurs`, PAS sur `fichier:ligne`. Une clé de ligne
    fait apparaître comme NEUVE toute figure sous laquelle on a ajouté un commentaire :
    la porte se déclenche sur du texte, on la désactive, elle ne garde plus rien. La
    paire de couleurs est ce que la porte juge réellement ; c'est donc ce qui l'identifie.
    """
    return f["fichier"] + " " + " ".join(sorted(f["paire"]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="sortie machine")
    ap.add_argument("--plancher", type=float, default=PLANCHER)
    ap.add_argument("--baseline", action="store_true",
                    help="réécrit le plafond — SEULEMENT après avoir corrigé une figure")
    args = ap.parse_args()

    toutes = figures()
    sous = [f for f in toutes if f["delta_e"] < args.plancher]

    if args.baseline:
        import collections
        ref = json.loads(_BASELINE.read_text(encoding="utf-8"))
        if len(sous) > ref["total"]:
            print(f"❌ {len(sous)} figures sous le plancher contre {ref['total']} "
                  "enregistrées. Le plafond DESCEND, il ne monte pas : régénérer ici "
                  "ferait taire une figure neuve au lieu de la corriger.", file=sys.stderr)
            return 1
        ref["total"] = len(sous)
        ref["cles"] = dict(sorted(collections.Counter(cle(f) for f in sous).items()))
        ref["detail"] = sorted(sous, key=lambda f: f["delta_e"])
        _BASELINE.write_text(json.dumps(ref, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        print(f"plafond réécrit : {len(sous)} figure(s) sous le plancher")
        return 0
    if args.json:
        print(json.dumps({"figures": len(toutes), "sous_le_plancher": len(sous),
                          "plancher": args.plancher, "detail": sous}, indent=2))
        return 0

    print(f"▶ {len(toutes)} figure(s) à ≥2 couleurs de série, "
          f"**{len(sous)}** sous le plancher de {args.plancher}\n")
    for f in sorted(sous, key=lambda x: x["delta_e"]):
        marque = "  atténué (un autre canal que la teinte)" if f["attenue"] else ""
        print(f"  ΔE {f['delta_e']:4.1f}  {f['sous']:<7} {f['fichier']}:{f['ligne']}"
              f"  {f['paire'][0]} ↔ {f['paire'][1]}{marque}")
    print("\nRAPPORT SEUL — rien n'est bloqué ici. La porte dure ne porte que sur le "
          "diff : `tests/test_a_new_figure_can_be_attributed.py`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
