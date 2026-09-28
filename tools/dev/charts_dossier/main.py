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
            "retirer": "Retirer", "a-trancher": "À trancher", "valider": "Validé"}
ROLES = {"meta": "Meta Ads", "plateforme": "KPI plateforme", "prediction": "Prédiction",
         "archi": "Robustesse de l'app", "business": "Business / admin"}
_COLOR = {"garder": "#1f8a4c", "corriger": "#c0392b", "fusionner": "#b7791f",
          "retirer": "#6b6b6b", "a-trancher": "#2c5282", "valider": "#1f8a4c"}

#: R286 — the owner's reading order (2026-09-28): what must CHANGE first, the validated last.
#: A fiche's place is the owner's verdict when there is one, else mine.
ORDER = [("corriger", "À corriger"), ("fusionner", "À fusionner"),
         ("a-trancher", "À trancher"), ("retirer", "À retirer"),
         ("revalider", "Fait — à revalider"), ("garder", "À garder"), ("valide", "Validés")]
_TO_DO = ("corriger", "fusionner")

RECOMMENDATIONS = [
    ("Une figure, une décision, lue d'un coup d'œil",
     "Stephen Few, <i>Information Dashboard Design</i>, p. 147",
     "Un tableau de bord se surveille et se comprend d'un regard. {ml_page}, les quatre barres de « gain » du Wrapped et les trois panneaux de la chronologie "
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
     "quand deux campagnes se chevauchent) sont les plus sûres ; celles qui traçaient une "
     "droite « R² = 1,00 » sur deux points, ou un « point d'équilibre » lu sur l'avance prise "
     "avant le premier euro de pub, affirmaient une causalité que la donnée ne porte pas "
     "(corrigé le 2026-09-26 : 12 mois, R² = 0,17, p = 0,18 ; équilibre jamais atteint)."),
]


def load() -> dict:
    import yaml
    return yaml.safe_load((HERE / "review.yaml").read_text(encoding="utf-8"))


def load_actions() -> dict:
    """R240 — {review key: {valide, actions}}, written by apply_comments.py."""
    import yaml
    path = HERE / "actions.yaml"
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}


def open_roadmap_ids(checklist_text: str) -> set[str]:
    """The ids of the rows still OPEN in the roadmap index — both tables. Pure."""
    import re
    return set(re.findall(r"^\| (R\d+) \|", checklist_text, re.M))


def archived_roadmap_ids(archive_text: str) -> set[str]:
    """The ids DELIVERED — an entry `- [x] **Rnnn —` or `## ✅ Rnnn —` of the archive. Pure.

    R254 — « done » is read HERE, never deduced from an id being absent from the open
    index: a mistyped or never-registered id was absent too, and showed « ✅ fait »."""
    import re
    return set(re.findall(r"^(?:- \[x\] \*\*|## ✅ )(R\d+)\b", archive_text, re.M))


def waiting_ids(checklist_text: str) -> set[str]:
    """The rows of the « 🙋 En attente de toi » table — the owner's gestures. Pure."""
    import re
    part = checklist_text.split("## 🙋", 1)[1] if "## 🙋" in checklist_text else ""
    return set(re.findall(r"^\| (R\d+) \|", part.split("\n---", 1)[0], re.M))


def action_state(rid: str | None, open_ids: set[str], done_ids: set[str]) -> str:
    """« fait » (archived), « ouvert » (a row of either table), else « inconnu ». Pure."""
    if rid and rid in done_ids:
        return "fait"
    if rid and rid in open_ids:
        return "ouvert"
    return "inconnu"


def unknown_actions(acts: dict, open_ids: set[str], done_ids: set[str],
                    waiting: set[str]) -> list[str]:
    """Every action that points at no real roadmap row, or an owner's gesture outside the
    🙋 table. The generation refuses to print a dossier with one of these. Pure."""
    bad = []
    for key, e in acts.items():
        for a in (e or {}).get("actions") or []:
            rid = a.get("rid")
            if action_state(rid, open_ids, done_ids) == "inconnu":
                bad.append(f"{key} : « {a.get('texte', '')[:50]} » — id {rid or 'absent'} "
                           "introuvable dans la roadmap")
            elif a.get("qui") == "toi" and rid not in waiting and rid not in done_ids:
                bad.append(f"{key} : geste du propriétaire {rid} hors de la table 🙋")
    return bad


