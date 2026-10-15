"""Every legend the app draws, and where the door put it — `revue/legendes.md` (R565).

Type: Utility (dev)
Uses: <out>/capture.json (written by capture.py, which records each figure AFTER the door)
Triggers: `make legend-inventory`
Persists in: <out>/legendes.md — git-ignored with the rest of `revue/` (artist names in
             trace labels)

Owner, 2026-10-15: « un livrable qui répertorie toutes les légendes ». One row per
rendered figure: page, code site, title, the entries a reader sees, the place chosen ON
the plot, and how many data points the legend box covers there (R574: « prouver que
chaque légende est sur le graphique, à l'endroit le moins gênant »).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


_FR = {"top": "haut", "bottom": "bas", "middle": "milieu", "right": "droite",
       "left": "gauche", "center": "centre"}


def _covered(spec: dict, place: str, entries: int) -> int:
    import plotly.graph_objects as go

    from src.dashboard.utils.legend_place import covered, paper_points
    return covered(paper_points(go.Figure(spec)), place, entries)


def legend_of(spec: dict) -> dict:
    """The legend of one figure's JSON: entries, place, points it covers. Pure."""
    lay = spec.get("layout", {})
    names = [str(t["name"]) for t in spec.get("data", [])
             if t.get("name") and t.get("showlegend") is not False]
    shown = lay.get("showlegend")
    if shown is False or (shown is None and len(names) < 2):
        return {"entries": [], "place": "—", "covered": 0}
    leg = lay.get("legend") or {}
    if leg.get("yref") == "container" or (leg.get("y") or 0) < 0:
        return {"entries": names, "place": "dessous", "covered": 0}
    vert, horiz = leg.get("yanchor", "top"), leg.get("xanchor", "right")
    return {"entries": names, "place": f"{_FR[vert]} {_FR[horiz]}",
            "covered": _covered(spec, f"{vert} {horiz}", len(names))}


def markdown(figures: list[dict]) -> str:
    """The inventory as a Markdown page, grouped by placement count first. Pure."""
    with_legend = [f for f in figures if f.get("legend", {}).get("entries")]
    counts: dict[str, int] = {}
    for f in with_legend:
        counts[f["legend"]["place"]] = counts.get(f["legend"]["place"], 0) + 1
    lines = ["# Légendes de l'app — inventaire (R565)", "",
             f"{len(figures)} figure(s) rendue(s), {len(with_legend)} avec une légende. "
             "Placement : " + ", ".join(f"{k} ×{v}" for k, v in sorted(counts.items())) + ".",
             f"Sous le graphique : {counts.get('dessous', 0)}. Points de données cachés "
             f"par la légende, au total : {sum(f['legend'].get('covered', 0) for f in with_legend)}.",
             "", "| # | Page | Site | Titre | Entrées | Position | Points cachés |",
             "|---|---|---|---|---|---|---|"]
    for f in with_legend:
        title = (f.get("title") or "").replace("|", "/").replace("\n", " ")[:70]
        entries = " · ".join(f["legend"]["entries"]).replace("|", "/")
        lines.append(f"| {f['id']} | {f['view']} | `{f.get('view_site') or f.get('site')}` "
                     f"| {title} | {entries} | {f['legend']['place']} "
                     f"| {f['legend'].get('covered', '?')} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else Path("revue")
    capture = json.loads((out / "capture.json").read_text(encoding="utf-8"))
    figures = capture["figures"]
    if not any("legend" in f for f in figures):
        print("❌ capture.json sans légendes (capture antérieure à R565). Run: make "
              "legend-inventory", file=sys.stderr)
        return 1
    (out / "legendes.md").write_text(markdown(figures), encoding="utf-8")
    print(f"✅ {out / 'legendes.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
