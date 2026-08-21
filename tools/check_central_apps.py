#!/usr/bin/env python3
"""Authenticate each SHARED central app from env — catch expiry before a tenant does.

Type: Utility
Uses: requests (direct platform auth endpoints), env vars (central credential model, ADR-006)
Triggers: manual / CI run — `python3 tools/check_central_apps.py`
Note: the probes themselves live in `src/utils/central_apps.py` — `tools/` is not
    importable inside the Airflow containers, and `alert_monitor` needs them nightly.

streaMLytics uses ONE admin-owned app per platform (ADR-006). An expired or
misconfigured central app blanks EVERY tenant at once. This probe authenticates
each configured central app directly so the failure is caught here, loudly,
instead of surfacing as "0 rows" per tenant. A platform whose env vars are
absent is skipped (not a failure); a CONFIGURED app that fails auth exits 1.
"""
import argparse
import os
import sys



sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.central_apps import (  # noqa: E402 — after the sys.path insert
    check_all_configured, check_meta, check_soundcloud,
    check_spotify, check_youtube,
)
from src.utils.env_files import (  # noqa: E402 — after the sys.path insert
    describe_env_source, load_project_env,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require", action="store_true",
        help="treat an absent central app as a failure (pre-flight before inviting "
             "an artist), instead of skipping it",
    )
    args = parser.parse_args()

    # Resolve the environment the APP resolves — root-anchored, `.env.local` first.
    # Run from a shell that exported nothing, this probe used to print "env not set"
    # for all four platforms and exit 0: the check written to prove the shared apps
    # work reported success while seeing nothing at all. Worse, it read a DIFFERENT
    # environment from the one the dashboard and the DAGs read, so it could not have
    # caught the defect it was pointed at — `.env.local` held an ad-account id in
    # META_APP_ID and a malformed token, and won locally over an already-correct
    # `.env` (measured 2026-08-22). Error class: env-resolved-against-cwd.
    loaded = load_project_env()
    print(f"env: {describe_env_source()}"
          + (f" — loaded {', '.join(loaded)}" if loaded else ""))

    checks = (check_spotify, check_youtube, check_soundcloud, check_meta)
    # A skipped (env-absent) platform returns True; only a configured failure → False.
    # Evaluated eagerly: every platform is reported, not just the first failure.
    results = [check() for check in checks]
    ok = all(results)
    if args.require:
        ok = check_all_configured() and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
