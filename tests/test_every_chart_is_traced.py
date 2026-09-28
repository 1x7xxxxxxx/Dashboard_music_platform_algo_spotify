"""R299 — every chart is traced: its Meta Ads question, its twins reviewed.

Type: Test
Uses: pytest, yaml
Depends on: tools/dev/charts_dossier/questions.py (MQ, SHARED_REVIEWED, shared_source_groups,
            rows), tools/dev/charts_dossier/inventory.py, tools/dev/charts_dossier/review.yaml
Persists in: nothing

The owner's goal (2026-09-28): no duplicate KPI, every chart tied to a Meta Ads marketing
question, one table in the PDF with duplicates highlighted. Three merges were found that
day by grouping the figures of a page on their SOURCES — the (page, sources, measure) twin
of R207 saw none of them, because each pair plotted one measure under two column names.

What is held:
- every `role: meta` fiche names one question of the closed list, and no other fiche does
  (the other roles already classify them — code-critic);
- every (page, sources) group of ≥ 2 figures carries a verdict, looked at — a new group
  fails until reviewed;
- the detector sees a planted group and spares a single figure; a « faux doublon » is not
  highlighted, a real one is.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / "tools" / "dev" / "charts_dossier"
sys.path.insert(0, str(DOSSIER))

import questions  # noqa: E402


def _review() -> dict:
    return yaml.safe_load((DOSSIER / "review.yaml").read_text(encoding="utf-8"))


def test_every_meta_fiche_names_a_marketing_question_and_only_those() -> None:
    bad = [f"{k}: {r.get('mq')!r}" for k, r in _review().items()
           if (r.get("role") == "meta") != (r.get("mq") in questions.MQ)]
    assert not bad, ("a Meta fiche without a question of MQ, or a non-Meta fiche with one "
                     "(tools/dev/charts_dossier/review.yaml `mq:`):\n  " + "\n  ".join(bad))


def test_every_group_of_figures_sharing_a_page_and_its_sources_was_reviewed() -> None:
    import inventory
    found = set(questions.shared_source_groups(inventory.sites()))
    new = found - set(questions.SHARED_REVIEWED)
    assert not new, ("figures of one page reading the same sources, not reviewed: "
                     f"{[sorted(g) for g in new]} — LOOK at them: merge the repeat, or record "
                     "the verdict in questions.SHARED_REVIEWED")
    stale = set(questions.SHARED_REVIEWED) - found
    assert not stale, f"reviewed groups that no longer exist: {[sorted(g) for g in stale]}"


def test_a_merged_fiche_is_gone_from_the_review() -> None:
    import json
    fiches = DOSSIER.parent.parent.parent / "revue" / "fiches.json"
    review = _review()
    carriers = {b for _a, b, _w in questions.MERGED}
    assert carriers and all(isinstance(n, int) for n in carriers)
    if fiches.exists():   # the fiche map is local (the dossier is gitignored)
        m = json.loads(fiches.read_text(encoding="utf-8"))
        for a, _b, _w in questions.MERGED:
            assert m.get(str(a), "").startswith("retired:") or m.get(str(a)) not in review


def test_the_detector_sees_a_group_and_spares_a_lone_figure_not_vacuous() -> None:
    inv = [{"kind": "figure", "site": "p.py:1", "key": "p.py::a#1", "sources": ["t"]},
           {"kind": "figure", "site": "p.py:9", "key": "p.py::b#1", "sources": ["t"]},
           {"kind": "figure", "site": "p.py:20", "key": "p.py::c#1", "sources": ["u"]},
           {"kind": "figure", "site": "q.py:1", "key": "q.py::a#1", "sources": ["t"]}]
    assert questions.shared_source_groups(inv) == [frozenset({"p.py::a#1", "p.py::b#1"})]


def test_a_false_twin_is_not_highlighted_and_a_real_one_is(monkeypatch) -> None:
    review = {"a#1": {"q": "a", "role": "meta", "mq": "M2"}, "b#1": {"q": "b", "role": "meta",
              "mq": "M2"}, "c#1": {"q": "c", "role": "archi"}, "d#1": {"q": "d", "role": "archi"}}
    monkeypatch.setattr(questions, "SHARED_REVIEWED",
                        {frozenset({"c#1", "d#1"}): ("faux doublon — deux mesures", frozenset())})
    got = {r["key"]: r for r in questions.rows(
        review, {}, {"a#1": 1, "b#1": 2, "c#1": 3, "d#1": 4}, {},
        [frozenset({"a#1", "b#1"}), frozenset({"c#1", "d#1"})], [])}
    assert got["a#1"]["twin"] and got["b#1"]["twin"], "a real twin is not highlighted"
    assert not got["c#1"]["twin"] and "faux doublon" in got["c#1"]["twin_note"]
    assert "REQ-CHART-04" in got["a#1"]["reqs"] and "REQ-CHART-04" not in got["c#1"]["reqs"]


def test_silver_is_said_only_where_a_source_names_it() -> None:
    silver = [questions.SILVER_PREFIX + "cumulative_by_platform", "v_x"]
    assert questions.layer_label("or", sources=silver) == "argent + or"
    assert questions.layer_label("or", sources=["v_x"]) == "or"
    assert questions.layer_label("—", role="business") == "état de l'app"
    assert questions.layer_label("—", role="meta").startswith("non tracée")
    assert "REQ-SILVER-01" in questions.requirements("argent + or", False, False)


def test_two_charts_answering_one_question_on_one_page_are_flagged() -> None:
    trace = [{"mq": "M7", "page": "breakdowns", "no": 1}, {"mq": "M7", "page": "breakdowns",
             "no": 2}, {"mq": "M7", "page": "x", "no": 3}, {"mq": "M1", "page": "x", "no": 4}]
    by = {x["code"]: x for x in questions.per_question(trace)}
    assert by["M7"]["same_page"] == {"breakdowns": 2} and by["M1"]["same_page"] == {}
    assert by["M3"]["fiches"] == [], "a question with no chart must be listed, not dropped"
