"""R257 — every note of the owner that is neither delivered nor obsolete points at a REAL
roadmap line: an open row (index or « en attente de toi »), an archived one, or a row of the
product backlog.

Type: Test
Uses: .claude/dev-docs/architecture/notes-triage.yaml, .claude/dev-docs/roadmap/{checklist,
      archive}.md, .claude/dev-docs/product-backlog.md, tools/dev/charts_dossier/main.py

Owner, 2026-09-27 : « vérifier qu'elles ont toutes été traduites en action dans la roadmap ».
The KPI dossier got this guard with R254; the architecture notes get the same one, reusing
its readers instead of a third way of parsing the roadmap.
"""
import importlib.util
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
_D = ROOT / "tools/dev/charts_dossier"
STILL_OPEN = {"partiel", "ouvert", "décision-requise"}
STATUTS = STILL_OPEN | {"livré", "obsolète"}


def _main():
    sys.path.insert(0, str(_D))
    spec = importlib.util.spec_from_file_location("dossier_main_notes", _D / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _text(rel: str) -> str:
    with open(ROOT / rel, encoding="utf-8") as fh:
        return fh.read()


def known_ids() -> set[str]:
    m = _main()
    checklist = _text(".claude/dev-docs/roadmap/checklist.md")
    backlog = set(re.findall(r"^\| (R\d+) \|", _text(".claude/dev-docs/product-backlog.md"), re.M))
    return (m.open_roadmap_ids(checklist)
            | m.archived_roadmap_ids(_text(".claude/dev-docs/roadmap/archive.md")) | backlog)


def unrouted(items: list[dict], ids: set[str]) -> list[str]:
    """Notes still to do whose roadmap id is missing or names no real line. Pure."""
    return [f"L{i.get('ligne')} « {str(i.get('resume'))[:60]} » → {i.get('roadmap') or 'aucune ligne'}"
            for i in items if i.get("statut") in STILL_OPEN and i.get("roadmap") not in ids]


def _items() -> list[dict]:
    with open(ROOT / ".claude/dev-docs/architecture/notes-triage.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_every_note_still_to_do_names_a_real_roadmap_line():
    items = _items()
    assert len(items) >= 300, "the triage was emptied"
    assert {i["statut"] for i in items} <= STATUTS, {i["statut"] for i in items} - STATUTS
    bad = unrouted(items, known_ids())
    assert not bad, "notes hors roadmap :\n" + "\n".join(bad)


def test_a_delivered_note_says_what_proves_it():
    bare = [i["ligne"] for i in _items() if i["statut"] == "livré"
            and str(i.get("preuve_statut", "—")).strip() in ("", "—")]
    assert not bare, f"notes livrées sans preuve : {bare}"


def test_the_detector_sees_a_note_without_a_line_or_with_a_ghost_one():
    ids = known_ids()
    assert unrouted([{"ligne": 1, "resume": "x", "statut": "ouvert"}], ids)
    assert unrouted([{"ligne": 1, "resume": "x", "statut": "partiel", "roadmap": "R9999"}], ids)
    assert not unrouted([{"ligne": 1, "resume": "x", "statut": "livré"}], ids)
    assert not unrouted([{"ligne": 1, "resume": "x", "statut": "ouvert",
                          "roadmap": sorted(ids)[0]}], ids)
