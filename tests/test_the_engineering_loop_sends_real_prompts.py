"""Every Impact agent of `engineering-loop.js` receives a real prompt carrying its finding.

Type: Sub
Uses: node, .claude/workflows/engineering-loop.js
Depends on: node on PATH (skips loudly without it) — no agent is spawned, all are stubbed

On 2026-09-25 the loop ran for the first time since it was written (2026-07-27), and
both Impact agents received the literal text « NaN ». Line 154 of the prompt carried an
UNESCAPED backtick (`.claude/`): it closed the template literal mid-prompt, and what
followed still parsed — `undefined / "…"` — so `node --check` stayed green and the
prompt became NaN. The rule « ≥ 2 findings -> run engineering-loop » had pointed at a
loop that could never have worked. This test runs the script body with stub
`agent/pipeline/log`, and asserts what each Impact agent would have been told.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / ".claude/workflows/engineering-loop.js"

_HARNESS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[1], 'utf8').replace(/^export const meta\s*=/m, 'const meta =');
const prompts = [];
const agent = async (p, o) => { prompts.push(p); return { refuted: true, refutation: 'stub' }; };
const pipeline = async (items, ...stages) => Promise.all(items.map(async (it, i) => {
  let r = it; for (const s of stages) { r = await s(r, it, i); if (r == null) break; } return r; }));
const parallel = async (ts) => Promise.all(ts.map(t => t()));
const log = () => {}; const phase = () => {};
const args = JSON.parse(process.argv[2]);
const body = new Function('agent', 'pipeline', 'parallel', 'log', 'phase', 'args', 'budget', 'workflow',
  `return (async () => { ${src} })()`);
body(agent, pipeline, parallel, log, phase, args, {total: null}, async () => null)
  .catch(() => {})
  .finally(() => process.stdout.write(JSON.stringify(prompts)));
"""


def _impact_prompts(findings: list[str], script: Path = _SCRIPT) -> list:
    if not shutil.which("node"):
        pytest.skip("node absent — the loop cannot be exercised here")
    r = subprocess.run(["node", "-e", _HARNESS, str(script), json.dumps(findings)],
                       capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout or "[]")


def test_each_impact_agent_is_told_its_finding() -> None:
    findings = ["premier défaut : X au fichier a.py:12", "second défaut : Y au fichier b.py:40"]
    prompts = _impact_prompts(findings)
    assert len(prompts) >= 2, f"the loop spawned {len(prompts)} agent(s) for 2 findings"
    for f in findings:
        hits = [p for p in prompts if isinstance(p, str) and f in p]
        assert hits, (f"no agent prompt carries the finding {f!r} — prompts were "
                      f"{[p if not isinstance(p, str) else p[:40] for p in prompts]}")
        assert len(hits[0]) > 500, "the prompt is too short to be the Impact brief"
        # A template that closes RIGHT AFTER the finding would still pass the two checks
        # above (code-critic, 2026-09-25): the brief must reach its closing sentence.
        assert "This phase produces a fiche, nothing else." in hits[0], \
            "the Impact brief is cut short — its template literal closes early"


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    """The script as it was until 2026-09-25 — one unescaped backtick — must be caught."""
    broken = tmp_path / "engineering-loop.js"
    broken.write_text(_SCRIPT.read_text(encoding="utf-8").replace(
        "    \\`.claude/\\` — the config layer", "    `.claude/` — the config layer", 1),
        encoding="utf-8")
    assert broken.read_text(encoding="utf-8") != _SCRIPT.read_text(encoding="utf-8"), \
        "the mutation did not apply — the test would prove nothing"
    prompts = _impact_prompts(["premier défaut : X au fichier a.py:12"], broken)
    assert not any(isinstance(p, str) and "premier défaut" in p for p in prompts), prompts
