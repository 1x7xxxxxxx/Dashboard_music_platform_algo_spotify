"""R299 — trace every chart: the Meta Ads question it answers, its layer, its twins.

Type: Utility
Uses: tools/dev/charts_dossier/triage.py (likely_twins — the (page, sources, measure) twin),
      review.yaml (`mq`), inventory.json (layer, sources), requirements.yaml (REQ ids)
Triggers: tools/dev/charts_dossier/main.py (the « Traçabilité » section of the PDF)
Persists in: nothing — the section is rebuilt at every dossier build

The owner's goal (2026-09-28): no duplicate KPI, merge what can be merged, every chart tied
to a Meta Ads marketing question, one table that traces it all — layer bronze/silver/gold
and his requirements — with duplicates highlighted.

Code-critic (BUILD-MODIFIED, 2026-09-28):
- `mq` only on `role: meta` fiches: the other roles already classify the rest; a second
  enum for them would be the duplicate this tool hunts;
- « two charts answer one question » is NOT a duplicate on its own — the 34 Meta fiches
  collapse onto seven questions by design (country, placement, age are angles of one
  question). A duplicate is confined to ONE PAGE: the (page, sources, measure) twin of
  `triage.likely_twins`, and the (page, sources) group reviewed below with its verdict;
- silver is claimed only where it is PROVEN: the slicer's hops never pass through
  `platform_timeseries` (measured: 0), but its SOURCES name the silver functions a figure
  reads (`src.dashboard.utils.platform_timeseries.<fn>`) — that name is the proof.
"""
from __future__ import annotations

import collections
import html

#: The closed list of the owner's Meta Ads marketing questions (notes L167, L482, R282).
MQ: dict[str, str] = {
    "M1": "Qu'est-ce que la pub m'apporte en écoutes ?",
    "M2": "Quelle campagne, quelle créa refaire ?",
    "M3": "Combien me coûte un résultat (clic, écoute) ?",
    "M4": "Quand juger, relancer ou couper une campagne ?",
    "M5": "Le trafic payé convertit-il jusqu'aux plateformes ?",
    "M6": "La pub est-elle rentable (point mort, ROI) ?",
    "M7": "Quelle audience, quel pays, quel placement ?",
}

ROLE_LABEL = {"plateforme": "Plateforme (organique)", "archi": "DevOps / robustesse",
              "prediction": "Modèle ML", "business": "Business / admin"}

#: (page, sources) groups of ≥2 figures, each LOOKED AT on 2026-09-28: (verdict, the keys that
#: are a real repeat and get highlighted — empty for a false twin). The (page, sources,
#: measure) twins of `likely_twins` are empty on that day.
_CR = "src/dashboard/views/meta_creatives.py::"
_CAT = "src/dashboard/views/trigger_algo/_tab_catalogue.py::_show_tab_catalogue#"
SHARED_REVIEWED: dict[frozenset, tuple[str, frozenset]] = {
    frozenset({"src/dashboard/views/trigger_algo/_tab_model.py::_show_volume_vs_recorded#1",
               "src/dashboard/views/trigger_algo/_tab_model.py::_show_error_by_prediction_week#1"}):
        ("faux doublon — par titre (dernière prédiction) vs par semaine de prédiction",
         frozenset()),
    frozenset({"src/dashboard/views/trigger_algo/_tab_catalogue.py::_show_tab_catalogue#1",
               "src/dashboard/views/trigger_algo/_tab_catalogue.py::_show_tab_catalogue#2"}):
        ("à trancher — les jauges (% du chemin) se calculent depuis les valeurs et leurs "
         "seuils du second graphique ; ma reco : garder les valeurs, les jauges en survol",
         frozenset({_CAT + "1", _CAT + "2"})),
    frozenset({f"src/dashboard/views/meta_creatives.py::{fn}#1" for fn in (
        "_render_ranking", "_render_hooks", "_render_creative_timeline", "_render_scatter",
        "_render_funnel", "_render_fatigue", "_render_activity")}):
        ("à trancher pour UN couple : le nuage dépense × CPR redit deux cadres du classement "
         "(ma reco : le garder replié, il montre les créas « à couper » d'un coup d'œil) ; "
         "les cinq autres sont des faux doublons — par accroche, dans le temps, par étape, "
         "par fréquence, par semaine active",
         frozenset({_CR + "_render_ranking#1", _CR + "_render_scatter#1"})),
}

