#!/usr/bin/env python3
"""
Hook PostToolUse — Vérification syntaxique et qualité Python.

Déclenché après chaque Write ou Edit sur un fichier .py.
Utilise ruff si disponible (lint + syntaxe), sinon py_compile (syntaxe seule).

Niveaux de sévérité :
  E9xx (syntax errors)   → exit 2  : Claude est bloqué et doit corriger
  F    (pyflakes)        → exit 0  : affiché à Claude à titre informatif
  Succès                 → exit 0  : silencieux

---
rex:
  - date: 2026-07-03
    issue: "Ruff renamed E999->invalid-syntax; hook matched only ' E9x'/'SyntaxError' so syntax errors warned instead of blocking"
    fix: "Add 'invalid-syntax' to the has_syntax_error check"
    severity: warn
---
"""
import json
import sys
import os
import pathlib
import subprocess
import shutil


# ── Une suite qui tourne sous un arbre qui bouge ne prouve rien ───────────────
#
# Mesuré DEUX fois le 2026-09-12. La suite complète met 6 min 35 ; j'ai édité des
# modules et régénéré des documents pendant qu'elle tournait. Résultat : quatre
# « échecs » signalés, dont **trois n'existaient pas** — verts dès qu'on les rejoue
# sur l'arbre stable.
#
# Le coût n'est pas le temps de tri. Un vrai échec noyé dans des faux se traite comme
# du bruit, et c'est exactement ce qui a failli arriver au seul vrai des quatre.
#
# Ce constat ne peut PAS être un rappel dans un fichier de règles : il dépend d'un
# fait que je ne vois pas au moment du geste — une suite tourne-t-elle, et depuis
# quand. C'est pour ça qu'il vit dans un hook, et qu'il arrive au moment de l'édition.
#
# AVERTISSEMENT, jamais blocage : éditer pendant une exécution ciblée (`-k`) est
# normal, et même pendant une suite complète c'est parfois le bon choix — à condition
# de savoir que le verdict qui suivra ne vaudra rien.
_FULL_SUITE = "pytest tests/"


def _cwd_of(pid: str) -> str:
    """Le répertoire de travail de ce processus — vide si illisible."""
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return ""


def warn_if_a_full_suite_is_running() -> None:
    """Dit qu'une suite complète tourne — son verdict ne décrira plus cet arbre.

    Ne lève jamais et ne bloque jamais : ce hook suit CHAQUE écriture de `.py`.

    ⚠️ **La sonde est scopée à CE dépôt depuis le 2026-09-18.** Elle énumérait les
    processus de la MACHINE et filtrait sur la sous-chaîne `pytest tests/` — un nom
    générique. Sur un poste qui porte plusieurs dépôts Python (celui-ci en porte au
    moins trois : `n8n-ollama`, `knowledge-rag`, et celui-là), la suite d'un AUTRE
    projet faisait avertir ici, et une suite de CE dépôt lancée depuis un autre
    répertoire n'était pas vue. C'est `probe-scoped-to-the-machine-not-the-repo`,
    transposée du conteneur au processus : le mécanisme fautif n'est pas Docker, c'est
    « une énumération de l'hôte filtrée par un texte qui ne nomme pas CE dépôt ».
    On lit donc `/proc/<pid>/cwd`, qui nomme le dépôt sans ambiguïté.
    """
    racine = str(pathlib.Path(__file__).resolve().parents[2])
    try:
        out = subprocess.run(["ps", "-eo", "pid,etimes,args"],
                             capture_output=True, text=True, timeout=5)
        found = running_suite(out.stdout.splitlines(), _cwd_of, racine)
        if found:
            pid, age = found
            print(
                f"⚠️  Une suite COMPLÈTE tourne depuis {age} s (pid "
                f"{pid}). Le fichier qu'on vient d'écrire n'y sera pas — son "
                "verdict décrira un arbre qui n'existe plus.\n"
                "   Deux fois le 2026-09-12 : 3 « échecs » sur 4 n'existaient pas, "
                "et le seul vrai a failli être rangé avec eux.\n"
                "   Soit tuer la suite et la relancer après, soit ne rien conclure "
                "de ce qu'elle rendra.",
                file=sys.stderr)
    except Exception:      # noqa: BLE001 — un hook qui lève bloquerait chaque écriture
        return


def running_suite(ps_lines: list, cwd_of, repo: str):
    """`(pid, age_s)` of a FULL suite of THIS repo among `ps -eo pid,etimes,args`
    lines, or None. `cwd_of(pid)` names the process's working directory. Pure.

    A filtered run (`-k`) is not the full suite; a `grep` for it is not a run; a
    suite whose cwd is another repository is not ours (2026-09-18).
    """
    for line in ps_lines:
        if _FULL_SUITE not in line or " -k " in line or "grep" in line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        if not cwd_of(parts[0]).startswith(repo):
            continue          # une suite d'un AUTRE dépôt — pas notre affaire
        return parts[0], int(parts[1])
    return None


def run_ruff(file_path: str) -> int:
    """Lance ruff, retourne le code de sortie à utiliser."""
    result = subprocess.run(
        [
            "ruff", "check",
            "--select", "E9,F401,F811,F821,F841",
            "--output-format", "concise",
            "--no-fix",
            file_path,
        ],
        capture_output=True,
        text=True,
    )

    output = (result.stdout + result.stderr).strip()

    if result.returncode == 0:
        return 0  # Tout est propre, silence

    # Détecter les erreurs de syntaxe (bloquantes) vs warnings (informatifs)
    has_syntax_error = (
        any(f" E9{d}" in output for d in range(10))
        or "SyntaxError" in output
        or "invalid-syntax" in output  # ruff renamed E999 -> invalid-syntax
    )

    if output:
        prefix = "🚨 Syntax error" if has_syntax_error else "⚠️  Ruff warning"
        print(f"{prefix} in {file_path}:\n{output}", file=sys.stderr)

    # E9 = bloquant, F = informatif (Claude voit mais n'est pas forcé de corriger)
    return 2 if has_syntax_error else 0


def run_py_compile(file_path: str) -> int:
    """Fallback : py_compile (stdlib). Syntaxe uniquement."""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", file_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"🚨 Syntax error in {file_path}:\n{result.stderr.strip()}", file=sys.stderr)
        print("Please fix the syntax error before proceeding.", file=sys.stderr)
        return 2
    return 0


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if tool_name not in ("Write", "Edit") or not file_path.endswith(".py"):
        sys.exit(0)

    warn_if_a_full_suite_is_running()

    if shutil.which("ruff"):
        sys.exit(run_ruff(file_path))
    else:
        sys.exit(run_py_compile(file_path))


if __name__ == "__main__":
    main()
