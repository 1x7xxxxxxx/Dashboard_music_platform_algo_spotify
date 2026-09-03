"""Guard: the weekly recap reaches paying tenants, and only them.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Error class `capability-resolved-only-inside-a-session`.

Measured 2026-09-03, building on the 2026-08-31 finding. The weekly digest sent one
message PER TENANT and every one of them to `ALERT_EMAIL`: the subject
`[Benken] Weekly KPI` **named** the tenant without addressing them, and the run logged
`7/7 emails sent`, all seven in the operator's inbox.

Making it a paid feature ran into something the repo had never needed before: **no
Airflow DAG had ever read the plan tables for entitlement.** The full precedence —
promo → active Stripe subscription → legacy `saas_artists.tier` → free — existed once,
inside `src/dashboard/auth.py`, behind `@st.cache_data` and `st.session_state`.
`alert_monitor.check_billing_sync` touches `artist_subscriptions`, but only to flag
Stripe drift to the operator; it never asks whether a tenant may have a feature.

## The four decisions these tests pin

1. **One resolver.** Extracted to `src/utils/plan_resolver`, imported by both
   `auth.py` and the DAG. Two implementations of a billing precedence drift in the
   direction that shows on neither surface: a customer paying for premium who stops
   receiving it, or a free tenant who receives it.
2. **A non-page capability set.** `PLAN_FEATURES` keys are Streamlit routes by
   contract, and `tests/test_plan_gating.py` iterates the free set AS PAGES. A digest
   is not a page.
3. **All eligible users, not one canonical.** `saas_users.artist_id` has no UNIQUE
   constraint, so picking one would need an arbitrary tie-break that silently drops a
   co-manager.
4. **A dedicated opt-out, not `marketing_consent`.** That flag defaults to FALSE and
   is only ever set at signup, so gating on it would mean most premium tenants never
   receive what they bought — with nothing reporting it.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
DAG = REPO / "airflow" / "dags" / "weekly_digest.py"
AUTH = REPO / "src" / "dashboard" / "auth.py"


def _dag_tree() -> ast.Module:
    return ast.parse(DAG.read_text(encoding="utf-8"))


def _fn(tree: ast.Module, name: str) -> ast.FunctionDef:
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == name), None)
    assert fn is not None, f"{name} is gone from weekly_digest.py — guard points at air"
    return fn


# ── 1. A free tenant is never mailed ────────────────────────────────────────

def test_the_digest_checks_the_capability_before_sending():
    send = _fn(_dag_tree(), "send_weekly_digest")
    called = {n.func.id for n in ast.walk(send)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "has_capability" in called, (
        "the digest no longer asks whether the tenant may have it. Every active "
        "tenant would be mailed, free ones included — a paid feature given away, and "
        "an e-mail to someone who never agreed to receive it."
    )


def test_only_premium_holds_the_digest_capability():
    from src.database.stripe_schema import PLAN_CAPABILITIES

    assert "weekly_digest" in PLAN_CAPABILITIES["premium"]
    assert "weekly_digest" not in PLAN_CAPABILITIES["free"]


def test_capabilities_are_not_page_routes():
    """The inverse of `PLAN_FEATURES`' contract, asserted so the two cannot merge."""
    from src.database.stripe_schema import ALWAYS_ACCESSIBLE, PLAN_CAPABILITIES, PLAN_FEATURES

    pages = set(PLAN_FEATURES["free"]) | set(ALWAYS_ACCESSIBLE)
    for plan, caps in PLAN_CAPABILITIES.items():
        overlap = caps & pages
        assert not overlap, (
            f"{plan} capability {overlap} is also a page route. Page entitlements "
            "belong in PLAN_FEATURES, which test_plan_gating iterates as pages; "
            "mixing the two makes both sets mean nothing."
        )


# ── 2. One resolver, reachable from a DAG ───────────────────────────────────

