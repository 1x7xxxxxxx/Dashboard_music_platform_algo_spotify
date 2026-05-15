"""Guard for error class `unregistered-write-table`.

Every table passed as a literal to PostgresHandler.upsert_many/insert_many must
be present in `_ALLOWED_TABLES` — otherwise the SQL-injection allowlist guard
raises a cryptic ValueError at write time and the DAG silently fails.
See .claude/dev-docs/error-classes.md#unregistered-write-table.
"""
import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
_CALL_RE = re.compile(r"\b(?:upsert_many|insert_many)\(\s*['\"]([a-z0-9_]+)['\"]")


def _allowed_tables() -> set[str]:
    ph = (_SRC / "database" / "postgres_handler.py").read_text(encoding="utf-8")
    block = re.search(r"_ALLOWED_TABLES = frozenset\(\{(.*?)\}\)", ph, re.S)
    assert block, "could not locate _ALLOWED_TABLES frozenset in postgres_handler.py"
    return set(re.findall(r"'([a-z0-9_]+)'", block.group(1)))


def test_every_write_table_is_registered():
    allowed = _allowed_tables()
    offenders: dict[str, list[str]] = {}
    for path in _SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in _CALL_RE.finditer(text):
            table = m.group(1)
            if table not in allowed:
                line = text[: m.start()].count("\n") + 1
                offenders.setdefault(table, []).append(f"{path.relative_to(_ROOT)}:{line}")
    assert not offenders, (
        "Tables written via upsert_many/insert_many but absent from "
        "_ALLOWED_TABLES (postgres_handler.py) — add them or the write raises "
        f"the SQL-injection guard and the DAG silently fails: {offenders}"
    )