#: Merged on 2026-09-28 (R299): the retired fiche, the fiche that now carries it, why.
MERGED: list[tuple[int, int, str]] = [
    (16, 15, "Instagram — le taux d'engagement était la courbe « par publication » divisée "
             "par UN nombre d'abonnés : même forme ; il passe au survol"),
    (21, 20, "Meta Ads — « Performance par campagne » (budget, clics, CPR) redisait trois des "
             "six cadres de « Performance globale », avec un AUTRE CPR (÷ résultats au lieu "
             "de ÷ clic sortant) : une étiquette, deux définitions sur une page"),
    (33, 29, "Créatives — le comparateur CTR/CPM/CPC redisait le CTR du classement sur les "
             "mêmes 15 créas ; CPM et CPC deviennent deux cadres du classement"),
]


def shared_source_groups(inventory: list[dict]) -> list[frozenset]:
    """Figures of one page file reading the SAME set of sources, ≥ 2 of them. Pure.

    Wider than `triage.likely_twins` (which also demands the same measure): the three merges
    of 2026-09-28 plotted one measure under different column names, and the measure axis
    alone saw none of them."""
    groups: dict = collections.defaultdict(set)
    for e in inventory:
        if e.get("kind") == "figure" and e.get("sources"):
            groups[(e["site"].split(":")[0], tuple(e["sources"]))].add(e["key"])
    return [frozenset(v) for v in groups.values() if len(v) > 1]


SILVER_PREFIX = "src.dashboard.utils.platform_timeseries."


def layer_label(layer: str, grafana: bool = False, sources: list[str] | tuple = (),
                role: str = "") -> str:
    """The layer in the owner's words. Pure. Silver only where a source NAMES it."""
    if grafana:
        return "télémétrie (Prometheus)"
    silver = any(str(x).startswith(SILVER_PREFIX) for x in sources)
    if layer == "—":
        return "état de l'app" if role == "business" else "non tracée (lecture hors SQL lisible)"
    base = {"or": "or", "brut": "bronze", "mixte": "mixte (or + bronze)"}.get(layer, layer)
    return f"argent + {base}" if silver else base


def requirements(layer: str, twin: bool, grafana: bool) -> list[str]:
    """The owner's requirements a row answers to — ids of requirements.yaml. Pure.
    `layer` is the LABEL of `layer_label` (« argent + or », « bronze », …)."""
    out = []
    if grafana:
        out += ["REQ-OBS-01", "REQ-OBS-02"]
    elif layer.startswith("argent"):
        out.append("REQ-SILVER-01")
    if not grafana and ("bronze" in layer):
        out.append("REQ-GOLD-03")
    elif not grafana and layer.endswith("or"):
        out.append("REQ-GOLD-01")
    if twin:
        out.append("REQ-CHART-04")
    return out


def rows(review: dict, inv: dict, no_of: dict, page_of: dict,
         groups: list[frozenset], twins: list[list[str]]) -> list[dict]:
    """One row per chart, in fiche order. Pure."""
    twin_of: dict[str, str] = {}
    for n, g in enumerate([*[frozenset(t) for t in twins], *groups], 1):
        for k in g:
            twin_of.setdefault(k, f"D{n}")
    out = []
    for k, r in review.items():
        graf = k.startswith("grafana:")
        srcs = inv.get(k, {}).get("sources", [])
        layer = layer_label(inv.get(k, {}).get("layer", "—"), graf, srcs, r.get("role", ""))
        reviewed = next((vr for g, vr in SHARED_REVIEWED.items() if k in g), None)
        real = bool(twin_of.get(k)) and (reviewed is None or k in reviewed[1])
        out.append({
            "no": no_of.get(k), "key": k, "page": "Grafana" if graf else page_of.get(k, "?"),
            "q": r.get("q", ""),
            "mq": r.get("mq") or ("D" if graf else ""),
            "family": (MQ.get(r.get("mq"), "") if r.get("mq")
                       else ROLE_LABEL.get(r.get("role"), r.get("role", ""))),
            "layer": layer,
            "sources": srcs,
            "reqs": requirements(layer, real, graf),
            "twin": twin_of.get(k, "") if real else "",
            "twin_note": reviewed[0] if reviewed else "",
            "v": r.get("v", ""),
        })
    return sorted(out, key=lambda x: x["no"] or 0)


def per_question(trace: list[dict]) -> list[dict]:
    """Each Meta question → its charts, and the pages where ≥ 2 charts answer it. Pure."""
    out = []
    for code, text in MQ.items():
        hits = [r for r in trace if r["mq"] == code]
        pages = collections.Counter(r["page"] for r in hits)
        out.append({"code": code, "text": text, "fiches": [r["no"] for r in hits],
                    "same_page": {p: n for p, n in pages.items() if n > 1}})
    return out


def _e(x) -> str:
    return html.escape(str(x))