STATUSES = {"a-faire": "À faire", "revalider": "Fait — à revalider",
            "sans-avis": "Sans avis", "valide": "Validé"}


def place(r: dict, st_: str) -> str:
    """The section of a fiche in the owner's order (R286). Pure.

    Validated or all-done first decide; otherwise the owner's verdict, else mine."""
    if st_ in ("valide", "revalider"):
        return st_
    v = r.get("owner_v") or r.get("v") or "a-trancher"
    return "valide" if v == "valider" else (v if v in dict(ORDER) else "a-trancher")


def what_to_do(r: dict, entry: dict | None) -> str:
    """R286 — « corriger quoi ? » : a fiche to correct or merge SAYS what, never a bare verdict.
    My actions when there are some, else my note, flagged as not yet a roadmap action. Pure."""
    v = r.get("owner_v") or r.get("v")
    if v not in _TO_DO:
        return ""
    mine = [a["texte"] for a in (entry or {}).get("actions") or [] if a.get("qui") == "moi"]
    body = (" ; ".join(esc(t) for t in mine) if mine
            else f"{esc(r.get('note') or 'à préciser')} <i>(pas encore d'action inscrite)</i>")
    return f'<p class="todo"><b>Ce qu\'il faut faire</b> — {body}</p>'


def status(entry: dict | None, open_ids: set[str], done_ids: set[str] | None = None) -> str:
    """Where a fiche goes in the dossier. Pure.

    `valide` — the owner kept it with nothing to do: the END of the dossier. An action of
    mine is done when its roadmap row is no longer open; all done ⇒ « à revalider » (the
    owner, not me, closes a KPI). A fiche the owner has not spoken about stays « sans avis »."""
    if not entry:
        return "sans-avis"
    if entry.get("valide"):
        return "valide"
    acts = entry.get("actions") or []
    done = done_ids if done_ids is not None else set()
    if acts and all(a.get("qui") == "moi" and a.get("rid") in done for a in acts):
        return "revalider"
    return "a-faire"


def esc(s) -> str:
    return html.escape(str(s or ""))


def number_html(number: tuple | None) -> str:
    """R241 — the chart's number, checked: vérifié / écart / non garanti / pas de rendu."""
    if not number:
        return ""
    from numbers_check import VERDICTS as NV
    key, why = number
    return f'<p class="num num-{key}"><b>{NV[key]}</b> — {esc(why)}</p>'


def actions_html(entry: dict | None, open_ids: set[str],
                 done_ids: set[str] | None = None) -> str:
    acts = (entry or {}).get("actions") or []
    if not acts:
        return ""
    rows = []
    for a in acts:
        who = "Toi" if a["qui"] == "toi" else "Moi"
        rid = a.get("rid")
        state = {"fait": " · <b>✅ fait</b>",
                 "ouvert": " · ⏳ en attente de toi" if a["qui"] == "toi" else " · en cours",
                 "inconnu": " · ❓ id inconnu"}[action_state(rid, open_ids, done_ids or set())]
        rows.append(f"<li><b>{who}</b> — {esc(a['texte'])}"
                    f"{f' <code>{esc(rid)}</code>' if rid else ''}{state}</li>")
    return f'<ul class="acts">{"".join(rows)}</ul>'


def fiche(key: str, r: dict, img: str | None, meta_line: str, extra: str = "",
          no: int | None = None, entry: dict | None = None,
          open_ids: set[str] | None = None, number: tuple | None = None,
          done_ids: set[str] | None = None) -> str:
    v = r.get("v", "a-trancher")
    owner = ""
    if r.get("owner_v") or r.get("owner"):
        ov = r.get("owner_v", "")
        owner = (f'<p class="owner"><b>Ton avis</b> — {VERDICTS.get(ov, ov)}'
                 f'{" : " + esc(r.get("owner")) if r.get("owner") else ""}</p>')
    img_html = (f'<img class="fig" src="{esc(img)}">' if img
                else f'<div class="nr">Non rendu — {esc(r.get("absent") or "cause à trouver (R242)")}.</div>')
    return f"""<div class="fiche">
<div class="head"><span class="no">Fiche {no}</span><span class="verdict" style="background:{_COLOR.get(v, '#444')}">{VERDICTS.get(v, v)}</span>
<span class="q">{esc(r.get('q'))}</span></div>
{img_html}
{number_html(number)}{what_to_do(r, entry)}<p class="note">{esc(r.get('note'))}</p>{owner}{actions_html(entry, open_ids or set(), done_ids)}
<p class="site"><code>{esc(key)}</code> · {esc(ROLES.get(r.get('role'), r.get('role')))} {meta_line}{extra}</p></div>"""


