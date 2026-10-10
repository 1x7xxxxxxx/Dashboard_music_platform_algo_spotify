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
sys.path.insert(0, str(REPO / ".claude" / "scripts"))
from judgement import RED, classify, looks_like_traceback  # noqa: E402 — sibling tree, R495

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
    # R264 (2026-09-28) made `closest:` mandatory on a new class; the control, left without
    # it, was refused by admission and the whole probe read red (security nightly 09-28).
    "closest": ("a-fallback-that-runs-when-the-first-branch-succeeded — a fabricated probe "
                "class, not a fallback defect"),
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


GREEN, REFUSED, CRASH = "green", "refused", "crash"

# R495 — the exit code a gate uses to REFUSE, and the line it prints when it does. A gate
# that exits non-zero without its marker (a traceback, a missing file, a usage error)
# refused nothing: it fell over, and the probe used to credit that as a refusal.
_REFUSAL = {
    "admission": (2, re.compile(r"^\s*⊘\s", re.M)),
    "sweep-verdict": (1, re.compile(r"^❌ ", re.M)),
    "health --check": (1, re.compile(r"n'est pas rangé")),
}


def gate_outcome(label: str, rc: int, output: str) -> str:
    """GREEN, REFUSED or CRASH for one gate run. Pure."""
    if rc == 0:
        return GREEN
    if label not in _REFUSAL:            # the catalogue tests: pytest's own judgement
        return REFUSED if classify(rc, output, pytest=True) == RED else CRASH
    code, marker = _REFUSAL[label]
    if rc == code and marker.search(output) and not looks_like_traceback(output):
        return REFUSED
    return CRASH


def probe_refused(outcomes: dict[str, str]) -> bool:
    """A defect is refused when one gate judged it AND no gate crashed. Pure.

    A crash next to a refusal leaves the probe unproven: the crashed gate is the one whose
    refusal it was meant to test, and nobody knows what it would have said."""
    vals = outcomes.values()
    return REFUSED in vals and CRASH not in vals


def run_gates(root: Path, regenerate: bool) -> dict[str, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if regenerate:
        # R345: only the health tool still writes a TRACKED file — the catalogue's ranking.
        # The generated documents are no longer versioned, so nothing else can go stale.
        subprocess.run([PY, "tools/dev/error_class_health.py"], cwd=root, capture_output=True,
                       env=env, timeout=600)
    out = {}
    for label, argv in GATES:
        r = subprocess.run(argv, cwd=root, capture_output=True, text=True, env=env, timeout=900)
        out[label] = gate_outcome(label, r.returncode, r.stdout + r.stderr)
    return out


def probe_hook(root: Path) -> tuple[int, str]:
    """The commit hook on a catalogue diff adding the probe class, in a worktree whose
    transcripts hold no sweeper call. Returns the hook's exit code and output."""
    payload = {"tool_name": "Bash", "tool_input": {"command": "git add -A && git commit -m probe"},
               "cwd": str(root)}
    # The worktree lives under a temp path: its transcript folder (~/.claude/projects/<slug>)
    # is empty, so no sweeper call can be found — the hook must refuse.
    r = subprocess.run([PY, ".claude/hooks/require_sweep_before_catalogue.py"], cwd=root,
                       input=json.dumps(payload), capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def hook_refused(rc: int, output: str) -> bool:
    """The Claude Code hook refused — exit 2 AND its own `🚫 BLOCKED` line. Pure."""
    return rc == 2 and "🚫 BLOCKED" in output and not looks_like_traceback(output)


def commit_refused(rc: int, output: str) -> bool:
    """The terminal commit was refused BY the catalogue-sweep check, not by any other
    pre-commit failure (a missing tool, a crashing hook). Pure."""
    return rc != 0 and "🚫 catalogue-sweep —" in output


def probe_terminal_commit(root: Path) -> tuple[int, str]:
    """A plain `git commit` of the probe class, outside Claude Code: exit code and output."""
    subprocess.run(["git", "add", CATALOGUE], cwd=root, capture_output=True)
    # An EMPTY transcript folder: the check must find no sweep and refuse. Without one it
    # stands aside by design (CI, another machine) — which would read as a pass here.
    empty = root.parent / "empty-transcripts"
    empty.mkdir(exist_ok=True)
    env = {**os.environ, "HOOK_TRANSCRIPTS_DIR": str(empty)}
    r = subprocess.run(["git", "-c", "user.email=p@p", "-c", "user.name=probe", "commit", "-q",
                        "-m", "probe", "--", CATALOGUE], cwd=root, capture_output=True, text=True,
                       env=env, timeout=600)
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only", default="", help="comma-separated probe names")
    a = ap.parse_args()
    # R331 (2026-09-29): the night WSL froze, this probe ran beside a full-size suite. It
    # holds the same lock as the test targets now (fd non-inheritable: its child pytest does
    # not keep it), and it never calls a `make test*` target, which would wait on itself.
    sys.path.insert(0, str(REPO / "tools" / "dev"))
    from heavy_lock import acquire  # noqa: PLC0415
    lock_fd = acquire("error-management-probe", float(os.environ.get("HEAVY_WAIT", "900")))
    if lock_fd is None:
        print("❌ une suite tient encore ~/.cache/heavy-memory.lock après l'attente — "
              "relancer quand elle a fini (`python3 tools/dev/heavy_lock.py` dit qui).")
        return 2
    subprocess.Popen([PY, str(REPO / "tools/dev/mem_trace.py"), "--label", "probe", "--watch",
                      str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

        def attempt(fields: dict, regenerate: bool) -> dict[str, str]:
            subprocess.run(["git", "checkout", "-q", "--", "."], cwd=wt, capture_output=True)
            cat.write_text(insert_class(original, fields), encoding="utf-8")
            return run_gates(wt, regenerate)

        control = attempt(dict(CONTROL), True)
        control_ok = all(o == GREEN for o in control.values())
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
            refused = probe_refused(res)
            ok &= refused
            rows.append((p.name, "refused", res, refused, p.guaranteed_by))
        subprocess.run(["git", "checkout", "-q", "--", "."], cwd=wt, capture_output=True)
        cat.write_text(insert_class(original, dict(CONTROL)), encoding="utf-8")
        hook_rc, hook_out = probe_hook(wt)
        hook_ok = hook_refused(hook_rc, hook_out)
        ok &= hook_ok
        rows.append(("commit via Claude Code, no sweeper call", "hook exit 2",
                     {"hook": REFUSED if hook_ok else f"{CRASH if hook_rc else GREEN} (exit {hook_rc})"},
                     hook_ok, "test_the_catalogue_needs_a_real_sweep.py"))
        term_rc, term_out = probe_terminal_commit(wt)
        term_ok = commit_refused(term_rc, term_out)
        ok &= term_ok
        rows.append(("plain `git commit` from a terminal, no sweep", "refused",
                     {"git commit": REFUSED if term_ok else f"{CRASH if term_rc else GREEN} (exit {term_rc})"},
                     term_ok, "R186 — pre-commit hook catalogue-sweep"))
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
            red = ", ".join(f"{k} ({v})" for k, v in res.items() if v not in (0, GREEN)) or "—"
            print(f"| {name} | {exp} | {red} | {'✅' if good else '❌'} | {by} |")
        print(f"\n{'✅ every gate refuses its defect' if ok else '❌ at least one gate does not refuse'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
