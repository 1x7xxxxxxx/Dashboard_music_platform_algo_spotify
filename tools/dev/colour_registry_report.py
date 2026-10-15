"""The colour registry, and the hex literals still written outside it (R603).

Type: Utility
Uses: ast, src/dashboard/utils/platform_colors.py (TYPE_COLOURS)
Triggers: `make colour-registry`, tests/test_a_platform_colour_has_one_definition.py
Persists in: revue/couleurs.md (generated, not versioned)

Owner, 2026-10-15 : « une couleur par type de donnée dans toute l'app ». The registry says
what each colour MEANS; this report says, per type, which modules read it, and lists every
`#rrggbb` literal still written by hand under src/dashboard/ — the guard ratchets that
same count (`hex_literals`), so the report and the test cannot disagree.
"""
from __future__ import annotations

import ast
import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DASH = ROOT / "src" / "dashboard"
HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
# The registry itself writes its colours: that is what it is for.
CARRIERS = {"platform_colors.py"}
# Type family → the names a module reads the family through.
READERS = {
    "campaign": ("PAIR_COLORS", "pair_colors", "BOTH_COLOR", '"campaign.'),
    "release": ("TITLE_COLORS", '"release.'),
    "playlist": ("ALGO_COLORS", '"playlist.'),
    "projection": ("LONG_TERM_COLOR", '"projection.'),
    "platform": ("platform_color", "PALETTE_LIGHT", "PALETTE_DARK", '"platform.'),
}


def _docstrings(tree: ast.AST) -> set[int]:
    out = set()
    for n in ast.walk(tree):
        body = getattr(n, "body", None)
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) \
                and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            out.add(id(body[0].value))
    return out


def hex_literals(root: Path | None = None) -> collections.Counter:
    """'relative/path.py' → number of hex colour literals, docstrings excluded."""
    root = root or DASH
    out: collections.Counter = collections.Counter()
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts or p.name in CARRIERS:
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        docs = _docstrings(tree)
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and id(n) not in docs and HEX.match(n.value.strip()):
                out[str(p.relative_to(root))] += 1
    return out


def readers() -> dict[str, list[str]]:
    """Type family → modules under src/dashboard/ that read it."""
    found: dict[str, list[str]] = {k: [] for k in READERS}
    for p in sorted(DASH.rglob("*.py")):
        if p.name in CARRIERS:
            continue
        text = p.read_text(encoding="utf-8")
        for fam, names in READERS.items():
            if any(n in text for n in names):
                found[fam].append(str(p.relative_to(DASH)))
    return found


def report() -> str:
    from src.dashboard.utils.platform_colors import TYPE_COLOURS
    lines = ["# Couleurs — une couleur par type de donnée", "",
             "Généré par `make colour-registry` (R603) depuis "
             "`src/dashboard/utils/platform_colors.py::TYPE_COLOURS`.", "",
             "| type | couleur | | lu par |", "|---|---|---|---|"]
    reads = readers()
    for key, hexa in TYPE_COLOURS.items():
        fam = key.split(".")[0]
        lines.append(f"| `{key}` | `{hexa}` | <span style='color:{hexa}'>■■■</span> | "
                     f"{len(reads.get(fam, []))} module(s) |")
    lines += ["", "Une créative prend la couleur de SA campagne (R597).", "",
              "## Lecteurs par famille", ""]
    for fam, mods in reads.items():
        lines.append(f"- **{fam}** : " + (", ".join(f"`{m}`" for m in mods) or "aucun"))
    hx = hex_literals()
    lines += ["", f"## Couleurs encore écrites en dur — {sum(hx.values())} dans {len(hx)} "
              "fichier(s)", "",
              "Le cliquet de `tests/test_a_platform_colour_has_one_definition.py` gèle ce "
              "compte fichier par fichier : il ne peut que descendre.", "",
              "| fichier | littéraux |", "|---|---|"]
    lines += [f"| `{f}` | {n} |" for f, n in hx.most_common()]
    return "\n".join(lines) + "\n"


def main(out_dir: str = "revue") -> int:
    dest = ROOT / out_dir / "couleurs.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(report(), encoding="utf-8")
    hx = hex_literals()
    print(f"✅ registre écrit, {sum(hx.values())} couleur(s) en dur dans {len(hx)} fichier(s) "
          f"→ {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
