"""Every env var a service's code can read is wired to its container, or decided (R408).

Type: Guard
Uses: docker-compose.example.yml, tests/test_env_contract._env_keys_read
Depends on: the source tree (AST only)
Persists in: nothing

R283 (2026-10-05): the owner set `STRIPE_REFERRAL_COUPON_ID` in the prod `.env`, and
`coupon_set` read False in BOTH the api and the dashboard. The compose services take an
explicit `environment:` map, no `env_file`, so a variable that is not named there never
reaches the container. `test_env_contract.py` could not see it: it checks a CLOSED list
of eleven names, and it has no `api` group. A sweep found three more dashboard reads in
the same state: `SESSION_IDLE_TIMEOUT_MINUTES`, `API_BASE_URL`, `DISTROKID_USD_EUR_RATE`.

The property this guard checks is the open one. Start from a service's own code, follow
its `src.*` imports transitively (function-level imports included), and collect every
env name read literally. Each name must either be declared in that service's
`environment:` or appear below with the reason its absence is intended. A new
`os.getenv` therefore forces a decision; it can no longer be silently unwired.

Mutations, 2026-10-05: removing `STRIPE_REFERRAL_COUPON_ID` from the api `environment:`
→ RED; adding a new `os.getenv("ZZ_PROBE")` to `src/dashboard/auth.py` → RED.
Not covered: a name built at runtime (`os.getenv(prefix + "_ID")`), and airflow
services (`test_env_contract.py` keeps its CRITICAL check there).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from tests.test_env_contract import _env_keys_read

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.example.yml"

# service → the code that IS that service (its import closure is followed from here).
SERVICES = {"dashboard": ["src/dashboard"], "api": ["src/api"]}

_DEFAULT = "absent ⇒ the code default is the production value; a tuning knob"
_LEGACY_DB = "superseded by DATABASE_URL, which pg_connect reads first"
# Absent on purpose, for every service.
INTENDED_ABSENT = {
    **{k: _DEFAULT for k in (
        "DASHBOARD_CACHE_EPOCH_TTL", "DASHBOARD_LOGIN_MAX", "DASHBOARD_LOGIN_WINDOW_SECS",
        "DASHBOARD_REGISTER_MAX", "DASHBOARD_REGISTER_WINDOW_SECS", "DASHBOARD_TOTP_MAX",
        "DASHBOARD_TOTP_WINDOW_SECS", "SESSION_REAUTH_INTERVAL_SECS", "RATE_LIMIT_STORE",
        "TRUSTED_PROXY_HOPS", "METRICS_ADDR", "STREAMLIT_METRICS_PORT", "ML_MODELS_PATH",
        "META_APP_DISPLAY_NAME", "PORT")},
    **{k: _LEGACY_DB for k in (
        "DATABASE_HOST", "DATABASE_NAME", "DATABASE_PASSWORD", "DATABASE_PORT",
        "DATABASE_USER")},
    "SERVICE_CALENDLY_URL": "the admin setting `service_calendly_url` wins; env is a seed",
    "AIRFLOW_ADMIN_USERNAME": "fallback name; compose wires AIRFLOW_USERNAME, read first",
    "AIRFLOW_ADMIN_PASSWORD": "fallback name; compose wires AIRFLOW_PASSWORD, read first",  # pragma: allowlist secret
    "STRIPE_ALLOW_UNSIGNED": "test-only switch; must stay unset in production",
}
# Reached only through `src/api/deps.py` → `src.dashboard.utils` → `auth`: imported by
# the api, never on a path an api request takes.
NOT_ON_AN_API_PATH = {"AIRFLOW_UI_URL", "APP_BASE_URL", "FERNET_KEY", "META_BUSINESS_ID",
                      "SESSION_IDLE_TIMEOUT_MINUTES"}


def _module_file(name: str) -> Path | None:
    p = ROOT / Path(*name.split("."))
    for c in (p.with_suffix(".py"), p / "__init__.py"):
        if c.exists():
            return c
    return None


def _imported(py: Path) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(ast.parse(py.read_text(encoding="utf-8-sig"))):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                base = ".".join(py.relative_to(ROOT).with_suffix("").parts[:-n.level])
                mod = f"{base}.{n.module}" if n.module else base
            else:
                mod = n.module or ""
            out |= {mod} | {f"{mod}.{a.name}" for a in n.names}
    # The dashboard runs with src/dashboard on sys.path: `from views.x import …`.
    return {f"src.dashboard.{m}" if m.startswith("views.") else m for m in out}


def _closure(roots: list[str]) -> set[Path]:
    seen: set[Path] = set()
    todo = [p for r in roots for p in (ROOT / r).rglob("*.py")]
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        todo += [mf for m in _imported(f) if m.startswith("src.")
                 if (mf := _module_file(m)) and mf not in seen]
    return seen


def _declared(service: str) -> set[str]:
    env = yaml.safe_load(COMPOSE.read_text())["services"][service].get("environment") or {}
    return set(env)


@pytest.mark.parametrize("service", list(SERVICES))
def test_every_env_read_is_wired_or_decided(service: str) -> None:
    allowed = _declared(service) | set(INTENDED_ABSENT)
    if service == "api":
        allowed |= NOT_ON_AN_API_PATH
    missing: dict[str, str] = {}
    for f in sorted(_closure(SERVICES[service])):
        for k in _env_keys_read(f) - allowed:
            missing.setdefault(k, str(f.relative_to(ROOT)))
    assert not missing, (
        f"`{service}` can read env var(s) its container never receives — set in .env, "
        f"they stay empty there (R283). Wire each into its `environment:` in "
        f"docker-compose.example.yml AND the prod compose, or record why absence is "
        f"intended:\n  " + "\n  ".join(f"{k}  (read in {f})" for k, f in sorted(missing.items())))


def test_no_decision_outlives_its_read() -> None:
    """An exception for a name no service reads any more is a stale decision."""
    read = {k for roots in SERVICES.values() for f in _closure(roots) for k in _env_keys_read(f)}
    stale = (set(INTENDED_ABSENT) | NOT_ON_AN_API_PATH) - read
    assert not stale, f"exceptions for names nothing reads: {sorted(stale)}"