GUIDE = """<h2>Comment me faire tes retours</h2>
<ol>
<li><b>Dis le numéro de la fiche</b> — « fiche 42 » (en haut à gauche de chaque graphique).</li>
<li><b>Commence par un verdict</b> : garder, corriger, fusionner, retirer — ou « à trancher ».</li>
<li>Puis le pourquoi, librement. <b>Un graphique par commentaire.</b></li>
<li>« Même chose pour les fiches 12 à 15 » marche. Un « oui » global sur la liste des chiffres
probablement faux (ci-dessous) suffit : je vérifie chacun avant de toucher au code.</li>
<li>Envoie-moi la transcription telle quelle. Je la rattache aux fiches, je te rends un tableau
trié PAR CAUSE (une correction répare souvent plusieurs graphiques), tu arbitres — et rien
n'entre dans la roadmap avant ton arbitrage.</li>
</ol>
<p>Les fiches « à trancher » n'ont pas pu être rendues (onglet, sélecteur ou clic) : pour elles,
un coup d'œil dans l'app vaut mieux que ce document.</p>"""


METHOD = """<h2>Méthode — un chiffre juste, et comment il le reste</h2>
<p><b>Bronze → argent → or.</b> Le <b>bronze</b> est la donnée telle que la plateforme la
rend (tables de collecte, CSV importés). L'<b>argent</b> la nettoie : une ligne par jour et
par titre, la ligne « Total » des exports retirée, un compteur à vie gardé comme compteur.
L'<b>or</b> porte UNE définition par métrique — une vue par KPI, listée dans
<code>tools/dev/metric_registry.py</code> avec son sens : un <i>flux</i> se somme, un
<i>cumul</i> se différencie et ne se somme jamais, un <i>niveau</i> se lit à sa dernière valeur.</p>
<p><b>Quatre règles font qu'un chiffre reste juste :</b></p>
<ol>
<li><b>Un graphique ne lit que l'or.</b> Le cliquet <code>make gold-coverage</code> refuse une
nouvelle lecture du bronze par un écran.</li>
<li><b>Deux définitions censées coïncider sont comparées chaque soir</b>
(<code>gold_invariants</code>, {n_inv} égalités ; <code>metric_bounds</code> : une somme ne dépasse
jamais son total à vie). Un écart part dans le mail du soir.</li>
<li><b>Ce que la figure DESSINE est contrôlé</b>, pas seulement ce qu'elle lit : un taux au-delà
de 100 %, un cumul qui redescend, deux barres sous une même étiquette. Lire l'or est
nécessaire, pas suffisant : un CTR multiplié deux fois par 100 lisait une vue juste.</li>
<li><b>Chaque correction vient avec un test qui rougit sur le défaut</b>, pour qu'il ne revienne pas.</li>
</ol>
<p>Chaque fiche porte ci-dessous le verdict de ces contrôles sur l'instantané de la production.</p>"""


