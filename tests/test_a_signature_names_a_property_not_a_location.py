"""No error-class signature is anchored on a `file:line`.

Type: Sub
Uses: .claude/dev-docs/error-classes.md
Depends on: nothing
Persists in: nothing

Class `a-signature-anchored-on-a-location`: a signature that names a LOCATION is coupled
to the shape of the code, not to the property — the next refactor moves the line and the
signature goes quiet, or red on nothing. The class signature was a `grep` over the
catalogue; this file runs the same question as a predicate, and proves it.
"""
from __future__ import annotations

import re
from pathlib import Path

_CATALOGUE = Path(__file__).resolve().parents[1] / ".claude" / "dev-docs" / "error-classes.md"
_HEADING = re.compile(r"^## ([a-z0-9][a-z0-9-]+)\s*$", re.M)
_SIGNATURE = re.compile(r"^- signature: (.*)$", re.M)
_LOCATION = re.compile(r"[a-zA-Z_/]+\.(?:py|sql|md):[0-9]+")


def anchored_signatures(catalogue: str) -> list[str]:
    """Classes whose `signature:` line names a `path.ext:LINE`. Pure."""
    heads = list(_HEADING.finditer(catalogue))
    out = []
    for n, head in enumerate(heads):
        end = heads[n + 1].start() if n + 1 < len(heads) else len(catalogue)
        sig = _SIGNATURE.search(catalogue, head.end(), end)
        if sig and _LOCATION.search(sig.group(1)):
            out.append(head.group(1))
    return out


def test_no_signature_is_anchored_on_a_line() -> None:
    anchored = anchored_signatures(_CATALOGUE.read_text(encoding="utf-8"))
    assert not anchored, (
        f"{anchored} : leur `signature:` nomme un `fichier:ligne`. Le prochain "
        "déplacement de code la rend muette ou rouge sur rien — elle garde un "
        "EMPLACEMENT, pas la propriété. Nommer la question (AST, prédicat, test), pas "
        "la ligne.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: a signature naming `platform_timeseries.py:412` is named; a
    `root_cause` that cites a line (prose is allowed to point) and a signature that
    runs a test file are not — nor a line number in the NEXT class's signature
    attributed to this one."""
    catalogue = (
        "## anchored-one\n"
        "- root_cause: `src/a.py:12` did it\n"
        "- signature: `sed -n 412p src/dashboard/utils/platform_timeseries.py:412`\n"
        "\n## property-one\n"
        "- root_cause: see `src/b.py:40`\n"
        "- signature: `python3 -m pytest tests/test_x.py -q`\n"
        "\n## no-signature\n"
        "- root_cause: `src/c.py:7`\n"
        "\n## anchored-two\n"
        "- signature: `grep -q X migrations/065_youtube.sql:3`\n")
    assert anchored_signatures(catalogue) == ["anchored-one", "anchored-two"]
