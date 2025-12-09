"""Script CLI pour gérer le mapping Campagnes Meta <-> Chansons Spotify."""
import sys
import os
from pathlib import Path
from tabulate import tabulate
import pandas as pd

# Setup chemin
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

def get_db():
    config = config_loader.load()
    return PostgresHandler(**config['database'])

def list_campaigns():
    """Liste les campagnes disponibles depuis la vue globale."""
    db = get_db()
    try:
        # On tape directement dans la table des stats globales
        query = """
            SELECT 
                campaign_name,
                MIN(date_start) as start_date,
                SUM(spend) as total_spend,
                SUM(clicks) as total_clicks
            FROM meta_insights_global
            GROUP BY campaign_name
            ORDER BY start_date DESC
        """
        df = db.fetch_df(query)
        return df
    finally:
        db.close()

def list_tracks():
    """Liste les chansons disponibles (S4A + API)."""
    db = get_db()
    try:
        # On combine S4A et API pour avoir le maximum de choix
        query = """
            SELECT DISTINCT song as track_name, song_uri as uri, 'S4A' as source
            FROM s4a_song_timeline
            UNION
            SELECT DISTINCT name, track_id, 'API'
            FROM spotify_tracks
            ORDER BY track_name
        """
        df = db.fetch_df(query)
        return df
    finally:
        db.close()

def list_mappings():
    """Affiche les liens existants."""
    db = get_db()
    try:
        query = """
            SELECT 
                id, 
                campaign_name, 
                spotify_track_uri, 
                created_at 
            FROM campaign_track_mapping
            ORDER BY created_at DESC
        """
        df = db.fetch_df(query)
        return df
    finally:
        db.close()

def add_mapping():
    """Wizard pour créer un lien."""
    print("\n--- 1. CHOIX DE LA CAMPAGNE ---")
    df_camp = list_campaigns()
    if df_camp.empty:
        print("❌ Aucune campagne trouvée.")
        return

    # Affichage indexé pour choix facile
    print(tabulate(df_camp[['campaign_name', 'total_spend']].reset_index(), headers='keys', tablefmt='simple'))
    
    try:
        idx = int(input("\n👉 Entrez le numéro de la campagne (index) : "))
        selected_camp = df_camp.iloc[idx]['campaign_name']
        print(f"✅ Campagne sélectionnée : {selected_camp}")
    except:
        print("❌ Sélection invalide.")
        return

    print("\n--- 2. CHOIX DE LA CHANSON ---")
    df_tracks = list_tracks()
    if df_tracks.empty:
        print("❌ Aucune chanson trouvée.")
        return

    print(tabulate(df_tracks.reset_index(), headers='keys', tablefmt='simple'))
    
    try:
        idx = int(input("\n👉 Entrez le numéro de la chanson : "))
        selected_uri = df_tracks.iloc[idx]['uri']
        selected_name = df_tracks.iloc[idx]['track_name']
        print(f"✅ Chanson sélectionnée : {selected_name}")
    except:
        print("❌ Sélection invalide.")
        return

    # Validation
    confirm = input(f"\nLier '{selected_camp}' <-> '{selected_name}' ? (o/n) : ")
    if confirm.lower() == 'o':
        db = get_db()
        try:
            query = """
                INSERT INTO campaign_track_mapping (campaign_name, spotify_track_uri)
                VALUES (%s, %s)
                ON CONFLICT (campaign_name, spotify_track_uri) DO NOTHING
            """
            with db.conn.cursor() as cur:
                cur.execute(query, (selected_camp, selected_uri))
                db.conn.commit()
            print("🎉 Mapping enregistré avec succès !")
        except Exception as e:
            print(f"❌ Erreur SQL : {e}")
        finally:
            db.close()

def delete_mapping():
    """Supprimer un lien."""
    df = list_mappings()
    if df.empty:
        print("Aucun mapping à supprimer.")
        return

    print(tabulate(df, headers='keys', tablefmt='simple', showindex=False))
    try:
        id_del = int(input("\n👉 Entrez l'ID du mapping à supprimer : "))
        db = get_db()
        with db.conn.cursor() as cur:
            cur.execute("DELETE FROM campaign_track_mapping WHERE id = %s", (id_del,))
            db.conn.commit()
        print("🗑️ Supprimé.")
        db.close()
    except:
        print("Erreur.")

def main_menu():
    while True:
        print("\n" + "="*50)
        print("🔗 GESTION MAPPING META x SPOTIFY (Mode CSV)")
        print("="*50)
        print("1️⃣  Ajouter un mapping")
        print("2️⃣  Lister les mappings")
        print("3️⃣  Lister les campagnes")
        print("4️⃣  Lister les chansons")
        print("5️⃣  Supprimer un mapping")
        print("0️⃣  Quitter")
        print("="*50)
        
        choice = input("\n👉 Votre choix : ")
        
        if choice == '1': add_mapping()
        elif choice == '2': 
            df = list_mappings()
            print("\n" + tabulate(df, headers='keys', tablefmt='grid'))
        elif choice == '3':
            df = list_campaigns()
            print("\n" + tabulate(df, headers='keys', tablefmt='grid'))
        elif choice == '4':
            df = list_tracks()
            print("\n" + tabulate(df, headers='keys', tablefmt='grid'))
        elif choice == '5': delete_mapping()
        elif choice == '0': break
        else: print("Choix invalide.")

if __name__ == "__main__":
    main_menu()