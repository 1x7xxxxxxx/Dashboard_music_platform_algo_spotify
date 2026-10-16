"""Every entry of guard_destructive's block/warn tables can still fire (R633).

Type: Test
Uses: pytest, .claude/hooks/guard_destructive.py
Depends on: .claude/hooks/guard_destructive.py
Persists in: nothing

Since 2026-09-16 the tables were matched as « the gesture is the COMMAND of its
segment ». Right for `git reset --hard`, wrong for six entries that are never a
command — `DROP TABLE` is an argument of `psql`, `--build` one of `docker compose`.
They could not fire any more, and `psql -c '<destructive SQL>'` passed, while the
table still read as coverage. Found 2026-10-16 by audit_fleet's `drop-table` probe.

guard_scope: each table entry fired by one real example (a new entry without an
example fails `test_every_entry_has_an_example`), the real SQL forms (client flag,
`make psql`, `docker exec`, a pipe, a heredoc into the client) and their prose
neighbours (commit message, grep, a heredoc written to a file). NOT covered: SQL
reached through a script file (`psql -f drop.sql`), a client named by a variable
(`$PSQL`), or a `python -c` that opens a connection.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "guard_destructive.py"
_spec = importlib.util.spec_from_file_location("guard_destructive_r633", _HOOK)
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)

# Concatenated so that this FILE does not carry the SQL gestures in clear.
_DT, _DD, _DS, _DF = "DROP " + "TABLE", "DROP " + "DATABASE", "DROP " + "SCHEMA", "DELETE " + "FROM"

# One example per entry — the key is the entry, the value a command that must fire it.
EXAMPLES = {
    "git push --force": "git push --force origin main",
    "git push -f ": "git push -f origin main",
    "git reset --hard": "git reset --hard HEAD~1",
    "git checkout -- .": "git checkout -- .",
    "git restore .": "git restore .",
    "git clean -f": "git clean -f",
    "docker system prune": "docker system prune -a --volumes",
    "DROP TABLE": f"psql -c '{_DT} users'",
    "DROP DATABASE": f"docker exec -i pg psql -U postgres -c '{_DD} spotify_etl'",
    "DROP SCHEMA": f"make psql Q='{_DS} public CASCADE'",
    "dropdb ": "dropdb spotify_etl",
    "git commit --no-verify": "git commit --no-verify -m x",
    "git commit -n ": "git commit -n -m x",
    "git push --no-verify": "git push --no-verify",
    "rm -rf": "rm -rf build/",
    "DELETE FROM": f"psql -c '{_DF} artists'",
    "git stash drop": "git stash drop",
    "docker volume rm": "docker volume rm pgdata",
    "truncate": "truncate -s 0 app.log",
    "pkill": "pkill -f streamlit",
    "make migrate": "make migrate",
    "init_db.sql": "cat init_db.sql | docker exec -i pg psql -U postgres",
    "--build": "docker compose up -d --build",
}

_TABLE = [*g._BLOCK_PATTERNS, *g._WARN_PATTERNS]


def test_every_entry_has_an_example() -> None:
    assert set(EXAMPLES) == {p for p, _ in _TABLE}, "a guard entry without an example cannot be shown to fire"


@pytest.mark.parametrize(("pattern", "message"), _TABLE, ids=[p for p, _ in _TABLE])
def test_the_entry_fires_on_its_example(pattern: str, message: str) -> None:
    verdict = g._gesture_fires(EXAMPLES[pattern], pattern)
    assert verdict, f"{pattern!r} never fires — the entry is dead: {EXAMPLES[pattern]!r}"


@pytest.mark.parametrize("command", [
    f"psql -c 'BEGIN; {_DT} x;'",
    f"docker exec -i pg psql -U postgres -d spotify_etl -c '{_DT} artists'",
    f"make psql Q='{_DT} users'",
    f"make prod-psql Q='{_DT} users'",
    f"echo '{_DT.lower()} x' | psql",
    f"psql -d spotify_etl <<'EOF'\n{_DS} public CASCADE;\nEOF",
    f"cd /srv && /usr/bin/psql -c '{_DD} x'",
])
def test_a_real_sql_gesture_is_blocked(command: str) -> None:
    verdict = g.check_command(command)
    assert verdict and verdict[0] == "block", f"not blocked: {command!r}"


@pytest.mark.parametrize("command", [
    f"git commit -m '{_DT} removed from the docs'",
    f"cat > m.sql <<'EOF'\n{_DT} x;\nEOF",
    f'grep -rn "{_DT}" migrations/',
    "psql -c 'SELECT 1'",
    'echo "--build"',
    "git log --grep=--build",
])
def test_a_mention_passes(command: str) -> None:
    verdict = g.check_command(command)
    assert not (verdict and verdict[0] == "block"), f"blocked a mention: {command!r}"
