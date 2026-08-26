"""Two checks asked the same question, and the mail answered it twice.

Measured 2026-08-26 on the nightly PRODUCTION alert:

    ⚪ Inscrits sans rien connecter depuis 7 jours   11 rows
    🔑 Credentials manquants                         12 rows   ← 11 of them the same

`readiness_stalled_flags` returns the platforms at TODO. `check_credentials_all`
returns the platforms absent from `declared_identities()`. TODO *is* "no declared
identity" — so `stalled` is `missing_creds` restricted to accounts older than a
week: a strict subset by construction, not by coincidence. Eleven facts were printed
twice under two different wordings of one gesture, and counted a second time in the
subject line ("12 credential(s) manquant(s)").

Only one row was not already stated above it — the admin's Spotify identity — and
that is the row worth reading. Eleven duplicates are what stop it being read.

This file guards the RELATION, not tonight's numbers: as long as both checks read
the same predicate, the mail must subtract. A future check that stops being a subset
should fail here loudly rather than silently start hiding rows.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
DAG = (REPO / "airflow/dags/alert_monitor.py").read_text(encoding="utf-8")


def test_both_checks_really_do_read_the_same_predicate():
    """The premise of the subtraction, asserted rather than assumed.

    If these two ever stop meaning the same thing, subtracting one from the other
    starts HIDING rows — a far worse defect than the duplication it fixed.
    """
    from src.utils.artist_readiness import TODO, readiness_stalled_flags

    src = inspect.getsource(readiness_stalled_flags)
    assert 'm["status"] == TODO' in src, (
        "readiness_stalled_flags no longer selects on TODO — the subtraction in "
        "alert_monitor assumes it does, and would now drop rows it should show")
    assert TODO == "todo"

    from src.utils.artist_readiness import platform_status
    status_src = inspect.getsource(platform_status)
    assert "TODO" in status_src and "identity" in status_src.lower(), (
        "TODO is no longer 'no declared identity' — re-check the subtraction")


def test_the_credentials_section_subtracts_what_was_already_said():
    assert "already_stated = {" in DAG, (
        "the mail states the same missing identity in two sections again")
    assert "if (m['artist_id'], m['platform']) not in already_stated" in DAG


def test_the_subtraction_keys_on_the_logical_platform_not_the_label():
    """`stalled` carries `m['label']` ('☁️ SoundCloud'); `missing_creds` carries
    'soundcloud'. Keying on the label would match nothing and silently subtract
    zero — a guard passing while the defect is fully intact."""
    assert "'key': m['key']," in DAG, (
        "stalled rows no longer carry the logical key — the subtraction would "
        "compare '☁️ SoundCloud' with 'soundcloud' and never match")
    tree = ast.parse(DAG)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Set):
            continue
        text = ast.unparse(node)
        if "already_stated" in text or "artist_id" in text and "key" in text:
            assert "'label'" not in text, f"subtraction keyed on a label: {text}"


def test_the_removal_is_announced():
    """A section that shrinks without saying so reads as coverage that got smaller."""
    assert "_dropped = _n_before - len(missing_creds)" in DAG
    assert "déjà dite(s)" in DAG, (
        "rows are removed from the mail with nothing telling the reader they were")


def test_the_subject_counts_what_the_section_shows():
    """The count was inflated by the duplicates: subtract BEFORE the subject is built."""
    body = DAG.index("already_stated = {")
    subject = DAG.index("credential(s) manquant(s)")
    assert body < subject, (
        "the subject line is built from the unsubtracted list — it would announce "
        "12 where the section shows 1")
