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

import pytest


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


# ---------------------------------------------------------------------------
# La prose qui PLACE une tâche dans une section nommée — ajoutée le 2026-09-15.
#
# Les trois tests ci-dessus lisent des TABLEAUX. Aucun ne lisait la prose, et
# c'est exactement là que le fichier a dérivé : le 2026-09-15, trois phrases
# affirmaient « R1 reste en attente, dans « 🙋 En attente de toi » plus bas »
# alors que cette table était VIDE depuis le 2026-09-10 et le disait elle-même
# quatre cents lignes plus bas — R1 ayant été rotée dans `archive.md`.
#
# L'ancre était juste, le tableau était juste ; seule la phrase à côté mentait.
# C'est la classe `a-prose-claim-that-cannot-be-verified`, que ce fichier
# nommait sans que rien ne la détecte. Le 2026-09-12 elle avait déjà frappé sur
# « quatre tâches rouvertes » contre un index vide.
#
# Ce qui est mécanisable n'est pas « cette phrase est-elle vraie » mais sa forme
# la plus fréquente et la plus coûteuse : une phrase qui LOCALISE un id dans une
# section nommée. Le prédicat exige les trois marques ensemble, dans une même
# phrase et dans cet ordre — l'id, puis une préposition de lieu, puis le nom de
# la section — pour ne pas confondre avec une phrase de DÉPART, qui met le nom
# de la section en sujet : « L'index `## 📋 Tâches ouvertes` est vide : R108, sa
# dernière ligne, a été livrée ». Celle-là dit le contraire et doit passer.
_SECTION_ALIAS = {_WAITING_H: "En attente de toi", _ACTIONABLE_H: "Tâches ouvertes"}
_LOCATIVE = re.compile(r"\b(?:dans|voir|sous|figure|portée? par|porté par|vit)\b", re.I)
_ANY_ID = re.compile(r"\bR(\d+)\b")


def _prose(text: str) -> str:
    """Le texte moins ce qui est déjà vérifié ailleurs : tableaux, titres, code."""
    out, fenced = [], False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            fenced = not fenced
            continue
        if fenced or stripped.startswith("|") or stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def _locating_claims(text: str) -> list[tuple[str, str, str]]:
    """(id, nom de section, phrase) pour chaque phrase qui place un id quelque part."""
    claims = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n\s*\n", _prose(text)):
        flat = " ".join(sentence.split())
        for head, alias in _SECTION_ALIAS.items():
            for anchor in re.finditer(re.escape(alias), flat):
                for ident in _ANY_ID.finditer(flat):
                    if ident.end() >= anchor.start():
                        continue  # phrase de départ : la section est le sujet
                    between = flat[ident.end():anchor.start()]
                    if len(between) > 120 or not _LOCATIVE.search(between):
                        continue
                    claims.append((f"R{ident.group(1)}", head, flat))
    return claims


def test_no_prose_sentence_places_a_task_in_a_section_that_has_no_such_row():
    """Une phrase qui situe une tâche doit la situer là où elle est vraiment.

    `/resume` lit ce fichier EN PREMIER et le résume à voix haute. Une phrase
    fausse ici n'est pas cosmétique : c'est l'état d'où part la séance. Le
    2026-09-15 elle a fait annoncer R1 comme la dernière tâche ouverte du dépôt,
    cinq jours après sa rotation.
    """
    rows = {_WAITING_H: set(_ids(_WAITING_H)), _ACTIONABLE_H: set(_ids(_ACTIONABLE_H))}
    wrong = [
        (task, _SECTION_ALIAS[head], sentence)
        for task, head, sentence in _locating_claims(ACTIVE.read_text(encoding="utf-8"))
        if task not in rows[head]
    ]
    assert not wrong, "\n".join(
        [
            f"{len(wrong)} phrase(s) placent une tâche dans une section qui ne la "
            "porte pas. Le tableau fait foi — c'est la prose qu'il faut corriger, "
            "ou la ligne qu'il faut remettre :",
        ]
        + [f"  {task} annoncée dans « {alias} » — {sentence[:150]}" for task, alias, sentence in wrong]
    )


