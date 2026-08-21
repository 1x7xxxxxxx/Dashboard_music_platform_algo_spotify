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

# A shell has no .env; Docker does. Resolve it from the repo root so this tool is
# correct from any cwd, and so a red verdict below means "missing", not "unloaded".
from src.utils.env_files import load_project_env  # noqa: E402

load_project_env()

_OK, _KO = "✅", "❌"


def _connect():
    """The one resolution (R33): DATABASE_URL → DATABASE_* → config.yaml.

    This used to read DATABASE_URL then config.yaml only, skipping the env vars —
    which is exactly how Airflow is configured. So the tool worked from a dev
    machine and not from the container where the collectors run.
    """
    from src.database.postgres_handler import PostgresHandler

    return PostgresHandler.from_env_or_config()


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
            f"{_KO} no canary tenant — one command away:\n\n"
            '    make canary NAME="Canary <toi>" SPOTIFY=<artist id> YOUTUBE=<UC…>\n\n'
            "Use YOUR OWN public profiles, and ones the admin does not already\n"
            "declare — a canary that borrows the admin's identity passes while the\n"
            "isolation it exists to test is broken. The tool refuses that, and\n"
            "refuses an identity another tenant already claims.\n"
            "Add --dry-run (DRY_RUN=1) to see what it would do first.\n\n"
            "Or pass --artist <id> to prove a specific existing tenant."
        )
    return rows[0][0], rows[0][1]


def step_central_apps(scope: set[str] | None = None) -> bool:
    """Every shared app is CHECKED and printed; only the in-scope ones gate.

    `check_meta` became fatal on a malformed token (2026-08-21) — correctly, it is
    the one Meta check that can be conclusive. But without a scope that made an
    unrelated platform's broken token block the canary's verification entirely, at
    step 1, before anything about the tenant was even looked at. A gate must fail
    on what it was asked to prove, not on its neighbours.
    """
    from src.utils.central_apps import missing_central_env
    from tools.check_central_apps import (check_meta, check_soundcloud,
                                          check_spotify, check_youtube)
    print("\n▶ 1. Central apps (shared, admin-owned)")
    checks = {"spotify": check_spotify, "youtube": check_youtube,
              "soundcloud": check_soundcloud, "meta": check_meta}
    gating = True
    for key, check in checks.items():
        ok = check()
        if scope is not None and key not in scope:
            if not ok:
                print(f"   ↑ {key} is red but out of scope (--platforms) — not gating.")
            continue
        gating = gating and ok
    # Absence is NARROWED to the scope, not skipped. It used to gate only an
    # unrestricted run — and the standing production verification is documented as
    # `--platforms youtube`, so the absence check never ran where it mattered most.
    # A scoped run must still prove that what it claims to prove is configured.
    missing = missing_central_env(scope)
    for platform, variables in missing.items():
        print(f"  {_KO} {platform}: central app NOT configured — "
              f"missing {', '.join(variables)}")
    return not missing and gating


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


def step_identity(db, artist_id: int, scope: set[str] | None = None) -> bool:
    """Red unless every IN-SCOPE platform declares the tenant's own id.

    `scope` exists for one honest case: the canary tenant cannot declare Meta or
    Instagram — both demand real ownership of an ad account. Without a scope the
    bar stays "every platform", so a green here keeps meaning "fully proven".
    Out-of-scope platforms are printed as skipped, never as passed: a reader must
    not be able to mistake a partial run for a complete one.
    """
    from src.utils.artist_readiness import _PLATFORMS, _identity

    print("\n▶ 2. Tenant identity (the artist's own ids, never the admin's)")
    creds = _credentials(db, artist_id)
    spotify_id = db.fetch_query(
        "SELECT spotify_artist_id FROM saas_artists WHERE id = %s", (artist_id,))[0][0]
    ok = True
    for platform in _PLATFORMS:
        if scope is not None and platform["key"] not in scope:
            print(f"  ⏭ {platform['label']} — out of scope (--platforms)")
            continue
        present = _identity(platform["key"], creds, spotify_id)
        print(f"  {_OK if present else _KO} {platform['label']}"
              + ("" if present else f" — {platform['id_hint']}"))
        ok = ok and present
    return ok


