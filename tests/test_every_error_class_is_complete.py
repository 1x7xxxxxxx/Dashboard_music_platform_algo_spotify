"""Chaque classe d'erreur dit comment on la détecte et ce qui la rend impossible.

Type: Test
Uses: pytest, re
Depends on: .claude/dev-docs/error-classes.md
Persists in: nothing

Pourquoi ce fichier existe (2026-09-15)
---------------------------------------
Ces deux questions étaient posées par `audit_runner.py`, en **deux étapes de CI
séparées** (`--fields --strict` et `--coverage`). Elles n'exécutent aucun test :
elles lisent le catalogue. Les poser ici les rend instantanées, visibles dans la
même sortie que le reste de la suite, et paramétrées **par classe** — un échec
nomme la classe fautive au lieu d'un compte global.

C'est le seul « test générique de classe d'erreur » qui ait un sens, et la nuance
compte : on ne peut pas écrire un garde générique qui vérifierait les 332 classes,
parce que **chacune garde une question différente** — c'est tout l'intérêt du
catalogue. Ce qu'on peut vérifier génériquement, c'est la FORME : une classe qui ne
dit pas comment on la détecte, ou ce qui la rendrait impossible, est une note, pas
une classe.

`audit_runner --fields` porte en plus un CLIQUET qu'il réécrit dans le document.
Ce fichier ne réécrit rien : un test qui modifie ce qu'il mesure ne peut pas être
lancé deux fois de suite avec le même sens.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CATALOGUE = REPO / ".claude" / "dev-docs" / "error-classes.md"

# Une classe = un titre `## <id>` suivi de ses champs `- clef: valeur`, jusqu'au
# titre suivant. L'ancre est le titre de NIVEAU DEUX : les `###` d'une section
# narrative n'ouvrent pas une classe.
_CLASS_HEAD = re.compile(r"^## ([a-z0-9][a-z0-9-]+)\s*$", re.M)

# Les formes qui ne sont pas des classes mais portent un titre de niveau deux.
_NOT_A_CLASS = frozenset({"contract", "index", "per-class-schema", "class-id"})

_MANUAL_KINDS = frozenset({"manual", "runtime-manual"})


def _blocks() -> dict[str, str]:
    text = CATALOGUE.read_text(encoding="utf-8")
    heads = list(_CLASS_HEAD.finditer(text))
    out: dict[str, str] = {}
    for i, m in enumerate(heads):
        cid = m.group(1)
        if cid in _NOT_A_CLASS:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[m.end():end]
        if "- status:" not in body:          # un titre qui n'ouvre pas une classe
            continue
        out[cid] = body
    return out


def _field(body: str, name: str) -> str:
    """La valeur sur LA LIGNE du champ, jamais celle de la suivante.

    `\\s*` a été essayé et il est FAUX : `\\s` contient `\\n`, donc sur un champ vidé
    (`- long_term_fix:` suivi de sa continuation) l'expression avalait le saut de
    ligne et capturait la ligne d'après. Le champ vide paraissait rempli, et la
    mutation qui le vidait passait au vert. `[ \\t]*` s'arrête à la fin de ligne.
    """
    m = re.search(rf"^- {name}:[ \t]*(.*)$", body, re.M)
    return (m.group(1).strip() if m else "")


_BLOCKS = _blocks()
_IDS = sorted(_BLOCKS)


@pytest.mark.parametrize("cid", _IDS)
def test_a_class_says_how_it_is_detected(cid):
    """Une signature, ou un `kind` qui assume explicitement de ne pas en avoir."""
    body = _BLOCKS[cid]
    signature, kind = _field(body, "signature"), _field(body, "kind")

    if signature:
        assert signature.strip("`").strip(), (
            f"`{cid}` porte un champ `signature` vide. Une signature vide ne sort "
            "jamais ≠ 0 : la classe se croit gardée et ne l'est pas."
        )
        return

    assert kind in _MANUAL_KINDS, (
        f"`{cid}` n'a pas de `signature` et son `kind` est `{kind or '(absent)'}`. "
        f"Sans signature, le seul `kind` honnête est l'un de {sorted(_MANUAL_KINDS)} "
        "— il déclare que la détection est un geste humain. Tout autre `kind` "
        "affirme une détection automatique qui n'existe pas."
    )


@pytest.mark.parametrize("cid", _IDS)
def test_a_class_names_its_cause_and_its_end(cid):
    """`root_cause` et `long_term_fix` : pourquoi c'est arrivé, et ce qui l'arrête.

    Une classe sans `long_term_fix` est une classe dont personne n'a décidé la fin :
    on la détectera indéfiniment. Le champ accepte explicitement
    « — (le garde EST le fix) », qui est une décision, pas un vide.
    """
    body = _BLOCKS[cid]
    for field in ("root_cause", "long_term_fix"):
        value = _field(body, field)
        assert value, (
            f"`{cid}` n'a pas de `{field}`. "
            + ("Sans cause racine, la classe décrit un symptôme et se rouvrira "
               "ailleurs." if field == "root_cause" else
               "Sans fin décidée, la classe sera détectée indéfiniment ; écrire "
               "« — (le garde EST le fix) » est une réponse valide, l'absence non.")
        )
        assert len(value) > 3, (
            f"`{cid}` porte un `{field}` de {len(value)} caractère(s) : "
            f"{value!r}. Trop court pour être relu dans six mois."
        )


def test_the_catalogue_was_actually_read():
    """Non-vacuité : zéro classe lue rendrait les deux tests ci-dessus vides.

    C'est le mode d'échec silencieux d'un test paramétré sur un balayage — si
    `_blocks()` cesse de reconnaître les titres, `parametrize` reçoit une liste
    vide, pytest ne collecte rien, et la suite reste verte sur un catalogue
    entièrement cassé.
    """
    assert len(_IDS) >= 300, (
        f"seulement {len(_IDS)} classes lues dans {CATALOGUE.name} — le catalogue "
        "en portait 332 le 2026-09-15. L'extraction est probablement cassée, et "
        "les tests paramétrés ci-dessus ne gardent plus rien."
    )
    assert "a-prose-claim-that-cannot-be-verified" in _BLOCKS, (
        "une classe connue manque à l'extraction : le motif de titre ne reconnaît "
        "plus la forme réelle du document."
    )
    sample = _BLOCKS["a-prose-claim-that-cannot-be-verified"]
    assert _field(sample, "status") == "guarded", (
        "l'extraction de champ ne rend plus la bonne valeur : "
        f"{_field(sample, 'status')!r}"
    )
