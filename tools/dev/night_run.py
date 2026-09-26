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

# ⚠️ La priorité est FACULTATIVE dans ce motif, et c'est un correctif du 2026-09-17.
# Il exigeait `(P\d)`, donc une ligne d'index dont la priorité vaut `—`, `?` ou rien
# disparaissait de `night-status` SANS erreur : la tâche existait dans la roadmap et
# n'existait pas à l'écran. Un écran de reprise qui perd une ligne sur un champ
# accessoire est pire qu'un écran qui refuse de s'afficher.
_INDEX_ROW = re.compile(r"^\|\s*(R\d+)\s*\|\s*(.+?)\s*\|\s*([^|]*?)\s*\|", re.M)


class GitUnavailable(RuntimeError):
    """`git` n'a pas répondu — on ne sait RIEN de l'arbre, ce n'est pas « propre »."""


def _git(*args: str) -> str:
    """La sortie de `git`, ou une LEVÉE. Ne rend jamais `""` sur un échec.

    ⚠️ Ceci avalait `OSError`/`SubprocessError`/timeout et rendait `""`. Dans
    `cmd_check`, `dirty = []` s'ensuivait, donc aucun problème signalé, donc **exit 0** :
    un `git` indisponible rendait le contrôle VERT. C'est
    `une-erreur-avalée-devient-une-absence` dans le garde qui doit justement dire si
    l'arbre est propre.
    """
    try:
        return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitUnavailable(f"git {' '.join(args)} : {type(exc).__name__}") from exc


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


# Les DEUX tables d'index de la roadmap. Une tâche qui attend un humain est OUVERTE ;
# elle n'est simplement pas commençable par une séance.
_INDEX_SECTIONS = ("## 📋 Tâches ouvertes", "## 🙋 En attente de toi")


def _section(text: str, title: str) -> str:
    """Le corps d'une section, découpé sur des titres EN DÉBUT DE LIGNE.

    ⚠️ `text.find(title)` trouvait la première OCCURRENCE, y compris dans la prose qui
    parle de la section. C'est le défaut exact que
    `tests/test_roadmap_index_is_honest.py:48-58` documente avoir expédié le 2026-08-21
    et corrigé par `re.search(..., re.M)` — corrigé dans le test, jamais propagé ici.
    Classe `a-document-slice-bounded-by-the-wrong-heading-level`.
    """
    m = re.search(r"^" + re.escape(title), text, re.M)
    if not m:
        return ""
    nxt = re.search(r"^## ", text[m.end():], re.M)
    return text[m.end():m.end() + nxt.start()] if nxt else text[m.end():]


def _open_tasks() -> list[tuple[str, str, str]]:
    """Les tâches ouvertes de la roadmap — LES DEUX tables, dans leur ordre.

    ⚠️ Ceci ne lisait que `## 📋 Tâches ouvertes`. Le 2026-09-17, R124 a été déplacée
    vers `## 🙋 En attente de toi` — sa place légitime, elle attend une session
    authentifiée en production — et cet écran a annoncé **« 0 tâche(s) ouverte(s) »**
    sur un dépôt qui en avait une. Le total a été rapporté au propriétaire comme vrai.

    C'est l'écran qu'on lit EN PREMIER après chaque compaction : s'y tromper sur un
    total est la façon la plus directe de faire oublier une tâche.
    """
    if not ROADMAP.exists():
        return []
    text = ROADMAP.read_text(encoding="utf-8")
    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for title in _INDEX_SECTIONS:
        for row in _INDEX_ROW.findall(_section(text, title)):
            if row[0] not in seen:
                seen.add(row[0])
                rows.append(row)
    return rows


def _current_unit(entries: list[dict]) -> dict | None:
    """La dernière unité `start` qu'aucun `done`/`park` DE LA MÊME TÂCHE n'a refermée.

    ⚠️ Ceci sortait au premier `done`/`park` rencontré, **quelle que soit sa tâche**.
    `start R124` puis `done R99` rendait « aucune unité ouverte » alors que R124
    courait toujours — et l'invariant des 3 h de `night-check` ne pouvait plus
    la voir. Le journal porte un champ `task` ; il suffisait de le lire.
    """
    closed: set[str] = set()
    for entry in reversed(entries):
        task = entry.get("task")
        kind = entry.get("kind")
        if kind in ("done", "park"):
            if task:
                closed.add(task)
            continue
        if kind == "start" and task not in closed:
            return entry
    return None


