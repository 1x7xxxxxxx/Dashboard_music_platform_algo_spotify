"""
CORRECTIF DASHBOARD - Affichage Index de Popularité
====================================================

Problème : Les données de popularité ne s'affichent pas car les filtres
de dates par défaut sont trop restrictifs (30 jours).

Solution : Modifier src/dashboard/views/spotify_s4a_combined.py

LIGNE ~195 : Remplacer la période par défaut de 30 à 60 jours
"""

# ============================================================================
# ANCIEN CODE (lignes ~195-210)
# ============================================================================
"""
        with col2:
            # Date début
            start_date_pop = st.date_input(
                "📅 Date début",
                value=datetime.now().date() - timedelta(days=30),  # ❌ ANCIEN
                format="DD/MM/YYYY",
                key="start_date_popularity"
            )
"""

# ============================================================================
# NOUVEAU CODE (À COPIER-COLLER)
# ============================================================================
"""
        with col2:
            # Date début - par défaut 60 jours pour être sûr d'avoir des données
            start_date_pop = st.date_input(
                "📅 Date début",
                value=datetime.now().date() - timedelta(days=60),  # ✅ NOUVEAU
                format="DD/MM/YYYY",
                key="start_date_popularity"
            )
"""

# ============================================================================
# ALTERNATIVE : Désactiver temporairement les filtres de date
# ============================================================================
"""
Si tu veux voir TOUTES les données sans filtre, remplace la requête :

LIGNE ~218 :

# ANCIEN
popularity_query = '''
    SELECT date, popularity
    FROM track_popularity_history
    WHERE track_name = %s
      AND date >= %s
      AND date <= %s
    ORDER BY date
'''
df_popularity = db.fetch_df(
    popularity_query,
    (selected_track, start_date_pop, end_date_pop)
)

# NOUVEAU (sans filtre de date)
popularity_query = '''
    SELECT date, popularity
    FROM track_popularity_history
    WHERE track_name = %s
    ORDER BY date
'''
df_popularity = db.fetch_df(
    popularity_query,
    (selected_track,)
)
"""

print("✅ Correctif préparé")
print("\nÉtapes :")
print("1. Ouvrir src/dashboard/views/spotify_s4a_combined.py")
print("2. Ligne ~195 : Changer days=30 → days=60")
print("3. Sauvegarder et relancer le dashboard")
print("\nOu bien utiliser l'alternative sans filtre de date.")