def test_the_locating_claim_predicate_tells_arrival_from_departure():
    """Non-vacuité : un prédicat qui ne voit rien passe sur un fichier faux.

    Les deux formes sont tirées du fichier réel — la phrase fautive du
    2026-09-15 et la phrase juste sur R108 qu'elle ne doit pas confondre avec.
    """
    arrival = "**R1** reste le seul geste humain, dans la section « 🙋 En attente de toi » plus bas : inviter la bêta."
    departure = "**L'index `## 📋 Tâches ouvertes` est vide** : R108, sa dernière ligne, a été livrée le 2026-09-14."

    seen = [task for task, _, _ in _locating_claims(arrival)]
    assert seen == ["R1"], (
        f"le prédicat ne voit plus une phrase qui PLACE une tâche ({seen!r}) : tant "
        "qu'il est cassé, le test ci-dessus passe sur du vide."
    )
    assert _locating_claims(departure) == [], (
        "le prédicat prend une phrase de DÉPART pour une phrase de placement — il "
        "rougirait sur chaque tâche correctement archivée."
    )
    # Une phrase de placement JUSTE ne doit rien déclencher non plus : le test
    # porte sur l'accord prose ↔ tableau, pas sur l'existence de la phrase.
    both = _locating_claims(arrival + "\n\n" + departure)
    assert [t for t, _, _ in both] == ["R1"], f"extraction instable sur deux phrases : {both!r}"


# ── Une phrase qui COMPTE des lignes — 2026-09-18 ────────────────────────────
#
# `test_no_prose_sentence_places_a_task_in_a_section_that_has_no_such_row` vérifie qu'un
# IDENTIFIANT est nommé dans la bonne section. Il ne regarde jamais **combien** de lignes
# une section porte — et c'est par là que ce fichier se trompe, encore et encore.
#
# Quatre occurrences, toutes dans `checklist.md`, toutes invisibles aux gardes :
#   2026-09-12  « quatre tâches rouvertes » — les quatre étaient closes, l'index vide.
#   2026-09-18  « Quatre tâches sont ouvertes » là où l'index en portait cinq, et
#               « l'ancre les nomme toutes les trois » — trois nombres dans une phrase.
#   2026-09-18  « la table En attente de toi reste VIDE » alors que R125 y était depuis
#               le matin.
#   2026-09-18  « la table porte UNE ligne » — corrigée le matin, redevenue fausse
#               l'après-midi à l'entrée de R140, par la même personne qui venait de
#               recaler la phrase voisine.
#
# La forme est toujours la même : un nombre écrit EN LETTRES à côté d'une section dont
# les lignes sont comptables. On peut donc le compter.
_NOMBRES = {"aucune": 0, "aucun": 0, "vide": 0, "zéro": 0,
            "une": 1, "un": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
            "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11,
            "douze": 12}
_MOT = "|".join(sorted(_NOMBRES, key=len, reverse=True))
# « porte DEUX lignes », « Huit tâches sont ouvertes dans cet index », « reste vide »
_COMPTE = re.compile(
    r"(?:\*\*)?\b(?P<n>" + _MOT + r"|\d+)(?:\*\*)?\s+"
    r"(?:ligne|tâche|item|entrée)s?\b"
    r"|(?:porte|reste|contient)\s+(?:\*\*)?(?P<m>" + _MOT + r"|\d+)(?:\*\*)?",
    re.I)


def _valeur(mot: str) -> int | None:
    mot = mot.strip("* ").lower()
    if mot.isdigit():
        return int(mot)
    return _NOMBRES.get(mot)


def _lignes_de(entete: str) -> int:
    return sum(1 for ligne in _section(entete) if _ROW.match(ligne))


