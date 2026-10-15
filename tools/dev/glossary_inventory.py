"""Where each glossary word appears in the app, and where it is still defined in place (R592).

Type: Utility
Uses: ast, src/dashboard/utils/glossary.py (TERMS and their detection patterns)
Triggers: `make glossary-inventory`, tests/test_the_glossary_defines_every_word.py
Persists in: revue/glossaire-inventaire.md (generated, not versioned)

Owner, 2026-10-15: the glossary page holds every technical word ONCE. This inventory
reads every string literal of `src/dashboard/` and says, per word, where a reader meets
it — and lists the in-place definitions that remain (the chart door's `charts.GLOSSARY`,
the cross view's « Les mots de cette page »), so a second definition is seen, not hoped
away.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.dashboard.utils.glossary import TERMS  # noqa: E402

SCAN = ROOT / "src" / "dashboard"
SKIP = {"glossary.py"}  # the glossary itself and its catalog define, they don't use
IN_PLACE = (("src/dashboard/utils/charts.py", "GLOSSARY"),
            ("src/dashboard/views/meta_ads_overview.py", "_GLOSSARY"))


def strings() -> list[tuple[str, int, str]]:
    """(relative path, line, text) of every string literal under src/dashboard/."""
    out = []
    for path in sorted(SCAN.rglob("*.py")):
        if path.name in SKIP or "i18n_catalog" in path.parts:
            continue
        rel = str(path.relative_to(ROOT))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                out.append((rel, node.lineno, node.value))
    return out


def occurrences() -> dict[str, list[str]]:
    """term key → sorted unique ['file:line'] where one of its patterns matches."""
    texts = strings()
    found: dict[str, list[str]] = {}
    for key, _g, _term, _def, patterns in TERMS:
        rx = re.compile("|".join(patterns), re.I)
        found[key] = sorted({f"{rel}:{line}" for rel, line, s in texts if rx.search(s)})
    return found


def in_place_definitions() -> list[tuple[str, int, str]]:
    """(file, line, key) of each entry in a local glossary that still defines a word."""
    out = []
    for rel, name in IN_PLACE:
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        for node in tree.body:
            target = getattr(node, "target", None) or (node.targets[0] if isinstance(
                node, ast.Assign) and len(node.targets) == 1 else None)
            if not (isinstance(target, ast.Name) and target.id == name):
                continue
            value = node.value
            keys = value.keys if isinstance(value, ast.Dict) else [
                e.elts[0] for e in getattr(value, "elts", []) if isinstance(e, ast.Tuple)]
            out += [(rel, k.lineno, k.value) for k in keys if isinstance(k, ast.Constant)]
    return out


def inventory() -> str:
    occ = occurrences()
    lines = ["# Glossaire — où l'app emploie chaque mot", "",
             "Généré par `make glossary-inventory` (R592). Chaque mot est défini UNE fois, "
             "sur la page « 📖 Glossaire » ; ce tableau dit où un lecteur le rencontre.", "",
             "| mot | groupe | occurrences | premiers sites |", "|---|---|---|---|"]
    for key, group, term, _d, _p in TERMS:
        sites = occ[key]
        lines.append(f"| {term} | {group} | {len(sites)} | "
                     f"{', '.join(f'`{s}`' for s in sites[:3]) or '—'} |")
    unused = [term for key, _g, term, _d, _p in TERMS if not occ[key]]
    lines += ["", f"**{len(unused)} mot(s) défini(s) que l'app n'emploie nulle part** : "
              + (", ".join(unused) or "aucun."), "",
              "## Définitions encore données en place", "",
              "Ces glossaires locaux répètent une définition sous le graphique ou la page "
              "qui emploie le mot. Le glossaire les contient tous ; ils restent tant qu'un "
              "lecteur en a besoin sans quitter la page.", "",
              "| fichier | ligne | mot |", "|---|---|---|"]
    lines += [f"| `{f}` | {ln} | {k} |" for f, ln, k in in_place_definitions()]
    return "\n".join(lines) + "\n"


def main(out_dir: str = "revue") -> int:
    dest = ROOT / out_dir / "glossaire-inventaire.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(inventory(), encoding="utf-8")
    occ = occurrences()
    print(f"✅ {len(TERMS)} mots, {sum(1 for v in occ.values() if v)} employés, "
          f"{len(in_place_definitions())} définition(s) en place → {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
