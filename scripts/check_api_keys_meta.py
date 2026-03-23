import os
from dotenv import load_dotenv
import requests

# Charger les variables du .env
load_dotenv()

def check_meta():
    token = os.getenv('META_ACCESS_TOKEN')
    ad_account = os.getenv('META_AD_ACCOUNT_ID')
    
    print(f"\n📱 TEST META ADS ({ad_account})")
    
    if not token:
        return print("❌ Pas de token configuré dans .env")
    
    # URL de test (liste des campagnes)
    url = f"https://graph.facebook.com/v21.0/{ad_account}/campaigns"
    
    # Appel API
    try:
        resp = requests.get(url, params={'access_token': token})
        
        if resp.status_code == 200:
            data = resp.json()
            count = len(data.get('data', []))
            print(f"✅ Token OK !")
            print(f"✅ Accès au compte pub réussi.")
            print(f"📊 {count} campagne(s) trouvée(s) (actives ou non).")
        else:
            print(f"❌ Erreur API : {resp.status_code}")
            print(f"   Message : {resp.text}")
            
    except Exception as e:
        print(f"❌ Erreur technique : {e}")

if __name__ == "__main__":
    check_meta()