def test_a_sentence_that_counts_rows_counts_the_rows_there_are() -> None:
    """Une phrase qui annonce un NOMBRE de lignes doit annoncer celui de la table.

    Elle n'est contrainte que lorsqu'elle NOMME sa section : « la table
    « 🙋 En attente de toi » porte deux lignes ». Une phrase qui compte autre chose —
    des plateformes, des défauts, des jours — ne nomme aucune de ces deux sections et
    n'est donc pas concernée. C'est ce qui sépare la propriété d'une chasse aux nombres.
    """
    texte = ACTIVE.read_text(encoding="utf-8")
    reels = {h: _lignes_de(h) for h in (_WAITING_H, _ACTIONABLE_H)}
    faux = []
    for entete, alias in _SECTION_ALIAS.items():
        for m in re.finditer(re.escape(alias), texte):
            # la fenêtre où une phrase peut encore parler de CETTE section
            fenetre = texte[m.end(): m.end() + 160]
            # coupée au premier saut de paragraphe : au-delà, la phrase a changé de sujet
            fenetre = fenetre.split("\n\n")[0]
            c = _COMPTE.search(fenetre)
            if not c:
                continue
            v = _valeur(c.group("n") or c.group("m") or "")
            if v is None or v == reels[entete]:
                continue
            ligne = texte[:m.start()].count("\n") + 1
            faux.append((ligne, alias, v, reels[entete], fenetre.strip()[:70]))
    assert not faux, (
        "".join(f"\n  checklist.md:{num} dit {v} pour « {a} », qui porte {r} — « {f}… »"
                for num, a, v, r, f in faux) +
        "\n\nUne phrase de ce fichier qui compte des lignes compte ce que la table "
        "compte, et rien d'autre. Quatre occurrences mesurées le 2026-09-18, dont deux "
        "le même jour : la phrase est corrigée, une ligne entre, la phrase redevient "
        "fausse. Aucun autre garde ne la voit — ils vérifient qu'un IDENTIFIANT est dans "
        "la bonne section, jamais COMBIEN de lignes elle porte.")


# ⚠️ L'ancrage sur l'ALIAS ne suffit pas, et ma propre mutation l'a montré.
# « **Quatre tâches sont ouvertes dans cet index** » ne contient pas la chaîne
# « Tâches ouvertes » — la phrase parle de la section sans la NOMMER, par « cet index ».
# Or c'est l'une des quatre occurrences historiques : le 2026-09-18 elle disait quatre
# là où l'index en portait cinq. Un garde ancré sur le nom de la section est vert dessus.
# Second ancrage, sur la PHRASE : tout « N tâche(s) … ouverte(s) … index » compte les
# lignes de la table actionnable, qu'il nomme la section ou non.
_COMPTE_INDEX = re.compile(
    r"(?:\*\*)?\b(?P<n>" + _MOT + r"|\d+)(?:\*\*)?\s+t[âa]ches?\b[^.\n]{0,60}?"
    r"\bouvertes?\b[^.\n]{0,40}?\bindex\b", re.I)


def test_a_sentence_that_counts_the_open_index_counts_its_rows() -> None:
    """« N tâches sont ouvertes dans cet index » compte les lignes de l'index.

    Séparé du test ci-dessus parce que la propriété est la même mais l'ancrage ne peut
    pas l'être : cette phrase désigne la section par « cet index », jamais par son titre.
    """
    texte = ACTIVE.read_text(encoding="utf-8")
    reel = _lignes_de(_ACTIONABLE_H)
    faux = []
    for m in _COMPTE_INDEX.finditer(texte):
        v = _valeur(m.group("n"))
        if v is not None and v != reel:
            faux.append((texte[:m.start()].count("\n") + 1, v, m.group(0)[:60]))
    assert not faux, (
        "".join(f"\n  checklist.md:{num} annonce {v} tâche(s) ouverte(s), l'index en "
                f"porte {reel} — « {ext}… »" for num, v, ext in faux) +
        "\n\nCette phrase désigne l'index par « cet index » et non par son titre : le "
        "garde ancré sur le nom de section est structurellement vert dessus. C'est la "
        "mutation qui l'a révélé, pas une relecture.")


def test_the_index_counting_predicate_is_not_vacuous() -> None:
    assert _COMPTE_INDEX.search("**Huit tâches sont ouvertes dans cet index** — R132") is not None
    assert _valeur(_COMPTE_INDEX.search("Quatre tâches sont ouvertes dans cet index").group("n")) == 4
    assert _COMPTE_INDEX.search("trois défauts ouverts dans le catalogue") is None


