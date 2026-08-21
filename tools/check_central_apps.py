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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require", action="store_true",
        help="treat an absent central app as a failure (pre-flight before inviting "
             "an artist), instead of skipping it",
    )
    args = parser.parse_args()

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
