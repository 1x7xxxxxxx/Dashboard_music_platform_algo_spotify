#!/usr/bin/env python3
"""Build the charts review dossier — every chart the app and Grafana draw, rendered and graded.

Type: Utility
Uses: capture.py (app figures), pdf_figures.py (artist PDF), grafana.py (ops panels),
      inventory.py (gold-coverage sites), review.yaml (the grades), WeasyPrint,
      tools/dev/architecture_dossier/style.py (CSS)
Triggers: `make charts-dossier OUT=<dir> [PROM=http://127.0.0.1:19090]`
Persists in: <OUT>/dossier-graphiques.pdf — OUTSIDE the repository (artist data)

R203 (2026-09-26). Run order: `capture.py` then this script, which also renders the artist PDF
figures and, when a Prometheus URL is given, the Grafana panels. Everything reads the LOCAL
snapshot database `spotify_etl_review` (see capture.py); Prometheus is read over a tunnel.
"""
from __future__ import annotations

import collections
import datetime as dt
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "dev" / "architecture_dossier"))

VERDICTS = {"garder": "Garder", "corriger": "Corriger", "fusionner": "Fusionner",
            "retirer": "Retirer", "a-trancher": "À trancher"}
ROLES = {"meta": "Meta Ads", "plateforme": "KPI plateforme", "prediction": "Prédiction",
         "archi": "Robustesse de l'app", "business": "Business / admin"}
_COLOR = {"garder": "#1f8a4c", "corriger": "#c0392b", "fusionner": "#b7791f",
          "retirer": "#6b6b6b", "a-trancher": "#2c5282"}

RECOMMENDATIONS = [
    ("Une figure, une décision, lue d'un coup d'œil",
     "Stephen Few, <i>Information Dashboard Design</i>, p. 147",
     "Un tableau de bord se surveille et se comprend d'un regard. Les 44 jauges de la page "
     "modèle, les quatre barres de « gain » du Wrapped et les trois panneaux de la chronologie "
     "de créa en sont l'inverse : chaque verdict « fusionner » ou « retirer » ci-dessous "
     "applique ce critère."),
    ("Les quatre signaux d'or : latence, trafic, erreurs, saturation",
     "Beyer et al., <i>Site Reliability Engineering</i> (Google), p. 86",
     "Grafana couvre les quatre — mais la LATENCE de rendu n'a que 1 à 2 points en sept jours "
     "(panneaux 1 et 7) : le signal existe sur le papier et ne mesure rien. La SATURATION du "
     "pool Postgres montre des replis directs par milliers. Ce sont les deux corrections "
     "d'architecture prioritaires."),
    ("Un modèle se dégrade : suivre la dérive en production",
     "Crowe et al., <i>Machine Learning Production Systems</i>, p. 322",
     "La matrice de confusion porte sur le jeu de test ; aucune figure ne suit la qualité du "
     "modèle DANS LE TEMPS en production. Or les prévisions Release Radar valent toutes 0 et "
     "P(DW) ne réagit pas à son levier. Recommandation : une figure « prédit vs constaté, "
     "semaine par semaine » avant de vendre davantage de prédictions (ADR-029)."),
    ("Corrélation n'est pas causalité",
     "Majors et al., <i>Observability Engineering</i>, p. 49",
     "Pour « qu'apporte Meta », les figures qui REFUSENT de conclure (le verdict d'auditeurs "
     "quand deux campagnes se chevauchent) sont les plus sûres ; celles qui tracent une droite "
     "« R² = 1,00 » sur un point, ou un « point d'équilibre » atteint à zéro, affirment une "
     "causalité que la donnée ne porte pas."),
]


def load() -> dict:
    import yaml
    return yaml.safe_load((HERE / "review.yaml").read_text(encoding="utf-8"))


def esc(s) -> str:
    return html.escape(str(s or ""))


def fiche(key: str, r: dict, img: str | None, meta_line: str, extra: str = "") -> str:
    v = r.get("v", "a-trancher")
    img_html = (f'<img class="fig" src="{esc(img)}">' if img
                else '<div class="nr">Non rendu — voir la note.</div>')
    return f"""<div class="fiche">
<div class="head"><span class="verdict" style="background:{_COLOR.get(v, '#444')}">{VERDICTS.get(v, v)}</span>
<span class="q">{esc(r.get('q'))}</span></div>
{img_html}
<table class="notes"><tr><td>Décision <b>{r.get('d')}/5</b></td><td>Confiance <b>{r.get('c')}/5</b></td>
<td>Pertinence <b>{r.get('p')}/5</b></td><td>{esc(ROLES.get(r.get('role'), r.get('role')))}</td></tr></table>
<p class="note">{esc(r.get('note'))}</p>
<p class="site"><code>{esc(key)}</code> {meta_line}{extra}</p></div>"""


