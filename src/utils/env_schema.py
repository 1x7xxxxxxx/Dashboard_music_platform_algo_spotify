"""The environment a service needs, checked when it starts — fatal in production (R619).

Type: Core
Uses: ast (the modules a service reaches, scanned for env reads), src.utils.instance_identity,
      src.utils.config_loader (the `config.yaml` alternative of FERNET_KEY)
Triggers: src/dashboard/serve.py (before Streamlit), src/api/main.py (`_preflight`), the
          airflow-scheduler command (`python -m src.utils.env_schema airflow-scheduler`),
          tools/check_env_parity.py (deploy)
Persists in: nothing

Why this exists — measured 2026-10-15
-------------------------------------
77 environment keys are read by literal name in src/ and airflow/dags/, and none was
validated at start. Two incidents came from an absent key that nothing said was absent:
2026-06-19 (Benken — the dashboard container had no central-app credential, every
connection test failed silently) and 2026-08-20 (the scheduler had no SMTP config for a
week: 672 failed runs, nobody told). The checks that existed were each written in ONE
caller (`app.py` for FERNET_KEY, `_preflight` for the API), so every new reader escaped.

What it validates, and what it deliberately does not
---------------------------------------------------
* `SCHEMA` holds only the keys that are REQUIRED in production or TYPED (int, float, url).
  The other read keys are in `UNVALIDATED`: known, listed, no default invented for them.
* Which service needs a key is DERIVED, never declared: a service needs the required keys
  that the modules it reaches (imports followed from its entry points, function-level
  imports included) read. This over-claims where an import is never executed — the API
  reaches `src.dashboard.utils` through the upward arc R626 removes — and over-claiming
  is the safe direction: the fix is wiring a key, not losing one.
* A read through a computed name cannot be scanned: it is in `NONLITERAL_READS` with
  its reason. `NAME = "KEY"` module constants are resolved.
Guard: tests/test_env_schema.py (every read key is classified, both ways).
"""
from __future__ import annotations

import ast
import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Spec:
    kind: str = "str"            # str | int | float | url
    required: bool = False       # in production
    min_len: int = 0
    alternatives: tuple[str, ...] = ()   # another env key that satisfies it
    config_key: str | None = None        # a config.yaml key that satisfies it


_REQ = Spec(required=True)
SCHEMA: dict[str, Spec] = {
    # Required — each one's absence degraded a user or operator path SILENTLY.
    "FERNET_KEY": Spec(required=True, config_key="fernet_key"),
    "APP_BASE_URL": Spec("url", required=True),   # links in mails pointed at localhost
    "STREAMLYTICS_ENV": _REQ,                      # absent ⇒ prod labels itself [LOCAL]
    "SMTP_HOST": _REQ, "SMTP_USER": _REQ, "SMTP_PASSWORD": _REQ, "ALERT_EMAIL": _REQ,
    "SPOTIFY_CLIENT_ID": _REQ, "SPOTIFY_CLIENT_SECRET": _REQ, "YOUTUBE_API_KEY": _REQ,
    "SOUNDCLOUD_CLIENT_ID": _REQ, "SOUNDCLOUD_CLIENT_SECRET": _REQ,
    "META_ACCESS_TOKEN": _REQ, "META_APP_ID": _REQ, "META_APP_SECRET": _REQ,
    "API_SECRET_KEY": Spec(required=True, min_len=32),  # else an ephemeral JWT key
    "DATABASE_URL": Spec(required=True, alternatives=("DATABASE_HOST",)),
    "STRIPE_SECRET_KEY": _REQ,
    "STRIPE_WEBHOOK_SECRET": _REQ,                 # absent ⇒ signatures not verified
    # Typed — read through int()/float() at import, or used as a link.
    **{k: Spec("int") for k in (
        "API_AUTH_RATE_LIMIT_MAX", "API_AUTH_RATE_LIMIT_WINDOW_SECS", "API_RATE_LIMIT_MAX",
        "API_RATE_LIMIT_WINDOW_SECS", "DASHBOARD_CACHE_EPOCH_TTL", "DASHBOARD_LOGIN_MAX",
        "DASHBOARD_LOGIN_WINDOW_SECS", "DASHBOARD_REGISTER_MAX",
        "DASHBOARD_REGISTER_WINDOW_SECS", "DASHBOARD_TOTP_MAX", "DASHBOARD_TOTP_WINDOW_SECS",
        "SESSION_IDLE_TIMEOUT_MINUTES", "SESSION_REAUTH_INTERVAL_SECS", "SMTP_PORT", "PORT",
        "STREAMLIT_METRICS_PORT", "TRUSTED_PROXY_HOPS", "READINESS_PROBE_BUDGET",
        "DATABASE_PORT", "ALERT_REPEAT_SILENCE_DAYS")},
    "DISTROKID_USD_EUR_RATE": Spec("float"),
    **{k: Spec("url") for k in (
        "API_BASE_URL", "AIRFLOW_BASE_URL", "AIRFLOW_UI_URL", "PROMETHEUS_URL",
        "STRIPE_CHECKOUT_URL", "STRIPE_PORTAL_URL")},
}

