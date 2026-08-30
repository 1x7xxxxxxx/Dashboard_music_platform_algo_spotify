#!/usr/bin/env python3
"""Provision (or reset) a sandbox tenant: rehearse the onboarding with real credentials.

Type: Utility
Uses: PostgresHandler, auth.hash_password, register._grant_welcome_trial
Triggers: `make artist-sandbox`
Depends on: saas_artists.is_sandbox (migration 080)
Persists in: saas_artists, saas_users, artist_credentials

The problem it solves
---------------------
To check that your OWN platform credentials work, you have to walk the onboarding from
zero and type them in. But a platform identity belongs to exactly one tenant, and yours
already belongs to your real account — so the uniqueness guard refuses, correctly.

Disabling that guard "temporarily" is the wrong shape: it is the guard that closed the
tenant leak two beta sessions were spent on, and a duplicate claim, once written, is
invisible. Migration 080 adds the third kind of tenant instead — a sandbox, exempt from
the guard in both directions, excluded from public counters and onboarding alerts, and
collecting for real (otherwise it would prove nothing).

Replaying from zero
-------------------
`--reset` is the part that makes this usable more than once: it drops the sandbox's
credentials and its collected rows, so the next login starts on the empty onboarding
again — same tenant, same login, nothing carried over.
"""
from __future__ import annotations

import argparse
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


_OK, _KO = "✅", "❌"

# Tables holding per-tenant collected rows, wiped by --reset. `artist_id` is the
# TENANT here; tables where that column is a Spotify id (artists, tracks,
# artist_history) are deliberately absent — see .claude/rules/python.md.
_TENANT_DATA_TABLES = (
    "artist_credentials",
    "s4a_song_timeline",
    "youtube_videos",
    "youtube_channels",
    "youtube_video_stats",
    "etl_run_log",
)


def _db():
    # `from_env_or_config`, comme tools/create_canary.py : le constructeur nu exige
    # cinq arguments et cet outil tourne aussi bien depuis WSL que dans un conteneur.
    from src.database.postgres_handler import PostgresHandler

    return PostgresHandler.from_env_or_config()


def _existing(db, slug: str):
    return db.fetch_query(
        "SELECT id, COALESCE(is_sandbox, FALSE) FROM saas_artists WHERE slug = %s",
        (slug,))


