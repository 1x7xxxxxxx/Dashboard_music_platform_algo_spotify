import streamlit as st
import pandas as pd
import plotly.express as px
from src.dashboard.utils import get_db_connection

def show():
    st.title("📱 Méta Ads - Vue Globale (Lifetime)")
    st.markdown("---")

    # --- 1. CONNEXION ---
    db = get_db_connection()
    
    # Récupération de la liste des campagnes
    try:
        # On regarde dans la table performance globale pour lister les campagnes
        df_list = db.fetch_df("SELECT DISTINCT campaign_name FROM meta_insights_performance ORDER BY campaign_name")
        all_campaigns = ["Toutes"] + df_list['campaign_name'].dropna().tolist()
    except Exception as e:
        st.error(f"Erreur connexion BDD: {e}")
        return

    # --- 2. SIDEBAR (Juste le filtre Campagne, pas de Date) ---
    with st.sidebar:
        st.header("🔍 Filtres")
        selected_campaign = st.selectbox("Filtrer par Campagne", all_campaigns)

    # Clause WHERE pour le SQL (Filtre uniquement sur le nom)
    where_clause = ""
    params = []
    
    if selected_campaign != "Toutes":
        where_clause = "WHERE campaign_name = %s"
        params = [selected_campaign]

    # --- 3. REQUÊTES SQL (Ciblage des tables GLOBALES) ---
    
    # A. KPIs Principaux (Table: meta_insights_performance)
    # Cette table contient déjà les colonnes link_clicks, cpm, etc.
    query_kpi = f"""
        SELECT 
            SUM(spend) as total_spend,
            SUM(results) as total_results,
            SUM(impressions) as total_impressions,
            SUM(link_clicks) as total_clicks,
            AVG(cpr) as avg_cpr,
            AVG(cpm) as avg_cpm,
            AVG(ctr) as avg_ctr
        FROM meta_insights_performance
        {where_clause}
    """
    df_kpi = db.fetch_df(query_kpi, params)

    # B. Engagement Social (Table: meta_insights_engagement)
    query_eng = f"""
        SELECT 
            SUM(page_interactions) as total_interactions,
            SUM(post_reactions) as total_reactions,
            SUM(comments) as total_comments,
            SUM(shares) as total_shares,
            SUM(saves) as total_saves
        FROM meta_insights_engagement
        {where_clause}
    """
    df_eng = db.fetch_df(query_eng, params)

    # C. Evolution (Table: meta_insights_performance_day)
    # Ici on prend UNIQUEMENT les colonnes qui existent sûr dans la table Day (Spend, Results, Impressions)
    query_trend = f"""
        SELECT day_date, SUM(spend) as spend, SUM(results) as results, SUM(impressions) as impressions
        FROM meta_insights_performance_day
        {where_clause}
        GROUP BY day_date ORDER BY day_date
    """
    df_trend = db.fetch_df(query_trend, params)

    # D. Répartitions (Tables spécifiques)
    # Pour les breakdowns, on filtre aussi par campagne si besoin
    query_geo = f"SELECT country, SUM(spend) as spend, SUM(results) as results FROM meta_insights_performance_country {where_clause} GROUP BY country"
    df_geo = db.fetch_df(query_geo, params)
    
    query_plat = f"SELECT platform, placement, SUM(spend) as spend FROM meta_insights_performance_placement {where_clause} GROUP BY platform, placement"
    df_plat = db.fetch_df(query_plat, params)

    # --- 4. AFFICHAGE DASHBOARD ---

    if df_kpi.empty or df_kpi['total_spend'].iloc[0] is None:
        st.warning("⚠️ Aucune donnée disponible. Vérifiez que le pipeline a bien tourné.")
        return

    kpi = df_kpi.iloc[0]
    eng = df_eng.iloc[0] if not df_eng.empty else None

    # --- SCORECARDS ---
    st.subheader("🚀 Performance Cumulée")
    c1, c2, c3, c4 = st.columns(4)
    
    c1.metric("Dépenses Totales", f"{kpi['total_spend']:,.0f} €")
    c2.metric("Résultats", f"{kpi['total_results']:,.0f}")
    
    # Calculs de sécurité (éviter division par zéro)
    cpr = kpi['total_spend'] / kpi['total_results'] if kpi['total_results'] and kpi['total_results'] > 0 else 0
    c3.metric("Coût par Résultat", f"{cpr:.2f} €")
    
    ctr = kpi['avg_ctr'] if kpi['avg_ctr'] else 0
    c4.metric("CTR Moyen", f"{ctr:.2f} %")

    # --- GRAPHIQUE ÉVOLUTION ---
    st.markdown("---")
    st.subheader("📈 Évolution Quotidienne")
    # --- GRAPHIQUE ÉVOLUTION ---
    st.markdown("---")
    st.subheader("📈 Évolution Quotidienne")
    if not df_trend.empty:
        # 1. Conversion explicite des types pour éviter l'erreur Plotly
        df_trend['day_date'] = pd.to_datetime(df_trend['day_date'])
        df_trend['spend'] = pd.to_numeric(df_trend['spend'], errors='coerce').fillna(0)
        df_trend['results'] = pd.to_numeric(df_trend['results'], errors='coerce').fillna(0)
        df_trend['impressions'] = pd.to_numeric(df_trend['impressions'], errors='coerce').fillna(0)
        
        tab_ev1, tab_ev2 = st.tabs(["💰 Dépenses & Résultats", "👁️ Impressions"])
        
        with tab_ev1:
            # Plotly gère mieux le 'wide-form' si les types sont uniformes (float)
            fig = px.line(df_trend, x='day_date', y=['spend', 'results'], 
                          title="Dépenses vs Résultats",
                          color_discrete_map={'spend': '#FF6361', 'results': '#003f5c'})
            
            # Ajustement des axes pour avoir deux échelles différentes (Gauche: €, Droite: Vol)
            fig.update_yaxes(title_text="Montant (€)", secondary_y=False)
            fig.update_layout(yaxis2=dict(
                title="Volume Résultats",
                overlaying='y',
                side='right',
                showgrid=False
            ))
            
            # On assigne la série 'results' à l'axe secondaire
            # Note: px.line ne le fait pas nativement, on patch la trace
            fig.data[1].yaxis = 'y2'
            
            st.plotly_chart(fig, width='stretch')
            
        with tab_ev2:
            fig_imp = px.bar(df_trend, x='day_date', y='impressions', title="Volume d'Impressions")
            st.plotly_chart(fig_imp, width='stretch')
    else:
        st.info("Pas de données d'évolution journalière disponibles.")

    # --- REPARTITION & ENGAGEMENT ---
    st.markdown("---")
    r1, r2 = st.columns(2)
    
    with r1:
        st.subheader("🌍 Top Pays (Dépenses)")
        if not df_geo.empty:
            top_geo = df_geo.sort_values('spend', ascending=False).head(10)
            fig_geo = px.bar(top_geo, x='spend', y='country', orientation='h', text_auto='.2s',
                             title="Budget par Pays")
            st.plotly_chart(fig_geo, width='stretch')
    
    with r2:
        st.subheader("❤️ Engagement Social")
        if eng is not None and eng['total_interactions'] is not None:
            # Création manuelle du dataset pour le funnel
            data_funnel = pd.DataFrame({
                'Etape': ['Réactions', 'Commentaires', 'Partages', 'Sauvegardes'],
                'Valeur': [
                    eng['total_reactions'] or 0,
                    eng['total_comments'] or 0,
                    eng['total_shares'] or 0,
                    eng['total_saves'] or 0
                ]
            })
            fig_funnel = px.funnel(data_funnel, x='Valeur', y='Etape')
            st.plotly_chart(fig_funnel, width='stretch')
        else:
            st.info("Pas de données d'engagement.")

    # --- PLACEMENTS ---
    st.markdown("---")
    st.subheader("📱 Placements & Plateformes")
    if not df_plat.empty:
        # Nettoyage pour le Sunburst
        df_plat['platform'] = df_plat['platform'].fillna('Inconnu')
        df_plat['placement'] = df_plat['placement'].fillna('Tous')
        # On s'assure que les valeurs sont positives
        df_plat = df_plat[df_plat['spend'] > 0]
        
        fig_sun = px.sunburst(
            df_plat, 
            path=['platform', 'placement'], 
            values='spend',
            title="Répartition du Budget"
        )
        st.plotly_chart(fig_sun, width='stretch')