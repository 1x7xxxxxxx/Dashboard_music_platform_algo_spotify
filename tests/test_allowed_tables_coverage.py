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
# Also catch the dynamic-dispatch pattern: a platform-registry config dict whose
# 'table' value feeds upsert_many(table=cfg['table'], ...) — e.g. upload_csv._PLATFORMS.
_CFG_RE = re.compile(r"['\"]table['\"]\s*:\s*['\"]([a-z0-9_]+)['\"]")


def _allowed_tables() -> set[str]:
    ph = (_SRC / "database" / "postgres_handler.py").read_text(encoding="utf-8")
    block = re.search(r"_ALLOWED_TABLES = frozenset\(\{(.*?)\}\)", ph, re.S)
    assert block, "could not locate _ALLOWED_TABLES frozenset in postgres_handler.py"
    return set(re.findall(r"'([a-z0-9_]+)'", block.group(1)))


def unregistered(text: str, allowed: set[str]) -> list[tuple[str, int]]:
    """(table, line) written by `text` and absent from `allowed`. Pure."""
    return [(m.group(1), text[: m.start()].count("\n") + 1)
            for m in (*_CALL_RE.finditer(text), *_CFG_RE.finditer(text))
            if m.group(1) not in allowed]


def test_every_write_table_is_registered():
    allowed = _allowed_tables()
    offenders: dict[str, list[str]] = {}
    for path in _SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for table, line in unregistered(text, allowed):
            offenders.setdefault(table, []).append(f"{path.relative_to(_ROOT)}:{line}")
    assert not offenders, (
        "Tables written via upsert_many/insert_many but absent from "
        "_ALLOWED_TABLES (postgres_handler.py) — add them or the write raises "
        f"the SQL-injection guard and the DAG silently fails: {offenders}"
    )


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity, both halves: a literal write and a registry-dispatched write to an
    unregistered table are named; the same writes to a registered table are not."""
    allowed = {"youtube_videos"}
    defect = ("db.upsert_many('hypeddit_clicks', rows, ['id'])\n"
              "_PLATFORMS = {'x': {'table': 'apple_new_stats'}}\n")
    assert unregistered(defect, allowed) == [("hypeddit_clicks", 1), ("apple_new_stats", 2)]
    fixed = ("db.upsert_many('youtube_videos', rows, ['id'])\n"
             "_PLATFORMS = {'x': {'table': 'youtube_videos'}}\n")
    assert unregistered(fixed, allowed) == []
    assert "youtube_videos" in _allowed_tables(), "the allowlist parser reads nothing"
