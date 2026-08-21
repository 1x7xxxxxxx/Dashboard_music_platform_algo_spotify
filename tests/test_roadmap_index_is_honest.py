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
    """Lines between this heading and the next `## ` one."""
    text = ACTIVE.read_text(encoding="utf-8")
    start = text.index(name)
    rest = text[start + len(name):]
    m = re.search(r"^## ", rest, re.M)
    return (rest[: m.start()] if m else rest).splitlines()


def _ids(name: str) -> list[str]:
    return [m.group(1) for line in _section(name) if (m := _ROW.match(line))]


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


def test_every_waiting_row_names_the_gesture_it_waits_on():
    """'BLOQUÉ' is a status. 'Regenerate the token in Business Manager' is a gesture.

    The whole reason these rows are out of the actionable index is that a person
    has to act. A row that does not say which act is back to being a status that
    never changes.
    """
    vague = []
    for line in _section(_WAITING_H):
        m = _ROW.match(line)
        if not m:
            continue
        body = m.group(2)
        # An imperative or an explicit hand-off marker — not merely a state word.
        if not re.search(
            r"action utilisateur|prérequis|Régénérer|Créer|déposer|ouvrir|"
            r"actionnable|corriger|inviter|ingest|UPDATE ", body, re.I
        ):
            vague.append(m.group(1))
    assert not vague, (
        f"{vague} sit in « En attente de toi » without naming what they wait for. "
        "State the gesture, or the row is a status that will never change."
    )


def test_the_actionable_index_says_what_it_is_for():
    """Its intro is the contract the two `/` commands rely on."""
    body = "\n".join(_section(_ACTIONABLE_H))
    assert "commencer maintenant" in body, (
        "the index no longer states that it holds work startable today — which is "
        "the only property `/resume` and `/sprint` actually need from it."
    )
