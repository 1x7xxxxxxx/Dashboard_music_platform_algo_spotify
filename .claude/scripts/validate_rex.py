#!/usr/bin/env python3
"""
.claude REX validator — enforces the rex: block schema from .claude/rules/rex-format.md.

Walks .claude/{agents,skills,commands,rules}/*.md, .claude/skills/*/SKILL.md,
.claude/hooks/*.py, .claude/scripts/*.py. For each tool, verifies:
- presence of a 'rex:' key in the frontmatter (.md) or docstring YAML block (.py)
- well-formed entries: ISO date, issue ≤ 120 chars, fix ≤ 200 chars, severity in allowlist

Exit codes:
- 0: OK (malformed entries = 0, missing keys irrelevant in non-strict mode)
- 1: malformed entries found, or missing keys in --strict mode
- 2: I/O or config error (missing .claude/, PyYAML not installed)

---
rex: []
---
"""
import argparse
import ast
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: PyYAML required (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)


_SCAN_DIRS: list[tuple[str, str]] = [
    ("agents",   "*.md"),
    ("skills",   "*.md"),
    ("commands", "*.md"),
    ("rules",    "*.md"),
    ("hooks",    "*.py"),
    ("scripts",  "*.py"),
]

_FM_RE = re.compile(r"\A---\n(.*?)\n---\s*\n", re.DOTALL)
_DOCSTRING_FM_RE = re.compile(r"---\n(.*?)\n---", re.DOTALL)
_VALID_SEVERITY = {"info", "warn", "crit"}


def _parse_md_frontmatter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = _FM_RE.match(text)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None


def _parse_py_docstring_rex(path: Path) -> dict | None:
    src = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    docstring = ast.get_docstring(tree) or ""
    m = _DOCSTRING_FM_RE.search(docstring)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None


def _validate_rex_entries(entries, source: str) -> list[str]:
    errors: list[str] = []
    if entries is None:
        return errors  # rex: (null) treated as empty
    if not isinstance(entries, list):
        return [f"{source}: 'rex' must be a list, got {type(entries).__name__}"]
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"{source}: rex[{i}] must be a dict")
            continue
        for key in ("date", "issue", "fix"):
            if key not in entry or not entry[key]:
                errors.append(f"{source}: rex[{i}] missing required key '{key}'")
        date = str(entry.get("date", ""))
        if date and not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            errors.append(f"{source}: rex[{i}].date must be YYYY-MM-DD, got {date!r}")
        if len(str(entry.get("issue", ""))) > 120:
            errors.append(f"{source}: rex[{i}].issue > 120 chars")
        if len(str(entry.get("fix", ""))) > 200:
            errors.append(f"{source}: rex[{i}].fix > 200 chars")
        sev = entry.get("severity")
        if sev is not None and sev not in _VALID_SEVERITY:
            errors.append(f"{source}: rex[{i}].severity must be one of {sorted(_VALID_SEVERITY)}, got {sev!r}")
    return errors


def _iter_files(claude_root: Path):
    for subdir, pattern in _SCAN_DIRS:
        d = claude_root / subdir
        if not d.exists():
            continue
        yield from d.glob(pattern)
    skills_dir = claude_root / "skills"
    if skills_dir.exists():
        for sub in skills_dir.iterdir():
            if sub.is_dir():
                skill_md = sub / "SKILL.md"
                if skill_md.exists():
                    yield skill_md


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate REX blocks across .claude/ tools")
    ap.add_argument("--strict", action="store_true", help="Exit 1 on missing 'rex' key")
    ap.add_argument("--root", type=Path, default=Path(".claude"), help="Path to .claude/ directory")
    args = ap.parse_args()

    claude_root = args.root.resolve()
    if not claude_root.exists():
        print(f"error: {claude_root} not found", file=sys.stderr)
        sys.exit(2)

    missing: list[str] = []
    errors: list[str] = []
    valid_count = 0

    for path in sorted(_iter_files(claude_root)):
        rel = path.relative_to(claude_root)
        fm = _parse_md_frontmatter(path) if path.suffix == ".md" else _parse_py_docstring_rex(path)

        if fm is None or "rex" not in fm:
            missing.append(str(rel))
            continue

        entry_errs = _validate_rex_entries(fm["rex"], str(rel))
        if entry_errs:
            errors.extend(entry_errs)
        else:
            valid_count += 1

    print(f"REX validator — {valid_count} tool(s) OK, "
          f"{len(missing)} without rex key, {len(errors)} entry error(s)")

    if missing:
        print("\nMissing rex: (add `rex: []` to frontmatter / docstring block):")
        for m in missing[:30]:
            print(f"  {m}")
        if len(missing) > 30:
            print(f"  ... and {len(missing) - 30} more")

    if errors:
        print("\nEntry errors:")
        for e in errors[:30]:
            print(f"  {e}")
        if len(errors) > 30:
            print(f"  ... and {len(errors) - 30} more")

    if errors:
        sys.exit(1)
    if missing and args.strict:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
