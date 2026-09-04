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
import os
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


def _default_email(slug: str) -> str:
    """Un alias `+slug` de l'adresse de l'opérateur, quand on en connaît une.

    `<slug>@sandbox.local` était le défaut : le domaine n'existe pas, donc les deux
    e-mails du parcours rebondissaient. Un alias `+` arrive dans la même boîte, se
    filtre, et surtout **existe** — c'est ce qui rend l'inscription rejouable en
    entier, e-mails compris.
    """
    for var in ("SANDBOX_EMAIL", "ALERT_EMAIL", "SMTP_USER"):
        base = (os.getenv(var) or "").strip()
        if "@" in base and not base.endswith(".local"):
            local, _, domain = base.partition("@")
            local = local.split("+", 1)[0]       # jamais un alias d'alias
            return f"{local}+{slug}@{domain}"
    return f"{slug}@sandbox.local"


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

    # « Rejouer depuis zéro » inclut les préférences que l'onboarding lui-même écrit.
    # Mesuré le 2026-09-04 : après un `--reset`, la connexion suivante atterrissait sur
    # l'ACCUEIL et non sur la mise en route, parce qu'un passage précédent avait décoché
    # « afficher cette page à la connexion » (migration 082). Le compte était vide de
    # données et pourtant plus tout à fait neuf — c'est le pire des deux : on croit
    # rejouer le premier parcours, on rejoue le deuxième.
    try:
        db.execute_query(
            "UPDATE saas_users SET show_setup_on_login = TRUE WHERE artist_id = %s",
            (artist_id,))
        print(f"   {_OK} préférences d'onboarding remises au défaut")
    except Exception as exc:                # noqa: BLE001 — colonne absente = base ancienne
        print(f"   ⚠️  show_setup_on_login: {type(exc).__name__}")


def _send_verification(email: str, username: str, token: str) -> bool:
    """Envoie le vrai e-mail de vérification. Ne lève jamais.

    Le même chemin que l'inscription (`verification_email.send_verification_email`),
    pas une copie : si un jour l'e-mail change, le bac à sable rejoue le nouveau.
    """
    try:
        from src.utils.verification_email import send_verification_email
        return bool(send_verification_email(email, username, token, lang="fr"))
    except Exception as exc:      # noqa: BLE001 — un mail manquant ne casse pas le reset
        print(f"   ⚠️  envoi impossible : {type(exc).__name__}")
        return False


