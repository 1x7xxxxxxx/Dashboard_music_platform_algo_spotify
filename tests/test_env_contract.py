"""Guard: a service's code must not read a central-app env var its container isn't given.

Type: Utility
Error class `env-not-wired-to-service`. The Benken incident (2026-06-19): the dashboard
container was deployed WITHOUT the central-app env vars (SPOTIFY/YOUTUBE/SOUNDCLOUD/META),
and SoundCloud was wired to no service at all — yet the credentials page reads them via
`os.getenv(...)`. Every connection test failed and nothing in CI could see it, because the
read has a silent `''` default. This test cross-checks "env vars read in a service's code"
against "env vars declared in that service's docker-compose.example.yml block".

Scope is the CRITICAL central-app set (vars whose absence silently breaks a USER path); a
default of `''` is exactly the trap, so we do NOT exempt vars that have a default.
"""
import ast
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.example.yml"

# Vars whose absence silently breaks a user path (connection test / collection).
CRITICAL = {
    "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET",
    "YOUTUBE_API_KEY",
    "SOUNDCLOUD_CLIENT_ID", "SOUNDCLOUD_CLIENT_SECRET",
    "META_ACCESS_TOKEN", "META_APP_ID", "META_APP_SECRET",
}

# code-path group → the docker-compose service that runs it (anchor merged by safe_load).
GROUPS = {
    "dashboard": (["src/dashboard"], "dashboard"),
    "airflow": (["src/collectors", "airflow/dags"], "airflow-scheduler"),
}


def _env_keys_read(py: Path) -> set[str]:
    """Literal env-var names read via os.getenv / os.environ.get / os.environ[...]."""
    keys: set[str] = set()
    try:
        tree = ast.parse(py.read_text(encoding="utf-8-sig"))
    except (SyntaxError, UnicodeDecodeError):
        return keys

    def _str(node):
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

    for node in ast.walk(tree):
        # os.getenv('X') / os.environ.get('X')
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.args:
            fn = node.func
            is_getenv = fn.attr == "getenv" and isinstance(fn.value, ast.Name) and fn.value.id == "os"
            is_environ_get = (
                fn.attr == "get" and isinstance(fn.value, ast.Attribute)
                and fn.value.attr == "environ"
                and isinstance(fn.value.value, ast.Name) and fn.value.value.id == "os"
            )
            if is_getenv or is_environ_get:
                k = _str(node.args[0])
                if k:
                    keys.add(k)
        # os.environ['X']
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute):
            v = node.value
            if (v.attr == "environ" and isinstance(v.value, ast.Name) and v.value.id == "os"):
                k = _str(node.slice)
                if k:
                    keys.add(k)
    return keys


def _critical_read_in(dirs: list[str]) -> dict[str, str]:
    """{critical_var: first file that reads it} across the given dirs."""
    found: dict[str, str] = {}
    for d in dirs:
        for py in (ROOT / d).rglob("*.py"):
            for k in _env_keys_read(py) & CRITICAL:
                found.setdefault(k, str(py.relative_to(ROOT)))
    return found


def _service_env_keys(service: str) -> set[str]:
    data = yaml.safe_load(COMPOSE.read_text())
    env = data["services"][service].get("environment", {}) or {}
    return set(env.keys()) if isinstance(env, dict) else set()


@pytest.mark.parametrize("group", list(GROUPS), ids=list(GROUPS))
def test_central_app_env_is_wired_to_its_service(group):
    dirs, service = GROUPS[group]
    read = _critical_read_in(dirs)
    declared = _service_env_keys(service)
    missing = {var: f for var, f in read.items() if var not in declared}
    assert not missing, (
        f"`{service}` runs code that reads central-app env var(s) NOT declared in its "
        f"docker-compose.example.yml `environment:` block — they'll be empty in that "
        f"container (the Benken incident):\n  "
        + "\n  ".join(f"{v}  (read in {f})" for v, f in sorted(missing.items()))
    )
