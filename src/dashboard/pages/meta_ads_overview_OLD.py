"""Page Vue d'ensemble Meta Ads."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
    """Affiche la page Meta Ads."""
    st.title("📱 Meta Ads - Vue d'ensemble")
    st.markdown("---")
    
    db = get_db()
    
    # === CAMPAGNES ===
    st.header("🎯 Campagnes")
    
    campaigns_query = """
        SELECT 
            campaign_id,
            campaign_name,
            status,
            objective,
            daily_budget,
            lifetime_budget,
            start_time,
            end_time,
            created_time,
            collected_at
        FROM meta_campaigns
        ORDER BY created_time DESC
    """
    
    df_campaigns = db.fetch_df(campaigns_query)
    
    if df_campaigns.empty:
        st.warning("⚠️ Aucune campagne trouvée. Lancez la collecte Meta Ads.")
        st.code("python collect_and_store_meta_ads.py")
        db.close()
        return
    
    # KPIs Campagnes
    col1, col2, col3, col4 = st.columns(4)
    
    total_campaigns = len(df_campaigns)
    active_campaigns = len(df_campaigns[df_campaigns['status'] == 'ACTIVE'])
    paused_campaigns = len(df_campaigns[df_campaigns['status'] == 'PAUSED'])
    
    col1.metric("📊 Total Campagnes", total_campaigns)
    col2.metric("✅ Actives", active_campaigns)
    col3.metric("⏸️ En pause", paused_campaigns)
    
    # Budget total
    total_lifetime_budget = df_campaigns['lifetime_budget'].sum()
    if pd.notna(total_lifetime_budget) and total_lifetime_budget > 0:
        col4.metric("💰 Budget Lifetime", f"{total_lifetime_budget:,.0f} €")
    else:
        total_daily_budget = df_campaigns['daily_budget'].sum()
        if pd.notna(total_daily_budget) and total_daily_budget > 0:
            col4.metric("💰 Budget Quotidien", f"{total_daily_budget:,.0f} €")
    
    st.markdown("---")
    
    # Graphiques Campagnes
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Répartition par Statut")
        status_counts = df_campaigns['status'].value_counts()
        
        fig_status = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Campagnes par Statut",
            color_discrete_sequence=px.colors.qualitative.Set3,
            hole=0.4
        )
        fig_status.update_layout(height=400)
        st.plotly_chart(fig_status, use_container_width=True)
    
    with col2:
        st.subheader("🎯 Répartition par Objectif")
        if 'objective' in df_campaigns.columns and df_campaigns['objective'].notna().any():
            objective_counts = df_campaigns['objective'].value_counts()
            
            fig_obj = px.bar(
                x=objective_counts.values,
                y=objective_counts.index,
                orientation='h',
                title="Campagnes par Objectif",
                labels={'x': 'Nombre', 'y': 'Objectif'},
                color=objective_counts.values,
                color_continuous_scale='Blues'
            )
            fig_obj.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig_obj, use_container_width=True)
        else:
            st.info("Aucun objectif défini")
    
    st.markdown("---")
    
    # === INSIGHTS (si disponibles) ===
    insights_query = """
        SELECT 
            date,
            SUM(impressions) as impressions,
            SUM(clicks) as clicks,
            SUM(spend) as spend,
            SUM(conversions) as conversions,
            AVG(ctr) as avg_ctr,
            AVG(cpc) as avg_cpc
        FROM meta_insights
        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY date
        ORDER BY date DESC
    """
    
    df_insights = db.fetch_df(insights_query)
    
    if not df_insights.empty:
        st.header("📈 Performance (30 derniers jours)")
        
        # KPIs Performance
        col1, col2, col3, col4 = st.columns(4)
        
        total_impressions = df_insights['impressions'].sum()
        total_clicks = df_insights['clicks'].sum()
        total_spend = df_insights['spend'].sum()
        total_conversions = df_insights['conversions'].sum()
        
        col1.metric("👁️ Impressions", f"{total_impressions:,.0f}")
        col2.metric("🖱️ Clicks", f"{total_clicks:,.0f}")
        col3.metric("💰 Dépenses", f"{total_spend:,.2f} €")
        col4.metric("🎯 Conversions", f"{total_conversions:,.0f}")
        
        st.markdown("---")
        
        # Graphique évolution
        st.subheader("📊 Évolution des Métriques")
        
        df_insights['date'] = pd.to_datetime(df_insights['date'])
        df_insights = df_insights.sort_values('date')
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_insights['date'],
            y=df_insights['impressions'],
            name='Impressions',
            mode='lines+markers',
            line=dict(color='#1f77b4', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=df_insights['date'],
            y=df_insights['clicks'],
            name='Clicks',
            mode='lines+markers',
            line=dict(color='#ff7f0e', width=2),
            yaxis='y2'
        ))
        
        fig.update_layout(
            title="Évolution Impressions & Clicks",
            xaxis_title="Date",
            yaxis_title="Impressions",
            yaxis2=dict(
                title="Clicks",
                overlaying='y',
                side='right'
            ),
            height=500,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # Top Ads
        st.subheader("🏆 Top 10 Ads par Impressions")
        
        top_ads_query = """
            SELECT 
                a.ad_name,
                c.campaign_name,
                SUM(i.impressions) as total_impressions,
                SUM(i.clicks) as total_clicks,
                SUM(i.spend) as total_spend,
                ROUND(AVG(i.ctr), 2) as avg_ctr
            FROM meta_insights i
            JOIN meta_ads a ON i.ad_id = a.ad_id
            JOIN meta_campaigns c ON a.campaign_id = c.campaign_id
            WHERE i.date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY a.ad_name, c.campaign_name
            ORDER BY total_impressions DESC
            LIMIT 10
        """
        
        df_top_ads = db.fetch_df(top_ads_query)
        
        if not df_top_ads.empty:
            st.dataframe(
                df_top_ads,
                hide_index=True,
                use_container_width=True,
                column_config={
                    'ad_name': 'Nom de l\'Ad',
                    'campaign_name': 'Campagne',
                    'total_impressions': st.column_config.NumberColumn('Impressions', format='%d'),
                    'total_clicks': st.column_config.NumberColumn('Clicks', format='%d'),
                    'total_spend': st.column_config.NumberColumn('Dépenses (€)', format='%.2f'),
                    'avg_ctr': st.column_config.NumberColumn('CTR Moyen (%)', format='%.2f')
                }
            )
        
        st.markdown("---")
    
    # === TABLEAU CAMPAGNES DÉTAILLÉ ===
    st.header("📋 Liste des Campagnes")
    
    df_display = df_campaigns.copy()
    
    # Formater les dates
    date_columns = ['created_time', 'start_time', 'end_time', 'collected_at']
    for col in date_columns:
        if col in df_display.columns:
            df_display[col] = pd.to_datetime(df_display[col], errors='coerce').dt.strftime('%Y-%m-%d %H:%M')
    
    # Colonnes à afficher
    display_cols = ['campaign_name', 'status', 'objective', 'daily_budget', 'lifetime_budget', 'created_time']
    df_display = df_display[[col for col in display_cols if col in df_display.columns]]
    
    st.dataframe(
        df_display,
        hide_index=True,
        use_container_width=True,
        height=400,
        column_config={
            'campaign_name': 'Nom de la Campagne',
            'status': 'Statut',
            'objective': 'Objectif',
            'daily_budget': st.column_config.NumberColumn('Budget Quotidien (€)', format='%.2f'),
            'lifetime_budget': st.column_config.NumberColumn('Budget Lifetime (€)', format='%.2f'),
            'created_time': 'Date de Création'
        }
    )
    
    st.markdown("---")
    
    # Informations et prochaines étapes
    if df_insights.empty:
        st.info("""
        **💡 Prochaines étapes :**
        
        Pour voir les statistiques de performance :
        1. ⏰ Attendre 1h que la limite API Meta se réinitialise
        2. 🔄 Relancer la collecte : `python collect_and_store_meta_ads.py`
        3. 📊 Les graphiques de performance apparaîtront automatiquement
        
        **Note :** Seules les ads ACTIVES génèrent des insights.
        """)
    else:
        st.success(f"✅ Données à jour - Dernière collecte : {df_campaigns['collected_at'].max()}")
    
    db.close()


if __name__ == "__main__":
    show()