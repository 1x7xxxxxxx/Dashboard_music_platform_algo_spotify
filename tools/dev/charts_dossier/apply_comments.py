#!/usr/bin/env python3
"""Pour the owner's dictated comments into review.yaml — one per chart, by FICHE number.

Type: Utility
Uses: review.yaml, <dossier>/fiches.json (fiche number → review key, written by main.py)
Triggers: `make charts-review COMMENTS=<file>`
Persists in: tools/dev/charts_dossier/review.yaml (fields `owner_v`, `owner` only)

R204 (2026-09-26). The owner reads the PDF, dictates, and sends the transcription; I turn it
into a small YAML — `42: {v: corriger, texte: "…"}` — and this script writes it next to MY
grade, never over it. It refuses a fiche number the dossier does not have, and a verdict
outside the set: a comment attached to the wrong chart is worse than a comment lost, because
nobody rereads what already looks filed.

    python3 tools/dev/charts_dossier/apply_comments.py <comments.yaml> <dossier-dir>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVIEW = HERE / "review.yaml"
VERDICTS = {"garder", "corriger", "fusionner", "retirer", "a-trancher"}


def plan(comments: dict, fiches: dict[int, str]) -> tuple[dict[str, dict], list[str]]:
    """({review key: {owner_v, owner}}, errors). Pure: nothing is written if an error exists."""
    out, errors = {}, []
    for raw_no, c in (comments or {}).items():
        try:
            no = int(raw_no)
        except (TypeError, ValueError):
            errors.append(f"« {raw_no} » n'est pas un numéro de fiche")
            continue
        if no not in fiches:
            errors.append(f"fiche {no} inconnue (le dossier en compte {len(fiches)})")
            continue
        c = c or {}
        v = str(c.get("v", "")).strip().lower().replace("à trancher", "a-trancher")
        if v not in VERDICTS:
            errors.append(f"fiche {no} : verdict « {c.get('v')} » hors de {sorted(VERDICTS)}")
            continue
        out[fiches[no]] = {"owner_v": v, "owner": str(c.get("texte", "")).strip()}
    return out, errors


def write(review_text: str, updates: dict[str, dict]) -> str:
    """Insert or replace `owner_v` / `owner` inside each block, textually — my own lines,
    the comments and the order of the file are kept. Pure."""
    lines, out, cur = review_text.split("\n"), [], None
    for ln in lines:
        m = re.match(r"^(\S.*):$", ln)
        if m:
            cur = m.group(1).strip('"')
        if cur in updates and re.match(r"^  (owner_v|owner): ", ln):
            continue                                 # replaced below, never duplicated
        out.append(ln)
        if cur in updates and re.match(r"^  v: ", ln):
            u = updates[cur]
            text = u["owner"].replace("\\", "\\\\").replace('"', '\\"')
            out += [f"  owner_v: {u['owner_v']}", f'  owner: "{text}"']
    return "\n".join(out)


def main(argv: list[str]) -> int:
    import yaml
    if len(argv) != 3:
        print(__doc__.split("\n\n")[-1], file=sys.stderr)
        return 2
    comments = yaml.safe_load(Path(argv[1]).read_text(encoding="utf-8")) or {}
    fiches = {int(k): v for k, v in
              json.loads((Path(argv[2]) / "fiches.json").read_text(encoding="utf-8")).items()}
    updates, errors = plan(comments, fiches)
    if errors:
        print("❌ rien n'est écrit :\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    REVIEW.write_text(write(REVIEW.read_text(encoding="utf-8"), updates), encoding="utf-8")
    print(f"✅ {len(updates)} avis versé(s) dans review.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
