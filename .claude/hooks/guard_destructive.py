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
    # ── MSDR-specific blocks ────────────────────────────────────────────────
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
    # ── MSDR-specific warnings ──────────────────────────────────────────────
    ("initialize_db",       "Re-running initialize_db triggers alembic upgrade head — verify revision chain is forward-only"),
    ("alembic downgrade",   "Alembic downgrade — reversible but can strip columns; prefer a new revision"),
    ("/admin/purge",        "Admin purge endpoint called — irreversible BLOB deletion"),
]


# ── Detection ─────────────────────────────────────────────────────────────────

def check_command(cmd: str) -> tuple[str, str] | None:
    """
    Returns (level, message) if the command matches a dangerous pattern.
    level is 'block' or 'warn'. Returns None if safe.
    """
    cmd_lower = cmd.lower()
    # Regex tier first: it expresses the dangerous shapes the literal tier cannot.
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
