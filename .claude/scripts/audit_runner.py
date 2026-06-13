#!/usr/bin/env python3
"""
Error-class signature runner — single executable source of truth.

Parses every class in `.claude/dev-docs/error-classes.md`, extracts its
`signature` / `kind` / `status`, and runs each signature.cmd. The catalogue
contract: a signature exits NON-ZERO when the anti-pattern is present (a "hit").

This replaces the hand-synced grep recipes in the Makefile `audit:` target, so
a class added to the catalogue is swept automatically (no catalogue↔Makefile
drift). `kind: deterministic` classes are CI-safe (0 false positives) and may
block; `kind: heuristic` classes run nightly, non-blocking (manual triage).

Usage:
  audit_runner.py --deterministic   # only kind: deterministic; exit 1 on any hit (CI blocking)
  audit_runner.py [--all]           # every class; exit 1 on any hit (nightly; caller tolerates with || true)
  audit_runner.py --list            # list id · kind · status, no run

Type: Utility (Claude Code config)
Uses: error-classes.md, subprocess
Persists in: — (report to stdout + exit code)

---
rex:
  - date: 2026-06-13
    issue: "make audit hardcoded ~6 grep signatures while error-classes.md catalogued 21 → drift; new classes never swept"
    fix: "audit_runner.py parses error-classes.md signatures and runs them; Makefile + CI delegate to it (catalogue = single source of truth)"
    ref: "DEVLOG#2026-06-13-suite22"
    severity: warn
---
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]            # .claude/scripts/ -> repo root
_CATALOGUE = _REPO / ".claude/dev-docs/error-classes.md"

# Documentation scaffolding sections that look like a class header but are not runnable.
_SKIP_IDS = {"class-id"}
_KEBAB = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def parse_classes(text: str) -> list[dict]:
    """Return one dict per real class: {id, kind, status, signature}."""
    out = []
    # Split on level-2 headers at line start; first chunk is the preamble (no class).
    for sec in re.split(r"^## ", text, flags=re.M)[1:]:
        lines = sec.splitlines()
        cid = lines[0].strip()
        if cid.lower() in _SKIP_IDS or not _KEBAB.match(cid):
            continue
        body = "\n".join(lines[1:])
        # First backtick-delimited span after "- signature:"; tolerate trailing prose
        # after the closing backtick (e.g. "`pytest …` (DB-gated: …)"). Signatures
        # never contain an internal backtick, so [^`]+ is exact.
        sig = re.search(r"^- signature:\s*`([^`]+)`", body, flags=re.M)
        if not sig:
            continue  # narrative sections (Index, Contract, Per-class schema) have no signature
        kind = re.search(r"^- kind:\s*(\w+)", body, flags=re.M)
        status = re.search(r"^- status:\s*([\w-]+)", body, flags=re.M)
        out.append({
            "id": cid,
            "kind": (kind.group(1) if kind else "heuristic").lower(),
            "status": (status.group(1) if status else "open").lower(),
            "signature": sig.group(1).strip(),
        })
    return out


def run_signature(sig: str) -> tuple[bool, str]:
    """Run one signature from the repo root. Returns (hit, output)."""
    proc = subprocess.run(
        sig, shell=True, cwd=_REPO,
        capture_output=True, text=True, timeout=300,
    )
    hit = proc.returncode != 0
    return hit, (proc.stdout + proc.stderr).strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Run error-class signatures from the catalogue")
    ap.add_argument("--deterministic", action="store_true",
                    help="Run only kind: deterministic classes; exit 1 on any hit (CI-safe)")
    ap.add_argument("--all", action="store_true", help="Run every class (default)")
    ap.add_argument("--list", action="store_true", help="List classes and exit")
    args = ap.parse_args()

    if not _CATALOGUE.exists():
        print(f"❌ catalogue not found: {_CATALOGUE}", file=sys.stderr)
        sys.exit(2)

    classes = parse_classes(_CATALOGUE.read_text(encoding="utf-8"))
    if not classes:
        print("❌ no classes parsed — check error-classes.md format", file=sys.stderr)
        sys.exit(2)

    if args.list:
        for c in classes:
            print(f"  {c['id']:<32} {c['kind']:<13} {c['status']}")
        print(f"\n{len(classes)} classes "
              f"({sum(c['kind'] == 'deterministic' for c in classes)} deterministic)")
        sys.exit(0)

    selected = [c for c in classes if c["kind"] == "deterministic"] if args.deterministic else classes
    mode = "deterministic" if args.deterministic else "all"
    print(f"▶ audit_runner ({mode}): {len(selected)} signatures\n")

    hits = []
    for c in selected:
        hit, output = run_signature(c["signature"])
        mark = "⚠ HIT" if hit else "✅"
        print(f"  {mark}  {c['id']}  [{c['kind']}/{c['status']}]")
        if hit:
            hits.append(c["id"])
            for line in output.splitlines()[:6]:
                print(f"        {line}")

    if hits:
        print(f"\n⚠ {len(hits)} class(es) with hits: {', '.join(hits)}")
        if args.deterministic:
            print("  (deterministic → CI-blocking: these are real, fix or re-triage the signature)")
        else:
            print("  (heuristic sweep → manual triage; nightly non-blocking)")
        sys.exit(1)
    print("\n✅ audit clean")
    sys.exit(0)


if __name__ == "__main__":
    main()