def _age_minutes(iso: str) -> int | None:
    """L'âge en minutes, ou `None` si l'horodatage est illisible.

    ⚠️ Ceci rendait **-1** sur `ValueError`. `-1 > 90` et `-1 > 180` sont faux, donc
    l'avertissement de `status` ET l'invariant de `check` disparaissaient sans un mot :
    un horodatage corrompu désarmait les deux seuils en se faisant passer pour une
    unité toute jeune. `une-erreur-avalée-devient-une-absence`.

    `None` force l'appelant à décider, et les deux appelants le disent maintenant.
    """
    try:
        then = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return None
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


MAIL_JOURNAL = REPO / ".claude" / "dev-docs" / "ops-mail-journal.md"


def mail_journal_age_days(text: str, today: str) -> "int | None":
    """Days since the newest `| YYYY-MM-DD` row of the ops mail journal, or None. Pure."""
    dates = re.findall(r"^\| (\d{4}-\d{2}-\d{2})", text, re.M)
    if not dates:
        return None
    newest = max(datetime.fromisoformat(d) for d in dates)
    return (datetime.fromisoformat(today) - newest).days


def cmd_status(_args) -> int:
    entries = _entries()
    tasks = _open_tasks()
    try:
        dirty = [ln for ln in _git("status", "--short").splitlines() if ln.strip()]
    except GitUnavailable as exc:
        print(f"\n▶ ARBRE     ⚠️ git n'a pas répondu ({exc}) — état INCONNU")
        dirty = []
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
        if age is None:
            # On le DIT. La version d'avant rendait -1, qui s'affichait « -1 min » et
            # passait sous les deux seuils : un horodatage corrompu ressemblait à une
            # unité toute neuve.
            print(f"  ⚠️  horodatage ILLISIBLE ({unit.get('at')!r}) — l'âge de cette "
                  "unité est inconnu, et le seuil des 90 min ne peut pas s'appliquer")
        else:
            print(f"  ouverte depuis {age} min (commencée à {unit.get('at')})")
            if age > 90:
                print("  ⚠️  Plus de 90 min : soit un tour est mort avant son `done`, "
                      "soit l'unité est trop grosse. Relire le diff AVANT de repartir.")
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
    # ── Les mails automatiques, que le propriétaire ne lit pas (2026-09-26) ──────
    try:
        age = mail_journal_age_days(MAIL_JOURNAL.read_text(encoding="utf-8"),
                                    _now()[:10])
    except OSError:
        age = None
    if age is None or age >= 1:
        print(f"\n▶ MAILS     📬 journal {'absent' if age is None else f'vieux de {age} j'} — "
              "chercher `from:noreply@streamlytics.fr` depuis la dernière ligne et trier "
              f"dans {MAIL_JOURNAL.relative_to(REPO)}")

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


def _reopening_conditions_met() -> list[str]:
    """Les tâches closes dont la condition de réouverture est REMPLIE.

    ⚠️ Branché ici le 2026-09-17, et la raison est le défaut qui l'a fait écrire :
    `tools/dev/reopen_check.py` est né parce que onze conditions de réouverture étaient
    écrites et **aucune évaluée**. Le laisser sans appelant aurait reproduit ce défaut
    d'un cran — un outil que rien ne lance ne dit rien à personne.

    Une panne de l'évaluateur ne rend PAS une liste vide : elle rend une ligne qui le
    dit. Une liste vide se lit « rien à rouvrir ».
    """
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "reopen_check", REPO / "tools" / "dev" / "reopen_check.py")
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(REPO))
        spec.loader.exec_module(mod)
    except Exception as exc:                                    # noqa: BLE001
        return [f"conditions de réouverture NON VÉRIFIÉES ({type(exc).__name__}) — "
                f"`make reopen-check` le dira"]
    out = []
    for trigger in getattr(mod, "TRIGGERS", []):
        verdict, detail = trigger.run()
        if verdict == mod.MET:
            out.append(f"[{trigger.task}] sa condition de réouverture est REMPLIE : "
                       f"{detail} — `make reopen-check`")
    return out


