"""Page Hypeddit - Vue d'ensemble des campagnes."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import sys
from datetime import datetime, timedelta

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader


def get_db():
    """Connexion PostgreSQL."""
    config = config_loader.load()
    db_config = config['database']
    return PostgresHandler(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )


def show():
    """Affiche la page Hypeddit."""
    st.title("🎵 Hypeddit Marketing")
    st.markdown("### Performances des campagnes de promotion musicale")
    st.markdown("---")
    
    db = get_db()
    
    # Vérifier si les tables existent
    if not db.table_exists('hypeddit_campaigns'):
        st.error("❌ Table Hypeddit non trouvée")
        st.info("""
        **Pour utiliser cette page, vous devez d'abord:**
        
        1. Créer les tables Hypeddit:
        ```bash
        python src/database/hypeddit_schema.py
        ```
        
        2. Configurer votre API key Hypeddit dans `.env`:
        ```
        HYPEDDIT_API_KEY=your_api_key_here
        ```
        
        3. Lancer la collecte depuis la page d'accueil
        """)
        db.close()
        return
    
    # ============================================================================
    # SECTION 1 : KPIs GLOBAUX (30 derniers jours)
    # ============================================================================
    st.header("🎯 Performance Globale (30 derniers jours)")
    
    kpis_query = """
        SELECT 
            COUNT(DISTINCT h.campaign_id) as active_campaigns,
            COALESCE(SUM(h.impressions), 0) as total_impressions,
            COALESCE(SUM(h.clicks), 0) as total_clicks,
            COALESCE(SUM(h.conversions), 0) as total_conversions,
            COALESCE(SUM(h.downloads), 0) as total_downloads,
            COALESCE(SUM(h.pre_saves), 0) as total_pre_saves,
            COALESCE(SUM(h.spend), 0) as total_spend,
            CASE 
                WHEN SUM(h.impressions) > 0 
                THEN ROUND((SUM(h.clicks)::numeric / SUM(h.impressions)::numeric) * 100, 2)
                ELSE 0 
            END as avg_ctr,
            CASE 
                WHEN SUM(h.conversions) > 0 
                THEN ROUND(SUM(h.spend) / SUM(h.conversions), 2)
                ELSE NULL 
            END as avg_cost_per_conversion
        FROM hypeddit_daily_stats h
        WHERE h.date >= CURRENT_DATE - INTERVAL '30 days'
    """
    
    df_kpis = db.fetch_df(kpis_query)
    
    if not df_kpis.empty and df_kpis.iloc[0]['active_campaigns'] > 0:
        kpi = df_kpis.iloc[0]
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        col1.metric(
            "📱 Campagnes Actives",
            f"{int(kpi['active_campaigns']):,}"
        )
        
        col2.metric(
            "👁️ Impressions",
            f"{int(kpi['total_impressions']):,}"
        )
        
        col3.metric(
            "🖱️ Clicks",
            f"{int(kpi['total_clicks']):,}",
            f"CTR: {kpi['avg_ctr']:.2f}%"
        )
        
        col4.metric(
            "✅ Conversions",
            f"{int(kpi['total_conversions']):,}"
        )
        
        col5.metric(
            "💰 Dépenses",
            f"{kpi['total_spend']:,.2f} $"
        )
        
        # Deuxième ligne de KPIs
        col1, col2, col3 = st.columns(3)
        
        col1.metric(
            "⬇️ Downloads",
            f"{int(kpi['total_downloads']):,}"
        )
        
        col2.metric(
            "💾 Pre-saves",
            f"{int(kpi['total_pre_saves']):,}"
        )
        
        if pd.notna(kpi['avg_cost_per_conversion']):
            col3.metric(
                "📊 Coût / Conversion",
                f"{kpi['avg_cost_per_conversion']:.2f} $"
            )
        else:
            col3.metric(
                "📊 Coût / Conversion",
                "N/A"
            )
    else:
        st.warning("⚠️ Aucune donnée disponible pour les 30 derniers jours")
    
    st.markdown("---")
    
    # ============================================================================
    # SECTION 2 : TABLEAU DES CAMPAGNES
    # ============================================================================
    st.header("📋 Vue d'ensemble des Campagnes")
    
    campaigns_query = """
        SELECT 
            c.campaign_name,
            c.campaign_type,
            c.status,
            c.start_date,
            c.end_date,
            COALESCE(SUM(s.conversions), 0) as total_conversions,
            COALESCE(SUM(s.downloads), 0) as total_downloads,
            COALESCE(SUM(s.pre_saves), 0) as total_pre_saves,
            COALESCE(SUM(s.spend), 0) as total_spend,
            CASE 
                WHEN SUM(s.conversions) > 0 
                THEN ROUND(SUM(s.spend) / SUM(s.conversions), 2)
                ELSE NULL 
            END as cost_per_conversion
        FROM hypeddit_campaigns c
        LEFT JOIN hypeddit_daily_stats s ON c.campaign_id = s.campaign_id
            AND s.date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY c.campaign_id, c.campaign_name, c.campaign_type, c.status, c.start_date, c.end_date
        ORDER BY total_conversions DESC
    """
    
    df_campaigns = db.fetch_df(campaigns_query)
    
    if not df_campaigns.empty:
        # Formater pour affichage
        df_display = df_campaigns.copy()
        
        df_display['start_date'] = pd.to_datetime(df_display['start_date']).dt.strftime('%d/%m/%Y')
        df_display['end_date'] = pd.to_datetime(df_display['end_date']).dt.strftime('%d/%m/%Y')
        
        df_display['total_conversions'] = df_display['total_conversions'].apply(lambda x: f"{int(x):,}")
        df_display['total_downloads'] = df_display['total_downloads'].apply(lambda x: f"{int(x):,}")
        df_display['total_pre_saves'] = df_display['total_pre_saves'].apply(lambda x: f"{int(x):,}")
        df_display['total_spend'] = df_display['total_spend'].apply(lambda x: f"{x:,.2f} $")
        df_display['cost_per_conversion'] = df_display['cost_per_conversion'].apply(
            lambda x: f"{x:.2f} $" if pd.notna(x) else "N/A"
        )
        
        df_display = df_display.rename(columns={
            'campaign_name': 'Nom',
            'campaign_type': 'Type',
            'status': 'Statut',
            'start_date': 'Début',
            'end_date': 'Fin',
            'total_conversions': 'Conversions',
            'total_downloads': 'Downloads',
            'total_pre_saves': 'Pre-saves',
            'total_spend': 'Dépenses',
            'cost_per_conversion': 'Coût/Conv.'
        })
        
        st.dataframe(
            df_display,
            hide_index=True,
            use_container_width=True,
            height=400
        )
        
        st.caption(f"📊 {len(df_campaigns)} campagne(s) • Données des 30 derniers jours")
    else:
        st.warning("⚠️ Aucune campagne trouvée")
    
    st.markdown("---")
    
    # ============================================================================
    # SECTION 3 : ÉVOLUTION TEMPORELLE
    # ============================================================================
    st.header("📈 Évolution des Performances")
    
    # Sélecteur de campagne
    if not df_campaigns.empty:
        campaign_names = df_campaigns['campaign_name'].tolist()
        
        selected_campaign = st.selectbox(
            "🎯 Sélectionner une campagne",
            options=['📊 Toutes les campagnes'] + campaign_names,
            key="hypeddit_campaign_selector"
        )
        
        # Filtres de date
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input(
                "📅 Date début",
                value=datetime.now().date() - timedelta(days=30),
                key="hypeddit_start_date"
            )
        
        with col2:
            end_date = st.date_input(
                "📅 Date fin",
                value=datetime.now().date(),
                key="hypeddit_end_date"
            )
        
        st.markdown("---")
        
        # Construire la requête selon la sélection
        if selected_campaign == '📊 Toutes les campagnes':
            time_query = """
                SELECT 
                    date,
                    SUM(conversions) as conversions,
                    SUM(downloads) as downloads,
                    SUM(pre_saves) as pre_saves,
                    SUM(spend) as spend,
                    AVG(ctr) as ctr
                FROM hypeddit_daily_stats
                WHERE date >= %s AND date <= %s
                GROUP BY date
                ORDER BY date
            """
            params = (start_date, end_date)
        else:
            # Récupérer le campaign_id
            campaign_id_query = """
                SELECT campaign_id 
                FROM hypeddit_campaigns 
                WHERE campaign_name = %s
            """
            campaign_id = db.fetch_query(campaign_id_query, (selected_campaign,))[0][0]
            
            time_query = """
                SELECT 
                    date,
                    conversions,
                    downloads,
                    pre_saves,
                    spend,
                    ctr
                FROM hypeddit_daily_stats
                WHERE campaign_id = %s 
                  AND date >= %s 
                  AND date <= %s
                ORDER BY date
            """
            params = (campaign_id, start_date, end_date)
        
        df_time = db.fetch_df(time_query, params)
        
        if not df_time.empty:
            df_time['date'] = pd.to_datetime(df_time['date'])
            
            # Créer le graphique combiné
            fig = go.Figure()
            
            # Conversions (barres)
            fig.add_trace(go.Bar(
                x=df_time['date'],
                y=df_time['conversions'],
                name='Conversions',
                marker_color='#1DB954',
                yaxis='y',
                hovertemplate='<b>Conversions</b><br>%{y:,.0f}<extra></extra>'
            ))
            
            # Downloads (ligne)
            fig.add_trace(go.Scatter(
                x=df_time['date'],
                y=df_time['downloads'],
                name='Downloads',
                mode='lines+markers',
                line=dict(color='#FF6B6B', width=2),
                yaxis='y',
                hovertemplate='<b>Downloads</b><br>%{y:,.0f}<extra></extra>'
            ))
            
            # Pre-saves (ligne)
            fig.add_trace(go.Scatter(
                x=df_time['date'],
                y=df_time['pre_saves'],
                name='Pre-saves',
                mode='lines+markers',
                line=dict(color='#FFD700', width=2),
                yaxis='y',
                hovertemplate='<b>Pre-saves</b><br>%{y:,.0f}<extra></extra>'
            ))
            
            # Dépenses (aire)
            fig.add_trace(go.Scatter(
                x=df_time['date'],
                y=df_time['spend'],
                name='Dépenses ($)',
                mode='lines',
                fill='tozeroy',
                fillcolor='rgba(100, 149, 237, 0.2)',
                line=dict(color='#6495ED', width=2),
                yaxis='y2',
                hovertemplate='<b>Dépenses</b><br>$%{y:,.2f}<extra></extra>'
            ))
            
            fig.update_layout(
                title=f"Performance : {selected_campaign}",
                xaxis_title="Date",
                yaxis=dict(
                    title="Conversions / Downloads / Pre-saves",
                    side='left'
                ),
                yaxis2=dict(
                    title="Dépenses ($)",
                    side='right',
                    overlaying='y'
                ),
                height=600,
                hovermode='x unified',
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Stats de la période
            col1, col2, col3, col4 = st.columns(4)
            
            col1.metric(
                "✅ Conversions Totales",
                f"{df_time['conversions'].sum():,.0f}"
            )
            
            col2.metric(
                "⬇️ Downloads Totaux",
                f"{df_time['downloads'].sum():,.0f}"
            )
            
            col3.metric(
                "💾 Pre-saves Totaux",
                f"{df_time['pre_saves'].sum():,.0f}"
            )
            
            col4.metric(
                "💰 Total Dépensé",
                f"${df_time['spend'].sum():,.2f}"
            )
            
        else:
            st.info("ℹ️ Aucune donnée disponible pour cette période/campagne")
    else:
        st.info("ℹ️ Aucune campagne disponible")
    
    st.markdown("---")
    
    # ============================================================================
    # SECTION 4 : COMPARAISON DES CAMPAGNES
    # ============================================================================
    if not df_campaigns.empty and len(df_campaigns) > 1:
        st.header("🏆 Comparaison des Campagnes")
        
        comparison_query = """
            SELECT 
                c.campaign_name,
                SUM(s.conversions) as conversions,
                SUM(s.downloads) as downloads,
                SUM(s.pre_saves) as pre_saves,
                SUM(s.spend) as spend,
                CASE 
                    WHEN SUM(s.conversions) > 0 
                    THEN ROUND(SUM(s.spend) / SUM(s.conversions), 2)
                    ELSE NULL 
                END as cost_per_conversion
            FROM hypeddit_campaigns c
            LEFT JOIN hypeddit_daily_stats s ON c.campaign_id = s.campaign_id
                AND s.date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY c.campaign_id, c.campaign_name
            HAVING SUM(s.conversions) > 0
            ORDER BY conversions DESC
            LIMIT 10
        """
        
        df_comparison = db.fetch_df(comparison_query)
        
        if not df_comparison.empty:
            # Graphique en barres horizontales
            fig_comparison = go.Figure()
            
            fig_comparison.add_trace(go.Bar(
                y=df_comparison['campaign_name'],
                x=df_comparison['conversions'],
                name='Conversions',
                orientation='h',
                marker_color='#1DB954',
                text=df_comparison['conversions'],
                texttemplate='%{text:,.0f}',
                textposition='outside'
            ))
            
            fig_comparison.update_layout(
                title="Top 10 Campagnes par Conversions",
                xaxis_title="Conversions",
                yaxis_title="",
                height=max(400, len(df_comparison) * 40),
                showlegend=False
            )
            
            st.plotly_chart(fig_comparison, use_container_width=True)
        else:
            st.info("ℹ️ Pas assez de données pour la comparaison")
    
    # Footer
    st.markdown("---")
    st.caption(f"📊 Dernière mise à jour : {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    db.close()


if __name__ == "__main__":
    show()