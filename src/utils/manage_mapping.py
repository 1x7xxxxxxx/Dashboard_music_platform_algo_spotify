"""Gestion de la table de mapping META x SPOTIFY."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader
import pandas as pd

def get_db():
    """Connexion PostgreSQL."""
    config = config_loader.load()
    return PostgresHandler(**config['database'])


def list_campaigns():
    """Liste toutes les campagnes Meta disponibles."""
    db = get_db()
    
    query = """
        SELECT 
            c.campaign_id,
            c.campaign_name,
            c.status,
            COUNT(DISTINCT i.ad_id) as ads_count,
            COALESCE(SUM(i.conversions), 0) as total_conversions
        FROM meta_campaigns c
        LEFT JOIN meta_ads a ON c.campaign_id = a.campaign_id
        LEFT JOIN meta_insights i ON a.ad_id = i.ad_id
        GROUP BY c.campaign_id, c.campaign_name, c.status
        ORDER BY c.created_time DESC
    """
    
    df = db.fetch_df(query)
    db.close()
    
    return df


def list_songs():
    """Liste toutes les chansons Spotify disponibles."""
    db = get_db()
    
    query = """
        SELECT DISTINCT
            st.song,
            sg.streams as total_streams,
            t.track_id,
            t.popularity
        FROM s4a_song_timeline st
        LEFT JOIN s4a_songs_global sg ON st.song = sg.song
        LEFT JOIN tracks t ON LOWER(t.track_name) = LOWER(st.song)
        GROUP BY st.song, sg.streams, t.track_id, t.popularity
        ORDER BY sg.streams DESC NULLS LAST
    """
    
    df = db.fetch_df(query)
    db.close()
    
    return df


def add_mapping(campaign_id: str, song: str, track_id: str = None):
    """Ajoute un mapping campagne ↔ chanson."""
    db = get_db()
    
    try:
        data = [{
            'campaign_id': campaign_id,
            'song': song,
            'track_id': track_id,
            'is_active': True
        }]
        
        db.upsert_many(
            table='meta_spotify_mapping',
            data=data,
            conflict_columns=['campaign_id', 'song'],
            update_columns=['track_id', 'is_active', 'updated_at']
        )
        
        print(f"✅ Mapping ajouté : {campaign_id} ↔ {song}")
        
    except Exception as e:
        print(f"❌ Erreur : {e}")
    
    db.close()


def list_mappings():
    """Liste tous les mappings actifs."""
    db = get_db()
    
    query = """
        SELECT 
            m.id,
            c.campaign_name,
            m.song,
            t.popularity as spotify_popularity,
            m.is_active,
            m.created_at
        FROM meta_spotify_mapping m
        JOIN meta_campaigns c ON m.campaign_id = c.campaign_id
        LEFT JOIN tracks t ON m.track_id = t.track_id
        ORDER BY m.created_at DESC
    """
    
    df = db.fetch_df(query)
    db.close()
    
    return df


def delete_mapping(mapping_id: int):
    """Désactive un mapping."""
    db = get_db()
    
    try:
        query = "UPDATE meta_spotify_mapping SET is_active = false WHERE id = %s"
        db.execute_query(query, (mapping_id,))
        print(f"✅ Mapping {mapping_id} désactivé")
    except Exception as e:
        print(f"❌ Erreur : {e}")
    
    db.close()


def interactive_add_mapping():
    """Mode interactif pour ajouter un mapping."""
    print("\n" + "="*70)
    print("🔗 AJOUT MAPPING META x SPOTIFY")
    print("="*70 + "\n")
    
    # Lister les campagnes
    print("📱 CAMPAGNES META DISPONIBLES :")
    print("-" * 70)
    df_campaigns = list_campaigns()
    
    if df_campaigns.empty:
        print("❌ Aucune campagne trouvée")
        return
    
    print(df_campaigns[['campaign_id', 'campaign_name', 'status', 'total_conversions']].to_string(index=True))
    
    # Sélection campagne
    print("\n")
    campaign_idx = input("👉 Entrez le numéro de la campagne (index) : ").strip()
    
    try:
        campaign_idx = int(campaign_idx)
        selected_campaign = df_campaigns.iloc[campaign_idx]
        campaign_id = selected_campaign['campaign_id']
        campaign_name = selected_campaign['campaign_name']
        
        print(f"\n✅ Campagne sélectionnée : {campaign_name}")
    except:
        print("❌ Index invalide")
        return
    
    # Lister les chansons
    print("\n🎵 CHANSONS SPOTIFY DISPONIBLES :")
    print("-" * 70)
    df_songs = list_songs()
    
    if df_songs.empty:
        print("❌ Aucune chanson trouvée")
        return
    
    print(df_songs[['song', 'total_streams', 'popularity']].to_string(index=True))
    
    # Sélection chanson
    print("\n")
    song_idx = input("👉 Entrez le numéro de la chanson (index) : ").strip()
    
    try:
        song_idx = int(song_idx)
        selected_song = df_songs.iloc[song_idx]
        song = selected_song['song']
        track_id = selected_song['track_id'] if pd.notna(selected_song['track_id']) else None
        
        print(f"\n✅ Chanson sélectionnée : {song}")
    except:
        print("❌ Index invalide")
        return
    
    # Confirmation
    print("\n" + "="*70)
    print("📋 RÉCAPITULATIF")
    print("="*70)
    print(f"Campagne : {campaign_name}")
    print(f"Chanson  : {song}")
    print(f"Track ID : {track_id or 'N/A'}")
    print("="*70)
    
    confirm = input("\n✅ Confirmer l'ajout ? (o/n) : ").strip().lower()
    
    if confirm == 'o':
        add_mapping(campaign_id, song, track_id)
        print("\n🎉 Mapping enregistré avec succès !")
    else:
        print("\n❌ Annulé")


def main_menu():
    """Menu principal."""
    while True:
        print("\n" + "="*70)
        print("🔗 GESTION MAPPING META x SPOTIFY")
        print("="*70)
        print("\n1️⃣  Ajouter un mapping")
        print("2️⃣  Lister les mappings")
        print("3️⃣  Lister les campagnes")
        print("4️⃣  Lister les chansons")
        print("5️⃣  Désactiver un mapping")
        print("0️⃣  Quitter")
        print("\n" + "="*70)
        
        choice = input("\n👉 Votre choix : ").strip()
        
        if choice == '1':
            interactive_add_mapping()
        
        elif choice == '2':
            df = list_mappings()
            if not df.empty:
                print("\n📋 MAPPINGS ACTIFS :")
                print("-" * 70)
                print(df.to_string(index=False))
            else:
                print("\n⚠️ Aucun mapping trouvé")
        
        elif choice == '3':
            df = list_campaigns()
            if not df.empty:
                print("\n📱 CAMPAGNES META :")
                print("-" * 70)
                print(df.to_string(index=False))
            else:
                print("\n⚠️ Aucune campagne trouvée")
        
        elif choice == '4':
            df = list_songs()
            if not df.empty:
                print("\n🎵 CHANSONS SPOTIFY :")
                print("-" * 70)
                print(df[['song', 'total_streams', 'popularity']].to_string(index=False))
            else:
                print("\n⚠️ Aucune chanson trouvée")
        
        elif choice == '5':
            df = list_mappings()
            if not df.empty:
                print("\n📋 MAPPINGS ACTIFS :")
                print(df[['id', 'campaign_name', 'song']].to_string(index=False))
                
                mapping_id = input("\n👉 ID du mapping à désactiver : ").strip()
                try:
                    delete_mapping(int(mapping_id))
                except:
                    print("❌ ID invalide")
            else:
                print("\n⚠️ Aucun mapping trouvé")
        
        elif choice == '0':
            print("\n👋 Au revoir !")
            break
        
        else:
            print("\n❌ Choix invalide")


if __name__ == "__main__":
    main_menu()