def step_connection_tests(db, artist_id: int, scope: set[str] | None = None) -> bool:
    """Reuse the exact probes the credentials form runs — no second implementation."""
    from src.dashboard.views.credentials._registry import CONNECTION_TESTS
    from src.utils.tenant_identity import storage_platform

    print("\n▶ 3. Connection tests (per platform, as the artist sees them)")
    creds = _credentials(db, artist_id)
    ok = True
    for platform, test in CONNECTION_TESTS.items():
        if scope is not None and platform not in scope:
            print(f"  ⏭ {platform} — out of scope (--platforms)")
            continue
        # STORAGE row, not the logical name: Instagram's id lives in the `meta` row,
        # so `creds.get('instagram')` would be empty for every tenant and the probe
        # would report a missing identity for one that is correctly declared.
        fields = dict(creds.get(storage_platform(platform), {}))
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


def step_data_landed(db, artist_id: int, scope: set[str] | None = None) -> bool:
    """Every platform is PRINTED; only the in-scope ones decide the verdict.

    Printing all of them is deliberate: a reader must see what was left out, or a
    scoped green reads as full coverage. Steps 2 and 3 honoured the scope while this
    one did not, which made a --platforms run stop on a platform it had been told to
    ignore (2026-08-21).
    """
    from src.utils.artist_readiness import OK, QUIET, artist_readiness

    print("\n▶ 4. Data actually landed for this tenant")
    ok = True
    for row in artist_readiness(db, artist_id):
        # QUIET counts as good: the source has a MEASURED reason to have nothing
        # (no ACTIVE ad campaign). Failing on it would make the preflight red for a
        # tenant who did everything right, and a gate that cries wolf gets skipped.
        # The label is printed either way, so a reader can challenge the reason.
        good = row["status"] in (OK, QUIET)
        counts = scope is None or row["key"] in scope
        print(f"  {row['icon']} {row['label']} — {row['status_label']}"
              + (f" · {row['next_action']}" if row["next_action"] else "")
              + ("" if counts else "   [out of scope]"))
        ok = ok and (good or not counts)
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
    parser.add_argument("--platforms", default=None,
                        help="comma-separated platforms to prove (default: all). Use it "
                             "for the canary, which cannot own a Meta ad account. A "
                             "restricted run is labelled as such in the verdict.")
    parser.add_argument("--skip-data", action="store_true",
                        help="skip steps 4-5 (identity/connection only — useful right "
                             "after connecting, before the first collection ran)")
    args = parser.parse_args()

    scope = None
    if args.platforms:
        from src.utils.artist_readiness import _PLATFORMS

        known = {p["key"] for p in _PLATFORMS}
        scope = {s.strip() for s in args.platforms.split(",") if s.strip()}
        # A typo must not silently empty the scope and turn the run green. This is
        # the whole risk of adding a scope flag to a gate: it can only ever narrow.
        unknown = scope - known
        if unknown:
            print(f"{_KO} unknown platform(s): {', '.join(sorted(unknown))}. "
                  f"Known: {', '.join(sorted(known))}", file=sys.stderr)
            return 2
        if not scope:
            print(f"{_KO} --platforms was empty", file=sys.stderr)
            return 2

    try:
        db = _connect()
    except Exception as exc:  # noqa: BLE001
        print(f"{_KO} cannot connect to the database: {exc}", file=sys.stderr)
        return 2

    try:
        artist_id, name = _resolve_artist(db, args.artist)
        print(f"Pre-flight for tenant {artist_id} — {name}")

        steps = [
            ("central apps", lambda: step_central_apps(scope)),
            ("tenant identity", lambda: step_identity(db, artist_id, scope)),
            ("connection tests", lambda: step_connection_tests(db, artist_id, scope)),
        ]
        if not args.skip_data:
            steps += [
                ("data landed", lambda: step_data_landed(db, artist_id, scope)),
                ("contamination", lambda: step_contamination(db, artist_id)),
            ]

        for label, step in steps:
            if not step():
                print(f"\n{_KO} STOP — «{label}» is red. Fix it before inviting an "
                      "artist; everything after it is untested.")
                return 1
    finally:
        db.close()

    if scope:
        print(f"\n{_OK} Pre-flight green FOR {', '.join(sorted(scope))} ONLY — the other "
              "platforms were not proven. Do not read this as ready-to-invite unless the "
              "artist connects exactly these.")
    else:
        print(f"\n{_OK} Pre-flight green — a non-admin tenant connects, collects and reads "
              "its own data. You can invite an artist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
