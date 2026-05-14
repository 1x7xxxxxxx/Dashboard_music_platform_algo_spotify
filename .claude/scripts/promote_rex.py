#!/usr/bin/env python3
"""
Auto-promote validated REX drafts from `.claude/sessions/pending-rex.md`
into each target tool's `rex:` frontmatter block.

Runs as the second Stop hook after `draft_rex.py`. Promotes only drafts
that meet ALL of these conditions:
  - `validated: true`
  - `entry.issue` is non-empty and != "?"
  - `entry.fix` is non-empty and != "?"
  - `entry.date`, `entry.severity` valid per rex-format.md
  - target file exists under .claude/{agents,skills,commands,rules,hooks,scripts}

Unpromoted drafts (still pending validation) remain in pending-rex.md.
When all drafts promote, pending-rex.md is deleted.

Always exits 0 (non-blocking). Errors written to stderr — Claude Code
surfaces hook stderr to the user.

---
rex: []
---
"""
import ast
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    # Fail silently if PyYAML missing — hook must never block a session.
    sys.exit(0)


_PENDING_FILE = ".claude/sessions/pending-rex.md"
_ALLOWED_TARGET_DIRS = (
    ".claude/agents/",
    ".claude/skills/",
    ".claude/commands/",
    ".claude/rules/",
    ".claude/hooks/",
    ".claude/scripts/",
)
_VALID_SEVERITY = {"info", "warn", "crit"}

# Markdown section + fenced YAML block.
_BLOCK_RE = re.compile(
    r"^## (?P<path>\S+)\s*\n```yaml\s*\n(?P<yaml>.*?)\n```\s*$",
    re.MULTILINE | re.DOTALL,
)
# Frontmatter at top of .md file.
_MD_FM_RE = re.compile(r"\A(---\n)(.*?)(\n---\s*\n)", re.DOTALL)


def _is_valid_entry(entry: dict) -> tuple[bool, str]:
    """Return (ok, reason). Reason is empty if ok."""
    if not isinstance(entry, dict):
        return False, "entry is not a mapping"
    for k in ("date", "issue", "fix"):
        v = entry.get(k)
        if not v or v == "?":
            return False, f"missing/placeholder {k!r}"
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(entry.get("date", ""))):
        return False, "date not YYYY-MM-DD"
    sev = entry.get("severity", "info")
    if sev not in _VALID_SEVERITY:
        return False, f"invalid severity {sev!r}"
    if len(str(entry["issue"])) > 120:
        return False, "issue > 120 chars"
    if len(str(entry["fix"])) > 200:
        return False, "fix > 200 chars"
    return True, ""


def _format_entry_yaml(entry: dict, indent: str = "  ") -> str:
    """Render entry as a `- key: value` list item with 2-space indent."""
    keys_order = ["date", "issue", "fix", "severity", "ref"]
    lines = []
    first = True
    for k in keys_order:
        if k not in entry:
            continue
        v = entry[k]
        prefix = f"{indent}- " if first else f"{indent}  "
        # Quote string values (handles colons, hyphens, etc).
        if isinstance(v, str):
            v_repr = yaml.safe_dump(v, default_style='"').strip()
        else:
            v_repr = str(v)
        lines.append(f"{prefix}{k}: {v_repr}")
        first = False
    return "\n".join(lines)


def _inject_md(path: Path, entry: dict) -> tuple[bool, str]:
    """Append entry to rex: list in .md frontmatter. Return (ok, msg)."""
    text = path.read_text(encoding="utf-8")
    m = _MD_FM_RE.match(text)
    if not m:
        return False, "no frontmatter"
    fm_body = m.group(2)
    try:
        parsed = yaml.safe_load(fm_body) or {}
    except yaml.YAMLError as e:
        return False, f"frontmatter not valid YAML: {e}"
    if not isinstance(parsed, dict):
        return False, "frontmatter root is not a mapping"
    new_fm = _append_entry_to_yaml_block(fm_body, entry)
    if new_fm is None:
        return False, "could not locate rex: key in frontmatter"
    new_text = m.group(1) + new_fm + m.group(3) + text[m.end():]
    path.write_text(new_text, encoding="utf-8")
    return True, ""


