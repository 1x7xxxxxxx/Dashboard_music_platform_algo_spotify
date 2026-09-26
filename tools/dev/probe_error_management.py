#!/usr/bin/env python3
"""Probe the whole error-class management chain: one fabricated defect per gate, run the REAL gate.

Type: Utility
Uses: git worktree (a throwaway copy of HEAD, history included), the real gates:
      .claude/scripts/audit_runner.py (--admission, --sweep-verdict),
      tools/dev/error_class_health.py, tools/dev/error_class_families.py,
      .claude/hooks/require_sweep_before_catalogue.py, the catalogue tests
Triggers: `make error-management-probe`; nightly job `error-management-probe`
          (.github/workflows/security-nightly.yml)
Persists in: nothing — the worktree is removed on exit

R184 (2026-09-26). Asked: « does the error management work, and which tests guarantee it? »
A test that a gate EXISTS answers the wrong question; a gate that is wired but no longer
refuses (a CI step removed, a ceiling raised, a rule loosened) reads exactly like one that
works. So each probe writes ONE complete, valid new class into a scratch copy of the repo,
breaks exactly one of its proofs, runs the gates CI runs, and requires at least one red —
and the unbroken control class must pass every gate, or the probes prove nothing.

Output: a table probe → expected → which gates went red → the test that guarantees it.
Exit 0 only if every probe is refused as expected and the control passes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOGUE = ".claude/dev-docs/error-classes.md"
PY = sys.executable
CID = "a-probe-class-fabricated-by-the-error-management-probe"

# A class that satisfies every rule the chain enforces on a NEW class. Each probe breaks one.
CONTROL = {
    "status": "guarded",
    "severity": "P3",
    "family": "un-garde-qui-ne-garde-pas",
    "kind": "deterministic",
    "admitted": "sites:2",
    "symptom": "a fabricated class used by the error-management probe to test every gate.",
    "root_cause": "`tools/dev/mail_red_verdict.py:57` — the probe cites a real file:line.",
    "cause_evidence": "read (tools/dev/mail_red_verdict.py:57)",
    "long_term_fix": "none — this class exists only inside the probe's scratch worktree.",
    "signature": "`true`",
    "seen_red": ("self-proving (tests/test_an_smtp_login_is_over_a_verified_channel.py::"
                 "test_the_detector_sees_the_defect_it_is_written_for)"),
    "guard": "{ type: pytest, ref: tests/test_an_smtp_login_is_over_a_verified_channel.py }",
    "guard_scope": ("un-garde-qui-ne-garde-pas — the probe ; couvre: the gates ; "
                    "ne couvre pas: anything outside the scratch worktree"),
    "siblings": ("swept:2026-09-26 — `sibling-sweeper` : 12 candidates → 10 excluded "
                 "(not the defect) → **2 sites vivants** (a.py:1, b.py:2)"),
    "first_seen": "2099-01-01",
}


def render(fields: dict) -> str:
    return f"\n## {CID}\n" + "".join(f"- {k}: {v}\n" for k, v in fields.items() if v is not None)


@dataclass
class Probe:
    name: str
    breaks: dict = field(default_factory=dict)   # field -> new value (None = removed)
    regenerate: bool = True                      # regenerate generated docs before the gates
    guaranteed_by: str = ""


PROBES = [
    Probe("no family", {"family": None},
          guaranteed_by="audit_runner --admission (ci.yml) · test_a_new_class_justifies_its_existence.py"),
    Probe("unknown family", {"family": "nope"},
          guaranteed_by="audit_runner --admission"),
    Probe("no admission ticket", {"admitted": None},
          guaranteed_by="audit_runner --admission · test_a_new_class_justifies_its_existence.py"),
    Probe("ticket sites:1", {"admitted": "sites:1"},
          guaranteed_by="audit_runner --admission"),
    # NOT probed: a `sites:N` ticket above the sweep's count. Measured on the 14 classes
    # admitted since 2026-09-19, the ticket counts sites AT admission and the sweep the sites
    # still live after the fix — different moments (see audit_runner.proof_gaps).
    Probe("no whole-repo sweep (not-swept)", {"siblings": "not-swept"},
          guaranteed_by="test_the_error_class_health_only_improves.py::test_no_hole_counter_ever_grows (siblings_never_swept = 0)"),
    Probe("no siblings field", {"siblings": None},
          guaranteed_by="test_no_hole_counter_ever_grows (siblings_never_swept = 0)"),
    Probe("sweep that only re-ran the guard",
          {"siblings": "swept:2026-09-26 — re-ran the guard, green"},
          guaranteed_by="audit_runner --sweep-verdict (ci.yml) · sites_unknown = 0"),
    Probe("sweep without a readable count", {"siblings": "swept:2026-09-26 — looked around"},
          guaranteed_by="audit_runner --sweep-verdict · sites_unknown = 0"),
    Probe("no root cause", {"root_cause": None},
          guaranteed_by="test_every_error_class_is_complete.py::test_a_class_names_its_cause_and_its_end"),
    Probe("root cause without file:line", {"root_cause": "it broke somehow",
                                           "cause_evidence": "read"},
          guaranteed_by="R185 — audit_runner --admission"),
    Probe("cause only inferred", {"cause_evidence": "inferred"},
          guaranteed_by="test_no_hole_counter_ever_grows (cause_inferred = 0)"),
    Probe("cause evidence missing", {"cause_evidence": None},
          guaranteed_by="test_no_hole_counter_ever_grows (cause_unknown, ceiling full) · R185"),
    Probe("guard never seen red (reason given)", {"seen_red": "never — no fixture can reach it yet"},
          guaranteed_by="test_no_hole_counter_ever_grows (guard_does_not_prove_itself, ceiling full)"),
    Probe("self-proof naming a missing test",
          {"seen_red": "self-proving (tests/test_nope.py::test_nope)"},
          guaranteed_by="test_a_self_proving_claim_names_a_real_test.py"),
    Probe("generated documents left stale", {}, regenerate=False,
          guaranteed_by="error_class_health --check (ci.yml) · error_class_families --check"),
    Probe("seen_red never, without a reason", {"seen_red": "never"},
          guaranteed_by="R185 — audit_runner --admission"),
    Probe("cause inferred, without file:line", {"cause_evidence": "inferred",
                                                "root_cause": "probably a race somewhere"},
          guaranteed_by="R185 — audit_runner --admission"),
]

# (label, argv, kind) — what CI runs on the catalogue, from the scratch worktree root.
GATES = [
    ("admission", [PY, ".claude/scripts/audit_runner.py", "--admission"]),
    ("sweep-verdict", [PY, ".claude/scripts/audit_runner.py", "--sweep-verdict"]),
    ("health --check", [PY, "tools/dev/error_class_health.py", "--check"]),
    ("families --check", [PY, "tools/dev/error_class_families.py", "--check"]),
    ("catalogue tests", [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "no:randomly",
                         "tests/test_every_error_class_is_complete.py",
                         "tests/test_error_class_index_is_complete.py",
                         "tests/test_a_self_proving_claim_names_a_real_test.py",
                         "tests/test_every_family_rule_has_a_proven_detector.py",
                         "tests/test_the_error_class_health_only_improves.py::test_no_hole_counter_ever_grows"]),
]


# What ci.yml must still run — a gate that exists but is no longer wired refuses nothing.
CI_WIRING = {
    "admission": "audit_runner.py --admission",
    "sweep-verdict": "audit_runner.py --sweep-verdict",
    "health --check": "error_class_health.py --check",
    "static signatures": "audit_runner.py --static",
}


def unwired(ci_text: str) -> list[str]:
    """The gates `ci.yml` no longer runs. Pure."""
    flat = " ".join(ci_text.split())
    return sorted(g for g, cmd in CI_WIRING.items() if cmd not in flat)


def insert_class(text: str, fields: dict) -> str:
    """The catalogue with the probe class appended and indexed. Pure."""
    row = (f"| [{CID}](#{CID}) | {fields.get('severity') or 'P3'} | "
           f"{fields.get('kind') or 'deterministic'} | {fields.get('status') or 'guarded'} | none |\n")
    m = re.search(r"^\| CLASS-ID .*\n\|[-| ]+\|\n", text, re.M)
    if m:
        text = text[:m.end()] + row + text[m.end():]
    return text.rstrip("\n") + "\n" + render(fields)


def run_gates(root: Path, regenerate: bool) -> dict[str, int]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if regenerate:
        for gen in ("tools/dev/error_class_health.py", "tools/dev/error_class_families.py"):
            subprocess.run([PY, gen], cwd=root, capture_output=True, env=env, timeout=600)
    out = {}
    for label, argv in GATES:
        r = subprocess.run(argv, cwd=root, capture_output=True, text=True, env=env, timeout=900)
        out[label] = r.returncode
    return out


def probe_hook(root: Path) -> int:
    """The commit hook on a catalogue diff adding the probe class, in a worktree whose
    transcripts hold no sweeper call. Returns the hook's exit code."""
    payload = {"tool_name": "Bash", "tool_input": {"command": "git add -A && git commit -m probe"},
               "cwd": str(root)}
    # The worktree lives under a temp path: its transcript folder (~/.claude/projects/<slug>)
    # is empty, so no sweeper call can be found — the hook must refuse.
    r = subprocess.run([PY, ".claude/hooks/require_sweep_before_catalogue.py"], cwd=root,
                       input=json.dumps(payload), capture_output=True, text=True, timeout=120)
    return r.returncode


