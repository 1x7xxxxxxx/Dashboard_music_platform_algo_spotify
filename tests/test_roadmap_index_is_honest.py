"""The open-task index must answer one question: what can I start right now?

Installed 2026-08-21, when that index emptied for the first time.

`/resume` and `/sprint` read `## 📋 Tâches ouvertes` to decide what to work on. For
months it also held items that could not be started by anyone reading it — four
measured unnecessary (ADR-007), six waiting on an input that does not exist
(ADR-008), five waiting on a human. Mixed together, an empty engineering queue
looked like a backlog nobody was burning down, and the items that *were*
actionable were harder to see.

The file now separates them:

    ## 📋 Tâches ouvertes        — startable today, by whoever is reading
    ## 🙋 En attente de toi      — blocked on a human action, named per row

That split is only worth having if it stays true. This pins the three ways it
could quietly stop being:

  * both sections exist (a rename would silently drop one);
  * no id sits in both (a row copied instead of moved reports twice);
  * every waiting row names the gesture it waits on, rather than a status.

It deliberately does NOT assert that the actionable index is empty. Empty is
today's state, not a goal — a task landing there tomorrow is the system working.
"""
from __future__ import annotations

import re
from pathlib import Path


def _repo_root() -> Path:
    for d in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ found above this test")


REPO = _repo_root()
ACTIVE = REPO / ".claude" / "dev-docs" / "roadmap" / "checklist.md"

_ACTIONABLE_H = "## 📋 Tâches ouvertes"
_WAITING_H = "## 🙋 En attente de toi"
_ROW = re.compile(r"^\| (R\d+) \|(.*)$")


def _section(name: str) -> list[str]:
    """Lines between this heading and the next `## ` one.

    Anchored at line start on purpose. A plain `text.index(name)` finds the first
    OCCURRENCE, and both headings are also mentioned in the intro prose two
    paragraphs above ("… est dans `## 🙋 En attente de toi` juste en dessous").
    That match lands before the real heading, so the extracted section is the
    intro and contains no rows — and every assertion below passes on an empty
    list. This test shipped that way for about ten minutes on 2026-08-21;
    `test_the_sections_are_not_empty` is what caught it, and is why it exists.
    """
    text = ACTIVE.read_text(encoding="utf-8")
    m0 = re.search(rf"^{re.escape(name)}", text, re.M)
    assert m0, f"heading {name!r} not found at the start of a line"
    rest = text[m0.end():]
    m = re.search(r"^## ", rest, re.M)
    return (rest[: m.start()] if m else rest).splitlines()


def _ids(name: str) -> list[str]:
    return [m.group(1) for line in _section(name) if (m := _ROW.match(line))]


def test_the_sections_are_not_empty():
    """Non-vacuity. Without this, every assertion below is true of nothing.

    The extraction reads a markdown file by heading; a heading that also appears
    in prose, a rename, or a reordering all produce an empty list rather than an
    error. An empty list satisfies `assert not offenders` perfectly.
    """
    total = len(_ids(_ACTIONABLE_H)) + len(_ids(_WAITING_H))
    assert total > 0, (
        "neither roadmap section yielded a single row. Either every item is "
        "genuinely gone — in which case delete this test — or the extraction is "
        "matching the wrong place and every check here is passing on nothing."
    )


def test_both_sections_exist():
    text = ACTIVE.read_text(encoding="utf-8")
    for heading in (_ACTIONABLE_H, _WAITING_H):
        assert heading in text, (
            f"{heading!r} is gone from checklist.md. The split between what can be "
            "started and what waits on a human is what makes the index readable at "
            "`/resume`; a rename drops one half silently."
        )


def test_no_item_is_in_both_sections():
    """A row copied rather than moved reports the same work twice."""
    both = set(_ids(_ACTIONABLE_H)) & set(_ids(_WAITING_H))
    assert not both, (
        f"{sorted(both)} appear in both sections. Moving is not copying — the same "
        "rule the two-file roadmap already enforces, one level down."
    )


