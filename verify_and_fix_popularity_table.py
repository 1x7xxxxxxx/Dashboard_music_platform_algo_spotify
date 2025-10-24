"""Vérification et création de la table track_popularity_history."""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def verify_and_create():
    print("\n" + "="*70)
    print("🔍 VÉRIFICATION TABLE TRACK_POPULARITY_HISTORY")
    print("="*70 + "\n")
    
    # Connexion à spotify_etl
    conn = psycopg2.connect(
        host=os.getenv('DATABASE_HOST', 'localhost'),
        port=int(os.getenv('DATABASE_PORT', 5433)),
        database='spotify_etl',
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD')
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Vérifier si la table existe
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'track_popularity_history'
        );
    """)
    
    exists = cursor.fetchone()[0]
    print(f"📋 Table existe : {'✅ OUI' if exists else '❌ NON'}")
    
    if not exists:
        print("\n🔧 Création de la table...")
        cursor.execute("""
            CREATE TABLE track_popularity_history (
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
            
            CREATE INDEX IF NOT EXISTS idx_track_pop_history_track_date 
            ON track_popularity_history(track_id, date);
        """)
        print("   ✅ Table créée avec succès")
    
    # Compter les enregistrements
    cursor.execute("SELECT COUNT(*) FROM track_popularity_history")
    count = cursor.fetchone()[0]
    print(f"\n📊 Enregistrements actuels : {count}")
    
    if count > 0:
        cursor.execute("""
            SELECT track_name, popularity, date, collected_at
            FROM track_popularity_history
            ORDER BY collected_at DESC
            LIMIT 5
        """)
        
        print("\n📋 Derniers enregistrements :")
        for row in cursor.fetchall():
            print(f"   • {row[0]} - Popularité: {row[1]} - Date: {row[2]}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*70)
    print("✅ VÉRIFICATION TERMINÉE")
    print("="*70 + "\n")

if __name__ == "__main__":
    verify_and_create()