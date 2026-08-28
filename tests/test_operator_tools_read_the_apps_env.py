""""It says env not set" is not a verdict — it means the probe looked somewhere else.

`tools/check_central_apps.py` is the command the runbook and the roadmap tell an
operator to run to prove the shared apps authenticate. Run from a shell that had
exported nothing, it printed `⚠️ env not set` for all four platforms and **exited 0**:
a check written to prove something reported success while seeing nothing.

Worse, it resolved a DIFFERENT environment from the one the app resolves, so it could
not have caught the defect it was aimed at. Measured 2026-08-22: `.env` already held
the correct app id and a valid System User token, while `.env.local` — which wins
locally by design — still held an AD ACCOUNT id in `META_APP_ID` and a token with one
stray pasted character. Everything Meta was broken locally and the probe said nothing.

Once wired, the same probe named the exact cause in one second.

Error class: env-resolved-against-cwd (this is its config-layer sibling).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Derived, not hand-listed: a tool a document tells an operator to run is a tool an
# operator will run from a bare shell. A new one is covered the day it is documented.
DOCS = (
    ".claude/dev-docs/roadmap/checklist.md",
    ".claude/dev-docs/runbook-actions-utilisateur.md",
    ".claude/dev-docs/error-classes.md",
    "CLAUDE.md",
)
# Tools that read no environment at all — they answer from files in the repo.
# Tools that genuinely read nothing from the environment. Each entry is a claim that
# has to stay true: `make_avatar_gif.py` derives every value from constants and from
# `src/dashboard/assets/logo_mark.svg`, and writes one GIF — there is no configuration
# for it to read the wrong copy of.
_NO_ENV = {"tools/dev/check_manifest_consistency.py", "tools/dev/graphify_render_html.py",
           "tools/dev/make_avatar_gif.py"}


def _documented_tools() -> list[str]:
    found: set[str] = set()
    for doc in DOCS:
        p = ROOT / doc
        if p.is_file():
            found |= set(re.findall(r"python3 (tools/[a-z0-9_/]+\.py)",
                                    p.read_text(encoding="utf-8")))
    return sorted(found)


def test_the_documented_tools_are_still_found() -> None:
    """If this list empties, every case below vacuously passes."""
    tools = _documented_tools()
    assert "tools/check_central_apps.py" in tools, (
        f"the probe is no longer named in any operator document; found {tools}"
    )


@pytest.mark.parametrize("tool", _documented_tools())
def test_an_operator_tool_resolves_the_environment_the_app_resolves(tool: str) -> None:
    if tool in _NO_ENV:
        pytest.skip(f"{tool} reads no environment")
    path = ROOT / tool
    assert path.is_file(), f"{tool} is documented but does not exist"

    tree = ast.parse(path.read_text(encoding="utf-8"))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "load_project_env" in called, (
        f"{tool} never calls load_project_env(). Run from a bare shell it reads a "
        "different environment from the dashboard and the DAGs — so it reports on a "
        "configuration nobody runs, and 'env not set' exits 0 as if all were well."
    )


def test_the_standalone_mailer_honours_the_same_env_precedence() -> None:
    """It cannot import the app package, so its order is restated — and restated drifts.

    `tools/notify_schema_drift.py` deliberately avoids importing the app (a broken
    import path must never be able to silence the drift alert), so it carries its own
    env loader. Read `.env` only, it answers from a file that is NOT the one the app
    resolves last — and the two disagreed for weeks.
    """
    from src.utils.env_files import ENV_FILES

    src = (ROOT / "tools/notify_schema_drift.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    declared = next(
        (tuple(e.value for e in n.value.elts)
         for n in ast.walk(tree)
         if isinstance(n, ast.Assign) and n.targets
         and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "_ENV_FILES"
         and isinstance(n.value, ast.Tuple)),
        None,
    )
    assert declared == tuple(ENV_FILES), (
        f"the standalone mailer reads {declared}, the app reads {tuple(ENV_FILES)}. "
        "First loaded wins, so a different order is a different configuration."
    )
