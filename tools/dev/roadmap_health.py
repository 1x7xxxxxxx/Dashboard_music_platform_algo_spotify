#!/usr/bin/env python3
"""The health of the roadmap — docs/ROADMAP-HEALTH.md, regenerated at each close (R644, baseline REQ-PARC-138).

Type: Utility
Uses: git, .claude/dev-docs/roadmap/{checklist,archive}.md
Triggers: tools/dev/roadmap.py close (child process — a failure warns, the close stands) ;
          `python3 tools/dev/roadmap_health.py` by hand
Depends on: the index table of checklist.md (`| Rnnn | tâche | P | Mesuré par |`) and the archive's
            `- [x] **Rnnn` entries
Persists in: docs/ROADMAP-HEALTH.md (versioned, dated: a function of the git ages, not of the tree)

Adapted from the master's tools/governance/roadmap_health.py (REQ-PM-07) to THIS repo's governance:
no proof ledger and no `est:` / `dep:` tags here, so a row's state reads only what the repo holds:

  - échec          its « Mesuré par » names nothing executable — no `command`, no file path ;
  - avertissement  older than AGE_WARN days (first commit citing its id) ;
  - ok             otherwise.

For the last RECENT closures, the actual is read, never declared: days from the first to the last
commit citing the id, and how many commits cite it.

    python3 tools/dev/roadmap_health.py            # write docs/ROADMAP-HEALTH.md
    python3 tools/dev/roadmap_health.py --check    # exit 1 when an open row is `échec`

guard_scope: tests/test_the_roadmap_health_is_written_at_each_close.py — row states, the report's
sections, close regenerating it.
NOT covered: whether a « Mesuré par » command still runs (the nightly replays them, not this report).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("ROADMAP_ROOT") or Path(__file__).resolve().parents[2])
CHECKLIST = ROOT / ".claude" / "dev-docs" / "roadmap" / "checklist.md"
ARCHIVE = ROOT / ".claude" / "dev-docs" / "roadmap" / "archive.md"
OUT = ROOT / "docs" / "ROADMAP-HEALTH.md"
AGE_WARN = 30
RECENT = 30
STATES = ("ok", "avertissement", "échec")

_ROW = re.compile(r"^\|\s*(R\d{1,4})\s*\|(.*)\|\s*(P[0-3])\s*\|(.*)\|\s*$")
_CLOSED = re.compile(r"^- \[[xX]\] \*\*(R\d{1,4})\b", re.M)
_EXECUTABLE = re.compile(r"`[^`]+`|\b[\w./-]+\.(?:py|sh|md|yaml|yml|json|sql)\b")


def rows(text: str) -> list[dict]:
    """The open rows of the 📋 index. Pure."""
    out, inside = [], False
    for ln in text.splitlines():
        if ln.startswith("## "):
            inside = "Tâches ouvertes" in ln
            continue
        m = _ROW.match(ln) if inside else None
        if m:
            out.append({"id": m.group(1), "task": re.sub(r"\s*<!--.*?-->", "", m.group(2)).strip(),
                        "p": m.group(3), "measured": m.group(4).strip()})
    return out


def closed_ids(archive: str) -> list[str]:
    """Closed ids, newest first (close writes at the top), each once. Pure."""
    seen: list[str] = []
    for tid in _CLOSED.findall(archive):
        if tid not in seen:
            seen.append(tid)
    return seen


def row_state(r: dict, age_d: float | None) -> tuple[str, str]:
    """One state per open row, and why. Pure."""
    if not _EXECUTABLE.search(r["measured"]):
        return "échec", "« Mesuré par » ne nomme ni commande ni fichier"
    if age_d is not None and age_d > AGE_WARN:
        return "avertissement", f"ouverte depuis {age_d:.0f} j (> {AGE_WARN})"
    return "ok", "—"


def citing_commits(tid: str) -> list[float]:
    """Commit times (epoch) whose subject or body cites `tid` as a word, oldest first."""
    r = subprocess.run(["git", "-C", str(ROOT), "log", "--format=%ct", "-E", f"--grep=\\b{tid}\\b"],
                       capture_output=True, text=True)
    return sorted(float(x) for x in r.stdout.split() if x.strip())


def collect(now: float | None = None) -> dict:
    now = now or dt.datetime.now().timestamp()
    open_rows = []
    for r in rows(CHECKLIST.read_text(encoding="utf-8")):
        ts = citing_commits(r["id"])
        age = (now - ts[0]) / 86400 if ts else None
        st, why = row_state(r, age)
        open_rows.append({**r, "age": age, "state": st, "why": why})
    closed = []
    for tid in closed_ids(ARCHIVE.read_text(encoding="utf-8"))[:RECENT]:
        ts = citing_commits(tid)
        closed.append({"id": tid, "days": (ts[-1] - ts[0]) / 86400 if ts else None, "commits": len(ts)})
    return {"now": now, "open": open_rows, "closed": closed}


def _num(x: float | None) -> str:
    return "—" if x is None else f"{x:.1f}"


def render_md(h: dict) -> str:
    when = dt.datetime.fromtimestamp(h["now"]).isoformat(timespec="seconds")
    counts = {s: sum(1 for r in h["open"] if r["state"] == s) for s in STATES}
    lines = ["# Santé de la roadmap", "",
             f"> Généré par `python3 tools/dev/roadmap_health.py` (R644) depuis "
             f"`.claude/dev-docs/roadmap/checklist.md` le {when} — ne pas éditer. Régénéré à chaque "
             "`make roadmap-close`.",
             "> Décision éclairée : quelle tâche ouvrir ensuite, laquelle n'a pas de mesure exécutable, "
             "laquelle traîne.", "",
             f"**{len(h['open'])} tâche(s) ouverte(s)** — " + " · ".join(f"{s} {counts[s]}" for s in STATES),
             "", "## Tâches ouvertes", ""]
    if h["open"]:
        lines += ["| id | P | âge (j) | état | pourquoi |", "|---|---|---|---|---|"]
        lines += [f"| {r['id']} | {r['p']} | {_num(r['age'])} | {r['state']} | {r['why']} |" for r in h["open"]]
    else:
        lines.append("Aucune tâche ouverte.")
    lines += ["", f"## {RECENT} dernières clôtures — réel mesuré", "",
              "| id | jours (premier → dernier commit qui la cite) | commits |", "|---|---|---|"]
    lines += [f"| {c['id']} | {_num(c['days'])} | {c['commits']} |" for c in h["closed"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 when an open row is `échec`")
    args = ap.parse_args(argv)
    h = collect()
    if args.check:
        bad = [r["id"] for r in h["open"] if r["state"] == "échec"]
        print("❌ sans mesure exécutable : " + ", ".join(bad) if bad else "✅ santé de la roadmap : aucun échec")
        return 1 if bad else 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render_md(h), encoding="utf-8")
    print(f"✅ {OUT.relative_to(ROOT)} — {len(h['open'])} ouverte(s), {len(h['closed'])} clôture(s) lues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
