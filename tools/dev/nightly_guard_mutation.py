#!/usr/bin/env python3
"""Mutate, every night, the guards changed this week — and name the ones nothing turns red.

Type: Utility
Uses: tools/dev/mutate_guards.py (try_mutations), git log
Triggers: .github/workflows/security-nightly.yml, job `guard-mutation`
Persists in: nothing — prints a verdict per guard, exit 1 when one is suspect

Rule 15ter says « mutate a new guard before believing it », and until 2026-09-26 that was a
gesture done by hand. The same day, doing it by hand for ~30 guards found three real defects
in guards (one crashed instead of judging, one proof pointed at a renamed test, two
mutations stayed green without embodying the defect). A gesture that finds that much is a
machine's job.

What it can say, honestly: a guard that stays GREEN on every mutation it was given is a
guard nobody has seen bite — it is flagged. What it cannot say: that a RED mutation embodies
the class (a renamed identifier often breaks a guard for a trivial reason). So red is never
reported as proof; only the absence of any red is reported, as a suspicion to read.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutate_guards as mg  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
_MAX_GUARDS = 12          # each guard costs up to 7 pytest runs; the nightly is not unbounded


def changed_guards(days: int = 2) -> list[str]:
    """Guard files ADDED in the window — rule 15ter is about NEW guards (168 were merely
    modified in the week of 2026-09-26: mutating all of them is a day, not a night)."""
    out = subprocess.run(["git", "-C", str(_ROOT), "log", f"--since={days}.days", "--diff-filter=A", "--name-only",
                          "--format=", "--", "tests/test_*.py"],
                         capture_output=True, text=True).stdout.split()
    seen, keep = set(), []
    for rel in out:
        if rel not in seen and (_ROOT / rel).is_file():
            seen.add(rel)
            keep.append(rel)
    return keep


def verdict(result: dict) -> str | None:
    """A suspicion to report, or None. Pure: tested without running anything."""
    if "skipped" in result:
        return "rouge AVANT toute mutation — le garde ne passe pas sur l'arbre tel quel"
    if "aucune" in result and result["aucune"] > 0:
        return f"vert sur les {result['aucune']} mutation(s) essayées — personne ne l'a vu mordre"
    if "epuise" in result:
        return f"vert sur {result['epuise']} mutations, budget épuisé — personne ne l'a vu mordre"
    return None          # a red mutation, or no applicable site (nothing to conclude)


def main() -> int:
    guards = changed_guards()
    dropped = max(0, len(guards) - _MAX_GUARDS)
    guards = guards[:_MAX_GUARDS]
    print(f"▶ {len(guards)} garde(s) ajouté(s) en 2 jours (le job tourne chaque nuit)"
          + (f" — {dropped} non mutés cette nuit (plafond {_MAX_GUARDS})" if dropped else ""))
    suspects = 0
    for rel in guards:
        v = verdict(mg.try_mutations(_ROOT / rel))
        suspects += v is not None
        print(f"   {'✗' if v else '✓'} {rel}" + (f" — {v}" if v else ""))
    print(f"{'❌' if suspects else '✅'} {suspects} garde(s) à relire")
    return 1 if suspects else 0


if __name__ == "__main__":
    raise SystemExit(main())
