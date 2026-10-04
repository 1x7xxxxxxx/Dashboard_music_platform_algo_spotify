"""The catalogue replay streams its revisions — it never holds them all (R352).

Type: Sub
Uses: tools/dev/error_class_health.py (_catalogue_at), git
Depends on: the git history of .claude/dev-docs/error-classes.md

Measured 2026-10-04: `_catalogue_at` read 583 revisions of a 2.4 MB catalogue into one
dict — VmHWM 4 047 Mo for a replay that only compares each revision with the previous
one. Run inside an xdist worker by `generated_cache.health_payload()`, it starved the
10 GB WSL VM until VS Code Remote lost its Hyper-V socket. Streamed: 71 Mo, same output.
"""
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dev"))
import error_class_health as health  # noqa: E402


def _shas() -> list[str]:
    out = subprocess.run(["git", "log", "--format=%H", "-n", "3", "--", health.CAT_REL],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return out.split()


def test_the_revisions_are_yielded_not_collected() -> None:
    revisions = health._catalogue_at(_shas())
    assert isinstance(revisions, types.GeneratorType), (
        f"_catalogue_at returned a {type(revisions).__name__}: every revision of the "
        "catalogue is then in memory at once (4 GB measured). Yield them one by one.")
    revisions.close()


def test_the_stream_yields_each_revision_in_order() -> None:
    shas = _shas()
    got = list(health._catalogue_at(shas))
    assert [sha for sha, _ in got] == shas
    for sha, text in got:
        committed = subprocess.run(["git", "show", f"{sha}:{health.CAT_REL}"], cwd=ROOT,
                                   capture_output=True, text=True, check=True).stdout
        assert text == committed.replace("\r\n", "\n")
