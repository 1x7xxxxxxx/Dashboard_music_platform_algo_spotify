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
---
"""
import json
import re
import shlex
import subprocess
import sys


# ── Patterns ──────────────────────────────────────────────────────────────────

# Blocking: exit 2 — Claude must explain and get explicit confirmation
_BLOCK_PATTERNS: list[tuple[str, str]] = [
    ("git push --force",        "Force push overwrites remote history — use 'git push' instead"),
    ("git push -f ",            "Force push overwrites remote history — use 'git push' instead"),
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
    (r"\brm\s+-[a-z]*[rf][a-z]*\s+(/|~|\$HOME)(\s|/|$)",
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
    (r"\brm\s+(-\S+\s+)*/(etc|usr|bin|sbin|lib|lib64|boot|dev|proc|sys|root"
     r"|home|srv|opt)(/|\s|$)",
     "Recursive delete of a system path — catastrophic"),
    (r"\brm\s+(-\S+\s+)*/var/(?!tmp)",
     "Recursive delete under /var — catastrophic"),
    (r"\bmkfs\.",
     "Filesystem creation destroys every byte on the target device"),
    (r"\bdd\b[^\n]*\bof=/dev/",
     "Block-device write destroys the existing filesystem"),
    (r"\bchmod\s+(-[a-zA-Z]+\s+)*777\b",
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

_RESTORE_RE = re.compile(
    r"\bgit\s+(?:-C\s+\S+\s+)*"
    r"(?:checkout(?:\s+(?:HEAD|@|[0-9a-f]{7,40}))?\s+--\s+|restore\s+)"
    r"(?P<paths>.+)")


def _paths_that_would_lose_work(command: str) -> list[str]:
    """Les chemins visés par un rétablissement git qui portent du travail non commité.

    Rend une liste vide dès que la question ne se pose pas : pas de correspondance, pas
    de dépôt git, chemin propre. Ne lève JAMAIS — ce hook s'exécute avant chaque appel
    Bash, et une exception ici bloquerait tout le travail au lieu d'un seul geste.
    """
    try:
        losses: list[str] = []
        # Une commande composée porte souvent le geste dans un seul de ses segments.
        for segment in re.split(r"&&|\|\||;|\n", command):
            m = _RESTORE_RE.search(segment)
            if not m:
                continue
            raw = m.group("paths")
            # `--staged` et `--source` ne touchent pas l'arbre de travail.
            if "--staged" in raw or "--source" in raw:
                continue
            try:
                paths = [a for a in shlex.split(raw) if not a.startswith("-")]
            except ValueError:
                paths = raw.split()
            for path in paths:
                out = subprocess.run(
                    ["git", "status", "--porcelain", "--", path],
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


# ── Detection ─────────────────────────────────────────────────────────────────

def check_command(cmd: str) -> tuple[str, str] | None:
    """
    Returns (level, message) if the command matches a dangerous pattern.
    level is 'block' or 'warn'. Returns None if safe.
    """
    cmd_lower = cmd.lower()
    # D'abord le garde à ÉTAT. Il ne bloque que si du travail serait réellement perdu,
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
    # Regex tier next: it expresses the dangerous shapes the literal tier cannot.
    for pattern, message in _BLOCK_REGEX:
        if re.search(pattern, cmd, re.IGNORECASE):
            return ("block", message)
    for pattern, message in _BLOCK_PATTERNS:
        if pattern.lower() in cmd_lower:
            return ("block", message)
    for pattern, message in _WARN_PATTERNS:
        if pattern.lower() in cmd_lower:
            return ("warn", message)
    return None


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

    result = check_command(command)
    if result is None:
        sys.exit(0)

    level, message = result

    if level == "block":
        print(
            f"🚫 BLOCKED — Destructive command detected:\n"
            f"   Command : {command[:120]}\n"
            f"   Reason  : {message}\n"
            f"   Action  : Explain the intent and request explicit user confirmation before retrying."
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
