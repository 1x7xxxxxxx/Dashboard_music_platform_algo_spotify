#!/usr/bin/env python3
"""
Hook PreToolUse — Guard against destructive Bash commands.

Intercepts Bash tool calls before execution.
- BLOCKING (exit 2): truly irreversible operations that should never run silently
- ADVISORY (exit 0): risky operations that print a warning but are allowed through

Always exits 0 for non-Bash tools and safe commands.

---
rex:
  - date: 2026-04-24
    issue: "Guards SQLite-specific post-migration PG + aucun équivalent DROP SCHEMA / dropdb / alembic destructive downgrade"
    fix: "Retiré rm sensor_data.db + PRAGMA journal_mode; ajouté block DROP SCHEMA + dropdb + ALEMBIC_ALLOW_DESTRUCTIVE_DOWNGRADE=1; warn alembic downgrade"
    severity: warn
  - date: 2026-10-19
    issue: "Une cible détruite n'était jugée qu'à travers rm : shred -u ~/.ssh/…, > ~/.bashrc, truncate -s0, cp|ln -sf /dev/null passaient ; cd ~ && rm -rf . était jugé dans le dossier du hook (T167, REX R76)"
    fix: "Table _OVERWRITERS (rm, shred, truncate, dd, cp|mv|install depuis /dev/null, ln -f, tee, sed -i … d) + redirections >, >|, &> ; prédicat overwrite-protected-path ; dossier de chaque commande suivi à travers cd/&&/;/||/( ) ; _DESTRUCTIVE et _xargs_kills dérivés de la table"
    severity: crit
---
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import sys as _sys  # R365 — one trace line per run, even for a silent hook
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "hooks"))
from _hook_trace import trace as _trace  # noqa: E402
_trace(__file__)


# ── Patterns ──────────────────────────────────────────────────────────────────

# Blocking: exit 2 — Claude must explain and get explicit confirmation
_BLOCK_PATTERNS: list[tuple[str, str]] = [
    ("git push --force",        "Force push overwrites remote history — use 'git push' instead. Every spelling counts: --force, -f, +<ref>, and since 2026-10-18 --force-with-lease and --force-if-includes too (a lease is still a rewrite: the owner decides it)"),
    ("git push -f ",            "Force push overwrites remote history — use 'git push' instead. Every spelling counts: --force, -f, +<ref>, and since 2026-10-18 --force-with-lease and --force-if-includes too (a lease is still a rewrite: the owner decides it)"),
    ("git reset --hard",        "Hard reset discards all uncommitted changes permanently"),
    ("git checkout -- .",       "Discards all uncommitted changes in working directory"),
    ("git restore .",           "Discards all uncommitted changes in working directory"),
    ("git clean -f",            "Permanently deletes untracked files"),
    ("docker system prune",     "Removes ALL unused Docker data including named volumes"),
    # `rm -rf /` etait compare en SOUS-CHAINE : il bloquait donc `rm -rf
    # /tmp/scratch`, l'idiome le plus courant et le plus inoffensif. Mesure le
    # 2026-07-30 sur le banc : 8 cellules sur 12 de la variante `arch` sur Opus
    # ont ete bloquees par ce garde, parce qu'Opus construit ses reproductions
    # dans des dossiers jetables (9 cellules sur 12, contre 1 sur 12 pour
    # Sonnet). Le garde cense proteger la racine interdisait le travail.
    #
    # Il devient une expression reguliere : la racine elle-meme, ou un chemin
    # systeme. `/tmp`, `/var/tmp` et tout chemin relatif passent.
    ("DROP TABLE",              "Irreversible PG/SQL table deletion"),
    ("DROP DATABASE",           "Irreversible database deletion"),
    ("DROP SCHEMA",             "Irreversible PG schema deletion (CASCADE loses all tables, alembic_version row, and dependent objects)"),
    ("dropdb ",                 "Drops an entire PostgreSQL database — irreversible"),
    # ── Repo policy: the pre-commit chain is the secret scanner ──────────
    ("git commit --no-verify",   "Skipping pre-commit hooks bypasses secret scanning"),
    ("git commit -n ",           "Skipping pre-commit hooks bypasses secret scanning"),
    # R444: the pre-push hook refuses a tree never seen green; skipping it is the
    # owner's call at the terminal, not a reflex of the model.
    ("git push --no-verify",     "Skipping the pre-push hook pushes a tree make test-changed never saw green (R444)"),
]

# Regex tier — the seven gates ARCH Ch.17 prescribes. These genuinely need
# regex: the literal-substring tier below cannot express them. A recursive
# delete as root does not contain the literal used by the substring list, a
# double space or a swapped flag order evades a literal match entirely, and a
# download piped into a shell has arbitrary text between the two halves.
#
# Threat model (ARCH p.164): these guard against ACCIDENTS caused by the model
# or by the developer through it. They are not a boundary against an adversary
# who controls the prompt.
_BLOCK_REGEX: list[tuple[str, str]] = [
    (r"curl\s+[^|]*\|\s*(sudo\s+)?(ba|z|k)?sh",
     "Piping a download into a shell executes unreviewed remote code"),
    (r"wget\s+[^|]*\|\s*(sudo\s+)?(ba|z|k)?sh",
     "Piping a download into a shell executes unreviewed remote code"),
    (r"\bsudo\s+rm\b",
     "Recursive delete as root — verify the path outside Claude Code"),
    # 2026-10-18 : drapeaux séparés ou répétés (`rm -r -f /`), `--`, la racine en glob
    # (`/*`), et la maison citée (`"$HOME"`, `${HOME}`) — quatre orthographes qui passaient.
    (r"""\brm\s+(?:-\S*\s+)*?(?:-[a-z]*[rf][a-z]*|--recursive|--force)\s+(?:-\S*\s+)*"""
     r"""(["']?)(?:/+\*?\1(?=\s|[;&|)]|$)|(?:~|\$HOME|\$\{HOME\})(?=["'/\s;&|)]|$))""",
     "Recursive delete of a root or home path — catastrophic"),
    # Les chemins SYSTEME, nommes un par un. Ils etaient couverts jusqu'au
    # 2026-07-30 par la sous-chaine `"rm -rf /"` de `_BLOCK_PATTERNS` — qui
    # bloquait du meme coup `rm -rf /tmp/scratch`, l'idiome le plus courant et le
    # plus inoffensif. Mesure sur le banc : 8 cellules sur 12 de la variante
    # `arch` sur Opus bloquees par ce garde, parce qu'Opus construit ses
    # reproductions dans des dossiers jetables (9 sur 12, contre 1 sur 12 pour
    # Sonnet). Le garde cense proteger la racine interdisait le travail.
    #
    # `/tmp`, `/var/tmp` et tout chemin relatif passent maintenant — avec un
    # avertissement, qui reste dans `_WARN_PATTERNS`.
    (r"\brm\s+(-\S+\s+)*[\"']?/(etc|usr|bin|sbin|lib|lib64|boot|dev|proc|sys|root"
     r"|home|srv|opt)(/|\s|$|[\"'])",
     "Recursive delete of a system path — catastrophic"),
    (r"\brm\s+(-\S+\s+)*[\"']?/var/(?!tmp)",
     "Recursive delete under /var — catastrophic"),
    (r"\bmkfs\.",
     "Filesystem creation destroys every byte on the target device"),
    (r"\bdd\b[^\n]*\bof=/dev/",
     "Block-device write destroys the existing filesystem"),
    # 2026-10-18 : `0777`, `a+rwx`, `ugo+rwx` — le même mode, trois orthographes qui passaient.
    (r"\bchmod\s+(?:-\S+\s+)*(?:0*777|[ugoa]*[ao][ugoa]*[+=]rwx)\b",
     "World-writable permissions — never correct on a real path"),
    (r":\s*\(\s*\)\s*\{[^}]*\|[^}]*&[^}]*\}\s*;?\s*:",
     "Fork bomb — exhausts the process table"),
]

# Advisory: exit 0 — prints warning but allows through
_WARN_PATTERNS: list[tuple[str, str]] = [
    ("rm -rf",              "Recursive delete — verify path before proceeding"),
    ("DELETE FROM",         "SQL delete — ensure WHERE clause is present"),
    ("git stash drop",      "Permanently discards stashed changes"),
    ("docker volume rm",    "Removes a Docker volume — data may be lost"),
    ("truncate",            "Truncates file content — verify target path"),
    ("pkill",               "Kills processes — verify target process name"),
    # ── Repo-specific warnings ──────────
    # Alembic and /admin/purge warnings lived here until 2026-08-21. Neither
    # could fire in this repo: ADR-002 rejects Alembic (migrations are plain
    # .sql files) and there is no purge endpoint. A guard that cannot fire is
    # not neutral — it is read as coverage that does not exist.
    ("make migrate",     "Applies EVERY migrations/*.sql against the live database. A migration ahead of its deployed code has already broken collection here "
                          "(class `migration-ahead-of-its-code`, 2026-08-20) — deploy the code first"),
    ("init_db.sql",       "init_db.sql is the fresh-install schema — piping it at a populated database is not idempotent"),
    ("--build",           "Rebuilds the image. Dockerfiles COPY src/ at build time, so a pull without it leaves stale code running (prod incident 2026-06-14)"),
]


# ── Le geste qui efface du travail sans le nommer ─────────────────────────────
#
# `git checkout -- .` et `git restore .` sont bloqués plus haut. La forme qui coûte
# vraiment n'est pas celle-là : c'est **`git checkout -- <un fichier>`**, qui a l'air
# chirurgical. Mesuré DEUX fois dans la séance du 2026-09-10, sur le même geste — défaire
# une mutation de test. La première fois il a détruit un correctif et deux clés i18n ; la
# seconde, la conversion de deux figures et l'élargissement d'un cliquet. Entre les deux
# j'avais ÉCRIT la leçon en mémoire, ce qui n'a rien empêché : une leçon en prose ne
# retient pas un geste réflexe.
#
# Un blocage sec serait faux. Sur un fichier non modifié ce geste est un no-op légitime,
# et c'est l'usage courant. Le garde interroge donc l'état RÉEL du dépôt et ne bloque que
# s'il y a quelque chose à perdre — en nommant quoi. C'est la différence entre un garde
# qu'on contourne et un garde qui apprend quelque chose.
#
# `git stash` fait le même travail sans rien jeter : c'est ce que le message propose.

# ⚠️ **`--` EST OPTIONNEL, et l'exiger a coûté un fichier le 2026-09-18.** Le motif
# d'origine demandait `checkout … -- <chemins>`. La forme que les mains écrivent
# réellement est `git checkout <fichier>`, sans séparateur — c'est celle qui a effacé
# `tests/test_dag_fleet_isolation.py` ce soir-là, en plein milieu d'une séance, après
# une mutation. Sondé ensuite, six orthographes :
#
#     git checkout <fichier>            NON VU  ← le geste qui a détruit le travail
#     git checkout HEAD <fichier>       NON VU
#     git checkout -- <fichier>         vu
#     git restore <fichier>             vu
#     git checkout main                 non vu  (et c'est correct)
#     git checkout -b <branche>         non vu  (et c'est correct)
#
# C'est la TROISIÈME orthographe du même geste, et `test_git_restore_is_the_same_gesture`
# existait déjà avec pour docstring « deux orthographes, un seul effet — en garder une
# seule serait la portée du défaut ». Le garde avait donc nommé sa propre classe et s'y
# est fait prendre : un garde écrit sur la FORME (`--`) et non sur la PROPRIÉTÉ (un
# rétablissement git visant un chemin qui porte du travail non commité).
#
# Rendre `--` optionnel ne crée pas de faux positif, parce que le verdict ne vient PAS
# du motif : `_paths_that_would_lose_work` écarte les drapeaux, puis interroge
# `git status --porcelain -- <chemin>`. `git checkout main` produit donc un chemin qui
# n'existe pas, aucune perte, aucun blocage. Un changement de branche ne devient bloqué
# que s'il existe un fichier SALE portant le nom de la branche — cas où git lui-même
# exige `--` pour lever l'ambiguïté.
def _paths_that_would_lose_work(command: str) -> list[str]:
    """Les chemins visés par un rétablissement git qui portent du travail non commité.

    Rend une liste vide dès que la question ne se pose pas : pas de rétablissement, pas
    de dépôt git, chemin propre. Ne lève JAMAIS — ce hook s'exécute avant chaque appel
    Bash, et une exception ici bloquerait tout le travail au lieu d'un seul geste.

    LE GESTE DOIT ÊTRE LA COMMANDE, pas une mention dans une phrase : le 2026-09-12, trois
    commandes bloquées d'affilée parce que le TEXTE contenait le geste, et les jetons de la
    phrase devenaient des chemins passés à `git status` — dont `:`, qui en pathspec désigne
    TOUS les fichiers. C'est `_commands` qui le garantit désormais (2026-10-18) : un heredoc
    ou un message multiligne n'est plus une commande, et `git -C d checkout -- f`,
    `sudo git restore f` ou `sh -c "git checkout f"` en sont une.
    """
    try:
        losses: list[str] = []
        for argv in _commands(command):
            g = _git(argv)
            if not g or g[0] not in ("checkout", "restore"):
                continue
            sub, args, cdirs = g
            if sub == "restore":
                touches, paths = _restore_parse(args)
                if not touches:
                    continue        # `--staged` seul ne touche pas l'arbre de travail
            else:
                paths = _checkout_paths(args)
            base = ["git"] + [x for d in cdirs for x in ("-C", d)]
            for path in (p for p in paths if not p.startswith("-")):
                out = subprocess.run(
                    base + ["status", "--porcelain", "--", path],
                    capture_output=True, text=True, timeout=10)
                if out.returncode != 0:
                    continue
                for line in out.stdout.splitlines():
                    if line.startswith("??"):
                        continue  # non suivi : ce geste ne le touche pas
                    # Colonne 2 = arbre de travail. C'est elle qui serait écrasée.
                    if len(line) > 3 and line[1] in "MD":
                        losses.append(line[3:].strip())
        return sorted(set(losses))
    except Exception:  # noqa: BLE001 — un garde qui lève bloquerait chaque commande
        return []


# ── `git clean`, le frère que le garde du rétablissement ne voyait pas ────────
#
# Mesuré le 2026-09-18 en balayant la FAMILLE du geste plutôt que son verbe : sur neuf
# façons d'écraser du travail non commité, cinq étaient bloquées et quatre passaient.
# `git clean -fd` est celle qui appartient sans discussion à la classe — elle supprime
# les fichiers NON SUIVIS, qui ne sont ni dans un commit, ni dans un stash, ni dans le
# reflog. Un test qu'on vient d'écrire et pas encore ajouté est exactement cela.
#
# ⚠️ Le garde du rétablissement ne pouvait pas l'attraper : il ignore délibérément les
# lignes `??` de `git status`, parce qu'un `checkout -- <fichier>` ne touche pas un
# fichier non suivi. `clean` ne touche QUE ceux-là. Deux gestes, une cause, des
# prédicats exactement complémentaires.
def _untracked_that_clean_would_delete(command: str) -> list[str]:
    """Les fichiers non suivis qu'un `git clean` de cette commande supprimerait.

    Vide dès que la question ne se pose pas : pas de `clean`, pas de `-f` (git refuse
    alors tout seul), `--dry-run`/`-n` (il ne supprime rien, même DANS un groupe :
    `git clean -fdn` répond « Would remove »), rien de non suivi. Lu par `_commands` et
    `_clean_forced`, `-C` compris. Ne lève JAMAIS, pour la même raison que son voisin.
    """
    try:
        for argv in _commands(command):
            g = _git(argv)
            if not g or g[0] != "clean" or not _clean_forced(g[1]):
                continue
            base = ["git"] + [x for d in g[2] for x in ("-C", d)]
            out = subprocess.run(base + ["status", "--porcelain"],
                                 capture_output=True, text=True, timeout=10)
            if out.returncode != 0:
                continue
            return sorted({ligne[3:].strip() for ligne in out.stdout.splitlines()
                           if ligne.startswith("??")})
        return []
    except Exception:  # noqa: BLE001 — un garde qui lève bloquerait chaque commande
        return []


# ── Le geste qui se tue lui-même, et emporte la suite de la ligne ─────────────
#
# `pkill -f "<motif>"` compare le motif à la ligne de commande de CHAQUE processus —
# y compris celle du shell qui l'exécute, puisqu'elle CONTIENT le motif. Le shell se
# suicide donc systématiquement, sort en 144, et **tout ce qui suit sur la ligne ne
# part jamais**.
#
# Mesuré TROIS fois dans la séance du 2026-09-12, à chaque fois avec le même dégât :
# la commande d'après — celle qui relançait la suite, celle qui écrivait le script,
# celle qui listait ce qui restait — n'a pas tourné, et le shell a rendu un code
# d'erreur qui ressemblait à un échec de la cible. Deux fois j'ai cru que le kill
# avait raté ; il avait réussi, c'est moi qui étais mort.
#
# Le garde ne bloque PAS un `pkill -f` seul en fin de ligne : là, se tuer après avoir
# tué est sans conséquence. Il bloque quand quelque chose suit, parce que c'est
# exactement le cas où le silence coûte.
#
# La forme sûre ne passe pas par un motif qui se contient lui-même :
#     ps -eo pid,cmd | grep "[p]ytest tests/" | awk '{print $1}' \
#       | while read p; do kill "$p"; done
# Le crochet `[p]` fait que la ligne du shell ne correspond plus au motif cherché.


# ── La SONDE en lecture, ajoutee le 2026-09-16 ───────────────────────────────
#
# Le garde du dessous ne connaissait que `pkill`. La CAUSE n'est pourtant pas le verbe :
# c'est qu'un motif passe a un outil qui compare des lignes de commande se trouve
# LUI-MEME, parce que la ligne du shell qui le porte le contient par construction.
# `pgrep -f` a exactement la meme cause, et j'ai reproduit la classe TROIS FOIS le
# 2026-09-16 — sur une classe que ce depot avait deja ecrite le 2026-09-12, avec son
# hook. La portee du garde etait le defaut, pas la connaissance.
#
# La consequence differe et c'est ce qui l'a rendue invisible : `pkill` tue le shell
# (code 144, bruyant) ; `pgrep` dans un `until` rend toujours VRAI, donc la boucle ne
# sort jamais. Silencieuse, elle passe pour une attente normale — trois ont tourne des
# heures en surveillant des suites deja finies, et m'ont fait conclure quatre fois
# qu'une suite etait morte alors qu'elle tournait.
# Les options de pgrep/pkill qui prennent une valeur SÉPARÉE (procps-ng).
_PGREP_VALUED = frozenset({"-u", "-U", "-g", "-G", "-P", "-s", "-t", "-F", "--euid", "--uid",
                           "--pgroup", "--group", "--parent", "--session", "--terminal",
                           "--pidfile", "--ns", "--nslist", "--signal", "-d", "--delimiter",
                           "--cgroup", "--env", "--older", "--newer", "-O", "-q", "--queue"})


def _full_pattern(argv: list[str]) -> str | None:
    """Le motif d'un `pgrep`/`pkill` QUI COMPARE LA LIGNE ENTIÈRE (`-f`, `--full`), ou None.

    Lu sur l'argv : `-f` dans n'importe quel groupe court (`-af`, `-fl`), `--full`, les
    options à valeur consommées, un signal (`-9`, `-KILL`) sauté — le motif est le premier
    positionnel."""
    full, i = False, 1
    while i < len(argv):
        a = argv[i]
        if a == "--":
            i += 1
            break
        if not a.startswith("-") or a == "-":
            break
        if a == "--full":
            full = True
        elif a in _PGREP_VALUED:
            i += 1
        elif not a.startswith("--") and not a[1:].isdigit() and not a[1:].isupper():
            if "f" in a[1:]:
                full = True
        i += 1
    if not full or i >= len(argv):
        return None
    return argv[i]


def _probe_would_find_its_own_shell(command: str) -> str | None:
    """Le motif d'un `pgrep -f` qui se contient lui-meme, ou None.

    Meme cause que `_pkill_would_kill_its_own_shell`, autre consequence : ici rien ne
    meurt, la boucle ne sort simplement jamais. C'est PIRE a diagnostiquer, parce qu'une
    attente qui dure ressemble a une attente normale.

    Un motif deja crante (`"[p]ytest"`) est la forme sure : verifie par execution le
    2026-09-16, `grep -c "[x]marker"` rend 0 alors que sa propre ligne porte le motif
    entre crochets.
    """
    # 2026-10-19 (T125) : lu sur les argv de `_commands`, plus sur `re.split(r"&&|\|\||;|\n")`
    # — un `;` CITÉ (`echo "x; pgrep -f foo"`) devenait un séparateur, et la phrase un geste.
    try:
        for argv in _commands(command):
            if not argv or argv[0] != "pgrep":
                continue
            pattern = _full_pattern(argv)
            if pattern is None:
                continue
            if "[" in pattern:
                # Crante : sur que si le texte n'apparait pas AILLEURS en clair sur la
                # ligne. Le 2026-09-22, `(pgrep -f "[s]treamlit run" && echo deja) ||
                # (nohup … streamlit run …)` a conclu « deja lance » sur sa propre
                # relance. Meme evaluation que `_grep_pattern_matches_its_own_line`.
                full = _sans_heredocs(command)
                at = full.find(pattern)
                rest = full[:at] + full[at + len(pattern):] if at >= 0 else full
                try:
                    if not re.search(pattern, rest):
                        continue
                except re.error:
                    continue
            return pattern
    except Exception:  # noqa: BLE001 — un garde qui leve bloquerait chaque commande
        return None
    return None


