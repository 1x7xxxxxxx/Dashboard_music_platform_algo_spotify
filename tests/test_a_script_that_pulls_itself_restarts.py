"""A deploy script that `git pull`s its own file restarts before doing anything else.

Type: Sub
Uses: tools/deploy.sh (read as text, line by line — it is bash, it has no AST here)
Depends on: nothing
Persists in: nothing

Class `script-replaced-while-it-runs`: `tools/deploy.sh` begins with `git pull`, which
rewrites the file it is running. bash reads a script incrementally, so the process keeps
executing the bytes it already read. Measured 2026-08-23: a gate added to the script was
pulled by the very deploy that did NOT run it. The fix re-execs right after the pull.
The class signature only grepped for the guard variable's NAME; this file asks the
property — nothing but bookkeeping runs between the pull and the re-exec.
"""
from __future__ import annotations

import re
from pathlib import Path

_DEPLOY = Path(__file__).resolve().parents[1] / "tools" / "deploy.sh"
_PULL = re.compile(r"^\s*git\s+pull\b")
_REEXEC = re.compile(r"\bexec\s+(?:bash\s+)?\"?\$0\"?")
# What may run from the OLD bytes: comments, echoes, variable bookkeeping, and the
# `if`/`fi` of the re-exec guard itself.
_BOOKKEEPING = re.compile(r"^\s*(?:#.*|echo\b.*|[a-z_]+=\"?\$\(git rev-parse[^)]*\)\"?|"
                          r"if \[.*DEPLOY_REEXECED.*|fi|)$")


def old_bytes_run(script: str) -> "list[str] | None":
    """Commands that run between the first `git pull` and the re-exec of `$0` — they
    run from the OLD file. `["no-reexec"]` when the script pulls and never re-execs;
    None when it never pulls. Pure."""
    lines = script.splitlines()
    pull = next((i for i, ln in enumerate(lines) if _PULL.match(ln)), None)
    if pull is None:
        return None
    after = lines[pull + 1:]
    reexec = next((i for i, ln in enumerate(after) if _REEXEC.search(ln)), None)
    if reexec is None:
        return ["no-reexec"]
    return [ln.strip() for ln in after[:reexec] if not _BOOKKEEPING.match(ln)]


def test_the_deploy_restarts_right_after_pulling_itself() -> None:
    found = old_bytes_run(_DEPLOY.read_text(encoding="utf-8"))
    assert found is not None, "deploy.sh no longer pulls — this guard reads nothing"
    assert found == [], (
        f"{found} : entre le `git pull` de deploy.sh et sa ré-exécution, ces commandes "
        "tournent depuis l'ANCIEN fichier. bash lit un script au fil de l'eau : une "
        "porte ajoutée dans ce pull ne tournerait pas pendant ce déploiement.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the deploy of 2026-08-23 — pull, then build — is named; so is a
    gate slipped between the pull and the re-exec; the pull → bookkeeping → guarded
    re-exec shape passes, and a script that never pulls is not judged."""
    old = "git fetch -q origin main\ngit pull --ff-only origin main\ndocker compose build\n"
    assert old_bytes_run(old) == ["no-reexec"]
    # The real script ANNOUNCES the pull before running it: an echo is not the pull.
    good = ('echo "▶ git pull --ff-only origin main"\n'
            'git fetch -q origin main\n'
            'before="$(git rev-parse --short HEAD)"\n'
            'git pull --ff-only origin main   # loud on a dirty tree\n'
            'after="$(git rev-parse --short HEAD)"\n'
            'echo "  $before → $after"\n'
            '# re-exec with the new bytes\n'
            'if [ -z "${DEPLOY_REEXECED:-}" ] && [ "$before" != "$after" ]; then\n'
            '    echo "re-exec"\n'
            '    DEPLOY_REEXECED=1 exec bash "$0" "$@"\nfi\n'
            './env_parity_gate.sh\n')
    assert old_bytes_run(good) == []
    slipped = good.replace('echo "  $before → $after"\n',
                           'echo "  $before → $after"\n./migrate.sh\n')
    assert old_bytes_run(slipped) == ["./migrate.sh"]
    assert old_bytes_run("docker compose build\n") is None
