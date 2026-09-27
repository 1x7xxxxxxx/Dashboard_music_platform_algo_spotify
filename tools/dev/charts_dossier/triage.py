#!/usr/bin/env python3
"""The arbitration table: every chart to act on, grouped by CAUSE, with both verdicts.

Type: Utility
Uses: review.yaml, <dossier>/fiches.json, <dossier>/inventory.json (R207 twins)
Triggers: `make charts-review`
Persists in: <dossier>/tri.md — the page the owner arbitrates BEFORE anything enters the roadmap

R204 (2026-09-26). One roadmap row per CAUSE, not per chart: the CTR scale is one defect on
four figures, « an absence written as zero » one defect on eight (CLAUDE.md rule 21 — sweep by
family). A chart enters the table when it has a cause, when the owner commented on it, or when
the owner's verdict differs from mine; a disagreement is flagged, never resolved silently.

Priority, in order: a probably WRONG number (my confidence ≤ 2) → the Meta question → the
app's robustness → the rest.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _priority(entries: list[dict]) -> tuple[int, str]:
    if any(e.get("c", 5) <= 2 and e.get("v") == "corriger" for e in entries):
        return 1, "P2 — chiffre probablement faux"
    if any(e.get("role") == "meta" for e in entries):
        return 2, "Question Meta"
    if any(e.get("role") in ("archi", "prediction") for e in entries):
        return 3, "Robustesse / prédiction"
    return 4, "Lisibilité"


def table(review: dict, fiche_of: dict[str, int]) -> list[dict]:
    """[{cause, priority, label, rows:[…], disagreements}] sorted by priority. Pure."""
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for key, r in review.items():
        r = r or {}
        owner_v = r.get("owner_v")
        if not (r.get("cause") or r.get("owner") or (owner_v and owner_v != r.get("v"))):
            continue
        groups[r.get("cause") or "sans-cause"].append({**r, "key": key,
                                                         "fiche": fiche_of.get(key)})
    out = []
    for cause, entries in groups.items():
        rank, label = _priority(entries)
        out.append({"cause": cause, "rank": rank, "label": label,
                    "rows": sorted(entries, key=lambda e: e["fiche"] or 0),
                    "disagreements": sum(1 for e in entries
                                         if e.get("owner_v") and e["owner_v"] != e.get("v"))})
    return sorted(out, key=lambda g: (g["rank"], -len(g["rows"]), g["cause"]))


def likely_twins(inventory: list[dict], fiche_of: dict[str, int]) -> list[list[str]]:
    """Figures of one page with the same (sources, measure) fingerprint — R207. Pure.

    The same fingerprint as `tests/test_no_two_figures_on_a_page_share_a_fingerprint.py`,
    shown to the owner at review time: a declared twin passes the test and still deserves
    a second look here."""
    groups: dict = collections.defaultdict(list)
    for e in inventory:
        if e.get("kind") == "figure" and e.get("measure") and e.get("sources"):
            groups[(e["site"].split(":")[0], tuple(e["sources"]),
                    tuple(e["measure"]))].append(e["key"])
    return [sorted(v, key=lambda k: fiche_of.get(k, 0)) for v in groups.values() if len(v) > 1]


def render(groups: list[dict], twins: list[list[str]] | None = None,
           fiche_of: dict[str, int] | None = None) -> str:
    lines = ["# Tri des retours — dossier des graphiques (R204)", "",
             "Une ligne de roadmap par CAUSE. Arbitre chaque cause : **retenir**, **reporter** "
             "ou **abandonner**. Rien n'entre dans la roadmap avant ton arbitrage.", ""]
    for g in groups:
        flag = f" · ⚠️ {g['disagreements']} désaccord(s)" if g["disagreements"] else ""
        lines += [f"## {g['cause']} — {g['label']} · {len(g['rows'])} graphique(s){flag}", "",
                  "| fiche | question | mon verdict | ton verdict | ton commentaire |",
                  "|---|---|---|---|---|"]
        for e in g["rows"]:
            lines.append(f"| {e['fiche'] or '?'} | {e.get('q', '')} | {e.get('v', '')} | "
                         f"{e.get('owner_v') or '—'} | {e.get('owner') or '—'} |")
        lines += ["", "Arbitrage : ☐ retenir · ☐ reporter · ☐ abandonner", ""]
    if twins:
        lines += ["## Doublons probables — même page, mêmes sources, même mesure (R207)", ""]
        for pair in twins:
            lines.append("- " + " ↔ ".join(
                f"fiche {(fiche_of or {}).get(k, '?')} ({k})" for k in pair))
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    import yaml
    out = Path(argv[1]) if len(argv) > 1 else None
    if out is None:
        print("usage: triage.py <dossier-dir>", file=sys.stderr)
        return 2
    review = yaml.safe_load((HERE / "review.yaml").read_text(encoding="utf-8"))
    fiches = json.loads((out / "fiches.json").read_text(encoding="utf-8"))
    fiche_of = {v: int(k) for k, v in fiches.items()}
    groups = table(review, fiche_of)
    inv_path = out / "inventory.json"
    inventory = json.loads(inv_path.read_text(encoding="utf-8")) if inv_path.exists() else []
    twins = likely_twins(inventory, fiche_of)
    (out / "tri.md").write_text(render(groups, twins, fiche_of), encoding="utf-8")
    print(f"✅ {out / 'tri.md'} : {len(groups)} cause(s), "
          f"{sum(len(g['rows']) for g in groups)} graphique(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