def _pkill_would_kill_its_own_shell(command: str) -> str | None:
    """Le motif d'un `pkill -f` suivi d'autre chose sur la même ligne, ou `None`.

    Ne lève jamais : ce hook précède chaque appel Bash, et une exception y bloquerait
    tout le travail au lieu d'un seul geste.
    """
    try:
        # ⚠️ `_sans_heredocs` MANQUAIT ICI, et seulement ici : les deux autres
        # détecteurs l'appliquaient déjà. Mesuré le 2026-09-16 — ce garde a bloqué la
        # commande qui ÉCRIVAIT la portée de sa propre classe, la prose citant `pkill -f`
        # dans un corps de heredoc. CLAUDE.md décrit exactement ce cas (« écrire SUR un
        # défaut déclenche le garde du défaut », trois commandes bloquées le
        # 2026-09-12) et le correctif n'avait été appliqué qu'à DEUX des trois lecteurs.
        # Un correctif qui ne balaie pas laisse la classe vivante à côté.
        for argv in _commands(command):
            # LE GESTE DOIT ÊTRE LA COMMANDE, pas un mot dans un argument.
            #
            # Sans ce filtre, le garde bloque toute MENTION du geste — le test qui
            # le vérifie, la documentation qui l'explique, l'édition du hook
            # lui-même. Il s'est bloqué ainsi à sa première utilisation, le
            # 2026-09-12, trois commandes d'affilée, et le correctif n'a pas pu
            # être écrit tant que la cause n'était pas comprise. C'est
            # `a-textual-guard-is-blind`, commis en écrivant le garde d'à côté.
            #
            # 2026-10-19 (T125) : c'est l'argv NORMALISÉ qui le garantit — `sudo`, `timeout 5`,
            # `sh -c` sautés ; et un `;` cité dans un message de commit n'est plus un
            # séparateur (l'ancien `re.split(r"&&|\|\||;|\n")` en faisait un).
            if not argv or argv[0] != "pkill":
                continue
            # Rien après ? Se tuer en dernier ne coûte rien.
            if not argv.follows:
                continue
            pattern = _full_pattern(argv)
            if pattern is None:
                continue
            # Un motif qui ne peut pas se contenir lui-même (crochet à la grep) est
            # déjà la forme sûre — on ne crie pas dessus.
            if "[" in pattern:
                continue
            return pattern
    except Exception:  # noqa: BLE001 — un garde qui lève bloquerait chaque commande
        return None
    return None


# ── Le crochet ne suffit pas, ajoute le 2026-09-24 ───────────────────────────
#
# La forme sure que ce hook RECOMMANDE — `ps … | grep "[s]treamlit run app.py"` — m'a
# tue le shell le 2026-09-24, exit 144, sur cette ligne :
#
#     pid=$(ps -eo pid,args | grep "[s]treamlit run src/dashboard/app.py" | awk …);
#     kill $pid; sleep 2; nohup .venv/bin/streamlit run src/dashboard/app.py … &
#
# Le crochet empeche le motif de se trouver dans SA PROPRE ecriture. Il n'empeche pas
# qu'il se trouve AILLEURS sur la ligne : la relance portait le texte en clair, donc la
# ligne du shell correspondait, `kill` l'a tue, et la relance n'est jamais partie.
# La propriete n'est pas « le motif porte un crochet » : c'est « le motif correspond a
# la ligne de commande qui l'execute ». On l'evalue donc comme grep le ferait : sur la
# ligne entiere, privee de la seule ecriture du motif.


_GREP_VALUED = frozenset({"-e", "-f", "-m", "-A", "-B", "-C", "-d", "-D", "--regexp", "--file",
                          "--max-count", "--after-context", "--before-context", "--context",
                          "--label", "--include", "--exclude", "--exclude-dir", "--color",
                          "--colour", "--devices", "--directories", "--binary-files"})


def _a_kill_follows(units: list[list[str]]) -> bool:
    """Une commande `kill`/`pkill` (`… | xargs kill` compris) que quelque chose SUIT."""
    return any(u and u[0] in ("kill", "pkill") and getattr(u, "follows", False) for u in units)


def _grep_pattern(argv: list[str]) -> str | None:
    """Le motif d'un `grep` : `-e MOTIF`, `--regexp=MOTIF`, ou le premier positionnel."""
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--":
            return argv[i + 1] if i + 1 < len(argv) else None
        if a in ("-e", "--regexp"):
            return argv[i + 1] if i + 1 < len(argv) else None
        if a.startswith("--regexp="):
            return a.split("=", 1)[1]
        if not a.startswith("-") or a == "-":
            return a
        if a.startswith("-e") and not a.startswith("--"):
            return a[2:]
        i += 2 if a in _GREP_VALUED else 1
    return None


def _grep_pattern_matches_its_own_line(command: str) -> str | None:
    """Le motif d'un `grep` qui trouvera la ligne du shell, sur une ligne qui tue
    puis continue — ou None. Ne leve jamais.

    2026-10-19 (T125) : lu sur les argv de `_commands` — l'étage qui NOURRIT le grep
    (`upstream`) est `ps`, une commande `kill` est SUIVIE. L'ancien découpage
    `re.split(r"&&|\\|\\||;|\\n")` prenait un `;` cité pour un séparateur."""
    try:
        units = _commands(command)
        if not _a_kill_follows(units):
            return None
        text = _sans_heredocs(command)
        for u in units:
            # Le danger n'existe que si grep lit la LISTE DES PROCESSUS : un grep sur
            # un fichier de log ne verra jamais la ligne du shell (faux positif mesure
            # le 2026-09-24 par le balayage de cette classe).
            if not u or u[0] not in ("grep", "egrep", "fgrep"):
                continue
            up = u.upstream
            if not up or up[0] != "ps":
                continue
            if any(a == "--invert-match" or (a[:1] == "-" and a[1:2] != "-" and "v" in a[1:])
                   for a in u[1:] if a.startswith("-") and a not in ("-e", "--")):
                continue                      # `grep -v grep` ÉCARTE sa ligne (rejeu T125)
            pattern = _grep_pattern(u)
            if not pattern:
                continue
            at = text.find(pattern)
            rest = text[:at] + text[at + len(pattern):] if at >= 0 else text
            try:
                if re.search(pattern, rest):
                    return pattern
            except re.error:
                continue
    except Exception:  # noqa: BLE001 — un garde qui leve bloquerait chaque commande
        return None
    return None


# ── Detection ─────────────────────────────────────────────────────────────────

# ── Un verdict avale par un tube, puis commite quand meme ────────────────────
#
# Mesure le 2026-09-17, sur cette ligne exacte :
#
#     pytest … -q 2>&1 | tail -3 && git add -A && git commit … && git push
#
# La suite etait ROUGE. `tail` a rendu 0, donc le `&&` a laisse passer, et le rouge
# est parti sur `main`. Le texte de l'echec etait a l'ecran, sous mes yeux, dans la
# sortie de la meme commande — ce n'est pas une erreur de lecture, c'est le shell qui
# a decide a ma place : **un tube rend le code du DERNIER etage**, jamais celui de
# l'etage qui portait le verdict.
#
# Pourquoi un garde et pas une note : c'est un idiome de frappe, pas un raisonnement.
# Il se retape par reflexe a chaque fois qu'on veut abreger une sortie longue, et ce
# depot a mesure trois fois qu'une note ne retient pas un reflexe.
# La TETE d'un etage, comparee a un ensemble : `python` et `python3` couvrent
# `python -m pytest`, dont la tete n'est pas `pytest`.
_VERIFIERS = frozenset({"pytest", "ruff", "mypy", "make", "python", "python3",
                       "audit_runner.py", "validate_rex.py"})


def _verdict_swallowed_by_a_pipe(command: str) -> str | None:
    """Un verdict tube dans un filtre, PUIS une livraison dans la meme chaine `&&`.

    Rend le segment de verification fautif, ou None.

    Ce qu'il ne bloque PAS, et c'est ce qui le rend tenable :
      * un verdict tube SANS livraison derriere — la forme de lecture normale ;
      * une livraison SANS verdict devant — un commit ordinaire ;
      * `set -o pipefail` ou `${PIPESTATUS`, qui reparent le code de sortie ;
      * un `;` a la place du `&&` : la livraison ne PRETEND alors rien du verdict.
    """
    texte = _sans_heredocs(command)
    if "pipefail" in texte or "PIPESTATUS" in texte:
        return None
    # ⚠️ **On decoupe des JETONS, jamais du texte.** La premiere version de ce garde
    # coupait la chaine sur `|` et `&&` avec une expression reguliere : elle s'est
    # bloquee elle-meme sur `echo "pytest | tail && git commit est un piege"`, ou les
    # trois marques vivent DANS un argument. C'est la classe deja nommee de ce depot,
    # `a-bash-hook-that-blocks-the-prose-about-the-gesture`, attrapee ici par son propre
    # cas de test. `shlex` garde une chaine citee en UN jeton, donc un operateur n'est
    # un operateur que s'il en est un.
    #
    # ⚠️ Et `shlex.split` NE SUFFIT PAS : il coupe sur les blancs, donc
    # `make test|tail -3&&git commit` lui rend `['make','test|tail','-3&&git',…]` et le
    # garde ne voyait AUCUN operateur — il passait au vert sur la forme sans espaces.
    # Trouve le 2026-09-17 en mutant : deux mutations sur trois sont d'abord passees
    # VERTES, et c'est ce vert-la qui a revele le trou. `punctuation_chars=True` fait de
    # `|`, `&&` et `;` des jetons a part entiere, sans toucher a ce qui est cite.
    try:
        analyseur = shlex.shlex(texte, posix=True, punctuation_chars=True)
        analyseur.whitespace_split = True
        jetons = list(analyseur)
    except ValueError:
        return None
    etapes: list[list[str]] = [[]]
    ops: list[str] = []
    for jeton in jetons:
        if jeton in ("|", "&&", "||", ";", "&", "|&"):
            ops.append(jeton)
            etapes.append([])
        else:
            etapes[-1].append(jeton)
    if "&&" not in ops:
        return None

    def _tete(argv: list[str]) -> str:
        i = 0
        while i < len(argv) and (argv[i].lower() in _PREFIXES_A_SAUTER or "=" in argv[i]):
            i += 1
        return argv[i].rsplit("/", 1)[-1].lower() if i < len(argv) else ""

    for i, argv in enumerate(etapes):
        if not argv or i >= len(ops) or ops[i] != "|":
            continue
        # L'etage qui porte le VERDICT est celui a GAUCHE du tube ; les suivants ne font
        # que filtrer. Un `| tee` conserve la sortie mais rend quand meme le code de
        # `tee` : aucun filtre n'est exempte, volontairement.
        if _tete(argv) not in _VERIFIERS:
            continue
        # Une LIVRAISON apres le tube, atteinte par un `&&` — donc qui PRETEND dependre
        # du verdict. Apres un `;` elle ne pretend rien, et n'est pas bloquee.
        #
        # ⚠️ On TRAVERSE les etages de filtrage. La premiere version s'arretait au
        # premier `ops[j-1] != "&&"`, donc au tube lui-meme : elle rendait None sur les
        # QUATRE cas qu'elle existe pour attraper. Un garde qui rate la forme reellement
        # tapee ne garde rien — trouve en jouant les cas, pas en relisant.
        vu_et = False
        for j in range(i + 1, len(etapes)):
            lien = ops[j - 1]
            if lien == "|" and not vu_et:
                continue          # encore un filtre du meme tube
            if lien != "&&":
                break             # `;` ou `||` : la livraison ne pretend plus rien
            vu_et = True
            tete = _tete(etapes[j])
            reste = etapes[j][1:] if etapes[j] else []
            if tete == "git" and reste and reste[0] in ("commit", "push", "tag"):
                return " ".join(argv)
            if tete == "gh" and reste[:2] in (["pr", "create"], ["release", "create"]):
                return " ".join(argv)
    return None


# ── Un commit refuse, puis un second commit qui emporte son index ─────────────
#
# Mesure le 2026-10-07 (R452), sur cette ligne exacte :
#
#     git commit -qm "R448 …" 2>&1 | grep -E "Failed|❌"; git add … && git commit -qm "R449 …"
#
# Le hook des durees a REFUSE le premier commit. Un refus pre-commit garde l'index
# intact ; le `;` a laisse partir le second, qui a emporte les fichiers de R448 sous le
# nom R449. Rien n'a ete perdu en apparence, et c'est le piege : le travail est livre,
# sous le mauvais numero, et la trace de roadmap ment. R450 attrape la consequence quand
# les fichiers sortent du perimetre declare — pas quand les deux lignes le partagent.
#
# La propriete, pas la forme : le second commit doit etre atteint par une chaine de `&&`
# DEPUIS le premier. Tout autre lien (`|`, `;`, `||`, un saut de ligne) le laisse partir
# quel que soit le verdict du premier.
def _git_subcommand(argv: list[str]) -> str:
    """`commit` pour `git commit`, `git -C d commit`, `rtk git commit`… ; '' sinon."""
    for n in _normalise(argv):
        g = _git(n)
        if g:
            return g[0]
    return ""


def _commit_riding_a_refused_one(command: str) -> str | None:
    """Deux `git commit` dans une commande, le second pas garde par `&&` depuis le
    premier. Rend le premier commit fautif, ou None."""
    try:
        cmds = _simple_commands(command)
    except Exception:  # noqa: BLE001
        return None
    # `--dry-run` n'ecrit rien : une sonde ne laisse pas d'index a emporter.
    commits = [k for k, (argv, _) in enumerate(cmds)
               if any((g := _git(n)) and g[0] == "commit" and "--dry-run" not in g[1]
                      for n in _normalise(argv))]
    for a, b in zip(commits, commits[1:]):
        if any(cmds[k][1] != "&&" for k in range(a + 1, b + 1)):
            return " ".join(cmds[a][0])
    return None


_UV_RUN_VALUED = frozenset({"--with", "--with-editable", "--with-requirements", "--python", "-p",
                            "--project", "--directory", "--extra", "--group", "--only-group",
                            "--no-group", "--env-file", "--index", "--index-url",
                            "--extra-index-url", "--package", "--find-links", "-f",
                            "--config-file", "--cache-dir"})


def _sans_runner(argv: list[str]) -> list[str]:
    """`uv run [opts] X`, `poetry run X`, `pipenv run X` -> l'argv normalisé de X."""
    while argv:
        if argv[0] == "uv" and argv[1:2] == ["run"]:
            i = 2
            while i < len(argv) and argv[i].startswith("-"):
                if argv[i] == "--":
                    i += 1
                    break
                i += 2 if argv[i] in _UV_RUN_VALUED else 1
            argv = argv[i:]
        elif argv[0] in ("poetry", "pipenv", "pdm", "hatch", "rye") and argv[1:2] == ["run"]:
            argv = argv[2:]
        else:
            break
        argv = (_normalise(argv) or [[]])[0]
    return argv


def _serial_full_suite(command: str) -> str | None:
    """Une suite COMPLÈTE lancée sans parallélisme. Rend le segment fautif, ou None.

    Ce n'est pas un geste destructeur — c'est un geste qui coûte QUINZE MINUTES, et que
    rien n'empêchait. Mesuré le 2026-09-16 : `pytest tests/ -q` en série rend 888, 921 et
    963 s sur ce poste ; `make test` pose `-n auto --dist loadgroup`. La forme nue a été
    lancée SIX FOIS dans une seule séance, parce que `CLAUDE.md` la documentait ainsi.

    Pourquoi un hook et pas la doc corrigée : la doc EST corrigée, et ce dépôt a mesuré
    trois fois qu'une note ne retient pas un geste réflexe — `checkout` deux fois le
    2026-09-10, `kill` trois fois le 2026-09-12, et l'édition-pendant-la-suite trois fois
    le 2026-09-16, la leçon étant écrite entre chaque.

    Ce qu'elle NE bloque PAS, et c'est ce qui la rend tenable :
      * un fichier ou une liste de fichiers (`pytest tests/test_x.py`) — le geste courant ;
      * tout ce qui porte déjà `-n` ;
      * `--store-durations`, qui doit tourner en SÉRIE à dessein (`make test-durations`).
    """
    # ⚠️ `timeout` et `nice` PRENNENT UN ARGUMENT : `timeout 1700 … pytest tests/` a
    # échappé au garde le 2026-09-16, six fois. C'est désormais `_commands` qui saute les
    # enveloppes avec leurs options, pour tous les gardes à la fois ; ici restent les
    # LANCEURS de projet (`uv run [opts]`, `poetry run`, `pipenv run`), qui n'enveloppent
    # que pytest et qu'aucun autre garde n'a à connaître.
    for argv in _commands(command):
        argv = _sans_runner(argv)
        if not argv:
            continue
        head = argv[0].lower()
        if head in ("pytest", "py.test") or head.endswith("pytest"):
            k = 0
        elif "python" in head or head.endswith(".exe"):
            # ⚠️ `rest` commence APRES le jeton `pytest`, jamais apres argv[0]. Sinon le
            # `-m` de `python -m pytest` est pris pour le `-m` de pytest (un filtre par
            # MARQUEUR) et toute la suite s'exempte elle-meme.
            k = next((j for j in range(1, min(len(argv), 5))
                      if argv[j] in ("pytest", "py.test")), 0)
            if not k:
                continue
        else:
            continue
        rest = argv[k + 1:]
        # L'ARBRE ENTIER, pas un fichier : l'argument est `tests` ou `tests/` tel quel.
        whole_tree = any(a.rstrip("/") == "tests" for a in rest if not a.startswith("-"))
        if not whole_tree:
            continue
        if any(a == "-n" or a.startswith("-n") or a.startswith("--numprocesses")
               for a in rest):
            continue
        # `--store-durations` doit tourner en SERIE a dessein (`make test-durations`).
        # `--collect-only` ne lance aucun test : quelques secondes, et c'est le geste
        # normal pour compter ou lister. Exempte apres que ce garde m'a bloque dessus —
        # un garde qui attrape un geste bon marche apprend a etre contourne.
        if "--store-durations" in rest or "--collect-only" in rest or "--co" in rest:
            continue
        # ⚠️ Une execution FILTREE n'est pas la suite complete. Ce garde m'a bloque le
        # 2026-09-16 sur `pytest tests/ -k "error_class or roadmap"` — une trentaine de
        # fichiers, pas 6 700 tests. C'est un defaut de PORTEE dans le garde lui-meme,
        # de la meme famille que celui qu'il documente : j'avais ecrit la regle sur la
        # CIBLE (`tests/`) au lieu de l'ecrire sur le GESTE (« lancer toute la suite »).
        # Trouve par le garde en me bloquant, ce qui est le seul moment ou ca ne coute
        # rien.
        if any(a in ("-k", "-m", "--lf", "--last-failed", "--ff", "--failed-first",
                     "--deselect") or a.startswith(("-k=", "-m=", "--deselect="))
               for a in rest):
            continue
        return " ".join(argv)
    return None


# ── The repo's own values: `guard_local.json`, next to this file (T150a, 2026-10-19) ──
#
# A repo that wrote ITS production host or ITS extra rule into this file forked all of it:
# the copy no longer matched a shipped version, `sync_payload` read it ✎ « local adaptation »,
# and no channel ever brought it the T125 shell reader (6 repos, measured 2026-10-19: prose in a
# commit message blocked, `rm -f ~/.cache/x.json` blocked, `echo ~ | xargs rm -rf` passed).
# The values live in data now, and the code stays the payload's bytes. The file may only ADD
# blocks: `prod_hosts` (list of hosts) and `block_patterns` (list of [regex, reason], matched on
# each EXECUTED command, never on the raw text). An exemption is code, reviewed in the master.
# It is never data a repo can write. The path comes from this file, never from cwd. If the file
# is absent, nothing is added. If it is malformed, one line goes to stderr and the defaults apply:
# no crash on every Bash call, no silent relaxation.
_LOCAL_FILE = _Path(__file__).resolve().parent / "guard_local.json"
_LOCAL_KEYS = frozenset({"prod_hosts", "block_patterns"})


def _load_local(path: _Path = _LOCAL_FILE) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """`(prod_hosts, block_patterns)` from the repo's guard_local.json. Absent → empty."""
    if not path.is_file():
        return (), ()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("top level is not an object")
        hosts = data.get("prod_hosts", [])
        pats = data.get("block_patterns", [])
        if not (isinstance(hosts, list) and all(isinstance(h, str) and h for h in hosts)):
            raise ValueError("prod_hosts must be a list of non-empty strings")
        if not (isinstance(pats, list) and all(
                isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) for x in p)
                for p in pats)):
            raise ValueError("block_patterns must be a list of [regex, reason]")
        for rx, _msg in pats:
            re.compile(rx)
        unknown = sorted(set(data) - _LOCAL_KEYS - {"_comment"})
        if unknown:
            print(f"guard_destructive: {path.name} — keys ignored (this file only adds "
                  f"blocks): {', '.join(unknown)}", file=sys.stderr)
        return tuple(hosts), tuple((rx, msg) for rx, msg in pats)
    except (OSError, ValueError, re.error) as e:
        print(f"guard_destructive: {path.name} unreadable ({e}) — built-in rules only",
              file=sys.stderr)
        return (), ()


# R191 (2026-09-26) — this project's production hosts: `prod_hosts` in guard_local.json
# (IP or domain) refuses `airflow tasks test` over ssh on them. Empty in the payload.
_PROD_HOSTS, _LOCAL_BLOCKS = _load_local()
_TASKS_TEST_RE = re.compile(r"\bairflow\s+tasks\s+test\b")


