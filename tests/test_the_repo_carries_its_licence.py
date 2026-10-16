"""The public repository says who owns it, and nothing contradicts it (R624).

Type: Hook
Uses: LICENSE, README.md, pyproject.toml
Persists in: nothing

Measured 2026-10-16: a PUBLIC repo with no LICENSE — every copy unlicensed, but nothing
told a reader so. The owner chose « tous droits réservés » (option a).

guard_scope: the LICENSE file, the README link that resolves to it, and the pyproject
`license` field. NOT covered: a licence written in a docstring or in a sub-directory
file other than the third-party one LICENSE names.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_OPEN = re.compile(r"\b(MIT|Apache|BSD|GPL|MPL|ISC|Unlicense|CC[- ]BY)\b", re.I)


def test_licence_reserves_all_rights() -> None:
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "All rights reserved." in text
    assert not re.search(r"\b(19|20)\d\d\b", text), "no year git cannot prove"


def test_licence_names_the_third_party_files_it_excludes() -> None:
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    for path in re.findall(r"(?:archive|docs)/[\w./-]+", text):
        assert (ROOT / path.rstrip("./")).exists(), f"LICENSE names a missing path: {path}"


def test_readme_links_to_the_licence() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    targets = re.findall(r"\]\(([^)]+)\)", readme)
    assert any((ROOT / t).resolve() == (ROOT / "LICENSE").resolve() for t in targets)


def test_pyproject_does_not_claim_an_open_licence() -> None:
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert not _OPEN.search(str(meta.get("license", ""))), meta.get("license")
    assert not any(_OPEN.search(c) for c in meta.get("classifiers", []))
