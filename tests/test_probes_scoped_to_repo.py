"""Health probes must observe THIS repo, not the machine they run on.

Installed 2026-08-21 (roadmap R36). Two probes shipped with the baseline payload
enumerated every container running on the host:

- `session_summary.check_docker_health()` warned about `msdr_api`,
  `msdr_dashboard`, `msdr_receiver` — a hardcoded list from the repo the payload
  was cut from. It had never once observed this project. Worse than useless: the
  neighbouring project's containers *were* running on this machine, so the probe
  read green while this repo's Postgres was down.
- `check_env.check_docker_tz_utc()` iterated `docker ps` unfiltered and told the
  user to add `TZ=UTC` to the environment block of `n8n-ollama` and
  `n8n-postgres`, containers belonging to a project that is not this one.

The class is `probe-scoped-to-the-machine-not-the-repo`. The fix both probes now
share: derive the expected set from the `container_name:` entries this repo's own
compose file declares.

This file is the guard. It was verified red against the pre-fix versions of both
modules and green after.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest


def _repo_root() -> Path:
    for d in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ found above this test")


REPO = _repo_root()
HOOKS = REPO / ".claude" / "hooks"
SCRIPTS = REPO / ".claude" / "scripts"


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _compose_container_names() -> set[str]:
    names: set[str] = set()
    for name in ("docker-compose.yml", "docker-compose.example.yml"):
        f = REPO / name
        if f.is_file():
            names.update(
                re.findall(r"^\s*container_name:\s*([A-Za-z0-9_.-]+)",
                           f.read_text(encoding="utf-8"), re.M)
            )
    return names


def test_this_repo_declares_container_names():
    """Everything below is vacuous if compose declares nothing."""
    assert _compose_container_names(), (
        "no `container_name:` in any compose file — the two probes below would "
        "silently fall back to observing every container on the machine."
    )


def test_session_summary_expects_only_this_repos_containers(monkeypatch):
    mod = _load(HOOKS / "session_summary.py")
    monkeypatch.chdir(REPO)
    expected = set(mod._expected_containers(str(REPO)))

    assert expected, "check_docker_health() has no expected set — it observes nothing"
    unknown = expected - _compose_container_names()
    assert not unknown, (
        f"expects container(s) this repo does not declare: {sorted(unknown)}. "
        "A name from another project reads as coverage that does not exist — and "
        "can read green because that project happens to be running."
    )


def test_check_env_scopes_the_tz_probe_to_this_repo(monkeypatch):
    monkeypatch.chdir(REPO)
    mod = _load(SCRIPTS / "check_env.py")
    declared = set(mod._declared_container_names())

    assert declared, (
        "check_docker_tz_utc() has nothing to filter on — it would inspect every "
        "container on the host, including other projects'."
    )
    unknown = declared - _compose_container_names()
    assert not unknown, f"not declared by this repo's compose: {sorted(unknown)}"


@pytest.mark.parametrize(
    "path",
    [HOOKS / "session_summary.py", SCRIPTS / "check_env.py"],
    ids=lambda p: p.name,
)
def test_no_foreign_project_container_names_hardcoded(path: Path):
    """The concrete regression: a literal container tuple from another repo."""
    text = path.read_text(encoding="utf-8")
    body = "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("#")
    )
    for needle in ("msdr_api", "msdr_dashboard", "msdr_receiver"):
        assert needle not in body, (
            f"{path.name} hardcodes {needle!r} — a container name from the repo "
            "this payload was cut from."
        )


def test_observation_stream_is_not_namespaced_by_another_project():
    """Writer and readers of the observation stream must agree on the directory.

    Sibling of the same class. `observe.py` wrote to `homunculus/msdr/` while
    `draft_devlog.py` read `homunculus/<project>/`: the DEVLOG drafter had been
    reading a file frozen since 2026-07-28, which is why `pending-devlog.md` sat
    stale with unfilled `?` fields.
    """
    literal = re.compile(
        r'"homunculus"\s*/\s*"[A-Za-z0-9_]+"|homunculus/[A-Za-z0-9_]+/'
    )
    offenders = []
    for py in sorted(HOOKS.glob("*.py")) + sorted(SCRIPTS.glob("*.py")):
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if literal.search(line):
                offenders.append(f"{py.relative_to(REPO)}:{i}: {line.strip()}")
    assert not offenders, (
        "a literal directory name under .claude/homunculus/ — derive it from the "
        "repo (`repo_root.name`) so writer and readers cannot diverge:\n  "
        + "\n  ".join(offenders)
    )