def _tasks_test_on_prod(command: str) -> str | None:
    """Un `airflow tasks test` lancé en PRODUCTION par ssh. Rend l'hôte visé, ou None.

    Mesuré deux fois le 2026-09-26 (11:27 et 16:58, `alert_monitor`) : sur Airflow 2.11,
    `tasks test` laisse un DagRun `__airflow_temporary_run_…` que le planificateur ADOPTE et
    exécute EN ENTIER — toutes les tâches du DAG, et leurs mails. La seconde fois, juste après
    un redémarrage du planificateur, trois tâches se sont bloquées sur la base d'Airflow et un
    faux « task check_billing_sync FAILED » est parti à la boîte du propriétaire.

    Lu sur la STRUCTURE (les argv de `_analyse`, guillemets respectés) : le geste
    est un jeton `ssh` suivi d'un hôte de prod, et la commande distante contient
    `airflow tasks test`. Une phrase qui en PARLE (`echo "… tasks test …"`) est un seul jeton
    et ne déclenche rien — la leçon de `a-bash-hook-that-blocks-the-prose-about-the-gesture`.
    """
    if not _PROD_HOSTS:
        return None
    # T150b : sur les argv DÉVELOPPÉS de `_analyse` — `H=<prod>; ssh $H airflow tasks test …`
    # passait par le `shlex` d'avant, qui ne voyait que `$H`.
    for argv in _analyse(command).units:
        if not argv or argv[0] != "ssh":
            continue
        j = 1
        while j < len(argv) and argv[j].startswith("-"):
            j += 2 if argv[j] in _SSH_VALUED else 1
        if j >= len(argv):
            continue
        host = argv[j]
        if not any(h in host for h in _PROD_HOSTS):
            continue
        remote = " ".join(argv[j + 1:])
        if _TASKS_TEST_RE.search(remote):
            return host
    return None


# R267 (owner notes L138/L170, critic d) — no gesture of Claude Code READS a `.env`.
# The permission deny in settings covers the Read tool; the shell was open: `cat .env`,
# `grep KEY .env.local`, `source .env` printed or loaded the secrets into a transcript.
# Read on STRUCTURE — the command of a segment is a reader and one of its arguments IS a
# `.env` file — so a commit message or a heredoc that talks about `.env` never trips it.
# `.env.example` and `.env.template` are exempt: committed, public, no value. The template
# name came from n8n (R009, 2026-10-19 into the master): the exemption named only
# `.env.example`, so the one env file n8n commits to be read was refused.
_ENV_TEMPLATES = frozenset({".env.example", ".env.template"})
_ENV_READERS = frozenset({
    "cat", "less", "more", "head", "tail", "grep", "egrep", "fgrep", "rg", "sed", "awk",
    "source", ".", "xxd", "od", "strings", "bat", "cut", "sort", "uniq", "diff", "base64",
    "cp", "tac", "nl", "column", "jq", "envsubst", "dotenv"})
_ENV_FILE = re.compile(r"^\.env(?:\.[\w.-]+)?$")


def _is_env(arg: str) -> str | None:
    name = arg.lstrip("<").rsplit("/", 1)[-1]
    if name.startswith(".en") and any(c in name for c in "*?["):
        return arg.lstrip("<")                 # `cat .env*`, `cat .en?` — a glob that hits it
    return arg.lstrip("<") if _ENV_FILE.match(name) and name not in _ENV_TEMPLATES else None


def _remote_command(argv: list[str]) -> str | None:
    """The command a wrapper runs: `bash -c '…'`, `docker exec <ctr> …`, `ssh <host> …`."""
    if not argv:
        return None
    head = argv[0].rsplit("/", 1)[-1]
    if head in ("bash", "sh", "zsh", "dash") and "-c" in argv:
        k = argv.index("-c")
        return argv[k + 1] if k + 1 < len(argv) else None
    if head == "docker" and len(argv) > 2 and argv[1] in ("exec", "run"):
        j = 2
        while j < len(argv) and argv[j].startswith("-"):
            j += 2 if argv[j] in ("-u", "--user", "-e", "--env", "-w", "--workdir") else 1
        return " ".join(argv[j + 1:]) or None          # argv[j] is the container
    if head == "ssh":
        j = 1
        while j < len(argv) and argv[j].startswith("-"):
            j += 2 if argv[j] in ("-o", "-i", "-p", "-l", "-J", "-F") else 1
        return " ".join(argv[j + 1:]) or None          # argv[j] is the host
    return None


def _reads_an_env_file(command: str) -> str | None:
    """The `.env` file a segment's command would read, or None.

    ⚠️ A SPEED BUMP, not a boundary (security-specialist, R267): `python3 -c
    "open('.env')"`, `git show HEAD:.env`, `vim`, `docker compose config` all read it and
    are not caught — no reading of the command's STRUCTURE can list every program that
    opens a file. It stops the reflexes: a reader, a redirect, a substitution, a wrapper
    (`bash -c`, `docker exec`, `ssh`), `xargs`, a glob.

    Three shapes: a READER given the file (`cat .env`), ANY command fed it by an input
    redirection (`python3 x.py < .env`), and either of those inside a command
    substitution (`echo $(cat .env)`), which is read recursively.
    """
    # 2026-10-19 (T125) : lu sur `_analyse` — guillemets, substitutions, enveloppes
    # (`bash -c`, `docker exec`, `ssh`, `sudo`, `xargs`) et heredocs exécutés compris. Le
    # découpage `re.split(r"(?:&&|\|\||\||;|\n)")` d'avant coupait un `;` cité. La cible
    # d'une redirection `>`/`>>` est ÉCRITE, jamais lue : `cat <<EOF > .env` la crée — elle
    # n'est pas un argument (`_simple_commands` la range dans `redirs`).
    an = _analyse(command)
    for argv in an.raw_cmds:                     # `< .env`, whatever the command
        for op, target in argv.redirs:
            if op == "<" and _is_env(target):
                return _is_env(target)
    raw_words = [w for argv in an.raw_cmds for w in argv]
    for argv in an.units:
        if not argv:
            continue
        inner = _remote_command(argv) if argv[0] == "docker" else None
        if inner and _reads_an_env_file(inner):  # `docker run img cat .env`
            return _reads_an_env_file(inner)
        if argv[0] not in _ENV_READERS:
            continue
        for arg in argv[1:]:
            if _is_env(arg):
                return _is_env(arg)
        # `ls | xargs cat` : l'entrée n'est pas lue — un `.env` nommé sur la ligne suffit.
        if getattr(argv, "stdin", None) == _UNREAD and any(_is_env(w) for w in raw_words):
            return "(par xargs)"
    return None


_COPIERS = frozenset({"cp", "rsync", "mv"})


def _is_a_backup_path(word: str, an: _Analysis) -> bool:
    """A backup folder: a `$VAR` left unresolved, /tmp, or a scratchpad. The argv of `_analyse`
    are already expanded (T150b): `B=/tmp/…/bak; cp $B/*.py x/` reads the /tmp path here."""
    return word.startswith("$") or "/tmp/" in word or "scratchpad" in word


def _glob_restore_into_repo(command: str) -> str | None:
    """A RESTORE by glob from a backup folder into the repo. Returns the command, or None.

    It happened on 2026-10-17 (dofus, R22, into the master on 2026-10-19 by T150a): `cp
    autofight/{a,b,c}.py $B/ … ; cp $B/*.py autofight/` copied back FIVE files, not three. The
    scratchpad folder, shared with the workflow agents, still held a `vision.py` and a
    `__main__.py` from the day before, and six fixes were undone in the working copy without a
    word. A backup is restored by the NAMES that were saved. Not blocked: the backup itself (a
    glob into the scratchpad) and a file-by-file restore.

    Read on the EXECUTED commands (`_analyse`), not by cutting the raw text: a sentence that
    talks about the gesture (`echo 'cp $B/*.py x/'`) is one argument of `echo`, and
    `timeout 5 cp $B/*.py src/` is still a `cp`.
    """
    an = _analyse(command)
    for u in an.units:
        if not u or u[0] not in _COPIERS:
            continue
        words = [a for a in u[1:] if not a.startswith("-")]
        if len(words) < 2:
            continue
        *sources, dest = words
        if _is_a_backup_path(dest, an):
            continue
        if any(_is_a_backup_path(a, an) and any(c in a for c in "*?[") for a in sources):
            return " ".join(u)
    return None


_CWD: str | None = None     # le dossier de la ligne jugée (le `cwd` du hook), pendant `check_command`


def check_command(cmd: str, cwd: str | None = None) -> tuple[str, str] | None:
    """
    Returns (level, message) if the command matches a dangerous pattern.
    level is 'block' or 'warn'. Returns None if safe. `cwd` : where the line runs (the
    scripts it names are read from there).

    FERMÉ en cas de doute (2026-10-19, T125) : si le lecteur du shell lève, la ligne est
    jugée au TEXTE brut par les anciennes règles (`_raw_verdict`) — jamais « rien à voir ».
    """
    global _CWD
    saved, _CWD = _CWD, cwd or _CWD
    try:
        return _check(cmd)
    except Exception:  # noqa: BLE001 — le repli est le jugement d'avant, pas un laissez-passer
        return _raw_verdict(cmd)
    finally:
        _CWD = saved


def _raw_verdict(text: str, warn: bool = True) -> tuple[str, str] | None:
    """Les règles d'AVANT le lecteur, au texte : le tier regex, puis la sous-chaîne
    littérale, puis l'avertissement. Le repli quand la ligne est illisible, et le juge du
    code qu'un interpréteur reçoit (`an.raw`) — un faux positif plutôt qu'un trou."""
    for pattern, message in _BLOCK_REGEX:
        if re.search(pattern, text, re.IGNORECASE):
            return ("block", message)
    low = text.lower()
    for pattern, message in _BLOCK_PATTERNS:
        if pattern.lower().strip() in low:
            return ("block", message)
    if not warn:
        return None
    for pattern, message in _WARN_PATTERNS:
        if pattern.lower() in low:
            return ("warn", message)
    return ("warn", "Ce garde n'a pas su lire cette commande (guillemets ou substitution "
                    "qu'il ne suit pas) : aucune règle ne l'a reconnue AU TEXTE, mais "
                    "rien n'a été vérifié sur sa structure. Relire avant de lancer.")


def _check(cmd: str) -> tuple[str, str] | None:
    an = _analyse(cmd)                       # lève sur une ligne illisible -> `_raw_verdict`
    env_file = _reads_an_env_file(cmd)
    if env_file:
        return ("block",
                f"cette commande LIT `{env_file}` : ses valeurs sont des secrets, et tout ce "
                "qu'une commande affiche entre dans la transcription. Aucun geste de Claude "
                "Code ne lit un `.env` (R267). Pour savoir si une clé est posée sans la "
                "montrer : `grep -c '^CLE=' fichier` n'est pas mieux — demander au "
                "propriétaire de lancer la commande avec `!`, ou tester l'EFFET (le service "
                "démarre, l'appel répond).")
    # Le verdict avale par un tube d'abord : il ne detruit rien et il ne coute pas de
    # temps — il fait LIVRER un rouge en croyant livrer un vert, ce qui est pire.
    avale = _verdict_swallowed_by_a_pipe(cmd)
    if avale:
        return ("block",
                f"`{avale}` est tube dans un filtre, et une LIVRAISON suit dans la meme "
                "chaine `&&`. Un tube rend le code du DERNIER etage : le verdict de "
                "cette verification est jete, et `&&` laissera passer meme si elle est "
                "ROUGE.\n"
                "   Arrive le 2026-09-17 sur ce depot : une suite rouge poussee sur "
                "`main`, le texte de l'echec affiche a l'ecran dans la meme sortie.\n"
                "   Formes sures :\n"
                "     • separer : lancer la verification, LIRE, puis commiter dans un "
                "second appel ;\n"
                "     • ou reparer le code de sortie : set -o pipefail; <cmd> | tail -3\n"
                "     • ou n'affirmer rien : remplacer `&&` par `;` devant la livraison.")
    porteur = _commit_riding_a_refused_one(cmd)
    if porteur:
        return ("block",
                f"`{porteur[:80]}` est suivi d'un SECOND `git commit` qui partira meme s'il "
                "est refuse : un refus pre-commit garde l'index, et le commit suivant "
                "l'emporte sous un autre numero (R448 parti sous R449, 2026-10-07).\n"
                "   Forme sure : un commit par appel, son code de sortie lu —\n"
                "     git commit -q -F - > ~/.cache/commit.log 2>&1 <<'EOF' … EOF\n"
                "     echo rc=$?\n"
                "   puis le commit suivant dans un second appel ; ou les enchainer par `&&`.")

    restaure = _glob_restore_into_repo(cmd)
    if restaure:
        return ("block",
                f"`{restaure[:90]}` restaure une sauvegarde par MOTIF : le dossier peut garder "
                "des fichiers d'avant (le bloc-notes est partagé avec les agents des workflows), "
                "et le motif les recopie aussi. Arrivé le 2026-10-17 : 5 fichiers recopiés au "
                "lieu de 3, six briques défaites en silence (dofus R22).\n"
                "   Forme sûre : restaurer par NOMS, ceux qu'on a sauvés —\n"
                "     cp \"$B/automate.py\" \"$B/decision.py\" autofight/\n"
                "   et sauver dans un dossier neuf : B=$(mktemp -d).")

    prod = _tasks_test_on_prod(cmd)
    if prod:
        return ("block",
                f"`airflow tasks test` en PRODUCTION ({prod}) : sur Airflow 2.11 il laisse un "
                "DagRun temporaire que le planificateur exécute EN ENTIER — toutes les tâches, "
                "et leurs mails. Mesuré deux fois le 2026-09-26 ; la seconde a mailé un faux "
                "« FAILED ».\n"
                "   Forme sûre : appeler la FONCTION de la tâche avec un `ti` minimal qui "
                "affiche ce qu'elle pousse (voir le runbook, R57) :\n"
                "     docker compose exec -T airflow-scheduler python -c \"import sys; "
                "sys.path.insert(0, '/opt/airflow/dags'); import alert_monitor as m; "
                "T = type('T', (), {'xcom_push': lambda self, **k: print(k)}); "
                "m.check_offsite_backup(ti=T())\"\n"
                "   ou déclencher le DAG normalement (`airflow dags trigger`).")

    # La suite en SÉRIE d'abord : elle ne détruit rien, elle vole quinze minutes, et
    # c'est le seul de ces gardes dont la forme sûre est plus COURTE à taper.
    serial = _serial_full_suite(cmd)
    if serial:
        return ("block",
                "cette commande lance la suite COMPLÈTE en SÉRIE — elle perd "
                "`-n auto --dist loadgroup`, que les cibles du Makefile posent. Mesuré "
                "le 2026-09-16 sur ce poste : 888, 921 et 963 s, soit ~15 min.\n"
                "Ce que tu veux est presque toujours l'une de ces trois :\n"
                "  make test-changed   # les tests atteignables depuis le diff — SECONDES\n"
                "  make test-fast      # tout sauf les documents\n"
                "  make test           # la barrière avant de livrer, drapeaux de la CI\n"
                "Un fichier précis n'est PAS bloqué : "
                "`.venv/bin/python -m pytest tests/test_x.py -q`.")

    # Le suicide de shell d'abord : il ne détruit pas de fichier, mais il fait
    # DISPARAÎTRE en silence tout ce qui suit, ce qui est plus dur à voir.
    probing = _probe_would_find_its_own_shell(cmd)
    if probing:
        return ("block",
                f"`pgrep -f {probing}` va se trouver LUI-MEME : la ligne de commande du "
                "shell qui l'execute contient ce motif, par construction.\n"
                "   Dans une boucle d'attente, il rend donc toujours vrai et la boucle "
                "NE SORT JAMAIS — silencieusement. Trois ont tourne des heures le "
                "2026-09-16 en surveillant des suites deja finies, et m'ont fait "
                "conclure QUATRE FOIS qu'une suite etait morte alors qu'elle tournait.\n"
                "   Formes sures :\n"
                "     • attendre une tache de fond : la notification arrive toute seule ;\n"
                f"     • sonder sans se contenir : ps -eo pid,args | grep \"[{probing[:1]}]{probing[1:]}\"\n"
                "     • ou lire l'etat ailleurs : tail -3 .pytest-last.log")

    suicidal = _pkill_would_kill_its_own_shell(cmd)
    if suicidal:
        return ("block",
                f"`pkill -f {suicidal}` va tuer le shell qui l'exécute : sa propre "
                "ligne de commande CONTIENT ce motif. Tout ce qui suit sur cette "
                "ligne ne partira jamais, et le shell sortira en 144 — un code qui "
                "ressemble à un échec de la cible. Arrivé trois fois le 2026-09-12.\n"
                "Forme sûre, où le motif ne se contient plus lui-même :\n"
                f"  ps -eo pid,cmd | grep \"[{suicidal[:1]}]{suicidal[1:]}\" "
                "| awk '{print $1}' | while read p; do kill \"$p\"; done")
    trouve = _grep_pattern_matches_its_own_line(cmd)
    if trouve:
        return ("block",
                f"`grep \"{trouve}\"` trouvera la ligne du shell qui l'execute : ce texte "
                "y figure AILLEURS, en clair — le crochet n'empeche que l'auto-"
                "correspondance de sa propre ecriture. Le `kill` qui suit tuera donc ce "
                "shell (exit 144) et la suite de la ligne ne partira pas. Arrive le "
                "2026-09-24 : une relance de Streamlit ecrite sur la meme ligne.\n"
                "Forme sure : tuer dans un appel, relancer dans le suivant — ou tuer par "
                "PID connu (celui d'une tache de fond).")
    # Puis le garde à ÉTAT. Il ne bloque que si du travail serait réellement perdu,
    # et son message peut NOMMER les fichiers — ce qu'aucun tier littéral ne peut faire.
    lost = _paths_that_would_lose_work(cmd)
    if lost:
        listing = ", ".join(lost[:6]) + (f" (+{len(lost) - 6})" if len(lost) > 6 else "")
        return ("block",
                "cette commande DÉTRUIRAIT du travail non commité : "
                f"{listing}. Ces modifications ne sont dans aucun commit ni aucun stash "
                "— rien ne les rendra. Si le but est de défaire une mutation de test, le "
                "geste sûr est `git stash && git stash drop`, ou commiter d'abord. Deux "
                "correctifs ont été perdus par cette commande le 2026-09-10, à quelques "
                "heures d'intervalle, sur ce même geste.")
    perdus = _untracked_that_clean_would_delete(cmd)
    if perdus:
        listing = ", ".join(perdus[:6]) + (f" (+{len(perdus) - 6})" if len(perdus) > 6 else "")
        return ("block",
                "ce `git clean` SUPPRIMERAIT des fichiers non suivis : "
                f"{listing}. Ils ne sont dans aucun commit, aucun stash, aucun reflog — "
                "rien ne les rendra. Un test ou un script qu'on vient d'écrire et pas "
                "encore `git add` est exactement dans ce cas. Si le but est de voir ce "
                "qui partirait : `git clean -nd`. Si c'est de le garder : `git add -A` "
                "d'abord, ou `git stash -u`.")
    # Regex tier next: it expresses the dangerous shapes the literal tier cannot.
    # 2026-10-19 (T125) : ce n'est plus une regex sur le TEXTE — `echo "rm -rf ~/x" >
    # notes.txt` bloquait et `timeout 5 rm -rf ~/x` passait. Chaque règle est un PRÉDICAT
    # sur les argv exécutés (`_BLOCK_PREDICATES`) ; `_BLOCK_REGEX` reste le juge du texte
    # que ce lecteur ne lit pas (code d'interpréteur, repli).
    for _name, pred, message in _BLOCK_PREDICATES:
        if pred(an):
            return ("block", message)
    # The repo's own blocks (guard_local.json): matched on each EXECUTED command, never on the
    # raw text, the way the predicates above are.
    for rx, message in _LOCAL_BLOCKS:
        if any(re.search(rx, " ".join(u), re.IGNORECASE) for u in an.units if u):
            return ("block", f"{message} (guard_local.json)")
    for text in an.raw:
        verdict = _raw_verdict(text, warn=False)
        if verdict:
            return verdict
    for pattern, message in _BLOCK_PATTERNS:
        if _gesture_fires(cmd, pattern):
            return ("block", message)
    for pattern, message in _WARN_PATTERNS:
        if _gesture_fires(cmd, pattern):
            return ("warn", message)
    for text in an.raw:
        low = text.lower()
        for pattern, message in _WARN_PATTERNS:
            if pattern.lower() in low:
                return ("warn", message)
    if an.gaps:
        return ("warn", an.gaps[0])
    return None


# ── Le tier regex, relu en prédicats sur les argv (2026-10-19, T125) ──────────────
#
# Une règle par geste, sur la COMMANDE qui s'exécute — enveloppes (`sudo`, `timeout`,
# `xargs`, `sh -c`, `find -exec`…) déroulées par `_analyse`, et l'entrée d'un `xargs`
# lue quand elle vient d'un `echo`/`printf`. Mêmes messages que `_BLOCK_REGEX`.
_ROOT_OR_HOME = re.compile(r"^(?:/+\.?\*?|~(?:/.*)?|\$HOME(?:/.*)?|\$\{HOME\}(?:/.*)?)$")
_SYSTEM_PATH = re.compile(r"^/+(?:etc|usr|bin|sbin|lib|lib64|boot|dev|proc|sys|root|home|srv"
                          r"|opt)(?:/|$)")
_VAR_PATH = re.compile(r"^/+var(?:/+(?!tmp(?:/|$)).*)?$")
_DD_SAFE = re.compile(r"^/dev/(?:null|zero|stdout|stderr|fd(?:/.*)?)$")
_CHMOD_WORLD = re.compile(r"^(?:0*777|[ugoa]*[ao][ugoa]*[+=]rwx)(?=,|$)", re.IGNORECASE)
_VAR_ANY = re.compile(r"\$\{(\w+)(?:(:?[-=])([^}]*))?\}|\$(\w+)")


# La racine, la maison, un dossier système de PREMIER niveau — jamais un sous-chemin : c'est
# la frontière de `mv`, de `rsync --delete` et d'une tête non résolue (`${R} -rf /`), où
# `_ROOT_OR_HOME` (qui prend `~/x`) bloquerait le travail ordinaire (`mv ~/a.txt ~/b.txt`).
_ROOT_LEVEL = re.compile(r"^(?:/+[.*]?|~/?\*?|\$HOME/?\*?|\$\{HOME\}/?\*?"
                         r"|/+(?:etc|usr|bin|sbin|lib|lib64|boot|dev|proc|sys|root|home|srv"
                         r"|opt|var)/*\*?|/+home/+[^/\s]+/*\*?)$")


