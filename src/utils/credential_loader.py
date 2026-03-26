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


def load_platform_credentials(artist_id: int, platform: str) -> dict:
    """Retourne les credentials déchiffrés pour (artist_id, platform).

    Fusionne extra_config (config publique) + secrets déchiffrés depuis
    token_encrypted. Retourne {} si aucune ligne trouvée ou erreur.

    Usage dans un DAG :
        creds = load_platform_credentials(artist_id, 'soundcloud')
        client_id = creds.get('client_id') or os.getenv('SOUNDCLOUD_CLIENT_ID')
    """
    import psycopg2

    host = os.getenv('DATABASE_HOST', 'localhost')
    port = int(os.getenv('DATABASE_PORT', 5432))
    database = os.getenv('DATABASE_NAME', 'spotify_etl')
    user = os.getenv('DATABASE_USER', 'postgres')
    password = os.getenv('DATABASE_PASSWORD', '')
    fernet_key = os.getenv('FERNET_KEY', '')

    try:
        conn = psycopg2.connect(
            host=host, port=port, database=database,
            user=user, password=password
        )
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
        logger.warning(f"credential_loader: erreur DB — {e}")
        return {}


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
    import psycopg2

    fernet_key = os.getenv('FERNET_KEY', '')
    if not fernet_key:
        logger.warning("update_platform_secret: FERNET_KEY not set — skipping.")
        return

    host = os.getenv('DATABASE_HOST', 'localhost')
    port = int(os.getenv('DATABASE_PORT', 5432))
    database = os.getenv('DATABASE_NAME', 'spotify_etl')
    user = os.getenv('DATABASE_USER', 'postgres')
    password = os.getenv('DATABASE_PASSWORD', '')

    try:
        from cryptography.fernet import Fernet
        f = Fernet(fernet_key.encode())

        conn = psycopg2.connect(
            host=host, port=port, database=database,
            user=user, password=password
        )
        conn.autocommit = True
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
        logger.info(
            f"update_platform_secret: '{secret_key}' updated for artist={artist_id} platform={platform}"
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
    import psycopg2

    host = os.getenv('DATABASE_HOST', 'localhost')
    port = int(os.getenv('DATABASE_PORT', 5432))
    database = os.getenv('DATABASE_NAME', 'spotify_etl')
    user = os.getenv('DATABASE_USER', 'postgres')
    password = os.getenv('DATABASE_PASSWORD', '')

    try:
        conn = psycopg2.connect(
            host=host, port=port, database=database,
            user=user, password=password
        )
        conn.autocommit = True
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


def get_active_artists(include_artist_id: int = None) -> list:
    """Retourne la liste des artist_id actifs depuis saas_artists.

    Si include_artist_id est fourni (depuis dag_run.conf), retourne
    uniquement cet artiste s'il est actif. Sinon retourne tous les actifs.

    Retourne [(id, name), ...].
    """
    import psycopg2

    host = os.getenv('DATABASE_HOST', 'localhost')
    port = int(os.getenv('DATABASE_PORT', 5432))
    database = os.getenv('DATABASE_NAME', 'spotify_etl')
    user = os.getenv('DATABASE_USER', 'postgres')
    password = os.getenv('DATABASE_PASSWORD', '')

    try:
        conn = psycopg2.connect(
            host=host, port=port, database=database,
            user=user, password=password
        )
        cur = conn.cursor()

        if include_artist_id:
            cur.execute(
                "SELECT id, name FROM saas_artists WHERE id = %s AND active = TRUE",
                (include_artist_id,)
            )
        else:
            cur.execute(
                "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id"
            )

        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

    except Exception as e:
        logger.warning(f"get_active_artists: erreur DB — {e}")
        return []
