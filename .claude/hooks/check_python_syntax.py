#!/usr/bin/env python3
"""
Hook PostToolUse — Vérification syntaxique et qualité Python.

Déclenché après chaque Write ou Edit sur un fichier .py.
Utilise ruff si disponible (lint + syntaxe), sinon py_compile (syntaxe seule).

Niveaux de sévérité :
  E9xx (syntax errors)   → exit 2  : Claude est bloqué et doit corriger
  F    (pyflakes)        → exit 0  : affiché à Claude à titre informatif
  Succès                 → exit 0  : silencieux
"""
import json
import sys
import subprocess
import shutil


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
    has_syntax_error = any(
        f" E9{d}" in output for d in range(10)
    ) or "SyntaxError" in output

    if output:
        prefix = "🚨 Syntax error" if has_syntax_error else "⚠️  Ruff warning"
        print(f"{prefix} in {file_path}:\n{output}")

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
        print(f"🚨 Syntax error in {file_path}:\n{result.stderr.strip()}")
        print("Please fix the syntax error before proceeding.")
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

    if shutil.which("ruff"):
        sys.exit(run_ruff(file_path))
    else:
        sys.exit(run_py_compile(file_path))


if __name__ == "__main__":
    main()
