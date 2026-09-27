"""R254 — every action of the KPI dossier points at a REAL roadmap row.

Type: Test
Uses: tools/dev/charts_dossier/actions.yaml, tools/dev/charts_dossier/main.py,
      .claude/dev-docs/roadmap/{checklist,archive}.md

Until 2026-09-27 an action read « ✅ fait » as soon as its id was ABSENT from the open
index — a mistyped id, or one never registered, was absent too. And the owner's own
gestures (fiches 62, 66) carried no id at all: they lived outside every roadmap table.
"""
import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
_D = ROOT / "tools/dev/charts_dossier"


def _main():
    sys.path.insert(0, str(_D))
    spec = importlib.util.spec_from_file_location("dossier_main", _D / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _text(rel: str) -> str:
    with open(ROOT / rel, encoding="utf-8") as fh:        # markdown, not code
        return fh.read()


def _state():
    m = _main()
    checklist = _text(".claude/dev-docs/roadmap/checklist.md")
    with open(_D / "actions.yaml", encoding="utf-8") as fh:
        acts = yaml.safe_load(fh)
    return (m, acts, m.open_roadmap_ids(checklist),
            m.archived_roadmap_ids(_text(".claude/dev-docs/roadmap/archive.md")),
            m.waiting_ids(checklist))


def test_every_dossier_action_names_a_real_roadmap_row():
    m, acts, open_ids, done, waiting = _state()
    assert done, "the archive reader found no delivered id — it is reading nothing"
    bad = m.unknown_actions(acts, open_ids, done, waiting)
    assert not bad, "actions outside the roadmap:\n" + "\n".join(bad)


def test_the_detector_sees_a_ghost_id_and_a_gesture_outside_the_waiting_table():
    m, _, open_ids, done, waiting = _state()
    ghost = {"f": {"actions": [{"qui": "moi", "texte": "x", "rid": "R9999"}]}}
    assert m.unknown_actions(ghost, open_ids, done, waiting)
    stray = {"f": {"actions": [{"qui": "toi", "texte": "x", "rid": "R254"}]}}
    assert m.unknown_actions(stray, open_ids | {"R254"}, done, waiting - {"R254"}), (
        "an owner's gesture on an index row (not the 🙋 table) went unseen")
    fine = {"f": {"actions": [{"qui": "moi", "texte": "x", "rid": sorted(done)[0]}]}}
    assert not m.unknown_actions(fine, open_ids, done, waiting)


def test_done_is_read_in_the_archive_not_deduced_from_absence():
    m = _main()
    assert m.action_state("R9999", {"R1"}, {"R2"}) == "inconnu"
    assert m.action_state("R2", {"R1"}, {"R2"}) == "fait"
    assert m.action_state("R1", {"R1"}, {"R2"}) == "ouvert"
