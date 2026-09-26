"""Every chart the app, the artist PDF and Grafana can draw has its graded review (R203).

Type: Sub
Uses: tools/dev/charts_dossier/inventory.py (gold-coverage sites), review.yaml,
      deploy/grafana/dashboards/streamlytics-ops.json, src/dashboard/utils/pdf_exporter/_report.py
Depends on: nothing (static reads; no database)
Persists in: nothing

Owner, 2026-09-26: « identifier tous les graphiques (grafana + streamlytics), y associer une note
d'impact et de pertinence ». The review is a file I wrote after LOOKING at each chart; this keeps
it complete — a figure site, a PDF chart or a Grafana panel added without a graded entry turns
this red, and so does a grade outside its scale.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
_DOSSIER = _ROOT / "tools" / "dev" / "charts_dossier"
_VERDICTS = {"garder", "corriger", "fusionner", "retirer", "a-trancher"}
_ROLES = {"meta", "plateforme", "prediction", "archi", "business"}


def _review() -> dict:
    with open(_DOSSIER / "review.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _pdf_chart_keys(tree: ast.AST) -> set[str]:
    """Keys of the `charts = {...}` dict literal of the report — read from its AST."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "charts"
                                                  for t in node.targets)
                and isinstance(node.value, ast.Dict)):
            return {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    return set()


def _grafana_ids(dashboard: dict) -> set[str]:
    return {f"grafana:{p['id']}" for p in dashboard.get("panels", [])}


def problems(review: dict, sites: set[str], pdf_keys: set[str], panels: set[str]) -> list[str]:
    """What is missing or out of scale. Pure."""
    expected = sites | {f"pdf:{k}" for k in pdf_keys} | panels
    out = [f"sans revue : {k}" for k in sorted(expected - set(review))]
    out += [f"revue d'un graphique qui n'existe plus : {k}" for k in sorted(set(review) - expected)]
    for k, r in review.items():
        r = r or {}
        for axis in ("d", "c", "p"):
            if not isinstance(r.get(axis), int) or not 1 <= r[axis] <= 5:
                out.append(f"{k} : note {axis}={r.get(axis)!r} hors de 1–5")
        if r.get("v") not in _VERDICTS:
            out.append(f"{k} : verdict {r.get('v')!r} inconnu")
        if r.get("role") not in _ROLES:
            out.append(f"{k} : rôle {r.get('role')!r} inconnu")
        if not (r.get("q") and r.get("note")):
            out.append(f"{k} : question ou note vide")
        if "owner_v" in r and r["owner_v"] not in _VERDICTS:
            out.append(f"{k} : ton verdict {r['owner_v']!r} inconnu")
        if "cause" in r and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(r["cause"])):
            out.append(f"{k} : cause {r['cause']!r} pas en kebab-case")
    return out


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    ok = {"q": "?", "note": "vu", "role": "meta", "d": 3, "c": 3, "p": 3, "v": "garder"}
    review = {"a.py:1": ok, "pdf:roi": ok, "grafana:1": ok}
    assert problems(review, {"a.py:1"}, {"roi"}, {"grafana:1"}) == []
    assert problems(review, {"a.py:1", "b.py:9"}, {"roi"}, {"grafana:1"}) == ["sans revue : b.py:9"]
    assert problems({**review, "grafana:1": {**ok, "d": 6}}, {"a.py:1"}, {"roi"}, {"grafana:1"})
    assert problems({**review, "pdf:roi": {**ok, "v": "peut-être"}}, {"a.py:1"}, {"roi"},
                    {"grafana:1"})
    assert problems(review, set(), {"roi"}, {"grafana:1"}) == [
        "revue d'un graphique qui n'existe plus : a.py:1"]
    tree = ast.parse("charts = {'roi': f(), 'meta': g()}\nother = {'x': 1}\n")
    assert _pdf_chart_keys(tree) == {"roi", "meta"}


def test_every_chart_has_its_graded_review() -> None:
    sys.path.insert(0, str(_DOSSIER))
    import inventory
    sites = {s["site"] for s in inventory.sites() if s["kind"] == "figure"}
    report = _ROOT / "src" / "dashboard" / "utils" / "pdf_exporter" / "_report.py"
    with open(report, encoding="utf-8") as fh:
        pdf_keys = _pdf_chart_keys(ast.parse(fh.read()))
    with open(_ROOT / "deploy/grafana/dashboards/streamlytics-ops.json", encoding="utf-8") as fh:
        panels = _grafana_ids(json.load(fh))
    assert sites and pdf_keys and panels, "an inventory came back empty"
    found = problems(_review(), sites, pdf_keys, panels)
    assert not found, (
        "the charts review (tools/dev/charts_dossier/review.yaml) is incomplete — LOOK at the "
        "chart (`make charts-dossier`) and grade it:\n  " + "\n  ".join(found))


# ── R204 : les retours du propriétaire ──────────────────────────────────────────────

def _tools():
    sys.path.insert(0, str(_DOSSIER))
    import apply_comments
    import triage
    return apply_comments, triage


def test_a_comment_lands_on_its_chart_or_nothing_is_written() -> None:
    """Unknown fiche or verdict ⇒ refused, and NOTHING is written; my grade is never touched."""
    ac, _ = _tools()
    fiches = {1: "a.py:1", 2: "b.py:2"}
    updates, errors = ac.plan({1: {"v": "Retirer", "texte": "inutile"}}, fiches)
    assert updates == {"a.py:1": {"owner_v": "retirer", "owner": "inutile"}} and errors == []
    _, errors = ac.plan({9: {"v": "garder"}}, fiches)
    assert errors and "fiche 9 inconnue" in errors[0]
    _, errors = ac.plan({1: {"v": "peut-être"}}, fiches)
    assert errors, "a verdict outside the set was accepted"
    before = 'a.py:1:\n  q: "?"\n  v: corriger\n  note: "mien"\n'
    after = ac.write(before, {"a.py:1": {"owner_v": "retirer", "owner": 'dit "non"'}})
    assert '  note: "mien"' in after and "  v: corriger" in after, "my grade was overwritten"
    assert '  owner: "dit \\"non\\""' in after and "  owner_v: retirer" in after
    again = ac.write(after, {"a.py:1": {"owner_v": "garder", "owner": "revu"}})
    assert again.count("owner_v:") == 1 and "owner_v: garder" in again, "a second pass duplicated"


def test_the_triage_groups_by_cause_and_flags_disagreements() -> None:
    _, tr = _tools()
    review = {
        "a.py:1": {"q": "a", "v": "corriger", "c": 1, "role": "plateforme", "cause": "zero"},
        "b.py:2": {"q": "b", "v": "corriger", "c": 3, "role": "meta", "cause": "zero",
                   "owner_v": "garder", "owner": "c'est juste"},
        "c.py:3": {"q": "c", "v": "garder", "c": 4, "role": "archi"},
        "d.py:4": {"q": "d", "v": "garder", "c": 4, "role": "meta", "owner_v": "retirer"},
    }
    groups = tr.table(review, {"a.py:1": 1, "b.py:2": 2, "c.py:3": 3, "d.py:4": 4})
    by = {g["cause"]: g for g in groups}
    assert set(by) == {"zero", "sans-cause"}, "a chart with nothing to act on entered the table"
    assert [e["fiche"] for e in by["zero"]["rows"]] == [1, 2]
    assert by["zero"]["disagreements"] == 1 and by["sans-cause"]["disagreements"] == 1
    assert groups[0]["cause"] == "zero", "a probably WRONG number must come first"
    assert "c'est juste" in tr.render(groups)
