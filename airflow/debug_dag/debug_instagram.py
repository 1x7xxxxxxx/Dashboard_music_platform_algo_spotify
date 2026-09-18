"""
🐛 DEBUGGER ULTIME - INSTAGRAM PIPELINE
Ce script teste isolément chaque étape du processus Instagram :
1. Variables d'environnement (.env)
2. Connexion à la Base de Données
3. Validité du Token Meta (Appel API)
4. Simulation d'insertion SQL (Dry Run)
"""

import os
import sys
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# --- Configuration Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("InstaDebug")

# --- Chargement Environnement ---
load_dotenv()

# Ajout du chemin pour importer vos modules
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# La rédaction doit survivre à l'échec de TOUT le reste : la ligne qui journalise un
# `ImportError` s'exécute précisément quand le bloc d'import a échoué. Un
# `safe_error` importé là-dedans y serait indéfini — un `NameError` à la place du
# message d'erreur qu'on venait chercher.

# ⚠️ `redact` en plus de `safe_error` : ce sont deux questions différentes.
# `safe_error(e)` traite une EXCEPTION ; le corps d'une réponse HTTP n'en est pas une,
# et ces sondes l'écrivent tel quel. `debug_soundcloud.py:116` lit le corps d'un POST
# qui portait `client_secret`, et `debug_instagram.py:165` est la branche `else` de la
# fonction dont les branches 401/400 n'affichent que `err.get('message')` — le
# balayage du 2026-09-18 avait converti les gestionnaires d'exception et laissé la
# branche du corps entier.
try:
    from src.utils.safe_error import redact, safe_error
except ImportError:  # pragma: no cover - le repli ne dit que le TYPE, qui ne fuit pas
    def safe_error(exc):  # type: ignore[misc]
        return type(exc).__name__

    def redact(text):  # type: ignore[misc]
        # Le repli n'essaie PAS de reproduire les motifs : il efface. Sans le
        # module, on ne sait pas ce qui est un secret — rendre le corps entier
        # serait choisir la lisibilité contre la confidentialité, dans le seul
        # cas où on ne peut pas trancher.
        return '<corps non rédigeable — src/ inatteignable>'


# Import conditionnel pour éviter le crash si le module manque
try:
    from src.database.postgres_handler import PostgresHandler
    DATABASE_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ Module src.database.postgres_handler introuvable. Test BDD limité.")
    DATABASE_AVAILABLE = False

def print_header(title):
    print(f"\n{'='*60}")
    print(f"📸  {title.upper()}")
    print(f"{'='*60}")

def step_1_check_env():
    print_header("Étape 1 : Vérification .env")

    required = [
        "INSTAGRAM_ACCESS_TOKEN",
        "INSTAGRAM_USER_ID",
        "DATABASE_HOST",
        "DATABASE_NAME",
        "DATABASE_USER",
        "DATABASE_PASSWORD"
    ]

    missing = []
    for var in required:
        val = os.getenv(var)
        if not val:
            missing.append(var)
        else:
            # Masquer les secrets pour l'affichage
            display_val = val[:5] + "..." if "TOKEN" in var or "PASSWORD" in var else val
            logger.info(f"✅ {var} = {display_val}")

    if missing:
        logger.error(f"❌ Variables manquantes : {', '.join(missing)}")
        return False
    return True

def step_2_check_database():
    print_header("Étape 2 : Connexion PostgreSQL")

    if not DATABASE_AVAILABLE:
        return False

    host = os.getenv('DATABASE_HOST', 'localhost')
    port = os.getenv('DATABASE_PORT', '5432')

    try:
        db = PostgresHandler.from_env_or_config()
        logger.info(f"✅ Connexion réussie vers {host}:{port}")

        # Test existence table
        try:
            res = db.fetch_df("SELECT count(*) FROM instagram_daily_stats")
            count = res.iloc[0,0]
            logger.info(f"   ℹ️ Table 'instagram_daily_stats' existe ({count} lignes).")
        except Exception as e:
            logger.warning(f"   ⚠️ La table semble manquer ou est vide : {safe_error(e)}")
            print("   💡 SQL de création suggéré :")
            print("""
            CREATE TABLE IF NOT EXISTS instagram_daily_stats (
                id SERIAL PRIMARY KEY,
                ig_user_id TEXT NOT NULL,
                username TEXT,
                followers_count INTEGER,
                follows_count INTEGER,
                media_count INTEGER,
                collected_at DATE NOT NULL
            );
            """)

        db.close()
        return True

    except Exception as e:
        logger.error(f"❌ Échec connexion BDD : {safe_error(e)}")
        return False

