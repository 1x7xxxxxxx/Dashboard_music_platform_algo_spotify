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


def test_the_extraction_still_finds_rows_when_there_are_rows():
    """Non-vacuity. Without it, every assertion below is true of nothing.

    L'extraction lit un markdown par titre : un titre qui apparaît AUSSI dans la prose,
    un renommage ou une réorganisation rendent une liste vide plutôt qu'une erreur — et
    une liste vide satisfait parfaitement `assert not offenders`. Ce test a expédié ce
    défaut pendant une dizaine de minutes le 2026-08-21.

    Il vérifiait « la roadmap a au moins une ligne », et disait lui-même quoi faire le
    jour où ce serait faux : « soit tout est réellement clos — auquel cas supprimer ce
    test — soit l'extraction vise à côté ». Le 2026-09-10, tout EST réellement clos.

    Supprimer le test serait pourtant la mauvaise moitié de l'alternative : il retirerait
    la protection de non-vacuité des cinq assertions qui suivent, exactement au moment où
    elles portent toutes sur des listes vides. La leçon du jour, mesurée sur un cliquet
    d'axes secondaires gelé à zéro qui certifiait une propriété fausse : **un contrôle
    qui n'a plus rien à trouver doit prouver qu'il sait encore VOIR.** La preuve se
    déplace donc de la roadmap vers le PARSEUR, sur un échantillon fabriqué ici.
    """
    sample = [
        "| R42 | quelque chose | P2 | mesuré par ceci |",
        "| R7 | autre chose | P3 | mesuré par cela |",
        "pas une ligne de tableau",
        "| X9 | identifiant qui n'est pas un R-id | P1 | — |",
    ]
    found = [m.group(1) for line in sample if (m := _ROW.match(line))]
    assert found == ["R42", "R7"], (
        f"le motif de ligne de roadmap ne reconnaît plus ses propres lignes : {found}. "
        "Tant qu'il est cassé, les cinq contrôles ci-dessous passent sur du vide, que "
        "la roadmap soit pleine ou non."
    )
    # Et le découpage par titre : les deux sections doivent exister et être trouvées au
    # DÉBUT d'une ligne, pas dans la prose qui les mentionne deux paragraphes plus haut.
    for heading in (_ACTIONABLE_H, _WAITING_H):
        _section(heading)  # lève si le titre n'est pas ancré en début de ligne


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

# The reverse direction. `test_every_waiting_row_names_the_gesture_it_waits_on` asks
# "does every open row have a procedure?"; nothing asked "does every procedure still
# have an open row?" — and that is the half that rotted.
# Anchored on the numbered task-section form the runbook actually uses — `## 8. R54 — …`
# — and not on "any heading mentioning an id". The looser version flagged R42 on its
# first run: `### Ce qui a changé le 2026-08-23 (R42)` is a narrative sub-heading INSIDE
# an already-struck section, describing history rather than proposing work. The
# predicate has to match the question (does this section present a task as to-do?)
# rather than the symptom (does an id appear in a heading?).
_LIVE_HEADING = re.compile(r"^## \d+\. (?!~~)(R\d+) ", re.M)


def _live_runbook_ids() -> set[str]:
    """Runbook sections NOT struck through — i.e. presented as still to do."""
    if not RUNBOOK.exists():
        return set()
    return set(_LIVE_HEADING.findall(RUNBOOK.read_text(encoding="utf-8")))


def test_no_runbook_section_outlives_its_task():
    """A closed task must not keep a live-looking procedure with a priority on it.

    Measured 2026-08-28. The runbook carried `## 1. R13 — … · P2`, `## 4. R17 — … · P3`
    and `## 9. R55 — … · P3` — three headings that read as open work, with a severity
    each, for tasks closed on 22, 21 and 26 August. The checklist knew; the runbook did
    not, and nothing compared them.

    The existing guard only walks checklist → runbook, so a row leaving the index takes
    its evidence with it and leaves the procedure looking live. This walks the other
    way. The convention it enforces already existed and was simply not checked: a done
    section is struck through and dated (`~~R20 — …~~ · ✅ FAIT le 2026-08-21`), which
    keeps the steps readable for the day the row comes back.

    Same class as the `## 🔖 REPRISE` header naming three closed ids the same morning:
    a document goes stale exactly where nothing reads it against the code.
    """
    open_ids = set(_ids(_ACTIONABLE_H)) | set(_ids(_WAITING_H))
    orphans = sorted(_live_runbook_ids() - open_ids)
    assert not orphans, (
        f"{orphans} have a live (not struck through) section in {RUNBOOK.name} but no "
        "row in either roadmap index. Either the task is open and its row is missing, "
        "or it is done and its heading must be struck through and dated — the "
        "`~~R20 — …~~ · ✅ FAIT le …` form already used by six other sections. A "
        "procedure that still shows a priority is a task that still looks open."
    )


def test_the_live_heading_pattern_actually_distinguishes_the_two_forms():
    """Non-vacuity: a regex that matched everything, or nothing, would pass silently.

    `_LIVE_HEADING` carries a negative lookahead, the kind of predicate that fails
    open. Pinned against both real forms rather than trusted.
    """
    import re as _re
    live = "## 5. R1 — Ouvrir la bêta privée · P3"
    done = "## 2. ~~R20 — Créer le canari~~ · ✅ FAIT le 2026-08-21"
    assert _LIVE_HEADING.findall(live) == ["R1"], "a live heading must be seen"
    assert _LIVE_HEADING.findall(done) == [], "a struck heading must be ignored"
    # Troisième assertion, DÉPLACÉE le 2026-09-10. Elle vérifiait que le runbook réel
    # porte au moins une section vivante — vrai tant qu'une tâche restait ouverte, faux
    # depuis que R1 est rotée. Son message disait « soit tout est fait, auquel cas
    # supprimer ce test ». Supprimer serait la mauvaise moitié de l'alternative : ce
    # qu'on veut prouver n'est pas que le fichier contient du travail, c'est que
    # l'EXTRACTEUR sait encore lire un fichier qui en contient. Même leçon qu'un cliquet
    # gelé à zéro — il doit prouver qu'il VOIT, pas seulement qu'il ne trouve rien.
    fabricated = "\n".join([
        "## 1. ~~R13 — deja clos~~ · CLOS le 2026-08-22",
        "## 2. R99 — une tache encore ouverte · P2",
        "## 3. ~~R20 — clos aussi~~ · FAIT le 2026-08-21",
        "du texte qui n'est pas un titre de section",
    ])
    assert _LIVE_HEADING.findall(fabricated) == ["R99"], (
        "l'extracteur de sections vivantes ne distingue plus les deux formes sur un "
        "fichier qui en contient : tant qu'il est casse, "
        "`test_no_runbook_section_outlives_its_task` passe sur du vide."
    )
