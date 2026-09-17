#!/usr/bin/env python3
"""L'état d'une séance longue, dans un fichier — parce que le contexte ne survit pas.

Type: Utility
Uses: git, .claude/dev-docs/roadmap/checklist.md
Triggers: `make night-status` / `make night-log` / `make night-park`, à chaque réveil
Persists in: .claude/dev-docs/roadmap/night-run.jsonl (append-only)

Le problème que ça résout, et le seul
--------------------------------------
Sur une séance de plusieurs heures, le contexte est COMPACTÉ plusieurs fois. Après
chaque compaction je reviens avec un résumé : je sais ce qu'on fait, pas *où j'en suis
exactement*. Mesuré sur cette séance — une compaction en une journée de travail.

La roadmap dit **quoi** faire. Elle ne dit pas **où j'en suis** : elle se met à jour
quand une brique est livrée, pas quand un lot de six classes est à mi-chemin. Entre les
deux il y a un trou de plusieurs heures, et c'est exactement la granularité d'un réveil.

Ce fichier est le journal de cette granularité-là. Une seule commande — `status` — doit
répondre « où j'en suis » en un écran, sans relire l'historique ni deviner.

Trois choix, et leurs raisons
------------------------------
**JSONL append-only, jamais réécrit.** Un tour qui meurt au milieu ne peut pas corrompre
ce qui précède. Ce dépôt a déjà payé la réécriture en place : deux duplications de la
roadmap par un `s.index()` qui recopiait la queue, toutes deux le même matin.

**`park` au lieu de `stop`.** Un blocage qui arrête la séance consomme toutes les heures
restantes. Bloqué ⇒ on écrit la question, on passe à la suivante. La question va dans le
journal ET dans la roadmap, là où un humain la lit.

**`status` lit l'ARBRE, pas seulement le journal.** Un journal peut mentir par omission
— un tour tué avant son `done` laisse une unité ouverte pour toujours. Croiser avec
`git status` et `git log` rend le mensonge visible : « unité ouverte depuis 47 min, arbre
sale, 3 fichiers » est un diagnostic ; « unité ouverte » tout seul n'en est pas un.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROADMAP = REPO / ".claude" / "dev-docs" / "roadmap" / "checklist.md"
JOURNAL = REPO / ".claude" / "dev-docs" / "roadmap" / "night-run.jsonl"
PROTOCOL = REPO / ".claude" / "dev-docs" / "roadmap" / "night-run.md"

_INDEX_ROW = re.compile(r"^\|\s*(R\d+)\s*\|\s*(.+?)\s*\|\s*(P\d)\s*\|", re.M)


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append(record: dict) -> None:
    record["at"] = _now()
    record["head"] = _git("rev-parse", "--short", "HEAD")
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _entries() -> list[dict]:
    if not JOURNAL.exists():
        return []
    out = []
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            # Une ligne illisible n'efface pas les autres : c'est tout l'intérêt du
            # format. On la signale sans la perdre.
            out.append({"kind": "unreadable", "raw": line[:120]})
    return out


def _open_tasks() -> list[tuple[str, str, str]]:
    """L'index `## 📋 Tâches ouvertes` de la roadmap, dans son ordre."""
    if not ROADMAP.exists():
        return []
    text = ROADMAP.read_text(encoding="utf-8")
    start = text.find("## 📋 Tâches ouvertes")
    if start < 0:
        return []
    end = text.find("\n## ", start + 1)
    return _INDEX_ROW.findall(text[start:end if end > 0 else len(text)])


def _current_unit(entries: list[dict]) -> dict | None:
    """La dernière unité `start` qu'aucun `done`/`park` n'a refermée."""
    for entry in reversed(entries):
        if entry.get("kind") in ("done", "park"):
            return None
        if entry.get("kind") == "start":
            return entry
    return None


