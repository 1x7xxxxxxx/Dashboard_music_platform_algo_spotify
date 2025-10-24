"""Diagnostic détaillé des données de popularité."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader
from datetime import datetime, timedelta


def diagnose_popularity_data():
    """Diagnostique complet des données de popularité."""
    print("\n" + "="*70)
    print("🔍 DIAGNOSTIC DONNÉES POPULARITÉ")
    print("="*70 + "\n")
    
    config = config_loader.load()
    db = PostgresHandler(**config['database'])
    
    # 1. Vérifier que la table existe
    print("1️⃣  Vérification de la table...")
    exists = db.table_exists('track_popularity_history')
    print(f"   {'✅' if exists else '❌'} Table 'track_popularity_history' existe : {exists}")
    
    if not exists:
        print("\n❌ La table n'existe pas. Lancez :")
        print("   python create_track_popularity_table.py")
        db.close()
        return
    
    print()
    
    # 2. Compter les enregistrements
    print("2️⃣  Nombre total d'enregistrements...")
    count = db.get_table_count('track_popularity_history')
    print(f"   📊 Total : {count:,} enregistrements")
    
    if count == 0:
        print("\n❌ Aucune donnée. Lancez :")
        print("   python test_popularity_manual.py")
        db.close()
        return
    
    print()
    
    # 3. Afficher TOUS les enregistrements
    print("3️⃣  Contenu COMPLET de la table :")
    print("-" * 70)
    
    query_all = """
        SELECT 
            id,
            track_id,
            track_name,
            popularity,
            date,
            collected_at
        FROM track_popularity_history
        ORDER BY collected_at DESC
    """
    
    df_all = db.fetch_df(query_all)
    
    if not df_all.empty:
        print(df_all.to_string(index=False, max_colwidth=50))
    else:
        print("   ⚠️ Aucune donnée trouvée")
    
    print()
    
    # 4. Statistiques par track
    print("4️⃣  Statistiques par track :")
    print("-" * 70)
    
    query_stats = """
        SELECT 
            track_name,
            COUNT(*) as nb_jours,
            MIN(date) as premiere_date,
            MAX(date) as derniere_date,
            MIN(popularity) as pop_min,
            MAX(popularity) as pop_max,
            ROUND(AVG(popularity), 1) as pop_moy
        FROM track_popularity_history
        GROUP BY track_name
        ORDER BY nb_jours DESC
    """
    
    df_stats = db.fetch_df(query_stats)
    
    if not df_stats.empty:
        print(df_stats.to_string(index=False, max_colwidth=40))
    else:
        print("   ⚠️ Aucune donnée")
    
    print()
    
    # 5. Vérifier les dates disponibles
    print("5️⃣  Plage de dates disponibles :")
    print("-" * 70)
    
    query_dates = """
        SELECT 
            MIN(date) as date_min,
            MAX(date) as date_max,
            COUNT(DISTINCT date) as nb_jours_distincts
        FROM track_popularity_history
    """
    
    df_dates = db.fetch_df(query_dates)
    
    if not df_dates.empty:
        row = df_dates.iloc[0]
        print(f"   📅 Première date : {row['date_min']}")
        print(f"   📅 Dernière date  : {row['date_max']}")
        print(f"   📊 Jours distincts : {row['nb_jours_distincts']}")
        
        # Calculer si c'est récent
        if row['date_max']:
            last_date = row['date_max']
            if isinstance(last_date, str):
                from datetime import datetime
                last_date = datetime.strptime(last_date, '%Y-%m-%d').date()
            
            delta = datetime.now().date() - last_date
            print(f"   ⏱️  Dernière collecte il y a : {delta.days} jour(s)")
            
            if delta.days > 1:
                print("\n   ⚠️  ATTENTION : Les données ne sont pas à jour !")
                print("      Lancez : python test_popularity_manual.py")
    else:
        print("   ⚠️ Impossible de récupérer les dates")
    
    print()
    
    # 6. Test de la requête utilisée par le dashboard
    print("6️⃣  Test de la requête du dashboard :")
    print("-" * 70)
    
    # Récupérer un track_name existant
    if not df_all.empty:
        test_track = df_all.iloc[0]['track_name']
        
        # Dates : 30 derniers jours
        start_date = (datetime.now() - timedelta(days=30)).date()
        end_date = datetime.now().date()
        
        print(f"   🎵 Track de test : {test_track}")
        print(f"   📅 Période : {start_date} → {end_date}")
        
        # Requête exacte du dashboard
        dashboard_query = """
            SELECT 
                date,
                popularity
            FROM track_popularity_history
            WHERE track_name = %s
              AND date >= %s
              AND date <= %s
            ORDER BY date
        """
        
        df_test = db.fetch_df(dashboard_query, (test_track, start_date, end_date))
        
        if not df_test.empty:
            print(f"\n   ✅ {len(df_test)} enregistrement(s) trouvé(s) :")
            print(df_test.to_string(index=False))
        else:
            print(f"\n   ❌ PROBLÈME : Aucun résultat avec cette requête !")
            print(f"      Vérifiez que les dates correspondent.")
            
            # Essayer sans filtre de date
            query_no_date = """
                SELECT date, popularity
                FROM track_popularity_history
                WHERE track_name = %s
                ORDER BY date
            """
            
            df_no_date = db.fetch_df(query_no_date, (test_track,))
            
            if not df_no_date.empty:
                print(f"\n   ℹ️  Avec le track_name uniquement : {len(df_no_date)} résultat(s)")
                print(df_no_date.to_string(index=False))
                print("\n   💡 Problème de filtre de dates dans le dashboard")
            else:
                print("\n   ❌ Aucun résultat même sans filtre de date")
                print("      Problème avec le track_name")
    
    print()
    
    # 7. Recommandations
    print("7️⃣  Recommandations :")
    print("-" * 70)
    
    if count == 0:
        print("   ❌ Aucune donnée → Lancez la collecte")
        print("      python test_popularity_manual.py")
    elif count < 10:
        print("   ⚠️  Peu de données → Collectez plus de jours")
        print("      python test_popularity_manual.py")
    else:
        if df_dates.iloc[0]['date_max']:
            last_date = df_dates.iloc[0]['date_max']
            if isinstance(last_date, str):
                from datetime import datetime
                last_date = datetime.strptime(last_date, '%Y-%m-%d').date()
            
            delta = datetime.now().date() - last_date
            
            if delta.days > 1:
                print("   ⚠️  Données obsolètes → Lancez une nouvelle collecte")
                print("      python test_popularity_manual.py")
            else:
                print("   ✅ Données à jour !")
                print("   💡 Si le dashboard ne fonctionne pas, vérifiez :")
                print("      1. Les filtres de dates dans le dashboard")
                print("      2. Les noms exacts des tracks")
                print("      3. La connexion à la bonne base (spotify_etl)")
    
    print("\n" + "="*70)
    print("✅ DIAGNOSTIC TERMINÉ")
    print("="*70 + "\n")
    
    db.close()


if __name__ == "__main__":
    diagnose_popularity_data()