# ⚠️ Troisième forme, trouvée le 2026-09-18 en fermant le goal : une LIGNE de table qui
# compte ses propres SOUS-SECTIONS de runbook. R140 annonçait « Trancher **quatre**
# décisions de produit » alors que treize s'y étaient ajoutées au fil des balayages —
# §16.1 à §16.17. Les deux gardes ci-dessus sont aveugles par construction : l'un compte
# les lignes d'une SECTION, l'autre les tâches de l'INDEX. Aucun ne regarde ce qu'une
# ligne dit d'un AUTRE fichier.
#
# C'est la cinquième occurrence de `a-prose-claim-that-cannot-be-verified` dans ce
# fichier, et la troisième de ma main. Le motif est stable : un nombre écrit en toutes
# lettres, un renvoi vers une section, et personne pour les confronter.
# ⚠️ `[^\n]*?` et NON `[^|]*?`. Premier jet : il interdisait le caractère `|`, et la
# mutation est passée — le compte et le renvoi vivent dans DEUX COLONNES de la même
# ligne de table, donc séparés par des `|`. Le prédicat cherchait une forme d'écriture
# (« pas de pipe entre les deux ») là où la propriété est « sur la même ligne ».
# Troisième fois dans la journée qu'un prédicat se trompe de cette façon exacte.
_RENVOI_RUNBOOK = re.compile(
    r"\*\*(?P<n>" + _MOT + r"|\d+)\s+d[ée]cisions?[^\n]*?"
    r"§\s*(?P<a>[\d.]+)\s*(?:à|a|-|–)\s*§?\s*(?P<b>[\d.]+)", re.I)


def test_a_row_that_counts_runbook_sections_counts_the_ones_there_are() -> None:
    """Une ligne qui annonce N décisions et renvoie à §x.1–§x.N compte les vraies.

    Le renvoi EST la contrainte : sans lui, « dix-sept décisions » ne se vérifie nulle
    part. C'est pourquoi ce garde n'exige pas un renvoi — il ne contraint que les lignes
    qui en portent un, et ne peut donc pas pousser à en retirer un pour se taire.
    """
    texte = ACTIVE.read_text(encoding="utf-8")
    runbook = (REPO / ".claude" / "dev-docs" / "runbook-actions-utilisateur.md")
    if not runbook.is_file():
        pytest.skip("runbook absent de cet arbre")
    corps = runbook.read_text(encoding="utf-8")
    faux = []
    for m in _RENVOI_RUNBOOK.finditer(texte):
        annonce = _valeur(m.group("n"))
        prefixe = m.group("a").split(".")[0]
        reelles = len(re.findall(rf"^#{{3}} {re.escape(prefixe)}\.\d+ ", corps, re.M))
        if annonce is not None and reelles and annonce != reelles:
            ligne = texte[:m.start()].count("\n") + 1
            faux.append((ligne, annonce, reelles, prefixe))
    assert not faux, (
        "".join(f"\n  checklist.md:{ln} annonce {a} décision(s) et renvoie à §{p}, "
                f"qui en porte {r}" for ln, a, r, p in faux) +
        "\n\nUne ligne d'index qui compte les sous-sections d'un runbook compte celles "
        "qui existent. R140 a annoncé « quatre » pendant que treize s'y ajoutaient : les "
        "deux autres gardes de comptage sont aveugles ici — l'un compte les lignes d'une "
        "SECTION, l'autre les tâches de l'INDEX, aucun ne regarde ce qu'une ligne dit "
        "d'un AUTRE fichier.")


def test_the_counting_predicate_reads_both_shapes() -> None:
    """Non-vacuité : le prédicat sépare-t-il vraiment un compte juste d'un compte faux ?

    Sans ceci, un motif qui ne matche jamais rend le test ci-dessus vert sur un fichier
    qui ment — le mode d'aveuglement que ce dépôt a mesuré dix fois.
    """
    def lu(phrase: str):
        # Le MÊME accès que le code réel : deux branches, `porte …` et `N lignes`, et
        # l'une peut gagner là où on attendait l'autre. Les tester séparément ferait
        # passer le test sur un chemin que la production n'emprunte pas.
        m = _COMPTE.search(phrase)
        return None if m is None else _valeur(m.group("n") or m.group("m") or "")

    assert lu("porte **DEUX lignes** : R125 et R140") == 2
    assert lu("**Huit tâches sont ouvertes** dans cet index") == 8
    assert lu("la table reste vide") == 0
    assert lu("porte 3 lignes") == 3
    # et une phrase qui ne compte PAS de lignes ne doit pas mordre
    assert lu("cette section explique le flux") is None
