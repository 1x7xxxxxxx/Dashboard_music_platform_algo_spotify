#!/usr/bin/env python3
"""
Hook UserPromptSubmit — Domain-aware context injection.

Detects keywords in the user prompt and injects the matching skill / rule file
from .claude/skills/ or .claude/rules/ as a system-reminder block before
Claude reads the prompt.

THIS HOOK WAS A NO-OP FROM THE DAY IT WAS INSTALLED UNTIL 2026-07-17, and it is worth knowing why.

The generic payload ships `DOMAINS = {}` and delegates filling it to the installer's LAST LINE —
`setup-claude-code.sh:553`: "Next: fill in CLAUDE.md placeholders and configure inject_context.py
domains." Measured across the sibling repos, that echo has a **33% success rate** (4 of 6 deployments
left it empty). It is not inattention: it is a manual step at the end of a script nobody reads.

The cost here: this hook is the ONLY injector of `.claude/rules/` and `.claude/skills/`, so an empty
DOMAINS silently orphaned BOTH trees — including any rule your CLAUDE.md calls
mandatory — such a rule reaches the model NEVER.

The fix is `_discover_domains()` (ported from the Dashboard sibling, itself from msdr where it was
born of a REX: "a new skill needs a hook edit"). A file that declares `keywords:` in its frontmatter
SELF-WIRES. That makes `DOMAINS = {}` non-fatal and turns :553 from a dependency into advice.

Always exits 0 — never blocks.

---
rex:
  - date: 2026-07-17
    issue: "DOMAINS={} shipped by the payload made this hook a no-op on every prompt since install; it is the only injector of rules/ and skills/, so both trees were orphaned. 4 of 6 deployments of this payload had the same empty dict."
    fix: "Ported _discover_domains() (Dashboard/msdr): a skill or rule declaring `keywords:` self-wires, so a forgotten post-install step can no longer silence the hook. Scans rules/ too, which no sibling does."
    ref: "CLAUDE.md · setup-claude-code.sh:553"
    severity: crit
---
"""
import glob
import json
import os
import re
import sys

# ── Path resolution ───────────────────────────────────────────────────────────

_HOOK_DIR    = os.path.dirname(os.path.abspath(__file__))   # .claude/hooks/
_CLAUDE_DIR  = os.path.dirname(_HOOK_DIR)                    # .claude/


# ── Domain → (keywords, source folder, file) ─────────────────────────────────
#
# Each entry maps trigger keywords (lowercased substring match) to a file under
# .claude/skills/ or .claude/rules/. ≥_MIN_HITS keywords in the prompt → inject.


def _discover_domains() -> dict[str, tuple[list[str], str, str]]:
    """Self-wiring: any skill OR rule declaring `keywords: a, b, c` registers itself.

    Two deliberate differences from the siblings this is ported from:
      · it scans `rules/` as well as `skills/`. Dashboard hardcodes "skills" and msdr's variant is
        skills-only 2-tuples — so NEITHER can inject a rule, and a safety rule is a rule.
        The 3-tuple design of this payload was the more capable of the three; this keeps it.
      · the caller MERGES this with the hardcoded set rather than `discovered or _FALLBACK`
        (Dashboard:107). With `or`, the first file to declare a keyword silently discards the whole
        fallback dict — a trap shaped exactly like the bug this hook is being repaired for.
    """
    found: dict[str, tuple[list[str], str, str]] = {}
    for folder in ("workflows", "skills", "rules"):
        base = os.path.join(_CLAUDE_DIR, folder)
        # Flat `<folder>/x.md` AND spec layout `<folder>/x/SKILL.md`. Scanning only
        # the flat form was silent data loss: after the spec-layout migration the
        # skills live one directory down, so a top-level glob finds an empty tree
        # and reports no error. Measured 2026-07-28 — 6 of 8 repos injected
        # NOTHING on a bug-shaped prompt while every board showed them green.
        paths = sorted(glob.glob(os.path.join(base, "*.md"))
                       + glob.glob(os.path.join(base, "*", "*.md")))
        for path in paths:
            try:
                with open(path, encoding="utf-8") as f:
                    head = f.read(2048)          # keywords live in the top frontmatter block
            except OSError:
                continue
            m = re.search(r"^keywords:\s*(.+)$", head, re.M)
            if not m:
                continue
            kws = [k.strip().lower() for k in m.group(1).split(",") if k.strip()]
            if not kws:
                continue
            # `fn` is relative to `folder` so load_file() can join it either way.
            fn = os.path.relpath(path, base)
            stem = os.path.dirname(fn) or os.path.splitext(os.path.basename(fn))[0]
            found[stem] = (kws, folder, fn)
    return found