def _root_level(path: str) -> bool:
    if _ROOT_LEVEL.match(path):
        return True
    home = _os.path.expanduser("~").rstrip("/")
    return bool(home) and path.rstrip("/*") == home


def _rm_parse(argv: list[str], an: _Analysis) -> tuple[bool, list[str]]:
    """`(récursif, cibles)` d'un `rm`, drapeaux séparés, groupés et `--` compris."""
    recursive, targets, end = False, [], False
    for a in argv[1:]:
        if end or not a.startswith("-") or a == "-":
            targets.append(a)
            continue
        if a == "--":
            end = True
        elif a == "--recursive":
            recursive = True
        elif not a.startswith("--") and ("r" in a or "R" in a):
            recursive = True
    return recursive, targets


def _units(an: _Analysis, head: str) -> list[_Argv]:
    return [u for u in an.units if u and (u[0] == head or (head == "mkfs" and u[0].startswith("mkfs.")))]


def _p_download(an: _Analysis) -> bool:
    return any(kind == "download" for kind, _ in an.events)


def _p_root_rm(an: _Analysis) -> bool:
    return any(set(u.wrappers) & {"sudo", "doas", "su"} for u in _units(an, "rm"))


def _p_root_or_home(an: _Analysis) -> bool:
    for u in _units(an, "rm"):
        recursive, targets = _rm_parse(u, an)
        if recursive and any(_ROOT_OR_HOME.match(t) for t in targets):
            return True
    return False


def _p_system_path(an: _Analysis) -> bool:
    return any(_SYSTEM_PATH.match(t) for u in _units(an, "rm") for t in _rm_parse(u, an)[1])


def _p_var(an: _Analysis) -> bool:
    return any(_VAR_PATH.match(t) for u in _units(an, "rm") for t in _rm_parse(u, an)[1])


def _p_mkfs(an: _Analysis) -> bool:
    return bool(_units(an, "mkfs"))


def _p_dd(an: _Analysis) -> bool:
    return any(a.startswith("of=/dev/") and not _DD_SAFE.match(a[3:])
               for u in _units(an, "dd") for a in u[1:])


def _p_chmod(an: _Analysis) -> bool:
    for u in _units(an, "chmod"):
        mode = next((a for a in u[1:] if not a.startswith("-")), None)   # 1er non-option
        if mode is not None and _CHMOD_WORLD.match(mode):
            return True
    return False


def _p_fork(an: _Analysis) -> bool:
    return any(kind == "fork" for kind, _ in an.events)


def _mv_sources(argv: list[str]) -> list[str]:
    """Les SOURCES d'un `mv` : tous ses positionnels sauf le dernier, ou tous avec `-t DIR`."""
    pos, end, target_dir = [], False, False
    i = 1
    while i < len(argv):
        a = argv[i]
        if end or not a.startswith("-") or a == "-":
            pos.append(a)
        elif a == "--":
            end = True
        elif a in ("-t", "--target-directory", "-S", "--suffix"):
            target_dir = target_dir or a in ("-t", "--target-directory")
            i += 1
        elif a.startswith(("--target-directory=",)) or (a.startswith("-t") and len(a) > 2):
            target_dir = True
        i += 1
    return pos if target_dir else pos[:-1]


def _p_mv_root(an: _Analysis) -> bool:
    return any(_root_level(src) for u in _units(an, "mv") for src in _mv_sources(u))


# rsync : les options dont la valeur est le mot SUIVANT (rsync(1)).
_RSYNC_VALUED = frozenset({"-e", "--rsh", "--exclude", "--include", "--filter", "-f",
                           "--files-from", "--exclude-from", "--include-from", "-T",
                           "--temp-dir", "--backup-dir", "--suffix", "--log-file",
                           "--password-file", "--link-dest", "--compare-dest", "--copy-dest",
                           "--chmod", "--chown", "--timeout", "--bwlimit", "--port",
                           "--max-size", "--min-size", "--out-format", "--info", "--debug",
                           "--rsync-path", "--partial-dir", "--usermap", "--groupmap",
                           "--max-delete", "--modify-window", "--contimeout", "--sockopts",
                           "--log-file-format", "--checksum-choice", "--compress-choice",
                           "-B", "--block-size", "-@", "--iconv", "--protocol"})


def _rsync_parse(argv: list[str]) -> tuple[list[str], list[str]]:
    """`(options, positionnels)` d'un `rsync`."""
    opts, pos, end = [], [], False
    i = 1
    while i < len(argv):
        a = argv[i]
        if end or not a.startswith("-") or a == "-":
            pos.append(a)
        elif a == "--":
            end = True
        else:
            opts.append(a)
            if a in _RSYNC_VALUED:
                i += 1
        i += 1
    return opts, pos


def _rsync_deletes(opts: list[str]) -> bool:
    return any(o.startswith("--del") for o in opts)


def _p_rsync_root(an: _Analysis) -> bool:
    """`rsync --delete* SRC DEST` avec DEST la racine ou la maison : DEST devient la copie de
    SRC, et un SRC vide efface tout. `--remove-source-files` d'une source de même niveau."""
    for u in _units(an, "rsync"):
        opts, pos = _rsync_parse(u)
        if len(pos) < 2:
            continue
        if _rsync_deletes(opts) and _root_level(pos[-1]):
            return True
        if "--remove-source-files" in opts and any(_root_level(p) for p in pos[:-1]):
            return True
    return False


_UNRESOLVED_HEAD = re.compile(r"\$(?:\{[^}]*\}|[A-Za-z_]\w*|\d)")


def _p_unresolved_head(an: _Analysis) -> bool:
    """`${R} -rf /` : une tête que la ligne n'affecte pas, sur une racine ou la maison — le
    verbe est inconnu, la cible ne l'est pas."""
    return any(u and _UNRESOLVED_HEAD.fullmatch(u[0]) and any(_root_level(a) for a in u[1:])
               for u in an.units)


def _p_xargs_blind(an: _Analysis) -> bool:
    return any(kind == "xargs-blind" for kind, _ in an.events)


# ── Écraser ou effacer une cible : UNE table, trois listes dérivées (T167) ─────────
#
# Le garde ne jugeait une cible détruite qu'à travers `rm` : `shred -u ~/.ssh/id_ed25519`,
# `> ~/.bashrc`, `truncate -s0`, `cp /dev/null`, `ln -sf /dev/null` passaient, et trois
# listes de verbes (`_DESTRUCTIVE`, `_xargs_kills`, les prédicats `rm`) ne s'accordaient pas
# (R73, R76). Chaque verbe qui écrase ou efface une cible a ici SES cibles (vides quand sa
# forme n'écrase rien) et dit s'il tue à l'aveugle derrière `xargs` ; `_DESTRUCTIVE` et
# `_xargs_kills` en sont dérivés.
_DEV_EMPTY = frozenset({"/dev/null", "/dev/zero"})
_SED_EMPTYING = re.compile(r"^\s*(?:[01]?\s*,\s*\$\s*)?d\s*;?\s*$")


def _opts_pos(argv: list[str], valued: frozenset[str]) -> tuple[list[str], list[str]]:
    """`(options, positionnels)` : `valued` prend le mot suivant, `--` clôt les options."""
    opts, pos, end, i = [], [], False, 1
    while i < len(argv):
        a = argv[i]
        if end or not a.startswith("-") or a == "-":
            pos.append(a)
        elif a == "--":
            end = True
        else:
            opts.append(a)
            if a in valued and i + 1 < len(argv):
                opts.append(argv[i + 1])
                i += 1
        i += 1
    return opts, pos


def _has_flag(opts: list[str], letter: str, long: str) -> bool:
    return any(o == long or o.startswith(long + "=")
               or (o.startswith("-") and not o.startswith("--") and letter in o[1:])
               for o in opts)


def _no_target_dir(opts: list[str]) -> bool:
    return not any(o in ("-t", "--target-directory") or o.startswith("--target-directory=")
                   or (o.startswith("-t") and not o.startswith("--")) for o in opts)


_CP_VALUED = frozenset({"-t", "--target-directory", "-S", "--suffix", "-m", "--mode", "-o",
                        "--owner", "-g", "--group"})


def _ow_rm(u: list[str]) -> list[str]:
    return _rm_parse(u, None)[1]


def _ow_pos(valued: frozenset[str]):
    return lambda u: _opts_pos(u, valued)[1]


def _ow_dd(u: list[str]) -> list[str]:
    return [a[3:] for a in u[1:] if a.startswith("of=")]


def _ow_from_empty(u: list[str]) -> list[str]:
    """`cp|mv|install /dev/null DEST` : DEST devient vide. Une autre source n'est pas jugée
    (trou déclaré : `cp junk ~/.ssh/id_ed25519`)."""
    opts, pos = _opts_pos(u, _CP_VALUED)
    if len(pos) >= 2 and _no_target_dir(opts) and any(p in _DEV_EMPTY for p in pos[:-1]):
        return [pos[-1]]
    return []


def _ow_ln(u: list[str]) -> list[str]:
    opts, pos = _opts_pos(u, frozenset({"-S", "--suffix", "-t", "--target-directory"}))
    if not _has_flag(opts, "f", "--force") or not _no_target_dir(opts) or not pos:
        return []
    return [pos[-1]] if len(pos) >= 2 else [pos[0].rstrip("/").rsplit("/", 1)[-1]]


def _ow_tee(u: list[str]) -> list[str]:
    opts, pos = _opts_pos(u, frozenset())
    return [] if _has_flag(opts, "a", "--append") else pos


def _ow_sed(u: list[str]) -> list[str]:
    """`sed -i` d'un script qui VIDE le fichier (`d`, `1,$d`) ; tout autre script le modifie."""
    opts, pos = _opts_pos(u, frozenset({"-e", "--expression", "-f", "--file", "-l",
                                        "--line-length"}))
    if not any(o.startswith("--in-place") or (o.startswith("-") and not o.startswith("--")
                                              and "i" in o[1:]) for o in opts):
        return []
    if any(o in ("-f", "--file") or o.startswith("--file=") for o in opts):
        return []
    scripts = [opts[j + 1] for j, o in enumerate(opts[:-1]) if o in ("-e", "--expression")]
    scripts += [o.split("=", 1)[1] for o in opts if o.startswith("--expression=")]
    files = pos
    if not scripts and pos:
        scripts, files = [pos[0]], pos[1:]
    return files if scripts and all(_SED_EMPTYING.match(x) for x in scripts) else []


# verbe -> (ses cibles écrasées ou effacées, tue-t-il À L'AVEUGLE derrière `xargs`)
_OVERWRITERS: dict[str, tuple[object, object]] = {
    "rm": (_ow_rm, lambda u: _rm_parse(u, None)[0]),
    "shred": (_ow_pos(frozenset({"-n", "--iterations", "-s", "--size", "--random-source"})),
              lambda u: True),
    "truncate": (_ow_pos(frozenset({"-s", "--size", "-r", "--reference"})), lambda u: True),
    "dd": (_ow_dd, lambda u: True),
    "cp": (_ow_from_empty, lambda u: False),
    "mv": (_ow_from_empty, lambda u: False),
    "install": (_ow_from_empty, lambda u: False),
    "ln": (_ow_ln, lambda u: False),
    "tee": (_ow_tee, lambda u: False),
    "sed": (_ow_sed, lambda u: False),
}
# Une redirection qui écrase sa cible ; `>>` et `&>>` ajoutent, ils ne détruisent rien.
_OVERWRITE_REDIRS = frozenset({">", ">|", "&>"})


def _overwrites(u: list[str]) -> list[str]:
    """Les cibles que `u` écrase ou efface, selon la table ; [] pour tout autre verbe."""
    entry = _OVERWRITERS.get(u[0]) if u else None
    return list(entry[0](u)) if entry else []


def _redir_targets(c: _Argv) -> list[str]:
    return [t for op, t in c.redirs
            if op in _OVERWRITE_REDIRS or (op == ">&" and not t.isdigit() and t != "-")]


def _abspath(t: str, d: str | None) -> str | None:
    """Le chemin absolu de `t` lancé depuis `d` (`~`, `$HOME`, `..` résolus), ou None quand
    il dépend de ce que la ligne ne dit pas (`~autre`, `$X`, une substitution)."""
    home = _os.path.expanduser("~").rstrip("/") or "/"
    for pre in ("$HOME", "${HOME}", "~"):
        if t == pre or t.startswith(pre + "/"):
            t = home + t[len(pre):]
            break
    if not t or t.startswith("~") or "$" in t or "`" in t:
        return None
    if not t.startswith("/"):
        if not d:
            return None
        t = _os.path.join(d, t)
    star = t.endswith("/*")
    p = _os.path.normpath("/" + t.lstrip("/"))
    return p.rstrip("/") + "/*" if star and not p.endswith("*") else p


def _canon(t: str, d: str | None) -> str | None:
    """`_abspath`, la maison écrite `~` : une seule orthographe à juger."""
    p = _abspath(t, d)
    if p is None:
        return None
    home = _os.path.expanduser("~").rstrip("/")
    if home and (p == home or p.startswith(home + "/")):
        return "~" + p[len(home):]
    return p


_SECRET_DIRS = frozenset({".ssh", ".gnupg", ".aws"})
# Les fichiers à point de la maison que leurs outils réécrivent seuls : des caches.
_DOT_CACHES = frozenset({".lesshst", ".wget-hsts", ".python_history"})
# `/dev/tcp/H/P` et `/dev/udp/H/P` : la socket de bash, `echo > /dev/tcp/127.0.0.1/5433` sonde
# un port (rejeu T167 : 14 des 29 bascules vers « block » de la première version).
_DEV_WRITABLE = re.compile(r"^/dev/(?:null|zero|stdout|stderr|tty|pts(?:/.*)?|fd(?:/.*)?"
                           r"|shm(?:/.*)?|tcp(?:/.*)?|udp(?:/.*)?)$")
_SYSTEM_OVERWRITE = re.compile(r"^/(?:etc|usr|bin|sbin|lib|lib64|boot|dev|proc|sys|root)(?:/|$)")


def _protected(c: str | None, erase: bool = True) -> bool:
    """Une cible CANONIQUE (`_canon`) qu'on n'écrase ni n'efface jamais : la maison, une
    entrée à point de premier niveau (`~/.bashrc`, `~/.claude`), ce qui vit sous `~/.ssh`,
    `~/.gnupg`, `~/.aws`, `~/.config/gh`, un chemin système (hors /home, /opt, /srv), sauf
    les périphériques où l'on écrit (`/dev/null`, `/dev/tty`…).

    `erase=False` (écraser EN PLACE : `>`, `truncate`, `tee`…) : la racine, la maison et un
    dossier de premier niveau sont des DOSSIERS — `> /` échoue (EISDIR), il ne détruit rien —
    et un fichier neuf à la racine (`/.pytest-last.log`) n'écrase rien. Rejeu T167 : `> /` lu
    dans la prose d'un message de commit, `tee ../../x` après un `cd` raté."""
    if c is None:
        return False
    if c in ("~", "~/*"):
        return erase
    if c.startswith("~/"):
        parts = c[2:].split("/")
        if parts[0] in _SECRET_DIRS or parts[:2] == [".config", "gh"]:
            return True
        name = parts[0]
        return (len(parts) == 1 and name.startswith(".") and name not in _DOT_CACHES
                and not name.startswith(".zcompdump"))
    if _DEV_WRITABLE.match(c):
        return False
    if not erase:
        if c.startswith("/dev/"):           # un périphérique RÉEL ; `/dev/null,` est de la prose
            return _os.path.exists(c)
        return c.count("/") >= 2 and bool(_SYSTEM_OVERWRITE.match(c) or _VAR_PATH.match(c))
    return _root_level(c) or bool(_SYSTEM_OVERWRITE.match(c) or _VAR_PATH.match(c))


def _dirs_of(u: _Argv, an: _Analysis) -> tuple[tuple[str, bool], ...]:
    return getattr(u, "dirs", None) or ((an.cwd or _os.getcwd(), False),)


def _p_overwrite(an: _Analysis) -> bool:
    """Une cible protégée écrasée ou effacée — par un verbe de la table ou une redirection,
    jugée dans CHAQUE dossier où la commande peut tourner. `rm` étant dans la table, sa cible
    relative résolue (`cd ~ && rm -rf .`, `rm -rf ..` depuis `~/x`) est jugée ici : `_protected`
    contient `_root_level`, un second prédicat `rm` résolu ne jugerait rien de plus.

    Ce qui tourne sur un AUTRE hôte (`ssh h '…'`, `docker exec`, `kubectl exec`) n'est pas
    jugé ici : sa maison et son `/etc` ne sont pas ceux de cette machine (trou déclaré ; les
    prédicats `rm` d'avant T167 le jugent toujours)."""
    for u in an.units:
        if set(u.wrappers) & _REMOTE_WRAPPERS:
            continue
        erase = bool(u) and u[0] == "rm"
        for t in _overwrites(u):
            if any(_protected(_canon(t, d), erase) for d in _judged_dirs(t, u, an)):
                return True
    for c in an.raw_cmds:
        if id(c) in an.remote_raw:
            continue
        for t in _redir_targets(c):
            if any(_protected(_canon(t, d), False) for d in _judged_dirs(t, c, an)):
                return True
    return False


def _judged_dirs(t: str, u: _Argv, an: _Analysis) -> list[str]:
    """Les dossiers où juger `t` : tous pour une cible absolue ; pour une cible relative,
    seulement ceux que la ligne CONNAÎT — après `cd $D` l'ancien dossier n'est qu'une
    supposition, et c'est le trou déclaré (avertissement), pas un blocage (rejeu T167 :
    `(cd $S/$n && bash setup.sh)` jugeait le `> .mcp.json` du script dans la maison)."""
    rel = not t.startswith(("/", "~", "$"))
    return [d for d, unc in _dirs_of(u, an) if not (rel and unc)]


_REMOTE_WRAPPERS = frozenset({"ssh", "docker", "docker-compose", "kubectl"})


_BLOCK_PREDICATES: list[tuple[str, object, str]] = [
    ("download-into-shell", _p_download, _BLOCK_REGEX[0][1]),
    ("root-rm", _p_root_rm, _BLOCK_REGEX[2][1]),
    ("rm-root-or-home", _p_root_or_home, _BLOCK_REGEX[3][1]),
    ("rm-system-path", _p_system_path, _BLOCK_REGEX[4][1]),
    ("rm-var", _p_var, _BLOCK_REGEX[5][1]),
    ("mkfs", _p_mkfs, _BLOCK_REGEX[6][1]),
    ("dd-device", _p_dd, _BLOCK_REGEX[7][1]),
    ("chmod-world", _p_chmod, _BLOCK_REGEX[8][1]),
    ("fork-bomb", _p_fork, _BLOCK_REGEX[9][1]),
    ("mv-root-or-home", _p_mv_root,
     "Moving a root, home or top-level system directory away — catastrophic"),
    ("rsync-delete-root-or-home", _p_rsync_root,
     "rsync --delete onto a root or home path erases everything the source lacks"),
    ("unresolved-head", _p_unresolved_head,
     "A command named by a variable this line never sets, run on a root or home path"),
    ("xargs-blind", _p_xargs_blind,
     "xargs feeds a destructive command from input this guard cannot read "
     "(a file, or an unknown producer) — list the targets first"),
    ("overwrite-protected-path", _p_overwrite,
     "Overwriting or erasing a protected path (home, a ~/.dotfile, ~/.ssh, ~/.gnupg, ~/.aws, "
     "~/.config/gh, a system path) — by shred, truncate, a `>` redirection, cp/mv/ln from "
     "/dev/null, tee, sed -i … d, or rm"),
]



# ── Le geste doit etre la COMMANDE de son segment, jamais un mot dans un argument ──
#
# Ce niveau comparait une SOUS-CHAINE sur la commande entiere :
# `if pattern.lower() in cmd_lower`. Il bloquait donc tout ce qui MENTIONNE le geste —
# un heredoc qui ecrit un script, un message de commit qui explique un correctif, une
# chaine Python entre guillemets.
#
# Mesure le 2026-09-16 : trois commandes bloquees d'affilee dans la meme seance, toutes
# en train d'ECRIRE ou de DOCUMENTER un retour arriere, aucune en train d'en faire un.
# Le depot avait deja nomme la classe (`a-bash-hook-that-blocks-the-prose-about-the-gesture`)
# et l'avait corrigee pour ses gardes A ETAT (`shlex.split` par segment, lignes 168 et
# 244) — mais pas pour le niveau litteral, qui est celui qu'on lit en premier.
#
# La question posee ici est structurelle : dans un segment de shell, les PREMIERS mots
# sont-ils exactement ceux du motif ? Le corps d'un heredoc appartient au segment du
# `cat`, dont l'argv commence par `cat` — il ne peut donc plus declencher.
_PREFIXES_A_SAUTER = {"sudo", "env", "nohup", "time", "command", "exec", "rtk", "proxy"}


def _sans_heredocs(command: str) -> str:
    """Retire le CORPS des heredocs — c'est de la donnee, jamais une commande.

    Sans ca, decouper sur les retours a la ligne transforme chaque ligne du corps en
    segment : `cat > x.sh <<EOF` suivi de `git reset --hard $before` faisait croire au
    garde qu'on lancait un retour arriere, alors qu'on ECRIVAIT un script qui en
    contient un. Mesure le 2026-09-16 : c'est le dernier des trois blocages de la
    seance, et le plus tenace.
    """
    lignes = command.split("\n")
    sortie, i = [], 0
    while i < len(lignes):
        ligne = lignes[i]
        sortie.append(ligne)
        m = re.search(r"<<-?\s*[\"\']?([A-Za-z_][A-Za-z0-9_]*)[\"\']?", ligne)
        i += 1
        if not m:
            continue
        delim = m.group(1)
        while i < len(lignes) and lignes[i].strip() != delim:
            i += 1                      # le corps est saute, pas analyse
        if i < len(lignes):
            i += 1                      # et le delimiteur de fin aussi
    return "\n".join(sortie)


