"""The MANIFEST `engineering-loop.js` returns keeps refused designs out of the fixes.

Type: Test
Uses: node, .claude/workflows/engineering-loop.js
Depends on: node on PATH (skips loudly without it) — no agent is spawned: `agent()`,
    `pipeline()`, `parallel()`, `phase()`, `log()` and `args` are simulated, and each fake
    agent answers in the shape of the schema its phase declares (IMPACT, VERDICT, PATCH,
    COMPLETENESS), keyed on `opts.phase` / `opts.label`.
Persists in: nothing — the harness reads the script and prints JSON on stdout.
Mutation record (2026-10-04): the Fix-phase gate `if (verdict.verdict === 'DO-NOT-BUILD')`
    rewritten to `if (verdict.verdict === 'NEVER')` (a refused design is patched anyway) ->
    `test_a_refused_design_never_reaches_the_fixes` went red on
    `AssertionError: a DO-NOT-BUILD design was sent to a Fix agent: ['fix:01', 'fix:02']`;
    file restored, `git diff --exit-status .claude/workflows/engineering-loop.js` -> 0.

REQ-HARN-09 (R360). Until this file the script was only syntax-checked (`node --check`)
and its prompts checked by `test_the_engineering_loop_sends_real_prompts.py`; nothing
verified the object it RETURNS — the only thing the main context acts on. Its contract,
read from the script: a DO-NOT-BUILD design never reaches a Fix agent and carries no
diff, it still appears in the manifest as a ROADMAP brick with the critic's reason; the
script itself never commits and never writes the ROADMAP — both are left to the
`deploy_order` it hands back.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / ".claude/workflows/engineering-loop.js"

# Finding 1 is approved (BUILD), finding 2 is refused (DO-NOT-BUILD).
_FINDINGS = ["first defect: X at a.py:12", "second defect: Y at b.py:40"]

_HARNESS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[1], 'utf8').replace(/^export const meta\s*=/m, 'const meta =');
const calls = [];
const agent = async (prompt, opts) => {
  const label = opts.label, phase = opts.phase;
  calls.push({ label, phase, isolation: opts.isolation || null, agentType: opts.agentType || null, prompt });
  const n = label.split(':')[1];
  if (phase === 'Impact') return {
    title: `defect ${n}`, root_cause: `file.py:${n}`, is_real: true, error_class: '',
    siblings: [{ path: `s${n}.py`, same_bug: true, why: 'same call' }],
    fix_scope: 'file.py', guard_plan: 'a test + its mutation',
    decides_irreversible: false, confidence: 'read', repro_command: `python3 repro_${n}.py` };
  if (phase === 'Critic') return n === '01'
    ? { verdict: 'BUILD', reason: 'sound as designed' }
    : { verdict: 'DO-NOT-BUILD', reason: 'refused: hides a tenant coupling' };
  if (phase === 'Fix') return {
    applied: true, files_touched: [`fixed_${n}.py`], diff: `diff --git a/fixed_${n}.py`,
    guard: `tests/test_${n}.py`, mutation_result: 'AssertionError fired', mutation_verified: true };
  if (phase === 'Improve') return {
    open_classes: [], what_was_not_swept: 'the stub swept nothing',
    proposed_detectors: [{ detector: 'one grep', covers: 'both | defects', measured_by: 'make detect' }] };
  throw new Error(`unexpected phase ${phase}`);
};
const pipeline = async (items, ...stages) => Promise.all(items.map(async (it, i) => {
  let r = it; for (const s of stages) { r = await s(r, it, i); if (r == null) break; } return r; }));
const parallel = async (ts) => Promise.all(ts.map(t => t()));
const log = () => {}; const phase = () => {};
const args = JSON.parse(process.argv[2]);
const body = new Function('agent', 'pipeline', 'parallel', 'log', 'phase', 'args', 'budget', 'workflow',
  `return (async () => { ${src} })()`);
body(agent, pipeline, parallel, log, phase, args, {total: null}, async () => null)
  .then(result => process.stdout.write(JSON.stringify({ result, calls })))
  .catch(e => process.stdout.write(JSON.stringify({ error: String(e && e.stack || e), calls })));
"""


def _exercise(args) -> dict:
    if not shutil.which("node"):
        pytest.skip("node absent — the loop cannot be exercised here")
    r = subprocess.run(["node", "-e", _HARNESS, str(_SCRIPT), json.dumps(args)],
                       capture_output=True, text=True, timeout=60)
    out = json.loads(r.stdout or "{}")
    assert "error" not in out, f"the script crashed under the harness: {out.get('error')}\n{r.stderr}"
    assert out.get("result"), f"the script returned nothing: stdout={r.stdout!r} stderr={r.stderr!r}"
    return out


@pytest.fixture(scope="module")
def run() -> dict:
    return _exercise(_FINDINGS)


