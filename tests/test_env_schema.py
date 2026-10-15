"""The env schema covers every key the code reads, and gates each service's start (R619).

Type: Hook
Uses: src/utils/env_schema.py, docker-compose.example.yml
Persists in: nothing

Two directions, both strict:
* every key read by `os.getenv`/`os.environ` (literal, or through a module constant) in
  src/ and airflow/dags/ is classified — in SCHEMA or UNVALIDATED, never both, never a
  stale entry; every NON-literal read is listed, with its reason, in NONLITERAL_READS;
* the example compose declares, for each gated service, the required keys its import
  graph reaches — the gap measured on prod on 2026-10-15 (dashboard without ALERT_EMAIL,
  api without STREAMLYTICS_ENV) is the reason.

guard_scope: `os.getenv(K)`, `os.environ.get(K)`, `os.environ[K]` with K a literal or a
module-level `NAME = "…"`. NOT covered: `getenv` imported bare (`from os import getenv`),
keys read by a third-party library (Airflow's own `AIRFLOW__*`), shell scripts.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from src.utils import env_schema as es

ROOT = Path(__file__).resolve().parents[1]


def _tracked_python() -> list[str]:
    out = subprocess.run(["git", "ls-files", "src/*.py", "airflow/dags/*.py"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
    return [f for f in out if (ROOT / f).is_file()]


def _all_reads() -> tuple[set[str], set[str]]:
    keys, nonliteral = set(), set()
    for f in _tracked_python():
        k, n = es.reads((ROOT / f).read_text(encoding="utf-8"))
        keys |= k
        nonliteral |= {f"{f}:{e}" for e in n}
    return keys, nonliteral


def test_every_read_key_is_classified_and_nothing_is_stale() -> None:
    keys, _ = _all_reads()
    known = set(es.SCHEMA) | es.UNVALIDATED
    assert not set(es.SCHEMA) & es.UNVALIDATED, "a key is both validated and not"
    assert not keys - known, f"read but unclassified — add to SCHEMA or UNVALIDATED: {sorted(keys - known)}"
    assert not known - keys, f"classified but no longer read — remove: {sorted(known - keys)}"


def test_every_nonliteral_read_is_explained() -> None:
    _, nonliteral = _all_reads()
    listed = set(es.NONLITERAL_READS)
    assert not nonliteral - listed, f"unexplained non-literal env reads: {sorted(nonliteral - listed)}"
    assert not listed - nonliteral, f"stale NONLITERAL_READS: {sorted(listed - nonliteral)}"


def test_the_reach_finds_the_keys_measured_on_2026_10_15() -> None:
    """Hard-coded on purpose: the guard does not read the set it checks."""
    assert {"API_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "DATABASE_URL",
            "STREAMLYTICS_ENV"} <= es.required_for("api")
    assert {"FERNET_KEY", "ALERT_EMAIL", "SMTP_HOST", "APP_BASE_URL"} <= es.required_for("dashboard")
    assert {"META_APP_ID", "META_APP_SECRET"} <= es.required_for("airflow-scheduler")
    assert "API_SECRET_KEY" not in es.required_for("dashboard")


# ── the gate, on fixtures ─────────────────────────────────────────────────────────────

def _tree(tmp_path: Path, body: str) -> Path:
    (tmp_path / "src" / "api").mkdir(parents=True)
    (tmp_path / "src" / "api" / "main.py").write_text("import os\n" + body)
    return tmp_path


def test_a_missing_required_key_is_named_never_its_neighbours(tmp_path: Path) -> None:
    root = _tree(tmp_path, "os.getenv('API_SECRET_KEY')\n")
    assert es.problems("api", env={}, config=dict, root=root) == ["API_SECRET_KEY is absent"]
    assert es.problems("api", env={"API_SECRET_KEY": "x" * 32}, config=dict, root=root) == []


def test_a_key_the_service_does_not_read_is_not_required(tmp_path: Path) -> None:
    root = _tree(tmp_path, "os.getenv('PORT')\n")
    assert es.problems("api", env={}, config=dict, root=root) == []


def test_alternatives_and_config_satisfy_a_key(tmp_path: Path) -> None:
    root = _tree(tmp_path, "os.getenv('DATABASE_URL')\nos.getenv('FERNET_KEY')\n")
    env = {"DATABASE_HOST": "db"}
    assert es.problems("api", env=env, config=lambda: {"fernet_key": "k"}, root=root) == []
    assert es.problems("api", env=env, config=dict, root=root) == [
        "FERNET_KEY is absent (nor config.yaml `fernet_key`)"]


def test_a_mistyped_value_is_named_without_its_value(tmp_path: Path) -> None:
    root = _tree(tmp_path, "os.getenv('SMTP_PORT')\nos.getenv('API_BASE_URL')\n"
                           "os.getenv('API_SECRET_KEY')\n")
    secret = "short-secret-value"  # pragma: allowlist secret
    found = es.problems("api", env={"SMTP_PORT": "abc", "API_BASE_URL": "nohost",
                                    "API_SECRET_KEY": secret}, config=dict, root=root)
    assert [p.split()[0] for p in found] == ["API_BASE_URL", "API_SECRET_KEY", "SMTP_PORT"]
    assert not any(secret in p or "abc" in p or "nohost" in p for p in found)


def test_main_refuses_only_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(es, "problems", lambda service: ["X is absent"])
    monkeypatch.setenv("STREAMLYTICS_ENV", "production")
    assert es.main(["api"]) == 1
    monkeypatch.setenv("STREAMLYTICS_ENV", "local")
    assert es.main(["api"]) == 0
    assert es.main(["nope"]) == 2


# ── the example compose declares what each gated service needs ───────────────────────

@pytest.mark.parametrize("service", ["dashboard", "api", "airflow-scheduler"])
def test_the_example_compose_declares_what_the_service_reads(service: str) -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.example.yml").read_text(encoding="utf-8"))
    env = compose["services"][service].get("environment") or {}
    declared = set(env) if isinstance(env, dict) else {e.split("=")[0] for e in env}
    missing = {k for k in es.required_for(service)
               if k not in declared and not set(es.SCHEMA[k].alternatives) & declared}
    assert not missing, f"{service}: required by its code, absent from the example: {sorted(missing)}"
