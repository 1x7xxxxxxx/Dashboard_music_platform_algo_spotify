"""Every legend the app draws, and where the door put it — `revue/legendes.md` (R565).

Type: Utility (dev)
Uses: <out>/capture.json (written by capture.py, which records each figure AFTER the door)
Triggers: `make legend-inventory`
Persists in: <out>/legendes.md — git-ignored with the rest of `revue/` (artist names in
             trace labels)

Owner, 2026-10-15: « un livrable qui répertorie toutes les légendes ». One row per
rendered figure: page, code site, title, the entries a reader sees, the corner chosen
(or « dessous » when every corner held data, or « — » when the figure has none).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def legend_of(spec: dict) -> dict:
    """The legend of one figure's JSON: its visible entries and its placement. Pure."""
    lay = spec.get("layout", {})
    names = [str(t["name"]) for t in spec.get("data", [])
             if t.get("name") and t.get("showlegend") is not False]
    shown = lay.get("showlegend")
    if shown is False or (shown is None and len(names) < 2):
        return {"entries": [], "place": "—"}
    leg = lay.get("legend") or {}
    if leg.get("yref") == "container" or (leg.get("y") or 0) < 0:
        place = "dessous"
    else:
        place = (f"{'haut' if leg.get('yanchor', 'top') == 'top' else 'bas'} "
                 f"{'droite' if leg.get('xanchor', 'right') == 'right' else 'gauche'}")
    return {"entries": names, "place": place}


def markdown(figures: list[dict]) -> str:
    """The inventory as a Markdown page, grouped by placement count first. Pure."""
    with_legend = [f for f in figures if f.get("legend", {}).get("entries")]
    counts: dict[str, int] = {}
    for f in with_legend:
        counts[f["legend"]["place"]] = counts.get(f["legend"]["place"], 0) + 1
    lines = ["# Légendes de l'app — inventaire (R565)", "",
             f"{len(figures)} figure(s) rendue(s), {len(with_legend)} avec une légende. "
             "Placement : " + ", ".join(f"{k} ×{v}" for k, v in sorted(counts.items())) + ".",
             "", "| # | Page | Site | Titre | Entrées | Position |", "|---|---|---|---|---|---|"]
    for f in with_legend:
        title = (f.get("title") or "").replace("|", "/").replace("\n", " ")[:70]
        entries = " · ".join(f["legend"]["entries"]).replace("|", "/")
        lines.append(f"| {f['id']} | {f['view']} | `{f.get('view_site') or f.get('site')}` "
                     f"| {title} | {entries} | {f['legend']['place']} |")
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
