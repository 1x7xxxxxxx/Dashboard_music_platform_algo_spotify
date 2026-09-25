#!/usr/bin/env bash
# Ask the owner for a secret in a Windows dialog and write it straight into an env file.
#
#   tools/dev/secret_prompt.sh [--nospace] <env-file> VAR [VAR…]
#
# Type: Utility
# Uses: powershell.exe (WinForms masked dialog, from WSL), python3
# Persists in: <env-file> — the VAR= line is replaced, or appended when absent
#
# Why (2026-09-25): a password typed into the Claude Code chat is sent to the API and written
# in clear in ~/.claude/projects/*.jsonl — two Gmail app passwords had to be revoked minutes
# after being pasted. This script lets Claude run the whole gesture while the value travels
# dialog → bash variable → file, and never through a command line, a tool output or the chat.
# It prints only the variable name and the value's LENGTH.
#
# --nospace removes inner spaces (Google shows app passwords as "xxxx xxxx xxxx xxxx").
# SECRET_PROMPT_CMD overrides the dialog (tests): a command whose stdout is the value.
set -euo pipefail

nospace=0
if [ "${1-}" = "--nospace" ]; then nospace=1; shift; fi
[ $# -ge 2 ] || { echo "usage: $0 [--nospace] <env-file> VAR [VAR…]"; exit 2; }
file="$1"; shift
[ -f "$file" ] || { echo "❌ $file introuvable"; exit 2; }

source "$(dirname "${BASH_SOURCE[0]}")/secret_dialog.sh"

write_var_py='
import sys, pathlib
path, var = sys.argv[1], sys.argv[2]
val = sys.stdin.read()
p = pathlib.Path(path)
lines = p.read_text(encoding="utf-8").splitlines()
hit = False
for i, ln in enumerate(lines):
    if ln.startswith(var + "="):
        lines[i] = var + "=" + val; hit = True
if not hit:
    lines.append(var + "=" + val)
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("remplacée" if hit else "ajoutée")
'

n=$#; i=0
for v in "$@"; do
    i=$((i + 1))
    [[ "$v" =~ ^[A-Z][A-Z0-9_]*$ ]] || { echo "❌ nom de variable invalide : $v"; exit 2; }
    val="$(dialog "$v" "$i/$n")"
    val="${val#"${val%%[![:space:]]*}"}"; val="${val%"${val##*[![:space:]]}"}"
    [ "$nospace" = 1 ] && val="${val// /}"
    [ -n "$val" ] || { echo "❌ $v : rien saisi (fenêtre fermée ?) — fichier inchangé"; exit 1; }
    how="$(printf '%s' "$val" | python3 -c "$write_var_py" "$file" "$v")"
    echo "🔑 $v : ${#val} caractères, $how dans $file"
    unset val
done
