#!/usr/bin/env python3
"""Prove a NON-admin tenant can connect, collect and read its own data. READ-ONLY.

Type: Utility
Uses: check_central_apps, CONNECTION_TESTS (credentials registry), artist_readiness,
    tenant_contamination_check
Triggers: `make artist-preflight` — run it BEFORE inviting an artist to test
Persists in: nothing

Two artist test sessions burned an hour each discovering, live, that the shared
apps were misconfigured and that the data on screen was the admin's. Every one of
those failures was detectable beforehand. This chains the checks that already
existed but were never run together, against a real tenant, and stops at the
first red.

  1. central apps      — present AND authenticating (--require: absent is red)
  2. tenant identity   — the artist declared their own id on each platform
  3. connection tests  — the same probes the credentials form runs, per platform
  4. data landed       — artist_readiness: identity + freshness, per platform
  5. contamination     — no row under this tenant belongs to someone else

Exit 0 = you can invite someone. Exit 1 = a named thing to fix first.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_OK, _KO = "✅", "❌"


def _connect():
    from src.database.postgres_handler import PostgresHandler

    url = os.environ.get("DATABASE_URL")
    if url:
        return PostgresHandler.from_url(url)
    from src.utils.config_loader import config_loader
    cfg = config_loader.load()["database"]
    return PostgresHandler(host=cfg["host"], port=cfg["port"], database=cfg["database"],
                           user=cfg["user"], password=cfg["password"])


def _resolve_artist(db, artist_id: int | None) -> tuple[int, str]:
    """The tenant to prove. Defaults to the canary (migration 064's is_canary)."""
    if artist_id:
        rows = db.fetch_query(
            "SELECT id, name FROM saas_artists WHERE id = %s AND active = TRUE",
            (artist_id,))
        if not rows:
            raise SystemExit(f"{_KO} artist_id={artist_id} does not exist or is inactive")
        return rows[0][0], rows[0][1]
    rows = db.fetch_query(
        "SELECT id, name FROM saas_artists WHERE is_canary = TRUE AND active = TRUE "
        "ORDER BY id LIMIT 1")
    if not rows:
        raise SystemExit(
            f"{_KO} no canary tenant. Create one (a real, non-admin account whose "
            "platform identities are yours but DIFFERENT from the admin's), then:\n"
            "    UPDATE saas_artists SET is_canary = TRUE WHERE id = <id>;\n"
            "Or pass --artist <id> to prove a specific tenant."
        )
    return rows[0][0], rows[0][1]


def step_central_apps() -> bool:
    from tools.check_central_apps import (check_all_configured, check_meta,
                                          check_soundcloud, check_spotify, check_youtube)
    print("\n▶ 1. Central apps (shared, admin-owned)")
    results = [c() for c in (check_spotify, check_youtube, check_soundcloud, check_meta)]
    return check_all_configured() and all(results)


def _credentials(db, artist_id: int) -> dict:
    """{platform: {field: value}} — non-secret identity fields only (no Fernet)."""
    out: dict[str, dict] = {}
    for platform, extra in db.fetch_query(
            "SELECT platform, extra_config FROM artist_credentials WHERE artist_id = %s",
            (artist_id,)):
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except ValueError:
                extra = {}
        out[platform] = extra or {}
    return out


def step_identity(db, artist_id: int) -> bool:
    from src.utils.artist_readiness import _PLATFORMS, _identity

    print("\n▶ 2. Tenant identity (the artist's own ids, never the admin's)")
    creds = _credentials(db, artist_id)
    spotify_id = db.fetch_query(
        "SELECT spotify_artist_id FROM saas_artists WHERE id = %s", (artist_id,))[0][0]
    ok = True
    for platform in _PLATFORMS:
        present = _identity(platform["key"], creds, spotify_id)
        print(f"  {_OK if present else _KO} {platform['label']}"
              + ("" if present else f" — {platform['id_hint']}"))
        ok = ok and present
    return ok


def step_connection_tests(db, artist_id: int) -> bool:
    """Reuse the exact probes the credentials form runs — no second implementation."""
    from src.dashboard.views.credentials._registry import CONNECTION_TESTS

    print("\n▶ 3. Connection tests (per platform, as the artist sees them)")
    creds = _credentials(db, artist_id)
    ok = True
    for platform, test in CONNECTION_TESTS.items():
        fields = dict(creds.get(platform, {}))
        if platform == "spotify" and not fields.get("spotify_artist_id"):
            row = db.fetch_query(
                "SELECT spotify_artist_id FROM saas_artists WHERE id = %s", (artist_id,))
            fields["spotify_artist_id"] = row[0][0] if row else ""
        try:
            passed, message = test(fields)
        except Exception as exc:  # noqa: BLE001 — a probe error is a red, not a crash
            passed, message = False, str(exc)
        print(f"  {_OK if passed else _KO} {platform}: {message.splitlines()[0][:140]}")
        ok = ok and passed
    return ok


def step_data_landed(db, artist_id: int) -> bool:
    from src.utils.artist_readiness import OK, artist_readiness

    print("\n▶ 4. Data actually landed for this tenant")
    ok = True
    for row in artist_readiness(db, artist_id):
        good = row["status"] == OK
        print(f"  {row['icon']} {row['label']} — {row['status_label']}"
              + (f" · {row['next_action']}" if row["next_action"] else ""))
        ok = ok and good
    return ok


def step_contamination(db, artist_id: int) -> bool:
    from tools.tenant_contamination_check import scan

    print("\n▶ 5. No other tenant's rows under this account")
    findings = [f for f in scan(db) if f["artist_id"] == artist_id]
    for f in findings:
        print(f"  {_KO} [{f['kind']}] {f['table']} — {f['rows']} rows: {f['detail']}")
    if not findings:
        print(f"  {_OK} clean")
    return not findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artist", type=int, default=None,
                        help="tenant to prove (default: the canary tenant)")
    parser.add_argument("--skip-data", action="store_true",
                        help="skip steps 4-5 (identity/connection only — useful right "
                             "after connecting, before the first collection ran)")
    args = parser.parse_args()

    try:
        db = _connect()
    except Exception as exc:  # noqa: BLE001
        print(f"{_KO} cannot connect to the database: {exc}", file=sys.stderr)
        return 2

    try:
        artist_id, name = _resolve_artist(db, args.artist)
        print(f"Pre-flight for tenant {artist_id} — {name}")

        steps = [
            ("central apps", step_central_apps),
            ("tenant identity", lambda: step_identity(db, artist_id)),
            ("connection tests", lambda: step_connection_tests(db, artist_id)),
        ]
        if not args.skip_data:
            steps += [
                ("data landed", lambda: step_data_landed(db, artist_id)),
                ("contamination", lambda: step_contamination(db, artist_id)),
            ]

        for label, step in steps:
            if not step():
                print(f"\n{_KO} STOP — «{label}» is red. Fix it before inviting an "
                      "artist; everything after it is untested.")
                return 1
    finally:
        db.close()

    print(f"\n{_OK} Pre-flight green — a non-admin tenant connects, collects and reads "
          "its own data. You can invite an artist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
