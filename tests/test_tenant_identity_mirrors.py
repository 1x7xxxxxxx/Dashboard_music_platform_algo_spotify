"""A tenant identity stored in two tables must be written by ONE code path.

Measured 2026-08-21: `saas_artists.spotify_artist_id` is what `spotify_api_daily`
reads to decide whose catalogue to collect; `artist_credentials.extra_config` is
what every screen and every readiness check reads. The credentials form wrote both.
`tools/create_canary.py` wrote only the second.

The canary then reported "Connecte -- artiste << Daft Punk >>" on every surface,
passed its connection test, and its DAG succeeded in half a second having collected
nothing. The tenant whose entire purpose is to catch a false green WAS the false green.

Error class: identity-mirrored-but-written-once (.claude/dev-docs/error-classes.md).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Everything that persists a tenant's own platform identity.
IDENTITY_WRITERS = [
    "tools/create_canary.py",
    "src/dashboard/views/credentials/_render.py",
]


def test_the_mirror_list_is_not_empty() -> None:
    """A vacuous mirror list would make every assertion below pass on nothing."""
    from src.utils.tenant_identity import IDENTITY_MIRRORS

    assert IDENTITY_MIRRORS, "no mirror declared — this guard would check nothing"
    assert IDENTITY_MIRRORS.get("spotify") == "spotify_artist_id"


def _calls(path: Path, func: str) -> bool:
    """Does this module CALL `func`? Importing it is not using it.

    The first version of this guard tested `func in text`, which the import line
    satisfied on its own: deleting the call left the test green. A guard that a
    mutation cannot turn red is decoration.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(
        isinstance(n, ast.Call)
        and (getattr(n.func, "id", None) == func
             or getattr(n.func, "attr", None) == func)
        for n in ast.walk(tree)
    )


@pytest.mark.parametrize("rel", IDENTITY_WRITERS)
def test_every_identity_writer_goes_through_the_shared_path(rel: str) -> None:
    assert _calls(ROOT / rel, "write_platform_identity"), (
        f"{rel} persists a tenant identity without CALLING the shared writer. It will "
        "miss the saas_artists mirror, exactly as create_canary.py did."
    )


@pytest.mark.parametrize("rel", IDENTITY_WRITERS)
def test_no_writer_inserts_into_credentials_behind_the_shared_path(rel: str) -> None:
    """The other half of the drift: a raw INSERT that bypasses the mirror entirely."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert "INSERT INTO artist_credentials" not in text, (
        f"{rel} writes artist_credentials directly. Every identity write goes through "
        "src.utils.tenant_identity.write_platform_identity, which also writes the "
        "saas_artists mirror."
    )


@pytest.mark.parametrize("rel", IDENTITY_WRITERS)
def test_no_writer_hand_rolls_the_mirror_update(rel: str) -> None:
    """The shape that drifted: a bare UPDATE of the mirror column, off on its own."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    hand_rolled = "UPDATE saas_artists SET spotify_artist_id"
    assert hand_rolled not in text, (
        f"{rel} writes the mirror by hand. Route it through "
        "src.utils.tenant_identity.write_platform_identity so a third writer cannot "
        "get it half right."
    )


def test_every_mirrored_column_exists_on_the_dag_read_path() -> None:
    """The mirror is only useful if the DAG really reads it — pin that it does."""
    from src.utils.tenant_identity import IDENTITY_MIRRORS

    dag = (ROOT / "airflow/dags/spotify_api_daily.py").read_text(encoding="utf-8")
    for column in IDENTITY_MIRRORS.values():
        assert f"SELECT {column} FROM saas_artists" in dag, (
            f"nothing reads saas_artists.{column} in spotify_api_daily any more — "
            "either the mirror is dead (drop it) or the DAG changed source."
        )


def test_write_platform_identity_refuses_an_unknown_platform() -> None:
    from src.utils.tenant_identity import write_platform_identity

    with pytest.raises(ValueError, match="unknown platform"):
        write_platform_identity(None, 1, "spotfy", {})


def test_the_shared_writer_is_syntactically_the_only_mirror_writer() -> None:
    """Sweep the whole tree, not just the two known writers."""
    offenders = []
    for path in list(ROOT.glob("src/**/*.py")) + list(ROOT.glob("tools/**/*.py")):
        if path.name == "tenant_identity.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "UPDATE saas_artists SET spotify_artist_id" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"mirror written outside the shared path: {offenders}"


def test_the_module_parses_and_exposes_its_contract() -> None:
    src = (ROOT / "src/utils/tenant_identity.py").read_text(encoding="utf-8")
    names = {n.name for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.FunctionDef)}
    assert {"write_platform_identity", "mirrored_columns"} <= names
