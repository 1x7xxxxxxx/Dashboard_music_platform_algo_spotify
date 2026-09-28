"""Every long-running compose service declares `mem_limit` (R266, ADR-030).

Before R266 no container had a limit: one runaway scheduler task could take the whole
box — Postgres, the API and the dashboards with it — and the OOM killer chose the
victim. Each limit was measured in production (peak over the running containers,
2026-09-28) and set at about twice it, the scheduler at 1.7x.

Exempt: one-shot services (`restart: "no"` or no restart policy AND a command that
exits — `airflow-init`), which are not running when the box is under load.
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPOSES = ("docker-compose.example.yml", "deploy/docker-compose.observability.yml",
            "deploy/docker-compose.replica.yml")
ONE_SHOT = frozenset({"airflow-init"})


class _Loader(yaml.SafeLoader):
    """Reads Compose tags (`!override`, `!reset`) as plain values."""


_Loader.add_multi_constructor("!", lambda loader, suffix, node: (
    loader.construct_sequence(node) if isinstance(node, yaml.SequenceNode)
    else loader.construct_mapping(node) if isinstance(node, yaml.MappingNode)
    else loader.construct_scalar(node)))


def _missing(services: dict) -> list[str]:
    return sorted(name for name, spec in services.items()
                  if name not in ONE_SHOT and not (spec or {}).get("mem_limit")
                  and "extends" not in (spec or {}))


def test_every_long_running_service_has_a_memory_limit():
    missing = []
    for rel in COMPOSES:
        services = yaml.load((ROOT / rel).read_text(encoding="utf-8"), Loader=_Loader)["services"]
        missing += [f"{rel}:{name}" for name in _missing(services)]
    assert not missing, f"services without mem_limit (R266, ADR-030): {missing}"


def test_the_detector_sees_a_service_without_a_limit():
    """Non-vacuity: the exact defect is seen, the corrected form is not."""
    assert _missing({"api": {"image": "x"}}) == ["api"]
    assert _missing({"api": {"image": "x", "mem_limit": "400m"}}) == []
    assert _missing({"airflow-init": {"image": "x"}}) == []
