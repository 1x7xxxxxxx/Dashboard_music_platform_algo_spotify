#!/usr/bin/env python3
"""
.claude REX validator — enforces the rex: block schema from .claude/rules/rex-format.md.

Walks .claude/{agents,skills,commands,rules}/*.md, .claude/skills/*/SKILL.md,
.claude/hooks/*.py, .claude/scripts/*.py. For each tool, verifies:
- presence of a 'rex:' key in the frontmatter (.md) or docstring YAML block (.py)
- well-formed entries: ISO date, issue ≤ 350 chars, fix ≤ 400 chars, severity in allowlist
  (raised 2026-06-04 from 120/200 — real ops REX lessons legitimately exceed the terse limit)

Exit codes:
- 0: OK (malformed entries = 0, missing keys irrelevant in non-strict mode)
- 1: malformed entries found, or missing keys in --strict mode
- 2: I/O or config error (missing .claude/, PyYAML not installed)

---
rex:
  - date: 2026-06-04
    issue: "Limites issue ≤120 / fix ≤200 trop serrées pour des REX ops légitimement riches (bridge-nf-call, network_mode-host DNS, sudo-stdin-pipe) → 11 entrées en erreur, faisaient échouer test_full_bootstrap_is_rex_valid"
    fix: "Limites relevées à issue ≤350 / fix ≤400 (+ rex-format.md). Non-destructif : on garde le savoir ops au lieu de charcuter les entrées. Repack payload requis pour propager au bootstrap."
    ref: "DEVLOG#2026-06-04 (PM6)"
    severity: info
  - date: 2026-07-23
    issue: "The colocated <tool>.rex.md archives landed inside the directories _iter_files() globs, so rotated lessons would have (a) escaped schema validation entirely — a moved lesson is still a lesson — and (b) entered the tool denominator of the REX coverage KPI as files that can never carry a rex: key."
    fix: "Excluded *.rex.md from _iter_files() and added _iter_archives(): archives are validated against the same entry schema and reported as archived_lessons (+24), never counted as tools. Same defect class as the workflows/ blind spot of 2026-07-22 — a coverage % is only as honest as the set it divides by."
    ref: "DEVLOG#2026-07-23 (suite 2) · 8e8ab6c"
    severity: warn
  - date: 2026-08-03
    issue: "_DOCSTRING_FM_RE matched an unanchored `---\\n`, so an RST section underline inside a module docstring opened a false frontmatter block. yaml.safe_load then raised on the prose and the tool was reported as having NO rex key. select_tests.py carried a correct `rex: []` the whole time; --strict exited 1 and named the wrong fix."
    fix: "Anchored the delimiter to a line that is exactly `---` (^...$ with MULTILINE). Guarded by test_the_rex_parser_survives_rst_underlines, seen red on the old regex."
    ref: "roadmap-two-files-2026-08-03"
    severity: crit
  - date: 2026-09-05
    issue: "Ce validateur est une etape BLOQUANTE de ci.yml et n'avait aucun
      exemplaire dans .pre-commit-config.yaml. Le commit 8176e97 a livre deux
      champs `issue` de 376 et 399 caracteres pour un plafond de 350 : commit
      vert sur le poste, huit runs CI consecutifs rouges sur main, decouverts
      treize heures plus tard par mail."
    fix: "Hook local `validate-rex` ajoute (files ^.claude/, pass_filenames false,
      0,6 s, sans reseau), et tests/test_the_rex_gate_runs_before_the_push.py garde
      la paire des deux cotes en LISANT le YAML, pas le texte : le commentaire du
      hook nomme lui-meme le script, donc un grep resterait vert apres suppression.
      Classe ci-gate-with-no-local-counterpart."
    ref: "error-classes#ci-gate-with-no-local-counterpart"
    severity: warn
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
    ("agents",    "*.md"),
    ("skills",    "*.md"),
    ("commands",  "*.md"),
    ("rules",     "*.md"),
    ("hooks",     "*.py"),
    ("scripts",   "*.py"),
    # ADDED 2026-07-22. `inject_context.py:91` self-wires tools from ("skills", "rules", "workflows")
    # — so a workflow IS an injectable tool — but this list omitted `workflows`, and so did
    # `tests/test_claude_config.py`. Consequence measured that day: `bug-resolution.md` had been
    # injected **35 times** (usage_report INJECTIONS), the third most-fired injectable in the repo,
    # and it could not carry a `rex:` block. The workflow whose whole job is to turn a bug into a
    # recorded lesson was the one tool structurally unable to record one.
    # The printed line "71 tool(s) OK … 20/71 carry a LESSON" was true of what it scanned and read as
    # coverage of the tool surface. It was not: a whole tree sat outside the denominator. Same shape
    # as `roadmap_stats` counting `- [ ]` while `- [~]` items sat unticked, and as I6 asserting a hole
    # two pieces of work had already closed — a green number whose denominator omits the unscanned.
    # `tests/test_rex_covers_every_injectable.py` now derives this list from the INJECTOR, so a tree
    # added there can never again be silently unvalidated here.
    ("workflows", "*.md"),
]

_FM_RE = re.compile(r"\A---\n(.*?)\n---\s*\n", re.DOTALL)

# `^...$` with MULTILINE: the delimiter must be a line that is EXACTLY `---`.
# Without the anchors this read `---\n` anywhere, and an RST section underline
# (`Pourquoi cet outil existe` over `-------------------------`) ends in three
# dashes and a newline — so the regex opened its "frontmatter" mid-underline,
# handed the prose that followed to yaml.safe_load, got a ScannerError, and
# reported the tool as having NO rex block at all. Measured 2026-08-03 on
# `scripts/select_tests.py`, whose `rex: []` was present and correct the whole
# time. A parser that reports absence when it means "I could not parse" sends
# the reader to add something that is already there.
_DOCSTRING_FM_RE = re.compile(r"^---\n(.*?)\n---[ \t]*$", re.DOTALL | re.MULTILINE)
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
        if len(str(entry.get("issue", ""))) > 350:
            errors.append(f"{source}: rex[{i}].issue > 350 chars")
        if len(str(entry.get("fix", ""))) > 400:
            errors.append(f"{source}: rex[{i}].fix > 400 chars")
        sev = entry.get("severity")
        if sev is not None and sev not in _VALID_SEVERITY:
            errors.append(f"{source}: rex[{i}].severity must be one of {sorted(_VALID_SEVERITY)}, got {sev!r}")
    return errors


def _iter_files(claude_root: Path):
    for subdir, pattern in _SCAN_DIRS:
        d = claude_root / subdir
        if not d.exists():
            continue
        # `*.rex.md` are colocated REX ARCHIVES (rotated overflow — see rex-format.md §Archive), not
        # tools: they carry no `keywords:`, are never injected, and must not be counted in the tool
        # denominator. Their entries are validated separately (`_iter_archives`).
        yield from (p for p in d.glob(pattern) if not p.name.endswith(".rex.md"))
    # `skills/<name>/SKILL.md` is deliberately NOT yielded as a tool.
    #
    # Its frontmatter is parsed by the harness at the start of EVERY session, so
    # a key outside the SKILL.md spec is paid for on every session for a history
    # nobody reads at runtime. The same decision removed skills/ from the
    # installer's INJECT_REX pass; this is the reading half of it, and the two
    # must agree or an install writes a key the validator then demands forever.
    #
    # The REX convention still binds hooks, scripts, agents, commands and rules —
    # everything above — because none of those is re-parsed per session.
    # A skill's history belongs in a colocated `<name>.rex.md` archive, which
    # `_iter_archives` already validates.


def _iter_archives(claude_root: Path):
    """Colocated `<tool>.rex.md` REX archives — validated for schema, but not tools."""
    for subdir, _ in _SCAN_DIRS:
        d = claude_root / subdir
        if d.exists():
            yield from d.glob("*.rex.md")


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
    with_lesson = 0

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
            if fm["rex"]:                       # a non-empty list = a lesson was actually written
                with_lesson += 1

    # Colocated archives: same schema, but they are not tools (no `rex:`-key requirement, not counted
    # in the tool denominator). A malformed ARCHIVED lesson must still fail the build — a rotated entry
    # is a real lesson, just moved.
    archived_lessons = 0
    for path in sorted(_iter_archives(claude_root)):
        fm = _parse_md_frontmatter(path)
        rel = path.relative_to(claude_root)
        if fm is None or "rex" not in fm:
            errors.append(f"{rel}: a `.rex.md` archive must carry a `rex:` block")
            continue
        errors.extend(_validate_rex_entries(fm["rex"], str(rel)))
        archived_lessons += len(fm["rex"] or [])

    print(f"REX validator — {valid_count} tool(s) OK, "
          f"{len(missing)} without rex key, {len(errors)} entry error(s)")

    # THE HONEST LINE. "N tool(s) OK" was the lie: this validator checks that the `rex:` KEY exists,
    # not that a LESSON does, so `rex: []` scores as OK and --strict exits 0. It printed "45 tool(s)
    # OK" while 87% of the corpus carried nothing — and rex-format.md documents the SAME state one
    # cycle earlier (40/44 empty), with the guard green throughout. Printing the real ratio does not
    # make the build red; it makes the number impossible to not-see. That is MEASURE-THEN-ANNOUNCE
    # applied to the validator itself, and it costs two lines.
    total = valid_count + len(errors)
    if total:
        pct = 100 * with_lesson / total
        print(f"               — {with_lesson}/{total} carry a LESSON ({pct:.0f}%); "
              f"the rest are `rex: []` (valid, and empty)")
    if archived_lessons:
        print(f"               — + {archived_lessons} lesson(s) rotated into colocated `.rex.md` "
              f"archives (validated, not double-counted)")

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
