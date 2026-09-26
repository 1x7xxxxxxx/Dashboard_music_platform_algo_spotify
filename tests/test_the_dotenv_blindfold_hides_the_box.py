"""The plugin that plays "a CI runner with no `.env`" really hides the `.env`.

Type: Sub
Uses: .claude/scripts/pytest_without_dotenv.py, src/utils/env_files.py
Depends on: nothing — the `.env` is a tmp file; the real one is never read
Persists in: nothing

Class `guard-reads-the-box-not-its-subject`: a guard whose verdict comes from the
workstation's `.env` is green where it was written and red where it runs. The class is
detected by replaying the tests that load a `tools/` module under
`pytest_without_dotenv`, which replaces `load_project_env` with a loader that loads
nothing. If that plugin stopped hiding anything, the replay would pass on every guard
that reads the box — this file proves it still hides.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import src.utils.env_files as env_files

_PLUGIN = Path(__file__).resolve().parents[1] / ".claude" / "scripts" / "pytest_without_dotenv.py"
_KEY = "STREAMLYTICS_PROBE_ONLY_IN_THE_BOX"


def _plugin():
    spec = importlib.util.spec_from_file_location("pytest_without_dotenv_probe", _PLUGIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path, monkeypatch) -> None:
    """Non-vacuity: a value that lives ONLY in a `.env` reaches a guard through the
    real loader — the 2026-09-05 shape, green on the workstation; under the plugin the
    same loader brings nothing, so that guard would go red, as it does on a runner."""
    (tmp_path / ".env").write_text(f"{_KEY}=operator@example.test\n", encoding="utf-8")
    monkeypatch.setattr(env_files, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv(_KEY, raising=False)

    assert env_files.load_project_env() == [".env"]
    assert os.environ.get(_KEY) == "operator@example.test"

    monkeypatch.delenv(_KEY)
    # The plugin rebinds the module attribute; register it with monkeypatch first so
    # the real loader is restored after this test.
    monkeypatch.setattr(env_files, "load_project_env", env_files.load_project_env)
    _plugin().pytest_configure(None)
    assert env_files.load_project_env() == []
    assert _KEY not in os.environ
