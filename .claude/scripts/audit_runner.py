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

# Best-effort usage telemetry (curator self-improvement loop). Defensive: a broken
# sidecar must never fail the audit / CI sweep.
try:
    from usage_telemetry import record as _telemetry_record
except Exception:  # noqa: BLE001 — telemetry is optional
    def _telemetry_record(*_a, **_k):
        return None

_REPO = Path(__file__).resolve().parents[2]            # .claude/scripts/ -> repo root
_CATALOGUE = _REPO / ".claude/dev-docs/error-classes.md"

# Documentation scaffolding sections that look like a class header but are not runnable.
_SKIP_IDS = {"class-id"}
_KEBAB = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def parse_all_headers(text: str) -> list[dict]:
    """Return one dict per class header (kebab id), signature-bearing OR NOT.

    {id, kind, status, signature|None}. Unlike the old parser this does NOT drop
    signature-less (prose) classes — the `--coverage` meta-guard needs to SEE them
    (a catalogued-but-un-swept class is the exact blind spot that let the 2026-07-07
    Alembic prose REX re-fire). The id is the FIRST token of the header, so a
    date/ADR suffix (`## foo (2026-07-11, ADR-047)`) no longer breaks kebab matching.
    """
    out = []
    for sec in re.split(r"^## ", text, flags=re.M)[1:]:
        lines = sec.splitlines()
        cid = (lines[0].strip().split() or [""])[0]      # first token → tolerate "(date, ADR)" suffix
        if cid.lower() in _SKIP_IDS or not _KEBAB.match(cid):
            continue
        body = "\n".join(lines[1:])
        # First backtick-delimited span after "- signature:"; tolerate trailing prose
        # after the closing backtick. Signatures never contain an internal backtick.
        # A `—` placeholder (no real command) counts as NO signature.
        sig = re.search(r"^- signature:\s*`([^`]+)`", body, flags=re.M)
        sig_val = sig.group(1).strip() if sig else None
        if sig_val in ("—", "-", ""):
            sig_val = None
        kind = re.search(r"^- kind:\s*([\w-]+)", body, flags=re.M)
        status = re.search(r"^- status:\s*([\w-]+)", body, flags=re.M)
        out.append({
            "id": cid,
            "kind": (kind.group(1) if kind else ("heuristic" if sig_val else "")).lower(),
            "status": (status.group(1) if status else "open").lower(),
            "signature": sig_val,
        })
    return out


def parse_classes(text: str) -> list[dict]:
    """Runnable classes only (those carrying a real `- signature:` command)."""
    return [c for c in parse_all_headers(text) if c["signature"]]


def run_signature(sig: str) -> tuple[bool, str]:
    """Run one signature from the repo root. Returns (hit, output)."""
    proc = subprocess.run(
        sig, shell=True, cwd=_REPO,
        capture_output=True, text=True, timeout=300,
    )
    hit = proc.returncode != 0
    return hit, (proc.stdout + proc.stderr).strip()


_OPTOUT_KINDS = {"manual", "runtime-manual"}  # acknowledged as intentionally NOT auto-swept


def _coverage(headers: list[dict]) -> int:
    """Meta-guard: every catalogued class must be GUARDED (has a runnable `- signature:`) OR
    carry an explicit opt-out `- kind:` ∈ {manual (needs host access), runtime-manual (no static
    footprint)}. A class with NEITHER (prose with no kind, or a kind that implies auto-sweep like
    `deterministic` but no signature) is UNGUARDED — the catalogue silently accreting un-swept
    prose is the structural blind spot. Exit 1 on any unguarded class."""
    unguarded = [h for h in headers if h["signature"] is None and h["kind"] not in _OPTOUT_KINDS]
    guarded = [h for h in headers if h["signature"]]
    optout = [h for h in headers if h["signature"] is None and h["kind"] in _OPTOUT_KINDS]
    total = len(headers)
    pct = (100 * len(guarded) // total) if total else 0
    print(f"▶ coverage: {total} classes — {len(guarded)} guarded ({pct}%) · "
          f"{len(optout)} manual/runtime opt-out · {len(unguarded)} UNGUARDED")
    if unguarded:
        print("\n❌ UNGUARDED classes (add a `- signature:` OR `- kind: runtime-manual`):")
        for h in unguarded:
            print(f"      {h['id']}  [kind={h['kind'] or '∅'}/{h['status']}]")
        return 1
    print("\n✅ coverage complete — every class is guarded or explicitly runtime-manual")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Run error-class signatures from the catalogue")
    ap.add_argument("--deterministic", action="store_true",
                    help="Run only kind: deterministic classes; exit 1 on any hit (CI-safe)")
    ap.add_argument("--static", action="store_true",
                    help="Run deterministic classes whose signature is grep-only (no pytest) — "
                         "for the IPC daily sweep (no PG / test env)")
    ap.add_argument("--coverage", action="store_true",
                    help="Meta-guard: fail if any class lacks a signature AND isn't runtime-manual")
    ap.add_argument("--all", action="store_true", help="Run every class (default)")
    ap.add_argument("--list", action="store_true", help="List classes and exit")
    args = ap.parse_args()

    if not _CATALOGUE.exists():
        print(f"❌ catalogue not found: {_CATALOGUE}", file=sys.stderr)
        sys.exit(2)

    text = _CATALOGUE.read_text(encoding="utf-8")
    headers = parse_all_headers(text)
    classes = [c for c in headers if c["signature"]]
    if not headers:
        print("❌ no classes parsed — check error-classes.md format", file=sys.stderr)
        sys.exit(2)

    if args.coverage:
        sys.exit(_coverage(headers))

    if args.list:
        skipped = [h for h in headers if not h["signature"]]
        for c in classes:
            print(f"  {c['id']:<44} {c['kind']:<15} {c['status']}")
        print(f"\n{len(classes)} runnable classes "
              f"({sum(c['kind'] == 'deterministic' for c in classes)} deterministic) · "
              f"{len(skipped)} without a signature")
        if skipped:
            print("  no-signature (coverage-tracked): "
                  + ", ".join(f"{h['id']}[{h['kind'] or '∅'}]" for h in skipped))
        sys.exit(0)

    # kind: manual / runtime-manual = never auto-run (need host access, or no static footprint).
    if args.static:
        selected = [c for c in classes
                    if c["kind"] == "deterministic" and "pytest" not in c["signature"]]
        mode = "static"
    elif args.deterministic:
        selected = [c for c in classes if c["kind"] == "deterministic"]
        mode = "deterministic"
    else:
        selected = [c for c in classes if c["kind"] not in ("manual", "runtime-manual")]
        mode = "all"
    print(f"▶ audit_runner ({mode}): {len(selected)} signatures\n")

    hits = []
    for c in selected:
        hit, output = run_signature(c["signature"])
        _telemetry_record("error_classes", c["id"], hit=hit)  # curator usage signal
        mark = "⚠ HIT" if hit else "✅"
        print(f"  {mark}  {c['id']}  [{c['kind']}/{c['status']}]")
        if hit:
            hits.append(c["id"])
            for line in output.splitlines()[:6]:
                print(f"        {line}")

    if hits:
        print(f"\n⚠ {len(hits)} class(es) with hits: {', '.join(hits)}")
        if args.deterministic or args.static:
            print("  (deterministic → CI-blocking: these are real, fix or re-triage the signature)")
        else:
            print("  (heuristic sweep → manual triage; nightly non-blocking)")
        sys.exit(1)
    print("\n✅ audit clean")
    sys.exit(0)


if __name__ == "__main__":
    main()
