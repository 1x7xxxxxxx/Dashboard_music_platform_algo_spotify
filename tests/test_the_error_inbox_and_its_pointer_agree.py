"""Le registre des erreurs et la ligne qui l'annonce disent le meme nombre.

Type: Sub
Uses: pathlib, re
Triggers: pytest
Depends on: .claude/dev-docs/error-inbox.md, .claude/dev-docs/roadmap/checklist.md
Persists in: —

Error class `a-generated-document-with-no-freshness-guard`.

Pourquoi ce garde ne verifie PAS la fraicheur
----------------------------------------------
`tools/error_inbox.py` est le seul des quatre generateurs de documents du depot a
deriver d'une ressource EXTERNE — la table `app_error_log`. Ses trois soeurs
(`gold_coverage`, `error_class_families`, `error_class_health`) derivent du depot :
leur garde recalcule le rendu et compare, n'importe ou, CI comprise.

Ici c'est impossible, et pretendre le contraire serait le piege. Un test qui
essaierait de joindre la base serait **vert par abstention** partout ou elle est
absente — donc vert en CI, c'est-a-dire vert la ou il compte. C'est la classe
`un-controle-qui-ne-peut-jamais-passer`, que le depot a deja payee sur un
`gh api … || echo true` qui declarait succes sur une panne reseau.

La fraicheur vraie est donc un geste MANUEL : `make error-inbox-check`, qui rend **2**
— un code a lui — quand il n'a rien pu verifier.

Ce que ce garde couvre, lui, tient sans base : **les deux surfaces qui annoncent un
nombre s'accordent**. Le document dit « N ouverte(s) » ; la roadmap porte une ligne de
renvoi ancree `<!-- error-inbox: open=N -->`. Elles sont ecrites par la MEME execution,
donc un desaccord signifie qu'une des deux a ete editee a la main ou perdue — et c'est
arrive : le 2026-09-17, la ligne ancree avait disparu de `checklist.md` pendant que le
document affirmait un compte.

Mutation record — 2026-09-17, deux mutations EXECUTEES et vues rouges :
  * le nombre de l'ancre de `checklist.md` passe de 1 a 7 → exit 1 ;
  * la ligne ancree retiree de `checklist.md` → exit 1 sur le test de presence.
0 apres remise en etat dans les deux cas.
"""

import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_DOC = _ROOT / ".claude" / "dev-docs" / "error-inbox.md"
_CHECKLIST = _ROOT / ".claude" / "dev-docs" / "roadmap" / "checklist.md"

_DOC_COUNT = re.compile(r"\*\*(\d+) ouverte\(s\)\*\*")
_ANCHOR = re.compile(r"<!-- error-inbox: open=(\d+) -->")


def test_the_roadmap_still_carries_the_pointer_to_the_inbox():
    """La roadmap annonce le registre — sinon personne ne sait qu'il existe.

    `CLAUDE.md` dit que « la roadmap n'en porte qu'une ligne de renvoi ancree ». Le
    2026-09-17, cette ligne avait disparu : rien ne l'a signale, et le registre est
    devenu invisible depuis le seul document qu'on lit en routine.
    """
    text = _CHECKLIST.read_text(encoding="utf-8")
    found = _ANCHOR.findall(text)
    assert len(found) == 1, (
        f"`.claude/dev-docs/roadmap/checklist.md` should carry exactly one anchored "
        f"pointer to the error inbox; found {len(found)}. Remède : make error-inbox — "
        f"il réécrit la ligne et son ancre ensemble, parce qu'elles sont une seule "
        f"affirmation."
    )


def test_the_document_and_the_pointer_agree_on_the_count():
    """Les deux surfaces écrites par la même exécution disent le même nombre."""
    doc = _DOC.read_text(encoding="utf-8")
    in_doc = _DOC_COUNT.search(doc)
    assert in_doc, (
        "`error-inbox.md` no longer states a count in the `**N ouverte(s)**` form this "
        "guard reads. If the rendering changed, update both together."
    )
    in_roadmap = _ANCHOR.search(_CHECKLIST.read_text(encoding="utf-8"))
    assert in_roadmap, "the roadmap pointer is gone — see the previous test."

    assert in_doc.group(1) == in_roadmap.group(1), (
        f"`error-inbox.md` says {in_doc.group(1)} open entries, the roadmap pointer "
        f"says {in_roadmap.group(1)}. Both are written by the SAME run of "
        f"`tools/error_inbox.py`, so a disagreement means one of them was hand-edited "
        f"or lost. Remède : make error-inbox.\n\n"
        f"⚠️ Ce garde ne dit RIEN de la fraîcheur : les deux peuvent s'accorder sur un "
        f"chiffre périmé. Seul `make error-inbox-check` voit la base, et il rend 2 "
        f"quand il ne la voit pas."
    )