def _wipe(db, artist_id: int) -> None:
    # Les identités passent par la porte partagée : une identité vit dans DEUX
    # endroits (la ligne de credentials et sa colonne miroir), et en oublier un
    # laisse un locataire sans credential qui répond quand même avec un identifiant
    # miroité — donc qui continue de collecter sous une identité qu'on croit retirée.
    from src.utils.tenant_identity import clear_platform_identities

    clear_platform_identities(db, artist_id)
    print(f"   {_OK} identités effacées (credentials + colonnes miroir)")

    for table in _TENANT_DATA_TABLES:
        if table == "artist_credentials":
            continue                      # déjà traité par la porte partagée
        try:
            db.execute_query(f"DELETE FROM {table} WHERE artist_id = %s", (artist_id,))
        except Exception as exc:            # noqa: BLE001 — a missing table is not fatal
            print(f"   ⚠️  {table}: {type(exc).__name__}")
            continue
        print(f"   {_OK} {table} vidée")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slug", default="sandbox", help="slug du locataire (défaut: sandbox)")
    ap.add_argument("--name", default="Bac à sable", help="nom affiché")
    ap.add_argument("--email", help="e-mail de connexion (défaut: <slug>@sandbox.local)")
    ap.add_argument("--reset", action="store_true",
                    help="vide identifiants et données collectées, garde le compte")
    ap.add_argument("--delete", action="store_true", help="supprime le locataire et son compte")
    ap.add_argument("--dry-run", action="store_true")
    args, unknown = ap.parse_known_args()
    if unknown:
        # `tools/migrate.sh --dry-run` a déjà appliqué pour de vrai parce qu'un argument
        # inconnu était ignoré en silence. Un outil qui écrit en base ne devine pas.
        print(f"{_KO} argument(s) inconnu(s) : {unknown}")
        return 2

    slug = args.slug.strip().lower()
    email = args.email or f"{slug}@sandbox.local"
    db = _db()
    try:
        rows = _existing(db, slug)

        if args.delete:
            if not rows:
                print(f"{_OK} rien à supprimer (slug={slug!r} inconnu)")
                return 0
            artist_id, is_sandbox = rows[0]
            if not is_sandbox:
                print(f"{_KO} l'artiste {artist_id} n'est PAS un bac à sable — refus. "
                      "Cet outil ne supprime que ce qu'il a créé.")
                return 1
            if args.dry_run:
                print(f"{_OK} dry-run : supprimerait le bac à sable {artist_id}")
                return 0
            _wipe(db, artist_id)
            db.execute_query("DELETE FROM saas_users WHERE artist_id = %s", (artist_id,))
            db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
            print(f"{_OK} bac à sable {artist_id} supprimé")
            return 0

        if rows and not rows[0][1]:
            print(f"{_KO} le slug {slug!r} existe déjà et n'est PAS un bac à sable "
                  f"(artist_id={rows[0][0]}). Choisis un autre --slug : cet outil ne "
                  "convertit pas un locataire réel.")
            return 1

        if args.dry_run:
            verb = "réinitialiserait" if rows else "créerait"
            print(f"{_OK} dry-run : {verb} le bac à sable slug={slug!r}, login {email}")
            return 0

        if rows:
            artist_id = rows[0][0]
            if args.reset:
                print(f"▶ réinitialisation du bac à sable {artist_id}")
                _wipe(db, artist_id)
        else:
            artist_id = db.fetch_query(
                "INSERT INTO saas_artists (name, slug, tier, active, is_sandbox) "
                "VALUES (%s, %s, 'free', TRUE, TRUE) RETURNING id",
                (args.name, slug))[0][0]
            print(f"{_OK} bac à sable créé — artist_id={artist_id}")

        # Le compte de connexion. Mot de passe régénéré à chaque passage : il n'est
        # affiché qu'ici, et un bac à sable n'a pas de secret à conserver.
        from src.dashboard.auth import hash_password
        password = secrets.token_urlsafe(12)
        now = datetime.now(timezone.utc)
        user = db.fetch_query("SELECT id FROM saas_users WHERE artist_id = %s", (artist_id,))
        if user:
            db.execute_query(
                "UPDATE saas_users SET password_hash = %s, email = %s, "
                "email_verified = TRUE, active = TRUE, token_version = token_version + 1 "
                "WHERE id = %s",
                (hash_password(password), email, user[0][0]))
            print(f"{_OK} compte existant mis à jour — mot de passe régénéré")
        else:
            db.execute_query(
                "INSERT INTO saas_users (username, email, password_hash, artist_id, role, "
                "active, email_verified, terms_accepted, terms_accepted_at) "
                "VALUES (%s, %s, %s, %s, 'artist', TRUE, TRUE, TRUE, %s)",
                (slug, email, hash_password(password), artist_id, now))
            print(f"{_OK} compte artiste créé")

        # Le même essai qu'une vraie inscription : sans lui, le parcours répété ne
        # serait pas celui que voit un nouvel artiste.
        from src.dashboard.views.register import _grant_welcome_trial
        _grant_welcome_trial(db, artist_id)
        print(f"{_OK} essai premium accordé, comme à l'inscription")

        print()
        print("─" * 62)
        print(f"  Connexion : {email}")
        print(f"  Mot de passe : {password}")
        print("─" * 62)
        print("  Le garde d'unicité laisse ce locataire réutiliser TES identifiants.")
        print("  Il collecte pour de vrai ; il ne compte dans aucune statistique.")
        print()
        print("  Rejouer depuis zéro : make artist-sandbox RESET=1")
        print("  Supprimer            : make artist-sandbox DELETE=1")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
