"""A full or selected suite runs in a memory-capped, niced scope — never beside VS Code bare.

Type: Sub
Uses: Makefile, systemd-run (optional)
Depends on: nothing for the static checks; a systemd user manager for the live one

R352 (2026-10-04): VS Code Remote WSL dropped three times in twenty minutes. The kernel
log showed order-7 allocation failures in `hvs_probe` — the Hyper-V socket VS Code uses
to reach Windows could not get its ring buffer — with swap full and a load of 32, during
a `make test-changed` already at the floor of 2 workers. A worker count cannot stop one
test or one process from taking the rest; a cgroup can, and it makes the OOM killer pick
inside the suite.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_MAKEFILE = Path(__file__).resolve().parents[1] / "Makefile"


def _suite_lines(text: str) -> list[str]:
    """Recipe lines that run the whole suite or the selected one."""
    return [ln for ln in text.splitlines() if ln.startswith("\t")
            and re.search(r"-m pytest (tests/ -q|-q \$\(PYTEST_DIST\))", ln)]


def _unscoped(text: str) -> list[str]:
    return [ln for ln in _suite_lines(text)
            if not re.search(r"\$\(SUITE_SCOPE\) \$\(PYTHON\) -m pytest", ln)]


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    bare = "test:\n\t@bash -c '$(HOLD_HEAVY_LOCK) $(PYTHON) -m pytest tests/ -q $(PYTEST_DIST)'\n"
    assert _unscoped(bare)


def test_every_suite_line_runs_in_the_scope() -> None:
    text = _MAKEFILE.read_text(encoding="utf-8")
    assert len(_suite_lines(text)) >= 3, "the suite targets moved — re-anchor this guard"
    assert not _unscoped(text), _unscoped(text)


def test_the_scope_caps_memory_and_lowers_priority() -> None:
    text = _MAKEFILE.read_text(encoding="utf-8")
    scope = re.search(r"^SUITE_SCOPE = ((?:.*\\\n)*.*)", text, re.M)
    assert scope, "SUITE_SCOPE disappeared"
    body = scope.group(1)
    assert "MemoryMax=" in body and "MemoryHigh=" in body
    assert "nice -n" in body, "without nice, a loaded CPU starves VS Code's heartbeats"


@pytest.mark.skipif(shutil.which("systemd-run") is None, reason="no systemd-run")
def test_the_cap_kills_inside_the_scope() -> None:
    probe = subprocess.run(["systemd-run", "--user", "--scope", "-q", "true"],
                           capture_output=True, timeout=20)
    if probe.returncode != 0:
        pytest.skip("no systemd user manager (CI, container)")
    hog = "b = bytearray(300 * 1024 * 1024); b[::4096] = b'x' * len(b[::4096])"
    r = subprocess.run(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=64M",
                        "-p", "MemorySwapMax=0", "--", "python3", "-c", hog],
                       capture_output=True, timeout=60)
    assert r.returncode != 0, "a 300 Mo allocation survived a 64 Mo cap"
