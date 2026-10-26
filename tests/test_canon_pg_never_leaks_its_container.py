"""`make canon-pg` removes its throwaway container on every exit (R666).

Type: Sub
Uses: Makefile (the `canon-pg` recipe)
Depends on: nothing at runtime — reads the Makefile
Persists in: nothing

Each recipe line used to run in its own shell, and the final `docker rm -f canon_pg` was a
line of its own: a failed step or an interrupt skipped it, and `canon_pg` stayed up for
hours (seen 2026-10-26, flagged by the fleet master's N19 probe). Measured: under
`timeout -s TERM 6 make canon-pg` the old recipe left the container, the new one does not.

guard_scope: the `canon-pg` recipe — the `docker run` that starts `canon_pg` must share ONE
shell with an EXIT trap that removes it, set before the run.
NOT covered: any other recipe that starts a container (`caddy-validate`, `backup-test`), and
a SIGKILL of make, which no trap can catch.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _logical_shells(target: str) -> list[str]:
    """The recipe's shell invocations: backslash-continued lines joined, comment lines dropped."""
    lines = (ROOT / "Makefile").read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(f"{target}:"))
    recipe = []
    for ln in lines[start + 1:]:
        if not ln.startswith("\t"):
            break
        recipe.append(ln.strip().lstrip("@"))
    shells, current = [], ""
    for ln in recipe:
        if not current and ln.startswith("#"):
            continue
        current += ln[:-1] + " " if ln.endswith("\\") else ln
        if not ln.endswith("\\"):
            shells.append(current)
            current = ""
    return shells


def test_the_container_is_started_under_an_exit_trap_that_removes_it() -> None:
    shells = _logical_shells("canon-pg")
    run = [s for s in shells if "docker run" in s and "canon_pg" in s]
    assert len(run) == 1, f"expected one shell starting canon_pg, got {run}"
    shell = run[0]
    trap = shell.find("trap 'docker rm -f canon_pg")
    assert trap != -1 and "EXIT" in shell[trap:shell.find("docker run")], (
        "the shell that starts canon_pg sets no EXIT trap removing it — a failed step "
        f"leaks the container: {shell[:200]}")
    assert trap < shell.find("docker run"), "the trap is set after the container starts"
