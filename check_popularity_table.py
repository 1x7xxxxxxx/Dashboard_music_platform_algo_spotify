# Crée ce fichier : check_popularity_table.py
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DATABASE_HOST', 'localhost'),
    port=int(os.getenv('DATABASE_PORT', 5433)),
    database='spotify_etl',  # ✅ IMPORTANT : pas airflow_db
    user=os.getenv('DATABASE_USER', 'postgres'),
    password=os.getenv('DATABASE_PASSWORD')
)

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
print(f"✅ Table track_popularity_history existe : {exists}")

if exists:
    # Compter les enregistrements
    cursor.execute("SELECT COUNT(*) FROM track_popularity_history")
    count = cursor.fetchone()[0]
    print(f"📊 Nombre d'enregistrements : {count}")
    
    # Afficher les 5 derniers
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