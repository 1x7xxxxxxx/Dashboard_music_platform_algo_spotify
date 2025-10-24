"""Script pour migrer les données de track_popularity_history de airflow_db vers spotify_etl."""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def migrate_popularity_data():
    print("\n" + "="*70)
    print("🔄 MIGRATION DONNÉES DE POPULARITÉ")
    print("="*70 + "\n")
    
    # Connexion aux deux bases
    print("1️⃣  Connexion aux bases de données...")
    
    # Source : airflow_db
    conn_source = psycopg2.connect(
        host=os.getenv('DATABASE_HOST', 'localhost'),
        port=int(os.getenv('DATABASE_PORT', 5433)),
        database='airflow_db',
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD')
    )
    cursor_source = conn_source.cursor()
    print("   ✅ Connecté à airflow_db (source)")
    
    # Destination : spotify_etl
    conn_dest = psycopg2.connect(
        host=os.getenv('DATABASE_HOST', 'localhost'),
        port=int(os.getenv('DATABASE_PORT', 5433)),
        database='spotify_etl',
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD')
    )
    cursor_dest = conn_dest.cursor()
    print("   ✅ Connecté à spotify_etl (destination)")
    
    # Vérifier que la table existe dans spotify_etl
    print("\n2️⃣  Vérification table dans spotify_etl...")
    cursor_dest.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'track_popularity_history'
        );
    """)
    
    exists = cursor_dest.fetchone()[0]
    
    if not exists:
        print("   ⚠️  Table n'existe pas, création...")
        cursor_dest.execute("""
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
        """)
        conn_dest.commit()
        print("   ✅ Table créée")
    else:
        print("   ✅ Table existe déjà")
    
    # Compter les données source
    print("\n3️⃣  Récupération des données depuis airflow_db...")
    cursor_source.execute("SELECT COUNT(*) FROM track_popularity_history")
    count_source = cursor_source.fetchone()[0]
    print(f"   📊 {count_source} enregistrements dans airflow_db")
    
    if count_source == 0:
        print("\n   ⚠️  Aucune donnée à migrer")
        cursor_source.close()
        conn_source.close()
        cursor_dest.close()
        conn_dest.close()
        return
    
    # Récupérer toutes les données
    cursor_source.execute("""
        SELECT track_id, track_name, popularity, collected_at, date
        FROM track_popularity_history
        ORDER BY date DESC, track_name
    """)
    
    rows = cursor_source.fetchall()
    print(f"   ✅ {len(rows)} enregistrements récupérés")
    
    # Insérer dans spotify_etl
    print("\n4️⃣  Insertion dans spotify_etl...")
    
    insert_query = """
        INSERT INTO track_popularity_history 
        (track_id, track_name, popularity, collected_at, date)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (track_id, date) 
        DO UPDATE SET 
            track_name = EXCLUDED.track_name,
            popularity = EXCLUDED.popularity,
            collected_at = EXCLUDED.collected_at
    """
    
    cursor_dest.executemany(insert_query, rows)
    conn_dest.commit()
    
    inserted_count = cursor_dest.rowcount
    print(f"   ✅ {inserted_count} enregistrements insérés/mis à jour")
    
    # Vérification finale
    print("\n5️⃣  Vérification finale...")
    cursor_dest.execute("SELECT COUNT(*) FROM track_popularity_history")
    count_dest = cursor_dest.fetchone()[0]
    print(f"   📊 Total dans spotify_etl : {count_dest} enregistrements")
    
    # Afficher quelques exemples
    cursor_dest.execute("""
        SELECT track_name, popularity, date
        FROM track_popularity_history
        ORDER BY date DESC, popularity DESC
        LIMIT 5
    """)
    
    examples = cursor_dest.fetchall()
    print("\n   📋 Exemples migrés :")
    for track_name, popularity, date in examples:
        print(f"      • {track_name}: {popularity}/100 (le {date})")
    
    # Fermer les connexions
    cursor_source.close()
    conn_source.close()
    cursor_dest.close()
    conn_dest.close()
    
    print("\n" + "="*70)
    print("✅ MIGRATION TERMINÉE AVEC SUCCÈS")
    print("="*70)
    print("\n💡 Prochaines étapes :")
    print("   1. Vérifiez le dashboard Streamlit")
    print("   2. Lancez une nouvelle collecte pour ajouter des données")
    print("   3. Les futures collectes iront automatiquement dans spotify_etl")
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    migrate_popularity_data()