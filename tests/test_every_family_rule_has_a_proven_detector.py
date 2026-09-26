"""Every family rule is backed by at least one guard that proves itself.

Type: Sub
Uses: .claude/dev-docs/error-classes.md (declared `family:` + `seen_red: self-proving (…)`),
      .claude/dev-docs/error-family-rules.md, tools/dev/error_class_families.py
Depends on: nothing
Persists in: nothing

R180 step 5. A rule without a detector is a wish. The link is DERIVED, never hand-listed
(a hand-written « caught at » path goes stale — code-critic, 2026-09-26): for each family,
the guards of its classes whose `seen_red` is `self-proving (<file>::<test>)`. The check is
on the EFFECT side of existence: the named test must exist in its file — a path that only
exists proves nothing.

⚠️ This covers the COMMIT side. A family's nightly probes are not checked here; they are
checked by `tests/test_every_nightly_check_is_scheduled_and_heard.py`.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_RULES = _ROOT / ".claude" / "dev-docs" / "error-family-rules.md"
_PROOF = re.compile(r"^self-proving \(([^:)\s]+)::(\w+)\)")


def _families_module():
    sys.path.insert(0, str(_ROOT / "tools" / "dev"))
    import error_class_families
    return error_class_families


def proven_guards(entries, declared_family, one_line) -> dict:
    """{family: {(file, test)}} from the entries' `seen_red: self-proving (…)`. Pure."""
    out: dict = {}
    for _cid, body in entries:
        fam = declared_family(body)
        m = _PROOF.match(one_line(body, "seen_red"))
        if fam and m:
            out.setdefault(fam, set()).add((m.group(1), m.group(2)))
    return out


def unbacked(families, proven, test_exists) -> list[str]:
    """Families with NO guard whose named test really exists in its file. Pure."""
    return sorted(f for f in families
                  if not any(test_exists(path, test) for path, test in proven.get(f, ())))


def _test_exists(path: str, test: str) -> bool:
    p = _ROOT / path
    if not p.is_file():
        return False
    return any(isinstance(n, ast.FunctionDef) and n.name == test
               for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))))


def test_every_family_has_a_self_proving_guard_that_exists() -> None:
    f = _families_module()
    proven = proven_guards(f._entries(), f.declared_family, f._one_line)
    missing = unbacked(sorted(f.SLUGS), proven, _test_exists)
    assert not missing, (
        f"{missing} : aucune garde auto-prouvante vivante pour ces familles. Une règle sans "
        "détecteur est un vœu — écrire une garde qui fabrique le défaut, ou déclarer la "
        "famille `review-only` dans error-family-rules.md.")


def test_the_rules_document_names_exactly_the_families() -> None:
    f = _families_module()
    named = set(re.findall(r"`([^`\s]+)` \(\d+\)", _RULES.read_text(encoding="utf-8")))
    assert named == set(f.SLUGS), (
        f"en trop dans les règles : {sorted(named - f.SLUGS)} ; "
        f"manquantes : {sorted(f.SLUGS - named)}")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: a family whose only proof names a file that is gone, or a test that is
    not in its file, is unbacked; one real proof backs it."""
    entries = [("a", "- family: fam-a\n- seen_red: self-proving (tests/gone.py::test_x)\n"),
               ("b", "- family: fam-b\n- seen_red: self-proving (tests/t.py::test_real)\n"),
               ("c", "- family: fam-b\n- seen_red: 2026-09-18\n")]

    def one_line(body, field):
        m = re.search(rf"^- {field}: (.+)$", body, re.M)
        return m.group(1) if m else ""

    def declared(body):
        return one_line(body, "family") or None

    proven = proven_guards(entries, declared, one_line)
    exists = {("tests/t.py", "test_real")}.__contains__
    assert unbacked(["fam-a", "fam-b", "fam-c"], proven,
                    lambda p, t: exists((p, t))) == ["fam-a", "fam-c"]
