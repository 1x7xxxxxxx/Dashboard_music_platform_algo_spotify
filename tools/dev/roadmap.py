#!/usr/bin/env python3
"""Ouvre et ferme une tache de roadmap sur ses TROIS surfaces, d'un seul geste.

Type: Utility
Uses: pathlib, re, argparse
Triggers: make roadmap-close / make roadmap-sync, .claude/commands/roadmap-done.md
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

R199 (2026-09-26) — LE chemin de rotation, et il DÉPLACE
----------------------------------------------------------
Trois chemins se contredisaient (`/roadmap-done`, `roadmap-keeper`, cet outil) et celui-ci
ne déplaçait rien : il exigeait qu'on ait déjà écrit l'archive à la main. Désormais, quand
l'archive ne porte pas encore la tâche, `close` ÉCRIT son entrée en tête — le texte de la
ligne d'index, sa mesure, et les commits qui la LIVRENT — puis retire la ligne et recale
l'ancre. Preuve de livraison exigée : au moins un commit qui cite l'id ET touche autre chose
que les deux fichiers de roadmap (« Roadmap : Rnnn inscrite » ne livre rien — code-critic).
Une seconde fermeture échoue : la ligne n'est plus ouverte.

Ce que l'outil ne fait PAS : il n'écrit pas le RÉCIT d'une livraison (`NOTE=` en ajoute une
ligne). Une brique entière, avec sa leçon, reste le travail de `roadmap-keeper`.
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


_ROADMAP_FILES = {".claude/dev-docs/roadmap/checklist.md", ".claude/dev-docs/roadmap/archive.md"}


def delivery_commits(tid: str) -> list[str]:
    """`<sha court> <sujet>` des commits qui citent `tid` ET touchent autre chose que la
    roadmap — un commit d'inscription ou d'archive ne livre rien."""
    import subprocess
    log = subprocess.run(["git", "-C", str(ROOT), "log", "--format=%H%x1f%h%x1f%s%x1f%b%x1e",
                          "-n", "3000"], capture_output=True, text=True).stdout
    out = []
    for rec in log.split("\x1e"):
        parts = rec.strip("\n").split("\x1f")
        if len(parts) < 4 or not re.search(rf"\b{tid}\b", parts[2] + " " + parts[3]):
            continue
        files = subprocess.run(["git", "-C", str(ROOT), "diff-tree", "--root", "--no-commit-id",
                                "--name-only", "-r", parts[0]],
                               capture_output=True, text=True).stdout.split()
        if any(f not in _ROADMAP_FILES for f in files):
            out.append(f"{parts[1]} {parts[2][:70]}")
    return out


def archive_block(row: str, commits: list[str], note: str, today: str) -> str:
    """L'entrée d'archive d'une ligne d'index. Forme lue par la conservation : `- [x] **Rnnn`."""
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    tid, task = cells[0], re.sub(r"\s*<!--.*?-->", "", cells[1]).strip()
    prio = cells[2] if len(cells) > 2 else ""
    measured = cells[3] if len(cells) > 3 else ""
    shas = ", ".join(c.split()[0] for c in commits)
    short = task if len(task) <= 90 else task[:87].rstrip() + "…"
    lines = [f"## ✅ {tid} — {short} (livrée {today})", "",
             f"- [x] **{tid} — {task}** ({prio}) ✅ ({today}, {shas})"]
    if measured:
        lines.append(f"  Mesuré par : {measured}")
    if note:
        lines.append(f"  {note}")
    lines += [f"  Commits : {' · '.join(commits)}", ""]
    return "\n".join(lines) + "\n"


def _insert_at_top(archive: str, block: str) -> str:
    """Juste après le premier séparateur `---` de l'en-tête : les plus récentes en tête."""
    marker = "\n---\n"
    i = archive.find(marker)
    if i < 0:
        return archive.rstrip("\n") + "\n\n" + block
    j = i + len(marker)
    return archive[:j] + "\n" + block + "\n" + archive[j:].lstrip("\n")


def cmd_close(args) -> int:
    """Retire la ligne d'index, ÉCRIT l'entrée d'archive si elle manque, recale l'ancre."""
    tid = args.id.upper()
    text = CHECKLIST.read_text(encoding="utf-8")

    rows = [ln for ln in text.splitlines() if re.match(rf"^\|\s*{tid}\s*\|", ln)]
    if not rows:
        print(f"❌ {tid} n'est pas ouverte (déjà fermée ?). Index actuel : "
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
        commits = delivery_commits(tid)
        if commits:
            import datetime as _dt
            block = archive_block(rows[0], commits, getattr(args, "note", "") or "",
                                  _dt.date.today().isoformat())
            ARCHIVE.write_text(_insert_at_top(archive, block), encoding="utf-8")
            print(f"✅ entrée d'archive écrite pour {tid} ({len(commits)} commit(s) de livraison)")
            recognised = True
    if not recognised:
        print(
            f"❌ {tid} : aucun commit ne la LIVRE (un commit qui la cite et touche autre "
            "chose que la roadmap), et `archive.md` ne la porte pas encore.\n", file=sys.stderr)
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
    c.add_argument("--note", default="", help="une ligne ajoutée à l'entrée d'archive")
    c.set_defaults(func=cmd_close)

    s = sub.add_parser("sync", help="remet l'ancre d'accord avec les deux tables d'index")
    s.set_defaults(func=cmd_sync)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
