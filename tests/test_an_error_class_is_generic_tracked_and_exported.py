"""R264 — error classes: a duplicate check at admission, their health exported to
Prometheus, and the slowest signatures measured.

Type: Test
Uses: .claude/scripts/audit_runner.py (duplicate_gap, slowest_report),
      tools/dev/error_class_metrics.py (render)

Critic verdicts (critic-2026-09-27.md, R264) : no « family signature » (a form predicate
over-counts, rule 20) — a duplicate check at ADMISSION ; the health exported through
Prometheus from the ONE parser's output, not a table in the tenants' base ; « measure
first » before speeding up the sweep (first measure: one signature = 70 % of 133 s).

Mutation record (2026-09-28) : `duplicate_gap` accepting a closest class of ANOTHER family
→ red ; `first-in-family` accepted in a populated family → red ; `render` dropping the
holes → red.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


audit = _load("audit_runner_r264", ".claude/scripts/audit_runner.py")
metrics = _load("error_class_metrics", "tools/dev/error_class_metrics.py")

_HEADERS = [{"id": "a-tenant-default", "family": "le-locataire"},
            {"id": "a-tenant-join", "family": "le-locataire"},
            {"id": "a-cumul-daily", "family": "un-cumul-pris-pour-un-quotidien"}]


def _new(closest, family="le-locataire"):
    return {"id": "a-new-one", "family": family, "closest": closest}


def test_a_new_class_names_its_closest_sibling_and_why():
    ok = _new("a-tenant-join — the join names its tenant, this one is the write")
    assert audit.duplicate_gap(ok, _HEADERS + [ok]) is None
    assert "aucun champ" in audit.duplicate_gap(_new(None), _HEADERS)
    assert "illisible" in audit.duplicate_gap(_new("a-tenant-join"), _HEADERS)


def test_the_closest_class_must_be_of_the_same_family():
    wrong = _new("a-cumul-daily — a different family entirely here")
    assert "n'est pas une autre classe" in audit.duplicate_gap(wrong, _HEADERS)


def test_first_in_family_only_when_the_family_is_empty():
    assert "compte déjà" in audit.duplicate_gap(_new("first-in-family"), _HEADERS)
    lone = _new("first-in-family", family="une-famille-vide")
    assert audit.duplicate_gap(lone, _HEADERS + [lone]) is None


def test_the_slowest_signatures_are_reported_with_their_share():
    lines = audit.slowest_report({"a": 90.0, "b": 10.0}, n=1)
    assert "100 s" in lines[0] and "a" in lines[1] and "90.0%" in lines[1]
    assert audit.slowest_report({}) == []


def test_the_catalogue_health_renders_as_prometheus_text_not_vacuous():
    doc = {"aggregate": {"population": {"classes": 427, "prose_only": 8},
                         "recurrence": {"observed": {"per_class_month": 0.17}},
                         "holes": {"seen_red_unknown": 10}}}
    text = metrics.render(doc)
    assert 'streamlytics_error_classes{kind="classes"} 427.0' in text
    assert "streamlytics_error_class_recurrence_per_class_month 0.17" in text
    assert 'streamlytics_error_class_holes{hole="seen_red_unknown"} 10.0' in text
    assert text.count("# TYPE") == 3


def test_a_sweep_past_its_budget_names_its_slowest_signature():
    """REQ-ERR-04 — the sweep fits the CI budget, or the run fails naming the culprit."""
    assert audit.over_budget({"a": 100.0, "b": 33.0}, budget=1800) is None
    verdict = audit.over_budget({"a": 1700.0, "b": 200.0}, budget=1800)
    assert verdict and "a" in verdict and "1900" in verdict
