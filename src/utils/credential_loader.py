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
