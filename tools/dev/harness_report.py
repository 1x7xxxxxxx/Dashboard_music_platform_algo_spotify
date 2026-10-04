#!/usr/bin/env python3
"""R356 — the harness report: every requirement, the probe that holds it, its method,
whether the probe is ACTIVE, what each component really did, and what to optimise.

Type: Utility
Uses: .claude/dev-docs/architecture/benchmark.json (written by arch_benchmark.py --json)
Triggers: make harness-report
Persists in: revue/harness-report.html — generated, never versioned (ADR-031)

Owner, 2026-10-04 : « un livrable qui nous montre les sondes actives pour chaque exigence
avec la méthode de harnais et les opportunités d'optimisation » — and « le seul livrable
qui doit être automatiquement mis à jour ». Nothing in it is written by hand: the catalogue
(requirements.yaml) is the source, benchmark.json the one derived object, this page a view.

Vocabulary, kept apart on purpose:
  * état « active »      — proof replayed GREEN and seen RED (SEEN_RED by hand, or a
                            self-proving test). Presence is not function.
  * « verte, non prouvée » — green, but nobody ever watched it fail.
  * activité             — what the transcripts recorded. A hook that prints nothing leaves
                            no trace: « aucune trace » is never read as « never fired ».
"""
from __future__ import annotations

import argparse
import collections
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".claude" / "dev-docs" / "architecture" / "benchmark.json"
DEFECTS = ROOT / ".claude" / "sessions" / "defect-log.json"   # R362, written by make defect-log
OUT = ROOT / "revue" / "harness-report.html"
ETATS = ("active", "verte, non prouvée", "rouge", "trou", "non rejouée")
_INVOKED = ("agent", "skill", "command", "workflow", "playbook", "make")


def opportunities(data: dict) -> list[dict]:
    """Every optimisation the data supports, most actionable first. Pure."""
    out = []
    for r in data["exigences"]:
        if r["etat"] == "rouge":
            out.append({"rang": 0, "type": "preuve rouge", "ref": r["id"],
                        "texte": f"{r['enonce']} — la preuve est rouge aujourd'hui"})
        if r["etat"] == "trou":
            out.append({"rang": 1, "type": "trou", "ref": r["id"],
                        "texte": r.get("a_ecrire") or "aucune preuve rejouable"})
        if r.get("opportunite"):
            out.append({"rang": 2, "type": "mesurée", "ref": r["id"], "texte": r["opportunite"]})
        red = r.get("vu_rouge") or {}
        if red.get("perime"):
            out.append({"rang": 3, "type": "vu rouge périmé", "ref": r["id"],
                        "texte": f"vu rouge le {red['date']}, fichier modifié depuis — re-muter"})
    unproven = [r["id"] for r in data["exigences"] if r["etat"] == "verte, non prouvée"]
    if unproven:
        out.append({"rang": 3, "type": "à muter", "ref": f"{len(unproven)} exigences",
                    "texte": "preuve verte jamais vue rouge : la muter (tools/dev/mutate_guards.py) "
                             "puis l'inscrire dans SEEN_RED — " + ", ".join(unproven[:12])
                             + (" …" if len(unproven) > 12 else "")})
    if data.get("activite_mesuree"):
        for comp, c in data["composants"].items():
            a = c.get("activite")
            # A `note` says the counter cannot conclude « never » (a silent hook, a log
            # younger than the transcripts): such a 0 is not an opportunity.
            if a and a["kind"] in _INVOKED and a["n"] == 0 and not a.get("note"):
                out.append({"rang": 4, "type": "jamais invoqué", "ref": comp,
                            "texte": f"0 usage en {data.get('seances')} séances — le brancher "
                                     "par une règle à flèche, ou le retirer vers archive/"})
            elif a and a["kind"] == "hook" and a.get("ms") and a["ms"] >= 1000:
                out.append({"rang": 4, "type": "hook lent", "ref": comp,
                            "texte": f"{a['ms']} ms en moyenne sur {a['n']} passages"})
    out += defect_opportunities(data.get("defauts") or [])
    return sorted(out, key=lambda o: (o["rang"], o["ref"]))


def defect_opportunities(rows: list[dict]) -> list[dict]:
    """R362: an open defect and an unanswered `recurrence:` ticket are work. Pure.

    Only the fingerprint and the status leave the log: the excerpts stay local (the repo
    is public, and the page is published)."""
    out = [{"rang": 0, "type": "défaut ouvert", "ref": r["fingerprint"],
            "texte": f"rouge depuis le {r['last_seen'][:10]}, aucun vert prouvé — le relancer, "
                     "ou make defect-close FP=… NOTE=…"}
           for r in rows if r.get("status") == "open"]
    out += [{"rang": 2, "type": "billet à répondre", "ref": r["fingerprint"],
             "texte": f"{r['recurrence_proposal']} — même cause ? "
                      "make defect-ticket FP=… VERDICT=same-cause|distinct NOTE=…"}
            for r in rows if r.get("recurrence_proposal") and not r.get("ticket")]
    return out


def summary(data: dict) -> dict:
    """Counts by state, by domain, and the baseline-v2 subset. Pure."""
    by_dom = collections.defaultdict(collections.Counter)
    for r in data["exigences"]:
        by_dom[r["domaine"]][r["etat"]] += 1
    return {"etats": collections.Counter(r["etat"] for r in data["exigences"]),
            "domaines": {k: dict(v) for k, v in by_dom.items()},
            "generiques": sum(r["portee"] == "generique" for r in data["exigences"])}


def render(data: dict) -> str:
    payload = {"data": data, "opportunites": opportunities(data), "resume": summary(data),
               "etats": ETATS}
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    page = (Path(__file__).with_name("harness_report.html.tpl")).read_text(encoding="utf-8")
    return (page.replace("{{COMMIT}}", html.escape(data["genere_depuis"]))
                .replace("{{DATA}}", blob))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    if not SRC.exists():
        print(f"❌ {SRC} absent — lancer d'abord : python3 tools/dev/arch_benchmark.py --json",
              file=sys.stderr)
        return 1
    data = json.loads(SRC.read_text(encoding="utf-8"))
    if DEFECTS.exists():
        data["defauts"] = [{k: r.get(k) for k in ("fingerprint", "status", "last_seen",
                                                   "recurrence_proposal", "ticket")}
                           for r in json.loads(DEFECTS.read_text(encoding="utf-8"))["defects"]]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(data), encoding="utf-8")
    s = summary(data)
    print(f"écrit : {args.out} — " + " · ".join(f"{k} : {s['etats'].get(k, 0)}" for k in ETATS)
          + f" · {len(opportunities(data))} opportunités")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
