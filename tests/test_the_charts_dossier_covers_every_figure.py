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
        if "absent" in r and not str(r["absent"]).startswith(("code mort — ", "donnée absente — ")):
            out.append(f"{k} : absent doit dire « code mort — » ou « donnée absente — »")
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
    sites = {s["key"] for s in inventory.sites() if s["kind"] == "figure"}
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


# ── R240 : les actions de chaque fiche, et les validées en fin de dossier ─────────────

def _main():
    sys.path.insert(0, str(_DOSSIER))
    import main
    return main


def test_a_fiche_goes_where_its_actions_say() -> None:
    """Validated → end; all my actions archived → « à revalider » (never validated by me);
    an open action, or one of the owner's, keeps it « à faire »."""
    m = _main()
    open_ids = {"R242"}
    assert m.status({"valide": True, "actions": []}, open_ids) == "valide"
    assert m.status(None, open_ids) == "sans-avis"
    done = {"actions": [{"qui": "moi", "texte": "x", "rid": "R241"}]}
    assert m.status(done, open_ids) == "revalider"
    assert m.status({"actions": [{"qui": "moi", "texte": "x", "rid": "R242"}]}, open_ids) == "a-faire"
    mine_and_yours = {"actions": [*done["actions"], {"qui": "toi", "texte": "saisir"}]}
    assert m.status(mine_and_yours, open_ids) == "a-faire", "the owner's own action was ignored"


def test_the_open_ids_are_read_from_the_index_rows() -> None:
    m = _main()
    text = "| R240 | a | P2 | m |\n| R241 | b | P2 | m |\ntexte R999 dans une phrase\n"
    assert m.open_roadmap_ids(text) == {"R240", "R241"}


def test_an_action_names_who_and_a_real_roadmap_id() -> None:
    ac, _ = _tools()
    fiches = {1: "a.py:1", 2: "b.py:2"}
    ok, errors = ac.plan_actions({1: {"v": "garder", "valide": True},
                                  2: {"v": "corriger", "actions": [
                                      {"qui": "moi", "texte": "x", "rid": "R241"}]}}, fiches)
    assert not errors and ok["a.py:1"]["valide"] and ok["b.py:2"]["actions"][0]["rid"] == "R241"
    _, errors = ac.plan_actions({2: {"actions": [{"qui": "lui", "texte": "x"}]}}, fiches)
    assert errors
    _, errors = ac.plan_actions({2: {"actions": [{"qui": "moi", "texte": "x", "rid": "241"}]}}, fiches)
    assert errors
    _, errors = ac.plan_actions({1: {"valide": True, "actions": [{"qui": "moi", "texte": "x"}]}}, fiches)
    assert errors, "a fiche both validated and carrying actions was accepted"


def test_a_fiche_keeps_its_number_when_another_is_retired() -> None:
    """R242 — retiring fiche 2 must not turn fiche 3 into fiche 2 (the owner dictates by number)."""
    m = _main()
    previous = {"a": 1, "b": 2, "c": 3}
    assert m.numbering({"a": 0, "c": 0}, previous) == {"a": 1, "c": 3}
    assert m.numbering({"a": 0, "c": 0, "d": 0}, previous)["d"] == 4, "a burnt number was reused"
    assert m.numbering({"x": 0, "y": 0}) == {"x": 1, "y": 2}


def test_a_hidden_branch_is_opened_by_its_widget() -> None:
    """R242 — the capture flips the widget that hides a branch, by key or by label."""
    sys.path.insert(0, str(_DOSSIER))
    import capture

    class W:
        def __init__(self, key, label):
            self.key, self.label, self.value = key, label, None

        def set_value(self, v):
            self.value = v

    class AT:
        toggle = [W("home_trend_cumul_1", "Cumulé")]
        selectbox = [W(None, "Métrique")]

    at = AT()
    assert capture.apply_variant(at, "toggle", "home_trend_cumul_1", True)
    assert at.toggle[0].value is True
    assert capture.apply_variant(at, "selectbox", "Métrique", "Engagement")
    assert not capture.apply_variant(at, "selectbox", "Absent", "x")
    assert "meta_breakdowns" in capture.VARIANTS


def test_a_chart_without_an_image_must_say_why() -> None:
    m = _main()
    review = {"a.py::f#1": {}, "b.py::g#1": {"absent": "code mort — rien ne l'appelle"},
              "grafana:1": {}, "pdf:x": {}}
    assert m.unexplained(review, rendered=set()) == ["a.py::f#1"]
    assert m.unexplained(review, rendered={"a.py::f#1"}) == []


def test_the_airflow_replay_answers_what_production_answered() -> None:
    """R242 — fiches 74–76: the API is recorded in production and replayed by path+params."""
    sys.path.insert(0, str(_DOSSIER))
    import airflow_replay as ar
    key = ar.request_key("GET", "http://airflow-webserver:8080/api/v1/dags", {"limit": 100})
    s = ar.ReplaySession({key: [200, {"dags": [{"dag_id": "x"}]}]})
    local = s.get("http://127.0.0.1:18080/api/v1/dags", params={"limit": 100})
    assert local.status_code == 200 and local.json()["dags"][0]["dag_id"] == "x", "host must not matter"
    assert s.get("http://h/api/v1/dags", params={"limit": 5}).status_code == 404
    assert "key(\"GET\", url, params)" in ar.RECORDER and "/api/v1" in ar.RECORDER, (
        "the recorder no longer keys requests the way the replay reads them")