# ── R633 : une entrée qui n'est jamais la COMMANDE de son segment ───────────────
#
# Le passage au « geste = commande du segment » (2026-09-16) a eu raison pour `git
# reset --hard` et tort pour six entrées de ces tables, qui ne sont JAMAIS une
# commande : `DROP TABLE` est l'argument de `psql`, `--build` celui de `docker
# compose`. Elles ne pouvaient plus se déclencher — `psql -c '<sql destructif>'`
# passait — et se lisaient comme une couverture qui n'existait plus. Trouvé le
# 2026-10-16 par la sonde `drop-table` d'audit_fleet (baseline).
#
# Une question structurelle par forme :
#   - SQL (et le schéma d'installation) : le pipeline atteint-il un CLIENT SQL ? Un
#     `git commit -m '…'` ou un `grep` n'en atteint aucun ; `echo … | psql`,
#     `make psql Q=…`, `docker exec … psql -c …` et un heredoc donné à `psql` oui.
#   - argument : est-ce un jeton d'une commande qui n'est pas de la prose ?
# Garde : tests/test_every_guard_entry_can_fire.py — chaque entrée a un exemple qui
# la déclenche, et une entrée neuve sans exemple fait échouer le test.
_CLIENT_BOUND = frozenset({"DROP TABLE", "DROP DATABASE", "DROP SCHEMA", "DELETE FROM", "init_db.sql"})
_ARGUMENT_GESTURES = frozenset({"--build"})
_SQL_CLIENTS = frozenset({"psql", "prod-psql", "mysql", "mariadb", "sqlite3"})
_PROSE_HEADS = frozenset({"echo", "printf", "git", "grep", "rg", "cat", "sed", "awk",
                          "head", "tail", "less", "gh", "python", "python3"})


def _gesture_fires(command: str, pattern: str) -> bool:
    if pattern in _CLIENT_BOUND:
        return _reaches_a_sql_client(command, pattern)
    if pattern in _ARGUMENT_GESTURES:
        return _is_an_argument_of_a_command(command, pattern)
    # 2026-10-18 : sur l'argv NORMALISÉ (`_commands`), lu par sous-commande quand le motif
    # a une lecture structurelle (`_STRUCTURAL`). la lecture d'avant
    # (`_is_the_command_of_a_segment`, une seule orthographe) est retirée par T125.
    pred = _STRUCTURAL.get(pattern)
    return any((pred(argv) if pred else _first_words(argv, pattern)) for argv in _commands(command))


def _pipelines(command: str) -> list[list[list[str]]]:
    """Pipelines (`&&`, `||`, `;`, newline) of stages (`|`), each an argv.

    Tokenised with quotes kept whole: a `;` inside `psql -c 'BEGIN; …;'` does not
    cut the SQL away from its client.
    """
    out: list[list[list[str]]] = []
    for line in _sans_heredocs(command).split("\n"):
        try:
            lex = shlex.shlex(line, posix=True, punctuation_chars="|&;")
            lex.whitespace_split = True
            toks = list(lex)
        except ValueError:
            toks = line.split()
        pipeline: list[list[str]] = [[]]
        for tok in toks:
            if tok in ("&&", "||", ";", ";;"):
                out.append(pipeline)
                pipeline = [[]]
            elif tok == "|":
                pipeline.append([])
            else:
                pipeline[-1].append(tok)
        out.append(pipeline)
    return [p for p in out if any(p)]


def _is_a_sql_client(argv: list[str]) -> bool:
    return any(a.rsplit("/", 1)[-1].lower() in _SQL_CLIENTS for a in argv)


def _reaches_a_sql_client(command: str, pattern: str) -> bool:
    rx = re.compile(r"(?<![\w-])" + r"\s+".join(map(re.escape, pattern.split())) + r"(?![\w-])",
                    re.IGNORECASE)
    # A heredoc given to a SQL client: its body IS the SQL that runs.
    lines, i = command.split("\n"), 0
    while i < len(lines):
        m = re.search(r"<<-?\s*[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?", lines[i])
        opener, i = lines[i], i + 1
        if not m:
            continue
        body = []
        while i < len(lines) and lines[i].strip() != m.group(1):
            body.append(lines[i])
            i += 1
        i += 1
        if _is_a_sql_client(opener.split()) and rx.search("\n".join(body)):
            return True
    for pipeline in _pipelines(command):
        if any(_is_a_sql_client(stage) for stage in pipeline) \
                and rx.search(" ".join(a for stage in pipeline for a in stage)):
            return True
    return False


def _is_an_argument_of_a_command(command: str, pattern: str) -> bool:
    for pipeline in _pipelines(command):
        for argv in pipeline:
            i = 0
            while i < len(argv) and (argv[i].lower() in _PREFIXES_A_SAUTER or "=" in argv[i]):
                i += 1
            if i >= len(argv) or argv[i].rsplit("/", 1)[-1].lower() in _PROSE_HEADS:
                continue
            if any(a == pattern or a.startswith(pattern + "=") for a in argv[i + 1:]):
                return True
    return False


# ── UN lecteur du shell pour tous les gardes de ce fichier (2026-10-18, 2026-10-19) ──
#
# Chaque garde ci-dessus comparait les PREMIERS MOTS d'un segment à UNE orthographe : le
# tier littéral (`git push --force` = les trois premiers mots), le tier regex
# (`rm -rf /`, `chmod 777`), `_serial_full_suite`, et les deux gardes à état par leur
# propre expression. Mesuré le 2026-10-18 sur l'ancien garde, toutes ces formes PASSAIENT :
#
#     git push origin main --force      git -C d push --force      git push origin +main
#     git --no-pager push -f            /usr/bin/git push --force  sh -c "git push --force"
#     git reset -q --hard               git -C d reset --hard      git commit -nm x
#     git commit -m x --no-verify       git push origin main --no-verify
#     docker --context x system prune   /usr/bin/dropdb x          rm -rf -- /
#     chmod 0777 /etc                   chmod a+rwx /etc           uv run pytest tests/
#
# et `git commit -m "s<LF><LF>git reset --hard …"` BLOQUAIT, parce que chaque garde
# coupait le texte sur `\n` sans regarder les guillemets : une ligne d'un message de commit
# devenait une commande. Une classe, deux symptômes — un analyseur qui connaît une seule
# des deux syntaxes du shell (`a-parser-that-knows-one-of-two-syntaxes`).
#
# ⚠️ 2026-10-19 (T125) — le correctif du 18 n'avait été posé que sur le tier LITTÉRAL. Le
# tier regex lisait encore le TEXTE brut (`echo "rm -rf ~/x" > notes.txt` bloqué, `timeout 5
# rm -rf ~/x` et `echo ~ | xargs rm -rf` passés), quatre gardes privés coupaient encore
# sur `re.split(r"&&|\|\||;|\n")` (un `;` cité devenait un séparateur), et le corps d'un
# heredoc était jeté sans condition — y compris celui qu'un shell EXÉCUTE (`bash <<EOF`,
# `| bash`, `python3 - <<EOF`). Désormais TOUT passe par `_analyse` :
#   * `_lex` lit les guillemets, capture chaque heredoc (délimiteur cité ? terminé ? combien
#     sur la ligne ?) et chaque substitution `$(…)`, `` `…` ``, `<(…)` qui S'EXÉCUTE ;
#   * `_normalise` saute les enveloppes en GARDANT leur trace (`sudo`, `xargs`…) et déroule
#     `sh -c`, `eval`, `env -S`, `su -c`, `ssh hôte CMD`, `docker|kubectl exec`, `watch`,
#     `flock`, `parallel`, `find -exec|-delete` ;
#   * `_walk` suit l'entrée standard : un `xargs` reçoit les mots de l'`echo` qui le nourrit,
#     un shell ou un interpréteur nourri d'un heredoc, d'une chaîne `<<<` ou d'un tube voit
#     son code LU — jamais jeté ;
#   * un corps de heredoc n'est de la DONNÉE que si tout tient (msdr R95) : délimiteur cité,
#     terminé, seul sur sa ligne, lu par `cat`/`tee`/`git commit -F -`, pas tubé dans un
#     shell, et le fichier qu'il écrit n'est plus nommé ensuite. Sinon il est lu comme du
#     shell. Non cité, ses `$(…)` s'exécutent et sont lus ;
#   * le code d'un interpréteur (`python3 -c`, `perl -e`, un heredoc donné à `python3 -`) est
#     balayé au TEXTE avec les anciennes règles, fermé en cas de doute ; un code Python qui
#     n'appelle rien de `os`/`subprocess`/`shutil`/`exec`/`eval` passe (liste blanche AST).
# Une exception de ce lecteur ne rend plus « rien » : `check_command` juge alors la ligne
# brute avec les anciennes règles de chaque tier (`_raw_verdict`) — fermé, pas ouvert.
#
# `_git(argv)` saute ensuite TOUTES les options globales de git (celles qui prennent une
# valeur séparée la consomment) et rend `(sous-commande, arguments, dossiers -C)`.
# ⚠️ `--exec-path` sans `=` n'en consomme pas : git l'affiche et sort (git.c).
#
# Les drapeaux se lisent PAR SOUS-COMMANDE, valeurs d'options comprises : dans un groupe
# court, une option à valeur termine le groupe (`-mnope` est le message « nope », pas
# `-n`) ; `-n` est `--no-verify` pour `commit` et `--dry-run` pour `push`.
#
# ⚠️ Ce que le garde reste : un frein aux ACCIDENTS (modèle ARCH p.164). Un alias ou une
# fonction shell n'est pas résolu, `cd d && git …` est jugé dans le dossier du hook, une
# variable n'est résolue que si la même ligne l'affecte (`D=~; rm -rf $D`), et l'entrée
# d'un `xargs` qu'il ne sait pas lire (`ls | xargs rm -rf`) est un trou DÉCLARÉ, signalé
# en avertissement. Les refus `permissions.deny` de settings.json sont des PRÉFIXES de
# commande — au mieux un premier filet ; c'est CE fichier qui fait foi.

import ast as _ast
import functools as _functools
import os as _os
import stat as _stat
import warnings as _warnings

_OPS = ("&>>", "<<<", "<<-", ";;", "&&", "||", "|&", "<<", ">>", "&>", ">&", "<&", ">|",
        "|", "&", ";", "(", ")", "<", ">")
_REDIRS = frozenset({"&>>", "<<<", ">>", "&>", ">&", "<&", ">|", "<", ">"})
_WRITES = frozenset({">", ">>", ">|", "&>", "&>>"})
_NAME_EQ = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\+?=")
_HEREDOC_DELIM = re.compile(r"""[ \t]*(?:'([^'\n]*)'|"([^"\n]*)"|\\?([^\s;&|()<>'"]+))""")
_RESERVED = frozenset({"{", "}", "!", "if", "then", "elif", "else", "fi", "while", "until",
                       "do", "done"})
_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh"})
_INTERPRETERS = re.compile(r"^(?:python(?:\d+(?:\.\d+)?)?|pypy3?|node|nodejs|perl|ruby)$")
_DOWNLOADERS = frozenset({"curl", "wget"})
# Dérivé de la table des verbes qui écrasent (T167) : une seule liste à tenir.
_DESTRUCTIVE = frozenset(_OVERWRITERS) | {"chmod", "chown", "mkfs"}
_MAX_DEPTH = 6
_UNREAD = "\x00stdin-unread"      # l'entrée d'un xargs que ce garde ne sait pas lire
_STDIN = "\x00stdin"              # le code d'un interpréteur arrive par son entrée standard
# Enveloppe -> (options qui prennent une valeur SÉPARÉE, nombre de positionnels avant la commande)
_WRAPPERS: dict[str, tuple[frozenset[str], int]] = {
    "sudo": (frozenset({"-u", "-g", "-h", "-p", "-C", "-U", "-r", "-t", "-D", "-R", "-T",
                        "--user", "--group", "--host", "--prompt", "--chdir", "--role",
                        "--type", "--close-from", "--other-user", "--chroot",
                        "--command-timeout"}), 0),
    "doas": (frozenset({"-u", "-C"}), 0),
    "timeout": (frozenset({"-s", "-k", "--signal", "--kill-after"}), 1),
    "nice": (frozenset({"-n", "--adjustment"}), 0),
    "ionice": (frozenset({"-c", "-n", "-p", "-P", "-u", "--class", "--classdata"}), 0),
    "stdbuf": (frozenset({"-i", "-o", "-e", "--input", "--output", "--error"}), 0),
    "taskset": (frozenset(), 1),
    "nohup": (frozenset(), 0),
    "time": (frozenset({"-f", "-o", "--format", "--output"}), 0),
    "command": (frozenset(), 0),
    "exec": (frozenset({"-a"}), 0),
    "env": (frozenset({"-u", "-C", "-S", "--unset", "--chdir", "--split-string"}), 0),
    # busybox/toybox : un multi-appel, `busybox rm -rf ~` EST `rm -rf ~` (T125, trouvé par le
    # critique de complétude : le niveau regex brut le bloquait par accident).
    "busybox": (frozenset(), 0),
    "toybox": (frozenset(), 0),
    "xargs": (frozenset({"-I", "-L", "-n", "-P", "-s", "-d", "-E", "-a", "--max-args",
                         "--max-procs", "--max-chars", "--delimiter", "--eof", "--arg-file",
                         "--replace", "--max-lines", "--process-slot-var"}), 0),
}
# git.c : les options globales dont la valeur est le mot SUIVANT.
_GIT_VALUED = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env",
                         "--super-prefix", "--attr-source"})
_SSH_VALUED = frozenset({"-o", "-i", "-p", "-l", "-J", "-F", "-b", "-c", "-D", "-E", "-e", "-I",
                         "-L", "-m", "-O", "-Q", "-R", "-S", "-W", "-w", "-B"})


class _Heredoc:
    """Un heredoc tel que `_lex` l'a lu. `count` : heredocs ouverts sur la même ligne."""
    __slots__ = ("delim", "quoted", "dash", "body", "terminated", "count")

    def __init__(self, delim: str, quoted: bool, dash: bool) -> None:
        self.delim, self.quoted, self.dash = delim, quoted, dash
        self.body, self.terminated, self.count = "", False, 1


class _Argv(list):
    """Un argv, et d'où il vient : les enveloppes sautées (`sudo`, `xargs`…), ce que
    `xargs` remplace (`-I R`, ou "" pour « ajoute à la fin »), son entrée standard, ses
    substitutions, heredocs et redirections, l'étage du tube qui le nourrit, et si
    quelque chose le SUIT sur la ligne (ce qui rend `pkill -f` suicidaire)."""
    __slots__ = ("wrappers", "xrep", "stdin", "subs", "heredocs", "redirs", "follows",
                 "upstream", "scanned", "exe", "groups", "dirs")

    def __init__(self, it=()) -> None:
        super().__init__(it)
        self.wrappers: tuple[str, ...] = ()
        self.xrep: str | None = None
        self.stdin: str | None = None
        self.subs: list[tuple[str, str]] = []
        self.heredocs: list[_Heredoc] = []
        self.redirs: list[tuple[str, str]] = []
        self.follows = False
        self.upstream: "_Argv | None" = None
        self.scanned = False
        self.exe: str | None = None         # la tête telle qu'écrite (`./x.sh`), avant `_base`
        self.groups: tuple[int, ...] = ()   # les sous-shells `( … )` qui l'entourent (T167)
        # Les dossiers où elle PEUT s'exécuter, `(chemin absolu, incertain)` — un `cd` de la
        # ligne les change (T167) ; None : le dossier du hook.
        self.dirs: "tuple[tuple[str, bool], ...] | None" = None

    def clone(self, it=None) -> "_Argv":
        n = _Argv(self if it is None else it)
        for k in self.__slots__:
            setattr(n, k, getattr(self, k))
        return n


class _Analysis:
    """Ce qu'une ligne exécute : `units` (argv normalisés, imbriqués compris), `events`
    (téléchargement exécuté, bombe fork), `gaps` (trous déclarés, en avertissement), `texts`
    (chaque texte lu comme du shell), `raw` (code lu au texte, règles anciennes), `vars`
    (affectations de la ligne : `NOM` -> ses valeurs POSSIBLES à cet endroit), `raw_cmds`
    (commandes simples développées, avant normalisation, redirections comprises), `cwd` (le
    dossier où la ligne s'exécute), `files` (les scripts lus : `(chemin, mtime_ns, taille)`),
    `cond` (profondeur de boucle ou de condition au point courant), `dirs` (les dossiers
    possibles au point courant, après les `cd` de la ligne — T167)."""
    __slots__ = ("units", "events", "gaps", "texts", "raw", "vars", "raw_cmds", "cwd",
                 "files", "cond", "dirs", "remote", "remote_raw")

    def __init__(self, cwd: str | None = None) -> None:
        self.units: list[_Argv] = []
        self.events: list[tuple[str, str]] = []
        self.gaps: list[str] = []
        self.texts: list[str] = []
        self.raw: list[str] = []
        self.vars: dict[str, list[str]] = {}
        self.raw_cmds: list[_Argv] = []
        self.cwd: str | None = cwd or _CWD
        self.files: list[tuple[str, int, int]] = []
        self.cond = 0
        self.dirs: "tuple[tuple[str, bool], ...] | None" = None
        self.remote = 0                     # profondeur sous `ssh`/`docker exec`/`kubectl exec`
        self.remote_raw: set[int] = set()   # `id` des `raw_cmds` nées sur un AUTRE hôte


def _delim(m: "re.Match[str]") -> tuple[str, bool]:
    if m.group(1) is not None:
        return m.group(1), True
    if m.group(2) is not None:
        return m.group(2), True
    return m.group(3) or "", m.group(0).lstrip().startswith("\\")


def _read_bodies(s: str, i: int, pending: list) -> int:
    """`s[i]` suit un saut de ligne : lit le corps de chaque heredoc en attente."""
    n = len(s)
    for hd in pending:
        lines = []
        done = False
        while i < n:
            j = s.find("\n", i)
            line = s[i:] if j < 0 else s[i:j]
            i = n if j < 0 else j + 1
            if (line.lstrip("\t") if hd.dash else line).strip() == hd.delim:
                done = True
                break
            lines.append(line)
        hd.body, hd.terminated, hd.count = "\n".join(lines), done, len(pending)
    return i


def _match_paren(s: str, i: int) -> int:
    """`s[i] == "("` : l'indice APRÈS sa parenthèse fermante (guillemets, commentaires et
    corps de heredocs respectés — `"$(cat <<'EOF' … don't … EOF)"` est l'idiome du commit)."""
    depth, n, pending = 0, len(s), []
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "\n":
            i = _read_bodies(s, i + 1, pending)
            pending = []
            continue
        if c == "<" and s.startswith("<<", i) and not s.startswith("<<<", i):
            dash = s.startswith("<<-", i)
            m = _HEREDOC_DELIM.match(s, i + (3 if dash else 2))
            if m:
                name, quoted = _delim(m)
                pending.append(_Heredoc(name, quoted, dash))
                i = m.end()
            else:
                i += 2
            continue
        if c == "#" and i > 0 and s[i - 1] in " \t\n;&|(":
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "'":
            j = s.find("'", i + 1)
            if j < 0:
                raise ValueError("unclosed '")
            i = j + 1
            continue
        if c == '"':
            i = _end_dq(s, i)
            continue
        if c == "`":
            i = _end_bq(s, i)
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced (")


def _end_bq(s: str, i: int) -> int:
    j = i + 1
    while j < len(s):
        if s[j] == "\\":
            j += 2
            continue
        if s[j] == "`":
            return j + 1
        j += 1
    raise ValueError("unclosed `")


def _end_dq(s: str, i: int, subs: list | None = None) -> int:
    """`s[i] == '"'` : l'indice APRÈS le guillemet fermant. `subs` reçoit les substitutions
    qu'un guillemet double laisse S'EXÉCUTER."""
    j, n = i + 1, len(s)
    while j < n:
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == '"':
            return j + 1
        if c == "$" and s[j + 1:j + 2] == "(":
            k = _match_paren(s, j + 1)
            if subs is not None and s[j + 2:j + 3] != "(":
                subs.append((s[j + 2:k - 1], "cmd"))
            j = k
            continue
        if c == "`":
            k = _end_bq(s, j)
            if subs is not None:
                subs.append((s[j + 1:k - 1], "cmd"))
            j = k
            continue
        j += 1
    raise ValueError('unclosed "')


def _lex(s: str, naive: bool = False) -> list[tuple[str, object]]:
    """Jetons d'une ligne de shell : ("w", mot) | ("op", opérateur) | ("redir", op) |
    ("hd", _Heredoc) | ("sub", (corps, "cmd"|"proc")).

    Un `\\n` est un opérateur SEULEMENT hors guillemets ; le corps d'un heredoc est LU au
    saut de ligne qui suit son ouverture et rendu avec ses propriétés — jamais jeté ici :
    c'est `_walk` qui décide s'il est donnée ou code. `naive` traite les guillemets comme
    des caractères ordinaires — le repli d'une commande mal citée, prudent comme l'ancien
    `segment.split()` : mieux vaut un faux positif qu'un trou.
    """
    toks: list[tuple[str, object]] = []
    word: str | None = None
    pending: list[_Heredoc] = []
    i, n = 0, len(s)

    def add(text: str) -> None:
        nonlocal word
        word = (word or "") + text

    while i < n:
        c = s[i]
        if c == "\n":
            if word is not None:
                toks.append(("w", word))
                word = None
            toks.append(("op", "\n"))
            i = _read_bodies(s, i + 1, pending)
            pending = []
            continue
        if c in " \t\r":
            if word is not None:
                toks.append(("w", word))
                word = None
            i += 1
            continue
        if c == "#" and word is None:
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "\\":
            if s[i + 1:i + 2] == "\n":
                i += 2
                continue
            add(s[i + 1:i + 2])
            i += 2
            continue
        if not naive and c == "'":
            j = s.find("'", i + 1)
            if j < 0:
                raise ValueError("unclosed '")
            add(s[i + 1:j])
            i = j + 1
            continue
        if not naive and c == "$" and s[i + 1:i + 2] == "'":
            j = i + 2
            while j < n and s[j] != "'":
                j += 2 if s[j] == "\\" else 1
            if j >= n:
                raise ValueError("unclosed $'")
            add(s[i + 2:j])
            i = j + 1
            continue
        if not naive and c == '"':
            subs: list = []
            j = _end_dq(s, i, subs)
            toks.extend(("sub", x) for x in subs)
            add(re.sub(r'\\([\\"$`])', r"\1", s[i + 1:j - 1].replace("\\\n", "")))
            i = j
            continue
        if not naive and c == "$" and s[i + 1:i + 2] == "(":
            j = _match_paren(s, i + 1)
            if s[i + 2:i + 3] != "(":               # `$((…))` est de l'arithmétique
                toks.append(("sub", (s[i + 2:j - 1], "cmd")))
            add(s[i:j])
            i = j
            continue
        if c == "$" and s[i + 1:i + 2] == "{":
            j = s.find("}", i)
            if j < 0:
                raise ValueError("unclosed ${")
            add(s[i:j + 1])
            i = j + 1
            continue
        if not naive and c == "`":
            j = _end_bq(s, i)
            toks.append(("sub", (s[i + 1:j - 1], "cmd")))
            add(s[i:j])
            i = j
            continue
        if not naive and c in "<>" and s[i + 1:i + 2] == "(":
            j = _match_paren(s, i + 1)      # substitution de processus : un mot
            toks.append(("sub", (s[i + 2:j - 1], "proc")))
            add(s[i:j])
            i = j
            continue
        op = next((o for o in _OPS if s.startswith(o, i)), None)
        if op is None:
            add(c)
            i += 1
            continue
        if op in _REDIRS or op in ("<<", "<<-"):
            if word is not None and (word.isdigit() or re.fullmatch(r"\{\w+\}", word)):
                word = None                 # `2>`, `{fd}>` : le descripteur n'est pas un mot
            if word is not None:
                toks.append(("w", word))
                word = None
            i += len(op)
            if op in ("<<", "<<-"):
                m = _HEREDOC_DELIM.match(s, i)
                if m:
                    name, quoted = _delim(m)
                    hd = _Heredoc(name, quoted, op == "<<-")
                    pending.append(hd)
                    toks.append(("hd", hd))
                    i = m.end()
                continue
            toks.append(("redir", op))
            continue
        if word is not None:
            toks.append(("w", word))
            word = None
        toks.append(("op", op))
        i += len(op)
    if word is not None:
        toks.append(("w", word))
    for hd in pending:                      # ouvert, jamais suivi d'un saut de ligne
        hd.count = len(pending)
    return toks


def _worst_link(links: list[str]) -> str:
    """Le lien qui précède une commande : `&&` seulement si TOUS les liens vus le sont."""
    if not links:
        return ""
    bad = [x for x in links if x != "&&"]
    return "&&" if not bad else (";" if bad[0] == "\n" else bad[0])


_VAR_REF = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})")