def red_main(runs: list[dict]) -> "str | None":
    """What to say when main's CI is red, from `gh run list --json` rows. Pure.

    Counts the consecutive FAILED completed runs from the newest; a cancelled run
    (superseded by a newer push) neither breaks nor extends the streak. None when the
    newest verdict is not a failure.
    """
    done = [r for r in runs if r.get("status") == "completed"
            and r.get("conclusion") != "cancelled"]
    done.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
    streak = 0
    for r in done:
        if r.get("conclusion") != "failure":
            break
        streak += 1
    if not streak:
        return None
    return (f"la CI de main est ROUGE depuis {streak} exécution(s) — la plus récente : "
            f"« {done[0].get('displayTitle', '?')[:60]} ». Lire le job rouge "
            "(`gh run view <id> --log-failed`) AVANT l'unité suivante")


def _main_ci_runs() -> "list[dict] | None":
    try:
        r = subprocess.run(
            ["gh", "run", "list", "--branch", "main", "--limit", "30", "--json",
             "status,conclusion,createdAt,displayTitle"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO))
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def cmd_check(_args) -> int:
    """Les invariants d'une séance longue. Sort ≠ 0 quand il y a à redire."""
    problems = _reopening_conditions_met()
    entries = _entries()
    unit = _current_unit(entries)
    if unit:
        age = _age_minutes(unit.get("at", ""))
        if age is None:
            problems.append(
                f"unité [{unit.get('task')}] : horodatage illisible "
                f"({unit.get('at')!r}) — son âge est INCONNU, l'invariant des 3 h n'a "
                "rien pu vérifier")
        elif age > 180:
            problems.append(f"unité [{unit.get('task')}] ouverte depuis plus de 3 h")
    # ⚠️ Le JOURNAL lui-même est exclu, et c'est un correctif, pas une commodité.
    # `night-done` écrit une ligne APRÈS le commit de l'unité — il ne peut pas faire
    # autrement, il enregistre le sha. L'arbre était donc sale à chaque fin d'unité et
    # `night-check` rouge à coup sûr : un invariant qui ne peut jamais tenir est un
    # invariant qu'on apprend à ignorer, ce qui est pire que pas d'invariant du tout.
    # Le journal est de la comptabilité ; il part avec le commit de l'unité SUIVANTE.
    # ⚠️ `git` muet est un PROBLÈME, jamais un arbre propre. Avant le 2026-09-17,
    # `_git` avalait l'échec et rendait `""` : `dirty` valait `[]`, aucun problème
    # n'était signalé, et `night-check` sortait VERT sur une machine où git ne
    # répondait pas. Le garde censé dire si l'arbre est propre affirmait qu'il l'était.
    try:
        dirty = [ln for ln in _git("status", "--short").splitlines()
                 if ln.strip() and JOURNAL.name not in ln]
        if dirty:
            problems.append(f"arbre sale ({len(dirty)}) — une unité finie se commite "
                            "avant la suivante")
        if _git("rev-parse", "--abbrev-ref", "@{u}") and _git("log", "--oneline",
                                                              "@{u}..HEAD"):
            problems.append("commits non poussés — un arrêt les perdrait de vue")
    except GitUnavailable as exc:
        problems.append(f"git n'a pas répondu ({exc}) — ce contrôle n'a RIEN vérifié "
                        "sur l'arbre ni sur les commits non poussés")
    if not PROTOCOL.exists():
        problems.append(f"{PROTOCOL.relative_to(REPO)} absent")

    # ── LA CI DE MAIN ────────────────────────────────────────────────────────────
    #
    # Mesuré le 2026-09-26 : main est restée rouge toute une nuit — **plus de 60
    # exécutions** — pendant que chaque unité passait `make test-changed` au vert et
    # que ce contrôle rendait 0. Deux causes s'empilaient (une durée manquante, puis
    # un document généré périmé), la première cachant la seconde. Le verdict qui
    # compte est celui de la CI : on le lit ici, à chaque fin d'unité.
    runs = _main_ci_runs()
    if runs is None:
        print("ℹ️  CI de main non vérifiée — `gh` absent ou muet ; ce contrôle n'a rien "
              "dit de la CI")
    else:
        rouge = red_main(runs)
        if rouge:
            problems.append(rouge)

    # ── UNE FERMETURE SANS OUVERTURE ────────────────────────────────────────────
    #
    # ⚠️ Trouvé le 2026-09-22 EN LE COMMETTANT : `night-done TASK=R161` lancé sans
    # `night-start`. Le journal est append-only, donc la ligne `start` manquante ne se
    # rattrape pas — et `night-check` restait **VERT**, parce qu'il ne cherchait qu'une
    # unité OUVERTE depuis plus de 3 h. Une unité fermée sans avoir été ouverte n'a
    # aucune durée, aucun sha de départ, et ne figure dans aucun écran de reprise :
    # après une compaction, le travail qu'elle nomme est invisible.
    #
    # C'est la même forme que `a-status-screen-that-reads-half-its-source` — l'écran
    # lisait une moitié de son invariant. La portée est étroite : on ne signale qu'une
    # `done`/`park` dont AUCUN `start` de la même tâche ne précède, et on ne remonte
    # pas au-delà du journal.
    # ⚠️ L'EXEMPTION SE VÉRIFIE, elle ne se code pas en dur. Le premier jet signalait
    # toute fermeture orpheline et rougissait donc POUR TOUJOURS sur R117, une orpheline
    # du 2026-09-17 que ce garde a découverte en naissant. Y répondre par une liste de
    # noms aurait produit exactement ce que ce dépôt a vidé le matin même : une
    # exemption qui survit à sa raison.
    #
    # Le remède est celui que le message prescrit déjà : le journal est append-only,
    # donc la ligne manquante s'écrit dans `archive.md`. Une orpheline est donc
    # ACCEPTABLE si et seulement si sa brique y est archivée — et cette condition se
    # vérifie à chaque exécution, sans nommer personne.
    archive = REPO / ".claude" / "dev-docs" / "roadmap" / "archive.md"
    try:
        archivees = archive.read_text(encoding="utf-8")
    except OSError as exc:
        problems.append(f"{archive.name} illisible ({exc}) — les fermetures orphelines "
                        "n'ont RIEN pu être vérifiées contre l'archive")
        archivees = None

    starts = {e.get("task") for e in entries if e.get("kind") == "start"}
    orphelines = sorted({e.get("task") for e in entries
                         if e.get("kind") in ("done", "park")
                         and e.get("task") and e.get("task") not in starts})
    if orphelines and archivees is not None:
        muettes = [t for t in orphelines
                   if f"**{t} —" not in archivees and f"**{t} -" not in archivees]
        if muettes:
            problems.append(
                f"unité(s) fermée(s) sans jamais avoir été ouverte(s), ET absente(s) "
                f"de l'archive : {', '.join(muettes)} — pas de durée, pas de sha de "
                "départ, et aucun récit. Le journal est append-only : la ligne "
                "manquante s'écrit dans `archive.md`, sous un bloc `- [x] **<id> — …**`.")

    # ── Le journal et la roadmap doivent parler des MÊMES tâches ────────────────
    #
    # ⚠️ Deux défauts fermés ici, tous deux vérifiés le 2026-09-17 :
    #
    # 1. `make night-note TASK=R999` était accepté et journalisé, et `night-check`
    #    ne le voyait pas. Un identifiant inventé — ou une faute de frappe sur un
    #    vrai — produisait une unité que personne ne pouvait relier à du travail.
    #
    # 2. `cmd_park` IMPRIME « écrire la même question dans "🙋 En attente de toi" de
    #    la roadmap », et `night-run.md` répète la consigne. **Rien ne le vérifiait.**
    #    Une question parquée qui n'est jamais écrite dans `checklist.md` n'existe
    #    pour aucun humain : elle vit dans un JSONL que seul cet écran lit.
    #
    # La portée est étroite à dessein : on ne vérifie que ce qui est ENCORE OUVERT —
    # l'unité en cours et les questions non refermées. Les tâches livrées ont quitté
    # l'index pour l'archive, et exiger qu'elles y soient encore ferait rougir le
    # contrôle sur chaque brique close.
    known = {tid for tid, _, _ in _open_tasks()}
    if known:
        pending = []
        if unit and unit.get("task"):
            pending.append(("unité en cours", unit["task"]))
        pending += [("question parquée", e["task"]) for e in open_questions(entries)
                    if e.get("task")]
        for kind, task in pending:
            if task not in known:
                problems.append(
                    f"{kind} [{task}] : aucune ligne d'index de la roadmap ne porte "
                    "cet identifiant. Soit la tâche n'y a jamais été écrite, soit "
                    "c'est une faute de frappe — dans les deux cas le journal et la "
                    "roadmap racontent deux histoires différentes")
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
