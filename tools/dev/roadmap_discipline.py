#!/usr/bin/env python3
"""How many dev actions ran without being on the roadmap first — and without their critic.

Type: Utility
Uses: git history, tools/dev/require_roadmap_id.py (verdict, open_rows, critic_decision),
      tools/dev/claude_transcripts.py (critic calls, local only)
Triggers: make roadmap-discipline (and make night-status), security-nightly job
          `dev-discipline`, the daily recap mail
Persists in: .claude/dev-docs/roadmap-discipline.json (--write) — its git history IS the series

R197 (2026-09-26), owner: « tester et intégrer des sondes de mesures pour monitorer combien de
tâches de dev se font sans inscription en roadmap ». Baseline, 14 days before the R196 gate:
116 product-code commits, 45 cited an open row written beforehand, 41 no id, 30 an id that
was not open beforehand.

Three measures, each with what it cannot see:
  * GIT (runs anywhere): each product-code commit of the window, classified by the gate's own
    `verdict()` against its PARENT's index. A commit made after the gate existed that still
    fails it is a BYPASS (`--no-verify`, a red CI left on main) — it stays in history even
    when CI refused it, which is why this is not the CI `roadmap` job twice.
  * CRITIC (local only): for each cited row decided `critic: requis`, was a code-critic (or an
    engineering-loop run) naming the Rnnn found in the transcripts BEFORE the first commit?
    Without transcripts (CI) the answer is `null` — « not measured here », never 0.
  * AGE: each open index row, from the first commit whose checklist carries its `| Rnnn |`
    line (`git log -G` on the id token — survives a text edit, unlike `-S`). > 14 days =
    stale: an action nobody finishes and nobody parks.

Exit 1 when there is a bypass or a stale row — the nightly turns red, the mail says why.

    python3 tools/dev/roadmap_discipline.py [--days N] [--baseline] [--write] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import require_roadmap_id as gate  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".claude" / "dev-docs" / "roadmap-discipline.json"
STALE_DAYS = 14


def _git(*args: str, root: Path = ROOT) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True).stdout


def classify(files: list[str], message: str, parent_checklist: str, parents: int,
             gated: bool, critic_gated: bool = True) -> str | None:
    """None for a commit that is not product code; else ok | no_id | not_open |
    undecided — and `bypass:<reason>` once the gate existed. A commit is judged by the rules
    that existed at its PARENT: before R198, an undecided row was the norm, not a fault. Pure."""
    if gate.is_exempt(message, parents) or not any(gate.is_product(f) for f in files):
        return None
    reason = gate.verdict(files, message, parent_checklist, parents)
    if reason is None:
        return "ok"
    kind = ("no_id" if "aucun Rnnn" in reason else
            "undecided" if "ne décide pas" in reason else "not_open")
    if kind == "undecided" and not critic_gated:
        return "ok"
    return f"bypass:{kind}" if gated else kind


def commits(days: int, root: Path = ROOT) -> list[dict]:
    out = []
    for sha in _git("rev-list", f"--since={days}.days", "HEAD", root=root).split():
        parents = _git("rev-list", "--parents", "-n", "1", sha, root=root).split()[1:]
        if not parents:
            continue
        p = parents[0]
        out.append({
            "sha": sha,
            "ts": int(_git("log", "-1", "--format=%at", sha, root=root).strip() or 0),
            "files": _git("diff-tree", "--no-commit-id", "--name-only", "-r", sha,
                          root=root).split(),
            "message": _git("log", "-1", "--format=%B", sha, root=root),
            "parent_checklist": _git("show", f"{p}:{gate.CHECKLIST}", root=root),
            "parents": len(parents),
            "gated": bool(_git("show", f"{p}:{gate._SELF}", root=root)),
            "critic_gated": "def critic_decision" in _git("show", f"{p}:{gate._SELF}", root=root),
        })
    return out


def git_half(rows: list[dict], baseline: bool) -> dict:
    counts = {"product": 0, "ok": 0, "no_id": 0, "not_open": 0, "undecided": 0, "bypass": 0}
    bypasses = []
    for c in rows:
        if not (baseline or c["gated"]):
            continue
        k = classify(c["files"], c["message"], c["parent_checklist"], c["parents"], c["gated"],
                     c.get("critic_gated", True))
        if k is None:
            continue
        counts["product"] += 1
        if k.startswith("bypass:"):
            counts["bypass"] += 1
            bypasses.append(f"{c['sha'][:7]} {c['message'].splitlines()[0][:60]} ({k[7:]})")
        else:
            counts[k] += 1
    return {**counts, "bypasses": bypasses}


def critic_half(rows: list[dict], calls: list[dict] | None) -> dict:
    """For each `requis` row cited by a product commit: a critic naming it before the
    FIRST such commit? `calls` None ⇒ not measurable here."""
    first: dict[str, int] = {}
    for c in rows:
        if classify(c["files"], c["message"], c["parent_checklist"], c["parents"], True) is None:
            continue
        for i in gate.requis_ids(c["message"], c["parent_checklist"]):
            first[i] = min(first.get(i, c["ts"]), c["ts"])
    if calls is None:
        return {"requis": len(first), "with_critic": None, "without_critic": None,
                "missing": None, "note": "transcriptions absentes : non mesuré ici"}
    from claude_transcripts import names
    missing = sorted(i for i, ts in first.items()
                     if not any(names(k, i) and k["ts"] <= ts for k in calls))
    return {"requis": len(first), "with_critic": len(first) - len(missing),
            "without_critic": len(missing), "missing": missing}


def ages(checklist: str, root: Path = ROOT, now: float | None = None) -> dict[str, int]:
    now = time.time() if now is None else now
    out = {}
    for rid in sorted(gate.open_ids(checklist)):
        log = _git("log", "--reverse", "--format=%at", "-G", rf"^\| *{rid} *\|", "--",
                   gate.CHECKLIST, root=root).split()
        out[rid] = int((now - int(log[0])) // 86400) if log else 0
    return out


def measure(days: int = 14, baseline: bool = False, root: Path = ROOT,
            calls: list[dict] | None | str = "auto") -> dict:
    rows = commits(days, root)
    if calls == "auto":
        from claude_transcripts import critic_calls
        calls = critic_calls(since=time.time() - (days + 7) * 86400)
    checklist = (root / gate.CHECKLIST).read_text(encoding="utf-8")
    age = ages(checklist, root)
    return {"days": days, "baseline": baseline,
            "git": git_half(rows, baseline),
            "critic": critic_half(rows, calls),
            "open_rows_age_days": age,
            "stale": sorted(r for r, d in age.items() if d > STALE_DAYS)}


def failing(report: dict) -> list[str]:
    out = []
    if report["git"]["bypass"]:
        out.append(f"{report['git']['bypass']} commit(s) de code passés sans ligne ouverte "
                   "AVANT eux, malgré le garde : " + " ; ".join(report["git"]["bypasses"]))
    if report["stale"]:
        out.append(f"ligne(s) ouverte(s) depuis plus de {STALE_DAYS} jours : "
                   + ", ".join(f"{r} ({report['open_rows_age_days'][r]} j)"
                               for r in report["stale"]))
    return out


def render(report: dict) -> str:
    g, c = report["git"], report["critic"]
    scope = "tout l'historique de la fenêtre" if report["baseline"] else "depuis le garde R196"
    pct = f"{100 * g['ok'] // g['product']} %" if g["product"] else "—"
    crit = ("non mesuré ici (pas de transcriptions)" if c["with_critic"] is None else
            f"{c['with_critic']}/{c['requis']} avec un critic qui la nomme AVANT le code"
            + (f" — sans : {', '.join(c['missing'])}" if c["missing"] else ""))
    lines = [
        f"Discipline de roadmap — {report['days']} jours, {scope}",
        f"  commits de code produit : {g['product']} · inscrits AVANT : {g['ok']} ({pct})",
        f"  sans id : {g['no_id']} · id pas ouvert avant : {g['not_open']} · "
        f"ligne sans décision critic : {g['undecided']} · CONTOURNEMENTS : {g['bypass']}",
        f"  tâches « critic: requis » : {crit}",
        "  âge des lignes ouvertes : " + (", ".join(
            f"{r} {d} j" for r, d in report["open_rows_age_days"].items()) or "(aucune)"),
    ]
    return "\n".join(lines + [f"  🚫 {f}" for f in failing(report)])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--baseline", action="store_true",
                    help="juger aussi les commits d'avant le garde (mesure de référence)")
    ap.add_argument("--write", action="store_true", help=f"écrire {OUT.relative_to(ROOT)}")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    report = measure(a.days, a.baseline)
    if a.write:
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2) if a.json else render(report))
    return 1 if failing(report) else 0


if __name__ == "__main__":
    sys.exit(main())
