"""One factory builds the DSN, and it works in both containers (R33).

Installed 2026-08-21. Four modules built their own connection, and they did not
agree — which mirrored a real split in production:

    Airflow      DATABASE_HOST=postgres, DATABASE_PORT=5432, no DATABASE_URL
    api/dashboard  DATABASE_URL set, no DATABASE_HOST

`credential_loader` (env vars, host default `localhost`) is imported only by DAGs
and collectors, which is the only reason its default never fired: inside the
dashboard container, where `DATABASE_HOST` is unset, it would have reached for
`localhost` and found nothing. `circuit_breaker` and `dag_run_logger` defaulted to
`postgres` instead — correct in Airflow, wrong anywhere else. `stripe_webhook` read
DATABASE_URL then config.yaml and knew nothing of the env vars.

Each worked where it happened to run. None worked in the other place.

`src.utils.pg_connect.connect()` resolves all three sources in order of
specificity, so no caller has to know which container it is in. These tests pin
that order, pin that no module rebuilds a DSN behind its back, and pin the two
behaviours that were deliberate and must survive the merge: `stripe_webhook`
still returns None rather than raising, and the factory itself still raises.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _repo_root() -> Path:
    for d in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ found above this test")


REPO = _repo_root()

# Every module that used to build its own DSN.
MIGRATED = (
    "src/utils/credential_loader.py",
    "src/utils/circuit_breaker.py",
    "src/utils/dag_run_logger.py",
    "src/api/routers/stripe_webhook.py",
    # R33 named five modules. The guard below found seven: three collectors filled
    # PostgresHandler's constructor from the same five variables, one layer up.
    "src/collectors/instagram_api_collector.py",
    "src/collectors/meta_ads_api_collector.py",
    "src/collectors/soundcloud_api_collector.py",
)


def _code(path: str) -> str:
    """Source with docstrings stripped — prose describing the old shape is not code."""
    tree = ast.parse((REPO / path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            if ast.get_docstring(node) and node.body and isinstance(node.body[0], ast.Expr):
                node.body.pop(0)
                if not node.body:
                    node.body.append(ast.Pass())
    return ast.unparse(ast.fix_missing_locations(tree))


# ── The single factory ───────────────────────────────────────────────────────

@pytest.mark.parametrize("path", MIGRATED)
def test_no_module_rebuilds_the_dsn(path):
    code = _code(path)
    assert "psycopg2.connect" not in code, (
        f"{path} builds its own connection again. The DSN belongs to "
        "src/utils/pg_connect.py — four copies is how the host default came to "
        "differ between two of them."
    )
    assert "pg_connect" in code or "from_env_or_config" in code, (
        f"{path} routes through neither pg_connect nor PostgresHandler.from_env_or_config "
        "— the two doors onto the single resolution."
    )


@pytest.mark.parametrize("path", MIGRATED)
def test_no_module_reads_the_connection_variables(path):
    code = _code(path)
    for var in ("DATABASE_HOST", "DATABASE_PORT", "DATABASE_NAME",
                "DATABASE_USER", "DATABASE_PASSWORD"):
        assert var not in code, (
            f"{path} reads {var} directly. Resolving the DSN in two places is "
            "how one of them ends up with a default the other does not have."
        )


def test_only_pg_connect_holds_a_default_host():
    """The grep that would have caught the original split in one line."""
    offenders = []
    pattern = re.compile(r"os\.getenv\(\s*['\"]DATABASE_HOST['\"]\s*,")
    for py in sorted((REPO / "src").rglob("*.py")):
        if py.name == "pg_connect.py":
            continue
        if pattern.search(py.read_text(encoding="utf-8")):
            offenders.append(str(py.relative_to(REPO)))
    assert not offenders, (
        f"a DATABASE_HOST default outside pg_connect.py: {offenders}. That is the "
        "exact shape of the 'localhost' vs 'postgres' divergence."
    )


# ── The resolution order ─────────────────────────────────────────────────────

def test_database_url_wins(monkeypatch):
    from src.utils import pg_connect

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:1/d")
    monkeypatch.setenv("DATABASE_HOST", "should-not-be-used")
    assert pg_connect.dsn_source() == "DATABASE_URL"
    with patch("psycopg2.connect", return_value=MagicMock()) as m:
        pg_connect.connect()
    m.assert_called_once_with("postgresql://u:p@h:1/d")


def test_env_vars_are_used_when_there_is_no_url(monkeypatch):
    """The Airflow shape: DATABASE_HOST set, DATABASE_URL absent."""
    from src.utils import pg_connect

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_HOST", "postgres")
    monkeypatch.setenv("DATABASE_PORT", "5432")
    monkeypatch.setenv("DATABASE_NAME", "spotify_etl")
    assert pg_connect.dsn_source() == "env"
    with patch("psycopg2.connect", return_value=MagicMock()) as m:
        pg_connect.connect()
    kwargs = m.call_args.kwargs
    assert kwargs["host"] == "postgres" and kwargs["port"] == 5432


def test_a_missing_configuration_says_what_to_do(monkeypatch):
    """Silence here becomes 'no rows' three call frames later."""
    from src.utils import pg_connect

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_HOST", raising=False)
    with patch.object(pg_connect, "_config_kwargs", return_value=None):
        with pytest.raises(RuntimeError) as exc:
            pg_connect.connect()
    msg = str(exc.value)
    assert "DATABASE_URL" in msg and "config.yaml" in msg, msg


def test_autocommit_is_honoured(monkeypatch):
    """Two of the four call sites write; the merge must not lose it."""
    from src.utils import pg_connect

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:1/d")
    fake = MagicMock()
    with patch("psycopg2.connect", return_value=fake):
        pg_connect.connect()
        assert fake.autocommit is False
        pg_connect.connect(autocommit=True)
        assert fake.autocommit is True


# ── The two behaviours that had to survive ───────────────────────────────────

def test_stripe_webhook_still_returns_none_instead_of_raising(monkeypatch):
    """A webhook must answer Stripe, not raise into the ASGI stack."""
    from src.api.routers import stripe_webhook

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:1/d")
    with patch("psycopg2.connect", side_effect=OSError("down")):
        assert stripe_webhook._get_db() is None


def test_the_factory_itself_still_raises(monkeypatch):
    """A connection helper that swallows its failure turns an outage into 'no rows'."""
    from src.utils import pg_connect

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:1/d")
    with patch("psycopg2.connect", side_effect=OSError("down")):
        with pytest.raises(OSError):
            pg_connect.connect()
