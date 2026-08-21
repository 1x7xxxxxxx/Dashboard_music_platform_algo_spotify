"""Brick 6 — Lecture des credentials depuis artist_credentials (DB).

Utilisé par les DAGs Airflow pour récupérer les clés API d'un artiste
sans dépendre uniquement des variables d'environnement.

Fonctionne en Docker (host=postgres) et en local (host=localhost:5433).
Nécessite FERNET_KEY dans l'environnement pour déchiffrer token_encrypted.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)


class CredentialLoadError(RuntimeError):
    """The credential store could not be READ (DB down, bad DSN, decrypt failure).

    Distinct from "this artist has not connected this platform", which is an
    empty dict. Conflating the two is what let a transient DB outage silently
    turn every tenant's collection into "collect the admin's data": callers
    fell back to env identities they should never have reached.
    """


class UnknownArtistError(RuntimeError):
    """A specific artist_id was requested but is absent or inactive."""


def _connect(autocommit: bool = False):
    """This module's door to the database — `src.utils.pg_connect` owns the DSN.

    Four functions below each read the same five variables and called
    `psycopg2.connect` with the same keywords. They were folded into one on
    2026-08-21; that one now delegates, because three OTHER modules had their own
    copy too and two of them defaulted the host differently. See `pg_connect` for
    what that split cost.
    """
    from src.utils.pg_connect import connect

    return connect(autocommit=autocommit)


def load_platform_credentials(artist_id: int, platform: str) -> dict:
    """Retourne les credentials déchiffrés pour (artist_id, platform).

    Fusionne extra_config (config publique) + secrets déchiffrés depuis
    token_encrypted. Retourne {} **uniquement** si l'artiste n'a pas connecté
    cette plateforme ; lève CredentialLoadError si le magasin est illisible.

    Usage dans un DAG — noter la distinction, elle est le cœur du sujet :

        creds = load_platform_credentials(artist_id, 'soundcloud')
        # credential d'APP (partagée, admin) → repli env légitime (ADR-006)
        client_id = creds.get('client_id') or os.getenv('SOUNDCLOUD_CLIENT_ID')
        # IDENTITÉ du locataire → JAMAIS de repli : l'env porte celle de l'admin
        user_id = (creds.get('user_id') or '').strip()
        if not user_id:
            continue  # pas connecté — on saute, on n'emprunte pas une identité
    """
    fernet_key = os.getenv('FERNET_KEY', '')

    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT token_encrypted, extra_config "
            "FROM artist_credentials "
            "WHERE artist_id = %s AND platform = %s",
            (artist_id, platform)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            logger.debug(f"credential_loader: aucune entrée pour artist={artist_id} platform={platform}")
            return {}

        token_encrypted, extra_config = row

        # Déchiffrer les secrets
        secrets = {}
        if token_encrypted and fernet_key:
            try:
                from cryptography.fernet import Fernet
                f = Fernet(fernet_key.encode())
                secrets = json.loads(f.decrypt(token_encrypted.encode()).decode())
            except Exception as e:
                logger.warning(f"credential_loader: déchiffrement échoué — {e}")

        # Normaliser extra_config
        extra = extra_config or {}
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except Exception:
                extra = {}

        return {**extra, **secrets}

    except Exception as e:
        # NOT `return {}`: an unreadable store is not an unconnected artist.
        logger.error(f"credential_loader: erreur DB — {e}")
        raise CredentialLoadError(
            f"cannot read credentials for artist_id={artist_id} platform={platform}: {e}"
        ) from e


def update_platform_secret(artist_id: int, platform: str,
                           secret_key: str, new_value: str,
                           expires_at=None) -> None:
    """Update a single secret field inside token_encrypted for (artist_id, platform).

    Decrypts the existing blob, updates secret_key with new_value, re-encrypts,
    and writes back. Optionally updates expires_at.
    Requires FERNET_KEY in environment. No-op if row does not exist.

    Usage (e.g. after auto-refreshing a Meta access_token):
        update_platform_secret(1, 'meta', 'access_token', new_token,
                               expires_at=datetime(2026, 5, 25))
    """
    import json

    fernet_key = os.getenv('FERNET_KEY', '')
    if not fernet_key:
        logger.warning("update_platform_secret: FERNET_KEY not set — skipping.")
        return

    try:
        from cryptography.fernet import Fernet
        f = Fernet(fernet_key.encode())

        conn = _connect(autocommit=True)
        cur = conn.cursor()

        # Read current blob
        cur.execute(
            "SELECT token_encrypted FROM artist_credentials WHERE artist_id = %s AND platform = %s",
            (artist_id, platform)
        )
        row = cur.fetchone()
        if not row:
            logger.warning(f"update_platform_secret: no row for artist={artist_id} platform={platform}")
            cur.close()
            conn.close()
            return

        # Decrypt → update → re-encrypt
        secrets = {}
        if row[0]:
            try:
                secrets = json.loads(f.decrypt(row[0].encode()).decode())
            except Exception:
                secrets = {}
        secrets[secret_key] = new_value
        new_blob = f.encrypt(json.dumps(secrets).encode()).decode()

        if expires_at is not None:
            cur.execute(
                "UPDATE artist_credentials SET token_encrypted = %s, expires_at = %s, updated_at = NOW() "
                "WHERE artist_id = %s AND platform = %s",
                (new_blob, expires_at, artist_id, platform)
            )
        else:
            cur.execute(
                "UPDATE artist_credentials SET token_encrypted = %s, updated_at = NOW() "
                "WHERE artist_id = %s AND platform = %s",
                (new_blob, artist_id, platform)
            )

        cur.close()
        conn.close()
        # INFO-02: use DEBUG to avoid leaking secret key names in shared Airflow logs
        logger.debug(
            f"update_platform_secret: token updated for artist={artist_id} platform={platform}"
            + (f" expires_at={expires_at}" if expires_at else "")
        )
    except Exception as e:
        logger.warning(f"update_platform_secret: failed — {e}")


def save_platform_credentials(artist_id: int, platform: str, extra_updates: dict) -> None:
    """Merge extra_updates into extra_config for (artist_id, platform).

    Performs a surgical JSONB merge — does not touch token_encrypted.
    Right-side wins on key conflicts (new value overwrites existing).
    No-op if no row exists for this (artist_id, platform).

    Usage (e.g. after auto-refreshing a client_id):
        save_platform_credentials(1, 'soundcloud', {'client_id': 'newvalue'})
    """
    import json

    try:
        conn = _connect(autocommit=True)
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE artist_credentials
            SET extra_config = COALESCE(extra_config, '{}'::jsonb) || %s::jsonb,
                updated_at   = NOW()
            WHERE artist_id = %s AND platform = %s
            """,
            (json.dumps(extra_updates), artist_id, platform)
        )
        cur.close()
        conn.close()
        logger.info(
            f"save_platform_credentials: updated {list(extra_updates.keys())} "
            f"for artist={artist_id} platform={platform}"
        )
    except Exception as e:
        logger.warning(f"save_platform_credentials: DB write failed — {e}")


