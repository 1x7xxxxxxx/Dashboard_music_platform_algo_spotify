#!/usr/bin/env python3
"""Has the error-class debt moved in the last N days? Exit 1 when it has not.

Type: Utility
Uses: git history of .claude/dev-docs/error-classes.md + error_class_health.holes_of (R345:
      the series is recomputed from the catalogue, the JSON is no longer versioned)
Triggers: .github/workflows/security-nightly.yml, job `debt-trend`
Persists in: nothing

Measured 2026-09-25 (R169): `guard_does_not_prove_itself` 306/414 and `cause_unknown` 140 did
not move on six consecutive commits. The ratchets forbid a RISE; nothing noticed a debt that
stopped FALLING — it was found by reading a report by hand. This mails it instead: when none
of the tracked counters fell over the window, the debt is frozen, and a frozen debt is the
state R169 was opened to end.

    python3 tools/dev/error_debt_trend.py [days]     (default 14)
    python3 tools/dev/error_debt_trend.py --series [N]   the holes at the last N catalogue
                                                         revisions (make error-health-history)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_FILE = ".claude/dev-docs/error-classes.md"
TRACKED = ("guard_does_not_prove_itself", "cause_unknown", "seen_red_unknown")


def _holes_at(rev: str) -> dict | None:
    """The hole counters of the catalogue AS IT WAS at `rev` — declared fields only, no
    replay. ⚠️ `guards_ref_missing` reads guard files on TODAY's disk: it is not tracked."""
    r = subprocess.run(["git", "-C", str(_ROOT), "show", f"{rev}:{_FILE}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    sys.path.insert(0, str(_ROOT / "tools" / "dev"))
    import error_class_health as h
    return h.holes_of(h._declared(r.stdout.replace("\r\n", "\n"))) or None


def _rev_before(days: int) -> str | None:
    """The snapshot at the start of the window — or, when the file is YOUNGER than the
    window, its oldest snapshot. Without that fallback the first nightly (2026-09-26) said
    « nothing to compare » for a file born eight days earlier: silent for two weeks."""
    r = subprocess.run(["git", "-C", str(_ROOT), "rev-list", "-1", f"--before={days}.days",
                        "HEAD", "--", _FILE], capture_output=True, text=True)
    if r.stdout.strip():
        return r.stdout.strip()
    r = subprocess.run(["git", "-C", str(_ROOT), "rev-list", "--reverse", "HEAD", "--", _FILE],
                       capture_output=True, text=True)
    revs = r.stdout.split()
    return revs[0] if revs else None


def frozen(then: dict, now: dict) -> bool:
    """No tracked counter fell. Pure: tested on fabricated snapshots.

    Only counters present in BOTH snapshots are compared: an older schema without a key
    must not read as « it was 0, so it did not fall »."""
    common = [k for k in TRACKED if k in then and k in now]
    return bool(common) and all(now[k] >= then[k] for k in common)


def series(n: int) -> int:
    """One line per catalogue revision, newest first: the tracked holes as they were."""
    r = subprocess.run(["git", "-C", str(_ROOT), "log", f"-{n}", "--format=%h %ad",
                        "--date=short", "--", _FILE], capture_output=True, text=True, check=True)
    for line in r.stdout.splitlines():
        rev = line.split()[0]
        holes = _holes_at(rev) or {}
        print(line, "  ".join(f"{k}={holes.get(k)}" for k in TRACKED))
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--series":
        return series(int(sys.argv[2]) if len(sys.argv) > 2 else 60)
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    rev = _rev_before(days)
    then, now = (_holes_at(rev) if rev else None), _holes_at("HEAD")
    if then is None or now is None:
        print(f"❔ pas d'instantané de {_FILE} il y a {days} jours — rien à comparer (ce "
              "n'est PAS une dette qui bouge)")
        return 0
    for k in TRACKED:
        print(f"   {k}: {then.get(k)} → {now.get(k)}")
    if frozen(then, now):
        print(f"❌ aucun compteur de dette n'a baissé en {days} jours — la dette est figée "
              "(R169 : `make error-debt` donne les classes à traiter en premier)")
        return 1
    print(f"✅ la dette a baissé en {days} jours")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