def test_the_dashboard_and_the_dag_share_one_resolver():
    auth = AUTH.read_text(encoding="utf-8")
    assert "plan_resolver" in auth, (
        "auth.py no longer delegates to src/utils/plan_resolver: the precedence now "
        "exists twice, and the copies drift where nothing looks."
    )


def test_the_resolver_imports_no_streamlit():
    """The condition for a DAG being able to import it at all."""
    src = (REPO / "src" / "utils" / "plan_resolver.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module]
        assert not any(m.split(".")[0] == "streamlit" for m in mods), (
            f"plan_resolver imports streamlit at line {node.lineno}. An Airflow task "
            "has no session; the import alone is enough to break it."
        )


def test_the_resolver_does_not_inherit_the_admin_shortcut():
    """`_view_as` is a session preview, never a billing fact.

    A DAG asking "may artist 12 have the digest?" must not get `premium` because
    somebody is previewing a page in a browser.
    """
    src = (REPO / "src" / "utils" / "plan_resolver.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    literals = [n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    code_strings = [s for s in literals if len(s) < 40]
    assert "_view_as" not in " ".join(code_strings)


# ── 3. Who is written to ────────────────────────────────────────────────────

def test_the_recipient_query_requires_verification_and_enrolment():
    tree = _dag_tree()
    fn = _fn(tree, "_digest_recipients")
    raw = " \n".join(n.value for n in ast.walk(fn)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str))
    # SQL comments stripped first. Without this the guard passes on a clause that has
    # been commented OUT — found by mutation on 2026-09-03: prefixing `AND
    # email_verified` with `--` left the string present and the test green, while the
    # query happily mailed unverified addresses. Presence is not activity.
    sql = " ".join(line.split("--", 1)[0] for line in raw.splitlines())
    for clause in ("email_verified", "weekly_digest_optout_at IS NULL",
                   "role = 'artist'", "active"):
        assert clause in sql, (
            f"the recipient query dropped `{clause}`. Without it the digest reaches "
            "an unverified address, an opted-out reader, or an admin account."
        )
    assert "artist_id = %s" in sql, "the recipient query is not scoped to one tenant"


def test_the_recipient_query_is_parameterised():
    fn = _fn(_dag_tree(), "_digest_recipients")
    for node in ast.walk(fn):
        assert not isinstance(node, ast.JoinedStr), (
            f"an f-string at line {node.lineno} in the recipient query: values go "
            "through %s, always (cross-cutting rule #8)."
        )


# ── 4. Failure is isolated, and undelivered paid mail is loud ───────────────

def test_one_tenant_failure_does_not_stop_the_others():
    send = _fn(_dag_tree(), "send_weekly_digest")
    handlers = [h for h in ast.walk(send) if isinstance(h, ast.ExceptHandler)]
    assert handlers, "per-tenant isolation is gone from the digest loop"
    assert any(any(isinstance(n, ast.Continue) for n in ast.walk(h)) for h in handlers), (
        "no `continue` in the failure branch: one tenant's bad data now stops every "
        "other tenant's digest."
    )


def test_a_premium_tenant_reached_by_nothing_makes_the_task_red():
    """A paid feature that silently did not ship is an incident, not a statistic."""
    send = _fn(_dag_tree(), "send_weekly_digest")
    raises = [n for n in ast.walk(send) if isinstance(n, ast.Raise)]
    assert raises, (
        "the digest can now finish green having delivered nothing to a paying "
        "customer. That is the shape of the 2026-08-31 defect, one layer over."
    )


def test_the_operator_alert_channel_is_untouched():
    """`send_alert` must keep going to ALERT_EMAIL — a mute monitor IS the incident."""
    alerts = (REPO / "src" / "utils" / "email_alerts.py").read_text(encoding="utf-8")
    assert "self.alert_email" in alerts
    dag = DAG.read_text(encoding="utf-8")
    assert "send_email(" in dag, "the digest no longer addresses tenants at all"
