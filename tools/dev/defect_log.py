#!/usr/bin/env python3
"""`make defect-log` — what the recorded symptoms say: one line per defect, not per sighting.

Type: Utility
Uses: .claude/sessions/defects.jsonl (written by .claude/scripts/defect_capture.py)
Depends on: nothing but the log
Persists in: .claude/sessions/defect-log.json and defect-log.md (gitignored — the repo is public)

R315 (2026-09-29). The log holds SYMPTOMS; this reads them as defects:
- `green`     a red test whose own file was later run green (the same node, not "some commit");
- `transient` red, then green in the SAME session — the red of an edit in progress;
- `open`      still no green after its last red;
- a fingerprint red on ≥ 2 distinct days with a green in between comes BACK: it is proposed
  for the catalogue's existing `recurrence:<d1>,<d2>` admission ticket (rule 15). Proposed
  only — a fingerprint groups by where a symptom surfaced, not by why (rule 20), so a human
  confirms the same cause before writing a class (code-critic, R315).
Refusals (hooks, pre-commit) are counted by reason: they measure MY repeated gestures.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSIONS = ROOT / ".claude" / "sessions"
LOG = SESSIONS / "defects.jsonl"


def load(path: Path = LOG) -> list[dict]:
    """The distinct events: a FAILED line shown twice in one tool output counts once."""
    seen, out = set(), []
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = (e.get("fingerprint"), e.get("session"), e.get("ts"), tuple(e.get("files", ())))
        if key not in seen:
            seen.add(key)
            out.append(e)
    return sorted(out, key=lambda e: e.get("ts", ""))


def _greens(events: list[dict]) -> list[tuple[str, str, set[str]]]:
    return [(e["ts"], e["session"], set(e.get("files") or ())) for e in events
            if e["kind"] == "test_green" and e.get("scope") in ("files", "suite")]


def _covers(files: set[str], node: str) -> bool:
    return not files or node.split("::", 1)[0] in files  # scope `suite`: no file named


def classify(events: list[dict]) -> list[dict]:
    """One row per red fingerprint. Pure."""
    greens = _greens(events)
    reds: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        if e["kind"] in ("test_red", "traceback"):
            reds[e["fingerprint"]].append(e)
    rows = []
    for fp, seen in reds.items():
        node = fp.removeprefix("test:")
        after = [g for g in greens if g[0] > seen[-1]["ts"] and fp.startswith("test:")
                 and _covers(g[2], node)]
        days = sorted({e["ts"][:10] for e in seen})
        returned = [d for d in days[1:] if any(
            g[0][:10] < d and g[0] > seen[0]["ts"] and _covers(g[2], node) for g in greens)]
        # R336: only a red on a CLEAN tree proposes a ticket; one on work in progress, or on
        # a tree nobody can vouch for (old events, backfill), is listed without one.
        clean = {e["ts"][:10] for e in seen if e.get("tree") == "clean"}
        back = [d for d in returned if d in clean]
        status = "open"
        if after:
            status = "transient" if len(days) == 1 and after[0][1] == seen[-1]["session"] \
                and len({e["session"] for e in seen}) == 1 else "green"
        rows.append({
            "fingerprint": fp, "kind": seen[0]["kind"], "status": status,
            "first_seen": seen[0]["ts"], "last_seen": seen[-1]["ts"], "days": days,
            "sightings": len(seen), "excerpt": seen[-1]["excerpt"],
            "recurrence_proposal": f"recurrence:{days[0]},{back[0]}" if back else None,
            "returned_unvouched": [d for d in returned if d not in clean],
        })
    return sorted(rows, key=lambda r: (r["recurrence_proposal"] is None, r["status"] != "open",
                                       r["last_seen"]), reverse=False)


def refusals(events: list[dict]) -> list[tuple[str, int, list[str]]]:
    """Refusals by reason, most repeated first: the gestures I keep making."""
    by: dict[str, list[str]] = defaultdict(list)
    for e in events:
        if e["kind"] in ("hook_refusal", "precommit_refusal"):
            by[e["fingerprint"]].append(e["ts"][:10])
    return sorted(((fp, len(d), sorted(set(d))) for fp, d in by.items()),
                  key=lambda r: -r[1])


def render(rows: list[dict], refused: list[tuple[str, int, list[str]]]) -> str:
    count = defaultdict(int)
    for r in rows:
        count[r["status"]] += 1
    proposals = [r for r in rows if r["recurrence_proposal"]]
    out = ["# Journal des défauts (généré par `make defect-log`, ne pas éditer)", "",
           f"{len(rows)} défaut(s) : " + ", ".join(f"{v} {k}" for k, v in sorted(count.items())),
           "", "## Revenus après un vert — billet `recurrence:` à confirmer", ""]
    out += [f"- `{r['fingerprint']}` — {r['recurrence_proposal']} ({r['sightings']} vues)"
            for r in proposals] or ["(aucun)"]
    unvouched = [r for r in rows if not r["recurrence_proposal"] and r.get("returned_unvouched")]
    out += ["", "## Revenus après un vert sur un arbre EN COURS ou inconnu — aucun billet (R336)", ""]
    out += [f"- `{r['fingerprint']}` — {', '.join(r['returned_unvouched'])}"
            for r in unvouched] or ["(aucun)"]
    out += ["", "## Sans vert prouvé depuis (le nœud n'a pas été relancé seul ni dans la suite complète)", ""]
    out += [f"- `{r['fingerprint']}` — vu le {r['last_seen'][:10]}"
            for r in rows if r["status"] == "open"] or ["(aucun)"]
    out += ["", "## Refus répétés (hooks, pre-commit) — mes gestes", "",
            "| refus | fois | jours |", "|---|---|---|"]
    out += [f"| `{fp}` | {n} | {', '.join(d)} |" for fp, n, d in refused if n >= 2]
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    events = load()
    if not events:
        print(f"ℹ️  aucun symptôme enregistré dans {LOG.relative_to(ROOT)} "
              "(le hook Stop l'écrit à chaque réponse ; rattrapage : "
              "python3 .claude/scripts/defect_capture.py --backfill <transcript>)")
        return 0
    rows, refused = classify(events), refusals(events)
    (SESSIONS / "defect-log.json").write_text(
        json.dumps({"defects": rows, "refusals": refused}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    md = render(rows, refused)
    (SESSIONS / "defect-log.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
