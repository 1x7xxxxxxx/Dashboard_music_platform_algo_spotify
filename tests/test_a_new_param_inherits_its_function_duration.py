"""R497 — a new `[param]` of an already-measured function is not a missing duration.

Type: Hook
Uses: tools/dev/check_durations_are_collectable.py
Depends on: nothing — pure function, in-memory ids

The commit hook's first refusal (`test-durations-missing`, 68 in 7 days on 2026-10-10)
was a catalogue class added to a test parametrized over the catalogue: one new id, in a
function `pytest-split` already knows, re-measured in series for nothing.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_F = "tests/test_x.py::test_each_class"


def _mod():
    spec = importlib.util.spec_from_file_location(
        "check_durations", ROOT / "tools/dev/check_durations_are_collectable.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_new_param_of_a_measured_function_is_not_missing():
    durees = {f"{_F}[a]": 0.1}
    collectes = {f"{_F}[a]", f"{_F}[b]"}
    reste, _ = _mod().inherited([f"{_F}[b]"], {}, durees, collectes)
    assert reste == []


def test_a_function_never_measured_is_still_missing():
    nouveaux = [f"{_F}[a]", "tests/test_y.py::test_plain"]
    reste, _ = _mod().inherited(nouveaux, {}, {}, set(nouveaux))
    assert reste == nouveaux, "a function with no measured param must still be measured"


def test_a_plain_test_never_inherits_from_a_param():
    durees = {f"{_F}[a]": 0.1}
    reste, _ = _mod().inherited([_F], {}, durees, {_F})
    assert reste == [_F], "an unparametrized id has no function to inherit from"


def test_a_phantom_param_is_tolerated_only_while_its_function_lives():
    phantoms = {f"{_F}[gone]": 0.1, "tests/test_z.py::test_removed[a]": 0.2}
    _, gardes = _mod().inherited([], phantoms, phantoms, {f"{_F}[a]"})
    assert gardes == {"tests/test_z.py::test_removed[a]": 0.2}


def test_a_test_that_becomes_parametrized_is_measured_again():
    """Its old plain duration says nothing about N params: the plain id is a phantom,
    the params are missing — neither inherits."""
    durees = {_F: 0.1}
    collectes = {f"{_F}[a]", f"{_F}[b]"}
    reste, gardes = _mod().inherited(sorted(collectes), {_F: 0.1}, durees, collectes)
    assert reste == sorted(collectes)
    assert gardes == {_F: 0.1}