def _in_test(cur: list[str]) -> bool:
    """`cur` est-il ouvert sur un `[[` EN POSITION DE COMMANDE et pas encore refermé ? Un
    `"[["` cité en argument (`echo "[[" || rm -rf ~`) n'ouvre rien : le lexer ayant perdu
    les guillemets, seul un `[[` de tête (après `if`/`while`/`!`…) compte."""
    i = 0
    while i < len(cur) and cur[i] in ("if", "elif", "while", "until", "!", "then", "do", "else"):
        i += 1
    return i < len(cur) and cur[i] == "[[" and "]]" not in cur[i + 1:]


def _simple_commands(command: str) -> list[tuple[_Argv, str]]:
    """Les commandes simples de la ligne, chacune avec le lien qui la précède. Chaque argv
    porte ses heredocs, ses substitutions et ses redirections (`(op, cible)`) — la cible
    d'une redirection n'est pas un argument."""
    try:
        toks = _lex(command)
    except ValueError:
        toks = _lex(command, naive=True)
    out: list[tuple[_Argv, str]] = []
    cur = _Argv()
    links: list[str] = []
    redir: str | None = None
    # Les sous-shells `( … )` ouverts au point courant, chacun par un numéro : `cd` y reste
    # (T167). Une commande faite de ses seules redirections (`> ~/.bashrc`) est une commande.
    gstack: list[int] = []
    gnext = 0

    def flush() -> bool:
        nonlocal cur
        if cur or cur.subs or cur.heredocs or cur.redirs:
            cur.groups = tuple(gstack)
            out.append((cur, _worst_link(links)))
            cur = _Argv()
            return True
        return False

    for kind, v in toks:
        if kind == "redir":
            redir = v
            continue
        if kind == "hd":
            cur.heredocs.append(v)
            continue
        if kind == "sub":
            cur.subs.append(v)
            continue
        if kind == "w":
            if redir is not None:
                cur.redirs.append((redir, v))
                redir = None
            else:
                cur.append(v)
            continue
        redir = None
        if v in ("&&", "||", "(", ")") and _in_test(cur):
            # `[[ -z $A || $A == x ]]` : un `||` DANS `[[ … ]]` relie deux tests, pas deux
            # commandes. Coupé là, `$A == x ]]` devenait une commande de tête `$A` — et
            # A=$(curl …) « exécutait » la sortie d'un téléchargement (rejeu T150b).
            cur.append(v)
            continue
        if v in ("(", ")"):
            if flush():
                links = []
            if v == "(":
                gnext += 1
                gstack.append(gnext)
            elif gstack:
                gstack.pop()
            continue
        if flush():
            links = [v]
        elif not (v == "\n" and links):     # `a &&<LF> b` : la ligne continue
            links.append(v)
    flush()
    return out


def _skip_options(argv: list[str], valued: frozenset[str], positional: int) -> int:
    """L'indice de la commande enveloppée, options et positionnels de l'enveloppe sautés."""
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--":
            i += 1
            break
        if not a.startswith("-") or a == "-":
            break
        i += 2 if a in valued else 1
    return min(i + positional, len(argv))


def _base(word: str) -> str:
    return word if word.startswith(("$(", "`")) else word.rsplit("/", 1)[-1]


def _xargs_replace(argv: list[str]) -> str:
    """Ce que `xargs` remplace dans sa commande : `-I R`, `-i`/`--replace` ({}), ou ""
    (ses mots d'entrée s'AJOUTENT à la fin)."""
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--" or not a.startswith("-") or a == "-":
            break
        if a == "-I":
            return argv[i + 1] if i + 1 < len(argv) else "{}"
        if a.startswith("-I"):
            return a[2:]
        if a in ("-i", "--replace"):
            return "{}"
        if a.startswith("--replace="):
            return a.split("=", 1)[1]
        if a.startswith("-i") and not a.startswith("--"):
            return a[2:]
        i += 2 if a in _WRAPPERS["xargs"][0] else 1
    return ""


def _su_command(argv: list[str]) -> str | None:
    for i, a in enumerate(argv[1:], start=1):
        if a in ("-c", "--command"):
            return argv[i + 1] if i + 1 < len(argv) else None
        if a.startswith("--command="):
            return a.split("=", 1)[1]
    return None


def _after_host(argv: list[str]) -> list[str]:
    """`ssh [opts] hôte CMD…` -> CMD… (le shell distant les reçoit joints)."""
    j = 1
    while j < len(argv) and argv[j].startswith("-"):
        j += 2 if argv[j] in _SSH_VALUED else 1
    return argv[j + 1:]


_EXEC_VALUED = frozenset({"-e", "--env", "-u", "--user", "-w", "--workdir", "--env-file",
                          "--detach-keys", "--index"})
_COMPOSE_VALUED = frozenset({"-f", "--file", "-p", "--project-name", "--env-file", "--profile",
                             "--project-directory", "--ansi", "--progress", "--parallel"})


def _docker_exec(argv: list[str]) -> list[str]:
    """`docker [compose] exec [opts] CIBLE CMD…` -> CMD… ; [] pour tout autre geste docker."""
    words = _docker_words(argv) if argv[0] == "docker" else ["compose"] + argv[1:]
    if words[:1] == ["container"]:
        words = words[1:]
    if words[:1] == ["compose"]:
        j = 1
        while j < len(words) and words[j].startswith("-"):
            j += 2 if words[j] in _COMPOSE_VALUED else 1
        words = words[j:]
    if words[:1] != ["exec"]:
        return []
    j = 1
    while j < len(words) and words[j].startswith("-"):
        j += 2 if words[j] in _EXEC_VALUED else 1
    return words[j + 1:]


def _kubectl_exec(argv: list[str]) -> list[str]:
    if "exec" in argv and "--" in argv and argv.index("exec") < argv.index("--"):
        return argv[argv.index("--") + 1:]
    return []


def _watch_rest(argv: list[str]) -> list[str]:
    j = 1
    while j < len(argv) and argv[j].startswith("-"):
        if argv[j] == "--":
            j += 1
            break
        j += 2 if argv[j] in ("-n", "--interval", "-q", "--equexit") else 1
    return argv[j:]


def _normalise(argv: list[str], depth: int = 0, an: _Analysis | None = None) -> list[_Argv]:
    """Les argv qu'une commande simple exécute vraiment (zéro, un ou plusieurs), chacun avec
    la trace des enveloppes qui l'entouraient."""
    if an is None:
        an = _Analysis()
    wr = list(getattr(argv, "wrappers", ()))
    xrep = getattr(argv, "xrep", None)
    argv = list(argv)

    def done(units: list[_Argv]) -> list[_Argv]:
        for u in units:
            u.wrappers = tuple(wr) + tuple(u.wrappers)
            if u.xrep is None:
                u.xrep = xrep
        return units

    def unit(words: list[str]) -> list[_Argv]:
        return done([_Argv(words)])

    def inner_text(text: str) -> list[_Argv]:
        return done(_walk_safe(text, depth + 1, an))

    def inner_argv(words: list[str]) -> list[_Argv]:
        if not words:
            return []
        if depth >= _MAX_DEPTH:
            an.raw.append(" ".join(words))
            return []
        return done(_normalise(_Argv(words), depth + 1, an))

    while argv:
        a0 = argv[0]
        if a0 in _RESERVED or _NAME_EQ.match(a0):
            argv = argv[1:]
            continue
        head = _base(a0)
        if head == "rtk":
            argv = argv[1:]
            if argv[:1] == ["proxy"]:
                argv = argv[1:]
            continue
        if head == "command" and argv[1:2] in (["-v"], ["-V"]):
            return []                       # une question, pas une exécution
        if head == "env":
            j = 1
            while j < len(argv) and argv[j].startswith("-"):
                if argv[j] in ("-S", "--split-string") and j + 1 < len(argv):
                    return inner_text(argv[j + 1] + " " + shlex.join(argv[j + 2:]))
                if argv[j].startswith("--split-string="):
                    return inner_text(argv[j].split("=", 1)[1] + " " + shlex.join(argv[j + 1:]))
                j += 2 if argv[j] in _WRAPPERS["env"][0] else 1
            argv = argv[j:]
            continue
        if head in _WRAPPERS:
            wr.append(head)
            if head == "xargs":
                xrep = _xargs_replace(argv)
            argv = argv[_skip_options(argv, *_WRAPPERS[head]):]
            continue
        break
    if not argv:
        return []
    exe = argv[0]
    argv[0] = _base(argv[0])
    head = argv[0]
    if head in _SHELLS:
        j, has_c = 1, False
        while j < len(argv) and argv[j][:1] in "-+" and argv[j] not in ("-", "--", "+"):
            if argv[j] in ("-o", "+o", "-O", "+O", "--rcfile", "--init-file"):
                j += 2
                continue
            if not argv[j].startswith("--") and "c" in argv[j][1:]:
                has_c = True
            j += 1
        if j < len(argv) and argv[j] == "--":
            j += 1
        if has_c and j < len(argv):
            return inner_text(argv[j])
        return unit(argv)
    if head == "eval":
        return inner_text(" ".join(argv[1:]))
    if head == "su":
        cmd = _su_command(argv)
        if cmd is None:
            return unit(argv)
        wr.append("su")
        return inner_text(cmd)
    if head == "ssh":
        outer, rest = unit(argv), _after_host(argv)
        if not rest:
            return outer
        wr.append("ssh")
        an.remote += 1
        try:
            return outer + inner_text(" ".join(rest))
        finally:
            an.remote -= 1
    if head in ("docker", "docker-compose", "kubectl"):
        outer = unit(argv)
        rest = _kubectl_exec(argv) if head == "kubectl" else _docker_exec(argv)
        if not rest:
            return outer
        wr.append(head)
        an.remote += 1
        try:
            return outer + inner_argv(rest)
        finally:
            an.remote -= 1
    if head == "watch":
        rest = _watch_rest(argv)
        if not rest:
            return unit(argv)
        wr.append("watch")
        return inner_text(" ".join(rest))
    if head == "flock":
        j = 1
        while j < len(argv) and argv[j].startswith("-") and argv[j] not in ("-c", "--command"):
            j += 2 if argv[j] in ("-w", "--wait", "--timeout", "-E", "--conflict-exit-code") else 1
        if j < len(argv) and argv[j] in ("-c", "--command"):
            wr.append("flock")
            return inner_text(argv[j + 1]) if j + 1 < len(argv) else []
        j += 1                              # le fichier verrou
        if j < len(argv) and argv[j] in ("-c", "--command"):
            wr.append("flock")
            return inner_text(argv[j + 1]) if j + 1 < len(argv) else []
        wr.append("flock")
        return inner_argv(argv[j:])
    if head == "parallel":
        return _parallel(argv, wr, inner_text, unit)
    if head == "find":
        return _find(argv, wr, inner_argv, unit)
    if head == "git":
        # `git -c alias.x='!cmd' x` : un alias qui commence par `!` est lancé par un shell (T125).
        bodies = [argv[j + 1].split("=", 1)[1][1:] for j in range(1, len(argv) - 1)
                  if argv[j] == "-c" and argv[j + 1].lower().startswith("alias.")
                  and "=" in argv[j + 1] and argv[j + 1].split("=", 1)[1].startswith("!")]
        if bodies:
            wr.append("git-alias")
            return unit(argv) + [u for b in bodies for u in inner_text(b)]
    units = unit(argv)
    units[0].exe = exe
    return units


_PARALLEL_VALUED = frozenset({"-j", "-P", "--jobs", "-S", "--sshlogin", "-a", "--arg-file",
                              "-d", "--delimiter", "--colsep", "-N", "-n", "--max-args", "-L",
                              "--timeout", "--joblog", "--results", "-I", "--replace"})


def _parallel(argv, wr, inner_text, unit) -> list[_Argv]:
    """`parallel [opts] MODÈLE ::: ENTRÉES` : le modèle, `{}` remplacé par chaque entrée ;
    sans `:::`, les entrées arrivent par l'entrée standard, comme pour `xargs`."""
    j = 1
    while j < len(argv) and argv[j].startswith("-") and argv[j] not in (":::", "::::"):
        j += 2 if argv[j] in _PARALLEL_VALUED else 1
    rest = argv[j:]
    if ":::" in rest:
        k = rest.index(":::")
        template, inputs = rest[:k], [w for w in rest[k + 1:] if w not in (":::", ":::+")]
    else:
        template, inputs = rest, None
    wr.append("parallel")
    if not template:
        return [u for w in (inputs or []) for u in inner_text(w)]
    tmpl = " ".join(template)
    if inputs is None:
        units = inner_text(tmpl)
        for u in units:
            if u.xrep is None:
                u.xrep = "{}" if "{}" in tmpl else ""
        return units
    out: list[_Argv] = []
    for w in inputs:
        out += inner_text(tmpl.replace("{}", shlex.quote(w)) if "{}" in tmpl
                          else tmpl + " " + shlex.quote(w))
    return out


def _find(argv, wr, inner_argv, unit) -> list[_Argv]:
    """`find RACINES … -exec CMD {} ;|+` et `-delete` : la commande lancée sur chaque
    racine (`{}` remplacé), et `-delete` lu comme `rm -r RACINE` — la sur-approximation
    fermée : ce que find peut atteindre, au pire."""
    j = 1
    while j < len(argv) and (argv[j] in ("-H", "-L", "-P") or argv[j].startswith(("-D", "-O"))):
        j += 2 if argv[j] == "-D" else 1
    roots = []
    while j < len(argv) and not argv[j].startswith("-") and argv[j] not in ("(", "!", ","):
        roots.append(argv[j])
        j += 1
    roots = roots or ["."]
    out = unit(argv)
    wr.append("find")
    i = j
    while i < len(argv):
        a = argv[i]
        if a in ("-exec", "-execdir", "-ok", "-okdir"):
            k, cmd = i + 1, []
            while k < len(argv) and argv[k] not in (";", "+"):
                cmd.append(argv[k])
                k += 1
            for r in roots:
                out += inner_argv([w.replace("{}", r) for w in cmd])
            i = k + 1
            continue
        if a == "-delete":
            for r in roots:
                out += inner_argv(["rm", "-r", r])
        i += 1
    return out


# ── L'entrée standard, les heredocs et le code des interpréteurs ─────────────────

def _reads_stdin_shell(u: list[str]) -> bool:
    """Un shell sans `-c` qui lit son script sur l'entrée standard (`bash`, `sh -s`)."""
    if not u or u[0] not in _SHELLS:
        return False
    j, s_flag = 1, False
    while j < len(u) and u[j][:1] in "-+" and u[j] not in ("-", "--", "+"):
        if u[j] in ("-o", "+o", "-O", "+O", "--rcfile", "--init-file"):
            j += 2
            continue
        if not u[j].startswith("--") and "s" in u[j][1:]:
            s_flag = True
        j += 1
    if j < len(u) and u[j] == "--":
        j += 1
    return s_flag or j >= len(u) or u[j] == "-"


def _interp_code(u: list[str]) -> tuple[str, str | None, str | None] | None:
    """`(langage, code | _STDIN | None, script | None)` d'un interpréteur, ou None."""
    if not u or not _INTERPRETERS.match(u[0]):
        return None
    head = u[0]
    lang = ("python" if head.startswith(("python", "pypy")) else
            "node" if head.startswith("node") else head)
    args = u[1:]
    i = 0
    if lang == "python":
        while i < len(args):
            a = args[i]
            if a == "-" or a == "--":
                return (lang, _STDIN, None) if a == "-" or i + 1 >= len(args) else (lang, None, args[i + 1])
            if a.startswith("-") and not a.startswith("--"):
                if "m" in a[1:] and a.index("m") < (a.index("c") if "c" in a else len(a)):
                    return None                  # `-m module` : pas de code en ligne
                if "c" in a[1:]:
                    k = a.index("c", 1)
                    code = a[k + 1:] or (args[i + 1] if i + 1 < len(args) else "")
                    return (lang, code, None)
                i += 2 if a in ("-W", "-X", "-Q") else 1
                continue
            if a.startswith("--"):
                i += 1
                continue
            return (lang, None, a)
        return (lang, _STDIN, None)
    flags = {"perl": "eE", "ruby": "e", "node": "ep"}[lang]
    codes = []
    while i < len(args):
        a = args[i]
        if a in ("--eval", "--print") and lang == "node":
            codes.append(args[i + 1] if i + 1 < len(args) else "")
            i += 2
            continue
        if a.startswith(("--eval=", "--print=")):
            codes.append(a.split("=", 1)[1])
            i += 1
            continue
        if a == "-":
            return (lang, _STDIN, None)
        if a == "--":
            i += 1
            break
        if a.startswith("-") and not a.startswith("--") and len(a) > 1:
            if a[-1] in flags and (lang != "node" or len(a) == 2):
                codes.append(args[i + 1] if i + 1 < len(args) else "")
                i += 2
                continue
            i += 1
            continue
        if a.startswith("--"):
            i += 1
            continue
        break
    if codes:
        return (lang, "\n".join(codes), None)
    if i < len(args):
        return (lang, None, args[i])
    return (lang, _STDIN, None)


def _reads_code(u: list[str]) -> bool:
    if _reads_stdin_shell(u):
        return True
    ic = _interp_code(u)
    return ic is not None and ic[1] is _STDIN


def _stdin_of(argv: _Argv, prev) -> tuple[str | None, bool]:
    """`(texte, présent)` de l'entrée standard d'une commande : `<<<`, heredoc, tube."""
    for op, target in reversed(argv.redirs):
        if op == "<<<":
            return target, True
        if op == "<":
            return None, True
    if argv.heredocs:
        return argv.heredocs[-1].body, True
    if prev is not None:
        return _stage_output(prev), True
    return None, False


def _stage_output(prev) -> str | None:
    """Ce qu'un étage écrit, s'il est lisible sans l'exécuter : `echo`, `printf`, `cat`
    d'un heredoc ou d'une chaîne `<<<`. None sinon."""
    argv, units = prev
    if len(units) != 1:
        return None
    u = units[0]
    if not u:
        return None
    if u[0] == "echo":
        args = list(u[1:])
        while args and re.fullmatch(r"-[neE]+", args[0]):
            args = args[1:]
        return " ".join(args)
    if u[0] == "printf":
        args = list(u[1:])
        if args[:1] == ["--"]:
            args = args[1:]
        if not args:
            return ""
        return "\n".join(args[1:]) if "%" in args[0] else args[0].replace("\\n", "\n")
    if u[0] == "cat" and all(a.startswith("-") for a in u[1:]):
        return _stdin_of(argv, None)[0]
    return None


def _static_output(body: str) -> str | None:
    """La sortie d'une substitution `$(…)` qu'on peut lire sans l'exécuter, ou None."""
    try:
        cmds = _simple_commands(body)
        if len(cmds) != 1:
            return None
        argv = cmds[0][0]
        return _stage_output((argv, _normalise(argv, _MAX_DEPTH, _Analysis())))
    except Exception:  # noqa: BLE001 — illisible = inconnu, jamais « sûr »
        return None


