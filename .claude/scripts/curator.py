#!/usr/bin/env python3
"""
Curator — config self-improvement loop (consolidation + telemetry + lifecycle).

Ported in spirit from the `hermes` orchestration: the value is that the config
*improves each iteration* by noticing redundancy and dead weight. REPORT-ONLY —
it proposes, never mutates (the human validates, like /rex-promote). Three passes:

  1. Consolidation — parse every tool's `rex:` entries + the error-class catalogue,
     flag near-duplicate pairs (token-overlap) as umbrella-merge candidates.
  2. Telemetry — read `.claude/curator/usage.json` (written by usage_telemetry via
     inject_context + audit_runner): most/least triggered skills & error-classes.
  3. Lifecycle — flag skills never auto-injected (file older than --stale-days) and
     fixed/closed error-classes that never hit, as archive candidates. A name in
     `.claude/curator/pinned.txt` is exempt.

Reuses validate_rex.py (rex parsing) + audit_runner.py (class parsing) — no
re-implementation. Output is a markdown report to stdout.

Usage:  curator.py [--stale-days N] [--root .claude]

Type: Utility (Claude Code config)
Uses: validate_rex, audit_runner, usage_telemetry, error-classes.md
Persists in: — (markdown report to stdout)

---
rex: []
---
"""
import argparse
import re
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

# Consolidation ast.parse()s every tool file; a stray invalid-escape in some
# docstring must not pollute the report. Keep the report clean.
warnings.filterwarnings("ignore", category=SyntaxWarning)

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

import audit_runner  # noqa: E402  — sibling module, parse_classes reuse
import validate_rex  # noqa: E402  — sibling module, rex parsing reuse

try:
    import usage_telemetry  # noqa: E402
except Exception:  # noqa: BLE001
    usage_telemetry = None

_STOP = frozenset(
    "the and for that with this from into when then than only also have were was are "
    "not but its was via per off out new add fix bug issue when while a an of to in on "
    "it is be by or as at no do so we re ll skip silent guard hook test class rule".split()
)
_TOKEN = re.compile(r"[a-z][a-z0-9_]{3,}")


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOP}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ── 1. Consolidation ─────────────────────────────────────────────────────────

def _collect_rex(claude_root: Path) -> list[tuple[str, set[str], str]]:
    """Return (tool_rel, token_set, summary) per rex entry across all tools."""
    out = []
    for path in sorted(validate_rex._iter_files(claude_root)):
        fm = (validate_rex._parse_md_frontmatter(path) if path.suffix == ".md"
              else validate_rex._parse_py_docstring_rex(path))
        if not fm or not isinstance(fm.get("rex"), list):
            continue
        rel = path.relative_to(claude_root)
        for e in fm["rex"]:
            if not isinstance(e, dict):
                continue
            text = f"{e.get('issue', '')} {e.get('fix', '')}"
            toks = _tokens(text)
            if toks:
                out.append((str(rel), toks, str(e.get("issue", ""))[:70]))
    return out


def _consolidation(claude_root: Path, threshold: float) -> list[str]:
    lines: list[str] = []
    rex = _collect_rex(claude_root)
    pairs = []
    for i in range(len(rex)):
        for j in range(i + 1, len(rex)):
            tool_a, ta, sa = rex[i]
            tool_b, tb, sb = rex[j]
            jac = _jaccard(ta, tb)
            if jac >= threshold:
                pairs.append((jac, tool_a, sa, tool_b, sb))
    pairs.sort(reverse=True)
    if pairs:
        lines.append(f"**{len(pairs)} near-duplicate REX pair(s)** (Jaccard ≥ {threshold:.2f}) — "
                     "consider an umbrella entry / shared rule:")
        for jac, ta, sa, tb, sb in pairs[:12]:
            lines.append(f"- `{jac:.2f}` {ta} «{sa}»  ⇄  {tb} «{sb}»")
    else:
        lines.append(f"No REX pair above Jaccard {threshold:.2f} — catalogue looks non-redundant.")

    # Error-class id overlap (shared significant tokens in the id itself).
    classes = audit_runner.parse_classes(
        (claude_root / "dev-docs/error-classes.md").read_text(encoding="utf-8")
    ) if (claude_root / "dev-docs/error-classes.md").exists() else []
    cls_pairs = []
    for i in range(len(classes)):
        for j in range(i + 1, len(classes)):
            a, b = classes[i]["id"], classes[j]["id"]
            jac = _jaccard(_tokens(a.replace("-", " ")), _tokens(b.replace("-", " ")))
            if jac >= 0.5:
                cls_pairs.append((jac, a, b))
    cls_pairs.sort(reverse=True)
    if cls_pairs:
        lines.append("")
        lines.append(f"**{len(cls_pairs)} error-class id(s) with overlapping themes** — possible merge:")
        for jac, a, b in cls_pairs[:8]:
            lines.append(f"- `{jac:.2f}` {a}  ⇄  {b}")
    return lines


