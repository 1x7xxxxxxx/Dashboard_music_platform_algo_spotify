"""A security finding injects the bug-resolution playbook, whose step 2 spawns the sweep.

Type: Sub
Uses: .claude/hooks/inject_context.py, .claude/workflows/bug-resolution.md
Depends on: python3 — the hook runs as a subprocess on a fabricated prompt

2026-09-25: gitleaks found 12 real secrets; the triage went to `security-specialist` and
no sibling sweep ran until the owner asked. The prompts of that day named « gitleaks »,
« secret », « fuite » — none was a keyword of the playbook, so it was never injected.
"""
import json
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_HOOK = _ROOT / ".claude/hooks/inject_context.py"
_MARK = "Workflow — bug resolution"


def _injects(prompt: str) -> bool:
    r = subprocess.run(["python3", str(_HOOK)], input=json.dumps({"prompt": prompt}),
                       capture_output=True, text=True, timeout=30, cwd=_ROOT)
    return _MARK in r.stdout


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    assert _injects("gitleaks a trouvé un secret dans l'historique public")
    assert _injects("il y a une fuite, le credential Spotify est exposé")
    assert not _injects("ajoute une colonne au tableau de la vue revenus"), \
        "an unrelated prompt must not drag the playbook in"