def _age_minutes(iso: str) -> int:
    try:
        then = datetime.fromisoformat(iso)
    except ValueError:
        return -1
    return int((datetime.now(timezone.utc) - then).total_seconds() // 60)


def _ancestors() -> set[int]:
    """Moi et toute ma lignée. Un processus ne se détecte pas lui-même."""
    out, pid = set(), os.getpid()
    while pid > 1 and pid not in out:
        out.add(pid)
        try:
            stat = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
            pid = int(stat.rsplit(") ", 1)[1].split()[1])
        except (OSError, IndexError, ValueError):
            break
    return out


def _suite_running() -> bool:
    """Une suite complète tourne-t-elle ? Écrire pendant fausse son verdict.

    ⚠️ Deux pièges, et j'ai marché dans le second en écrivant ce fichier.

    **`ps | grep` est intercepté** par le wrapper RTK, qui rend une sortie vide — quatre
    conclusions fausses le 2026-09-16 sur ce seul point. On lit donc `/proc`.

    **Et la sonde matchait le shell qui la portait.** Première version : `"pytest" in
    cmdline and "tests/" in cmdline`, sur le cmdline APLATI en une chaîne. Le shell qui
    exécutait cette commande porte le texte du script dans son propre `cmdline` — donc
    les deux mots — et `status` annonçait « UNE SUITE TOURNE » alors qu'aucune ne
    tournait. C'est `a-kill-pattern-that-matches-its-own-shell` à la lettre : un motif
    qui se contient lui-même. Le dépôt l'a payée trois fois le 2026-09-16 et une
    quatrième ici, dans un fichier écrit POUR rendre une séance longue fiable.

    Deux corrections, et il faut les deux : on lit les **jetons** d'argv (`\0`), jamais
    la chaîne aplatie — `pytest` doit être un argument entier, pas un mot dans une
    phrase — et on exclut sa propre lignée.
    """
    mine = _ancestors()
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) in mine:
            continue
        try:
            argv = [a for a in (proc / "cmdline").read_bytes().split(b"\0") if a]
        except OSError:
            continue
        tokens = [a.decode("utf-8", "replace") for a in argv]
        is_pytest = any(tok == "pytest" or tok.endswith("/pytest") for tok in tokens)
        targets_suite = any(tok == "tests" or tok.startswith("tests/") for tok in tokens)
        if is_pytest and targets_suite:
            return True
    return False


def open_questions(entries: list[dict]) -> list[dict]:
    """Les `park` qu'aucun `done` POSTÉRIEUR n'a tranchés.

    Extraite du corps de `cmd_status` le 2026-09-17, et pour une raison mesurée : la
    règle y était en ligne, donc le test qui la vérifiait en rejouait une COPIE. Muter
    le module laissait ses assertions de comportement VERTES — seul le contrôle textuel
    rougissait. Un garde qui teste son propre double ne garde rien.

    Le critère est l'ORDRE, pas la présence : un `done` postérieur referme la question,
    un `park` postérieur à un `done` la rouvre (tâche reprise puis rebloquée).
    """
    answered: set[str] = set()
    for e in entries:
        task = e.get("task")
        if not task:
            continue
        if e.get("kind") == "done":
            answered.add(task)
        elif e.get("kind") == "park":
            answered.discard(task)
    return [e for e in entries
            if e.get("kind") == "park" and e.get("task") not in answered]


def cmd_status(_args) -> int:
    entries = _entries()
    tasks = _open_tasks()
    dirty = [ln for ln in _git("status", "--short").splitlines() if ln.strip()]
    unpushed = _git("log", "--oneline", "@{u}..HEAD") if _git("rev-parse",
                                                             "--abbrev-ref",
                                                             "@{u}") else "?"

    print("═" * 72)
    print(f"  OÙ J'EN SUIS — {_now()}")
    print("═" * 72)

    unit = _current_unit(entries)
    if unit:
        age = _age_minutes(unit.get("at", ""))
        print(f"\n▶ EN COURS  [{unit.get('task', '?')}]  {unit.get('what', '')}")
        print(f"  ouverte depuis {age} min (commencée à {unit.get('at')})")
        if age > 90:
            print("  ⚠️  Plus de 90 min : soit un tour est mort avant son `done`, soit "
                  "l'unité est trop grosse. Relire le diff AVANT de repartir.")
    else:
        print("\n▶ EN COURS  aucune unité ouverte — prendre la suivante ci-dessous")

    print(f"\n▶ ARBRE     HEAD {_git('rev-parse', '--short', 'HEAD')} · "
          f"{len(dirty)} fichier(s) non commité(s)")
    for line in dirty[:8]:
        print(f"              {line}")
    if len(dirty) > 8:
        print(f"              … et {len(dirty) - 8} de plus")
    if unpushed and unpushed != "?":
        print(f"  ⚠️  {len(unpushed.splitlines())} commit(s) non poussé(s)")
    if _suite_running():
        print("  ⚠️  UNE SUITE TOURNE — ne pas écrire dans l'arbre : son verdict "
              "décrirait un arbre qui n'existe plus.")

    print(f"\n▶ ROADMAP   {len(tasks)} tâche(s) ouverte(s), dans l'ordre de l'index :")
    for tid, label, prio in tasks:
        print(f"              {tid:<5} {prio}  {label[:88]}")

    # Une question parquée que sa PROPRE tâche a fini par trancher cesse d'être une
    # question. Ceci listait tous les `park` du journal, sans jamais les retirer :
    # R117 a été parquée le 2026-09-17 au matin (« déplacer le dépôt tue la session
    # qui le fait ») puis LIVRÉE le même jour, et `night-status` a continué de la
    # poser. Un écran de reprise qui affirme un blocage résolu envoie chercher une
    # décision déjà prise — famille `un-document-qui-affirme-un-état-périmé`.
    #
    # Le critère est l'ORDRE, pas la simple présence : un `done` postérieur au `park`
    # le referme ; un `park` postérieur à un `done` rouvre bel et bien la question.
    parked = open_questions(entries)
    if parked:
        print(f"\n▶ PARQUÉ    {len(parked)} question(s) en attente d'un humain :")
        for entry in parked[-5:]:
            print(f"              [{entry.get('task', '?')}] {entry.get('what', '')[:78]}")

    print("\n▶ JOURNAL   les 6 dernières entrées :")
    for entry in entries[-6:]:
        kind = entry.get("kind", "?")
        print(f"              {entry.get('at', '')[:16]}  {kind:<5} "
              f"[{entry.get('task', '-')}] {entry.get('what', '')[:60]}")
    if not entries:
        print("              (vide — première unité de la séance)")
    print()
    return 0


