"""R317 — `make night-status` says a suite is running only when one is, and names it.

Type: Test
Uses: tools/dev/night_run.py (`is_a_suite`, `_suite_running`)
Depends on: nothing live
Persists in: nothing

2026-09-29 00:40: « UNE SUITE TOURNE » with no pytest process left to find, and nothing in
the line to check the claim against. A `--collect-only` pass (the pre-commit duration check
collects the whole suite) runs no test, so no edit can falsify its verdict.

Mutation record (2026-09-29): seen red with the `collects_only` clause removed, and with the
pid/argv dropped from what `_suite_running` returns.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dev"))

import night_run  # noqa: E402


def test_a_real_suite_is_seen_and_a_collection_is_not() -> None:
    assert night_run.is_a_suite([".venv/bin/python", "-m", "pytest", "tests/", "-n", "4"])
    assert night_run.is_a_suite(["/x/.venv/bin/pytest", "tests/test_a.py"])
    assert not night_run.is_a_suite(["python3", "-m", "pytest", "tests/", "--collect-only"])
    assert not night_run.is_a_suite(["pytest", "--co", "-q", "tests"])
    assert not night_run.is_a_suite(["bash", "-c", "echo pytest tests/"]), (
        "a word inside a shell line is not a pytest process")


def test_the_warning_names_the_process_it_saw(tmp_path) -> None:
    (tmp_path / "4242").mkdir()
    (tmp_path / "4242" / "cmdline").write_bytes(b"python3\0-m\0pytest\0tests/\0")
    (tmp_path / "self").mkdir()
    seen = night_run._suite_running(tmp_path)
    assert seen and "4242" in seen and "pytest tests/" in seen, (
        f"the probe must say WHICH process it saw — a bare True cannot be checked: {seen!r}")
    (tmp_path / "4242" / "cmdline").write_bytes(b"python3\0-m\0pytest\0tests/\0--co\0")
    assert night_run._suite_running(tmp_path) is None
