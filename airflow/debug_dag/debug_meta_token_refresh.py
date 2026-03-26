"""Debug script for meta_token_refresh DAG.

Tests:
1. DB connection + artist_credentials read
2. Current token status (expires_at, days left)
3. Dry-run of the Meta token exchange (no write)
4. Full refresh with DB persist (optional, pass --write flag)

Usage:
    python airflow/debug_dag/debug_meta_token_refresh.py           # dry-run
    python airflow/debug_dag/debug_meta_token_refresh.py --write   # full refresh
"""
import os
import sys
import logging
import requests
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("MetaTokenRefreshDebug")

load_dotenv()
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.database.postgres_handler import PostgresHandler
    DB_AVAILABLE = True
except ImportError:
    logger.warning("PostgresHandler not available.")
    DB_AVAILABLE = False


def print_header(title):
    print(f"\n{'='*60}")
    print(f"🔑  {title.upper()}")
    print(f"{'='*60}")


def step_1_check_credentials():
    print_header("Étape 1 : Credentials Meta en DB")
    try:
        from src.utils.credential_loader import get_active_artists, load_platform_credentials
        artists = get_active_artists()
        if not artists:
            logger.warning("Aucun artiste actif.")
            return []

        valid = []
        for artist_id, name in artists:
            creds = load_platform_credentials(artist_id, 'meta')
            has_token = bool(creds.get('access_token'))
            has_app = bool(creds.get('app_id')) and bool(creds.get('app_secret'))
            status = "✅" if (has_token and has_app) else "⚠️"
            logger.info(f"{status} {name} (id={artist_id}) — access_token: {has_token}, app_id+secret: {has_app}")
            if has_token and has_app:
                valid.append((artist_id, name, creds))
        return valid
    except Exception as e:
        logger.error(f"Erreur : {e}")
        return []


def step_2_check_expiry(artists_with_creds):
    print_header("Étape 2 : Expiration des tokens")
    import psycopg2
    host = os.getenv('DATABASE_HOST', 'localhost')
    port = int(os.getenv('DATABASE_PORT', 5432))

    results = []
    for artist_id, name, creds in artists_with_creds:
        try:
            conn = psycopg2.connect(
                host=host, port=port,
                database=os.getenv('DATABASE_NAME', 'spotify_etl'),
                user=os.getenv('DATABASE_USER', 'postgres'),
                password=os.getenv('DATABASE_PASSWORD', ''),
            )
            cur = conn.cursor()
            cur.execute(
                "SELECT expires_at FROM artist_credentials WHERE artist_id = %s AND platform = 'meta'",
                (artist_id,)
            )
            row = cur.fetchone()
            cur.close()
            conn.close()

            expires_at = row[0] if row else None
            if expires_at:
                if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo:
                    expires_at = expires_at.replace(tzinfo=None)
                days_left = (expires_at - datetime.utcnow()).days
                if days_left <= 0:
                    logger.error(f"❌ {name}: token EXPIRÉ depuis {abs(days_left)} jour(s) ({expires_at.date()})")
                elif days_left <= 15:
                    logger.warning(f"⚠️  {name}: expire dans {days_left} jour(s) ({expires_at.date()}) — REFRESH URGENT")
                elif days_left <= 30:
                    logger.warning(f"⚠️  {name}: expire dans {days_left} jour(s) ({expires_at.date()}) — refresh recommandé")
                else:
                    logger.info(f"✅ {name}: expire dans {days_left} jour(s) ({expires_at.date()}) — OK")
                results.append((artist_id, name, creds, expires_at, days_left))
            else:
                logger.warning(f"⚠️  {name}: expires_at non renseigné — refresh nécessaire pour le populer")
                results.append((artist_id, name, creds, None, -1))
        except Exception as e:
            logger.error(f"❌ {name}: erreur DB — {e}")

    return results


def step_3_dry_run_exchange(token_info):
    print_header("Étape 3 : Dry-run échange de token (pas d'écriture)")
    for artist_id, name, creds, expires_at, days_left in token_info:
        access_token = creds['access_token']
        app_id = creds['app_id']
        app_secret = creds['app_secret']

        logger.info(f"▶ Test échange pour {name}...")
        try:
            r = requests.get(
                'https://graph.facebook.com/v18.0/oauth/access_token',
                params={
                    'grant_type': 'fb_exchange_token',
                    'client_id': app_id,
                    'client_secret': app_secret,
                    'fb_exchange_token': access_token,
                },
                timeout=15,
            )
            data = r.json()
            if r.status_code == 200 and data.get('access_token'):
                expires_in = data.get('expires_in', 5184000)
                new_expires = datetime.utcnow() + timedelta(seconds=expires_in)
                logger.info(
                    f"  ✅ Échange OK — nouveau token obtenu, "
                    f"expire le {new_expires.strftime('%Y-%m-%d')} (+{expires_in // 86400}j)"
                )
            else:
                err = data.get('error', data)
                logger.error(f"  ❌ Échec : {err}")
        except Exception as e:
            logger.error(f"  ❌ Exception : {e}")


def step_4_full_refresh(token_info):
    print_header("Étape 4 : Refresh complet avec écriture en DB")
    from src.utils.credential_loader import update_platform_secret

    for artist_id, name, creds, expires_at, days_left in token_info:
        logger.info(f"▶ Refresh pour {name}...")
        try:
            r = requests.get(
                'https://graph.facebook.com/v18.0/oauth/access_token',
                params={
                    'grant_type': 'fb_exchange_token',
                    'client_id': creds['app_id'],
                    'client_secret': creds['app_secret'],
                    'fb_exchange_token': creds['access_token'],
                },
                timeout=15,
            )
            data = r.json()
            if r.status_code == 200 and data.get('access_token'):
                new_token = data['access_token']
                expires_in = data.get('expires_in', 5184000)
                new_expires = datetime.utcnow() + timedelta(seconds=expires_in)
                update_platform_secret(
                    artist_id, 'meta', 'access_token', new_token,
                    expires_at=new_expires,
                )
                logger.info(f"  ✅ Token sauvegardé en DB — expire le {new_expires.strftime('%Y-%m-%d')}")
            else:
                logger.error(f"  ❌ Échec : {data.get('error', data)}")
        except Exception as e:
            logger.error(f"  ❌ Exception : {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Persist refreshed token to DB')
    args = parser.parse_args()

    artists = step_1_check_credentials()
    if not artists:
        print("\n✅ Fin du diagnostic (aucun artiste à traiter).")
        sys.exit(0)

    token_info = step_2_check_expiry(artists)
    step_3_dry_run_exchange(token_info)

    if args.write:
        step_4_full_refresh(token_info)
    else:
        logger.info("\n💡 Dry-run seulement. Passer --write pour écrire en DB.")

    print("\n✅ Fin du diagnostic.")