def cmd_start(args) -> int:
    _append({"kind": "start", "task": args.task, "what": args.what})
    print(f"unité ouverte : [{args.task}] {args.what}")
    return 0


def cmd_done(args) -> int:
    _append({"kind": "done", "task": args.task, "what": args.what})
    print(f"unité fermée : [{args.task}] {args.what}")
    return 0


def cmd_park(args) -> int:
    _append({"kind": "park", "task": args.task, "what": args.what})
    print(f"PARQUÉ [{args.task}] : {args.what}")
    print("→ écrire la même question dans « 🙋 En attente de toi » de la roadmap, "
          "puis passer à la tâche suivante. Ne pas s'arrêter dessus.")
    return 0


def cmd_note(args) -> int:
    _append({"kind": "note", "task": args.task, "what": args.what})
    return 0


def cmd_check(_args) -> int:
    """Les invariants d'une séance longue. Sort ≠ 0 quand il y a à redire."""
    problems = []
    entries = _entries()
    unit = _current_unit(entries)
    if unit and _age_minutes(unit.get("at", "")) > 180:
        problems.append(f"unité [{unit.get('task')}] ouverte depuis plus de 3 h")
    # ⚠️ Le JOURNAL lui-même est exclu, et c'est un correctif, pas une commodité.
    # `night-done` écrit une ligne APRÈS le commit de l'unité — il ne peut pas faire
    # autrement, il enregistre le sha. L'arbre était donc sale à chaque fin d'unité et
    # `night-check` rouge à coup sûr : un invariant qui ne peut jamais tenir est un
    # invariant qu'on apprend à ignorer, ce qui est pire que pas d'invariant du tout.
    # Le journal est de la comptabilité ; il part avec le commit de l'unité SUIVANTE.
    dirty = [ln for ln in _git("status", "--short").splitlines()
             if ln.strip() and JOURNAL.name not in ln]
    if dirty:
        problems.append(f"arbre sale ({len(dirty)}) — une unité finie se commite "
                        "avant la suivante")
    if _git("rev-parse", "--abbrev-ref", "@{u}") and _git("log", "--oneline",
                                                          "@{u}..HEAD"):
        problems.append("commits non poussés — un arrêt les perdrait de vue")
    if not PROTOCOL.exists():
        problems.append(f"{PROTOCOL.relative_to(REPO)} absent")
    for problem in problems:
        print(f"⚠️  {problem}")
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="où j'en suis, en un écran").set_defaults(fn=cmd_status)
    sub.add_parser("check", help="les invariants ; ≠ 0 s'il y a à redire").set_defaults(
        fn=cmd_check)
    for name, fn, helptext in (
            ("start", cmd_start, "j'ouvre une unité de travail"),
            ("done", cmd_done, "je la ferme"),
            ("park", cmd_park, "bloqué : j'écris la question et je passe"),
            ("note", cmd_note, "un fait à ne pas perdre")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("task", help="l'identifiant de roadmap, ex. R122")
        p.add_argument("what", help="une phrase, au présent")
        p.set_defaults(fn=fn)
    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
