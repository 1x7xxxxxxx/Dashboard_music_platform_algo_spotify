"""Script pour lister toutes les bases PostgreSQL disponibles."""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def list_databases():
    print("\n" + "="*70)
    print("🔍 LISTE DES BASES DE DONNÉES DISPONIBLES")
    print("="*70 + "\n")
    
    try:
        # Connexion à la base 'postgres' (toujours disponible)
        conn = psycopg2.connect(
            host=os.getenv('DATABASE_HOST', 'localhost'),
            port=int(os.getenv('DATABASE_PORT', 5433)),
            database='postgres',
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        cursor = conn.cursor()
        
        # Lister toutes les bases
        cursor.execute("""
            SELECT datname 
            FROM pg_database 
            WHERE datistemplate = false
            ORDER BY datname;
        """)
        
        databases = cursor.fetchall()
        
        print(f"📊 {len(databases)} base(s) de données trouvée(s) :")
        print("-" * 70)
        
        for (db_name,) in databases:
            print(f"   • {db_name}")
            
            # Vérifier si track_popularity_history existe dans cette base
            try:
                conn_test = psycopg2.connect(
                    host=os.getenv('DATABASE_HOST', 'localhost'),
                    port=int(os.getenv('DATABASE_PORT', 5433)),
                    database=db_name,
                    user=os.getenv('DATABASE_USER', 'postgres'),
                    password=os.getenv('DATABASE_PASSWORD')
                )
                cursor_test = conn_test.cursor()
                
                cursor_test.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'track_popularity_history'
                    );
                """)
                
                exists = cursor_test.fetchone()[0]
                
                if exists:
                    cursor_test.execute("SELECT COUNT(*) FROM track_popularity_history")
                    count = cursor_test.fetchone()[0]
                    print(f"     └─ ✅ track_popularity_history : {count} enregistrements")
                
                cursor_test.close()
                conn_test.close()
                
            except Exception as e:
                print(f"     └─ ⚠️  Erreur accès : {str(e)[:50]}")
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*70 + "\n")
        
    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    list_databases()