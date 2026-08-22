"""The nightly credential audit must ask about every platform, and about identities.

Installed 2026-08-22. Two defects in one task, `alert_monitor.check_credentials_all`:

  * `MONITORED_PLATFORMS = ['spotify','youtube','soundcloud','meta']` — four names
    typed by hand while `PLATFORM_IDENTITIES` has five. **Instagram was never asked
    about**, so a tenant losing their `ig_user_id` was invisible to the monitor while
    `instagram_daily` silently skipped them.
  * `if not creds` tested whether the dict was EMPTY, not whether an identity was
    present. Benken's `meta` row holds an `account_id` and nothing else, so the audit
    counted "credentials present" for a platform that has never produced one row —
    and would have counted the same row as proof for Instagram.

Both are the same mistake at different levels: restating what a registry already
knows. `declared_identities()` exists precisely to answer "which logical platforms
does this tenant actually carry an identity for".
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DAG = REPO / "airflow" / "dags" / "alert_monitor.py"


def test_the_audit_scope_is_not_a_hand_written_list():
    src = DAG.read_text(encoding="utf-8")
    assert "MONITORED_PLATFORMS = [" not in src, (
        "the audit scope is a literal list again. It was four names while the "
        "registry had five, and Instagram went unasked for months. Derive it from "
        "tenant_identity.PLATFORM_IDENTITIES."
    )
    assert "PLATFORM_IDENTITIES" in src, (
        "nothing in alert_monitor references the identity registry — the scope "
        "cannot be derived from it"
    )


def test_the_audit_covers_every_platform_the_registry_knows():
    """The list the audit iterates must equal the registry, not a subset."""
    import sys

    sys.path.insert(0, str(REPO))
    from src.utils.tenant_identity import PLATFORM_IDENTITIES

    # Import the helper without importing Airflow: extract and exec just the function.
    src = DAG.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "_monitored_platforms")
    ns: dict = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<x>", "exec"), ns)  # noqa: S102

    assert set(ns["_monitored_platforms"]()) == set(PLATFORM_IDENTITIES), (
        "the audited platforms differ from the registry — that difference is exactly "
        "where Instagram lived for months"
    )
    assert "instagram" in ns["_monitored_platforms"](), (
        "Instagram is missing again; it is the one that was missing before"
    )


def test_presence_is_judged_on_the_identity_not_on_the_row():
    """`if not creds` is dict-emptiness. A row can exist and carry no identity."""
    src = DAG.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "check_credentials_all")
    body = ast.get_source_segment(src, fn) or ""

    assert "declared_identities" in body, (
        "check_credentials_all no longer asks the shared helper which identities are "
        "declared. Testing the credentials dict for emptiness reports a `meta` row "
        "holding only an account_id as 'present' for every platform sharing that row."
    )

    # AST, not text: the first version of this assertion searched the source for the
    # literal "if not creds" and matched the COMMENT that explains why it is wrong.
    # A guard that can be tripped by its own documentation is not reading the code.
    truthiness_tests = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.If) and isinstance(n.test, ast.UnaryOp)
        and isinstance(n.test.op, ast.Not)
        and isinstance(n.test.operand, ast.Name)
        and n.test.operand.id in ("creds", "credentials")
    ]
    assert not truthiness_tests, (
        "the dict-emptiness test is back "
        f"(line {truthiness_tests[0].lineno}): a row that exists is not an identity"
    )


def test_a_row_with_only_an_instagram_id_does_not_count_as_meta():
    """The concrete asymmetry, as data — meta and instagram share one storage row."""
    import sys

    sys.path.insert(0, str(REPO))
    from src.utils.tenant_identity import declared_identities

    only_ig = declared_identities({"meta": {"ig_user_id": "17841400000000000"}})
    assert "instagram" in only_ig
    assert "meta" not in only_ig, (
        "an ig_user_id counted as a Meta Ads identity — the shared row is why the "
        "emptiness test was wrong in both directions"
    )

    only_ads = declared_identities({"meta": {"account_id": "act_65390907"}})
    assert "meta" in only_ads
    assert "instagram" not in only_ads, (
        "an ad account counted as an Instagram identity"
    )
