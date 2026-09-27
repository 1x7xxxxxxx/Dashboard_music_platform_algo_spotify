#!/usr/bin/env python3
"""Pour the owner's dictated comments into review.yaml — one per chart, by FICHE number.

Type: Utility
Uses: review.yaml, <dossier>/fiches.json (fiche number → review key, written by main.py)
Triggers: `make charts-review COMMENTS=<file>`
Persists in: tools/dev/charts_dossier/review.yaml (fields `owner_v`, `owner` only),
             tools/dev/charts_dossier/actions.yaml (R240 — `valide`, `actions`)

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
ACTIONS = HERE / "actions.yaml"
VERDICTS = {"garder", "corriger", "fusionner", "retirer", "a-trancher"}
WHO = {"toi", "moi"}


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


def plan_actions(comments: dict, fiches: dict[int, str]) -> tuple[dict[str, dict], list[str]]:
    """R240 — ({review key: {valide, actions}}, errors). Pure.

    `valide: true` is the owner's « on garde », nothing left to do: the fiche goes to the END
    of the dossier. Each action says WHO does it (`toi` / `moi`) and, for mine, the roadmap id
    that carries it — the dossier marks it done when that row is archived.
    """
    import re as _re
    out, errors = {}, []
    for raw_no, c in (comments or {}).items():
        try:
            no = int(raw_no)
        except (TypeError, ValueError):
            continue                                  # already reported by plan()
        if no not in fiches:
            continue
        c = c or {}
        acts = []
        for a in c.get("actions") or []:
            if a.get("qui") not in WHO or not str(a.get("texte", "")).strip():
                errors.append(f"fiche {no} : action {a!r} — qui ∈ {sorted(WHO)} et un texte")
                continue
            rid = a.get("rid")
            if rid is not None and not _re.fullmatch(r"R\d+", str(rid)):
                errors.append(f"fiche {no} : id de roadmap « {rid} » invalide")
                continue
            acts.append({"qui": a["qui"], "texte": str(a["texte"]).strip(),
                         **({"rid": str(rid)} if rid else {})})
        if c.get("valide") and acts:
            errors.append(f"fiche {no} : validée ET porteuse d'actions — l'un ou l'autre")
            continue
        if c.get("valide") or acts:
            out[fiches[no]] = {"valide": bool(c.get("valide")), "actions": acts}
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
    actions, act_errors = plan_actions(comments, fiches)
    errors += act_errors
    if errors:
        print("❌ rien n'est écrit :\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    REVIEW.write_text(write(REVIEW.read_text(encoding="utf-8"), updates), encoding="utf-8")
    current = (yaml.safe_load(ACTIONS.read_text(encoding="utf-8")) or {}) if ACTIONS.exists() else {}
    current.update(actions)
    ACTIONS.write_text("# R240 — generated by apply_comments.py from the owner's dictated review.\n"
                       + yaml.safe_dump(current, allow_unicode=True, sort_keys=False, width=100),
                       encoding="utf-8")
    print(f"✅ {len(updates)} avis versé(s) dans review.yaml, {len(actions)} fiche(s) dans actions.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