RUNBOOK = REPO / ".claude" / "dev-docs" / "runbook-actions-utilisateur.md"

# A waiting row's id must appear in a runbook heading. `~~R20~~` (struck through,
# done) counts: the procedure is still written, and a row that comes back finds it.
_RUNBOOK_HEADING = re.compile(r"^#{2,3} .*\b(R\d+)\b", re.M)


def _documented_ids() -> set[str]:
    if not RUNBOOK.exists():
        return set()
    return set(_RUNBOOK_HEADING.findall(RUNBOOK.read_text(encoding="utf-8")))


def test_every_waiting_row_names_the_gesture_it_waits_on():
    """'BLOQUÉ' is a status. 'Regenerate the token in Business Manager' is a gesture.

    The whole reason these rows are out of the actionable index is that a person has
    to act. A row that does not say which act is back to being a status that never
    changes.

    HOW this is checked changed on 2026-08-22, and the change matters more than the
    rule. The first version matched the row against ten hand-written French verbs
    (`Régénérer|Créer|déposer|…`). R22 — "external network intrusion test, endpoint
    fuzzing, `pip install pip-audit && pip-audit -r requirements.txt`" — names three
    gestures, one of them a literal shell command, and used none of those ten words.
    The guard failed a row that was doing exactly what it asked for.

    A hand-written scope is a scope that goes stale silently: it can only recognise
    the phrasings that existed the day it was written, and it says nothing when a new
    one appears. That is the second time in one night this class shipped (see
    `## 🔖 REPRISE`), so the predicate is now structural instead:

        a waiting row must have a section in the runbook, keyed by its id.

    The runbook is where the steps AND their verification live, so this asks for the
    thing that is actually useful rather than for a word. It also cannot be satisfied
    by rewording the row.
    """
    documented = _documented_ids()
    undocumented = [
        m.group(1) for line in _section(_WAITING_H)
        if (m := _ROW.match(line)) and m.group(1) not in documented
    ]
    assert not undocumented, (
        f"{undocumented} sit in « En attente de toi » with no section in "
        f"{RUNBOOK.name}. The index says a person has to act; the runbook is where "
        "the steps and the command that proves it worked are written. Without one, "
        "the row is a status that will never change."
    )


def test_the_actionable_index_says_what_it_is_for():
    """Its intro is the contract the two `/` commands rely on."""
    body = "\n".join(_section(_ACTIONABLE_H))
    assert "commencer maintenant" in body, (
        "the index no longer states that it holds work startable today — which is "
        "the only property `/resume` and `/sprint` actually need from it."
    )


def test_the_roadmap_never_states_two_different_test_counts() -> None:
    """Two summary paragraphs, two numbers, and the reader believes the first one.

    Measured 2026-08-21: rewriting the resume header left the previous paragraph
    in place underneath. The file then claimed, four lines apart, "920 colonnes /
    92 tables · 1067 tests verts" and "917 colonnes / 91 tables · 900 tests verts",
    plus "trois items" against "cinq items".

    This is the file `/resume` reads FIRST, so a stale number here is not cosmetic:
    it is the state a session starts from. Contradiction is checkable without
    knowing which number is right — and a document that disagrees with itself is
    wrong whichever half you trust.
    """
    text = ACTIVE.read_text(encoding="utf-8")

    counts = set(re.findall(r"\*\*([\d\s]{3,7}) tests verts\*\*", text))
    normalised = {c.replace(" ", "").replace(" ", "") for c in counts}
    assert len(normalised) <= 1, (
        f"the roadmap states {len(normalised)} different test counts: "
        f"{sorted(normalised)}. Whichever is right, the file contradicts itself — "
        "and this is the first thing /resume reads."
    )

    tables = set(re.findall(r"(\d{2,4}) colonnes / (\d{1,3}) tables", text))
    assert len(tables) <= 1, (
        f"the roadmap states {len(tables)} different schema sizes: {sorted(tables)}."
    )
