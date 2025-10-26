"""Script d'analyse du CSV Apple Music uploadé."""
import pandas as pd
from pathlib import Path

print("\n" + "="*70)
print("🍎 ANALYSE DU CSV APPLE MUSIC")
print("="*70 + "\n")

csv_path = Path(r"C:\Users\timot\Desktop\Dashboard_music_platform_algo_spotify\data\raw\apple_music\songs_1700256678_2015-06-30_2025-10-24.csv")

if not csv_path.exists():
    print(f"❌ Fichier introuvable: {csv_path}")
    exit(1)

print(f"📄 Fichier: {csv_path.name}")
print(f"📏 Taille: {csv_path.stat().st_size / 1024:.2f} KB")

try:
    # Lire le CSV
    df = pd.read_csv(csv_path, encoding='utf-8')
    
    print(f"\n📊 Informations générales:")
    print(f"   • Lignes: {len(df)}")
    print(f"   • Colonnes: {len(df.columns)}")
    
    print(f"\n📋 Noms des colonnes:")
    for i, col in enumerate(df.columns, 1):
        print(f"   {i}. '{col}'")
    
    print(f"\n🔍 Types de données:")
    for col in df.columns:
        print(f"   • {col}: {df[col].dtype}")
    
    print(f"\n📈 Statistiques:")
    numeric_cols = df.select_dtypes(include=['number']).columns
    if len(numeric_cols) > 0:
        print(df[numeric_cols].describe())
    
    print(f"\n👀 Aperçu des 5 premières lignes:")
    print(df.head())
    
    print(f"\n🔢 Valeurs manquantes:")
    missing = df.isnull().sum()
    if missing.sum() > 0:
        print(missing[missing > 0])
    else:
        print("   ✅ Aucune valeur manquante")
    
    # Détection du type de CSV
    print(f"\n🏷️  Détection du type de CSV:")
    
    columns_lower = [col.lower().strip() for col in df.columns]
    
    if any('song' in col for col in columns_lower):
        print("   ✅ Type détecté: SONGS PERFORMANCE")
        print("   → Contient des informations sur les chansons")
        
        # Colonnes importantes
        song_col = [col for col in df.columns if 'song' in col.lower()][0]
        print(f"\n   📊 Colonne chanson: '{song_col}'")
        print(f"   📊 Nombre de chansons uniques: {df[song_col].nunique()}")
        
        if any('play' in col for col in columns_lower):
            plays_col = [col for col in df.columns if 'play' in col.lower()][0]
            print(f"   📊 Colonne plays: '{plays_col}'")
            print(f"   📊 Total plays: {df[plays_col].sum():,}")
            print(f"   📊 Moyenne plays: {df[plays_col].mean():.0f}")
            
            # Top 5 chansons
            print(f"\n   🏆 Top 5 chansons par plays:")
            top_5 = df.nlargest(5, plays_col)[[song_col, plays_col]]
            for idx, row in top_5.iterrows():
                print(f"      {row[song_col]}: {row[plays_col]:,} plays")
        
        if any('listener' in col for col in columns_lower):
            listeners_col = [col for col in df.columns if 'listener' in col.lower()][0]
            print(f"   📊 Colonne listeners: '{listeners_col}'")
            print(f"   📊 Total listeners: {df[listeners_col].sum():,}")
    
    elif 'date' in columns_lower and 'play' in ' '.join(columns_lower):
        print("   ✅ Type détecté: DAILY PLAYS")
        print("   → Contient l'évolution quotidienne des plays")
        
        date_col = [col for col in df.columns if 'date' in col.lower()][0]
        print(f"\n   📊 Colonne date: '{date_col}'")
        print(f"   📊 Période: {df[date_col].min()} → {df[date_col].max()}")
        print(f"   📊 Nombre de jours: {df[date_col].nunique()}")
    
    elif 'listener' in ' '.join(columns_lower).lower():
        print("   ✅ Type détecté: LISTENERS")
        print("   → Contient l'évolution des listeners")
    
    else:
        print("   ⚠️  Type non reconnu")
        print("   → Vérifiez les colonnes ci-dessus")
    
    print("\n" + "="*70)
    print("✅ ANALYSE TERMINÉE")
    print("="*70 + "\n")
    
    # Recommandations
    print("💡 Prochaines étapes:")
    print("   1. Copier ce fichier dans: data/raw/apple_music/")
    print("   2. Lancer: python process_apple_music_csv.py")
    print("   3. Ou utiliser le bouton dans Streamlit\n")

except Exception as e:
    print(f"\n❌ Erreur lors de l'analyse: {e}")
    import traceback
    traceback.print_exc()