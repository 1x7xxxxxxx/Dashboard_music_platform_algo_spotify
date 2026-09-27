#!/usr/bin/env python3
"""R257 — the architecture benchmark: every requirement, its proof REPLAYED, today's verdict.

Type: Utility
Uses: yaml, subprocess, pathlib
Reads: .claude/dev-docs/architecture/{domains,requirements}.yaml
Writes: .claude/dev-docs/architecture/benchmark.md (generated — never edited by hand)
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
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / ".claude" / "dev-docs" / "architecture"
STATUTS = ("conforme", "partiel", "absent", "non-mesure")
PY = str(ROOT / ".venv" / "bin" / "python") if (ROOT / ".venv" / "bin" / "python").exists() \
    else sys.executable


def load() -> tuple[dict, list[dict]]:
    with open(ARCH / "domains.yaml", encoding="utf-8") as fh:
        domains = yaml.safe_load(fh)
    with open(ARCH / "requirements.yaml", encoding="utf-8") as fh:
        reqs = yaml.safe_load(fh) or []
    return domains, reqs


def structure_errors(domains: dict, reqs: list[dict]) -> list[str]:
    """What makes the catalogue unusable — the guard test reads this. Pure on the files."""
    errs, seen = [], set()
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
            if not (ROOT / path).is_file():
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
            if not (ROOT / f).exists():
                errs.append(f"domaine {key} : chemin absent {f}")
    return errs


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
    args = ap.parse_args()
    domains, reqs = load()
    errs = structure_errors(domains, reqs)
    if errs:
        print("❌ catalogue invalide :\n  " + "\n  ".join(errs), file=sys.stderr)
        return 1
    proofs = None if args.no_run else replay(reqs)
    (ARCH / "benchmark.md").write_text(render(domains, reqs, proofs) + "\n", encoding="utf-8")
    red = [k for k, v in (proofs or {}).items() if v == "rouge"]
    print(f"écrit : {ARCH / 'benchmark.md'} — {len(reqs)} exigences, {len(red)} preuve(s) rouge(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