def _has_download(text: str, depth: int) -> bool:
    tmp = _Analysis()
    units = _walk_safe(text, depth + 1, tmp)
    return any(u and u[0] in _DOWNLOADERS for u in units) or any(
        e[0] == "download" for e in tmp.events)


def _body_subs(body: str) -> list[str]:
    """Les `$(…)` et `` `…` `` d'un corps de heredoc NON cité : le shell les exécute."""
    out, i, n = [], 0, len(body)
    while i < n:
        c = body[i]
        if c == "\\":
            i += 2
            continue
        if c == "$" and body[i + 1:i + 2] == "(":
            k = _match_paren(body, i + 1)
            if body[i + 2:i + 3] != "(":
                out.append(body[i + 2:k - 1])
            i = k
            continue
        if c == "`":
            k = _end_bq(body, i)
            out.append(body[i + 1:k - 1])
            i = k
            continue
        i += 1
    return out


def _stdin_message(u: list[str]) -> bool:
    """`git commit -F -`, `git tag -F -`, `gh … --body-file -` : le corps est un MESSAGE."""
    g = _git(u)
    if g and g[0] in ("commit", "tag"):
        args = g[1]
    elif u[:1] == ["gh"]:
        args = u[1:]
    else:
        return False
    for i, a in enumerate(args):
        if a in ("--file=-", "--body-file=-", "-F-"):
            return True
        if (a in ("--file", "--body-file") or re.fullmatch(r"-[A-Za-z]*F", a)) \
                and args[i + 1:i + 2] == ["-"]:
            return True
    return False


def _names(f: str, later: list[tuple[_Argv, str]]) -> bool:
    """Le fichier `f` est-il nommé de nouveau plus loin sur la ligne ?"""
    base = f.rsplit("/", 1)[-1]
    for argv, _ in later:
        words = list(argv) + [t for _, t in argv.redirs]
        if any(w == f or w.rsplit("/", 1)[-1] == base or w.endswith("=" + f) for w in words):
            return True
        if any(f in body for body, _ in argv.subs):
            return True
    return False


def _heredocs(argv: _Argv, units: list[_Argv], cmds, k: int, depth: int,
              an: _Analysis) -> list[_Argv]:
    """Décide, pour chaque heredoc de la commande `k`, s'il est DONNÉE ou CODE (msdr R95).

    Donnée seulement si : délimiteur cité, terminé, seul sur sa ligne, lu par `cat`, `tee`
    ou un message (`git commit -F -`), pas tubé dans un shell, et le fichier qu'il écrit
    n'est plus nommé ensuite. Non cité mais sinon inerte : ses `$(…)` s'exécutent et sont
    lus. Dans tous les autres cas le corps est lu comme du shell. Un corps donné à un shell
    ou à un interpréteur est lu par `_feed`, qui en connaît le langage."""
    if not argv.heredocs or any(_reads_code(u) for u in units):
        return []
    out: list[_Argv] = []
    piped_into_code = False
    for j in range(k + 1, len(cmds)):
        if cmds[j][1] not in ("|", "|&"):
            break
        if any(_reads_code(u) for u in _normalise(cmds[j][0], _MAX_DEPTH, _Analysis())):
            piped_into_code = True
    consumer = units[-1] if units else None
    inert = consumer is not None and bool(consumer) and (
        consumer[0] in ("cat", "tee") or _stdin_message(consumer))
    written = [t for op, t in argv.redirs if op in _WRITES]
    if consumer is not None and consumer[:1] == ["tee"]:
        written += [a for a in consumer[1:] if not a.startswith("-")]
    later = cmds[k + 1:]
    named = [f for f in written if _names(f, later)]
    # Écrit, puis lancé par un interpréteur NON shell (`python3 f.py`) : le corps est lu
    # dans SA langue, jamais comme du shell — un commentaire Python qui cite `git clean`
    # n'est pas un `git clean` (rejeu T125). Le fichier nommé par autre chose reste lu
    # comme du shell (msdr R95 : ce garde ne sait pas ce que la suite en fait).
    run_as: dict[str, str] = {}
    for f in named:
        base = f.rsplit("/", 1)[-1]
        for later_argv, _ in later:
            for lu in _normalise(later_argv, _MAX_DEPTH, _Analysis()):
                lang = _file_language(lu, base)
                if lang:
                    run_as[f] = lang
    only_interp = bool(named) and all(
        f in run_as and run_as[f] != "shell" and _names_only_by_interp(f, later)
        for f in named)
    for hd in argv.heredocs:
        inert_shape = hd.terminated and hd.count == 1 and inert and not piped_into_code
        shape = inert_shape and not named
        if shape and hd.quoted:
            continue
        if shape:
            for body in _body_subs(hd.body):
                out += _walk_safe(body, depth + 1, an)
            continue
        if not (inert_shape and hd.quoted and only_interp):
            out += _walk_safe(hd.body, depth + 1, an)
        for f in named:                     # écrit, puis lancé par un interpréteur
            if f in run_as:
                out += _scan_code(run_as[f], hd.body, depth, an)
    return out


def _names_only_by_interp(f: str, later: list[tuple[_Argv, str]]) -> bool:
    """Chaque commande suivante qui nomme `f` le donne à un interpréteur comme son code."""
    base = f.rsplit("/", 1)[-1]
    for later_argv, op in later:
        if not _names(f, [(later_argv, op)]):
            continue
        if not any(_file_language(lu, base)
                   for lu in _normalise(later_argv, _MAX_DEPTH, _Analysis())):
            return False
    return True


# Les outils qui lisent un fichier `.py` comme du Python : `pytest` l'importe (il
# l'exécute), les autres le lisent sans l'exécuter. Aucun ne le donne à un shell.
_PY_FILE_TOOLS = frozenset({"pytest", "py.test", "ruff", "mypy", "black", "flake8", "pylint",
                            "pyflakes", "isort", "py_compile"})


def _file_language(lu: list[str], base: str) -> str | None:
    """La langue dans laquelle la commande `lu` lit le fichier `base`, ou None."""
    ic = _interp_code(lu)
    if ic and ic[2] and ic[2].rsplit("/", 1)[-1] == base:
        return ic[0]
    if not lu or not base.endswith(".py"):
        return None
    head = lu[0]
    if head.startswith("python") and "-m" in lu[:-1]:
        head = lu[lu.index("-m") + 1]
    if head in _PY_FILE_TOOLS and any(a.rsplit("/", 1)[-1] == base for a in lu[1:]):
        return "python"
    return None


_PY_MODULES = frozenset({"os", "subprocess", "shutil", "importlib", "pty", "commands"})
_PY_DANGER_ATTRS = frozenset({"unlink", "rmdir", "rmtree", "system", "popen"})
_PY_RUNNERS = frozenset({"run", "call", "check_call", "check_output", "Popen", "getoutput",
                         "getstatusoutput", "execv", "execvp", "execvpe", "spawnv", "spawnvp"})


def _py_name(node) -> tuple[str | None, str | None]:
    """`(racine, dernier)` du nom appelé : `os.path.join` -> ("os", "join")."""
    last = node.attr if isinstance(node, _ast.Attribute) else (
        node.id if isinstance(node, _ast.Name) else None)
    while isinstance(node, _ast.Attribute):
        node = node.value
    while isinstance(node, _ast.Call):
        node = node.func
        while isinstance(node, _ast.Attribute):
            node = node.value
    return (node.id if isinstance(node, _ast.Name) else None), last


def _py_danger(tree) -> bool:
    """La liste blanche AST : vrai dès qu'un appel touche `os`, `subprocess`, `shutil`,
    `importlib`, une suppression pathlib (`unlink`, `rmdir`), `exec`, `eval`, `__import__`."""
    alias, names = set(_PY_MODULES), set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in _PY_MODULES:
                    alias.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, _ast.ImportFrom) and node.module \
                and node.module.split(".")[0] in _PY_MODULES:
            names.update(a.asname or a.name for a in node.names)
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Call):
            continue
        root, last = _py_name(node.func)
        if isinstance(node.func, _ast.Name):
            if last in ("exec", "eval", "__import__") or last in names:
                return True
        elif root in alias or last in _PY_DANGER_ATTRS:
            return True
    return False


def _py_str(node) -> str | None:
    return node.value if isinstance(node, _ast.Constant) and isinstance(node.value, str) else None


def _py_path(node) -> str | None:
    """Le chemin qu'une expression Python désigne, quand il se lit sans l'exécuter :
    `os.path.expanduser('~')`, `Path.home() / 'x'`, `os.environ['HOME']`…"""
    s = _py_str(node)
    if s is not None:
        return s
    if isinstance(node, _ast.BinOp) and isinstance(node.op, _ast.Div):
        left, right = _py_path(node.left), _py_path(node.right)
        return _os.path.join(left, right) if left is not None and right is not None else None
    if isinstance(node, _ast.Subscript) and _py_str(node.slice) == "HOME":
        return "$HOME"
    if not isinstance(node, _ast.Call):
        return None
    _, last = _py_name(node.func)
    recv = node.func.value if isinstance(node.func, _ast.Attribute) else None
    first = node.args[0] if node.args else None
    if last == "home":
        return "~"
    if last in ("get", "getenv") and first is not None and _py_str(first) == "HOME":
        return "$HOME"
    if last == "join" and node.args:
        parts = [_py_path(a) for a in node.args]
        return _os.path.join(*parts) if None not in parts else None
    if last in ("expanduser", "abspath", "realpath", "normpath", "resolve", "absolute",
                "Path", "PosixPath", "PurePath", "fspath", "str"):
        if first is not None:
            return _py_path(first)
        return _py_path(recv) if recv is not None else ("." if last in ("Path", "PosixPath") else None)
    return None


def _py_units(tree, depth: int, an: _Analysis) -> list[_Argv]:
    """Les argv qu'un code Python lance (`subprocess.run([...])`) et ce qu'il supprime
    (`shutil.rmtree(cible)` lu comme `rm -r cible`)."""
    out: list[_Argv] = []
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Call):
            continue
        _, last = _py_name(node.func)
        if last in _PY_RUNNERS and node.args:
            seq = node.args[0]
            if last.startswith(("execv", "spawnv")) and len(node.args) > 1:
                seq = node.args[1]
            if isinstance(seq, (_ast.List, _ast.Tuple)):
                words = [_py_path(e) or "<?>" for e in seq.elts]
                u = _Argv(words)
                u.wrappers = ("python",)
                out += _normalise(u, depth + 1, an)
        elif last in ("rmtree", "rmdir", "removedirs", "remove", "unlink"):
            target = node.args[0] if node.args else (
                node.func.value if isinstance(node.func, _ast.Attribute) else None)
            path = _py_path(target) if target is not None else None
            u = _Argv(["rm", "-r", path or "<?>"] if last in ("rmtree", "rmdir", "removedirs")
                      else ["rm", path or "<?>"])
            u.wrappers = ("python",)
            out.append(u)
    return out


_PY_SHELL_SINKS = frozenset({"system", "popen", "getoutput", "getstatusoutput"})


def _py_shell_strings(tree, code: str, an: _Analysis) -> list[str]:
    """Les chaînes qu'un code Python donne à un SHELL (`os.system`, `os.popen`,
    `subprocess.run("…", shell=True)`) — elles seules sont lues comme du shell.

    Une chaîne qui n'atteint aucun shell est une donnée : `NEW = ["Bash(git push
    --force:*)"]` dans un script qui importe `os` n'est pas un push (rejeu T125 : 17 lignes
    réelles bloquées ainsi). Ce que le garde ne lit pas — un argument calculé donné à un
    shell, `exec`, `eval`, `__import__`, `importlib` — fait balayer TOUT le texte par les
    règles brutes (`an.raw`) : fermé, jamais « sûr »."""
    out: list[str] = []
    sweep = False
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Call):
            continue
        root, last = _py_name(node.func)
        if last in ("exec", "eval", "__import__") or root == "importlib" or last == "import_module":
            sweep = True
            continue
        shell = last in _PY_SHELL_SINKS or (last in _PY_RUNNERS and any(
            k.arg == "shell" and not (isinstance(k.value, _ast.Constant) and not k.value.value)
            for k in node.keywords))
        if not shell or not node.args:
            continue
        first = node.args[0]
        s = _py_str(first)
        if s is not None:
            out.append(s)
        elif isinstance(first, _ast.JoinedStr) and all(
                _py_str(v) is not None for v in first.values):
            out.append("".join(_py_str(v) for v in first.values))
        else:
            sweep = True                    # un shell reçoit ce que ce garde ne calcule pas
    if sweep:
        an.raw.append(code)
    return out


_STRING_LITERAL = re.compile(r"""'((?:\\.|[^'\\])*)'|"((?:\\.|[^"\\])*)"|`([^`]*)`""")


def _scan_code(lang: str, code: str, depth: int, an: _Analysis) -> list[_Argv]:
    """Le code d'un interpréteur. Python qui n'appelle rien de dangereux (liste blanche AST)
    passe ; tout le reste est balayé AU TEXTE avec les anciennes règles (`an.raw`), et
    chaque chaîne littérale est jugée comme du shell. Illisible = balayé, jamais « sûr »."""
    if lang == "python":
        try:
            with _warnings.catch_warnings():     # `"\$"` in the code: not the hook's stderr
                _warnings.simplefilter("ignore")
                tree = _ast.parse(code)
        except (SyntaxError, ValueError):
            an.raw.append(code)
            return []
        if not _py_danger(tree):
            return []
        out: list[_Argv] = []
        for s in _py_shell_strings(tree, code, an):
            out += _walk_safe(s, depth + 1, an)
        return out + _py_units(tree, depth, an)
    an.raw.append(code)
    out = []
    for m in _STRING_LITERAL.finditer(code):
        s = m.group(1) or m.group(2) or m.group(3) or ""
        if s.strip():
            out += _walk_safe(s, depth + 1, an)
    return out


def _feed(u: _Argv, argv: _Argv, prev, download: bool, depth: int,
          an: _Analysis) -> list[_Argv]:
    """Ce que reçoit l'entrée standard de `u`, et ce qu'il exécute de ce qu'il reçoit."""
    extra: list[_Argv] = []
    text, present = _stdin_of(argv, prev)
    if u.xrep is not None and u.stdin is None:
        if text is not None:
            u.stdin = text
            if u.xrep:
                items = [x.strip() for x in text.split("\n") if x.strip()]
                base = list(u)
                if items:
                    u[:] = [w.replace(u.xrep, items[0]) for w in base]
                    for it in items[1:]:
                        extra.append(u.clone([w.replace(u.xrep, it) for w in base]))
            else:
                u.extend(text.split())
        else:
            u.stdin = _UNREAD
            if u and _xargs_blind(u, prev):
                an.events.append(("xargs-blind", u[0]))
            elif u and (u[0] in _DESTRUCTIVE or u[0].startswith("mkfs")) and (
                    u[0] not in _OVERWRITERS or _xargs_kills(u)
                    or _overwrites(list(u) + ["\x00xargs"])):
                an.gaps.append(f"`xargs {u[0]}` reçoit une entrée que ce garde ne lit pas : "
                               "ses cibles sont inconnues (trou déclaré, guard_scope T125). "
                               "Vérifier la liste avant de lancer.")
    if u.scanned or not u:
        return extra
    u.scanned = True
    head = u[0]
    script = _shell_script(u)
    if script is not None:
        extra += _read_script(script, head in ("source", "."), depth, an)
    reads = _reads_stdin_shell(u)
    ic = None if reads else _interp_code(u)
    if reads or (ic is not None and ic[1] is _STDIN):
        if download and prev is not None:
            an.events.append(("download", head))
        elif text is not None:
            extra += _walk_safe(text, depth + 1, an) if reads else _scan_code(ic[0], text, depth, an)
        elif present:
            an.gaps.append(f"`{head}` exécute une entrée que ce garde ne lit pas "
                           "(trou déclaré, guard_scope T125).")
    elif ic is not None and isinstance(ic[1], str):
        extra += _scan_code(ic[0], ic[1], depth, an)
    if reads or head in _SHELLS or head in ("source", ".") or ic is not None:
        for w in u[1:]:
            if w.startswith("<(") and w.endswith(")") and _has_download(w[2:-1], depth):
                an.events.append(("download", head))
    body = None
    if head.startswith("$(") and head.endswith(")"):
        body = head[2:-1]
    elif head.startswith("`") and head.endswith("`") and len(head) > 1:
        body = head[1:-1]
    if body is not None:
        if _has_download(body, depth):
            an.events.append(("download", "$(…)"))
        else:
            out = _static_output(body)
            if out is not None:
                extra += _walk_safe(out + " " + shlex.join(u[1:]), depth + 1, an)
            else:
                an.gaps.append("la ligne exécute la SORTIE d'une substitution que ce garde ne "
                               "lit pas (trou déclaré, guard_scope T125).")
    return extra


# ── Les variables : UN point de développement, à la production des argv (T150b) ─────
#
# Chaque `$X` d'un mot est remplacé par la valeur que la ligne lui donne À CET ENDROIT, cité
# ou non (un faux positif plutôt qu'un trou : `T=~; rm -rf '$T'` bloque), puis coupé aux
# blancs si le mot n'en contenait pas. Une affectation dans une boucle ou une condition, et
# la liste d'un `for`, s'AJOUTENT aux valeurs possibles ; ailleurs elles les remplacent. Au
# plus `_MAX_ALTS` lectures d'une commande : au-delà, trou déclaré.
_MAX_ALTS = 16
_DECLARERS = frozenset({"export", "declare", "local", "readonly", "typeset"})
_OPENERS = frozenset({"if", "while", "until", "case", "select"})
_CLOSERS = frozenset({"fi", "done", "esac"})


def _word_alts(word: str, an: _Analysis, split: bool = True) -> list[list[str]]:
    """Les lectures possibles d'un mot, chacune une liste de mots (coupée aux blancs)."""
    outs = [word]
    if "$" in word:
        for m in reversed(list(_VAR_ANY.finditer(word))):
            vals = an.vars.get(m.group(1) or m.group(4))
            if vals is None and m.group(2) is not None and m.group(3):
                # `${PY:-python3}` : la valeur par défaut. Un défaut VIDE (`${2:-}`) ne dit
                # rien de la valeur : `OUT=${2:-}` lu comme "" ferait de `$OUT/x` un `/x`.
                vals = [m.group(3)]
            if vals is None:
                continue
            outs = [o[:m.start()] + v + o[m.end():] for o in outs for v in vals]
            if len(outs) > _MAX_ALTS:
                outs = outs[:_MAX_ALTS + 1]
                break
    res = []
    for o in outs:
        st = re.fullmatch(r"\$\((.*)\)(.*)", o, re.S)
        if st and not o.startswith("$(("):
            static = _static_output(st.group(1))
            if static is not None:
                o = static.strip() + st.group(2)
        # Coupé aux blancs comme le shell, sauf un mot cité (il contenait déjà un blanc) et
        # une valeur qui reste une substitution non lue : `$(cd "$(dirname …)" && pwd)`
        # coupé en morceaux ferait de `$(cd` un nom de script.
        cut = split and not re.search(r"\s", word) and "$(" not in o and "`" not in o
        res.append(o.split() if cut else [o])
    return res


def _assign(name: str, values: list[str], an: _Analysis) -> None:
    if an.cond > 0 and name in an.vars:
        old = an.vars[name]
        an.vars[name] = (old + [v for v in values if v not in old])[:_MAX_ALTS]
    else:
        an.vars[name] = values[:_MAX_ALTS]


def _assigned(word: str, an: _Analysis) -> None:
    m = _NAME_EQ.match(word)
    vals = [" ".join(a) for a in _word_alts(word[m.end():], an, split=False)]
    _assign(m.group(0).rstrip("+="), vals, an)


def _expand_command(argv: _Argv, an: _Analysis) -> list[_Argv]:
    """Les lectures d'une commande simple, ses affectations prises en compte À LEUR PLACE
    (`T=~; rm -rf $T; T=/tmp/x` lit `~`)."""
    words = list(argv)
    i = 0
    while i < len(words):
        w = words[i]
        if w in _OPENERS:
            an.cond += 1
        elif w in _CLOSERS:
            an.cond = max(0, an.cond - 1)
        elif w in _RESERVED:
            pass
        elif _NAME_EQ.match(w):
            _assigned(w, an)
        else:
            break
        i += 1
    head = words[i] if i < len(words) else None
    if head in ("for", "select") and i + 2 < len(words) and words[i + 2] == "in":
        vals = [x for w in words[i + 3:] for alt in _word_alts(w, an) for x in alt]
        _assign(words[i + 1], vals or [""], an)
        an.cond += 1                        # le `done` qui suit la referme
        return [argv]
    if head in _DECLARERS:
        for w in words[i + 1:]:
            if _NAME_EQ.match(w):
                _assigned(w, an)
    if not an.vars and not any("$(" in w for w in words):
        return [argv]
    alts: list[list[str]] = [[]]
    over = False
    for w in words:
        wa = _word_alts(w, an)
        alts = [a + b for a in alts for b in wa]
        if len(alts) > _MAX_ALTS:
            alts, over = alts[:_MAX_ALTS], True
    redirs: list[list[tuple[str, str]]] = [[]]
    for op, t in argv.redirs:
        ta = [x[0] for x in _word_alts(t, an, split=False)] if op != "<<<" else [t]
        redirs = [r + [(op, x)] for r in redirs for x in ta]
        if len(redirs) > _MAX_ALTS:
            redirs, over = redirs[:_MAX_ALTS], True
    if over or len(alts) * len(redirs) > _MAX_ALTS:
        an.gaps.append(f"plus de {_MAX_ALTS} lectures possibles de ses variables : ce garde "
                       f"n'en juge que {_MAX_ALTS} (trou déclaré, guard_scope T150b).")
    out: list[_Argv] = []
    for a in alts:
        for r in redirs:
            n = argv.clone(a)
            n.redirs = r
            out.append(n)
            if len(out) >= _MAX_ALTS:
                return out
    return out


