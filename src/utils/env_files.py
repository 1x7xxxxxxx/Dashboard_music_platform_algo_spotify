"""Load the project's .env files from the REPOSITORY ROOT, never from the cwd.

Type: Utility
Uses: python-dotenv
Triggers: called by every shell entrypoint (tools/*, dashboard app) at startup
Depends on: .env.local / .env at the repository root
Persists in: os.environ (process-local)

Why this exists — two failures, one class:

1. `make artist-preflight` reported "Spotify central app NOT configured" for
   credentials that were configured, just not in that shell. A red that names the
   wrong cause sends you fixing the wrong thing.
2. `src/dashboard/app.py` tested `os.path.exists('.env.local')` relative to the
   CWD, while the documented launch is `cd src/dashboard && streamlit run app.py`.
   `load_dotenv` then returned False -- silently. Measured 2026-08-21.

Both come from resolving the env file against the caller's cwd. This resolves it
against this file's location instead, so it is correct from any directory.

Precedence, deliberately: an ALREADY-INJECTED variable always wins. Airflow and
Docker inject the real environment; a stale .env in the image must never override
it. Locally, `.env.local` wins over `.env` because it is loaded first and
python-dotenv does not overwrite what is already set.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Order matters: first loaded wins (override=False), so the local file is first.
ENV_FILES = (".env.local", ".env")


def load_project_env(override: bool = False) -> list[str]:
    """Load root-anchored .env files into os.environ. Returns the names loaded.

    Never raises: inside the Airflow containers `.env` is mounted root-owned 600
    and unreadable by the airflow uid, where the environment is injected anyway.
    """
    loaded: list[str] = []
    for name in ENV_FILES:
        path = PROJECT_ROOT / name
        if not path.is_file():
            continue
        try:
            from dotenv import load_dotenv

            load_dotenv(path, override=override)
        except (PermissionError, OSError) as e:
            logger.debug("%s not readable (%s); relying on the injected environment.", name, e)
            continue
        loaded.append(name)
    return loaded


def describe_env_source() -> str:
    """One line naming what was loaded -- so a red verdict can say WHERE it looked."""
    present = [n for n in ENV_FILES if (PROJECT_ROOT / n).is_file()]
    if not present:
        return f"no .env file at {PROJECT_ROOT} -- using the injected environment only"
    return f"{', '.join(present)} at {PROJECT_ROOT}"