def _inject_py(path: Path, entry: dict) -> tuple[bool, str]:
    """Append entry to rex: list inside .py docstring YAML block."""
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return False, f"file is not valid Python: {e}"
    if not (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        return False, "no module-level docstring"
    doc = tree.body[0].value
    docstring = doc.value
    yaml_block_re = re.compile(r"(---\n)(.*?)(\n---)", re.DOTALL)
    m = yaml_block_re.search(docstring)
    if not m:
        return False, "no YAML block (---...---) in docstring"
    new_yaml = _append_entry_to_yaml_block(m.group(2), entry)
    if new_yaml is None:
        return False, "could not locate rex: key in docstring YAML"
    new_docstring = (
        docstring[:m.start()] + m.group(1) + new_yaml + m.group(3)
        + docstring[m.end():]
    )
    # Replace the original docstring literal in src. Use the AST col_offset
    # to find the exact source span. ast.Constant nodes include end_col_offset
    # in py3.8+, but a simpler robust approach is to find and replace the
    # original string content, since the docstring is unique enough.
    old_literal = src[doc.col_offset:]
    # Find the closing triple-quote of the docstring relative to its start.
    # ast.get_source_segment is the right tool here.
    src_segment = ast.get_source_segment(src, doc)
    if src_segment is None:
        return False, "could not extract docstring source segment"
    # Build replacement: same quote style, new content.
    if src_segment.startswith('"""'):
        new_literal = f'"""{new_docstring}"""'
    elif src_segment.startswith("'''"):
        new_literal = f"'''{new_docstring}'''"
    else:
        return False, "docstring not triple-quoted"
    new_src = src.replace(src_segment, new_literal, 1)
    path.write_text(new_src, encoding="utf-8")
    return True, ""


def _append_entry_to_yaml_block(yaml_text: str, entry: dict) -> str | None:
    """Return yaml_text with entry appended to the rex: list, or None."""
    lines = yaml_text.split("\n")
    # Find rex: key. Accept 'rex:', 'rex: []', or 'rex:' followed by indented items.
    rex_idx = None
    for i, ln in enumerate(lines):
        if re.match(r"^rex\s*:", ln):
            rex_idx = i
            break
    if rex_idx is None:
        return None
    rex_line = lines[rex_idx]
    entry_block = _format_entry_yaml(entry)
    # Case 1: `rex: []` → replace with `rex:` + entry.
    if re.match(r"^rex\s*:\s*\[\s*\]\s*$", rex_line):
        lines[rex_idx] = "rex:"
        lines.insert(rex_idx + 1, entry_block)
        return "\n".join(lines)
    # Case 2: `rex:` with existing items below. Find end of items and append.
    if re.match(r"^rex\s*:\s*$", rex_line):
        # Scan downward; entries continue while line is indented or empty.
        j = rex_idx + 1
        while j < len(lines):
            ln = lines[j]
            if ln == "" or ln.startswith("  "):
                j += 1
                continue
            break
        lines.insert(j, entry_block)
        return "\n".join(lines)
    return None


def _inject(target_rel: str, entry: dict) -> tuple[bool, str]:
    path = Path(target_rel)
    if not path.exists():
        return False, f"target not found: {target_rel}"
    if not any(target_rel.startswith(d) for d in _ALLOWED_TARGET_DIRS):
        return False, f"target outside allowed dirs: {target_rel}"
    if path.suffix == ".md":
        return _inject_md(path, entry)
    if path.suffix == ".py":
        return _inject_py(path, entry)
    return False, f"unsupported suffix: {path.suffix}"


def main() -> int:
    pending = Path(_PENDING_FILE)
    if not pending.exists():
        return 0
    text = pending.read_text(encoding="utf-8")
    blocks = list(_BLOCK_RE.finditer(text))
    if not blocks:
        return 0

    promoted: list[str] = []
    kept_blocks: list[str] = []
    errors: list[str] = []

    for m in blocks:
        block_text = m.group(0)
        path = m.group("path")
        yaml_text = m.group("yaml")
        try:
            parsed = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            errors.append(f"{path}: YAML parse error — {e}")
            kept_blocks.append(block_text)
            continue
        if not isinstance(parsed, dict):
            errors.append(f"{path}: block root is not a mapping")
            kept_blocks.append(block_text)
            continue
        if not parsed.get("validated"):
            kept_blocks.append(block_text)
            continue
        entry = parsed.get("entry") or {}
        ok, reason = _is_valid_entry(entry)
        if not ok:
            kept_blocks.append(block_text)
            continue
        target = parsed.get("target") or path
        if not any(target.startswith(d) for d in _ALLOWED_TARGET_DIRS):
            errors.append(f"{target}: outside allowed dirs")
            kept_blocks.append(block_text)
            continue
        ok, msg = _inject(target, entry)
        if ok:
            promoted.append(target)
        else:
            errors.append(f"{target}: {msg}")
            kept_blocks.append(block_text)

    if kept_blocks:
        # Preserve the header (everything before the first `## `).
        first_block_start = blocks[0].start()
        header = text[:first_block_start]
        pending.write_text(header + "\n\n".join(kept_blocks) + "\n", encoding="utf-8")
    else:
        pending.unlink()

    if promoted:
        print(
            f"REX auto-promote: {len(promoted)} entry/entries injected "
            f"into {', '.join(promoted)}",
            file=sys.stderr,
        )
    for e in errors:
        print(f"REX auto-promote: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
