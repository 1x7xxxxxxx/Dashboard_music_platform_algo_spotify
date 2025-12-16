import requests

CLIENT_ID = "xXKzFLdhfXAtbaLbKFp4cNoiduLizuYO"  # Collez le nouveau ici
USER_ID = "377065610"              # Votre ID utilisateur (chiffres)

url = f"https://api-v2.soundcloud.com/users/{USER_ID}/tracks"
params = {
    'client_id': CLIENT_ID,
    'limit': 5
}
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

print(f"Test de connexion vers : {url}")
try:
    response = requests.get(url, params=params, headers=headers)
    print(f"Status Code : {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Succès ! Voici le premier titre trouvé :")
        if 'collection' in data and len(data['collection']) > 0:
            print(f"Titre : {data['collection'][0]['title']}")
        else:
            print("Aucun titre trouvé (mais la connexion marche).")
    elif response.status_code == 401:
        print("❌ Erreur 401 : Le Client ID est invalide ou expiré.")
    elif response.status_code == 403:
        print("❌ Erreur 403 : Accès interdit. SoundCloud bloque votre IP ou le User-Agent.")
    else:
        print(f"❌ Erreur {response.status_code} : {response.text}")

except Exception as e:
    print(f"Erreur Python : {e}")