def build(out: Path) -> Path:
    review = load()
    cap = json.loads((out / "capture.json").read_text(encoding="utf-8"))
    pdfj = json.loads((out / "pdf_figures.json").read_text(encoding="utf-8"))
    gra_path = out / "grafana.json"
    gra = json.loads(gra_path.read_text(encoding="utf-8")) if gra_path.exists() else None
    inv = {s["site"]: s for s in json.loads((out / "inventory.json").read_text(encoding="utf-8"))}

    first, views_of, count = {}, collections.defaultdict(list), collections.Counter()
    for f in cap["figures"]:
        first.setdefault(f["site"], f)
        count[f["site"]] += 1
        if f["view"] not in views_of[f["site"]]:
            views_of[f["site"]].append(f["view"])

    app_keys = [k for k in review if not k.startswith(("pdf:", "grafana:"))]
    by_view: dict[str, list[str]] = collections.defaultdict(list)
    for k in app_keys:
        view = views_of[k][0] if views_of.get(k) else Path(k.split(":")[0]).stem
        by_view[view].append(k)

    verdicts = collections.Counter(r.get("v") for r in review.values())
    total = len(review)
    suspects = [k for k, r in review.items() if r.get("v") == "corriger" and r.get("c", 5) <= 2]
    meta_keys = sorted((k for k, r in review.items() if r.get("role") == "meta"),
                       key=lambda k: (-review[k].get("d", 0), k))

    parts = [f"""<h1>Tous les graphiques de streaMLytics — revue avant déploiement</h1>
<p class="lead">R203 · {dt.date.today():%d/%m/%Y} · données : instantané de la production du
{dt.date.today():%d/%m/%Y}, artiste 1 (1x7xxxxxxx), restauré en local — la production n'a jamais été
connectée au rendu. Réglages par défaut des pages.</p>
<h2>Synthèse</h2>
<table class="sum"><tr><th>Graphiques revus</th><td>{total}</td></tr>
<tr><th>… de l'app (sites de code)</th><td>{len(app_keys)} — {len(cap['figures'])} images rendues</td></tr>
<tr><th>… du rapport PDF artiste</th><td>{sum(1 for k in review if k.startswith('pdf:'))}</td></tr>
<tr><th>… de Grafana</th><td>{sum(1 for k in review if k.startswith('grafana:'))}</td></tr>
""" + "".join(f"<tr><th>{VERDICTS[v]}</th><td>{verdicts.get(v, 0)}</td></tr>" for v in VERDICTS)
             + "</table>"]
    parts.append("<h3>À vérifier en premier — des chiffres probablement FAUX (confiance ≤ 2)</h3><ul>"
                 + "".join(f"<li><code>{esc(k)}</code> — {esc(review[k].get('note'))}</li>"
                           for k in suspects) + "</ul>")
    parts.append("<h2>Qu'apporte la campagne Meta Ads ? — les graphiques qui répondent</h2>"
                 "<p>Classés par note de décision. Les réponses les plus sûres : l'argent (point mort "
                 "à 242 ans, 261 € de revenus pour 3 088 € de pub) et le verdict d'auditeurs, qui "
                 "refuse de conclure quand il ne le peut pas.</p><table class='idx'>"
                 + "".join(f"<tr><td>{review[k].get('d')}/5</td><td>{VERDICTS.get(review[k].get('v'))}</td>"
                           f"<td>{esc(review[k].get('q'))}</td><td><code>{esc(k)}</code></td></tr>"
                           for k in meta_keys) + "</table>")
    parts.append("<h2>Recommandations du corpus</h2>" + "".join(
        f"<h3>{t}</h3><p class='src'>{s}</p><p>{b}</p>" for t, s, b in RECOMMENDATIONS))
    parts.append("<h2>Méthode et limites</h2><ul>"
                 "<li>Chaque graphique a été REGARDÉ ; les notes sont un jugement écrit dans "
                 "<code>tools/dev/charts_dossier/review.yaml</code>, relisible et corrigeable.</li>"
                 "<li>Seul le choix par défaut des sélecteurs et des onglets est rendu ; un site non "
                 "atteint est listé « non rendu », jamais omis.</li>"
                 "<li>« À vérifier » signale un chiffre suspect que je n'ai pas encore recalculé.</li>"
                 "<li>Grafana : panneaux redessinés depuis Prometheus (7 derniers jours) ; un trou "
                 "reste un trou.</li></ul>")

    for view in by_view:
        parts.append(f"<h2 class='page'>Page « {esc(view)} »</h2>")
        for k in by_view[view]:
            f = first.get(k)
            s = inv.get(k, {})
            meta_line = (f"· couche {esc(s.get('layer', '—'))} · sources : "
                         f"{esc(', '.join(s.get('sources', [])[:4]) or '—')}")
            extra = ""
            if count[k] > 1:
                extra += f" · {count[k]} images (boucle)"
            if len(views_of.get(k, [])) > 1:
                extra += " · aussi sur : " + esc(", ".join(views_of[k][1:]))
            parts.append(fiche(k, review[k], f"figures/{f['png']}" if f else None, meta_line, extra))

    parts.append("<h2 class='page'>Rapport PDF de l'artiste</h2>")
    pdf_png = {f["key"]: f["png"] for f in pdfj["figures"]}
    for k in [k for k in review if k.startswith("pdf:")]:
        parts.append(fiche(k, review[k], pdf_png.get(k[4:]), "· figure matplotlib du rapport"))

    parts.append("<h2 class='page'>Grafana — robustesse de l'app</h2>")
    gpng = {f"grafana:{p['id']}": (p["png"], p.get("points")) for p in (gra or {}).get("panels", [])}
    for k in [k for k in review if k.startswith("grafana:")]:
        png, pts = gpng.get(k, (None, None))
        parts.append(fiche(k, review[k], png, f"· {pts if pts is not None else '?'} points mesurés en 7 jours"))

    from style import CSS
    css = CSS.replace("streaMLytics — architecture et qualité des données",
                      "streaMLytics — revue des graphiques (R203)") + """
.fiche { page-break-inside: avoid; border-top: 1px solid #ddd; padding-top: 3mm; margin-top: 4mm; }
.fiche .head { display: flex; gap: 3mm; align-items: baseline; }
.verdict { color: #fff; font-weight: bold; font-size: 8.5pt; padding: .6mm 2mm; border-radius: 1mm; }
.q { font-weight: bold; }
img.fig { width: 100%; max-height: 105mm; object-fit: contain; margin: 2mm 0; }
.nr { color: #777; font-style: italic; padding: 3mm 0; }
table.notes td { font-size: 8.5pt; padding: .5mm 3mm .5mm 0; }
.note { margin: 1mm 0; } .site { color: #888; font-size: 7.5pt; margin: 0; }
h2.page { page-break-before: always; } .src { color: #666; font-size: 8.5pt; margin: 0; }
table.idx td, table.sum td, table.sum th { font-size: 8.5pt; padding: .6mm 2mm; text-align: left; }
"""
    doc = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>streaMLytics — revue des graphiques</title><style>{css}</style></head>
<body>{''.join(parts)}</body></html>"""
    (out / "dossier.html").write_text(doc, encoding="utf-8")
    from weasyprint import HTML
    dest = out / "dossier-graphiques.pdf"
    HTML(string=doc, base_url=str(out)).write_pdf(dest)
    return dest


def main(argv: list[str]) -> int:
    out = Path(argv[1]).resolve() if len(argv) > 1 else None
    if out is None or ROOT in out.parents or out == ROOT:
        print("❌ donner le dossier de sortie de capture.py, HORS du dépôt", file=sys.stderr)
        return 2
    import capture
    import inventory
    import pdf_figures
    capture.point_at_snapshot()
    capture.cut_egress()
    (out / "inventory.json").write_text(json.dumps(inventory.sites(), ensure_ascii=False),
                                        encoding="utf-8")
    pdf_figures.render(out)
    if len(argv) > 2:
        import grafana
        grafana.render(out, argv[2])
    dest = build(out)
    print(f"✅ {dest} ({dest.stat().st_size / 1024:.0f} Ko)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
