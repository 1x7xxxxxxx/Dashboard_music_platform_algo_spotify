"""pytest plugin: record, per test module, the tracked files it opens and the dirs it lists.

Type: Utility
Uses: builtins.open, os.scandir, os.listdir (wrapped), pytest item hooks
Triggers: tools/dev/select_audit.py (`-p select_trace_plugin`, SELECT_TRACE_OUT set)
Persists in: $SELECT_TRACE_OUT/<pid>.json — one file per xdist worker

R338 (2026-09-29): the offline ORACLE for `select_tests.py` (code-critic: never a runtime
input — a trace goes stale silently; an audit that reruns it cannot). Reads made through a
subprocess are invisible to it, and are left to the selector's mention rule.
"""
import atexit
import builtins
import io
import json
import os

_ROOT = os.path.abspath(os.environ.get("SELECT_TRACE_ROOT", "."))
_OUT = os.environ.get("SELECT_TRACE_OUT")
_cur = [None]
_reads: dict[str, set[str]] = {}


def _rec(p) -> None:
    if _cur[0] is None or _OUT is None:
        return
    try:
        a = os.path.abspath(os.fspath(p))
    except TypeError:
        return
    if a.startswith(_ROOT + os.sep):
        r = os.path.relpath(a, _ROOT)
        if not r.startswith((".git", ".venv")) and "__pycache__" not in r:
            _reads.setdefault(_cur[0], set()).add(r)


_open, _scandir, _listdir = builtins.open, os.scandir, os.listdir


def _op(f, *a, **k):
    if isinstance(f, (str, bytes, os.PathLike)):
        _rec(f)
    return _open(f, *a, **k)


def _sd(p="."):
    _rec(p)
    return _scandir(p)


def _ld(p="."):
    _rec(p)
    return _listdir(p)


if _OUT:
    builtins.open = io.open = _op
    os.scandir, os.listdir = _sd, _ld

    @atexit.register
    def _flush() -> None:
        with _open(os.path.join(_OUT, f"{os.getpid()}.json"), "w") as fh:
            json.dump({k: sorted(v) for k, v in _reads.items()}, fh)


def _set(item) -> None:
    _cur[0] = os.path.relpath(str(item.path), _ROOT)


def pytest_runtest_setup(item):
    _set(item)


def pytest_runtest_call(item):
    _set(item)


def pytest_runtest_teardown(item):
    _set(item)
