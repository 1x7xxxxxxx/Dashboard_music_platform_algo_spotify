"""R445 — `make roadmap-close ID="Ra Rb"` closes each ID and runs the readers once.

Type: Sub
Uses: Makefile (dry-run expansion through `make -n`)
"""
from __future__ import annotations

import subprocess
import sys
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


def test_a_parent_makes_variables_do_not_reach_a_tests_own_make(tmp_path: Path) -> None:
    """R708: through a REAL make — simulating its env is what the defect would slip past."""
    makefile = tmp_path / "parent.mk"
    nodes = ("tests/test_roadmap_close_takes_several_ids.py::test_every_id_is_closed "
             "tests/test_the_makefile_is_its_own_index.py"
             "::test_test_with_args_keeps_the_workers_and_skips_the_stamp")
    makefile.write_text(f"run:\n\t@{sys.executable} -m pytest {nodes} -q -p no:cacheprovider\n",
                        encoding="utf-8")
    out = subprocess.run(["make", "-C", str(ROOT), "-f", str(makefile), "run",
                          "NOTE=Rendu tel quel, avec = dedans", "ARGS=tests/test_x.py"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout[-1500:]


def test_the_readers_run_once_whatever_the_number_of_ids():
    lines = _dry("R1 R2 R3")
    assert sum(ln.count("run_readers.py") for ln in lines) == 1