# baseline T110 — a repo whose docs live elsewhere, with no code-critic agent, declares it.
_DECLARED = {"findings": _FINDINGS, "roadmap": "docs/roadmap/checklist.md", "prefix": "T",
             "method": "docs/METHOD.md", "critic_agent": None, "batch": "python3 -m pytest -q"}


@pytest.fixture(scope="module")
def declared() -> dict:
    return _exercise(_DECLARED)


def _entry(manifest: list, title: str) -> dict:
    hits = [m for m in manifest if m.get("title") == title]
    assert len(hits) == 1, f"expected one manifest entry titled {title!r}, got {manifest}"
    return hits[0]


def test_the_manifest_covers_every_finding(run) -> None:
    summary = run["result"]["summary"]
    assert summary["findings"] == 2 and summary["in_manifest"] == 2, summary
    assert summary["dropped_still_open"] == 0, summary
    assert (summary["patched"], summary["refused"]) == (1, 1), summary


def test_a_refused_design_never_reaches_the_fixes(run) -> None:
    fix_labels = [c["label"] for c in run["calls"] if c["phase"] == "Fix"]
    assert fix_labels == ["fix:01"], f"a DO-NOT-BUILD design was sent to a Fix agent: {fix_labels}"
    refused = _entry(run["result"]["manifest"], "defect 02")
    assert refused["verdict"] == "DO-NOT-BUILD"
    assert refused["files_touched"] == [] and not refused["diff"], refused
    # Refused is not dropped: it reaches the manifest as a brick carrying the critic's reason.
    assert refused["critic_reason"] == "refused: hides a tenant coupling"
    assert refused["roadmap_action"].startswith("brick:"), refused["roadmap_action"]


def test_an_approved_design_ships_its_diff(run) -> None:
    built = _entry(run["result"]["manifest"], "defect 01")
    assert built["verdict"] == "BUILD"
    assert built["files_touched"] == ["fixed_01.py"]
    assert built["diff"] == "diff --git a/fixed_01.py", "the patch must travel back as data"
    assert built["mutation_verified"] is True
    assert not built["roadmap_action"].startswith("brick:"), built["roadmap_action"]


def test_the_fix_runs_isolated_and_the_script_neither_commits_nor_writes_the_roadmap(run) -> None:
    fixes = [c for c in run["calls"] if c["phase"] == "Fix"]
    assert all(c["isolation"] == "worktree" for c in fixes), fixes
    for c in fixes:
        assert "DO NOT: git add, git commit, git push, or edit .claude/dev-docs/roadmap" in c["prompt"]
    # The commit and the ROADMAP are handed back as steps for the main context, in that order.
    order = run["result"]["deploy_order"]
    roadmap_step = next(i for i, s in enumerate(order) if "ROADMAP first" in s)
    commit_step = next(i for i, s in enumerate(order) if "commit the approved fixes" in s)
    assert roadmap_step < commit_step, order
    assert run["result"]["completeness"]["what_was_not_swept"], "the Improve answer is missing"


def test_an_array_call_keeps_the_critic_agent_and_this_repo_s_paths(run) -> None:
    critics = [c for c in run["calls"] if c["phase"] == "Critic"]
    assert critics and all(c["agentType"] == "code-critic" for c in critics), critics
    assert ".claude/skills/impact-analysis/SKILL.md" in run["calls"][0]["prompt"]


def test_a_repo_declares_its_docs_and_goes_without_a_critic_agent(declared) -> None:
    """Mutation (2026-10-18): `...(DOCS.critic ? …)` → `agentType: 'code-critic'` → red here."""
    calls = declared["calls"]
    assert declared["result"]["summary"]["in_manifest"] == 2
    assert [c["agentType"] for c in calls if c["phase"] == "Critic"] == [None, None]
    assert "docs/METHOD.md" in calls[0]["prompt"] and "impact-analysis/SKILL.md" not in calls[0]["prompt"]
    fix = next(c for c in calls if c["phase"] == "Fix")
    assert "or edit docs/roadmap/checklist.md" in fix["prompt"]
    assert any("python3 -m pytest -q" in s for s in declared["result"]["deploy_order"])


def test_every_entry_and_detector_carries_a_ready_roadmap_row(declared) -> None:
    m = declared["result"]["manifest"]
    built, refused = _entry(m, "defect 01"), _entry(m, "defect 02")
    assert built["roadmap_row"] == "| Tnnn | defect 01 <!-- défaut --> | P2 | `tests/test_01.py` |"
    assert refused["roadmap_row"].startswith("| Tnnn | Refusé (DO-NOT-BUILD) : defect 02 — refused")
    assert refused["roadmap_row"].endswith("| P2 | `python3 repro_02.py` |"), refused["roadmap_row"]
    assert declared["result"]["detector_rows"] == [
        "| Tnnn | Détecteur : one grep — couvre both \\| defects | P2 | `make detect` |"]


def test_the_deploy_starts_by_checking_each_diff_applies(run) -> None:
    first = run["result"]["deploy_order"][0]
    assert first.startswith("0. `git apply --check` EACH diff") and "still OPEN" in first, first
