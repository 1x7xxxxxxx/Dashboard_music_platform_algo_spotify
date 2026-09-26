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


def subtraction_problems(source: str) -> list[str]:
    """What is wrong with the subtraction of already-stated identities, read on the
    DAG's AST. Pure.

    `no-subtraction`: no `already_stated` set is built.
    `keyed-on-label`: the set is keyed on a display label ('☁️ SoundCloud'), which
    never equals the logical platform ('soundcloud') — it subtracts nothing.
    `rows-without-key`: no row carries a `'key'` field for the set to read.
    `not-filtered`: nothing filters a list with `… not in already_stated`.
    `silent-removal`: rows are removed and nothing counts them for the reader.
    `subject-after-body`: the subject is counted before the subtraction.
    """
    tree = ast.parse(source)
    built = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
             and any(getattr(t, "id", "") == "already_stated" for t in n.targets)]
    if not built:
        return ["no-subtraction"]
    out = []
    keys = ast.unparse(built[0].value)
    if "'label'" in keys or '"label"' in keys:
        out.append("keyed-on-label")
    # Keying on `.get('key')` subtracts nothing if the stalled rows stop CARRYING it.
    if not any(isinstance(d, ast.Dict) and any(
            isinstance(k, ast.Constant) and k.value == "key" for k in d.keys)
            for d in ast.walk(tree)):
        out.append("rows-without-key")
    filtered = [c for c in ast.walk(tree) if isinstance(c, ast.Compare)
                and any(isinstance(op, ast.NotIn) for op in c.ops)
                and any(getattr(x, "id", "") == "already_stated" for x in c.comparators)]
    if not filtered:
        out.append("not-filtered")
    counted = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
               and any(getattr(t, "id", "") == "_dropped" for t in n.targets)]
    if not counted:
        out.append("silent-removal")
    subject = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Constant)
               and isinstance(n.value, str) and "credential(s) manquant(s)" in n.value]
    if subject and min(subject) < built[0].lineno:
        out.append("subject-after-body")
    return out


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity, class `two-checks-one-question-reported-twice`: the mail of before
    the fix (no subtraction), a subtraction keyed on the label, a subject counted
    before the subtraction, and a silent removal are each named; the fixed shape is
    not."""
    fixed = (
        "stalled = [{'artist_id': 1, 'key': 'soundcloud', 'label': 'SC'}]\n"
        "already_stated = {(s['artist_id'], s.get('key')) for s in stalled}\n"
        "_n_before = len(missing)\n"
        "missing = [m for m in missing\n"
        "           if (m['artist_id'], m['platform']) not in already_stated]\n"
        "_dropped = _n_before - len(missing)\n"
        "subject.append(f'{len(missing)} credential(s) manquant(s)')\n")
    assert subtraction_problems(fixed) == []
    assert subtraction_problems("subject.append('1 credential(s) manquant(s)')\n") == [
        "no-subtraction"]
    on_label = fixed.replace("s.get('key')", "s['label']")
    assert subtraction_problems(on_label) == ["keyed-on-label"]
    silent = fixed.replace("_dropped = _n_before - len(missing)\n", "")
    assert subtraction_problems(silent) == ["silent-removal"]
    early = ("subject.append(f'{len(missing)} credential(s) manquant(s)')\n"
             + fixed.replace("subject.append(f'{len(missing)} credential(s) manquant(s)')\n",
                             ""))
    assert subtraction_problems(early) == ["subject-after-body"]
    keyless = fixed.replace("'key': 'soundcloud', ", "")
    assert subtraction_problems(keyless) == ["rows-without-key"]
    unfiltered = fixed.replace("not in already_stated", "in {(0, 0)}")
    assert subtraction_problems(unfiltered) == ["not-filtered"]


def test_the_credentials_section_subtracts_what_was_already_said():
    found = set(subtraction_problems(DAG)) & {"no-subtraction", "not-filtered"}
    assert not found, (
        f"{found} : the mail states the same missing identity in two sections again")


def test_the_subtraction_keys_on_the_logical_platform_not_the_label():
    """`stalled` carries `m['label']` ('☁️ SoundCloud'); `missing_creds` carries
    'soundcloud'. Keying on the label would match nothing and silently subtract
    zero — a guard passing while the defect is fully intact."""
    assert not set(subtraction_problems(DAG)) & {"keyed-on-label", "rows-without-key"}, (
        "the subtraction compares '☁️ SoundCloud' with 'soundcloud' and never matches")


def test_the_removal_is_announced():
    """A section that shrinks without saying so reads as coverage that got smaller."""
    assert not set(subtraction_problems(DAG)) & {"silent-removal"}, (
        "rows are removed from the mail with nothing telling the reader they were")


def test_the_subject_counts_what_the_section_shows():
    """The count was inflated by the duplicates: subtract BEFORE the subject is built."""
    assert not set(subtraction_problems(DAG)) & {"subject-after-body"}, (
        "the subject line is built from the unsubtracted list — it would announce "
        "12 where the section shows 1")
