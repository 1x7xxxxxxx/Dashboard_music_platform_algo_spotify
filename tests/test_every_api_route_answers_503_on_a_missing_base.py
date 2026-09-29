"""Every API route that receives the database either fails closed with 503 or checks None.

Type: Sub
Uses: src/api/main.py (the app's routes and their dependency trees)
Depends on: nothing — FastAPI's dependant graph, read without a request

R333 (2026-09-29): the R332 sweep flagged `get_db()` for yielding None to every router,
which would answer 500 on a base outage. Read route by route, it does not: each one also
depends on `get_current_user`, which raises 503 on a None base BEFORE the endpoint runs,
or is the login, which checks None itself. What this pins is that property, so a new
route taking `get_db` without authentication cannot bring the 500 back.

Mutation record (2026-09-29): seen red with `login` removed from SELF_CHECKED. The first
draft walked `app.routes` only and passed on 2 routes out of 11 — caught by that mutation.
"""
from fastapi.routing import APIRoute

from src.api.deps import get_current_user, get_db
from src.api.main import app
from src.api.routers.auth import login

# Endpoints that take the base without a user, each checking None itself (read 2026-09-29).
SELF_CHECKED = {login}


def _calls(dep) -> set:
    out = {dep.call}
    for sub in dep.dependencies:
        out |= _calls(sub)
    return out


def _flat(routes) -> list[APIRoute]:
    """Every APIRoute, including those behind FastAPI 0.14x's `_IncludedRouter` wrapper —
    `app.routes` alone showed 2 of the 11 routes, and this guard passed on nothing."""
    out = []
    for r in routes:
        if isinstance(r, APIRoute):
            out.append(r)
        elif getattr(r, "original_router", None) is not None:
            out += _flat(r.original_router.routes)
    return out


def unsafe(routes) -> list[str]:
    return [r.endpoint.__name__ for r in _flat(routes)
            if get_db in (calls := _calls(r.dependant)) and get_current_user not in calls
            and r.endpoint not in SELF_CHECKED]


def test_the_walk_reaches_the_included_routers() -> None:
    names = {r.endpoint.__name__ for r in _flat(app.routes)}
    assert {"login", "get_kpis", "get_me"} <= names, sorted(names)


def test_no_route_hands_a_missing_base_to_its_body() -> None:
    assert not unsafe(app.routes), (
        "these routes take get_db without get_current_user (which answers 503 on a None "
        f"base) — with Postgres down they would answer 500: {unsafe(app.routes)}")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    from fastapi import Depends, FastAPI

    probe = FastAPI()

    @probe.get("/leak")
    def leak(db=Depends(get_db)):  # noqa: B008
        return {}

    @probe.get("/safe")
    def safe(db=Depends(get_db), user=Depends(get_current_user)):  # noqa: B008
        return {}

    assert unsafe(probe.routes) == ["leak"]
