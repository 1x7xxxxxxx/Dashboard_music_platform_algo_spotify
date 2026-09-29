"""A `recurrence:` ticket is proposed only for a red that ran on a committed, clean tree.

Type: Sub
Uses: .claude/scripts/defect_capture.py (tree_states), tools/dev/defect_log.py (classify)
Depends on: nothing — fabricated events

R336 (2026-09-29): `make defect-log` proposed 32 tickets and triage (R328) confirmed none —
~21 were gates red on the author's own uncommitted edit. The tree state is stamped PER EVENT
(code-critic R336): a red followed by a fix and a commit in the same turn is `unknown`, not
`clean`, which is the false positive the stamp exists to remove.

Mutation record (2026-09-29): seen red with `last_commit <= at` turned into `>=`, and with
`classify` proposing from every returned day instead of the clean ones.
"""
import importlib.util
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dc = _load(".claude/scripts/defect_capture.py", "defect_capture")
dl = _load("tools/dev/defect_log.py", "defect_log")
T = "2026-09-29T10:00:00+00:00"
AT = datetime.fromisoformat(T).timestamp()


def _red(ts: str = T) -> dict:
    return {"kind": "test_red", "fingerprint": "test:tests/test_x.py::t", "ts": ts}


def test_each_red_carries_the_tree_it_ran_on() -> None:
    cases = [(True, AT - 60, "wip"), (False, AT - 60, "clean"),
             (False, AT + 60, "unknown"),        # committed AFTER the red, same turn
             (None, None, "unknown")]            # git unreadable, or backfill
    for dirty, last_commit, expected in cases:
        ev = [_red(), {"kind": "test_green", "ts": T}]
        dc.tree_states(ev, dirty, last_commit)
        assert ev[0]["tree"] == expected, (dirty, last_commit)
        assert "tree" not in ev[1], "only reds are stamped"


def _events(tree: "str | None") -> list[dict]:
    red1 = dict(_red("2026-09-27T10:00:00+00:00"), session="s", excerpt="x")
    green = {"kind": "test_green", "ts": "2026-09-27T12:00:00+00:00", "session": "s",
             "scope": "files", "files": ["tests/test_x.py"]}
    red2 = dict(_red("2026-09-28T10:00:00+00:00"), session="s", excerpt="x")
    if tree:
        red2["tree"] = tree
    return [red1, green, red2]


def test_only_a_clean_return_proposes_a_ticket() -> None:
    [row] = dl.classify(_events("clean"))
    assert row["recurrence_proposal"] == "recurrence:2026-09-27,2026-09-28"
    for tree in ("wip", "unknown", None):          # None: an event written before R336
        [row] = dl.classify(_events(tree))
        assert row["recurrence_proposal"] is None, tree
        assert row["returned_unvouched"] == ["2026-09-28"], "it is still listed, without a ticket"
