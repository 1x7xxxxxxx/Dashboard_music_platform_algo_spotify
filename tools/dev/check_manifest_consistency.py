#!/usr/bin/env python3
"""
Type: Utility
Uses: pyproject.toml, requirements.txt, uv.lock
Depends on: stdlib only (tomllib, re)
Persists in: nothing (read-only check)
Triggers: Makefile `check-manifest`, pre-commit local hook, ci.yml blocking step

Assert exact-pin parity for any package pinned `==` in >=2 of
pyproject.toml / requirements.txt / uv.lock. Exit 1 + a MANIFEST-DRIFT line per
offender on disagreement; exit 0 when consistent. Closes error class
`streamlit-pin-drift` (see .claude/dev-docs/error-classes.md).

---
rex: []
---
"""

import re
import sys
import tomllib
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_PIN_RE = re.compile(r"^([A-Za-z0-9._-]+)(?:\[[^\]]+\])?\s*==\s*([A-Za-z0-9._!+-]+)")


def _norm(name: str) -> str:
    """PEP-503 name normalization."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def _parse_pyproject(path: Path) -> dict[str, str]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    pins: dict[str, str] = {}
    for req in data.get("project", {}).get("dependencies", []):
        m = _PIN_RE.match(req.strip())
        if m:
            pins[_norm(m.group(1))] = m.group(2)
    return pins


def _parse_requirements(path: Path) -> dict[str, str]:
    # requirements.txt is not TOML and ships a UTF-8 BOM; strip BOM + CR.
    text = path.read_text(encoding="utf-8-sig").replace("\r", "")
    pins: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].split(";", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = _PIN_RE.match(line)
        if m:
            pins[_norm(m.group(1))] = m.group(2)
    return pins


def _parse_uvlock(path: Path) -> dict[str, str]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return {
        _norm(p["name"]): p["version"]
        for p in data.get("package", [])
        if "name" in p and "version" in p
    }


def _drift(sources: dict[str, dict[str, str]]) -> list[str]:
    names: set[str] = set()
    for pins in sources.values():
        names |= pins.keys()
    offenders: list[str] = []
    for name in sorted(names):
        present = {src: pins[name] for src, pins in sources.items() if name in pins}
        if len(present) >= 2 and len(set(present.values())) > 1:
            cells = " ".join(
                f"{src}={sources[src].get(name, '—')}" for src in sources
            )
            offenders.append(f"MANIFEST-DRIFT {name}  {cells}")
    return offenders


def main() -> int:
    try:
        sources = {
            "pyproject": _parse_pyproject(_REPO / "pyproject.toml"),
            "requirements": _parse_requirements(_REPO / "requirements.txt"),
            "uv.lock": _parse_uvlock(_REPO / "uv.lock"),
        }
    except (FileNotFoundError, OSError, tomllib.TOMLDecodeError) as e:
        print(f"manifest-consistency: cannot read manifests: {e}", file=sys.stderr)
        return 2
    offenders = _drift(sources)
    if offenders:
        for line in offenders:
            print(line, file=sys.stderr)
        print(
            f"{len(offenders)} package(s) drift between manifests. "
            "Fix: align the pins, then run `uv lock`.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
