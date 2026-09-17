"""Aucun document de ce dépôt ne nomme une cible `make` qui n'existe pas.

Type: Test
Uses: re
Depends on: Makefile, .claude/dev-docs/**, .claude/rules/**, CLAUDE.md
Persists in: nothing

Le garde existait déjà — `test_the_night_protocol_is_runnable::
test_every_make_target_the_protocol_names_exists` — mais portait sur **un seul
document**, le protocole de nuit. Élargi le 2026-09-17 en balayant les frères de
`a-runbook-that-names-a-command-nobody-can-run`.

Le balayage a trouvé son site immédiatement, et dans MA propre écriture du jour :
un `guard_scope` de `error-classes.md` nommait `make caddy-drift`, qui n'a jamais
existé — la cible réelle est `caddy-validate`. Une commande fantôme dans un champ
qu'on lit pour savoir quoi lancer coûte une minute à chaque lecteur, et ne rougit
nulle part.

⚠️ Ce test ne dit RIEN de ce que la cible fait : elle peut exister et ne pas
répondre à la phrase qui l'invoque. Il ferme la moitié mécanisable de la question.

⚠️ **Il s'est déclenché sur SA PROPRE DOCUMENTATION, dans l'heure qui a suivi son
écriture.** En consignant le site trouvé, j'ai écrit la cible fantôme sous la forme
prescriptive `` `make caddy-drift` `` dans `error-classes.md` — et le garde l'a
signalée, à raison. C'est la classe `a-bash-hook-that-blocks-the-prose-about-the-gesture`,
que ce dépôt a déjà payée trois fois le 2026-09-12.

La parade retenue n'est PAS une exemption, et c'est délibéré : un garde qui s'exempte
des documents cesse de garder l'endroit où les commandes fantômes vivent le plus.
**C'est la CITATION qui change de forme** — on nomme une cible inexistante par son nom
seul (`caddy-drift`), jamais sous la forme qu'un lecteur pourrait copier. Le garde lit
`` `make X` `` parce que c'est la forme PRESCRIPTIVE ; écrire autrement, c'est dire
« cette chose existe » sans dire « lance-la ».

Mutation record — 2026-09-17, deux mutations, deux vues ROUGES :
  1. réintroduire `make caddy-drift` dans `error-classes.md` → rouge, cible nommée.
  2. `_TARGETS` vidé                                          → rouge (anti-vacuité).

---
rex: []
---
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# `make X` est un gabarit dans la prose, pas une cible. Idem pour un mot tronqué :
# le motif s'arrête au premier caractère non autorisé, donc une phrase comme
# « les cibles `make night-*` » produit un nom incomplet.
_PLACEHOLDERS = {"X", "Y", "N", "<id>", "target", "cible"}


def _targets() -> set[str]:
    text = (_ROOT / "Makefile").read_text(encoding="utf-8")
    return set(re.findall(r"^([a-zA-Z0-9_.-]+):", text, re.M))


def _documents() -> list[Path]:
    docs = list((_ROOT / ".claude" / "dev-docs").rglob("*.md"))
    docs += list((_ROOT / ".claude" / "rules").glob("*.md"))
    docs += [_ROOT / "CLAUDE.md"]
    return [d for d in docs if d.exists()]


def test_the_scope_is_not_empty() -> None:
    """Anti-vacuité sur les DEUX côtés : sans cibles ou sans documents, tout passe."""
    assert len(_targets()) > 20, "le Makefile ne rend presque aucune cible"
    assert len(_documents()) > 10, "aucun document scruté"


def test_no_document_names_a_make_target_that_does_not_exist() -> None:
    targets = _targets()
    fantomes: dict[str, list[str]] = {}
    for doc in _documents():
        # Seulement ce qui est ENTRE BACKTICKS et complet : `make <cible>`. La forme
        # libre en prose attrape des troncatures et des gabarits.
        for name in re.findall(r"`make ([a-zA-Z0-9_.]+(?:-[a-zA-Z0-9_.]+)*)`",
                               doc.read_text(encoding="utf-8")):
            if name in _PLACEHOLDERS or name in targets:
                continue
            fantomes.setdefault(name, []).append(str(doc.relative_to(_ROOT)))
    assert not fantomes, (
        "des documents nomment des cibles `make` qui n'existent pas :\n  "
        + "\n  ".join(f"make {k} ← {', '.join(sorted(set(v)))}"
                      for k, v in sorted(fantomes.items()))
        + "\n\nSoit la cible a été renommée et le document est resté en arrière, soit "
          "elle n'a jamais existé. Dans les deux cas le lecteur lance une commande qui "
          "échoue, et rien ne le signalait.")
