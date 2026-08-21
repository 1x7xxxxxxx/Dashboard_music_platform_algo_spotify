"""Guard — the gate that says go/no-go has tests of its own.

Error class `gate-with-no-test-of-its-own`.

`tools/artist_preflight.py` is the one thing standing between a broken tenant and a
real artist sitting in front of the product: the runbook opens with "on n'invite
personne tant que `make artist-preflight` n'est pas vert". Until 2026-08-22 it had
**no test at all** — `grep artist_preflight` found only `Makefile:71`, two allowlists
and prose — and no schedule. Its scope logic, its QUIET-counts-as-good rule and its
out-of-scope printing were unverified. A regression that made it green by default
would have been found by nobody, and its greenness is exactly what the runbook trusts.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


@pytest.fixture(scope="module")
def pf():
    spec = importlib.util.spec_from_file_location(
        "artist_preflight", REPO / "tools" / "artist_preflight.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── the scope flag can only ever narrow, never blank ──────────────────────────

def test_a_typo_in_platforms_exits_2_instead_of_going_green(pf, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["artist_preflight.py", "--platforms", "spotifyy"])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = pf.main()
    assert rc == 2, "an unknown platform silently emptied the scope"


def test_an_empty_platforms_value_exits_2(pf, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["artist_preflight.py", "--platforms", " , "])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = pf.main()
    assert rc == 2


def test_instagram_is_an_accepted_scope(pf, monkeypatch) -> None:
    """It became probeable in the same session; the scope must accept it."""
    from src.utils.artist_readiness import _PLATFORMS

    assert "instagram" in {p["key"] for p in _PLATFORMS}


# ── step 4: QUIET is good, out-of-scope never gates, everything is printed ─────

class _FakeDb:
    def fetch_query(self, *a, **k):
        return []


def _rows(monkeypatch, pf, rows):
    monkeypatch.setattr("src.utils.artist_readiness.artist_readiness",
                        lambda db, aid: rows)


def _row(key, status, label, icon="🟢", action=""):
    return {"key": key, "label": label, "icon": icon, "status": status,
            "status_label": label, "expected_silence": None, "last_dt": None,
            "next_action": action}


def test_quiet_counts_as_good(pf, monkeypatch) -> None:
    """A measured 'nothing to send' must not red the gate for a correct tenant."""
    _rows(monkeypatch, pf, [_row("meta", "quiet", "📱 Meta Ads", "⏸️")])
    with redirect_stdout(io.StringIO()):
        assert pf.step_data_landed(_FakeDb(), 1) is True


def test_a_broken_probe_reds_the_gate(pf, monkeypatch) -> None:
    """`BROKEN` is not `OK` and not `QUIET`: the gate must stop."""
    _rows(monkeypatch, pf, [_row("youtube", "broken", "🎬 YouTube", "⚠️")])
    with redirect_stdout(io.StringIO()):
        assert pf.step_data_landed(_FakeDb(), 1) is False


def test_an_out_of_scope_red_does_not_gate(pf, monkeypatch) -> None:
    _rows(monkeypatch, pf, [_row("soundcloud", "no_data", "☁️ SoundCloud", "🔴")])
    with redirect_stdout(io.StringIO()):
        assert pf.step_data_landed(_FakeDb(), 1, {"youtube"}) is True


def test_an_out_of_scope_platform_is_still_printed(pf, monkeypatch) -> None:
    """A scoped green must not read as full coverage."""
    _rows(monkeypatch, pf, [_row("soundcloud", "no_data", "☁️ SoundCloud", "🔴")])
    buf = io.StringIO()
    with redirect_stdout(buf):
        pf.step_data_landed(_FakeDb(), 1, {"youtube"})
    out = buf.getvalue()
    assert "SoundCloud" in out and "out of scope" in out


# ── step 1: absence is narrowed to the scope, never skipped ───────────────────

def test_a_scoped_run_still_requires_its_own_platform(pf, monkeypatch) -> None:
    """The standing production run is `--platforms youtube`; if absence is skipped
    there, the one check aimed at the beta failure never runs in production."""
    for var in ("YOUTUBE_API_KEY",):
        monkeypatch.delenv(var, raising=False)
    buf = io.StringIO()
    with redirect_stdout(buf):
        ok = pf.step_central_apps({"youtube"})
    assert ok is False, "a scoped run passed with its own platform unconfigured"
    assert "NOT configured" in buf.getvalue()


# ── step 3: a raising probe is a red verdict, not a crash ─────────────────────

def test_a_raising_probe_becomes_a_red_not_a_traceback(pf, monkeypatch) -> None:
    def _boom(_fields):
        raise RuntimeError("network down")

    monkeypatch.setattr(
        "src.dashboard.views.credentials._registry.CONNECTION_TESTS",
        {"youtube": _boom})
    monkeypatch.setattr(pf, "_credentials", lambda db, aid: {"youtube": {}})
    buf = io.StringIO()
    with redirect_stdout(buf):
        ok = pf.step_connection_tests(_FakeDb(), 1)
    assert ok is False
    assert "network down" in buf.getvalue()
