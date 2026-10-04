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
- `fixed`     (R353) a traceback whose file was committed after it, then main's CI went green;
- `closed`    (R353) closed by hand with its reason: `make defect-close FP=… NOTE=…`.
R353 also reads two more red kinds: `ci-step:<job>/<step>` (a CI red with no test node,
closed by the next CI green) and `cron:<job>:<step>` (this machine's cron jobs, closed by
the same step's next `rc=0`) — before it, only a `test:` red could ever close.
- a fingerprint red on ≥ 2 distinct days with a green in between comes BACK: it is proposed
  for the catalogue's existing `recurrence:<d1>,<d2>` admission ticket (rule 15). Proposed
  only — a fingerprint groups by where a symptom surfaced, not by why (rule 20), so a human
  confirms the same cause before writing a class (code-critic, R315).
Refusals (hooks, pre-commit) are counted by reason: they measure MY repeated gestures.
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
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


RED_KINDS = ("test_red", "traceback", "ci_step", "cron_red")


def _closers(fp: str, seen: list[dict], events: list[dict], greens: list,
             touched: dict[str, str]) -> list[tuple[str, str, str]]:
    """(ts, session, how) of every event that says this fingerprint is fixed. Pure.

    R353 — before it, only a `test:` red could ever close: a traceback, a gate red or a cron
    failure stayed `open` forever, so `open` stopped meaning anything."""
    kind = seen[0]["kind"]
    out = [(e["ts"], e["session"], "closed") for e in events
           if e["kind"] == "closed" and e["fingerprint"] == fp]
    if kind == "test_red":
        node = fp.removeprefix("test:")
        out += [(g[0], g[1], "green") for g in greens if _covers(g[2], node)]
    elif kind == "ci_step":
        out += [(g[0], g[1], "green") for g in greens if g[1].startswith("ci:")]
    elif kind == "cron_red":
        out += [(e["ts"], e["session"], "green") for e in events
                if e["kind"] == "cron_ok" and e["fingerprint"] == fp]
    elif kind == "traceback" and touched.get(fp.partition("@")[2], "") > seen[-1]["ts"]:
        # its file was committed AFTER its last sighting, then main's CI went green
        fixed_at = touched[fp.partition("@")[2]]
        out += [(g[0], g[1], "fixed") for g in greens
                if g[1].startswith("ci:") and g[0] > fixed_at]
    return sorted(out)


def _status(seen: list[dict], after: list[tuple[str, str, str]], days: list[str]) -> str:
    if not after:
        return "open"
    if after[-1][2] in ("closed", "fixed"):
        return after[-1][2]
    one_session = len({e["session"] for e in seen}) == 1
    if seen[0]["kind"] in ("cron_red", "ci_step"):  # a job that recovered, not an edit
        return "green"
    if len(days) == 1 and one_session and after[0][1] == seen[-1]["session"]:
        return "transient"
    return "green"


def classify(events: list[dict], touched: dict[str, str] | None = None) -> list[dict]:
    """One row per red fingerprint. Pure.

    `touched`: file → when it was last committed (UTC, the log's format), for tracebacks."""
    greens, touched = _greens(events), touched or {}
    reds: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        if e["kind"] in RED_KINDS:
            reds[e["fingerprint"]].append(e)
    rows = []
    for fp, seen in reds.items():
        closers = _closers(fp, seen, events, greens, touched)
        after = [c for c in closers if c[0] > seen[-1]["ts"]]
        days = sorted({e["ts"][:10] for e in seen})
        returned = [d for d in days[1:] if any(
            c[0][:10] < d and c[0] > seen[0]["ts"] for c in closers)]
        # R336: only a red on a CLEAN tree proposes a ticket; one on work in progress, or on
        # a tree nobody can vouch for (old events, backfill), is listed without one.
        clean = {e["ts"][:10] for e in seen if e.get("tree") == "clean"}
        back = [d for d in returned if d in clean]
        rows.append({
            "fingerprint": fp, "kind": seen[0]["kind"], "status": _status(seen, after, days),
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


def touched_files(rows_or_events: list[dict]) -> dict[str, str]:
    """file → its last commit (UTC, the log's format), for every traceback's file."""
    out = {}
    for fp in {e["fingerprint"] for e in rows_or_events if e.get("kind") == "traceback"}:
        f = fp.partition("@")[2]
        try:
            iso = subprocess.run(["git", "log", "-1", "--format=%cI", "--", f], cwd=ROOT,
                                 capture_output=True, text=True, timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if iso:
            out[f] = datetime.fromisoformat(iso).astimezone(timezone.utc).isoformat(
                timespec="milliseconds")
    return out


def summary(rows: list[dict]) -> str:
    """One line for a session start or `make night-status`. Pure."""
    open_ = [r for r in rows if r["status"] == "open"]
    by = defaultdict(int)
    for r in open_:
        by[r["kind"]] += 1
    tickets = sum(1 for r in rows if r["recurrence_proposal"])
    detail = ", ".join(f"{n} {k}" for k, n in sorted(by.items()))
    return (f"{len(open_)} défaut(s) ouvert(s)" + (f" ({detail})" if detail else "")
            + (f", {tickets} billet(s) recurrence: à confirmer" if tickets else "")
            + " — `make defect-log`")


def close(fp: str, note: str, path: Path = LOG) -> int:
    """R353: a defect no green can close (a throwaway script, a job retired) is closed by
    hand, WITH its reason — never by deleting its lines."""
    if not note.strip():
        print("❌ NOTE vide — dire pourquoi ce défaut est clos (make defect-close FP=… NOTE=…)")
        return 1
    known = {e["fingerprint"] for e in load(path)}
    if fp not in known:
        print(f"❌ empreinte inconnue du journal : {fp!r} (voir .claude/sessions/defect-log.md)")
        return 1
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps({"kind": "closed", "fingerprint": fp, "excerpt": note.strip(),
                              "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                              "session": "manual", "status": "observed"},
                             ensure_ascii=False) + "\n")
    print(f"✅ clos : {fp} — {note.strip()}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "--close":
        return close(argv[2] if len(argv) > 2 else "", " ".join(argv[3:]))
    events = load()
    if len(argv) >= 2 and argv[1] == "--summary":
        if events:
            print("🩺 Journal des défauts : " + summary(classify(events, touched_files(events))))
        return 0
    if not events:
        print(f"ℹ️  aucun symptôme enregistré dans {LOG.relative_to(ROOT)} "
              "(le hook Stop l'écrit à chaque réponse ; rattrapage : "
              "python3 .claude/scripts/defect_capture.py --backfill <transcript>)")
        return 0
    rows, refused = classify(events, touched_files(events)), refusals(events)
    (SESSIONS / "defect-log.json").write_text(
        json.dumps({"defects": rows, "refusals": refused}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    md = render(rows, refused)
    (SESSIONS / "defect-log.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
