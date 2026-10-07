#!/usr/bin/env python3
"""Say, for every red test of main's CI, by which road it got past the local gate.

Type: Utility
Uses: `gh run list` (ci.yml on main), git diff, .claude/scripts/select_tests.py (select),
      .claude/sessions/defects.jsonl (the reds `import_ci_reds.py` wrote)
Triggers: `make defect-log`, after `tools/dev/import_ci_reds.py`
Persists in: .claude/sessions/ci-red-escapes.json (cache per run — `select` costs seconds)

R446 (2026-10-07). A red CI already leaves a trace (mail, defect log), but not its CAUSE
of escape, and the remedy depends entirely on it:
  * `selector-miss` — `make test-changed` on the diff last-green → red would NOT have run
    the test: the selector is wrong, fix it (R447 was found this way, a P2);
  * `unstamped-push` — the test would have run, and the pushed tree is older than the R444
    pre-push gate: pushed without a green local run, which R444 now refuses;
  * `local-vs-ci` — the test would have run AND the push passed the R444 gate: green here,
    red there — an environment difference to name (DB, .env, order, date);
  * `ci-step` — a failed step with no test node: outside the selector's reach.
Network or git failure is fail-soft: the reason is printed and nothing is classified.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / ".claude" / "sessions" / "defects.jsonl"
CACHE = ROOT / ".claude" / "sessions" / "ci-red-escapes.json"
R444_COMMIT = "8f4e499d"   # the pre-push gate: a push after it was stamped green locally
sys.path.insert(0, str(ROOT / ".claude" / "scripts"))

ADVICE = {
    "selector-miss": "le sélecteur l'aurait raté — corriger select_tests.py (une ligne de roadmap)",
    "unstamped-push": "poussé sans arbre vert (avant R444) — la porte pre-push le refuse désormais",
    "local-vs-ci": "vert ici, rouge en CI — nommer l'écart d'environnement (base, .env, ordre, date)",
    "ci-step": "étape CI sans nœud de test — hors du sélecteur",
}


def reds_by_run(events: list[dict]) -> dict[str, list[str]]:
    """{run id: [red fingerprints]} for main's CI reds in the defect log. Pure."""
    out: dict[str, list[str]] = {}
    for e in events:
        if e.get("source") == "ci" and e.get("kind") in ("test_red", "ci_step"):
            run = str(e.get("session", "")).removeprefix("ci:")
            out.setdefault(run, [])
            if e["fingerprint"] not in out[run]:
                out[run].append(e["fingerprint"])
    return out


def previous_green(runs: list[dict], run_id: str) -> str | None:
    """headSha of the last successful run created before `run_id` (runs newest first). Pure."""
    seen = False
    for r in runs:
        if str(r["databaseId"]) == run_id:
            seen = True
        elif seen and r.get("conclusion") == "success":
            return r["headSha"]
    return None


def escape(fingerprint: str, selection: dict, gated: bool) -> str:
    """The road one red took. `selection` is `select()`'s result on the escaping diff. Pure."""
    if not fingerprint.startswith("test:"):
        return "ci-step"
    path = fingerprint[len("test:"):].split("::", 1)[0]
    if not selection.get("all") and path not in selection.get("paths", []):
        return "selector-miss"
    return "local-vs-ci" if gated else "unstamped-push"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def classify_run(run: dict, green: str, reds: list[str]) -> list[dict]:
    import select_tests as st
    diff = _git("diff", "--name-only", green, run["headSha"])
    if diff.returncode:
        raise RuntimeError(f"git diff {green[:8]}..{run['headSha'][:8]}: {diff.stderr.strip()[:120]}")
    selection = st.select(ROOT, _changed=diff.stdout.split())
    gated = _git("merge-base", "--is-ancestor", R444_COMMIT, run["headSha"]).returncode == 0
    return [{"fingerprint": fp, "road": escape(fp, selection, gated)} for fp in reds]


def render(rows: list[tuple[dict, list[dict]]]) -> str:
    out = ["## Rouges de CI de main — par où ils sont passés (R446)", ""]
    for run, found in rows:
        out.append(f"- run {run['databaseId']} ({run['createdAt'][:16]}, {run['headSha'][:8]})")
        out += [f"  - `{f['road']}` {f['fingerprint'][:110]} — {ADVICE[f['road']]}" for f in found]
    return "\n".join(out) if rows else "\n".join(out + ["- aucun rouge de CI dans le journal"])


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def main() -> int:
    try:
        runs = json.loads(subprocess.run(
            ["gh", "run", "list", "--workflow", "ci.yml", "--branch", "main", "--status",
             "completed", "-L", "200", "--json", "databaseId,conclusion,headSha,createdAt"],
            cwd=ROOT, capture_output=True, text=True, timeout=120, check=True).stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        print(f"⚠ rouges de CI non classés ({type(e).__name__}) — rien à dire")
        return 0
    try:
        events = [json.loads(ln) for ln in LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        events = []
    reds, cache, rows = reds_by_run(events), _load_json(CACHE, {}), []
    for run in runs:
        rid = str(run["databaseId"])
        if run.get("conclusion") != "failure" or rid not in reds:
            continue
        if rid not in cache:
            green = previous_green(runs, rid)
            if not green:
                continue
            try:
                cache[rid] = classify_run(run, green, reds[rid])
            except (RuntimeError, OSError) as e:
                print(f"⚠ run {rid} non classé : {e}")
                continue
        rows.append((run, cache[rid]))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    print(render(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
