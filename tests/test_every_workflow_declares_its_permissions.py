"""Every workflow declares its token permissions, and writes only where it must (R623).

Type: Hook
Uses: .github/workflows/*.yml (parsed with yaml, never read as text)
Persists in: nothing

The repository's default workflow token is read-only today (`gh api
repos/…/actions/permissions/workflow` → `default_workflow_permissions: read`). That is a
SETTING: one click flips it to write-all for every workflow that names nothing. A
top-level `permissions:` block makes the file carry its own bound.

guard_scope: top-level and job-level `permissions` of every workflow, mapping and scalar
forms (`write-all`, `read-all`). NOT covered: a reusable workflow called with `uses:`
(none today), a step that reads a PAT from `secrets.*` instead of the job token.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
# (workflow, scope) pairs allowed to WRITE, each with its reason.
WRITE_ALLOWED = {
    ("dependabot-lock.yml", "contents"),  # pushes the regenerated uv.lock to the PR branch
    ("dependabot-lock.yml", "actions"),   # re-runs CI on that push
}


def _load(path: Path) -> dict:
    return yaml.safe_load(path.open(encoding="utf-8"))


def _blocks(doc: dict) -> list[tuple[str, object]]:
    out = [("top", doc.get("permissions"))]
    out += [(job, spec.get("permissions")) for job, spec in (doc.get("jobs") or {}).items()
            if isinstance(spec, dict) and "permissions" in spec]
    return out


def writes(name: str, doc: dict) -> set[tuple[str, str]]:
    """(where, scope) pairs this workflow grants WRITE on, outside the allowlist."""
    bad = set()
    for where, perms in _blocks(doc):
        if perms == "write-all":
            bad.add((where, "write-all"))
        elif isinstance(perms, dict):
            bad |= {(where, scope) for scope, level in perms.items()
                    if level == "write" and (name, scope) not in WRITE_ALLOWED}
    return bad


def test_there_are_workflows_to_check() -> None:
    assert len(WORKFLOWS) >= 6, [p.name for p in WORKFLOWS]


def test_every_workflow_has_a_top_level_permissions_block() -> None:
    missing = [p.name for p in WORKFLOWS if "permissions" not in _load(p)]
    assert not missing, ("no top-level `permissions:` — the token falls back to the repo "
                         f"setting: {missing}")


def test_no_workflow_writes_outside_the_allowlist() -> None:
    found = {p.name: sorted(writes(p.name, _load(p))) for p in WORKFLOWS}
    found = {k: v for k, v in found.items() if v}
    assert not found, f"write permission not in WRITE_ALLOWED (add it with its reason): {found}"


def test_the_allowlist_has_no_stale_entry() -> None:
    granted = set()
    for p in WORKFLOWS:
        for _, perms in _blocks(_load(p)):
            if isinstance(perms, dict):
                granted |= {(p.name, s) for s, lvl in perms.items() if lvl == "write"}
    assert not WRITE_ALLOWED - granted, f"stale: {sorted(WRITE_ALLOWED - granted)}"


def test_the_predicate_sees_each_write_form() -> None:
    assert writes("x.yml", {"permissions": "write-all", "jobs": {}}) == {("top", "write-all")}
    assert writes("x.yml", {"permissions": {"contents": "read"},
                            "jobs": {"j": {"permissions": {"issues": "write"}}}}) == {("j", "issues")}
    assert writes("x.yml", {"permissions": "read-all", "jobs": {}}) == set()