def section_html(trace: list[dict]) -> str:
    """The « Traçabilité » section: the questions, then every chart, twins highlighted."""
    q = per_question(trace)
    holes = [x for x in q if not x["fiches"]]
    qrows = "".join(
        f"<tr class='{'dup' if x['same_page'] else ''}'><td><b>{x['code']}</b></td>"
        f"<td>{_e(x['text'])}</td><td>{len(x['fiches'])}</td>"
        f"<td>{', '.join(map(str, x['fiches'])) or '— aucun graphique'}</td>"
        f"<td>{_e('; '.join(f'{p} ×{n}' for p, n in x['same_page'].items()))}</td></tr>"
        for x in q)
    merged = "".join(f"<li>Fiche <b>{a}</b> fusionnée dans la fiche <b>{b}</b> — {_e(why)}</li>"
                     for a, b, why in MERGED)
    def src(x: str) -> str:
        return "argent:" + x[len(SILVER_PREFIX):] if x.startswith(SILVER_PREFIX) else x
    trows = "".join(
        f"<tr class='{'dup' if r['twin'] else ''}'><td>{r['no']}</td><td>{_e(r['page'])}</td>"
        f"<td>{_e(r['q'])}<div class='srcs'>{_e(', '.join(src(x) for x in r['sources'][:3]))}"
        f"{' …' if len(r['sources']) > 3 else ''}</div></td>"
        f"<td><b>{_e(r['mq'])}</b> {_e(r['family'])}</td><td>{_e(r['layer'])}</td>"
        f"<td>{'<br>'.join(_e(x) for x in r['reqs'])}</td><td><b>{_e(r['twin'])}</b></td></tr>"
        for r in trace)
    notes: dict[str, tuple[str, list]] = {}
    for r in trace:
        if r["twin_note"]:
            notes.setdefault(r["twin_note"], (r["twin"], []))[1].append(r["no"])
    groups = "".join(f"<li>Fiches {', '.join(map(str, nos))}{' — <b>' + _e(t) + '</b>' if t else ''}"
                     f" : {_e(n)}</li>" for n, (t, nos) in notes.items())
    n_twins = len({r["twin"] for r in trace if r["twin"]})
    layers = collections.Counter(r["layer"] for r in trace)
    return f"""<h1 class='page'>Traçabilité — chaque graphique, sa question, sa couche (R299)</h1>
<p class="lead">Ton objectif du 28/09 : aucun KPI en doublon, tout ce qui peut l'être fusionné,
chaque graphique rattaché à une question marketing Meta Ads, sa couche bronze / argent / or et
tes exigences. <b>Surligné en jaune</b> : un doublon à trancher sur une même page.</p>
<h3>Ce qui a été fusionné (sans perte)</h3><ul>{merged}</ul>
<h3>Les questions marketing Meta Ads — qui y répond</h3>
<p>Plusieurs graphiques pour une question n'est PAS un doublon (pays, placement, âge sont des
angles d'une même question). La colonne « même page » signale seulement où plusieurs graphiques
d'une MÊME page y répondent — surligné, à relire.{' Questions sans aucun graphique : '
+ ', '.join(x['code'] for x in holes) + '.' if holes else ''}</p>
<table class='idx trace'><tr><th>code</th><th>question</th><th>nb</th><th>fiches</th>
<th>même page</th></tr>{qrows}</table>
<h3>Tous les graphiques — {len(trace)} lignes, {n_twins} groupe(s) de doublon à trancher</h3>
<p>Couches : {_e(', '.join(f'{k} {v}' for k, v in layers.most_common()))}. <b>Argent</b> :
dite seulement quand une source NOMME une fonction de <code>platform_timeseries</code>
(ADR-019, préfixe « argent: » dans les sources). « Non tracée » : le lecteur passe par une
requête que l'analyse statique ne lit pas — pas une absence de couche, un trou de preuve.
Exigences : REQ-SILVER-01 l'argent a une identité ; REQ-GOLD-01
une métrique = une vue or ; REQ-GOLD-03 ne lire que l'or ; REQ-CHART-04 aucune redondance ;
REQ-OBS-01/02 Grafana, sans redite dans l'admin.</p>
<h3>Les graphiques d'une même page qui lisent les mêmes sources — mon verdict</h3>
<ul>{groups}</ul>
<table class='idx trace'><colgroup><col style='width:5%'><col style='width:14%'>
<col style='width:37%'><col style='width:18%'><col style='width:11%'><col style='width:10%'>
<col style='width:5%'></colgroup><tr><th>fiche</th><th>page</th><th>question · sources</th>
<th>question marketing</th><th>couche</th><th>exigences</th><th>dbl.</th></tr>
{trows}</table>"""