# Read, known, not validated: optional switches, identities that MUST stay empty in a
# multi-tenant deploy (tools/check_env_parity.py `_MUST_BE_EMPTY`), and values whose
# absence has a correct behaviour. No default is invented here — the reader keeps its own.
UNVALIDATED = frozenset({
    "AIRFLOW_ADMIN_PASSWORD", "AIRFLOW_ADMIN_USERNAME", "AIRFLOW_PASSWORD",
    "AIRFLOW_USERNAME",  # guarded where they are read: build_airflow_trigger()
    "API_ENABLE_DOCS", "API_STRICT_BOOT", "CORS_ORIGINS", "DATABASE_HOST", "DATABASE_NAME",
    "DATABASE_PASSWORD", "DATABASE_USER", "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET", "LEGACY_SINGLE_TENANT", "META_APP_DISPLAY_NAME",
    "META_BUSINESS_ID", "META_IG_DISCOVERY_ID", "METRICS_ADDR", "ML_MODELS_PATH",
    "OFFSITE_GIT_REMOTE", "OFFSITE_RECEIPT", "R2_REMOTE", "RATE_LIMIT_STORE",
    "SERVICE_CALENDLY_URL", "SOUNDCLOUD_REFRESH_TOKEN", "SPOTIFY_ARTIST_IDS",
    "STREAMLYTICS_ALLOW_ARTIST_EMAIL",  # an opt-in: absent IS the decision « no » (email_alerts)
    "STREAMLYTICS_GITHUB_REPO", "STRIPE_ALLOW_UNSIGNED", "STRIPE_REFERRAL_COUPON_ID",
    "YOUTUBE_CHANNEL_ID",
})

# `file:line-free expression` of every env read whose key is computed, with its reason.
NONLITERAL_READS = {
    "src/dashboard/utils/app_settings.py:env":
        "the key comes from CLES (SERVICE_CALENDLY_URL, SERVICE_PRICE_*): an env override "
        "of an admin setting that otherwise lives in the database",
    "src/dashboard/views/credentials/_core.py:k":
        "iterates _APP_LEVEL_CREDS: central-app keys, each in SCHEMA by its literal name",
    "src/utils/central_apps.py:var":
        "iterates _REQUIRED_ENV: central-app keys, each in SCHEMA by its literal name",
    "src/utils/email_alerts.py:self._OPT_IN":
        "STREAMLYTICS_ALLOW_NONPROD_EMAIL, a per-run opt-in outside production",
}

# A service's code, as entry points. The dashboard's views are imported by module string
# (routes.py), so every file under src/dashboard is an entry.
ENTRIES = {
    "dashboard": ("src/dashboard",),
    "api": ("src/api/main.py",),
    "airflow-scheduler": ("airflow/dags", "dags"),   # repo path, then the container's
}


def _env_arg(node: ast.AST) -> ast.AST | None:
    """The key argument of an env read, or None. getenv / environ.get|pop|setdefault / environ[...]."""
    if isinstance(node, ast.Call) and node.args and isinstance(node.func, ast.Attribute):
        fn = node.func
        if fn.attr == "getenv" and isinstance(fn.value, ast.Name) and fn.value.id == "os":
            return node.args[0]
        if fn.attr in ("get", "pop", "setdefault") and isinstance(fn.value, ast.Attribute) \
                and fn.value.attr == "environ":
            return node.args[0]
    if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) \
            and isinstance(node.value, ast.Attribute) and node.value.attr == "environ":
        return node.slice
    return None


