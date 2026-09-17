#!/usr/bin/env python3
"""Ouvre et ferme une tache de roadmap sur ses TROIS surfaces, d'un seul geste.

Type: Utility
Uses: pathlib, re, argparse
Triggers: make roadmap-close / make roadmap-open, .claude/commands/roadmap-done.md
Depends on: .claude/dev-docs/roadmap/{checklist,archive}.md
Persists in: les deux fichiers de roadmap

Pourquoi cet outil existe — les frictions MESUREES le 2026-09-17
-----------------------------------------------------------------
La rotation etait une procedure en PROSE (`.claude/commands/roadmap-done.md`), executee a
la main. Elle est correcte et detaillee, et elle a quand meme laisse passer deux erreurs
dans une seule seance, parce qu'elle ne nomme ni l'une ni l'autre :

  1. **L'ancre de reprise** `<!-- reprise: open=... -->` est une TROISIEME surface, a cote
     des deux tables d'index. Oubliee une fois -> `test_the_anchor_matches_the_open_index`
     rouge, apres coup.
  2. **Le format d'archive.** `test_no_brick_id_vanishes_from_both_files` ne reconnait un
     identifiant que sous deux formes — une ligne de tableau `| Rxxx |` ou une case cochee
     `- [x] **Rxxx`. Une entree ecrite en titre `## Rxxx — ...` est donc INVISIBLE pour
     lui : deux taches ont ete signalees comme « disparues des deux fichiers » alors
     qu'elles etaient bien dans l'archive, sous un titre.

Les deux ont ete rattrapees par les tests. C'est le bon filet, mais il attrape APRES,
et la lecon du depot est constante : un geste reflexe ne se retient pas par une note.

⚠️ Une troisieme friction, mesuree le meme jour et NON corrigeable ici : l'agent
`roadmap-keeper` a tourne **31 minutes sans rien ecrire** sur une rotation d'une tache.
La rotation a ete faite a la main. Cet outil la rend mecanique, ce qui retire la raison
de lancer un agent pour ca — `roadmap-keeper` reste utile pour une BRIQUE entiere, ou il
doit juger, pas compter.

Ce que l'outil ne fait PAS
---------------------------
Il n'ecrit aucun contenu : ni le detail d'une tache, ni le recit d'une livraison. Il
deplace, coche, retire et met l'ancre d'accord. Le texte reste ecrit a la main, parce
qu'une rotation qui redige aussi la lecon produirait des lecons de machine.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

# ⚠️ `ROADMAP_ROOT` existe pour que cet outil soit TESTABLE sans copier son propre code.
# Sans elle, un test devait recopier ce fichier dans une arborescence temporaire pour que
# `parents[2]` tombe au bon endroit — c'est-a-dire lire du source Python en texte, ce que
# `tests/test_a_guard_reads_structure_not_text.py` refuse a juste titre. Et c'est aussi
# le piege deja paye par le depot : une copie vers /tmp casse toute resolution de racine
# par `__file__`. Une variable d'environnement coute une ligne et retire les deux.
ROOT = pathlib.Path(os.environ.get("ROADMAP_ROOT") or
                    pathlib.Path(__file__).resolve().parents[2])
CHECKLIST = ROOT / ".claude" / "dev-docs" / "roadmap" / "checklist.md"
ARCHIVE = ROOT / ".claude" / "dev-docs" / "roadmap" / "archive.md"

_ANCHOR = re.compile(r"<!--\s*reprise:\s*open=([^>]*?)\s*-->")
_INDEX_ROW = re.compile(r"^\|\s*(R\d{1,4})\s*\|", re.M)


def _index_ids(text: str) -> list[str]:
    """Les identifiants listes par les DEUX tables d'index.

    Les deux, et c'est le point : `## 📋 Tâches ouvertes` et `## 🙋 En attente de toi`
    sont toutes deux des taches ouvertes. Un ecran de reprise qui n'en lisait qu'une a
    annonce « 0 tache » sur un depot qui en avait une (2026-09-17).
    """
    seen: list[str] = []
    for m in _INDEX_ROW.finditer(text):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def _set_anchor(text: str, ids: list[str]) -> str:
    if not _ANCHOR.search(text):
        raise SystemExit(
            "❌ l'ancre `<!-- reprise: open=… -->` est absente de checklist.md. "
            "C'est elle que `/resume` lit en premier ; la recreer avant de continuer.")
    return _ANCHOR.sub(f"<!-- reprise: open={', '.join(ids)} -->", text, count=1)


def cmd_sync(_args) -> int:
    """Remet l'ancre d'accord avec les deux tables. Idempotent."""
    text = CHECKLIST.read_text(encoding="utf-8")
    ids = _index_ids(text)
    before = _ANCHOR.search(text).group(1).strip() if _ANCHOR.search(text) else "?"
    new = _set_anchor(text, ids)
    if new == text:
        print(f"✅ ancre déjà d'accord avec l'index : {before or '(vide)'}")
        return 0
    CHECKLIST.write_text(new, encoding="utf-8")
    print(f"✅ ancre mise à jour : {before or '(vide)'} → {', '.join(ids) or '(vide)'}")
    return 0


def cmd_close(args) -> int:
    """Retire la ligne d'index, met l'ancre d'accord, et VERIFIE le format d'archive."""
    tid = args.id.upper()
    text = CHECKLIST.read_text(encoding="utf-8")

    rows = [ln for ln in text.splitlines() if re.match(rf"^\|\s*{tid}\s*\|", ln)]
    if not rows:
        print(f"❌ aucune ligne d'index pour {tid}. Index actuel : "
              f"{', '.join(_index_ids(text)) or '(vide)'}", file=sys.stderr)
        return 1
    if len(rows) > 1:
        print(f"❌ {len(rows)} lignes d'index pour {tid} — trancher à la main d'abord.",
              file=sys.stderr)
        return 1

    archive = ARCHIVE.read_text(encoding="utf-8")
    # ⚠️ LA verification qui manquait a la prose. Le test de conservation ne reconnait
    # un identifiant que sous ces deux formes ; une entree en titre `## Rxxx` est
    # invisible pour lui, et la tache est declaree « disparue des deux fichiers ».
    recognised = (re.search(rf"^\|\s*{tid}\s*\|", archive, re.M)
                  or re.search(rf"^- \[[xX]\] \*\*{tid}\b", archive, re.M))
    if not recognised:
        print(
            f"❌ {tid} n'est pas encore dans `archive.md` SOUS UNE FORME RECONNUE.\n"
            f"\n"
            f"   `tests/test_roadmap_two_files.py::test_no_brick_id_vanishes_from_both_files`\n"
            f"   ne lit que deux formes :\n"
            f"       | {tid} | … |            (ligne de tableau)\n"
            f"       - [x] **{tid} — …**       (case cochée)\n"
            f"\n"
            f"   Un titre `## {tid} — …` ne suffit PAS : la tâche serait comptée comme\n"
            f"   disparue des deux fichiers. Mesuré le 2026-09-17 sur R128 et R129.\n"
            f"\n"
            f"   Écrire l'entrée d'archive d'abord, puis relancer.", file=sys.stderr)
        return 1

    text = text.replace(rows[0] + "\n", "", 1)
    ids = _index_ids(text)
    text = _set_anchor(text, ids)
    CHECKLIST.write_text(text, encoding="utf-8")
    print(f"✅ {tid} retirée de l'index · ancre → {', '.join(ids) or '(vide)'}")
    print(f"   reste {len(ids)} tâche(s) ouverte(s)")
    print("   vérifier : python3 -m pytest tests/test_roadmap_two_files.py "
          "tests/test_the_resume_header_is_checked.py -q")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("close", help="retire une tâche de l'index et recale l'ancre")
    c.add_argument("id", help="identifiant, ex. R128")
    c.set_defaults(func=cmd_close)

    s = sub.add_parser("sync", help="remet l'ancre d'accord avec les deux tables d'index")
    s.set_defaults(func=cmd_sync)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
