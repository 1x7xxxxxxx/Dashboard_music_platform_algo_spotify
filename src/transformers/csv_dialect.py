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
    header = str(text or "").lstrip("﻿").split("\n", 1)[0]
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


def describe(sep: str) -> str:
    """A separator named the way a person would say it, for an error message."""
    return {",": "virgule", ";": "point-virgule", "\t": "tabulation",
            "|": "barre verticale"}.get(sep, repr(sep))
