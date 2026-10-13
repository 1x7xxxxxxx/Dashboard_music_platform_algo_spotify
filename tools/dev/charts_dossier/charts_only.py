"""Charts-only dossier — the figures of a few pages, nothing else (R551).

Type: Utility
Uses: main.fiche / main.load / main.numbering, inventory.sites, style.CSS, WeasyPrint
Triggers: `python3 tools/dev/charts_dossier/charts_only.py OUT` after `capture.py OUT <views>`
Persists in: OUT/graphiques.pdf (OUT outside git — it carries artist data)

Owner, 2026-10-13: « un pdf pour me rendre uniquement les graphiques de la vue croisée + de
la view prédiction, sur le même principe ». Same fiche as the dossier's body (number,
question, image, 🎯 line), grouped by page; no decisions page, no annexes, no Grafana, no
« non rendu » fiche. A figure captured on an alias page AND on the Vue croisée is printed
once; every image of a looped site is printed (they draw different breakdowns).
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import sys
from pathlib import Path

import main

# Printed group → the capture views that make it. The aliases open the Vue croisée on one
# of its sections, so their figures belong to it.
GROUPS = (
    ("Vue croisée", ("meta_ads_overview", "meta_x_spotify", "meta_creatives",
                     "meta_breakdowns", "instagram")),
    ("Prédiction", ("trigger_algo",)),
)


def figures_by_key(cap: dict, key_of: dict) -> dict[str, list[dict]]:
    """Each key's images, taken from the FIRST view that drew it — an alias repeats them."""
    first_view: dict[str, str] = {}
    out: dict[str, list[dict]] = collections.defaultdict(list)
    for f in cap["figures"]:
        k = key_of.get(f["site"], f["site"])
        if first_view.setdefault(k, f["view"]) == f["view"]:
            out[k].append(f)
    return out


def build(out: Path) -> Path:
    import inventory
    review = main.load()
    no_of = main.numbering(review)
    cap = json.loads((out / "capture.json").read_text(encoding="utf-8"))
    key_of = {s["site"]: s["key"] for s in inventory.sites()}
    figs = figures_by_key(cap, key_of)
    parts = [f"<h1>streaMLytics — graphiques de la vue croisée et de Prédiction</h1>"
             f"<p class='lead'>{dt.date.today():%d/%m/%Y} · instantané de la production, "
             f"artiste 1 · {sum(map(len, figs.values()))} graphiques.</p>"]
    for title, views in GROUPS:
        keys = [k for k, fs in figs.items() if fs[0]["view"] in views]
        n = sum(len(figs[k]) for k in keys)
        parts.append(f"<h1 class='page'>{title} — {n} graphique(s)</h1>")
        for k in keys:
            r = review.get(k) or {"q": figs[k][0].get("title") or k}
            for f in figs[k]:
                parts.append(main.fiche(k, r, f"figures/{f['png']}", "", no=no_of.get(k, "—"),
                                        mode="compact"))
    from style import CSS
    css = CSS.replace("streaMLytics — architecture et qualité des données",
                      "streaMLytics — graphiques vue croisée + Prédiction") + """
.fiche { page-break-inside: avoid; border-top: 1px solid #ddd; padding-top: 3mm; margin-top: 4mm; }
.fiche .head { display: flex; gap: 3mm; align-items: baseline; }
.fiche .verdict { display: none; }
.q { font-weight: bold; } .no { font-weight: bold; font-size: 11pt; margin-right: 2mm; }
img.fig { width: 100%; max-height: 105mm; object-fit: contain; margin: 2mm 0; }
h1.page { page-break-before: always; }
p.decide { font-size: 10.5pt; font-weight: bold; color: #1a4d8f; margin: 1mm 0 2mm; }
.mq { font-size: 8pt; background: #dde6f5; padding: 0 1.5mm; border-radius: 1mm; }
"""
    doc = (f'<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>streaMLytics — '
           f'graphiques</title><style>{css}</style></head><body>{"".join(parts)}</body></html>')
    (out / "graphiques.html").write_text(doc, encoding="utf-8")
    from weasyprint import HTML
    dest = out / "graphiques.pdf"
    HTML(string=doc, base_url=str(out)).write_pdf(dest)
    return dest


if __name__ == "__main__":
    target = Path(sys.argv[1]).resolve()
    if not main._outside_git(target):
        sys.exit("❌ dossier dans le dépôt et non ignoré par git")
    pdf = build(target)
    print(f"✅ {pdf} ({pdf.stat().st_size / 1024:.0f} Ko)")