def _adopt(db, needle: str) -> int:
    """Promeut en bac à sable un compte créé par le VRAI formulaire d'inscription.

    Pourquoi cette porte existe, alors que l'outil REFUSE par ailleurs de convertir un
    locataire réel : les deux réponses sont la même. Rejouer le parcours « depuis la
    création de compte » veut dire passer par le formulaire — donc créer un locataire
    ordinaire — et c'est seulement ENSUITE qu'on a besoin de l'exemption d'unicité pour
    y saisir ses propres identifiants. Sans cette commande, la seule façon d'obtenir un
    bac à sable était de sauter l'inscription, c'est-à-dire de ne pas tester ce qu'on
    voulait tester.

    Ce qui la rend sûre est la condition, pas l'intention : **on refuse tout locataire
    qui porte déjà des données collectées**. Un compte qui a des lignes n'est pas un
    compte fraîchement inscrit, et l'exempter du garde d'unicité rouvrirait la fuite de
    locataire que ce garde a fermée.
    """
    rows = db.fetch_query(
        "SELECT a.id, a.slug, a.name, COALESCE(a.is_sandbox, FALSE), u.email, "
        "       COALESCE(a.is_canary, FALSE) "
        "FROM saas_artists a LEFT JOIN saas_users u ON u.artist_id = a.id "
        "WHERE a.slug = %s OR lower(u.email) = lower(%s)",
        (needle.strip().lower(), needle.strip()))
    if not rows:
        print(f"{_KO} aucun compte pour {needle!r} — inscris-le d'abord par le "
              "formulaire, puis relance cette commande.")
        return 0
    artist_id, slug, name, is_sandbox, email, is_canary = rows[0]
    if is_sandbox:
        print(f"{_OK} {slug} (artist_id={artist_id}) est déjà un bac à sable")
        return artist_id
    if is_canary:
        # Trois genres de locataire, et le canari n'est PAS exempt du garde d'unicité :
        # c'est un drapeau, pas une permission. Le promouvoir en bac à sable lui
        # donnerait cette permission en silence, et le canari est justement ce qui
        # prouve chaque nuit que la collecte par locataire fonctionne.
        print(f"{_KO} {slug} (artist_id={artist_id}) est un CANARI. Refus : le canari "
              "n'est pas exempt du garde d'unicité, et l'exempter viderait de son sens "
              "la surveillance nocturne qu'il porte.")
        return 0

    for table in _TENANT_DATA_TABLES:
        if table == "artist_credentials":
            continue
        try:
            n = db.fetch_query(
                f"SELECT COUNT(*) FROM {table} WHERE artist_id = %s", (artist_id,))
        except Exception:      # noqa: BLE001 — table absente : rien à protéger
            continue
        if n and n[0][0]:
            print(f"{_KO} {slug} (artist_id={artist_id}) porte déjà {n[0][0]} ligne(s) "
                  f"dans {table} — ce n'est pas un compte fraîchement inscrit. Refus : "
                  "exempter un locataire vivant du garde d'unicité rouvrirait la fuite "
                  "que ce garde a fermée.")
            return 0

    db.execute_query("UPDATE saas_artists SET is_sandbox = TRUE WHERE id = %s",
                     (artist_id,))
    print(f"{_OK} {slug} (artist_id={artist_id}, {email}) est devenu un bac à sable — "
          f"« {name} » peut désormais réutiliser TES identifiants de plateforme.")
    return artist_id


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slug", default="sandbox", help="slug du locataire (défaut: sandbox)")
    ap.add_argument("--name", default="Bac à sable", help="nom affiché")
    ap.add_argument("--email", help="e-mail de connexion (défaut: <slug>@sandbox.local)")
    ap.add_argument("--reset", action="store_true",
                    help="vide identifiants et données collectées, garde le compte")
    ap.add_argument("--delete", action="store_true", help="supprime le locataire et son compte")
    ap.add_argument("--adopt", metavar="SLUG_OR_EMAIL",
                    help="promeut en bac à sable un compte créé par le VRAI formulaire "
                         "d'inscription (refuse s'il porte déjà des données)")
    ap.add_argument("--verified", action="store_true",
                    help="saute l'étape de vérification d'e-mail (compte prêt à l'emploi)")
    ap.add_argument("--dry-run", action="store_true")
    args, unknown = ap.parse_known_args()
    if unknown:
        # `tools/migrate.sh --dry-run` a déjà appliqué pour de vrai parce qu'un argument
        # inconnu était ignoré en silence. Un outil qui écrit en base ne devine pas.
        print(f"{_KO} argument(s) inconnu(s) : {unknown}")
        return 2

    if args.adopt:
        db = _db()
        try:
            return 0 if _adopt(db, args.adopt) else 1
        finally:
            try:
                db.close()
            except Exception:      # noqa: BLE001
                pass

    slug = args.slug.strip().lower()
    email = args.email or _default_email(slug)
    if email.endswith(".local"):
        # Constaté le 2026-09-04 : le mot de bienvenue est bien parti, et Gmail l'a
        # renvoyé — « le domaine sandbox.local est introuvable ». Un bac à sable qui
        # rejoue l'inscription doit recevoir ce qu'un artiste reçoit, sinon il ne
        # rejoue pas l'inscription : il en saute la moitié.
        print(f"⚠️  {email} n'est pas une adresse livrable — les e-mails de "
              "bienvenue et de vérification REBONDIRONT.")
        print("   Passe --email ton.adresse+sandbox@gmail.com, ou pose ALERT_EMAIL "
              "dans l'environnement pour que l'alias soit calculé tout seul.")
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

        # Le parcours d'un vrai artiste COMMENCE à la vérification de l'e-mail, et
        # `--reset` sautait cette étape (`email_verified = TRUE`). Signalé le
        # 2026-09-04 : « ça ne nous remet pas à l'étape de mail à vérifier ». Or
        # `authenticate` refuse un compte non vérifié — la seule façon de rejouer
        # l'étape est donc de poser le jeton ET d'imprimer le lien, sans dépendre de
        # l'arrivée d'un mail : le bac à sable sert justement à ne dépendre de rien.
        verified = args.verified
        token = None if verified else secrets.token_urlsafe(32)

        user = db.fetch_query("SELECT id FROM saas_users WHERE artist_id = %s", (artist_id,))
        if user:
            db.execute_query(
                "UPDATE saas_users SET password_hash = %s, email = %s, "
                "email_verified = %s, verification_token = %s, "
                "active = TRUE, token_version = token_version + 1 "
                "WHERE id = %s",
                (hash_password(password), email, verified, token, user[0][0]))
            print(f"{_OK} compte existant mis à jour — mot de passe régénéré")
        else:
            db.execute_query(
                "INSERT INTO saas_users (username, email, password_hash, artist_id, role, "
                "active, email_verified, verification_token, terms_accepted, "
                "terms_accepted_at) "
                "VALUES (%s, %s, %s, %s, 'artist', TRUE, %s, %s, TRUE, %s)",
                (slug, email, hash_password(password), artist_id, verified, token, now))
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
        if token:
            base = (os.getenv("APP_BASE_URL") or "http://localhost:8501").rstrip("/")
            link = f"{base}/?page=verify&token={token}"
            # ENVOYER le mail, pas seulement armer le jeton.
            #
            # `--reset` annonçait « le parcours commence ici, comme pour un vrai
            # artiste » et ne faisait pas la seule chose qu'un vrai artiste reçoit.
            # Signalé le 2026-09-04 : « je viens de refaire le process mais toujours
            # pas de mail ». Un outil qui rejoue un parcours doit rejouer ses effets,
            # ou dire lequel il ne rejoue pas — pas laisser croire.
            sent = _send_verification(email, slug, token)
            print("─" * 62)
            print("  ⚠️  Compte NON vérifié — le parcours commence ici, comme pour un")
            print("      vrai artiste.")
            if sent:
                print(f"  ✉️  E-mail de vérification ENVOYÉ à {email}.")
                print("      Clique le lien dans le mail — ou, si tu ne veux pas")
                print("      attendre, celui-ci :")
            else:
                print("  ❌ L'e-mail n'est PAS parti (SMTP absent de ce conteneur ou")
                print("     refus du relais). Le jeton est bien posé : utilise le lien.")
            print(f"  {link}")
            print("      (`--verified` saute cette étape quand tu veux juste entrer.)")
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
