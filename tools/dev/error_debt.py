#!/usr/bin/env python3
"""Which error classes to pay down first — and which ceilings could now be tightened.

Type: Utility
Uses: .claude/dev-docs/error-classes.md, .claude/dev-docs/error-class-health.json,
      tests/test_the_error_class_health_only_improves.py (its `_CEILINGS`, read by AST)
Triggers: `make error-debt`
Persists in: nothing — prints a work list

Why this exists
---------------
Measured 2026-09-25 on six consecutive commits: `guard_does_not_prove_itself` 306/414 and
`cause_unknown` 140 did not move once. The ratchets forbid a rise; nothing proposes a
fall, so the debt is frozen, not paid. Paying 306 guards is not a plan; paying the
classes that have ALREADY recurred is — a guard that does not prove itself on a class that
came back is the costliest hole there is.

Order: recurred and not self-proving (most recurrences first), then cause `unknown`.
Ceilings are NOT tightened here (code-critic, 2026-09-25: a ceiling that follows the last
measure would go red the day a corrected parser legitimately raises an under-counted
figure). The tool only PRINTS a ceiling above its measured value, so the manual gesture is
proposed instead of forgotten.

    python3 tools/dev/error_debt.py [N]
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CATALOGUE = _ROOT / ".claude/dev-docs/error-classes.md"
_HEALTH = _ROOT / ".claude/dev-docs/error-class-health.json"
_RATCHET = _ROOT / "tests/test_the_error_class_health_only_improves.py"
_HEAD = re.compile(r"^## ([a-z0-9][a-z0-9-]+)\s*$", re.M)
_RECUR = re.compile(r"^\s+- \d{4}-\d{2}-\d{2} \(récidive\):", re.M)


def recurrences(text: str) -> dict[str, int]:
    """{class id: number of `(récidive)` History lines}."""
    heads = list(_HEAD.finditer(text))
    out = {}
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out[h.group(1)] = len(_RECUR.findall(text, h.end(), end))
    return out


def work_list(classes: dict, recur: dict[str, int], n: int) -> list[tuple[str, str]]:
    ranked = []
    for cid, c in classes.items():
        r = recur.get(cid, 0)
        if r and c.get("seen_red") != "self-proving":
            ranked.append((0, -r, cid, f"récidivée {r}× — rendre le garde auto-prouvant "
                                       "(test_the_detector_sees_the_defect_it_is_written_for)"))
        elif c.get("cause_evidence") == "unknown":
            ranked.append((1, 0, cid, "cause `unknown` — lire le code, écrire read/measured"))
    return [(cid, why) for _, _, cid, why in sorted(ranked)[:n]]


def ceilings() -> dict[str, int]:
    tree = ast.parse(_RATCHET.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", None) == "_CEILINGS" for t in node.targets):
            return {k.value: v.value for k, v in zip(node.value.keys, node.value.values)
                    if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)}
    return {}


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    health = json.loads(_HEALTH.read_text(encoding="utf-8"))
    recur = recurrences(_CATALOGUE.read_text(encoding="utf-8"))
    todo = work_list(health["classes"], recur, n)
    print(f"▶ {len(todo)} classe(s) à traiter en premier (unité : 3 par séance)")
    for cid, why in todo:
        print(f"   {cid}\n      → {why}")
    holes = health["aggregate"]["holes"]
    slack = {k: (c, holes[k]) for k, c in ceilings().items() if k in holes and holes[k] < c}
    if slack:
        print("\n▶ plafonds resserrables À LA MAIN (tests/test_the_error_class_health_only_improves.py) :")
        for k, (c, v) in slack.items():
            print(f"   {k}: {c} → {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