def probe_terminal_commit(root: Path) -> int:
    """A plain `git commit` of the probe class, outside Claude Code: its exit code."""
    subprocess.run(["git", "add", CATALOGUE], cwd=root, capture_output=True)
    r = subprocess.run(["git", "-c", "user.email=p@p", "-c", "user.name=probe", "commit", "-q",
                        "-m", "probe", "--", CATALOGUE], cwd=root, capture_output=True, text=True,
                       timeout=600)
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only", default="", help="comma-separated probe names")
    a = ap.parse_args()
    rows, ok = [], True
    import yaml  # noqa: PLC0415
    wf = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").open(encoding="utf-8"))
    missing = unwired("\n".join(s.get("run") or "" for job in wf["jobs"].values()
                                for s in job.get("steps", [])))
    ok &= not missing
    rows.append(("ci.yml still wires every gate", "all wired", {g: 1 for g in missing},
                 not missing, "tests/test_the_error_management_chain_refuses_every_defect.py"))
    tmp = Path(tempfile.mkdtemp(prefix="error-probe-"))
    wt = tmp / "wt"
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(wt), "HEAD"], cwd=REPO,
                   check=True, capture_output=True)
    try:
        if (REPO / ".venv").exists() and not (wt / ".venv").exists():
            (wt / ".venv").symlink_to(REPO / ".venv")
        cat = wt / CATALOGUE
        original = cat.read_text(encoding="utf-8")

        def attempt(fields: dict, regenerate: bool) -> dict[str, int]:
            subprocess.run(["git", "checkout", "-q", "--", "."], cwd=wt, capture_output=True)
            cat.write_text(insert_class(original, fields), encoding="utf-8")
            return run_gates(wt, regenerate)

        control = attempt(dict(CONTROL), True)
        control_ok = all(rc == 0 for rc in control.values())
        ok &= control_ok
        rows.append(("CONTROL (valid new class)", "all green", control, control_ok, "—"))
        wanted = {n.strip() for n in a.only.split(",") if n.strip()}
        for p in PROBES:
            if wanted and p.name not in wanted:
                continue
            fields = dict(CONTROL)
            for k, v in p.breaks.items():
                fields[k] = v
            res = attempt(fields, p.regenerate)
            refused = any(rc != 0 for rc in res.values())
            ok &= refused
            rows.append((p.name, "refused", res, refused, p.guaranteed_by))
        subprocess.run(["git", "checkout", "-q", "--", "."], cwd=wt, capture_output=True)
        cat.write_text(insert_class(original, dict(CONTROL)), encoding="utf-8")
        hook_rc = probe_hook(wt)
        hook_ok = hook_rc == 2
        ok &= hook_ok
        rows.append(("commit via Claude Code, no sweeper call", "hook exit 2",
                     {"hook": hook_rc}, hook_ok, "test_the_catalogue_needs_a_real_sweep.py"))
        term_rc = probe_terminal_commit(wt)
        term_ok = term_rc != 0
        ok &= term_ok
        rows.append(("plain `git commit` from a terminal, no sweep", "refused",
                     {"git commit": term_rc}, term_ok, "R186 — pre-commit hook catalogue-sweep"))
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO,
                       capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)

    if a.json:
        print(json.dumps([{"probe": r[0], "expected": r[1], "gates": r[2], "ok": r[3],
                           "guaranteed_by": r[4]} for r in rows], ensure_ascii=False, indent=1))
    else:
        print("| probe | expected | red gates | verdict | guaranteed by |")
        print("|---|---|---|---|---|")
        for name, exp, res, good, by in rows:
            red = ", ".join(f"{k} ({v})" for k, v in res.items() if v != 0) or "—"
            print(f"| {name} | {exp} | {red} | {'✅' if good else '❌'} | {by} |")
        print(f"\n{'✅ every gate refuses its defect' if ok else '❌ at least one gate does not refuse'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
