"""R705 — `make hooks-install` must not silently unwrap the fleet's pre-push wrapper.

Type: Test
Uses: tools/dev/restore_pre_push_wrapper.py, the real `pre-commit install`, Makefile

The wrapper was moved to `pre-push.legacy` on 2026-10-26 and pushes stopped reaching
gate-timings, with every gate still green.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "restore_pre_push_wrapper", ROOT / "tools/dev/restore_pre_push_wrapper.py")
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)

WRAPPER = f"""#!/usr/bin/env bash
# {tool.MARK}

# start templated
INSTALL_PYTHON=/stale/python
ARGS=(hook-impl --config=.pre-commit-config.yaml --hook-type=pre-push)
# end templated

exit 0
"""


def _clean_env() -> dict:
    # The suite also runs inside a commit hook, where GIT_DIR points at the real repo.
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _install(repo: Path) -> None:
    subprocess.run([sys.executable, "-m", "pre_commit", "install", "--hook-type", "pre-push"],
                   cwd=repo, env=_clean_env(), check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, env=_clean_env(), check=True)
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    return tmp_path


def _hook(repo: Path) -> Path:
    return repo / ".git/hooks/pre-push"


def test_the_wrapper_survives_two_installs_in_a_row(repo):
    _hook(repo).write_text(WRAPPER, encoding="utf-8")
    for _ in range(2):
        _install(repo)
        assert tool.MARK not in _hook(repo).read_text(encoding="utf-8"), "premise: installer unwraps"
        assert tool.restore(_hook(repo)) == "restored"
        text = _hook(repo).read_text(encoding="utf-8")
        assert tool.MARK in text
        assert "/stale/python" not in text, "the templated block must come from the fresh hook"
        assert os.access(_hook(repo), os.X_OK)
        assert not _hook(repo).with_name("pre-push.legacy").exists()


def test_a_wrapper_already_in_place_is_left_alone(repo):
    _hook(repo).write_text(WRAPPER, encoding="utf-8")
    assert tool.restore(_hook(repo)) == "in-place"
    assert _hook(repo).read_text(encoding="utf-8") == WRAPPER


def test_a_foreign_legacy_hook_is_not_touched(repo):
    _hook(repo).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    _install(repo)
    framework = _hook(repo).read_text(encoding="utf-8")
    assert tool.restore(_hook(repo)) == "nothing-to-restore"
    assert _hook(repo).read_text(encoding="utf-8") == framework
    assert _hook(repo).with_name("pre-push.legacy").exists()


def test_no_wrapper_at_all_is_a_no_op(repo):
    _install(repo)
    assert tool.restore(_hook(repo)) == "nothing-to-restore"


def test_a_hook_without_a_template_keeps_the_wrapper_and_fails(repo):
    _hook(repo).write_text("#!/bin/sh\n", encoding="utf-8")
    _hook(repo).with_name("pre-push.legacy").write_text(WRAPPER, encoding="utf-8")
    assert tool.main(["x", str(_hook(repo))]) == 1
    assert _hook(repo).with_name("pre-push.legacy").exists()


def test_hooks_install_restores_right_after_the_installer():
    make = (ROOT / "Makefile").read_text(encoding="utf-8")
    recipe = make[make.index("\nhooks-install:"):make.index("##@ Graphe & divers")]
    assert recipe.index("@pre-commit install") < recipe.index("restore_pre_push_wrapper.py")
