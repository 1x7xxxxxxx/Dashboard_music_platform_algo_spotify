#!/usr/bin/env python3
"""R257 — the architecture benchmark: every requirement, its proof REPLAYED, today's verdict.

Type: Utility
Uses: yaml, subprocess, pathlib
Reads: .claude/dev-docs/architecture/{domains,requirements}.yaml
Writes: .claude/dev-docs/architecture/benchmark.md (generated ON DEMAND and NOT versioned
        since R279 — a committed copy went stale at every requirement edit)
Triggers: make arch-benchmark ; tests/test_every_requirement_has_a_probe.py (structure only)

Owner, 2026-09-27: « identifier les domaines micro, les exigences de façon exhaustive, les
livrables, faire le benchmark avec ce qu'on a vs le théorique — et pour chaque exigence la
méthode pour confirmer la bonne gestion avec des tests ciblés sur une partie ou une ligne ».

A requirement carries ONE proof aimed at a precise site:
  * `pytest: tests/test_x.py::test_y` — a node the suite already runs, or
  * `cmd: <shell>` — a command whose exit code is the verdict (make target, audit script).
Its declared `statut` says what we believe; the replayed proof says what is TRUE today.
A « conforme » whose proof goes red is printed as a REGRESSION, never as conforme. A
requirement without a proof is a hole, counted and listed — never dropped.

    python3 tools/dev/arch_benchmark.py            # replay every proof, write benchmark.md
    python3 tools/dev/arch_benchmark.py --no-run   # structure only (no proof replayed)
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / ".claude" / "dev-docs" / "architecture"
STATUTS = ("conforme", "partiel", "absent", "non-mesure")
# R356 — how a requirement is held, and whether its machinery travels to another project.
METHODES = ("hook", "commit", "ci", "nuit", "regle-agent", "playbook", "humain", "demande")
PORTEES = ("generique", "streamlytics")
SETTINGS = ROOT / ".claude" / "settings.json"
_HOOK_PATH = re.compile(r"\.claude/[\w/-]+\.py")
PY = str(ROOT / ".venv" / "bin" / "python") if (ROOT / ".venv" / "bin" / "python").exists() \
    else sys.executable


def load() -> tuple[dict, list[dict]]:
    with open(ARCH / "domains.yaml", encoding="utf-8") as fh:
        domains = yaml.safe_load(fh)
    with open(ARCH / "requirements.yaml", encoding="utf-8") as fh:
        reqs = yaml.safe_load(fh) or []
    return domains, reqs


def _tracked() -> set[str]:
    """Paths git tracks, with every parent directory. A file that only exists on this
    machine (docker-compose.yml is ignored) passed a disk check here and failed in CI —
    the catalogue may only cite what a fresh checkout has."""
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout
    paths = set()
    for f in out.splitlines():
        parts = f.split("/")
        paths.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
    return paths


def structure_errors(domains: dict, reqs: list[dict]) -> list[str]:
    """What makes the catalogue unusable — the guard test reads this. Pure on the files."""
    errs, seen = [], set()
    tracked = _tracked()
    for r in reqs:
        rid = r.get("id", "?")
        if rid in seen:
            errs.append(f"{rid} : id en double")
        seen.add(rid)
        if r.get("domaine") not in domains:
            errs.append(f"{rid} : domaine inconnu « {r.get('domaine')} »")
        if r.get("statut") not in STATUTS:
            errs.append(f"{rid} : statut « {r.get('statut')} » hors {STATUTS}")
        if not r.get("sources"):
            errs.append(f"{rid} : aucune source (note du propriétaire, ADR, théorie)")
        preuve = r.get("preuve") or {}
        node = preuve.get("pytest")
        if node:
            path = node.split("::")[0]
            if path not in tracked:
                errs.append(f"{rid} : preuve pytest vers un fichier absent ({path})")
            elif "::" in node:
                name = node.split("::")[1].split("[")[0]
                with open(ROOT / path, encoding="utf-8") as fh:
                    if f"def {name}(" not in fh.read():
                        errs.append(f"{rid} : le test {name} n'existe pas dans {path}")
        cmd = preuve.get("cmd")
        if cmd and cmd.startswith("make "):
            target = cmd.split()[1]
            with open(ROOT / "Makefile", encoding="utf-8") as fh:
                if not any(line.startswith(f"{target}:") for line in fh):
                    errs.append(f"{rid} : cible make « {target} » absente")
        if r.get("statut") == "conforme" and not (node or cmd):
            errs.append(f"{rid} : déclaré conforme sans preuve rejouable")
    for key, d in domains.items():
        for f in (d.get("fichiers") or []) + (d.get("gardes") or []):
            if f.rstrip("/") not in tracked:
                errs.append(f"domaine {key} : chemin absent du dépôt {f}")
    return errs


def _make_targets() -> set[str]:
    with open(ROOT / "Makefile", encoding="utf-8") as fh:
        return {m.group(1) for m in re.finditer(r"^([\w-]+):", fh.read(), re.M)}


def harness_components(settings_path: Path | None = None) -> set[str]:
    """Every piece of the Claude Code harness: hook scripts REGISTERED in settings.json (a
    registration is real even before the file is committed), plus the versioned agents,
    skills, rules, workflows, slash commands, and every `make test*` target."""
    settings = json.loads((settings_path or SETTINGS).read_text(encoding="utf-8"))
    comps = {m for entries in (settings.get("hooks") or {}).values() for e in entries
             for h in e.get("hooks", []) for m in _HOOK_PATH.findall(h.get("command", ""))}
    tracked = _tracked()
    for pattern in ("agents/*.md", "skills/*/SKILL.md", "rules/*.md", "workflows/*",
                    "commands/*.md"):
        comps |= {rel for p in (ROOT / ".claude").glob(pattern)
                  if (rel := str(p.relative_to(ROOT))) in tracked}
    comps |= {f"Makefile:{t}" for t in _make_targets() if t.startswith("test")}
    return comps


def component_errors(comps: set[str], reqs: list[dict]) -> list[str]:
    """Both directions: a component no requirement names, a named component that does not
    resolve; plus `methode`/`portee` outside their enums. Only `composants:` counts."""
    errs, named = [], set()
    tracked, targets = _tracked(), _make_targets()
    for r in reqs:
        rid = r.get("id", "?")
        for c in r.get("composants") or []:
            named.add(c)
            alive = (c.split(":", 1)[1] in targets) if c.startswith("Makefile:") else c in tracked
            if not alive and c not in comps:
                errs.append(f"{rid} : composant introuvable {c}")
        harness = rid.startswith("REQ-HARN") or "composants" in r
        for field, allowed in (("methode", METHODES), ("portee", PORTEES)):
            if field in r and r[field] not in allowed:
                errs.append(f"{rid} : {field} « {r[field]} » hors {allowed}")
            elif harness and field not in r:
                errs.append(f"{rid} : {field} manquant")
    errs += [f"{c} : aucun `composants:` ne le nomme — ajouter une exigence"
             for c in sorted(comps - named)]
    return errs


def _mutation_evidence() -> tuple[dict, object]:
    """SEEN_RED (a red seen by hand) and self_proving, from the nightly job — one source."""
    spec = importlib.util.spec_from_file_location(
        "nightly_guard_mutation", ROOT / "tools" / "dev" / "nightly_guard_mutation.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SEEN_RED, mod.self_proving


def last_red(detail: str) -> str:
    """The NEWEST date in a SEEN_RED entry. Re-mutations are appended at the end, so the
    head is the oldest red (R412: 11 proofs re-mutated on 2026-10-05 read stale for ever)."""
    return max(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", detail), default=detail[:10])


def proof_state(req: dict, proof: str, seen_red: dict, self_proving) -> dict:
    """active = replayed green AND seen red (by hand, or self-proving). Pure but for the
    file read of `self_proving` and `git log` for the staleness of a dated red."""
    p = req.get("preuve") or {}
    if not (p.get("pytest") or p.get("cmd")):
        return {"etat": "trou", "vu_rouge": None}
    # A `cmd:` proof is keyed by its command (R412): no file to date, so never « périmé ».
    path = (p.get("pytest") or "").split("::")[0] or p.get("cmd", "")
    red = None
    if path in seen_red:
        red = {"comment": "à la main", "detail": seen_red[path], "date": last_red(seen_red[path])}
        last = subprocess.run(["git", "log", "-1", "--format=%cs", "--", path], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip()
        red["perime"] = bool(last) and last > red["date"]
    elif path and (ROOT / path).is_file() and self_proving(ROOT / path):
        red = {"comment": "auto-prouvant", "detail": "fabrique son défaut à chaque run"}
    if proof == "rouge":
        etat = "rouge"
    elif proof == "—":
        etat = "non rejouée"
    else:
        etat = "active" if red else "verte, non prouvée"
    return {"etat": etat, "vu_rouge": red}


def _activity() -> dict:
    spec = importlib.util.spec_from_file_location(
        "usage_report", ROOT / ".claude" / "scripts" / "usage_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    usage = mod.read()
    usage["ci"] = {w.name: _ci_runs(w.name) for w in (ROOT / ".github" / "workflows").glob("*.yml")}
    return usage


def _ci_runs(workflow: str) -> dict | None:
    """R366: a GitHub workflow runs on GitHub, not in a transcript — ask `gh`, None if it cannot."""
    try:
        out = subprocess.run(["gh", "run", "list", "--workflow", workflow, "--limit", "50",
                              "--json", "createdAt,conclusion"], cwd=ROOT, capture_output=True,
                             text=True, timeout=30)
        runs = json.loads(out.stdout) if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        runs = None
    if runs is None:
        return None
    return {"kind": "ci", "n": len(runs), "last": runs[0]["createdAt"][:10] if runs else None,
            "echecs": sum(r["conclusion"] == "failure" for r in runs),
            "note": "50 derniers runs GitHub"}


# R366 — where a command or a skill can be TRIGGERED: the surfaces that act (hooks, scripts,
# settings, rules, other commands/skills/agents/workflows, Makefile) and CLAUDE.md outside
# its tables. A table row or tooling-reference.md documents; measured, it never fires.
_IMPERATIVE_GLOBS = (".claude/hooks/*.py", ".claude/scripts/*.py", ".claude/settings.json",
                     ".claude/rules/*.md", ".claude/commands/*.md", ".claude/skills/*/SKILL.md",
                     ".claude/workflows/*", ".claude/agents/*.md", "Makefile")


def imperative_surfaces(root: Path = ROOT) -> dict[str, str]:
    out = {str(p.relative_to(root)): p.read_text(encoding="utf-8", errors="ignore")
           for g in _IMPERATIVE_GLOBS for p in root.glob(g) if p.is_file()}
    claude = root / "CLAUDE.md"
    if claude.exists():
        out["CLAUDE.md"] = "\n".join(ln for ln in claude.read_text(encoding="utf-8").splitlines()
                                     if not ln.lstrip().startswith("|"))
    return out


def trigger_sites(comp: str, surfaces: dict[str, str]) -> list[str]:
    """The imperative surfaces that name this command or skill — `/name`, `skills/name`,
    `Skill(name` — never its own file, never the bare word. Pure."""
    name = Path(comp).parent.name if comp.endswith("SKILL.md") else Path(comp).stem
    pat = re.compile(rf"(?<![\w/-])/{re.escape(name)}(?![\w-])|skills/{re.escape(name)}\b"
                     rf"|Skill\(\s*[\"']?{re.escape(name)}\b")
    return sorted(f for f, text in surfaces.items() if f != comp and pat.search(text))


def component_activity(comp: str, usage: dict) -> dict | None:
    """{'n': runs, 'last': date, 'kind': …} from the transcripts; None where unmeasurable."""
    if not usage.get("found"):
        return None
    stem = Path(comp).stem
    last = usage.get("last_seen", {})
    if comp.startswith("Makefile:"):
        t = comp.split(":", 1)[1]
        return {"kind": "make", "n": usage["make_targets"].get(t, 0), "last": last.get(f"make:{t}")}
    if "/hooks/" in comp or ("/scripts/" in comp and comp.endswith(".py")):
        runs = usage.get("hook_runs", {}).get(comp)
        if runs:  # R365: the trace journal sees silent runs too
            return {"kind": "hook", "n": runs["n"], "last": runs["last"][:10],
                    "ms": runs["ms"] // runs["n"], "echecs": usage["hook_failures"].get(comp, 0),
                    "note": "journal de traces (R365)"}
        n = usage["hooks"].get(comp, 0)
        return {"kind": "hook", "n": n, "last": last.get(f"hook:{comp}"),
                "ms": usage["hook_ms"].get(comp, 0) // n if n else None,
                "echecs": usage["hook_failures"].get(comp, 0),
                "note": None if n else "aucune trace — ni transcript, ni journal R365"}
    if "/agents/" in comp:
        return {"kind": "agent", "n": usage["agents"].get(stem, 0), "last": last.get(f"agent:{stem}")}
    if "/skills/" in comp:
        name = Path(comp).parent.name
        return {"kind": "skill", "n": usage["skills"].get(name, 0), "last": last.get(f"skill:{name}")}
    if "/rules/" in comp:
        return {"kind": "rule", "n": usage["rules"].get(stem, 0), "last": None,
                "note": "séances qui l'ont chargée"}
    if "/commands/" in comp:
        return {"kind": "command", "n": usage["commands"].get(stem, 0) + usage["skills"].get(stem, 0),
                "last": last.get(f"command:{stem}") or last.get(f"skill:{stem}")}
    if comp.startswith(".github/workflows/"):
        return usage.get("ci", {}).get(Path(comp).name) or {
            "kind": "ci", "n": 0, "last": None, "note": "gh injoignable — non mesuré"}
    if "/workflows/" in comp:
        inj = usage.get("injections", {})
        rel = "workflows/" + Path(comp).name
        if comp.endswith(".js"):
            return {"kind": "workflow", "n": usage["workflows"].get(stem, 0),
                    "last": last.get(f"workflow:{stem}")}
        return {"kind": "playbook", "n": inj.get("counts", {}).get(rel, 0),
                "last": (inj.get("last_seen", {}).get(rel) or "")[:10] or None,
                "note": "injections journalisées depuis R357"}
    return None


def _commit() -> str:
    return subprocess.run(["git", "log", "-1", "--format=%h %cs %s"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def build(domains: dict, reqs: list[dict], proofs: dict | None, usage: dict | None) -> dict:
    """The ONE derived object: benchmark.md and the harness page are rendered from it."""
    seen_red, self_proving = _mutation_evidence()
    comps = harness_components()
    usage = usage or {"found": False}
    owners = collections.defaultdict(list)
    out_reqs = []
    for r in reqs:
        p = r.get("preuve") or {}
        methode = r.get("methode") or ("ci" if p.get("pytest") else "demande" if p.get("cmd")
                                       else None)
        state = proof_state(r, (proofs or {}).get(r["id"], "—"), seen_red, self_proving)
        for c in r.get("composants") or []:
            owners[c].append(r["id"])
        out_reqs.append({
            "id": r["id"], "domaine": r["domaine"], "enonce": r["enonce"],
            "priorite": r.get("priorite"), "statut": r["statut"],
            "verdict": verdict(r["statut"], (proofs or {}).get(r["id"], "—")),
            "methode": methode, "methode_deduite": "methode" not in r,
            "portee": r.get("portee", "streamlytics"),
            "preuve": p.get("pytest") or p.get("cmd"), "a_ecrire": r.get("a_ecrire"),
            "mutation": r.get("mutation"), "ecart": r.get("ecart"),
            "roadmap": r.get("roadmap"), "opportunite": r.get("opportunite"),
            "premisse_corrigee": r.get("premisse_corrigee"),
            "composants": r.get("composants") or [], **state})
    surfaces = imperative_surfaces()
    components = {c: {"exigences": owners.get(c, []), "activite": component_activity(c, usage),
                      **({"declencheurs": trigger_sites(c, surfaces)}
                         if "/commands/" in c or c.endswith("SKILL.md") else {})}
                  for c in sorted(comps | set(owners))}
    return {"genere_depuis": _commit(), "rejoue": proofs is not None,
            "activite_mesuree": bool(usage.get("found")),
            "seances": usage.get("sessions"),
            "domaines": {k: {"nom": d["nom"]} for k, d in domains.items()},
            "exigences": out_reqs, "composants": components}


def replay(reqs: list[dict], timeout: int = 900) -> dict[str, str]:
    """{id: 'vert'|'rouge'|'—'} — pytest nodes in ONE run, commands one by one."""
    out = {r["id"]: "—" for r in reqs}
    nodes = {r["id"]: r["preuve"]["pytest"] for r in reqs if (r.get("preuve") or {}).get("pytest")}
    if nodes:
        res = subprocess.run([PY, "-m", "pytest", *sorted(set(nodes.values())), "-q",
                              "-p", "no:randomly", "-rA", "--no-header"],
                             cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        passed = {ln.split(" ", 1)[1].strip() for ln in res.stdout.splitlines()
                  if ln.startswith("PASSED ")}
        for rid, node in nodes.items():
            hits = [p for p in passed if p == node or p.startswith(node + "::")
                    or p.startswith(node + "[")]
            out[rid] = "vert" if hits else "rouge"
    for r in reqs:
        cmd = (r.get("preuve") or {}).get("cmd")
        if cmd:
            try:
                rc = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True,
                                    timeout=timeout).returncode
            except subprocess.TimeoutExpired:
                rc = 124
            out[r["id"]] = "vert" if rc == 0 else "rouge"
    return out


def verdict(declared: str, proof: str) -> str:
    """The printed verdict: a red proof is never shown as conforme. Pure."""
    if proof == "rouge" and declared == "conforme":
        return "RÉGRESSION"
    if proof == "rouge":
        return f"{declared} (preuve rouge)"
    return declared


def render(domains: dict, reqs: list[dict], proofs: dict[str, str] | None) -> str:
    by_dom = collections.defaultdict(list)
    for r in reqs:
        by_dom[r["domaine"]].append(r)
    counts = collections.Counter(
        verdict(r["statut"], (proofs or {}).get(r["id"], "—")).split(" ")[0] for r in reqs)
    holes = [r["id"] for r in reqs if not ((r.get("preuve") or {}).get("pytest")
                                            or (r.get("preuve") or {}).get("cmd"))]
    lines = ["# Benchmark d'architecture — actuel contre théorique",
             "",
             "> **Généré** par `make arch-benchmark` depuis `domains.yaml` et `requirements.yaml`.",
             "> Ne pas éditer à la main : corriger le catalogue, puis régénérer.",
             "",
             f"**{len(reqs)} exigences** sur **{len(by_dom)} domaines** (carte : {len(domains)}). "
             + " · ".join(f"{k} : {counts.get(k, 0)}" for k in
                          ("conforme", "partiel", "absent", "non-mesure", "RÉGRESSION"))
             + f" · sans preuve rejouable : {len(holes)}"
             + ("" if proofs else " · *(preuves non rejouées : --no-run)*"),
             ""]
    for key in domains:
        rs = by_dom.get(key)
        if not rs:
            continue
        lines += [f"## {domains[key]['nom']} (`{key}`)", "",
                  "| id | exigence | verdict | preuve | théorie | écart / livrable |",
                  "|---|---|---|---|---|---|"]
        for r in rs:
            p = r.get("preuve") or {}
            proof = p.get("pytest") or p.get("cmd") or "—"
            state = (proofs or {}).get(r["id"], "—")
            theory = "; ".join(s["theorie"] for s in r["sources"] if "theorie" in s) or "—"
            gap = (r.get("ecart") or "—") + (f" → {r['roadmap']}" if r.get("roadmap") else "")
            lines.append(f"| {r['id']} | {r['enonce']} | {verdict(r['statut'], state)} "
                         f"| `{proof}` {'✅' if state == 'vert' else '❌' if state == 'rouge' else ''} "
                         f"| {theory} | {gap} |")
        lines.append("")
    if holes:
        lines += ["## Trous — exigences sans preuve rejouable", "",
                  *[f"- {h}" for h in holes], ""]
    lines += ["## Rejouer une preuve sur une ligne précise", "",
              "1. Lancer la preuve seule : `.venv/bin/python -m pytest <node> -q` ou la commande.",
              "2. Appliquer la `mutation` déclarée de l'exigence sur SA ligne (ou "
              "`python3 tools/dev/mutate_guards.py <test>`).",
              "3. La preuve doit ROUGIR ; restaurer, vérifier `git status` propre.", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-run", action="store_true")
    ap.add_argument("--json", action="store_true",
                    help="also write benchmark.json (proof states, activity) for the harness page")
    args = ap.parse_args()
    domains, reqs = load()
    errs = structure_errors(domains, reqs) + component_errors(harness_components(), reqs)
    if errs:
        print("❌ catalogue invalide :\n  " + "\n  ".join(errs), file=sys.stderr)
        return 1
    proofs = None if args.no_run else replay(reqs)
    (ARCH / "benchmark.md").write_text(render(domains, reqs, proofs).rstrip("\n") + "\n", encoding="utf-8")
    if args.json:
        data = build(domains, reqs, proofs, _activity())
        (ARCH / "benchmark.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    red = [k for k, v in (proofs or {}).items() if v == "rouge"]
    print(f"écrit : {ARCH / 'benchmark.md'} — {len(reqs)} exigences, {len(red)} preuve(s) rouge(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