def numbers_section(out: Path, review: dict, cap: dict, key_of: dict, inv: dict,
                    no_of: dict, views_of: dict) -> tuple[dict, str]:
    """R241 — ({key: (verdict, why)}, the method + KPI table HTML)."""
    import numbers_check
    chk = out / "checks.json"
    checks = json.loads(chk.read_text(encoding="utf-8")) if chk.exists() else None
    findings = (checks or {}).get("findings", [])
    traces: dict[str, list] = collections.defaultdict(list)
    for f in cap["figures"]:
        traces[key_of.get(f["site"], f["site"])] += f.get("traces") or []
    number_of = {}
    for k in review:
        if k.startswith("grafana:"):
            continue
        s_ = inv.get(k, {})
        number_of[k] = numbers_check.verdict(traces.get(k) if k in traces else None,
                                             s_.get("layer", "?"), s_.get("sources", []), findings,
                                             review[k].get("role"))
    counts = collections.Counter(v for v, _ in number_of.values())
    head = ("<p><b>Sur cet instantané :</b> "
            + " · ".join(f"{numbers_check.VERDICTS[v]} : {counts.get(v, 0)}"
                         for v in numbers_check.VERDICTS)
            + (f" — contrôles du soir : {len(findings)} écart(s) sur {checks['pairs']} "
               f"couples et {checks['bounds']} bornes.</p>" if checks
               else " — contrôles du soir non rejoués (checks.json absent).</p>"))
    sys.path.insert(0, str(ROOT))
    from src.utils.gold_invariants import INVARIANTS     # counted, never typed (was « 34 »: 31)
    return number_of, (METHOD.replace("{n_inv}", str(len(INVARIANTS))) + head
                       + kpi_table(review, inv, no_of, views_of))


