"""A test directory git ignores is not part of the suite — the selector must not pick it.

Baseline T96 (2026-10-18): on assistant_perso, `vendor/hermes-agent` (git-ignored, not in
PRUNE) put 157 vendored tests in front of a two-hook diff; 337 went red and the push was
refused for code nobody had touched."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _select_tests():
    spec = importlib.util.spec_from_file_location("_st_ignored", ROOT / ".claude/scripts/select_tests.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_walk_prunes_an_ignored_directory(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("vendor/\n")
    for rel in ("tests/test_mine.py", "vendor/lib/tests/test_theirs.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("def test_x():\n    pass\n")
    walked = {p.relative_to(tmp_path).as_posix() for p in _select_tests()._walk_python(tmp_path)}
    assert "tests/test_mine.py" in walked
    assert not any(w.startswith("vendor/") for w in walked), walked


def test_a_declared_root_inside_an_ignored_directory_is_still_walked(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("gen/\n")
    (tmp_path / "gen/pkg").mkdir(parents=True)
    (tmp_path / "gen/pkg/m.py").write_text("X = 1\n")
    walked = _select_tests()._walk_python(tmp_path, [tmp_path, tmp_path / "gen/pkg"])
    assert tmp_path / "gen/pkg/m.py" in walked