def step_3_test_api():
    print_header("Étape 3 : Test API Meta (Instagram)")

    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    user_id = os.getenv("INSTAGRAM_USER_ID")
    from src.utils.meta_config import META_GRAPH_BASE_URL
    base_url = META_GRAPH_BASE_URL

    url = f"{base_url}/{user_id}"
    params = {
        'fields': 'username,followers_count',
        'access_token': token
    }

    logger.info(f"📡 Appel vers : {url}")

    try:
        response = requests.get(url, params=params, timeout=15)

        logger.info(f"   Code HTTP : {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            logger.info("✅ SUCCÈS ! Token valide.")
            logger.info(f"   👤 Username : {data.get('username')}")
            logger.info(f"   📈 Abonnés : {data.get('followers_count')}")
            return data

        elif response.status_code == 401:
            err = response.json().get('error', {})
            logger.error("❌ ERREUR 401 (Non autorisé)")
            logger.error(f"   Message : {err.get('message')}")
            logger.error("   ➡️  Le token est expiré ou invalide.")

        elif response.status_code == 400:
            err = response.json().get('error', {})
            logger.error("❌ ERREUR 400 (Bad Request)")
            logger.error(f"   Message : {err.get('message')}")
            logger.error("   ➡️  Vérifiez l'ID utilisateur (INSTAGRAM_USER_ID).")

        else:
            logger.error(f"❌ Erreur inconnue : {redact(response.text)}")

    except Exception as e:
        logger.error(f"❌ Exception Python lors de l'appel : {type(e).__name__}")

    return None

def step_4_dry_run_insert(api_data):
    print_header("Étape 4 : Simulation Insertion (Dry Run)")

    if not api_data:
        logger.warning("⏩ Pas de données API, simulation annulée.")
        return

    record = {
        'ig_user_id': api_data.get('id'),
        'username': api_data.get('username'),
        'followers_count': api_data.get('followers_count', 0),
        'follows_count': 0, # Donnée non demandée dans le test léger
        'media_count': 0,   # Idem
        'collected_at': datetime.now().strftime('%Y-%m-%d')
    }

    print("📝 Données prêtes pour l'insertion :")
    print(f"   {record}")

    print("\n🔍 Requête SQL simulée :")
    print(f"""
    DELETE FROM instagram_daily_stats WHERE collected_at = '{record['collected_at']}';
    INSERT INTO instagram_daily_stats (ig_user_id, username, followers_count, ...)
    VALUES ('{record['ig_user_id']}', '{record['username']}', {record['followers_count']}, ...);
    """)

    logger.info("✅ Logique de données valide.")

def step_5_test_media():
    print_header("Étape 5 : Test API Media (/{ig-user-id}/media)")
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    user_id = os.getenv("INSTAGRAM_USER_ID")
    from src.utils.meta_config import META_GRAPH_BASE_URL
    url = f"{META_GRAPH_BASE_URL}/{user_id}/media"
    params = {
        'fields': 'id,caption,media_type,permalink,timestamp,'
                  'like_count,comments_count',
        'access_token': token, 'limit': 5,
    }
    logger.info(f"📡 Appel vers : {url}")
    try:
        r = requests.get(url, params=params, timeout=15)
        logger.info(f"   Code HTTP : {r.status_code}")
        if r.status_code == 200:
            items = r.json().get('data', [])
            logger.info(f"✅ {len(items)} média(s) récupéré(s) (page 1, limit 5)")
            for m in items[:3]:
                logger.info(
                    f"   • {m.get('media_type')} {m.get('id')} "
                    f"❤️{m.get('like_count')} 💬{m.get('comments_count')}"
                )
            return [m.get('id') for m in items]
        logger.error(f"❌ Échec media : {redact(r.text[:200])}")
    except Exception as e:
        logger.error(f"❌ Exception media : {type(e).__name__}")
    return []


def step_6_test_media_insights(media_ids):
    print_header("Étape 6 : Test API Insights (/{media-id}/insights)")
    if not media_ids:
        logger.warning("⏩ Pas de media_id, test insights annulé.")
        return
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    from src.utils.meta_config import META_GRAPH_BASE_URL
    mid = media_ids[0]
    url = f"{META_GRAPH_BASE_URL}/{mid}/insights"
    params = {'metric': 'impressions,reach,engagement,saved,shares',
              'access_token': token}
    logger.info(f"📡 Appel vers : {url}")
    try:
        r = requests.get(url, params=params, timeout=15)
        logger.info(f"   Code HTTP : {r.status_code}")
        if r.status_code == 200:
            for it in r.json().get('data', []):
                vals = it.get('values', [])
                v = vals[0].get('value') if vals else None
                logger.info(f"   • {it.get('name')} = {v}")
            logger.info("✅ Insights OK.")
        else:
            logger.error(f"❌ Échec insights : {redact(r.text[:200])}")
    except Exception as e:
        logger.error(f"❌ Exception insights : {type(e).__name__}")


if __name__ == "__main__":
    if step_1_check_env():
        db_ok = step_2_check_database()
        data = step_3_test_api()
        if data:
            step_4_dry_run_insert(data)
        media_ids = step_5_test_media()
        step_6_test_media_insights(media_ids)

    print("\n✅ Fin du diagnostic.")
