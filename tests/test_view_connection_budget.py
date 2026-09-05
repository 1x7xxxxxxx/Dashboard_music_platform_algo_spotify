"""One render, one connection — and a ceiling on the views that break it.

Installed 2026-08-21, replacing roadmap item R9's description with its measurement.

R9 read: "16 views still on legacy `get_db_connection()` — valid but non-conforming
to rule #9. Tech-debt, **not a leak**." Measuring the 18 files that actually match
showed something the sentence hides:

    admin.py            5 connections per render  ← fixed 2026-08-21, now 1
    hypeddit.py         5   ← fixed 2026-08-21, now 1
    airflow_kpi.py      4   ← fixed 2026-08-21, now 1
    export_csv.py       2   ← fixed 2026-08-21, now 1
    export_pdf.py       2   ← fixed 2026-08-21, now 1

Rule #9 does not say "prefer one connection", it says a view opens exactly one and
never opens a second as a fallback. Five is not a style deviation.

The other thirteen open exactly one and differ only in how they spell the guard —
those are conformance, and migrating them is a one-line change per view whenever
one is touched.

Three of them, though, cannot use `view_session()` as it stands, and that is worth
knowing before anyone attempts the sweep R9 implied:

  * `admin.py`, `airflow_kpi.py`, `perf_monitor.py` never call `get_artist_id()` —
    they are cross-tenant admin surfaces, and `view_session()` insists on a tenant.
    Both `admin` and `airflow_kpi` are down to ONE connection anyway (2026-08-21):
    the rule-#9 breach was the count, and it is fixed without `view_session()`;
  * `referral.py` REFUSES admins outright (`artist_id is None` → info + return),
    the exact opposite of `view_session()`'s admin → `artist_id = 1` fallback.
    Migrating it mechanically would hand admins a referral programme the view
    deliberately denies them.

This test does not migrate anything. It stops the count from growing, and it fails
loudly if someone "modernises" a view whose semantics do not fit.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


def _repo_root() -> Path:
    for d in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ found above this test")


REPO = _repo_root()
VIEWS = REPO / "src" / "dashboard" / "views"

# Measured 2026-08-21. Lower a number when a view is migrated; never raise one.
# A view absent from this map must open at most one connection.
_KNOWN_MULTI: dict[str, int] = {}
# Emptied 2026-08-21.
#
# ⚠️ Corrected 2026-08-30. This comment used to read "Every view under
# src/dashboard/views/ now opens exactly one connection per render". That claim was
# false, and it was false *because of how this file measures*: the count below is a
# regex over the source text, so it cannot see `project_db()`, `view_session()`, or a
# connection opened by a CALLEE. Measured at the render — patching
# `PostgresHandler._connect` and rendering all 42 views — `hypeddit` opened TWO,
# because `_render_history()` closed the shared connection mid-page and
# `_ensure_connection()` silently reconnected.
#
# The runtime count now lives in `tests/test_a_render_opens_one_connection.py`, which
# asks rule #9's actual question. This file keeps its ratchet on the TEXTUAL count —
# still useful, and honest about being a proxy.
#
# A name reappearing here is a regression, not a baseline.
# Lowered 2026-08-21: export_csv.py and export_pdf.py each opened a `db2` while
# `db` was still open — the fallback rule #9 forbids by name. export_pdf's was the
# starker case: `_show_form(db)` received the right connection as a parameter and
# opened another anyway. Both now open exactly one, so they left this map.

# Views whose session semantics `view_session()` cannot express today.
_CANNOT_MIGRATE_AS_IS = {
    "admin.py": "cross-tenant admin surface — never resolves a tenant",
    "airflow_kpi.py": "cross-tenant admin surface — never resolves a tenant",
    "perf_monitor.py": "cross-tenant admin surface — never resolves a tenant",
    "referral.py": "refuses admins; view_session gives them artist_id = 1",
}


def _view_files() -> list[Path]:
    return sorted(p for p in VIEWS.rglob("*.py") if "__pycache__" not in str(p))


def _connections(path: Path) -> int:
    """Les APPELS à `get_db_connection()`, lus dans l'arbre — pas dans le texte.

    C'était une expression régulière jusqu'au 2026-09-05, et elle a compté DEUX
    connexions dans `_platform_soundcloud.py` là où il n'y en a qu'une : la seconde
    occurrence est un commentaire qui explique justement quand cette fonction rend
    `None`. Un garde qui lit du texte se déclenche sur sa propre documentation, et la
    seule façon de le faire taire est d'affaiblir le commentaire — c'est-à-dire de
    payer en lisibilité une erreur de mesure. Le dépôt appelle ça
    `guard-matches-its-own-comment` ; on lit donc l'AST.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(
        1 for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (getattr(node.func, "id", "") == "get_db_connection"
             or getattr(node.func, "attr", "") == "get_db_connection")
    )


def test_no_view_opens_more_connections_than_it_used_to():
    """The ceiling. Migrating lowers a number; nothing may raise one."""
    regressions = []
    for path in _view_files():
        rel = str(path.relative_to(VIEWS))
        n = _connections(path)
        allowed = _KNOWN_MULTI.get(rel, 1)
        if n > allowed:
            regressions.append(f"{rel}: {n} connections (ceiling {allowed})")
    assert not regressions, (
        "a view opens more connections than its recorded ceiling:\n  "
        + "\n  ".join(regressions)
        + "\n\nRule #9: one connection per show(), via view_session(). Never open a "
          "second as a fallback inside the same function."
    )


def test_the_ceiling_map_has_no_stale_entries():
    """A view that got migrated must be removed from the map, not left inflated.

    Otherwise the ceiling silently permits a regression back to the old number.
    """
    stale = []
    for rel, allowed in _KNOWN_MULTI.items():
        path = VIEWS / rel
        if not path.exists():
            stale.append(f"{rel}: listed but the file is gone")
            continue
        n = _connections(path)
        if n < allowed:
            stale.append(f"{rel}: now opens {n}, ceiling still says {allowed}")
    assert not stale, (
        "the ceiling map is out of date — lower these to lock the improvement in:\n  "
        + "\n  ".join(stale)
    )


@pytest.mark.parametrize("rel,reason", sorted(_CANNOT_MIGRATE_AS_IS.items()))
def test_the_views_view_session_cannot_serve_still_cannot(rel, reason):
    """Documented so a future sweep does not migrate them by pattern-match.

    Each assertion re-derives the reason from the source rather than trusting the
    comment: if a view starts resolving a tenant, or stops refusing admins, this
    fails and the map gets revisited instead of quietly lying.
    """
    src = (VIEWS / rel).read_text(encoding="utf-8")
    if "never resolves a tenant" in reason:
        assert "get_artist_id()" not in src, (
            f"{rel} now resolves a tenant — it may be migratable; revisit the map."
        )
    else:
        assert re.search(r"artist_id is None:\s*\n\s*st\.(info|warning)", src), (
            f"{rel} no longer refuses admins the way it did — revisit the map "
            "before migrating it to view_session()."
        )


def test_view_session_is_the_documented_path_for_new_views():
    """Rule #7 and #9 are structural only if the helper actually exists."""
    from src.dashboard.utils import view_session

    assert view_session.__doc__ and "artist_id" in view_session.__doc__
