"""The action-drift report prints the two marks its catalogue signatures grep for.

Type: Sub
Uses: tools/dev/check_action_drift.py (row_marks)
Depends on: nothing — no GitHub call

Classes `a-prudence-rule-with-no-expiry-becomes-a-freeze` (a pin two majors behind → 🔴)
and `an-action-pin-derived-from-a-version-number` (a tag that does not exist upstream →
INTROUVABLE). Their signatures grep the report; nothing proved the report could print them.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_action_drift", Path(__file__).resolve().parents[1] / "tools/dev/check_action_drift.py")
cad = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cad)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """setup-uv held six majors behind (the freeze) → 🔴 ; `@v10`, a tag deduced from a
    version number and absent upstream → INTROUVABLE ; an unanswered API → ❓, not a verdict."""
    assert cad.row_marks(6, True)[0] == "🔴"
    assert cad.row_marks(1, True)[0] == "🟠"
    assert cad.row_marks(0, True) == ("✅", "✅")
    assert "INTROUVABLE" in cad.row_marks(0, False)[1]
    assert "INTROUVABLE" not in cad.row_marks(0, None)[1], "could not ask is not absent"


SHA = "d23441a48e516b6c34aea4fa41551a30e30af803"  # pragma: allowlist secret — public commit of actions/checkout v6.1.0


def test_a_sha_pin_takes_its_version_from_the_comment_never_from_the_hex() -> None:
    """R607: the hex of a SHA was read as a version — two live pins reported INTROUVABLE
    and « -23434 » majors behind, every night."""
    assert cad.pin_of(SHA, " v6.1.0 — pinned: this job holds the SMTP secrets") == ("v6.1.0", SHA)
    assert cad.pin_of(SHA, None) == (None, SHA), "no comment: unversioned, never guessed"
    assert cad.pin_of("v6", None) == ("v6", None)
    m = cad._USES.match(f"      - uses: actions/checkout@{SHA}  # v6.1.0")
    assert cad.pin_of(m.group(2), m.group(3)) == ("v6.1.0", SHA)


def test_a_comment_that_names_another_commit_is_called_a_liar() -> None:
    assert cad.sha_resolution(SHA, SHA) is True
    assert cad.sha_resolution(SHA, "0" * 40) == "menteur"
    assert "MENTEUR" in cad.row_marks(0, cad.sha_resolution(SHA, "0" * 40))[1]
    assert cad.sha_resolution(SHA, "") is False
    assert cad.sha_resolution(SHA, None) is None, "could not ask is not a verdict"
