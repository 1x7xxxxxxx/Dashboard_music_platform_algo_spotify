"""Guard: every table written through PostgresHandler must be in the SQL allowlist.

Type: Test
Uses: src/database/postgres_handler._ALLOWED_TABLES, static scan of src/
Persists in: —

Motivation (2026-06-10): adding a table requires editing THREE places — the
migration, the schema module, and `_ALLOWED_TABLES` in postgres_handler.py. Forget
the last and `upsert_many()` raises `ValueError: SQL injection guard: table 'X' is
not in the allowed list` — at RUNTIME, in the user's face (it shipped: the
s4a_song_nonalgo_streams save crashed live). This test scans the codebase for the
deterministic write signals and fails at PR time instead.

Scope is intentionally limited to UNAMBIGUOUS literals to stay false-positive-free:
- `upsert_many("table", ...)`  — first positional arg, the exact call that validates.
- `"table": "name"` / `'table': 'name'` dict configs (e.g. upload_csv._PLATFORMS),
  which feed `upsert_many(table=cfg['table'], ...)` dynamically.
Dynamic table args built any other way are out of scope (can't resolve statically).
"""
import re
from pathlib import Path

from src.database.postgres_handler import _ALLOWED_TABLES

_SRC = Path(__file__).resolve().parents[1] / "src"

# upsert_many("table", ...) — literal first arg, tolerant of newlines after "(".
_UPSERT_RE = re.compile(r"upsert_many\(\s*[\"']([a-z_][a-z0-9_]*)[\"']")
# "table": "name"  /  'table': 'name'  — platform-registry style config dicts.
_CFG_RE = re.compile(r"[\"']table[\"']\s*:\s*[\"']([a-z_][a-z0-9_]*)[\"']")


def _written_tables() -> dict[str, list[str]]:
    """{table_name: [files it appears in]} for every statically-resolvable write."""
    hits: dict[str, list[str]] = {}
    for py in _SRC.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for table in set(_UPSERT_RE.findall(text)) | set(_CFG_RE.findall(text)):
            hits.setdefault(table, []).append(py.name)
    return hits


def test_every_written_table_is_allowlisted():
    written = _written_tables()
    # Sanity: the scan must actually find writes, else the regex silently passes.
    assert written, "static scan found no upsert_many/table-config writes — regex broke?"
    missing = {t: files for t, files in written.items() if t not in _ALLOWED_TABLES}
    assert not missing, (
        "Tables written via PostgresHandler but absent from _ALLOWED_TABLES "
        f"(would raise at runtime): {missing}. Add them to _ALLOWED_TABLES in "
        "src/database/postgres_handler.py."
    )