def kpi_table(review: dict, inv: dict, no_of: dict, views_of: dict) -> str:
    """Each KPI (gold object) → the fiches that read it; two on one page = a twin to judge."""
    sys.path.insert(0, str(ROOT / "tools" / "dev"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("metric_registry",
                                                  ROOT / "tools/dev/metric_registry.py")
    reg = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reg
    spec.loader.exec_module(reg)
    rows = []
    for obj, m in sorted(reg.REGISTRY.items(), key=lambda kv: kv[1].name):
        readers = [k for k in review if obj in inv.get(k, {}).get("sources", [])]
        pages = collections.Counter(views_of.get(k, ["?"])[0] for k in readers)
        twin = any(n > 1 for n in pages.values())
        rows.append(f"<tr><td><b>{esc(m.name)}</b></td><td>{esc(m.sense)}</td>"
                    f"<td><code>{esc(obj)}</code></td>"
                    f"<td>{', '.join(str(no_of[k]) for k in readers) or '—'}</td>"
                    f"<td>{'⚠️ deux sur une page' if twin else ''}</td></tr>")
    return ("<h3>Les KPI et les graphiques qui les lisent</h3><p>Une ligne par métrique de la "
            "couche or. « deux sur une page » : deux graphiques d'une même page lisent la même "
            "métrique — le doublon probable à trancher.</p><table class='idx'><tr><th>KPI</th>"
            "<th>sens</th><th>vue or</th><th>fiches</th><th></th></tr>" + "".join(rows)
            + "</table>")


def page_phrase(cap: dict, view: str = "ml_performance") -> str:
    """How many figures a page drew, COUNTED from capture.json — never typed by hand.

    The dossier said « 44 jauges » for a page that drew 44 figures of which 38 were
    gauges from one line of code (2026-09-26): a count written in prose drifts from the
    render it describes. This one is recomputed at every build.
    """
    per_site = collections.Counter(f["site"] for f in cap["figures"] if f["view"] == view)
    n, top = sum(per_site.values()), max(per_site.values(), default=0)
    if top > 1:
        return (f"Les {n} figures de la page modèle (dont {top} dessinées par une seule "
                "ligne de code)")
    return f"Les {n} figures de la page modèle"


def unexplained(review: dict, rendered: set[str]) -> list[str]:
    """App charts with no image AND no declared cause (`absent:`) — R242. Pure.

    « Non rendu — voir la note » hid sixteen charts for a day: three were one toggle away,
    three behind an Airflow API the render never reached, three behind a SHAP crash in
    production. A chart without an image must say WHY, or the build names it."""
    return [k for k, r in review.items()
            if not k.startswith(("pdf:", "grafana:")) and k not in rendered
            and not (r or {}).get("absent")]


def numbering(review: dict, previous: dict[str, int] | None = None) -> dict[str, int]:
    """Fiche numbers, STABLE: a chart keeps its number for good, a new one takes the next free
    number, a retired one's number is never reused. Pure.

    R242: numbers were the order of review.yaml, so retiring a chart (fiches 59, 61, 70, 71
    asked by the owner) would have renumbered every fiche after it — and his next review,
    dictated « fiche 72 … », would have landed on the wrong chart."""
    previous = previous or {}
    out = {k: previous[k] for k in review if k in previous}
    nxt = max([*previous.values(), 0]) + 1
    for k in review:
        if k not in out:
            out[k] = nxt
            nxt += 1
    return dict(sorted(out.items(), key=lambda kv: kv[1]))


PROPOSALS_INTRO = """<h1 class='page'>Propositions — ce que la pub Meta apporte à nos écoutes (R282)</h1>
<p class="lead">Ta question (notes L167, L482) : « qu'est-ce que nous apporte la campagne Meta Ads
sur nos streams ». Chaque graphique ci-dessous est une PROPOSITION dessinée sur l'instantané :
il n'est pas dans l'app. Dis-moi lesquels garder — chacun deviendra une ligne de roadmap, avec
sa vue or et son test. Un jour de pub est souvent aussi une semaine de sortie : ce qui est
mesuré ici est une association, jamais la preuve d'un effet.</p>
<p><b>Et une question restée ouverte (note L268)</b> : le seuil de déclenchement de
l'algorithme et la prédiction en pointillés sur la courbe Meta × Spotify — maintenant, ou
toujours après le réglage initial ?</p>"""


def proposals_html(out: Path) -> str:
    """The R282 section, from `proposals.json` — empty when the proposals were not drawn."""
    path = out / "proposals.json"
    if not path.exists():
        return ""
    parts = [PROPOSALS_INTRO]
    for n, p in enumerate(json.loads(path.read_text(encoding="utf-8")), 1):
        body = (f"<img class='fig' src='{esc(p['png'])}'>" if p.get("png")
                else f"<p class='nr'>Non dessiné : {esc(p.get('reason'))}</p>")
        parts.append(f"<div class='fiche'><p class='q'>P{n}. {esc(p['title'])}</p>"
                     f"<p class='note'>La décision : {esc(p['decision'])}</p>{body}"
                     + (f"<p class='num'>Mesuré : {esc(p['finding'])}</p>" if p.get("finding") else "")
                     + f"<p class='site'>données : {esc(p['data'])}</p></div>")
    return "".join(parts)


def build(out: Path) -> Path:
    review = load()
    fj = out / "fiches.json"
    previous = ({v: int(k) for k, v in json.loads(fj.read_text(encoding="utf-8")).items()}
                if fj.exists() else {})
    no_of = numbering(review, previous)
    (out / "fiches.json").write_text(
        # Retired charts keep their line: their number is burnt, never handed out again.
        json.dumps({str(n): k for k, n in sorted({**previous, **no_of}.items(),
                                                   key=lambda kv: kv[1])},
                   ensure_ascii=False, indent=1),
        encoding="utf-8")
    cap = json.loads((out / "capture.json").read_text(encoding="utf-8"))
    gra_path = out / "grafana.json"
    gra = json.loads(gra_path.read_text(encoding="utf-8")) if gra_path.exists() else None
    inv_rows = json.loads((out / "inventory.json").read_text(encoding="utf-8"))
    if inv_rows and "key" not in inv_rows[0]:          # artefacts captured before stable keys
        nth: collections.Counter = collections.Counter()
        for r in sorted(inv_rows, key=lambda r: (r["site"].rsplit(":", 1)[0],
                                                  int(r["site"].rsplit(":", 1)[1]))):
            rel = r["site"].rsplit(":", 1)[0]
            nth[(rel, r["fn"])] += 1
            r["key"] = f"{rel}::{r['fn']}#{nth[(rel, r['fn'])]}"
    key_of = {s["site"]: s["key"] for s in inv_rows}   # file:line → stable key
    inv = {key_of[s["site"]]: s for s in inv_rows}

    first, views_of, count = {}, collections.defaultdict(list), collections.Counter()
    for f in cap["figures"]:
        k = key_of.get(f["site"], f["site"])
        first.setdefault(k, f)
        count[k] += 1
        if f["view"] not in views_of[k]:
            views_of[k].append(f["view"])

    app_keys = [k for k in review if not k.startswith(("pdf:", "grafana:"))]
    by_view: dict[str, list[str]] = collections.defaultdict(list)
    for k in app_keys:
        view = views_of[k][0] if views_of.get(k) else Path(k.split(":")[0]).stem
        by_view[view].append(k)

    # R240 — the artist PDF report is out of this dossier until every KPI is validated
    # (owner, 2026-09-27); its fiche numbers are kept, never reused.
    review = {k: r for k, r in review.items() if not k.startswith("pdf:")}
    acts = load_actions()
    checklist = (ROOT / ".claude/dev-docs/roadmap/checklist.md").read_text(encoding="utf-8")
    open_ids = open_roadmap_ids(checklist)
    done_ids = archived_roadmap_ids(
        (ROOT / ".claude/dev-docs/roadmap/archive.md").read_text(encoding="utf-8"))
    # R254 — an action that names no real roadmap row stops the dossier: printed, it
    # would read « ✅ fait » or float outside every table the owner and I read.
    bad = unknown_actions(acts, open_ids, done_ids, waiting_ids(checklist))
    if bad:
        print(f"❌ {len(bad)} action(s) sans ligne de roadmap réelle :", file=sys.stderr)
        for b_ in bad:
            print(f"   {b_}", file=sys.stderr)
        raise SystemExit(1)
    st_of = {k: status(acts.get(k), open_ids, done_ids) for k in review}
    number_of, method = numbers_section(out, review, cap, key_of, inv, no_of, views_of)
    missing = unexplained(review, set(first))
    if missing:
        print(f"⚠️ {len(missing)} graphique(s) sans image ni cause déclarée : "
              + ", ".join(f"fiche {no_of[k]}" for k in missing), file=sys.stderr)
    by_status = collections.Counter(st_of.values())
    total = len(review)
    # R241 — the MEASURED discrepancies of this snapshot, not the grading of an older
    # review: on 2026-09-27 the graded list still named fiches fixed that very day.
    suspects = [k for k in review if number_of.get(k, ("", ""))[0] == "ecart"]

    parts = [f"""<h1>Les KPI de streaMLytics — ce qu'il reste à faire, puis ce qui est validé</h1>
<p class="lead">{dt.date.today():%d/%m/%Y} · données : instantané de la production du
{dt.date.today():%d/%m/%Y}, artiste 1 (1x7xxxxxxx), restauré en local — la production n'a jamais été
connectée au rendu. Réglages par défaut des pages.</p>
<h2>Synthèse</h2>
<table class="sum"><tr><th>Graphiques revus</th><td>{total} — {len(app_keys)} de l'app, {sum(1 for k in review if k.startswith('grafana:'))} de Grafana ({len(cap['figures'])} images rendues)</td></tr>
""" + "".join(f"<tr><th>{STATUSES[s_]}</th><td>{by_status.get(s_, 0)}</td></tr>" for s_ in STATUSES)
             + "<tr><th>Rapport PDF de l'artiste</th><td>retiré de ce dossier jusqu'à validation de tous les KPI</td></tr></table>"]
    parts.append(GUIDE)
    parts.append(proposals_html(out))
    parts.append(method)
    if suspects:
        parts.append("<h3>À vérifier en premier — les écarts mesurés sur cet instantané</h3><ul>"
                     + "".join(f"<li><b>Fiche {no_of[k]}</b> — {esc(number_of[k][1])}</li>"
                               for k in suspects) + "</ul>")
    parts.append("<h2>Recommandations du corpus</h2>" + "".join(
        f"<h3>{t}</h3><p class='src'>{s}</p><p>{b.replace('{ml_page}', page_phrase(cap))}</p>"
        for t, s, b in RECOMMENDATIONS))
    parts.append("<h2>Méthode et limites</h2><ul>"
                 "<li>Chaque graphique a été REGARDÉ ; les notes sont un jugement écrit dans "
                 "<code>tools/dev/charts_dossier/review.yaml</code>, relisible et corrigeable.</li>"
                 "<li>Chaque action porte son id de roadmap ; elle passe ✅ quand la ligne est "
                 "archivée, c'est-à-dire livrée et tests verts. Une fiche dont toutes mes actions "
                 "sont faites attend TA revalidation — je ne valide jamais un KPI à ta place.</li>"
                 "<li>Seul le choix par défaut des sélecteurs et des onglets est rendu ; un site non "
                 "atteint est listé « non rendu », jamais omis.</li>"
                 "<li>Grafana : panneaux redessinés depuis Prometheus (7 derniers jours).</li></ul>")

    def render_one(k: str) -> str:
        if k.startswith("grafana:"):
            png, pts = gpng.get(k, (None, None))
            return fiche(k, review[k], png,
                         f"· {pts if pts is not None else '?'} points mesurés en 7 jours",
                         no=no_of[k], entry=acts.get(k), open_ids=open_ids,
                         done_ids=done_ids)
        f = first.get(k)
        s_ = inv.get(k, {})
        meta_line = (f"· couche {esc(s_.get('layer', '—'))} · sources : "
                     f"{esc(', '.join(s_.get('sources', [])[:4]) or '—')}")
        extra = ""
        if count[k] > 1:
            extra += f" · {count[k]} images (boucle)"
        if len(views_of.get(k, [])) > 1:
            extra += " · aussi sur : " + esc(", ".join(views_of[k][1:]))
        return fiche(k, review[k], f"figures/{f['png']}" if f else None, meta_line, extra,
                     no_of[k], entry=acts.get(k), open_ids=open_ids, number=number_of.get(k),
                     done_ids=done_ids)

    gpng = {f"grafana:{p['id']}": (p["png"], p.get("points")) for p in (gra or {}).get("panels", [])}
    graf_keys = [k for k in review if k.startswith("grafana:")]
    place_of = {k: place(review[k], st_of[k]) for k in review}
    for st_key, title in ORDER:
        keys = [k for k in [*[k for v_ in by_view for k in by_view[v_]], *graf_keys]
                if place_of[k] == st_key]
        if not keys:
            continue
        parts.append(f"<h1 class='page'>{title} — {len(keys)} fiche(s)</h1>")
        current_view = None
        for k in keys:
            view = ("Grafana" if k.startswith("grafana:")
                    else (views_of[k][0] if views_of.get(k) else Path(k.split(":")[0]).stem))
            if view != current_view:
                parts.append(f"<h2>Page « {esc(view)} »</h2>")
                current_view = view
            parts.append(render_one(k))

    parts.append("<h2 class='page'>Index des fiches</h2><table class='idx'>" + "".join(
        f"<tr><td>{n}</td><td>{STATUSES[st_of[k]]}</td><td>{esc(review[k].get('q'))}</td></tr>"
        for k, n in no_of.items() if k in review) + "</table>")

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
.no { font-weight: bold; font-size: 11pt; margin-right: 2mm; }
.num { margin: 1mm 0; font-size: 9pt; } .num-ecart { color: #c0392b; }
.num-verifie { color: #1f8a4c; } .num-non-garanti { color: #b7791f; } .num-etat-app { color: #2c5282; }
ul.acts { margin: 1mm 0 1mm 4mm; padding: 0; font-size: 9pt; }
.todo { background: #fff4e5; border-left: 3px solid #c0392b; padding: 1.5mm 3mm; margin: 1mm 0; }
.owner { background: #eef4ff; border-left: 3px solid #2c5282; padding: 1.5mm 3mm; margin: 1mm 0; }
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
    if len(argv) > 2 and argv[1] == "--rebuild":
        # From the artefacts already captured — no snapshot, no Prometheus (R204).
        out = Path(argv[2]).resolve()
        if not _outside_git(out):
            print("❌ dossier dans le dépôt et non ignoré par git", file=sys.stderr)
            return 2
        dest = build(out)
        print(f"✅ {dest} ({dest.stat().st_size / 1024:.0f} Ko)")
        return 0
    out = Path(argv[1]).resolve() if len(argv) > 1 else None
    if out is None or not _outside_git(out):
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
    import proposals
    proposals.render(out)
    if len(argv) > 2:
        import grafana
        grafana.render(out, argv[2])
    dest = build(out)
    print(f"✅ {dest} ({dest.stat().st_size / 1024:.0f} Ko)")
    return 0



def _outside_git(out: Path) -> bool:
    """Outside the repository, or inside a folder git IGNORES (`revue/`, .gitignore) — the
    dossier carries real artist data and the repository history is public."""
    import subprocess
    if ROOT not in out.parents and out != ROOT:
        return True
    probe = out / "dossier-graphiques.pdf"
    return subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", str(probe)]).returncode == 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
