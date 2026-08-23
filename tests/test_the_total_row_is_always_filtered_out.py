"""
Guard — every query on `s4a_song_timeline` excludes the CSV's "Total" row.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: src/**, airflow/dags/**
Persists in: nothing (read-only assertions)

Error class: mandatory-filter-with-no-guard.

`CLAUDE.md` says it in bold — "**Mandatory**: every query on `s4a_song_timeline` must add
`AND song NOT ILIKE '%1x7xxxxxxx%'`" — because Spotify for Artists CSVs carry a summary
row whose `song` is the artist's own name. Summing without excluding it roughly DOUBLES
every stream total.

It has already cost real money-facing numbers: the 2026-06-11 ship-blocker audit found
two unfiltered queries in `trigger_algo/_tab_budget_roi.py`, and the displayed cost per
stream was divided by ~2 as a result. The fix was applied to those two sites. **No guard
was written**, so the rule went on being enforced by memory alone.

Measured 2026-08-23, while investigating why `data_quality_check` is paused: that DAG
queries the table FIVE times and carries the filter ZERO times. Across `src/` and
`airflow/` the table is named 109 times and the filter appears 30 times.

Read on the AST of the SQL string, not by grepping the file: a file can mention the
table in a comment, and a guard that counts substrings fails on its own documentation —
the lesson of the four hollow guards of 2026-08-22.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TABLE = "s4a_song_timeline"
FILTER_TOKEN = "1x7xxxxxxx"

# A query only needs the filter when it READS the table. A DDL statement, an INSERT or a
# DELETE has no summary row to exclude — demanding the filter there would be noise, and
# noise is how a guard gets disabled.
_READS = re.compile(r"\bFROM\s+" + TABLE + r"\b|\bJOIN\s+" + TABLE + r"\b", re.I)
_WRITES = re.compile(r"^\s*(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE)\b",
                     re.I | re.M)
# The exclusion has TWO legitimate forms, and the parameterised one is the BETTER one:
#
#     AND song NOT ILIKE '%1x7xxxxxxx%'      -- literal
#     AND song NOT ILIKE %s                  -- ARTIST_FILTER passed as a parameter
#
# The first version of this guard only recognised the literal and reported 23 files,
# nearly all of them correct. That is `watchdog-becomes-the-noise` — and a detector that
# cries wolf on the repository's own preferred style is a detector someone disables.
# The predicate that matches the QUESTION is "does this read exclude the summary row",
# not "does this string contain a magic value".
_EXCLUDES = re.compile(r"\bsong\s+NOT\s+ILIKE\b", re.I)

# The defect is DOUBLING A TOTAL. It needs a read that can aggregate ACROSS songs, so
# only those are flagged. Measured while writing this guard: without the two refinements
# below it reported 10 files, of which 5 were correct —
#   * a read pinned to one song (`WHERE song = %s`) can only return the summary row if
#     the caller explicitly asks for it by name;
#   * `SELECT MAX(collected_at)` cannot be distorted by an extra row.
# Reporting those would have taught the reader to skip this test, which is how a guard
# stops guarding. The predicate now matches the QUESTION — "can this read double a
# total?" — rather than the table name.
# `TRIM(song) = %s` pins a song exactly as `song = %s` does.
_PINS_ONE_SONG = re.compile(r"\bsong\s*\)?\s*=", re.I)
# An EXISTENCE probe — "does this tenant have any CSV data at all" — is not a total.
# `home.py` asks `(SELECT COUNT(*) … LIMIT 1) AS has_csv`, and the answer is the same
# whether or not the summary row is counted.
_EXISTENCE_PROBE = re.compile(r"COUNT\s*\(\s*\*\s*\)[^;]*\bLIMIT\s+1\b", re.I | re.S)
# A shell command RENDERED to the operator on a help page is not a query this app runs.
_NOT_OUR_QUERY = re.compile(r"docker\s+exec|psql\s+-U", re.I)
_AGGREGATES_ACROSS_SONGS = re.compile(
    r"\bstreams\b|\bCOUNT\s*\(|\bSUM\s*\(|\bGROUP\s+BY\b|\bDISTINCT\s+song\b|"
    r"\bNOT\s+EXISTS\b", re.I)


def _sql_literals(path: Path) -> list[tuple[int, str]]:
    """Every string constant in the module, with its line — read off the AST."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append((node.lineno, node.value))
        elif isinstance(node, ast.JoinedStr):
            # f-strings: stitch the literal halves so `FROM {tbl}` still shows its WHERE
            parts = [v.value for v in node.values
                     if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            if parts:
                out.append((node.lineno, " ".join(parts)))
    return out


def _files() -> list[Path]:
    out = []
    for sub in ("src", "airflow"):
        for path in sorted((ROOT / sub).rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            if TABLE in path.read_text(encoding="utf-8"):
                out.append(path)
    return out


def _unfiltered_reads(path: Path) -> list[int]:
    bad = []
    for lineno, sql in _sql_literals(path):
        if not _READS.search(sql):
            continue
        if _WRITES.search(sql):
            continue
        if FILTER_TOKEN in sql or _EXCLUDES.search(sql):
            continue
        if _PINS_ONE_SONG.search(sql):
            continue
        if _EXISTENCE_PROBE.search(sql) or _NOT_OUR_QUERY.search(sql):
            continue
        if not _AGGREGATES_ACROSS_SONGS.search(sql):
            continue
        bad.append(lineno)
    return sorted(set(bad))


def test_the_scope_is_not_empty() -> None:
    files = _files()
    assert len(files) >= 5, (
        f"only {[f.name for f in files]} mention {TABLE} — the walk is wrong, and a "
        "guard that silently matches nothing is the defect it exists to prevent"
    )


@pytest.mark.parametrize("rel", [p.relative_to(ROOT).as_posix() for p in _files()])
def test_a_read_of_the_timeline_excludes_the_total_row(rel: str) -> None:
    bad = _unfiltered_reads(ROOT / rel)
    assert not bad, (
        f"{rel} reads {TABLE} without `AND song NOT ILIKE '%{FILTER_TOKEN}%'` at "
        f"line(s) {bad}. The CSV's summary row is named after the artist, so the sum "
        f"roughly doubles — that is how the displayed cost per stream was halved in "
        f"June. If a read genuinely needs the Total row, say so in the SQL itself."
    )


def test_the_detector_recognises_the_defect_it_is_written_for() -> None:
    """Pins the detector against a synthetic module, so it cannot rot into a no-op."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        bad = Path(d) / "bad.py"
        bad.write_text('q = """SELECT streams FROM s4a_song_timeline WHERE artist_id = 1"""\n',
                       encoding="utf-8")
        assert _unfiltered_reads(bad) == [1]

        good = Path(d) / "good.py"
        good.write_text(
            'q = """SELECT streams FROM s4a_song_timeline\n'
            "         WHERE artist_id = %s AND song NOT ILIKE '%1x7xxxxxxx%'\"\"\"\n",
            encoding="utf-8")
        assert _unfiltered_reads(good) == [], "the literal form must be accepted"

        param = Path(d) / "param.py"
        param.write_text(
            'q = """SELECT streams FROM s4a_song_timeline\n'
            '         WHERE artist_id = %s AND song NOT ILIKE %s"""\n',
            encoding="utf-8")
        assert _unfiltered_reads(param) == [], (
            "the PARAMETERISED form must be accepted — it is the repository's preferred "
            "style and rejecting it made this guard report 23 correct files")

        pinned = Path(d) / "pinned.py"
        pinned.write_text(
            'q = """SELECT date, streams FROM s4a_song_timeline WHERE song = %s"""\n',
            encoding="utf-8")
        assert _unfiltered_reads(pinned) == [], (
            "a read pinned to one song cannot pick up the summary row by accident")

        maxonly = Path(d) / "maxonly.py"
        maxonly.write_text(
            'q = """SELECT MAX(collected_at) FROM s4a_song_timeline"""\n', encoding="utf-8")
        assert _unfiltered_reads(maxonly) == [], (
            "a MAX over a timestamp cannot be doubled by an extra row")

        trimmed = Path(d) / "trimmed.py"
        trimmed.write_text(
            'q = """SELECT streams FROM s4a_song_timeline WHERE TRIM(song) = %s"""\n',
            encoding="utf-8")
        assert _unfiltered_reads(trimmed) == [], "TRIM(song) = %s pins a song too"

        probe = Path(d) / "probe.py"
        probe.write_text(
            'q = """SELECT (SELECT COUNT(*) FROM s4a_song_timeline '
            'WHERE artist_id = %s LIMIT 1) AS has_csv"""\n', encoding="utf-8")
        assert _unfiltered_reads(probe) == [], "an existence probe is not a total"

        write = Path(d) / "write.py"
        write.write_text('q = """DELETE FROM s4a_song_timeline WHERE artist_id = %s"""\n',
                         encoding="utf-8")
        assert _unfiltered_reads(write) == [], "a write has no summary row to exclude"
