"""R445 — `make roadmap-close ID="Ra Rb"` closes each ID and runs the readers once.

Type: Sub
Uses: Makefile (dry-run expansion through `make -n`)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _dry(ids: str) -> list[str]:
    out = subprocess.run(["make", "-n", "--no-print-directory", "roadmap-close", f"ID={ids}"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return out.splitlines()


def _run_loop(ids: str) -> list[str]:
    """Execute the expanded loop with `roadmap.py` replaced by an echo."""
    loop = next(ln for ln in _dry(ids) if "roadmap.py close" in ln)
    # one `<arg>` per argument: an ID list passed as ONE argument shows as `<R1 R2>`
    shim = loop.replace("python3 tools/dev/roadmap.py close", "printf '<%s>\\n'")
    out = subprocess.run(["sh", "-c", shim], capture_output=True, text=True, check=True)
    return [ln.strip("<>") for ln in out.stdout.splitlines()]


def test_every_id_is_closed():
    assert [w for w in _run_loop("R1 R2 R3") if w.startswith("R")] == ["R1", "R2", "R3"]


def test_a_single_id_still_closes_once():
    assert [w for w in _run_loop("R7") if w.startswith("R")] == ["R7"]


def test_the_readers_run_once_whatever_the_number_of_ids():
    lines = _dry("R1 R2 R3")
    assert sum(ln.count("run_readers.py") for ln in lines) == 1
