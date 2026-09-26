"""The nightly recap reads GitHub's verdicts without lying about them.

Type: Sub
Uses: src/utils/nightly_recap.py
Depends on: nothing — runs are fabricated, the network is replaced by a fake opener
Persists in: nothing

R181 (2026-09-26): one mail a night carries the production findings and the three GitHub
workflows. A cancelled run is not red, an unreadable GitHub is not green, and a red
workflow is said to have ALREADY been mailed at its break — never announced as new.
"""
from __future__ import annotations

import io
import json

from src.utils import nightly_recap as nr


def _run(conclusion: str, day: str) -> dict:
    return {"conclusion": conclusion, "created_at": f"2026-09-{day}T02:00:00Z",
            "html_url": f"https://github.com/x/runs/{day}"}


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: a red streak is dated from its FIRST red run (the break mail), and a
    cancelled run on top neither clears nor extends it; green is green; no data is not
    green; unreadable is said as unreadable."""
    runs = [_run("cancelled", "26"), _run("failure", "25"), _run("failure", "24"),
            _run("success", "23")]
    v = nr.verdict(runs)
    assert (v["state"], v["since"]) == ("red", "2026-09-24")
    assert nr.verdict([_run("success", "26"), _run("failure", "25")])["state"] == "green"
    assert nr.verdict([_run("cancelled", "26")])["state"] == "unknown"
    assert nr.verdict(None)["state"] == "unreadable"


def test_the_section_never_renders_unreadable_as_green() -> None:
    html, red = nr.github_section({"CI": {"state": "unreadable", "since": None, "url": None},
                                   "Santé": {"state": "green", "since": None,
                                             "url": "https://g/1"}})
    assert not red
    assert "INCONNU" in html and "pas vert" in html
    html, red = nr.github_section({"CI": {"state": "red", "since": "2026-09-24",
                                          "url": None}})
    assert red and "mail de cassure devait partir" in html


def test_an_unreachable_github_reads_as_unreadable_not_green() -> None:
    def broken(*_a, **_k):
        raise OSError("network down")

    assert all(v["state"] == "unreadable" for v in nr.github_verdicts(opener=broken).values())


def test_the_fetch_parses_the_public_api_shape() -> None:
    payload = {"workflow_runs": [_run("success", "26")]}

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout):
        assert "status=completed" in req.full_url and "branch=main" in req.full_url
        return _Resp(json.dumps(payload).encode())

    assert nr.fetch_runs("ci.yml", "main", opener=fake) == payload["workflow_runs"]


def test_a_quiet_recap_says_that_silence_would_mean_a_dead_monitor() -> None:
    subject, body = nr.short_recap("2026-09-26 23:00", "nuit calme, rien de neuf",
                                   "<h3>GitHub</h3>")
    assert subject.startswith("📋 Récap de la nuit")
    assert "moniteur lui-même ne tourne plus" in body and "<h3>GitHub</h3>" in body
