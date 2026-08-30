"""A "not a real tenant" flag must be applied by every query that excludes one.

Type: Test
Uses: re
Depends on: src/**.py, airflow/**.py, src/utils/tenant_kind.py
Persists in: nothing

The class
---------
Before migration 080, "not a real tenant" was spelled `COALESCE(is_canary, FALSE) =
FALSE`, written out in two unrelated files: a public counter in `live_pulse.py` (inside
an f-string) and the onboarding-shaped checks in `credential_loader.py`. Adding a
second flag meant finding both by hand.

That is a class this repo already knows under another name: a rule that lives in two
places diverges, and the copy nobody thinks about is the one that stays wrong. The
predicate now lives once, in `src/utils/tenant_kind.py`.

What this asserts
-----------------
No SQL anywhere filters on one tenant-kind flag without the other. A query may
legitimately mention `is_sandbox` alone — `sandbox_tenant_ids` does, and that is the
definition of the set, not an exclusion — so the check is on the EXCLUSION shape
(`is_canary, FALSE) = FALSE`, `NOT is_canary`, `is_canary = FALSE`), not on the mere
appearance of a name.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ROOTS = ("src", "airflow", "tools")
_CANON = _ROOT / "src/utils/tenant_kind.py"

# "this row is NOT a canary" — the shapes an exclusion actually takes here.
_EXCLUDES_CANARY = re.compile(
    r"(COALESCE\(\s*is_canary[^)]*\)\s*=\s*FALSE|NOT\s+is_canary|is_canary\s*=\s*FALSE)",
    re.I)
_MENTIONS_SANDBOX = re.compile(r"is_sandbox", re.I)


def _python_files():
    for root in _ROOTS:
        for path in sorted((_ROOT / root).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            yield path


def test_the_shared_predicate_still_covers_both_flags():
    """The VALUE of the constant, not the text of the file.

    The first version of this assertion read the source and looked for the flag
    names — and stayed GREEN through a mutation that removed `is_sandbox` from the
    predicate, because the module's own docstring names it four times. Fourth textual
    guard caught being blind in one evening; the constant is importable, so there was
    never a reason to read the file at all.
    """
    from src.utils.tenant_kind import EXCLUDE_NON_HUMAN, HUMAN_TENANTS, NON_HUMAN_TENANT

    for flag in ("is_canary", "is_sandbox"):
        for name, sql in (("NON_HUMAN_TENANT", NON_HUMAN_TENANT),
                          ("HUMAN_TENANTS", HUMAN_TENANTS),
                          ("EXCLUDE_NON_HUMAN", EXCLUDE_NON_HUMAN)):
            assert flag in sql, (
                f"{name} no longer tests {flag}: {sql!r}\n"
                "It is the single definition of 'not a real tenant'; a flag missing "
                "from it is a flag that silently stops excluding, everywhere at once."
            )


def test_no_query_excludes_one_tenant_flag_without_the_other():
    offenders: list[str] = []
    for path in _python_files():
        if path == _CANON:
            continue                      # the definition itself
        body = path.read_text(encoding="utf-8")
        for i, line in enumerate(body.splitlines(), 1):
            if _EXCLUDES_CANARY.search(line) and not _MENTIONS_SANDBOX.search(line):
                offenders.append(f"{path.relative_to(_ROOT)}:{i}  {line.strip()[:80]}")

    assert not offenders, (
        "a query excludes canaries but not sandboxes:\n  " + "\n  ".join(offenders)
        + "\n\nBoth are tenants the operator runs, and both must stay out of public "
          "counters and onboarding alerts — a sandbox that leaks into either is a "
          "rehearsal being reported as a customer.\n"
          "Import the predicate from src/utils/tenant_kind.py instead of writing the "
          "condition again."
    )
