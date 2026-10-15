"""The cross view's figures, walked from its five sections, against what each one draws (R569).

Type: Utility
Uses: ast, yaml, tools/dev/charts_dossier/cross_view.yaml (the declarative registry)
Triggers: `make cross-view-inventory`, tests/test_the_cross_view_draws_each_datum_once.py
Persists in: revue/vue-croisee-inventaire.md (generated, not versioned)

Owner, 2026-10-15: « une donnée = un graphique », no table, understood from the chart
alone. R567 and R568 removed what a reading found; this keeps it removed. The figure
sites are FOUND, not listed: the walk starts at each section's render function in
`meta_ads_overview.SECTIONS` and follows every call into `src/`, so a figure added three
modules down is seen. What each site draws — its (dimension · metric) pairs — cannot be
read off the code reliably (the measure hides behind helpers), so it is DECLARED in
`cross_view.yaml`; the walk makes that declaration exhaustive and never stale.
"""
from __future__ import annotations

import ast
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
OVERVIEW = "src/dashboard/views/meta_ads_overview.py"
REGISTRY = Path(__file__).with_name("cross_view.yaml")
SECTION_FUNCS = {"chrono": "_render_chrono", "entonnoir": "_render_funnel_section",
                 "creas": "_render_creatives", "audiences": "_render_audiences",
                 "instagram": "_render_instagram"}
_FIGURE = "plotly_chart"
_TABLES = frozenset({"dataframe", "table", "data_editor"})
_DOOR = "src/dashboard/utils/charts.py"   # the chart door: its own `plotly_chart` is no site


def _module_path(dotted: str) -> str | None:
    for cand in (dotted.replace(".", "/") + ".py", dotted.replace(".", "/") + "/__init__.py"):
        if (ROOT / cand).exists():
            return cand
    return None


class _Walker:
    """Every figure and table call reachable from a section, as `path::func#n` sites."""

    def __init__(self) -> None:
        self._trees: dict[str, ast.Module] = {}
        self.seen: set[tuple[str, str]] = set()
        self.figures: dict[str, str] = {}      # site -> section
        self.tables: list[str] = []            # `path:line func` of each table call

    def _tree(self, path: str) -> ast.Module:
        if path not in self._trees:
            self._trees[path] = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        return self._trees[path]

    def _imports(self, path: str) -> dict[str, tuple]:
        out: dict[str, tuple] = {}
        for n in ast.walk(self._tree(path)):
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("src."):
                for a in n.names:
                    sub = _module_path(f"{n.module}.{a.name}")
                    if sub:
                        out[a.asname or a.name] = ("mod", sub)
                    elif _module_path(n.module):
                        out[a.asname or a.name] = ("fn", _module_path(n.module), a.name)
        return out

    def visit(self, path: str, name: str, section: str) -> None:
        if (path, name) in self.seen or path == _DOOR:
            return
        self.seen.add((path, name))
        funcs = {n.name: n for n in ast.walk(self._tree(path))
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        if name not in funcs:
            return
        imports, n_fig = self._imports(path), 0
        calls = sorted((c for c in ast.walk(funcs[name]) if isinstance(c, ast.Call)),
                       key=lambda c: (c.lineno, c.col_offset))
        for c in calls:
            f = c.func
            attr = f.attr if isinstance(f, ast.Attribute) else None
            if attr == _FIGURE:
                n_fig += 1
                self.figures.setdefault(f"{path}::{name}#{n_fig}", section)
            elif attr in _TABLES or (attr in ("markdown", "write") and _md_table(c)):
                self.tables.append(f"{path}:{c.lineno} {name}")
            if isinstance(f, ast.Name):
                if f.id in funcs:
                    self.visit(path, f.id, section)
                elif imports.get(f.id, ("",))[0] == "fn":
                    self.visit(imports[f.id][1], imports[f.id][2], section)
            elif (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                  and imports.get(f.value.id, ("",))[0] == "mod"):
                self.visit(imports[f.value.id][1], f.attr, section)


def _md_table(call: ast.Call) -> bool:
    """A markdown table: a string argument with a `|---` separator row."""
    texts = [n.value for n in ast.walk(call) if isinstance(n, ast.Constant)
             and isinstance(n.value, str)]
    return any(line.strip().startswith("|") and "---" in line
               for s in texts for line in s.splitlines())


def walk() -> _Walker:
    w = _Walker()
    for section, func in SECTION_FUNCS.items():
        w.visit(OVERVIEW, func, section)
    return w


def load_registry(path: Path = REGISTRY) -> dict[str, dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def duplicates(registry: dict[str, dict]) -> list[str]:
    """Each (dimension · metric) drawn by two sites that can render together. Pure.

    A site declaring `instead_of: <site>` never renders beside that site (two campaigns
    chosen draw the pair, else the single funnel) — the pair it shares is no duplicate."""
    owners: dict[str, list[str]] = {}
    for site, entry in registry.items():
        for pair in entry.get("draws", ()):
            owners.setdefault(pair, []).append(site)
    out = []
    for pair, sites in owners.items():
        live = [s for s in sites if registry[s].get("instead_of") not in sites]
        if len(live) > 1:
            out.append(f"« {pair} » : {', '.join(live)}")
    return out


def inventory(registry: dict[str, dict], figures: dict[str, str]) -> str:
    dup = Counter(p for e in registry.values() for p in e.get("draws", ()))
    lines = ["# Vue croisée — inventaire des figures (généré, R569)", "",
             "Une ligne par figure atteignable depuis les cinq sections. « Doublon » nomme "
             "une donnée tracée ailleurs ; `instead_of` = jamais rendue en même temps.", "",
             "| Section | Figure | Données tracées | Doublon éventuel |", "|---|---|---|---|"]
    order = {s: i for i, s in enumerate(SECTION_FUNCS)}
    for site in sorted(figures, key=lambda s: (order[figures[s]], s)):
        e = registry.get(site, {})
        draws = e.get("draws", ["⚠️ non déclarée"])
        twins = [p for p in draws if dup[p] > 1]
        note = (f"au lieu de `{e['instead_of'].split('::')[-1]}`" if e.get("instead_of")
                else ("⚠️ " + " ; ".join(twins) if twins else "—"))
        lines.append(f"| {figures[site]} | `{site.split('/')[-1]}` | {' ; '.join(draws)} "
                     f"| {note} |")
    return "\n".join(lines) + "\n"


def main(out_dir: str = "revue") -> int:
    w, reg = walk(), load_registry()
    dest = ROOT / out_dir / "vue-croisee-inventaire.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(inventory(reg, w.figures), encoding="utf-8")
    print(f"✅ {len(w.figures)} figures, {len(duplicates(reg))} doublon(s), "
          f"{len(w.tables)} tableau(x) → {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
