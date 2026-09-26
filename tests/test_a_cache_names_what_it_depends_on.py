"""A `setup-uv` cache says which file it is keyed on — never the action's default.

Type: Sub
Uses: .github/ (the `jobs:` of every YAML file — a composite action's `runs.steps` is not read ; none uses setup-uv today)
Depends on: nothing
Persists in: nothing

Class `a-major-upgrade-that-moves-a-default`: `astral-sh/setup-uv` v4 keyed its cache on
`**/uv.lock`, v10 on `**/*requirements*.txt`. This repository installs with
`uv sync --frozen`, which installs ONLY what `uv.lock` says — after the bump, the cache
was invalidated by a file that does not decide what is installed, and not by the one
that does. A cache keyed on an unwritten default moves with every major. The class
signature was a one-line `python3 -c`; this file asks the same question and proves it.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_GITHUB = Path(__file__).resolve().parents[1] / ".github"


def unkeyed_caches(document: dict) -> list[str]:
    """`job[step]` of every `setup-uv` step that enables its cache without naming
    `cache-dependency-glob`. Pure."""
    out = []
    for name, job in ((document or {}).get("jobs") or {}).items():
        for n, step in enumerate((job or {}).get("steps") or []):
            if "setup-uv" not in str((step or {}).get("uses", "")):
                continue
            with_ = (step or {}).get("with") or {}
            if with_.get("enable-cache") and "cache-dependency-glob" not in with_:
                out.append(f"{name}[{n}]")
    return out


def test_every_uv_cache_names_its_key() -> None:
    files = sorted(_GITHUB.rglob("*.y*ml"))
    assert files, "no workflow found under .github — the scan sees nothing"
    offenders = [f"{p.relative_to(_GITHUB).as_posix()} → {hit}" for p in files
                 for hit in unkeyed_caches(yaml.safe_load(p.read_text(encoding="utf-8")))]
    assert not offenders, (
        f"{offenders} : `setup-uv` active son cache sans `cache-dependency-glob`. La clé "
        "est alors le DÉFAUT de l'action, qui a changé entre v4 (`uv.lock`) et v10 "
        "(`*requirements*.txt`). Écrire `cache-dependency-glob: uv.lock`.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the step after the v10 bump — cache enabled, no key — is named; the
    step that names `uv.lock`, a disabled cache, and a step of another action with the
    same inputs, are not."""
    doc = {"jobs": {
        "test": {"steps": [
            {"uses": "actions/checkout@v4"},
            {"uses": "astral-sh/setup-uv@v6", "with": {"enable-cache": True}}]},
        "lint": {"steps": [
            {"uses": "astral-sh/setup-uv@v6",
             "with": {"enable-cache": True, "cache-dependency-glob": "uv.lock"}},
            {"uses": "astral-sh/setup-uv@v6", "with": {"enable-cache": False}},
            {"uses": "actions/setup-python@v5", "with": {"enable-cache": True}}]}}}
    assert unkeyed_caches(doc) == ["test[1]"]
