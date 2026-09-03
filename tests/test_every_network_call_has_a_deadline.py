"""Guard: a network call from a collector cannot hang forever.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Error class `retry-blind-to-the-exception-its-client-raises`, found while porting
msdr's `dns-resolution-outlives-socket-timeout` on 2026-09-03.

The defect is NOT that the call was unbounded — that was the first diagnosis and it
was wrong. Measured by constructing the real client, googleapiclient's default
`Http()` carries `timeout=60`. What was broken is one layer up:

`httplib2` raises **`socket.timeout`** on that 60 s expiry. `src/utils/retry.py`
listed `psycopg2.OperationalError`, `requests.exceptions.Timeout` and
`ConnectionError` — none of which it is. So the five `@retry(max_attempts=3)`
decorators on this collector had **never rejoué a single attempt**: a transient blip
failed the task outright, while every `requests`-based sibling retried three times.
Invisible, because a red YouTube run reads as an API outage rather than as a retry
that did not happen.

The convention already existed one directory over: `soundcloud_api_collector.py`
passes `timeout=` at four call sites, `instagram_api_collector.py` at one. YouTube was
the hole in it, which is why this guard checks the whole directory rather than the one
file that was broken.

msdr's phrasing of the general rule still holds and is broader than this fix: *a
per-socket timeout is NOT an operation timeout — DNS, the TLS handshake and retries
all sit outside it.* Here the missing piece was the retry, not the socket.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
COLLECTORS = REPO / "src" / "collectors"

# `requests` verbs that reach the network. `Session()` is absent on purpose: nothing
# in this directory uses one, and listing a shape nobody writes invites a false sense
# of coverage.
_NET_CALLS = {"get", "post", "put", "patch", "delete", "head"}


def _calls_without_timeout(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in _NET_CALLS:
            continue
        base = node.func.value
        if not (isinstance(base, ast.Name) and base.id == "requests"):
            continue
        if not any(k.arg == "timeout" for k in node.keywords):
            out.append(f"{path.relative_to(REPO).as_posix()}:{node.lineno} "
                       f"requests.{node.func.attr}(…)")
    return out


def test_every_requests_call_in_a_collector_carries_a_timeout():
    offenders: list[str] = []
    for path in sorted(COLLECTORS.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        offenders += _calls_without_timeout(path)
    assert not offenders, (
        f"{len(offenders)} network call(s) with no deadline:\n  "
        + "\n  ".join(offenders)
        + "\n\nA collector runs unattended at night. Without a timeout the task holds "
        "until the DAG-level timeout kills the whole run — every tenant loses the day, "
        "and the failure names the DAG instead of the platform."
    )


def test_the_youtube_client_is_built_with_a_bounded_http():
    """The one site the sweep above cannot see, because it takes no `timeout=`.

    `build()` accepts an `http=`; without it googleapiclient supplies its own
    `httplib2.Http()` — bounded, but at ITS default of 60 s, not this repo's 30 s.
    A keyword-argument sweep sees nothing missing when the argument is not a keyword
    at all, hence a second, differently-shaped assertion.
    """
    tree = ast.parse((COLLECTORS / "youtube_collector.py").read_text(encoding="utf-8"))
    builds = [n for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
              and n.func.id == "build"]
    assert builds, "no build() call in youtube_collector — this guard points at air"
    for call in builds:
        assert any(k.arg == "http" for k in call.keywords), (
            f"build() at line {call.lineno} has no `http=`: the client then inherits "
            "googleapiclient's own default (60 s) instead of this repo's 30 s ceiling, "
            "so one platform hanging outlives the others."
        )


def test_the_built_client_really_carries_the_timeout():
    """Reading the source proves intent; constructing it proves behaviour.

    The AST check above passes on `http=httplib2.Http()` with no timeout at all. This
    one builds the real object and reads the value back.
    """
    pytest.importorskip("googleapiclient")
    from src.collectors.youtube_collector import YouTubeCollector

    collector = YouTubeCollector("fake-key-for-construction-only")
    assert collector.youtube._http.timeout, (
        "the client was constructed without an effective timeout — the `http=` "
        "argument is present but carries none."
    )


def test_a_socket_timeout_is_retried_and_a_missing_file_is_not():
    """The actual fix, asserted in BOTH directions.

    Only the positive half would pass on `OSError`, which also swallows
    `FileNotFoundError` and `PermissionError` — neither of which becomes true by
    waiting. Retrying them turns a clear failure into three slow ones.
    """
    import socket

    from src.utils.retry import RETRIABLE_EXCEPTIONS

    retriable = tuple(RETRIABLE_EXCEPTIONS)
    assert issubclass(socket.timeout, retriable), (
        "a socket timeout is not retriable, so @retry on the googleapiclient path "
        "cannot fire — which is the defect, not the timeout value."
    )
    for never in (FileNotFoundError, PermissionError):
        assert not issubclass(never, retriable), (
            f"{never.__name__} is retriable. The list has been widened to OSError; "
            "waiting does not make a missing file appear."
        )
