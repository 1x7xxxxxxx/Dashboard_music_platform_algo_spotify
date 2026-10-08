#!/usr/bin/env python3
"""
Curator — config self-improvement loop (consolidation + telemetry + lifecycle).

Ported in spirit from the `hermes` orchestration: the value is that the config
*improves each iteration* by noticing redundancy and dead weight. REPORT-ONLY —
it proposes, never mutates (the human validates, like /rex-promote). Three passes:

  1. Consolidation — parse every tool's `rex:` entries + the error-class catalogue,
     flag near-duplicate pairs (token-overlap) as umbrella-merge candidates.
  2. Telemetry — skills from the TRANSCRIPTS and `sessions/injections.jsonl` (read by
     usage_report.py); error-classes from `.claude/curator/usage.json`, DATED.
     R470 (2026-10-08): both used to come from usage.json. Its `skills` counter died on
     2026-07-28 (fbab253e removed the call in inject_context.py) and the report went on
     printing « audit-collectors: 6× · last 2026-06-19 » as if it were current; its
     `error_classes` counter is fed only by a local `make audit` and stood still from
     2026-09-27. A section now says when its source last moved, and a source still for
     more than _FROZEN_DAYS days says so in the report instead of passing for a measure.
  3. Lifecycle — flag skills never used (file older than --stale-days) and
     fixed/closed error-classes that never hit, as archive candidates. A name in
     `.claude/curator/pinned.txt` is exempt.

Reuses validate_rex.py (rex parsing) + audit_runner.py (class parsing) — no
re-implementation. Output is a markdown report to stdout.

Usage:  curator.py [--stale-days N] [--root .claude]

Type: Utility (Claude Code config)
Uses: validate_rex, audit_runner, usage_telemetry, usage_report, error-classes.md
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

_FROZEN_DAYS = 7

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

def skill_activity(data: dict) -> dict:
    """{skill: {invoked, injected, last}} from usage_report.read(). Pure.

    `invoked` = `Skill` tool calls in the transcripts; `injected` = files under
    `skills/<name>/` that inject_context.py logged. `last` = newest date of either.
    """
    out: dict = {}
    for name, n in (data.get("skills") or {}).items():
        rec = out.setdefault(name, {"invoked": 0, "injected": 0, "last": ""})
        rec["invoked"] += n
        rec["last"] = max(rec["last"], (data.get("last_seen") or {}).get(f"skill:{name}", "")[:10])
    inj = data.get("injections") or {}
    for f, n in (inj.get("counts") or {}).items():
        parts = f.split("/")
        if len(parts) < 3 or parts[0] != "skills":
            continue
        rec = out.setdefault(parts[1], {"invoked": 0, "injected": 0, "last": ""})
        rec["injected"] += n
        rec["last"] = max(rec["last"], (inj.get("last_seen") or {}).get(f, "")[:10])
    return out


def freshness(last: str, today: datetime | None = None) -> str:
    """One line saying when a telemetry source last moved — and if it stood still. Pure."""
    if not last:
        return "_source never recorded anything._"
    now = today or datetime.now(timezone.utc)
    try:
        age = (now - datetime.strptime(last[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)).days
    except ValueError:
        return f"_last record: {last!r} (unreadable date)._"
    if age > _FROZEN_DAYS:
        return (f"⚠️ **source frozen since {last[:10]} ({age} d)** — these counts describe "
                "that day, not this week.")
    return f"_last record: {last[:10]} ({age} d ago)._"


def _usage_report() -> dict:
    try:
        import usage_report
        return usage_report.read()
    except Exception as exc:  # noqa: BLE001 — a report-only pass must not crash the review
        return {"found": False, "error": f"{type(exc).__name__}: {exc}"}


def _telemetry(claude_root: Path, transcripts: dict | None = None) -> tuple[list[str], dict]:
    data = transcripts if transcripts is not None else _usage_report()
    lines: list[str] = []
    acts = skill_activity(data)
    lines.append("**skills** (transcripts + injections.jsonl — invoked / injected):")
    if not acts:
        lines.append(f"- none recorded{(' — ' + data['error']) if data.get('error') else ''}")
    for name, r in sorted(acts.items(), key=lambda kv: -(kv[1]["invoked"] + kv[1]["injected"])):
        lines.append(f"- {name}: {r['invoked']} invoked · {r['injected']} injected · last {r['last'] or '?'}")
    lines.append(freshness(max((r["last"] for r in acts.values()), default="")))
    usage: dict = {"skill_activity": acts}
    if usage_telemetry is None or not usage_telemetry.usage_path().exists():
        return lines + ["", "**error_classes**: no usage.json — run `make audit` to record one."], usage
    import json
    try:
        ec = json.loads(usage_telemetry.usage_path().read_text(encoding="utf-8")).get("error_classes", {})
    except (OSError, ValueError):
        return lines + ["", "**error_classes**: usage.json unreadable."], usage
    usage["error_classes"] = ec
    lines += ["", "**error_classes** (usage.json — fed only by a local `make audit`):"]
    for name, rec in sorted(ec.items(), key=lambda kv: kv[1].get("count", 0), reverse=True)[:10]:
        lines.append(f"- {name}: {rec.get('count', 0)}× · last {rec.get('last', '?')}"
                     f" · runs={rec.get('runs', 0)} hits={rec.get('hits', 0)}")
    lines.append(freshness(max((r.get("last", "") for r in ec.values()), default="")))
    return lines, usage


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

    # Skills never used and older than the staleness window. A skill is a DIRECTORY
    # (`skills/<name>/SKILL.md`): the flat `skills/*.md` glob this pass used matched only
    # the `*.rex.md` side files, so it judged no skill at all (R470).
    skill_usage = usage.get("skill_activity", {})
    stale_skills = []
    for sk in sorted((claude_root / "skills").glob("*/SKILL.md")):
        name = sk.parent.name
        if name in pinned:
            continue
        rec = skill_usage.get(name)
        age = (now - datetime.fromtimestamp(sk.stat().st_mtime, timezone.utc)).days
        if rec is None and age > stale_days:
            stale_skills.append(f"- {name} (never invoked nor injected, file {age}d old)")
        elif rec and (ds := _days_since(rec.get("last", ""))) is not None and ds > stale_days:
            stale_skills.append(f"- {name} (last used {ds}d ago)")
    if stale_skills:
        lines.append(f"**Skills not used in >{stale_days}d** (archive candidates — verify keywords first):")
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
    # Dated so a forgotten weekly review becomes VISIBLE (R171/R172, 2026-09-25):
    # « weekly » was a wish in SCHEDULE.md that nothing ever checked.
    try:
        (root / "curator" / "last-run").write_text(
            __import__("datetime").date.today().isoformat() + "\n", encoding="utf-8")
    except OSError:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