def get_active_artists(include_artist_id: int = None,
                       exclude_canaries: bool = False) -> list:
    """Retourne la liste des artist_id actifs depuis saas_artists.

    Trois issues, volontairement distinctes :
      - aucun artiste actif en base              → [] (déploiement mono-tenant vide)
      - include_artist_id absent ou inactif      → UnknownArtistError
      - magasin illisible (DB down, DSN faux)    → CredentialLoadError

    Les confondre est ce qui faisait qu'un `conf={'artist_id': 12}` sur un artiste
    inactif — ou une simple coupure DB — se traduisait par « collecte la chaîne de
    l'admin sous artist_id=1 » au lieu de « artiste inconnu ».

    `exclude_canaries` sert aux contrôles orientés ONBOARDING. Le locataire canari
    est un artiste actif comme un autre, mais ce n'est pas un client à accompagner :
    il ne déclarera jamais SoundCloud, Meta ni Instagram (ce dernier exige une
    propriété réelle du compte), et son indicateur Spotify mesure le CSV S4A qu'il
    n'aura jamais. Le compter produirait chaque nuit « 3 credentials manquants » et
    « connecté sans données » pour un locataire dont c'est l'état NORMAL — soit une
    alerte quotidienne qui n'appelle aucune action, donc la manière la plus sûre
    d'apprendre à ignorer les alertes. Sa santé a son propre contrôle dédié
    (`check_canary_health`), qui pose la seule question pertinente le concernant :
    collecte-t-il encore ce qu'il a déclaré ?

    Retourne [(id, name), ...].
    """
    try:
        conn = _connect()
        cur = conn.cursor()

        if include_artist_id:
            cur.execute(
                "SELECT id, name FROM saas_artists WHERE id = %s AND active = TRUE",
                (include_artist_id,)
            )
        else:
            cur.execute(
                "SELECT id, name FROM saas_artists WHERE active = TRUE"
                + (" AND COALESCE(is_canary, FALSE) = FALSE" if exclude_canaries else "")
                + " ORDER BY id"
            )

        rows = cur.fetchall()
        cur.close()
        conn.close()

        if include_artist_id and not rows:
            raise UnknownArtistError(
                f"artist_id={include_artist_id} does not exist or is not active — "
                "refusing to fall back to another tenant's identity"
            )
        return rows

    except (UnknownArtistError, CredentialLoadError):
        raise
    except Exception as e:
        logger.error(f"get_active_artists: erreur DB — {e}")
        raise CredentialLoadError(f"cannot list active artists: {e}") from e