def reads(source: str) -> tuple[set[str], list[str]]:
    """(literal keys, unparsed expressions of the non-literal reads) of one module."""
    tree = ast.parse(source)
    consts = {n.targets[0].id: n.value.value for n in ast.walk(tree)
              if isinstance(n, ast.Assign) and len(n.targets) == 1
              and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant)
              and isinstance(n.value.value, str)}
    keys, other = set(), []
    for node in ast.walk(tree):
        arg = _env_arg(node)
        if arg is None:
            continue
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            keys.add(arg.value)
        elif isinstance(arg, ast.Name) and arg.id in consts:
            keys.add(consts[arg.id])
        else:
            other.append(ast.unparse(arg))
    return keys, other


def _module_file(root: Path, dotted: str) -> Path | None:
    p = root.joinpath(*dotted.split("."))
    for cand in (p.with_suffix(".py"), p / "__init__.py"):
        if cand.is_file():
            return cand
    return None


def _imports(tree: ast.AST, root: Path) -> set[Path]:
    """Files of the `src.*` modules a module imports, at any depth, each prefix included."""
    out = set()
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
        for name in names:
            parts = name.split(".")
            if parts[0] != "src":
                continue
            for i in range(2, len(parts) + 1):
                f = _module_file(root, ".".join(parts[:i]))
                if f:
                    out.add(f)
    return out


def _entry_files(service: str, root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in ENTRIES[service]:
        p = root / rel
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files += sorted(p.rglob("*.py"))
            if service == "airflow-scheduler":
                break   # the repo path and the container path are the same tree
    return files


@lru_cache(maxsize=None)
def keys_read_by(service: str, root: Path = ROOT) -> frozenset[str]:
    """Every env key read by the modules `service` reaches from its entry points."""
    seen: set[Path] = set()
    stack = _entry_files(service, root)
    keys: set[str] = set()
    while stack:
        f = stack.pop()
        if f in seen:
            continue
        seen.add(f)
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        keys |= reads(src)[0]
        stack += _imports(tree, root)
    return frozenset(keys)


def required_for(service: str, root: Path = ROOT) -> frozenset[str]:
    return frozenset(k for k in keys_read_by(service, root) if SCHEMA.get(k, Spec()).required)


def _type_problem(key: str, spec: Spec, value: str) -> str | None:
    if spec.kind == "int":
        try:
            int(value)
        except ValueError:
            return f"{key} is not an integer"
    elif spec.kind == "float":
        try:
            float(value)
        except ValueError:
            return f"{key} is not a number"
    elif spec.kind == "url":
        u = urlparse(value)
        if u.scheme not in ("http", "https") or not u.netloc:
            return f"{key} is not an http(s) URL"
    if len(value) < spec.min_len:
        return f"{key} is shorter than {spec.min_len} characters"
    return None


def _config() -> dict:
    from src.utils.config_loader import config_loader
    return config_loader.load() or {}


def problems(service: str, env: dict[str, str] | None = None, config=_config,
             root: Path = ROOT) -> list[str]:
    """What is wrong with `env` for `service`: absent required keys, mistyped values.
    Never a value in the message — only the key."""
    env = os.environ if env is None else env
    out = []
    for key in sorted(keys_read_by(service, root) & SCHEMA.keys()):
        spec, value = SCHEMA[key], (env.get(key) or "").strip()
        if value:
            p = _type_problem(key, spec, value)
            if p:
                out.append(p)
            continue
        if not spec.required or key not in required_for(service, root):
            continue
        if any((env.get(a) or "").strip() for a in spec.alternatives):
            continue
        if spec.config_key and config().get(spec.config_key):
            continue
        alt = [*spec.alternatives] + ([f"config.yaml `{spec.config_key}`"] if spec.config_key else [])
        out.append(f"{key} is absent" + (f" (nor {', '.join(alt)})" if alt else ""))
    return out


def main(argv: list[str] | None = None) -> int:
    """`python -m src.utils.env_schema <service>`: exit 1 in production on any problem,
    a warning and 0 elsewhere — a dev box or CI keeps starting."""
    from src.utils.instance_identity import is_production

    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] not in ENTRIES:
        print(f"usage: python -m src.utils.env_schema {{{'|'.join(ENTRIES)}}}", file=sys.stderr)
        return 2
    found = problems(args[0])
    if not found:
        print(f"▶ env schema: {args[0]} — every required key present and well-typed", flush=True)
        return 0
    head = f"env schema: {args[0]} — {len(found)} problem(s): " + "; ".join(found)
    if is_production():
        print(f"❌ {head} — refusing to start in production", file=sys.stderr, flush=True)
        return 1
    print(f"⚠ {head} (not production: starting anyway)", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