# ── xargs aveugle, et les scripts shell lus sur le disque (T150b) ──────────────────
#
# Un `xargs` destructeur dont l'entrée vient d'un fichier (`-a`, `<`), de rien, ou d'un
# producteur inconnu BLOQUE ; derrière un `find`/`ls` relatif il reste un avertissement
# (l'idiome `find . -name __pycache__ | xargs rm -rf`), sauf s'il part d'une racine.
_LISTERS = frozenset({"find", "ls", "fd", "fdfind", "git", "grep", "rg"})


def _xargs_kills(u: list[str]) -> bool:
    """Dérivé de `_OVERWRITERS` (T167) : `rm -r`, `shred`, `truncate`, `dd`, et `mkfs`."""
    entry = _OVERWRITERS.get(u[0])
    return bool(entry and entry[1](u)) or u[0].startswith("mkfs")


def _xargs_blind(u: _Argv, prev) -> bool:
    if not _xargs_kills(u):
        return False
    up = u.upstream if u.upstream is not None else (prev[1][-1] if prev and prev[1] else None)
    if up is None or not up:
        return True                         # `-a liste`, `< liste`, ou rien
    if up[0] not in _LISTERS:
        return True                         # un producteur que ce garde ne lit pas
    return any(_root_level(a) for a in up[1:] if not a.startswith("-"))


_SHEBANG_SHELL = re.compile(r"^#!\s*\S*?(?:/|^)(?:env\s+(?:-\S+\s+)*)?(?:sh|bash|zsh|dash|ksh)\b")
_SCRIPT_MAX = 256 * 1024


def _shell_script(u: _Argv) -> str | None:
    """Le chemin du script SHELL que `u` exécute : `source F`, `. F`, `bash F`, `./F`."""
    head = u[0]
    if head in ("source", ".") and len(u) > 1:
        return u[1]
    if head in _SHELLS:
        if _reads_stdin_shell(u):
            return None
        j = 1
        while j < len(u) and u[j][:1] in "-+" and u[j] not in ("-", "--", "+"):
            # `bash -n F` ne fait que vérifier la syntaxe : rien de F ne s'exécute.
            if (u[j][:1] == "-" and u[j][1:2] != "-" and "n" in u[j][1:]) or u[j] == "--noexec" \
                    or (u[j] == "-o" and j + 1 < len(u) and u[j + 1] == "noexec"):
                return None
            j += 2 if u[j] in ("-o", "+o", "-O", "+O", "--rcfile", "--init-file") else 1
        if j < len(u) and u[j] == "--":
            j += 1
        return u[j] if j < len(u) else None
    exe = getattr(u, "exe", None)
    if exe and "/" in exe and "$" not in exe and "`" not in exe:
        return "\x00exe:" + exe
    return None


def _read_script(path: str, sourced: bool, depth: int, an: _Analysis) -> list[_Argv]:
    """Le texte d'un script shell, lu comme la ligne qui le lance. Un fichier absent ou
    illisible est un trou ; un exécutable dont le shebang n'est pas un shell n'est pas lu
    (les scripts python/node : guard_scope T150b, non couvert)."""
    exe = path.startswith("\x00exe:")
    if exe:
        path = path[len("\x00exe:"):]
    full = _os.path.join(an.cwd or _os.getcwd(), _os.path.expanduser(path))
    try:
        st = _os.stat(full)
        if not _stat.S_ISREG(st.st_mode):
            raise OSError("not a file")
        if st.st_size > _SCRIPT_MAX:
            raise OSError("too large")
        if exe and not _os.access(full, _os.X_OK):
            return []                       # `./f` sans le droit x ne s'exécute pas
        with open(full, "rb") as f:
            data = f.read(_SCRIPT_MAX + 1)
    except OSError:
        if not exe:
            an.gaps.append(f"le script `{path}` n'a pas pu être lu : ce qu'il exécute est "
                           "inconnu (trou déclaré, guard_scope T150b).")
        return []
    an.files.append((full, st.st_mtime_ns, st.st_size))
    if b"\0" in data:
        if not exe:
            an.gaps.append(f"`{path}` n'est pas un texte : non lu (trou déclaré, T150b).")
        return []
    text = data.decode("utf-8", "replace")
    if exe and text.startswith("#!") and not _SHEBANG_SHELL.match(text.split("\n", 1)[0]):
        return []
    if sourced:
        return _walk_safe(text, depth + 1, an)
    saved, cond = {k: list(v) for k, v in an.vars.items()}, an.cond
    an.cond = 0
    try:
        return _walk_safe(text, depth + 1, an)
    finally:
        an.vars, an.cond = saved, cond


_FORK_RE = re.compile(r":\s*\(\s*\)\s*\{[^}]*\|[^}]*&[^}]*\}\s*;?\s*:")
_QUOTED_SPAN = re.compile(r"""'[^']*'|"(?:\\.|[^"\\])*\"""")


# ── Le dossier de chaque commande : les `cd` de la ligne (T167) ────────────────────
#
# `cd ~ && rm -rf .` était jugé dans le dossier du hook. Chaque commande porte les dossiers
# où elle PEUT tourner : après `cd X &&` le nouveau, après `;` l'ancien ET le nouveau, après
# `||` l'ancien seul ; un sous-shell `( … )` rend l'ancien en sortant. Un `cd` vers ce que la
# ligne ne dit pas (`cd $D`, `cd -`, `popd`) garde l'ancien, marqué incertain : trou déclaré.
_MAX_DIRS = 8
_CD_VALUED = frozenset()


def _cd_target(u: list[str]) -> tuple[bool, str | None]:
    """`(est un changement de dossier, cible)` ; cible None : inconnue de la ligne."""
    if not u or u[0] not in ("cd", "pushd", "popd"):
        return False, None
    if u[0] == "popd":
        return True, None
    _opts, pos = _opts_pos(u, _CD_VALUED)
    if not pos:
        return True, ("~" if u[0] == "cd" else None)
    if pos[0] == "-" or pos[0].startswith("+") or pos[0].startswith("-"):
        return True, None
    return True, pos[0]


def _dedupe(states: list) -> list:
    seen, out = set(), []
    for s in states:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out[:_MAX_DIRS * 2]


def _walk(text: str, depth: int, an: _Analysis) -> list[_Argv]:
    """Tout ce que `text` exécute, imbriqué compris. Lève si le texte est illisible : c'est
    `check_command` qui ferme alors la porte (`_raw_verdict`)."""
    if depth > _MAX_DEPTH:
        an.raw.append(text)
        return []
    saved_dirs = an.dirs
    try:
        return _walk_in(text, depth, an)
    finally:
        an.dirs = saved_dirs


def _walk_in(text: str, depth: int, an: _Analysis) -> list[_Argv]:
    an.texts.append(text)
    if _FORK_RE.search(_QUOTED_SPAN.sub("''", _sans_heredocs(text))):
        an.events.append(("fork", text))
    cmds = _simple_commands(text)
    out: list[_Argv] = []
    prev = None
    download = False
    start = an.dirs or ((an.cwd or _os.getcwd(), False),)
    # (dossier, incertain, la dernière commande a-t-elle réussi)
    states: list[tuple[str, bool, bool]] = [(d, unc, True) for d, unc in start]
    gstack: list[list[tuple[str, bool, bool]]] = []
    groups: tuple[int, ...] = ()
    dirs = start
    for k, (argv, link) in enumerate(cmds):
        g = getattr(argv, "groups", ())
        while groups and g[:len(groups)] != groups:
            outer = gstack.pop()            # sortie d'un sous-shell : ses `cd` s'y arrêtent
            states = _dedupe([(d, unc, ok) for d, unc, _ in outer for ok in (True, False)])
            groups = groups[:-1]
        while len(g) > len(groups):
            gstack.append(states)
            groups = g[:len(groups) + 1]
        piped = link in ("|", "|&")
        if piped:
            ran = []                        # un étage de tube : même dossier, sous-shell
        else:
            want = {"&&": (True,), "||": (False,)}.get(link, (True, False))
            ran = [s for s in states if s[2] in want] or states
            dirs = tuple(_dedupe([(d, unc) for d, unc, _ in ran]))
        argv.dirs = dirs
        an.dirs = dirs
        if link not in ("|", "|&"):
            prev, download = None, False
        alts = _expand_command(argv, an)
        an.raw_cmds.extend(alts)
        if an.remote:
            an.remote_raw.update(id(a) for a in alts)
        units = [u for alt in alts for u in _normalise(alt, depth, an)]
        for u in units:
            if u.upstream is None and prev is not None and prev[1]:
                u.upstream = prev[1][-1]
        extra: list[_Argv] = []
        for u in list(units):
            extra += _feed(u, argv, prev, download, depth, an)
        for body, _kind in argv.subs:
            extra += _walk_safe(body, depth + 1, an)
        extra += _heredocs(argv, units, cmds, k, depth, an)
        for op, target in argv.redirs:
            if op == "<<<" and not any(_reads_code(u) for u in units):
                # Le texte d'une chaîne `<<<` reste lu comme une ligne (T125 : `cat <<<'…'`
                # bloque) ; mais une chaîne qui n'est qu'une référence `$J` n'a pas de texte à
                # elle : lue nue, `read a <<< "$J"` (J=$(curl …)) « exécutait » la sortie de
                # curl. Derrière `echo`, seules ses substitutions tournent (rejeu T150b).
                bare = _VAR_REF.fullmatch(target) is not None
                extra += _walk_safe(("echo " if bare else "") + target, depth + 1, an)
        if k < len(cmds) - 1:
            for u in units + extra:
                u.follows = True
        for u in units + extra:
            if u.dirs is None:
                u.dirs = dirs
        if any(unc for _d, unc in dirs) and any(
                not t.startswith(("/", "~", "$")) for t in
                [t for u in units for t in _overwrites(u)]
                + [t for c in alts for t in _redir_targets(c)]):
            an.gaps.append("un `cd` de la ligne va vers un dossier qu'elle ne dit pas (`cd $D`, "
                           "`cd -`) : la cible relative qui suit est jugée dans l'ancien "
                           "(trou déclaré, guard_scope T167).")
        if not piped:
            nxt = cmds[k + 1][1] if k + 1 < len(cmds) else ""
            cd = None
            if alts and nxt not in ("|", "|&", "&"):  # `cd x | …`, `cd x &` : un sous-shell
                w = list(alts[0])
                i = 0
                while i < len(w) and (w[i] in _RESERVED or _NAME_EQ.match(w[i])):
                    i += 1
                is_cd, target = _cd_target(w[i:])
                cd = (target,) if is_cd else None
            ran_set = set(ran)
            new: list[tuple[str, bool, bool]] = []
            for d, unc, _ok in ran:
                if cd is not None:
                    nd = _abspath(cd[0], d) if cd[0] is not None else None
                    new.append((nd, unc, True) if nd is not None else (d, True, True))
                    new.append((d, unc, False))
                else:
                    new += [(d, unc, True), (d, unc, False)]
            states = _dedupe(new + [s for s in states if s not in ran_set])
        out += units + extra
        if any(u and u[0] in _DOWNLOADERS for u in units):
            download = True
        prev = (argv, units)
    return out


def _walk_safe(text: str, depth: int, an: _Analysis) -> list[_Argv]:
    """`_walk` d'un texte IMBRIQUÉ : illisible, il est balayé au texte (`an.raw`)."""
    try:
        return _walk(text, depth, an)
    except Exception:  # noqa: BLE001 — fermé : le texte passe aux anciennes règles
        an.raw.append(text)
        return []


@_functools.lru_cache(maxsize=64)
def _commands_cached(command: str, cwd: str | None = None) -> _Analysis:
    """L'analyse d'une ligne, dans son dossier. LÈVE sur une entrée illisible — l'ancienne
    version rendait `()`, et chaque garde structurel concluait « rien à voir » : fermé
    devenu ouvert."""
    an = _Analysis(cwd)
    an.units = _walk(command, 0, an)
    return an


def _files_unchanged(an: _Analysis) -> bool:
    try:
        return all((st := _os.stat(f)).st_mtime_ns == m and st.st_size == n
                   for f, m, n in an.files)
    except OSError:
        return False


def _analyse(command: str, cwd: str | None = None) -> _Analysis:
    """Clé (commande, dossier) ; une analyse qui a LU un script n'est resservie que si ce
    script n'a pas changé (chemin, mtime, taille) — sinon elle est refaite."""
    cwd = cwd or _CWD or _os.getcwd()
    an = _commands_cached(command, cwd)
    if an.files and not _files_unchanged(an):
        _commands_cached.cache_clear()
        an = _commands_cached(command, cwd)
    return an


def _commands_list(command: str, depth: int = 0) -> list[_Argv]:
    return [u.clone() for u in _analyse(command).units]


def _commands(cmd: str) -> list[_Argv]:
    """Les argv que cette ligne de shell exécute, normalisés (voir l'en-tête de section)."""
    return _commands_list(cmd, 0)


def _git(argv: list[str]) -> tuple[str, list[str], list[str]] | None:
    """`(sous-commande, arguments, dossiers -C)` d'un argv normalisé dont la tête est git."""
    if not argv or argv[0] != "git":
        return None
    i, cdirs = 1, []
    while i < len(argv) and argv[i].startswith("-"):
        if argv[i] in _GIT_VALUED:
            if argv[i] == "-C" and i + 1 < len(argv):
                cdirs.append(argv[i + 1])
            i += 2
        else:
            i += 1          # --no-pager, -P, --bare, --git-dir=x, --literal-pathspecs…
    if i >= len(argv):
        return None
    return argv[i], argv[i + 1:], cdirs


def _long(a: str) -> str:
    return a[2:].split("=", 1)[0]


def _force_push(args: list[str]) -> bool:
    """`--force`, `-f` (même dans un groupe), `--force-with-lease`, `--force-if-includes`,
    leurs abréviations, ou une refspec `+<réf>`."""
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--") and a != "--":
            name = _long(a)
            if name.startswith("forc"):
                return True
            if name in ("repo", "receive-pack", "exec", "push-option") and "=" not in a:
                i += 2
                continue
        elif a.startswith("-") and len(a) > 1 and a != "--":
            skip = False
            for k, ch in enumerate(a[1:], start=1):
                if ch == "f":
                    return True
                if ch == "o":
                    skip = k == len(a) - 1
                    break
            if skip:
                i += 2
                continue
        elif a.startswith("+") and len(a) > 1:
            return True
        i += 1
    return False


def _push_no_verify(args: list[str]) -> bool:
    """`--no-verify` (ou une abréviation non ambiguë). Pour push, `-n` est `--dry-run`."""
    return any(a.startswith("--") and _long(a).startswith("no-veri") for a in args)


_COMMIT_VALUED_LONG = frozenset({"message", "file", "author", "date", "reuse-message",
                                 "reedit-message", "fixup", "squash", "cleanup", "template",
                                 "trailer", "pathspec-from-file"})


def _commit_no_verify(args: list[str]) -> bool:
    """`--no-verify`, ou `-n` dans un groupe court AVANT toute option à valeur."""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            return False
        if a.startswith("--"):
            name = _long(a)
            if name.startswith("no-veri"):
                return True
            if name in _COMMIT_VALUED_LONG and "=" not in a:
                i += 2
                continue
        elif a.startswith("-") and len(a) > 1:
            skip = False
            for k, ch in enumerate(a[1:], start=1):
                if ch == "n":
                    return True
                if ch in "mFCct":           # la valeur est le reste du groupe, ou le mot suivant
                    skip = k == len(a) - 1
                    break
                if ch in "uS":              # valeur optionnelle, collée seulement
                    break
            if skip:
                i += 2
                continue
        i += 1
    return False


def _reset_hard(args: list[str]) -> bool:
    for a in args:
        if a == "--":
            return False
        if a.startswith("--") and _long(a) in ("ha", "har", "hard"):
            return True
    return False


_WHOLE_TREE = frozenset({".", "./", ":/", ":/."})


def _checkout_paths(args: list[str]) -> list[str]:
    """Les chemins qu'un `git checkout` rétablirait (tree-ish de tête écarté)."""
    if "--" in args:
        return args[args.index("--") + 1:]
    pos, i = [], 0
    while i < len(args):
        a = args[i]
        if a in ("-b", "-B", "--orphan"):
            i += 2
            continue
        if not a.startswith("-"):
            pos.append(a)
        i += 1
    return pos[1:] if len(pos) > 1 else pos


def _restore_parse(args: list[str]) -> tuple[bool, list[str]]:
    """`(touche l'arbre de travail, chemins)` d'un `git restore`.

    Seul `--staged` SANS `--worktree` épargne l'arbre ; `--source` ne l'épargne PAS (il
    l'écrase depuis une autre révision) — l'ancien garde l'exemptait."""
    staged = worktree = after = False
    paths: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if after or not a.startswith("-") or a == "-":
            paths.append(a)
        elif a == "--":
            after = True
        elif a.startswith("--"):
            name = _long(a)
            if name == "staged":
                staged = True
            elif name == "worktree":
                worktree = True
            elif name in ("source", "pathspec-from-file", "conflict") and "=" not in a:
                i += 1
        else:
            for k, ch in enumerate(a[1:], start=1):
                if ch == "S":
                    staged = True
                elif ch == "W":
                    worktree = True
                elif ch == "s":
                    if k == len(a) - 1:
                        i += 1
                    break
        i += 1
    return (not staged or worktree), paths


def _restore_all(args: list[str]) -> bool:
    touches, paths = _restore_parse(args)
    return touches and any(p in _WHOLE_TREE for p in paths)


def _clean_forced(args: list[str]) -> bool:
    """`git clean` avec `-f`/`--force` et sans `-n`/`--dry-run` (groupes courts lus)."""
    force = dry = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            break
        if a.startswith("--"):
            name = _long(a)
            force |= name == "force"
            dry |= name == "dry-run"
            if name == "exclude" and "=" not in a:
                i += 1
        elif a.startswith("-") and len(a) > 1:
            for k, ch in enumerate(a[1:], start=1):
                if ch == "f":
                    force = True
                elif ch == "n":
                    dry = True
                elif ch == "e":
                    if k == len(a) - 1:
                        i += 1
                    break
        i += 1
    return force and not dry


_DOCKER_VALUED = frozenset({"-c", "--context", "--config", "-H", "--host", "-l", "--log-level",
                            "--tlscacert", "--tlscert", "--tlskey"})


def _docker_words(argv: list[str]) -> list[str]:
    if not argv or argv[0] != "docker":
        return []
    i = 1
    while i < len(argv) and argv[i].startswith("-"):
        i += 2 if argv[i] in _DOCKER_VALUED else 1
    return argv[i:]


def _rm_recursive_forced(argv: list[str]) -> bool:
    if not argv or argv[0] != "rm":
        return False
    rec = force = False
    for a in argv[1:]:
        if a == "--":
            break
        if a.startswith("--"):
            rec |= a == "--recursive"
            force |= a == "--force"
        elif a.startswith("-"):
            rec |= "r" in a or "R" in a
            force |= "f" in a
    return rec and force


def _git_is(sub: str, pred):
    def fires(argv: list[str]) -> bool:
        g = _git(argv)
        return g is not None and g[0] == sub and pred(g[1])
    return fires


# Le motif de la table -> sa lecture structurelle. Un motif absent d'ici retombe sur
# « les premiers mots de l'argv NORMALISÉ sont ceux du motif ».
_STRUCTURAL = {
    "git push --force": _git_is("push", _force_push),
    "git push -f ": _git_is("push", _force_push),
    "git reset --hard": _git_is("reset", _reset_hard),
    "git checkout -- .": _git_is("checkout", lambda a: "--" in a and any(
        p in _WHOLE_TREE for p in a[a.index("--") + 1:])),
    "git restore .": _git_is("restore", _restore_all),
    "git clean -f": _git_is("clean", _clean_forced),
    "docker system prune": lambda argv: _docker_words(argv)[:2] == ["system", "prune"],
    "git commit --no-verify": _git_is("commit", _commit_no_verify),
    "git commit -n ": _git_is("commit", _commit_no_verify),
    "git push --no-verify": _git_is("push", _push_no_verify),
    "git stash drop": _git_is("stash", lambda a: a[:1] == ["drop"]),
    "docker volume rm": lambda argv: _docker_words(argv)[:2] == ["volume", "rm"],
    "rm -rf": _rm_recursive_forced,
}


def _first_words(argv: list[str], pattern: str) -> bool:
    besoin = pattern.lower().split()
    return bool(besoin) and [a.lower() for a in argv[:len(besoin)]] == besoin


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    # Fermé, même si le repli lève : une exception ici sortait en 1, que Claude Code lit
    # comme « pas de décision » — la commande partait (2026-10-19, T125).
    try:
        result = check_command(command, data.get("cwd"))
    except Exception:  # noqa: BLE001
        try:
            result = _raw_verdict(command)
        except Exception:  # noqa: BLE001
            result = ("block", "guard_destructive n'a pas pu juger cette commande.")
    if result is None:
        sys.exit(0)

    level, message = result

    if level == "block":
        # stderr, PAS stdout : le contrat PreToolUse remonte stderr. Ecrit sur stdout,
        # ce bloc etait avale — l'outil rapportait « No stderr output » et l'appelant
        # voyait une porte fermee SANS raison. Meme defaut, meme correctif que
        # `pre_commit_scan.py` le 2026-09-16.
        print(
            f"🚫 BLOCKED — Destructive command detected:\n"
            f"   Command : {command[:120]}\n"
            f"   Reason  : {message}\n"
            f"   Action  : Explain the intent and request explicit user confirmation before retrying.",
            file=sys.stderr,
        )
        sys.exit(2)
    else:
        print(
            f"⚠️  WARNING — Risky command:\n"
            f"   Command : {command[:120]}\n"
            f"   Reason  : {message}\n"
            f"   Proceeding — verify this is intentional."
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