# ── 2. Telemetry ─────────────────────────────────────────────────────────────

def _telemetry(claude_root: Path) -> tuple[list[str], dict]:
    if usage_telemetry is None:
        return ["usage_telemetry unavailable — skipping telemetry pass."], {}
    p = usage_telemetry.usage_path()
    if not p.exists():
        return ["No usage.json yet — telemetry accrues as hooks/audits run. "
                "(Run `make audit` + submit a few bug-keyword prompts to seed it.)"], {}
    import json
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["usage.json unreadable."], {}
    lines: list[str] = []
    for cat in ("skills", "error_classes"):
        rows = data.get(cat, {})
        if not rows:
            continue
        ranked = sorted(rows.items(), key=lambda kv: kv[1].get("count", 0), reverse=True)
        lines.append(f"**{cat}** (by trigger count):")
        for name, rec in ranked[:10]:
            extra = ""
            if cat == "error_classes":
                extra = f" · runs={rec.get('runs', 0)} hits={rec.get('hits', 0)}"
            lines.append(f"- {name}: {rec.get('count', 0)}× · last {rec.get('last', '?')}{extra}")
    return (lines or ["usage.json present but empty."]), data


# ── 3. Lifecycle ─────────────────────────────────────────────────────────────

def _days_since(date_str: str) -> int | None:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return (datetime.now(timezone.utc) - d).days


def _pinned(claude_root: Path) -> set[str]:
    f = claude_root / "curator/pinned.txt"
    if not f.exists():
        return set()
    return {ln.strip() for ln in f.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")}


def _lifecycle(claude_root: Path, usage: dict, stale_days: int) -> list[str]:
    lines: list[str] = []
    pinned = _pinned(claude_root)
    now = datetime.now(timezone.utc)

    # Skills never auto-injected and older than the staleness window.
    skill_usage = usage.get("skills", {})
    stale_skills = []
    for sk in sorted((claude_root / "skills").glob("*.md")):
        name = sk.stem
        if name in pinned:
            continue
        rec = skill_usage.get(name)
        age = (now - datetime.fromtimestamp(sk.stat().st_mtime, timezone.utc)).days
        if rec is None and age > stale_days:
            stale_skills.append(f"- {name} (never injected, file {age}d old)")
        elif rec and (ds := _days_since(rec.get("last", ""))) is not None and ds > stale_days:
            stale_skills.append(f"- {name} (last injected {ds}d ago)")
    if stale_skills:
        lines.append(f"**Skills not injected in >{stale_days}d** (archive candidates — verify keywords first):")
        lines.extend(stale_skills)

    # Fixed/closed error-classes that never hit → guard for a class that never recurs.
    cat_path = claude_root / "dev-docs/error-classes.md"
    if cat_path.exists():
        classes = audit_runner.parse_classes(cat_path.read_text(encoding="utf-8"))
        ec_usage = usage.get("error_classes", {})
        cold = []
        for c in classes:
            if c["id"] in pinned:
                continue
            if c["status"] in ("fixed", "closed", "resolved"):
                rec = ec_usage.get(c["id"], {})
                if rec.get("hits", 0) == 0 and rec.get("runs", 0) >= 1:
                    cold.append(f"- {c['id']} (status {c['status']}, 0 hits over {rec.get('runs')} runs)")
        if cold:
            lines.append("")
            lines.append("**Closed error-classes with 0 hits** (could archive — kept only as a guard):")
            lines.extend(cold)
    return lines or ["No stale skills or cold error-classes — lifecycle clean."]


def main() -> None:
    ap = argparse.ArgumentParser(description="Curator — consolidation + telemetry + lifecycle (report-only)")
    ap.add_argument("--root", type=Path, default=Path(".claude"))
    ap.add_argument("--stale-days", type=int, default=30)
    ap.add_argument("--threshold", type=float, default=0.55, help="Jaccard threshold for REX duplicates")
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.exists():
        print(f"error: {root} not found", file=sys.stderr)
        sys.exit(2)

    print("# Curator report\n")
    print("_Report-only — proposes, never mutates. Validate each item before acting._\n")

    print("## 1. Consolidation\n")
    print("\n".join(_consolidation(root, args.threshold)) + "\n")

    print("## 2. Telemetry\n")
    tel_lines, usage = _telemetry(root)
    print("\n".join(tel_lines) + "\n")

    print("## 3. Lifecycle\n")
    print("\n".join(_lifecycle(root, usage, args.stale_days)) + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
