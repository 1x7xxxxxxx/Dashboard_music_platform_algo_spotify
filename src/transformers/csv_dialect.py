"""Which character separates the columns of this export, and how to say so.

Type: Utility
Uses: csv (stdlib only — imported by parsers that run inside Airflow)
Triggers: s4a_csv_parser, distrokid_parser
Depends on: nothing
Persists in: nothing

Why this module exists — R52, reported by an artist whose export never imported.

A Spotify-for-Artists or distributor export downloaded on a French-locale machine is
usually semicolon-separated: Excel writes the list separator of the system locale, and
on `fr-FR` that is `;`. Every reader in this repo assumed otherwise:

    s4a_csv_parser      `pd.read_csv(file_path)`      → comma only
    distrokid_parser    `_sniff_sep`                  → tab vs comma, never `;`
    apple/imusician     `pd.read_csv(file_path, ...)` → comma only

A semicolon file therefore parses as ONE column, no expected header is found, and the
S4A path answered `{'type': None, 'data': []}` out of a bare `except:` — the refusal
named nothing, so "my CSV does not work" was the whole diagnosis available to the
artist and to us.

Two decisions worth stating, because the naive version of each is wrong:

  * **Count on the HEADER line, not the whole file.** A song title containing a comma
    ("Hello, Goodbye") is ordinary; a header line containing one is the separator.
  * **A tie is not a guess.** When two candidates score equally the file is ambiguous,
    and `sniff_separator` says so rather than picking. A silently wrong separator
    produces a one-column frame that looks like a *schema* problem for hours.
"""
from __future__ import annotations

import math
import numbers
import re

# Ordered by how likely a real export uses it. Order only breaks ties in `max`, and
# ties are refused below, so this is documentation rather than logic.
SEPARATORS = (",", ";", "\t", "|")


class AmbiguousSeparatorError(ValueError):
    """The header line does not identify one separator. Refuse rather than guess."""


def sniff_separator(text: str) -> str:
    """The column separator of `text`, decided on its header line.

    Raises `AmbiguousSeparatorError` when no candidate wins outright — including the
    single-column case, where every count is zero and any answer would be a guess
    dressed as a measurement.
    """
    # `str(x or "")` est le motif qui écrit la chaîne « nan » : un NaN pandas est
    # VRAI en booléen, donc il traverse le `or` et `str()` le rend littéral.
    # Ici le paramètre est typé `str`, donc le risque est théorique — mais un
    # motif dont la forme est fautive se recopie, et celui-ci a déjà produit
    # 2 533 lignes de « nan » dans le parseur iMusician.
    header = (text if isinstance(text, str) else "").lstrip("\ufeff").split("\n", 1)[0]
    counts = {sep: header.count(sep) for sep in SEPARATORS}
    best = max(counts.values())
    if best == 0:
        raise AmbiguousSeparatorError(
            "no column separator found on the header line — the file may have a "
            "preamble row above its headers, or hold a single column. "
            f"Header read: {header[:120]!r}")
    winners = [s for s, n in counts.items() if n == best]
    if len(winners) > 1:
        raise AmbiguousSeparatorError(
            f"header line is ambiguous: {', '.join(map(repr, winners))} each appear "
            f"{best} time(s). Re-export with a single separator. "
            f"Header read: {header[:120]!r}")
    return winners[0]


def without_spaces(value) -> str:
    """`value` as text with EVERY Unicode space removed — the plain one, and the no-break
    (U+00A0) and narrow no-break (U+202F) spaces a French-locale Excel groups thousands
    with. A list of known characters (`.replace(' ', '')`) missed the last two, and four
    export parsers read `1\u00a0000` streams as 0 (R499, found by a property test)."""
    return "".join(str(value).split())


def describe(sep: str) -> str:
    """A separator named the way a person would say it, for an error message."""
    return {",": "virgule", ";": "point-virgule", "\t": "tabulation",
            "|": "barre verticale"}.get(sep, repr(sep))


# What a cell holds when it holds NO number — legitimately 0 to the caller, never a
# rejection. Anything else that does not read is unreadable (R502 counts those).
_BLANK = frozenset({"", "-", "—", "–", "nan", "none", "n/a", "null"})


def decimal_for(sep: str) -> str:
    """The decimal mark of a file, decided ONCE from its column separator (R503).

    A `;` file is what a French-locale Excel writes, and that locale writes `1 234,5`;
    every other separator comes from a `.`-decimal locale. Deciding per FILE is what
    removes the ambiguity: `1.234` alone is either 1.234 or 1234, the file is not.
    """
    return "," if sep == ";" else "."


def read_csv_options(sep: str) -> dict:
    """The `pd.read_csv` keywords for a file of this separator: pandas converts a cell
    it recognises BEFORE any reader of ours sees it, so `1.234` in a `;` file became
    1.234 unless pandas is told the file's decimal mark too (R503)."""
    dec = decimal_for(sep)
    return {"sep": sep, "decimal": dec, "thousands": "." if dec == "," else None}


def _split_decimal(text: str, decimal: str) -> tuple[str, str | None]:
    """(grouping marks, decimal mark) for one number written with `.`/`,`."""
    marks = {c for c in text if c in ".,"}
    if len(marks) == 2:
        # Both present: the rightmost is the decimal mark, whatever the file says.
        dec = text[max(text.rfind("."), text.rfind(","))]
        return ("." if dec == "," else ","), dec
    if not marks:
        return "", None
    (mark,) = marks
    if text.count(mark) > 1:
        return mark, None
    if mark == decimal:
        return "", mark
    # The file's OTHER mark, once: grouping only if exactly three digits follow it.
    head, tail = text.split(mark)
    if len(tail) == 3 and 1 <= len(head.lstrip("+-")) <= 3:
        return mark, None
    return "", mark


def read_number(value, decimal: str = ".") -> float | None:
    """`value` as a number, `None` when the cell is blank, `ValueError` when unreadable.

    `decimal` is the FILE's decimal mark (`decimal_for`). Grouping by any Unicode space,
    or by the other mark in groups of three, is read; anything else raises instead of
    reading 0 — `1.234,5` read 1, 0 or 0.0 depending on which of five readers saw it.
    """
    if decimal not in (".", ","):
        raise ValueError(f"decimal mark must be '.' or ',', got {decimal!r}")
    if isinstance(value, bool):
        raise ValueError(f"a boolean is not a number: {value!r}")
    if isinstance(value, numbers.Real):
        number = float(value)
        return None if math.isnan(number) else number
    text = without_spaces("" if value is None else value)
    if text.lower() in _BLANK:
        return None
    group, dec = _split_decimal(text, decimal)
    whole, _, frac = text.partition(dec) if dec else (text, "", "")
    sign = whole[:1] if whole[:1] in "+-" else ""
    whole = whole[len(sign):]
    pattern = (rf"\d{{1,3}}(?:{re.escape(group)}\d{{3}})+" if group else r"\d*")
    if not re.fullmatch(pattern, whole) or not re.fullmatch(r"\d*", frac) \
            or not (whole or frac):
        raise ValueError(f"unreadable number: {str(value)[:40]!r}")
    return float(f"{sign}{whole.replace(group, '') if group else whole or '0'}.{frac or '0'}")
