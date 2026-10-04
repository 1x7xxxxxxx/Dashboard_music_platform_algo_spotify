"""R363 — a test never appends to the repo's real measurement logs.

Type: Test
Uses: .claude/hooks/inject_context.py (in-process), tools/dev/roadmap.py (subprocess,
      ROADMAP_ROOT)
Depends on: nothing live
Persists in: nothing (tmp_path only)

The scenario (2026-10-04): the suite ran `inject_context.py` with a prompt and no
`session_id`, and every run added two `"session": ""` lines to the real
`.claude/sessions/injections.jsonl` — the usage counter (R357) then reported test prompts
as real skill injections. The sweep found a second live site (session_start.py run with
cwd = the repo, guarded in test_every_session_starts_by_reading_the_ops_mails.py) and a
latent one: `close_night_unit` ignored `ROADMAP_ROOT`.

Mutation record (2026-10-04): seen red with the `data.get("session_id")` condition
removed from inject_context.main (test 1), and with `nr.JOURNAL` restored as the default
journal in roadmap.close_night_unit (test 3).
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("inject_context",
                                               ROOT / ".claude/hooks/inject_context.py")
ic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ic)
PROMPT = "gitleaks a trouvé un secret exposé, c'est un bug à balayer"


def _run_hook(monkeypatch, payload: dict) -> list:
    calls: list = []
    monkeypatch.setattr(ic, "log_injection", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    with pytest.raises(SystemExit):
        ic.main()
    return calls


def test_a_payload_without_a_session_is_not_logged(monkeypatch, capsys) -> None:
    assert _run_hook(monkeypatch, {"prompt": PROMPT}) == []
    assert capsys.readouterr().out, "the hook must still inject — only the log is skipped"


def test_a_real_session_is_still_logged(monkeypatch) -> None:
    calls = _run_hook(monkeypatch, {"prompt": PROMPT, "session_id": "abc"})
    assert calls and calls[0][1] == "abc"


def test_closing_a_task_writes_the_night_journal_under_roadmap_root(tmp_path) -> None:
    d = tmp_path / ".claude" / "dev-docs" / "roadmap"
    d.mkdir(parents=True)
    journal = d / "night-run.jsonl"
    journal.write_text(json.dumps({"at": "x", "kind": "start", "task": "R900"}) + "\n")
    code = ("import sys; sys.path.insert(0, 'tools/dev'); import roadmap; "
            "print(roadmap.close_night_unit('R900', 'n'))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True,
                         text=True, timeout=60,
                         env={**os.environ, "ROADMAP_ROOT": str(tmp_path)})
    assert out.stdout.strip() == "True", out.stderr
    assert '"done"' in journal.read_text()
