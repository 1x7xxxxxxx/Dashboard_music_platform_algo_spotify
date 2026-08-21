"""A .env resolved against the CWD loads nothing, silently. Pin it to the repo root.

Two failures on 2026-08-21, one class:
  - `make artist-preflight` printed "central app NOT configured" for credentials that
    were present in .env but absent from that shell;
  - `src/dashboard/app.py` tested os.path.exists('.env.local') relative to the cwd,
    while the documented launch is `cd src/dashboard && streamlit run app.py`.
    load_dotenv() returned False and said nothing.

Error class: env-resolved-against-cwd (.claude/dev-docs/error-classes.md).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Every entrypoint a human starts from a shell, where no environment is injected.
SHELL_ENTRYPOINTS = [
    "tools/artist_preflight.py",
    "tools/create_canary.py",
    "tools/tenant_contamination_check.py",
    "tools/dev/soundcloud_oauth_authorize.py",
    "src/dashboard/app.py",
]


@pytest.mark.parametrize("rel", SHELL_ENTRYPOINTS)
def test_every_shell_entrypoint_loads_the_project_env(rel: str) -> None:
    """It must call the root-anchored loader, not re-implement a cwd-relative one."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert "load_project_env" in text, (
        f"{rel} reads its configuration from a bare shell without loading .env. "
        "Call src.utils.env_files.load_project_env()."
    )


@pytest.mark.parametrize("rel", SHELL_ENTRYPOINTS)
def test_no_entrypoint_resolves_an_env_file_against_the_cwd(rel: str) -> None:
    """The exact shape that failed: a bare relative '.env' handed to the filesystem."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    for bad in ("exists('.env", 'exists(".env', "load_dotenv('.env", 'load_dotenv(".env'):
        assert bad not in text, (
            f"{rel} resolves an env file against the CWD ({bad}…). Run from any other "
            "directory and it loads nothing, without raising."
        )


def test_the_loader_finds_the_files_from_an_unrelated_cwd() -> None:
    """The effect, not the artefact: run it from /tmp and it must still resolve."""
    from src.utils.env_files import ENV_FILES, PROJECT_ROOT

    assert PROJECT_ROOT == ROOT, "PROJECT_ROOT drifted from the repository root"
    present = [n for n in ENV_FILES if (PROJECT_ROOT / n).is_file()]
    if not present:
        pytest.skip("no .env file on this machine — nothing to resolve")

    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "from src.utils.env_files import load_project_env\n"
        "print(','.join(load_project_env()))\n" % str(ROOT)
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=os.sep + "tmp",
        capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    loaded = [x for x in out.stdout.strip().split(",") if x]
    assert loaded == present, (
        f"from /tmp the loader resolved {loaded}, expected {present} — it is "
        "still following the caller's cwd."
    )


def test_an_injected_variable_is_never_overridden_by_a_file() -> None:
    """Airflow injects the real environment; a stale .env must not win over it."""
    from src.utils.env_files import ENV_FILES, PROJECT_ROOT, load_project_env

    if not any((PROJECT_ROOT / n).is_file() for n in ENV_FILES):
        pytest.skip("no .env file on this machine")

    key = "SPOTIFY_CLIENT_ID"
    sentinel = "injected-wins-9f3c"
    before = os.environ.get(key)
    os.environ[key] = sentinel
    try:
        load_project_env()
        assert os.environ[key] == sentinel, (
            "load_project_env() overwrote an already-injected variable — inside a "
            "container that silently swaps the real credentials for a stale file's."
        )
    finally:
        if before is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = before
