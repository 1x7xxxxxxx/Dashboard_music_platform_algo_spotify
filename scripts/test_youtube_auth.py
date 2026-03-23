import sys
import os
from pathlib import Path
from dotenv import load_dotenv  # <--- IMPORT CRUCIAL
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# 1. Setup des chemins
# On remonte de 2 niveaux (scripts -> racine du projet) pour trouver 'src' et '.env'
current_dir = Path(__file__).resolve().parent
if current_dir.name == 'scripts':
    project_root = current_dir.parent
else:
    project_root = current_dir

sys.path.append(str(project_root))

# 2. Charger les variables d'environnement (C'est ça qui manquait !)
# On force le chargement du fichier .env à la racine
dotenv_path = project_root / '.env'
load_dotenv(dotenv_path)

# Imports du projet
from src.utils.config_loader import config_loader

def test_youtube_access():
    print("\n" + "="*60)
    print("🎬 TEST CONNEXION YOUTUBE DATA API")
    print("="*60)

    try:
        # 3. Récupération des clés
        # Maintenant os.getenv va fonctionner car load_dotenv a été appelé
        api_key = os.getenv('YOUTUBE_API_KEY')
        channel_id = os.getenv('YOUTUBE_CHANNEL_ID')

        if not api_key:
            print("❌ ERREUR: YOUTUBE_API_KEY manquante. Vérifiez le fichier .env")
            return

        print(f"🔑 Clé API détectée : {api_key[:5]}...{api_key[-5:]}")
        print(f"📺 Channel ID cible : {channel_id}")

        # 4. Connexion au service
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        # 5. Test réel : Récupérer les infos de la chaîne
        print("\n📡 Tentative d'appel API...")
        request = youtube.channels().list(
            part='snippet,statistics',
            id=channel_id
        )
        response = request.execute()

        if 'items' in response and len(response['items']) > 0:
            channel = response['items'][0]
            title = channel['snippet']['title']
            subs = channel['statistics']['subscriberCount']
            views = channel['statistics']['viewCount']
            
            print(f"\n✅ SUCCÈS ! Connexion établie.")
            print(f"   Nom de la chaîne : {title}")
            print(f"   Abonnés : {subs}")
            print(f"   Vues totales : {views}")
        else:
            print(f"\n❌ ÉCHEC : La requête a réussi mais la chaîne '{channel_id}' est introuvable.")
            print("👉 Vérifiez l'ID de la chaîne (il doit commencer par 'UC...')")

    except HttpError as e:
        print(f"\n❌ ERREUR HTTP GOOGLE :")
        try:
            error_content = e.error_details[0]
            reason = error_content.get('reason')
            message = error_content.get('message')
        except:
            reason = "Inconnu"
            message = str(e)

        print(f"   Raison : {reason}")
        print(f"   Message : {message}")
        
        if reason == 'quotaExceeded':
            print("\n⚠️ QUOTA DÉPASSÉ : Vous avez utilisé vos 10,000 unités aujourd'hui.")
        elif reason == 'keyInvalid' or 'API key not valid' in message:
            print("\n⚠️ CLÉ INVALIDE : Vérifiez la clé dans la Google Cloud Console.")

    except Exception as e:
        print(f"\n❌ ERREUR TECHNIQUE : {e}")

if __name__ == "__main__":
    test_youtube_access()