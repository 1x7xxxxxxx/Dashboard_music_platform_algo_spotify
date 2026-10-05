"""R356 — the harness report turns every state of benchmark.json into something visible.

Type: Test
Uses: tools/dev/harness_report.py (opportunities, summary, render)
Depends on: nothing live — a synthetic benchmark payload
Persists in: nothing

What must hold:
1. a red proof, a hole, a measured opportunity, a stale seen-red, an unproven green and a
   component never invoked each become an opportunity — none may vanish from the page;
2. a 0 that carries a `note` (a silent hook, a log younger than the transcripts) is NOT a
   « never invoked » opportunity: the counter cannot conclude « never »;
3. the payload is embedded so that a `</script>` in a statement cannot close the script.

Mutation record (2026-10-04): seen red with the unproven-green branch removed, with the
`note` exemption removed from the « jamais invoqué » branch, and with the `</` escape dropped.

R416 — the count is the point: only what calls for a gesture is an opportunity. A hole
deferred by an ADR, a dormant and a manual component go to the inventory; a dormant a hook
SUGGESTED to the model is « suivi manqué », back among the opportunities.
Mutations, 2026-10-05: the `differe` branch, the inventory filter, the `suggested` branch
and the `.` of the slash predicate's lookbehind removed → RED each. The last one stayed
GREEN until `../curator` joined the fixture: a path the `.` alone excludes.
Not covered: a suggestion phrased without the slash (« load the airflow-dag skill »).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("harness_report",
                                               ROOT / "tools/dev/harness_report.py")
hr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hr)


def _req(i: str, etat: str, **kw) -> dict:
    return {"id": i, "domaine": "d", "enonce": f"énoncé {i}", "etat": etat, "portee": "generique",
            "methode": "commit", "vu_rouge": None, "opportunite": None, "a_ecrire": None, **kw}


def _data() -> dict:
    return {"genere_depuis": "abc 2026-10-04 x", "rejoue": True, "activite_mesuree": True,
            "seances": 3, "domaines": {"d": {"nom": "D"}},
            "exigences": [
                _req("R-RED", "rouge"), _req("R-HOLE", "trou", a_ecrire="écrire X"),
                _req("R-LATER", "trou", a_ecrire="écrire Y", differe="ADR-030 — le fan-out"),
                _req("R-OPP", "active", opportunite="gagner 3 s"),
                _req("R-STALE", "active", vu_rouge={"date": "2026-01-01", "perime": True}),
                _req("R-GREEN", "verte, non prouvée"),
                _req("R-JS", "active", enonce="</script><b>x"),
            ],
            "composants": {
                ".claude/agents/idle.md": {"exigences": ["R-OPP"],
                                           "activite": {"kind": "agent", "n": 0, "last": None}},
                ".claude/hooks/mute.py": {"exigences": ["R-OPP"],
                                          "activite": {"kind": "hook", "n": 0, "last": None,
                                                       "note": "aucune trace"}},
                ".claude/commands/waits.md": {"exigences": ["R-OPP"], "declencheurs": [".claude/hooks/x.py"],
                                              "activite": {"kind": "command", "n": 0, "last": None}},
                ".claude/commands/byhand.md": {"exigences": ["R-OPP"], "declencheurs": [],
                                               "manuel": "audit lancé par le propriétaire",
                                               "activite": {"kind": "command", "n": 0, "last": None}},
                ".claude/commands/nagged.md": {"exigences": ["R-OPP"], "declencheurs": [".claude/hooks/x.py"],
                                               "activite": {"kind": "command", "n": 0, "last": None,
                                                            "suggere": 40}},
                ".claude/workflows/young.md": {"exigences": ["R-OPP"], "activite": {
                    "kind": "playbook", "n": 0, "last": None, "note": "journal depuis R357"}},
            }}


def _types(items: list[dict]) -> set[tuple[str, str]]:
    return {(o["type"], o["ref"]) for o in items}


def test_every_state_becomes_an_opportunity() -> None:
    types = _types(hr.opportunities(_data()))
    for expected in [("preuve rouge", "R-RED"), ("trou", "R-HOLE"), ("mesurée", "R-OPP"),
                     ("vu rouge périmé", "R-STALE"), ("à muter", "1 exigences"),
                     ("orphelin", ".claude/agents/idle.md"),
                     ("suivi manqué", ".claude/commands/nagged.md")]:
        assert expected in types, expected
    assert not any(ref in (".claude/hooks/mute.py", ".claude/workflows/young.md")
                   for _, ref in types | _types(hr.inventory(_data())))


def test_what_waits_is_inventory_never_an_opportunity() -> None:
    waiting = {("différé", "R-LATER"), ("dormant", ".claude/commands/waits.md"),
               ("manuel", ".claude/commands/byhand.md")}
    assert waiting <= _types(hr.inventory(_data()))
    assert not waiting & _types(hr.opportunities(_data()))
    assert not {ref for _, ref in waiting} & {ref for _, ref in _types(hr.opportunities(_data()))}


def test_a_hook_suggestion_counts_the_slash_form_only() -> None:
    spec = importlib.util.spec_from_file_location("usage_report", ROOT / ".claude/scripts/usage_report.py")
    ur = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ur)
    acc = ur._empty()
    ur._scan_hook(acc, {"type": "hook_success", "command": "x", "stdout": "run /retro twice: /retro",
                        "content": "📝 .claude/skills/airflow-dag.rex.md changed; see a/sweep/b; cd ../curator"}, None)
    assert acc["suggested"] == {"retro": 1}, acc["suggested"]


def test_the_page_embeds_the_payload_safely() -> None:
    page = hr.render(_data())
    assert "{{DATA}}" not in page and "{{COMMIT}}" not in page
    blob = page.split("const P = ", 1)[1].split(";\nconst D", 1)[0]
    assert "</script>" not in blob
    assert json.loads(blob)["data"]["exigences"][-1]["enonce"] == "</script><b>x"
    assert hr.summary(_data())["etats"]["active"] == 3
