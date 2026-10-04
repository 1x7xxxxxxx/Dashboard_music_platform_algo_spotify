"""The local worker count reserves memory only for what can still GROW during a suite.

Type: Sub
Uses: tools/dev/pytest_workers.py
Depends on: nothing — fabricated memory and process lists

On 2026-09-17 a fixed 5 120 Mo reserve was set after three OOM kills, and it pinned
`make test` at 2 workers. On 2026-09-25 n8n moved to Sundays and knowledge-rag started
dropping its model when idle, so the reserve now follows what is actually running.
The dangerous direction is the one these tests pin: an ingestion or Ollama that IS
running must still bring the count back down.

R352 (2026-10-04): the knowledge-rag reserve assumed 1 600 Mo for a server measured at
2 228 Mo after one search (VmHWM); VS Code Remote dropped three times. The 4 GB processes
of that day were the error-class-health replay, not the server (see pytest_workers.py).
"""
import importlib.util
from pathlib import Path

_TOOL = Path(__file__).resolve().parents[1] / "tools/dev/pytest_workers.py"
_spec = importlib.util.spec_from_file_location("pytest_workers", _TOOL)
pw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pw)

_RAG_SERVER = pw.Proc(["/home/u/knowledge-rag/.venv/bin/python3", "server.py"], 225,
                      "/home/u/knowledge-rag")
_RAG_WRAPPER = pw.Proc(["uv", "run", "--directory", "/home/u/knowledge-rag", "python",
                        "server.py"], 38, "/home/u")
_SHELL_MENTION = pw.Proc(["/bin/bash", "-c", "grep knowledge-rag server.py"], 3, "/home/u")
_INGEST = pw.Proc(["/home/u/knowledge-rag/.venv/bin/python", "ingest_drop.py"], 900,
                  "/home/u/knowledge-rag")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """An ingestion running on today's memory must fall back to the floor of 2."""
    n, why = pw.workers(6600, [_RAG_SERVER, _INGEST], ollama_up=False, ncpu=8)
    assert n == 2, why


def test_ollama_up_brings_the_count_down() -> None:
    assert pw.workers(6600, [], ollama_up=True, ncpu=8)[0] == 2


def test_a_quiet_workstation_gets_more_than_the_old_floor() -> None:
    n, why = pw.workers(6600, [], ollama_up=False, ncpu=8)
    assert n == 7, why


def test_an_idle_rag_server_reserves_its_measured_peak_not_1600() -> None:
    """One idle server, 6 000 Mo free: 6 without it, 4 with the old 1 600, 3 at its peak."""
    assert pw.workers(6000, [], ollama_up=False, ncpu=8)[0] == 6
    n, why = pw.workers(6000, [_RAG_SERVER], ollama_up=False, ncpu=8)
    assert n == 3, why
    n, why = pw.workers(9000, [_RAG_SERVER], ollama_up=False, ncpu=8)
    assert n == 7, why


def test_a_loaded_model_can_still_grow_to_its_peak() -> None:
    """A loaded server at 1 500 Mo can still reach 2 228: the rest is reserved, not zero."""
    loaded = pw.Proc(_RAG_SERVER.argv, 1500, _RAG_SERVER.cwd)
    n, why = pw.workers(6600, [loaded], ollama_up=False, ncpu=8)
    assert n == 6, why


def test_a_full_swap_widens_the_reserve() -> None:
    roomy = pw.workers(6600, [], ollama_up=False, ncpu=8, swap_free_mb=3000)[0]
    full = pw.workers(6600, [], ollama_up=False, ncpu=8, swap_free_mb=0)[0]
    assert full < roomy


def test_only_the_python_server_counts_not_its_wrapper_nor_a_mention() -> None:
    """A text match counted the `uv run` wrapper and a shell as two more servers."""
    one = pw.workers(6600, [_RAG_SERVER], ollama_up=False, ncpu=8)[0]
    same = pw.workers(6600, [_RAG_SERVER, _RAG_WRAPPER, _SHELL_MENTION],
                      ollama_up=False, ncpu=8)[0]
    assert one == same


def test_the_bounds_hold() -> None:
    assert pw.workers(20_000, [], ollama_up=False, ncpu=8)[0] == 8
    assert pw.workers(500, [], ollama_up=False, ncpu=8)[0] == 2
