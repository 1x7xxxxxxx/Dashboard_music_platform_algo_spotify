"""A semicolon export imported as nothing, and the refusal named nothing.

R52, reported by an artist ("Benj") whose S4A export never imported. Measured causes,
both real:

  * `s4a_csv_parser.parse_csv_file` read with `pd.read_csv(file_path)` — comma only.
    An export downloaded on a French-locale machine is `;`-separated, because Excel
    writes the list separator of the system locale. The frame came back as ONE
    column, no expected header was found…
  * …and the surrounding `except:` — bare, which this repo's own Python rules forbid
    — returned `{'type': None, 'data': []}`. Indistinguishable from "empty file".
    "My CSV does not work" was the entire diagnosis available to the artist and to us.

`distrokid_parser._sniff_sep` had the same blind spot from the other side: it chose
between tab and comma and never considered `;`. Two readers of one question, which is
the shape catalogued as `two-checks-one-question-reported-twice` — so they now share
`csv_dialect.sniff_separator` rather than agreeing by luck.

The refusal is asserted as hard as the parse: a parser that cannot read a file must
say WHICH separator it tried, because that is the missing sentence nine times in ten.
"""
from __future__ import annotations

import pathlib

import pytest

from src.transformers.csv_dialect import (
    AmbiguousSeparatorError, describe, sniff_separator,
)

_HEADER = "date{s}streams{s}listeners{s}saves"
_ROW = "2026-08-01{s}120{s}80{s}4"


@pytest.mark.parametrize("sep", [",", ";", "\t", "|"])
def test_every_separator_a_real_export_uses_is_recognised(sep):
    assert sniff_separator(_HEADER.format(s=sep)) == sep


def test_the_semicolon_case_that_started_this():
    """The literal shape of the file that never imported."""
    assert sniff_separator("date;streams;listeners;saves\n2026-08-01;120;80;4") == ";"


def test_a_comma_inside_a_title_does_not_beat_the_real_separator():
    """Counted on the HEADER line: a song called "Hello, Goodbye" is ordinary data."""
    text = 'song;streams\n"Hello, Goodbye";120\n"Come, Together";90'
    assert sniff_separator(text) == ";"


def test_a_bom_does_not_hide_the_first_column():
    """Excel writes a UTF-8 BOM. It must not become part of the first header."""
    assert sniff_separator("﻿date;streams;saves") == ";"


def test_a_tie_is_refused_rather_than_guessed():
    """A silently wrong separator yields a one-column frame that reads as a SCHEMA
    problem for hours. Refusing costs one message; guessing costs an afternoon."""
    with pytest.raises(AmbiguousSeparatorError, match="ambiguous"):
        sniff_separator("a,b;c")


def test_a_single_column_header_is_refused_not_defaulted():
    with pytest.raises(AmbiguousSeparatorError, match="no column separator"):
        sniff_separator("justonecolumn")


def test_describe_speaks_french_to_a_french_speaking_artist():
    assert describe(";") == "point-virgule"
    assert describe("\t") == "tabulation"


# ── end to end, through the parser the DAG actually calls ────────────────────

def _write(tmp_path: pathlib.Path, name: str, text: str) -> pathlib.Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_a_semicolon_file_now_parses(tmp_path):
    from src.transformers.s4a_csv_parser import S4ACSVParser

    f = _write(tmp_path, "monTitre-28day.csv",
               "date;streams\n2026-08-01;120\n2026-08-02;90\n")
    out = S4ACSVParser().parse_csv_file(f)
    assert out["data"], f"the semicolon export still imports nothing: {out}"


def test_a_file_refused_at_the_sniff_stage_says_why(tmp_path):
    from src.transformers.s4a_csv_parser import S4ACSVParser

    f = _write(tmp_path, "monTitre-28day.csv", "onlyonecolumn\nvalue\n")
    out = S4ACSVParser().parse_csv_file(f)
    assert out["type"] is None
    assert "separator" in out.get("reason", ""), (
        "a refusal with no reason is the defect this file exists for — the caller "
        f"cannot tell an empty file from an unreadable one: {out}")


def test_a_file_refused_at_the_READ_stage_names_the_separator(monkeypatch, tmp_path):
    """The other refusal branch, and the first version of this file never reached it.

    A single-column file is refused while SNIFFING, so it exercises the first branch
    twice and the second one never — a mutation that deleted the read-stage reason
    left every assertion green. A guard has to reach each branch it claims.
    """
    import pandas as pd

    from src.transformers.s4a_csv_parser import S4ACSVParser

    f = _write(tmp_path, "monTitre-28day.csv", "date;streams\n2026-08-01;120\n")

    def _boom(*a, **k):
        raise pd.errors.ParserError("bad line 3")

    monkeypatch.setattr(pd, "read_csv", _boom)
    out = S4ACSVParser().parse_csv_file(f)
    assert out["type"] is None
    reason = out.get("reason", "")
    assert "point-virgule" in reason, (
        "the refusal must name the separator it actually tried — that is the "
        f"sentence missing nine times in ten: {reason!r}")
    assert "ParserError" in reason


def test_both_readers_agree_on_the_separator():
    """The two sniffers disagreed on `;`. They must not be able to drift again."""
    from src.transformers.distrokid_parser import DistroKidParser

    text = "date;streams;saves\n2026-08-01;1;2"
    assert DistroKidParser._sniff_sep(text) == sniff_separator(text) == ";"


def test_no_bare_except_survives_anywhere_under_src():
    """This repo forbids `except:` (`.claude/rules/python.md`). It is what turned an
    unreadable file into an empty one here — so its absence is part of the fix, not a
    style note.

    Repo-wide and AST-based, for two measured reasons. The first draft of this
    assertion searched the TEXT of one file, and the very first run found a SECOND
    bare handler further down the same file that the fix had not touched — one
    instance is never the class. And a text search cannot tell `except:` from
    `except: pass` on one line, which is how four of the nine were written.
    """
    import ast

    repo = pathlib.Path(__file__).resolve().parents[1]
    bare = [f"{f.relative_to(repo)}:{n.lineno}"
            for f in sorted((repo / "src").rglob("*.py"))
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8")))
            if isinstance(n, ast.ExceptHandler) and n.type is None]
    assert not bare, (
        "bare `except:` catches KeyboardInterrupt and SystemExit too, and renders "
        f"every failure as 'nothing to read': {bare}")
