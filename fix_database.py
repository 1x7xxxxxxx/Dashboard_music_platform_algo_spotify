"""Script pour corriger la configuration de la base de données."""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def create_spotify_etl_database():
    """Crée la base spotify_etl si elle n'existe pas."""
    
    # Connexion à postgres pour créer la DB
    conn = psycopg2.connect(
        host=os.getenv('DATABASE_HOST', 'localhost'),
        port=int(os.getenv('DATABASE_PORT', 5433)),
        database='postgres',
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD')
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Vérifier si spotify_etl existe
    cursor.execute("SELECT 1 FROM pg_database WHERE datname='spotify_etl'")
    exists = cursor.fetchone()
    
    if not exists:
        print("📊 Création de la base spotify_etl...")
        cursor.execute("CREATE DATABASE spotify_etl")
        print("✅ Base créée")
    else:
        print("✅ Base spotify_etl existe déjà")
    
    cursor.close()
    conn.close()
    
    # Maintenant créer les tables dans spotify_etl
    conn = psycopg2.connect(
        host=os.getenv('DATABASE_HOST', 'localhost'),
        port=int(os.getenv('DATABASE_PORT', 5433)),
        database='spotify_etl',
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD')
    )
    cursor = conn.cursor()
    
    # Créer la table track_popularity_history
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS track_popularity_history (
        id SERIAL PRIMARY KEY,
        track_id VARCHAR(50) NOT NULL,
        track_name VARCHAR(255) NOT NULL,
        popularity INTEGER DEFAULT 0,
        collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        date DATE DEFAULT CURRENT_DATE,
        UNIQUE(track_id, date)
    );
    
    CREATE INDEX IF NOT EXISTS idx_track_pop_history_track 
    ON track_popularity_history(track_id);
    
    CREATE INDEX IF NOT EXISTS idx_track_pop_history_date 
    ON track_popularity_history(date DESC);
    """
    
    cursor.execute(create_table_sql)
    conn.commit()
    
    print("✅ Table track_popularity_history créée")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔧 CONFIGURATION BASE DE DONNÉES")
    print("="*70 + "\n")
    
    create_spotify_etl_database()
    
    print("\n" + "="*70)
    print("✅ CONFIGURATION TERMINÉE")
    print("="*70 + "\n")