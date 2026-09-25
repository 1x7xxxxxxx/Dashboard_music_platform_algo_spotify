"""A commit whose staged changes carry a provider-format secret is refused before it exists.

Type: Sub
Uses: tools/dev/gitleaks_staged.sh, .gitleaks.toml, .pre-commit-config.yaml, ci.yml
Depends on: git; the pinned gitleaks binary (skips loudly without it — `make hooks-install`)

The 12 secrets of the public history were committed in 2025-10, before any scanner.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[1]
_HOOK = _ROOT / "tools/dev/gitleaks_staged.sh"
_BIN = shutil.which("gitleaks") or str(Path.home() / ".local/bin/gitleaks")
# Built at run time so this file never carries the literal it tests for.
_FAKE_GCP_KEY = "AIza" + "Sy" + "Dq9x7Lm2Kp4Vn8Rt1Wc6Yb3Hj5Fg0Ze7Qs"  # pragma: allowlist secret — fabricated, GCP shape


def _repo(tmp_path: Path, content: str) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    shutil.copy(_ROOT / ".gitleaks.toml", tmp_path / ".gitleaks.toml")
    (tmp_path / "settings.py").write_text(content)
    subprocess.run(["git", "-C", str(tmp_path), "add", "settings.py"], check=True)
    return tmp_path


def _hook(repo: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(_HOOK)], cwd=repo, capture_output=True, text=True,
                          timeout=60, env=env or os.environ.copy())


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    if not os.access(_BIN, os.X_OK):
        pytest.skip("gitleaks absent — run `make hooks-install` (the commit hook would refuse too)")
    leaked = _hook(_repo(tmp_path / "a", f'YOUTUBE_API_KEY = "{_FAKE_GCP_KEY}"\n'))
    assert leaked.returncode != 0, "a staged GCP-format key went through"
    assert _FAKE_GCP_KEY not in leaked.stdout + leaked.stderr, "the hook printed the secret"
    clean = _hook(_repo(tmp_path / "b", 'YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]\n'))
    assert clean.returncode == 0, clean.stdout + clean.stderr


def test_a_missing_scanner_refuses_the_commit(tmp_path) -> None:
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    r = _hook(_repo(tmp_path / "c", "x = 1\n"), env)
    assert r.returncode == 1 and "make hooks-install" in r.stdout


def test_the_hook_and_the_ci_job_are_wired() -> None:
    hooks = [h["id"] for r in yaml.safe_load((_ROOT / ".pre-commit-config.yaml").read_text())["repos"]
             for h in r["hooks"]]
    assert "gitleaks-staged" in hooks and "detect-secrets" in hooks
    ci = yaml.safe_load((_ROOT / ".github/workflows/ci.yml").read_text())["jobs"]
    assert "secrets" in ci and "secrets" in ci["notify"]["needs"]
    assert not ci["secrets"].get("continue-on-error"), "the CI scan must BLOCK"
