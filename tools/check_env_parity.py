#!/usr/bin/env python3
"""Are the central-app credentials actually PRESENT in the containers that read them?

Type: Utility
Uses: src.utils.central_apps._REQUIRED_ENV (derived, never restated)
Triggers: tools/deploy.sh (blocking), `make env-parity`
Depends on: docker
Persists in: nothing — reads presence only, never a value

Why this exists — measured twice.

2026-06-19, the first beta artist: every connection test failed, and the cause was not
a credential, it was a CONTAINER. `streamlytics_dashboard` had **no central-app env var
at all**. `os.getenv('X')` returns None when a variable is absent, so a container missing
one behaves exactly like a container holding an empty one: no exception, no log, no
difference at the call site. The declaration lives in `docker-compose.yml`, the read
lives in `src/`, and nothing joined the two. Class `env-not-wired-to-service`.

2026-08-23, the reason this is a SCRIPT and not another test: `make sync-check` compares
the schema, the migration ledger, the `tools/` mount, the Caddyfile and the git HEAD —
**zero environment variables** — and it cannot do better, because the production
`docker-compose.yml` is gitignored. No test can read both sides. `tools/prod_introspect.sh`
already measured this, correctly, and was wired to nothing.

Never prints a value. `SET(<length>)` is enough to tell "present" from "absent", which is
the only question here — a wrong value is `check_central_apps`'s job, not this one's.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.central_apps import _REQUIRED_ENV  # noqa: E402

# Which services read which platforms' credentials. Derived from what the code in each
# service actually imports: the Airflow services run the collectors, the dashboard runs
# the connection tests. `api` is deliberately absent — it touches neither today, and
# claiming otherwise would make this check fail on a truth.
_SERVICE_PLATFORMS = {
    "airflow_scheduler": tuple(_REQUIRED_ENV),
    "airflow_webserver": tuple(_REQUIRED_ENV),
    "streamlytics_dashboard": tuple(_REQUIRED_ENV),
}

# Read by more than the central apps, and just as fatal when missing.
#
# APP_BASE_URL added 2026-08-23, and its absence is exactly what this check exists to
# catch: it was set on the dashboard and ABSENT on the scheduler, so every onboarding
# report sent by Airflow carried a one-click unsubscribe link pointing at
# http://localhost:8501. The first version of this file did not list it — a parity check
# is only as wide as its list, which is the same failure mode as a guard's scope.
# ALERT_EMAIL likewise: the scheduler is where the nightly mail is decided.
_SERVICE_EXTRA = {
    # STREAMLYTICS_ENV ajouté le 2026-08-24, et son absence est PIRE que celle des
    # autres : sans elle, `instance_identity.instance_label()` rend `[LOCAL] ` et la
    # PRODUCTION préfixerait ses propres alertes comme si elles venaient d'un poste
    # de dev. Une variable dont l'absence retourne le sens du message doit être une
    # porte, pas une convention.
    # STREAMLYTICS_ALLOW_ARTIST_EMAIL added 2026-09-03, when the weekly recap became a
    # PAID feature. Its absence used to mean silence, and that was the right default
    # while nobody had decided to write to clients. It is no longer: a premium tenant
    # receiving nothing because a variable is missing is an incident, not prudence —
    # and `tools/deploy.sh` failing on this check imposes the right order, set the
    # variable, then deploy.
    "airflow_scheduler": ("FERNET_KEY", "APP_BASE_URL", "ALERT_EMAIL",
                          "STREAMLYTICS_ENV", "STREAMLYTICS_ALLOW_ARTIST_EMAIL",
                          "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"),
    "airflow_webserver": ("FERNET_KEY", "APP_BASE_URL"),
    "streamlytics_dashboard": ("FERNET_KEY", "APP_BASE_URL", "STREAMLYTICS_ENV",
                               "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"),
}

# These carry the ADMIN's own identity. Present-and-non-empty in a multi-tenant
# deployment is not a warning, it is the leak of 2026-08-20 re-armed: every collector
# would fall back on them and file one tenant's rows under another.
_MUST_BE_EMPTY = ("SPOTIFY_ARTIST_IDS", "META_AD_ACCOUNT_ID", "YOUTUBE_CHANNEL_ID",
                  "SOUNDCLOUD_USER_ID", "INSTAGRAM_USER_ID", "LEGACY_SINGLE_TENANT")


def _container_env(container: str) -> dict[str, str] | None:
    """`VAR -> value` inside a running container, or None if it is not running."""
    try:
        out = subprocess.run(["docker", "exec", container, "env"],
                             capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    env = {}
    for line in out.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            env[k] = v
    return env


def check(strict: bool = True) -> int:
    problems: list[str] = []
    checked = 0

    for container, platforms in _SERVICE_PLATFORMS.items():
        env = _container_env(container)
        if env is None:
            # Not running is not the same as misconfigured, and saying so keeps this
            # usable on a box where only some services are up.
            print(f"  ⏭ {container}: not running — skipped")
            continue
        checked += 1

        wanted: list[str] = []
        for platform in platforms:
            wanted.extend(_REQUIRED_ENV[platform])
        wanted.extend(_SERVICE_EXTRA.get(container, ()))

        for var in wanted:
            value = env.get(var, "")
            if value:
                print(f"  ✅ {container}: {var}=SET({len(value)})")
            else:
                state = "EMPTY" if var in env else "ABSENT"
                print(f"  ❌ {container}: {var}={state}")
                problems.append(f"{container} is missing {var}")

        for var in _MUST_BE_EMPTY:
            if env.get(var):
                print(f"  🚨 {container}: {var} is SET — this holds the ADMIN's identity")
                problems.append(
                    f"{container} has {var} set: every collector would fall back on the "
                    f"admin's identity and file one tenant's rows under another")

    if not checked:
        print("  ⚠️ no container was reachable — nothing was proven")
        return 1 if strict else 0

    if problems:
        print(f"\n❌ env parity: {len(problems)} problem(s)")
        for p in problems:
            print(f"   • {p}")
        print("\n   Fix on the box: edit /opt/streamlytics/.env, then")
        print("   docker compose up -d --force-recreate "
              "airflow-scheduler airflow-webserver dashboard api")
        print("   ⚠️ .env.local is NOT read by Docker Compose — only .env is.")
        return 1

    print(f"\n✅ env parity: {checked} container(s), every required variable present")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--warn-only", action="store_true",
                    help="report but always exit 0 (for a first run on a new box)")
    args = ap.parse_args()
    print("▶ env parity: are the central-app credentials in the containers that read them?")
    rc = check(strict=not args.warn_only)
    return 0 if args.warn_only else rc


if __name__ == "__main__":
    raise SystemExit(main())
