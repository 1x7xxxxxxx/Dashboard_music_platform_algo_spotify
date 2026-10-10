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
    return {"conclusion": conclusion, "status": "completed", "created_at": f"2026-09-{day}T02:00:00Z",
            "html_url": f"https://github.com/x/runs/{day}", "head_sha": f"sha{day}"}


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _github(runs_body: dict, head: str):
    """A fake opener: the runs page, and the branch's head commit."""
    def fake(req, timeout):
        if "/commits/" in req.full_url:
            return _Resp(json.dumps({"sha": head}).encode())
        # R316: the completed filter runs on the runs, not in a lagging server-side index
        assert "status=completed" not in req.full_url and "branch=main" in req.full_url
        return _Resp(json.dumps(runs_body).encode())
    return fake


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
    done, running = _run("success", "26"), dict(_run("failure", "27"), status="in_progress")
    fake = _github({"workflow_runs": [running, done]}, head="sha27")
    assert nr.fetch_runs("ci.yml", "main", opener=fake) == [done], (
        "a run still in progress is not a verdict")
    fake = _github({"message": "API rate limit exceeded"}, head="sha27")
    assert nr.fetch_runs("ci.yml", "main", opener=fake) is None, (
        "an error body is « unreadable », not an empty list read as « unknown »")
    assert "illisible" in nr.describe(None) and "success" in nr.describe([done])


def test_a_list_without_the_head_commit_is_stale_not_red() -> None:
    """R407 — mail ops 2026-10-05 15:18: « CI (main) ROUGE depuis le 2026-09-20 », read
    on a lagging page whose newest run predated main's head. Mutation 2026-10-05: the
    `is_fresh` check removed from `fetch_runs` → RED."""
    stale = {"workflow_runs": [_run("failure", "21"), _run("failure", "20")]}
    runs = nr.fetch_runs("ci.yml", "main", opener=_github(stale, head="sha30"))
    assert runs is None, "a page without main's head run was judged — stale read as a verdict"
    assert nr.verdict(runs)["state"] == "unreadable"
    assert nr.fetch_runs("ci.yml", "main", opener=_github(stale, head=None)) is None, (
        "an unknown head cannot vouch for the list")
    assert nr.fetch_runs("ci.yml", "main", opener=_github(stale, head="sha21")) is not None


def test_a_quiet_recap_says_that_silence_would_mean_a_dead_monitor() -> None:
    subject, body = nr.short_recap("2026-09-26 23:00", "nuit calme, rien de neuf",
                                   "<h3>GitHub</h3>")
    assert subject.startswith("📋 Récap de la nuit")
    assert "moniteur lui-même ne tourne plus" in body and "<h3>GitHub</h3>" in body


# R493 — 2026-10-09 and 10: the nightly's `notify` mailed red (guard-mutation) while this recap
# said « Sécurité — nuit : vert ». Every job and step carries `continue-on-error`, so GitHub
# shows the whole run green; the failed jobs travel in a `notify` annotation.
_NOTIFY_JOBS = {"jobs": [{"name": "gitleaks", "status": "completed",
                          "check_run_url": "https://api/check-runs/1"},
                         {"name": "notify", "status": "completed",
                          "check_run_url": "https://api/check-runs/2"}]}


def test_a_green_run_with_a_failed_job_is_not_rendered_green() -> None:
    v = {"state": "green", "since": None, "url": None, "jobs": ["guard-mutation"]}
    html, red = nr.github_section({"Sécurité — nuit": v})
    assert "🟠" in html and "guard-mutation" in html and "✅" not in html
    assert not red, "amber, not a headline red: the nightly already mailed it"
    html, _ = nr.github_section({"Sécurité — nuit": {**v, "jobs": None}})
    assert "ILLISIBLE" in html and "✅" not in html, "unreadable jobs are not green"
    html, _ = nr.github_section({"Sécurité — nuit": {**v, "jobs": []}})
    assert "✅" in html


def test_the_failed_jobs_are_read_from_the_notify_annotation() -> None:
    assert nr.notify_annotations_url(_NOTIFY_JOBS) == "https://api/check-runs/2/annotations"
    assert nr.notify_annotations_url({"jobs": [{"name": "notify", "status": "in_progress"}]}) is None
    ann = [{"title": "other", "message": "x"},
           {"title": nr.FAILED_JOBS_TITLE, "message": "gitleaks,guard-mutation"}]
    assert nr.failed_jobs(ann) == ["gitleaks", "guard-mutation"]
    assert nr.failed_jobs([]) == []
    assert nr.failed_jobs({"message": "API rate limit exceeded"}) is None


def test_what_notify_writes_is_what_the_recap_reads() -> None:
    """The title is a contract between two files; one round-trip proves both ends."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "nv", Path(__file__).resolve().parents[1] / "tools/dev/nightly_verdict.py")
    nv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nv)
    cmd = nv.annotation(["gitleaks", "guard-mutation"])
    title, message = cmd.removeprefix("::warning title=").split("::", 1)
    assert nr.failed_jobs([{"title": title, "message": message}]) == ["gitleaks", "guard-mutation"]
    assert nv.annotation([]) is None


def test_an_unreadable_jobs_endpoint_is_unreadable() -> None:
    def fake(req, timeout):
        if req.full_url.endswith("/jobs"):
            return _Resp(json.dumps(_NOTIFY_JOBS).encode())
        raise OSError("rate limited")
    assert nr.fetch_failed_jobs(42, opener=fake) is None
    assert nr.fetch_failed_jobs(None, opener=fake) is None