# Curated entries win on a key collision — a hand-tuned keyword set beats a discovered one.
_HARDCODED: dict[str, tuple[list[str], str, str]] = {}

DOMAINS: dict[str, tuple[list[str], str, str]] = {**_discover_domains(), **_HARDCODED}

_MAX_DOMAINS = 3     # Max files injected per prompt (context budget)
_MAX_LINES   = 120   # Max lines per file (truncate heavy files)
_MIN_HITS    = 2     # Minimum keyword matches for a domain to trigger

_DOMAIN_PRIORITY: list[str] = list(DOMAINS.keys())


def load_file(folder: str, filename: str, max_lines: int = _MAX_LINES) -> str | None:
    """Read a skill/rule file, truncate to max_lines. Returns None if missing."""
    path = os.path.join(_CLAUDE_DIR, folder, filename)
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            truncated = lines[:max_lines]
            truncated.append(
                f"\n… [truncated at {max_lines} lines — full file at .claude/{folder}/{filename}]\n"
            )
            return "".join(truncated).strip()
        return "".join(lines).strip()
    except OSError:
        return None


# ── Detection ─────────────────────────────────────────────────────────────────

def detect_domains(prompt: str) -> list[str]:
    if not DOMAINS:
        return []
    prompt_lower = prompt.lower()
    matched = []
    for domain, (keywords, _, _) in DOMAINS.items():
        hit_count = sum(1 for kw in keywords if kw in prompt_lower)
        if hit_count >= _MIN_HITS:
            matched.append(domain)
    matched.sort(key=lambda d: _DOMAIN_PRIORITY.index(d) if d in _DOMAIN_PRIORITY else 99)
    return matched[:_MAX_DOMAINS]


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    prompt = data.get("prompt", "")
    if not prompt:
        sys.exit(0)

    detected = detect_domains(prompt)
    if not detected:
        sys.exit(0)

    blocks: list[str] = []
    for domain in detected:
        _, folder, filename = DOMAINS[domain]
        content = load_file(folder, filename)
        if content:
            blocks.append(content)

    if blocks:
        print("\n".join(blocks))

    sys.exit(0)


if __name__ == "__main__":
    main()


# ── Example DOMAINS entries (delete or adapt) ────────────────────────────────
#
# Web app project:
#
#   DOMAINS = {
#       "api": (
#           ["route", "endpoint", "fastapi", "express", "flask",
#            "request", "response", "status code"],
#           "rules", "api.md",
#       ),
#       "database": (
#           ["postgres", "mysql", "sqlite", "schema", "migration",
#            "query", "table", "column"],
#           "rules", "database.md",
#       ),
#       "debug": (
#           ["debug", "traceback", "stack trace", "exception",
#            "ne fonctionne pas", "broken", "silent fail"],
#           "skills", "systematic-debugging.md",
#       ),
#   }
#
# Data / ML project:
#
#   DOMAINS = {
#       "ml": (
#           ["train", "model", "feature", "scikit", "torch", "shap",
#            "drift", "mlflow", "registry"],
#           "skills", "mlops.md",
#       ),
#       "data": (
#           ["pipeline", "extract", "transform", "load", "etl",
#            "dataset", "schema validation"],
#           "skills", "data-engineering.md",
#       ),
#   }
