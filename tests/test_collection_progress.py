"""Reading a collection run's outcome. Pure logic, no Streamlit, no Airflow.

The sidebar said "Lancé !" and never mentioned the collection again. Both beta
testers pressed it, waited, saw an empty dashboard and concluded the app was
broken. These tests pin the two decisions that turn a run into something an
artist can act on: what state a run is in, and what a failure means for them.
"""
import pytest

from src.dashboard.utils.collection_progress import failure_hint, summarise


# ── A run's state, from its tasks ───────────────────────────────────────────

def test_all_tasks_successful_is_a_success():
    assert summarise(["success", "success"]) == "success"


def test_one_failed_task_fails_the_run():
    """The artist cares about the outcome, not which of four tasks reached it."""
    assert summarise(["success", "failed"]) == "failed"
    assert summarise(["running", "failed"]) == "failed"


def test_upstream_failure_counts_as_a_failure():
    assert summarise(["success", "upstream_failed"]) == "failed"


def test_a_running_task_keeps_the_run_running():
    assert summarise(["success", "running"]) == "running"
    assert summarise(["queued", "scheduled"]) == "running"


def test_no_task_yet_is_unknown_not_success():
    """Airflow has not scheduled anything yet — claiming success would be a lie."""
    assert summarise([]) == "unknown"
    assert summarise([None, None]) == "unknown"


# ── What a failure means for the artist ─────────────────────────────────────

@pytest.mark.parametrize("log,expected_fragment", [
    ("googleapiclient.errors.HttpError ... playlistNotFound", "Topic"),
    ("(#100) Object does not exist, cannot be loaded", "asset sharing"),
    ("Meta API error code-190 invalid token", "administrateur"),
    ("PermissionError: [Errno 13] Permission denied: '/opt/airflow/data/raw'",
     "administrateur"),
    ("there is no unique or exclusion constraint matching the ON CONFLICT",
     "schéma"),
    ("quotaExceeded: The request cannot be completed", "quota"),
    ("SoundCloud API 401 — access token rejected", "identifiants"),
])
def test_known_failures_are_translated_into_a_next_action(log, expected_fragment):
    hint = failure_hint(log)
    assert hint is not None, f"unrecognised: {log[:40]}"
    assert expected_fragment in hint


def test_an_unknown_failure_returns_none_rather_than_a_guess():
    """Inventing an explanation is how 'all the credentials failed' became the
    only sentence anyone could say about a broken session."""
    assert failure_hint("ValueError: something nobody has seen before") is None
    assert failure_hint("") is None
    assert failure_hint(None) is None


def test_hints_cover_the_failures_actually_seen_in_production():
    """Each entry exists because it happened; losing one loses a diagnosis."""
    seen = [
        "playlistNotFound", "Object does not exist", "code-190",
        "Permission denied", "no unique or exclusion constraint",
    ]
    for needle in seen:
        assert failure_hint(f"traceback ... {needle} ...") is not None, needle
