"""Vérification des credentials YouTube API - VERSION CORRIGÉE."""
import os
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*70)
print("🔑 VÉRIFICATION CREDENTIALS YOUTUBE")
print("="*70 + "\n")

# Récupérer les variables
api_key = os.getenv('YOUTUBE_API_KEY')
channel_id = os.getenv('YOUTUBE_CHANNEL_ID')

# Vérifier présence
print("📋 Variables d'environnement :")
print(f"   YOUTUBE_API_KEY: {'✅ Présent' if api_key else '❌ MANQUANT'}")
if api_key:
    print(f"      Longueur: {len(api_key)} caractères")
    print(f"      Début: {api_key[:10]}...")

print(f"   YOUTUBE_CHANNEL_ID: {'✅ Présent' if channel_id else '❌ MANQUANT'}")
if channel_id:
    print(f"      ID: {channel_id}")

print("\n" + "="*70)

if not api_key or not channel_id:
    print("❌ CREDENTIALS MANQUANTS")
    print("\n💡 Solution :")
    print("   1. Créer une API Key sur Google Cloud Console")
    print("   2. Activer YouTube Data API v3")
    print("   3. Ajouter dans .env :")
    print("      YOUTUBE_API_KEY=votre_api_key")
    print("      YOUTUBE_CHANNEL_ID=votre_channel_id")
    print("\n   Tutoriel: https://developers.google.com/youtube/v3/getting-started")
    print("="*70 + "\n")
    exit(1)

# Test de connexion
print("\n🧪 TEST CONNEXION API...")

try:
    from googleapiclient.discovery import build
    
    youtube = build('youtube', 'v3', developerKey=api_key)
    
    # Test simple : récupérer info chaîne
    request = youtube.channels().list(
        part='statistics,snippet',
        id=channel_id
    )
    response = request.execute()
    
    if response.get('items'):
        channel = response['items'][0]
        stats = channel['statistics']
        snippet = channel['snippet']
        
        print("✅ CONNEXION RÉUSSIE !\n")
        print(f"📺 Chaîne: {snippet.get('title')}")
        
        # ✅ CORRECTION : Formatter sans virgule pour éviter l'erreur
        subs = stats.get('subscriberCount', '0')
        videos = stats.get('videoCount', '0')
        views = stats.get('viewCount', '0')
        
        print(f"👥 Abonnés: {int(subs):,}".replace(',', ' '))
        print(f"📹 Vidéos: {int(videos):,}".replace(',', ' '))
        print(f"👁️  Vues: {int(views):,}".replace(',', ' '))
        
        print("\n✅ Tout est OK ! Vous pouvez lancer la collecte.")
    else:
        print("⚠️  API accessible mais chaîne introuvable")
        print(f"   Vérifier le CHANNEL_ID: {channel_id}")

except Exception as e:
    print(f"❌ ERREUR DE CONNEXION: {e}")
    print("\n💡 Causes possibles :")
    print("   - API Key invalide")
    print("   - YouTube Data API v3 non activée")
    print("   - Quota API dépassé")
    print("   - Channel ID incorrect")

print("\n" + "="*70 + "\n")