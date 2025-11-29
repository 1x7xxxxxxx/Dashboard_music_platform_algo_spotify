"""Page META ADS - Vue d'ensemble optimisée."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import sys
from datetime import datetime, timedelta

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

from src.dashboard.utils import get_db_connection

def get_date_range_filter(key_suffix=""):
    """Crée un filtre de sélection de dates."""
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "📅 Date début",
            value=datetime.now().date() - timedelta(days=30),
            key=f"start_date_{key_suffix}"
        )
    
    with col2:
        end_date = st.date_input(
            "📅 Date fin",
            value=datetime.now().date(),
            key=f"end_date_{key_suffix}"
        )
    
    return start_date, end_date


def show():
    """Affiche la page META ADS optimisée."""
    st.title("📱 META ADS")
    st.markdown("---")
    
    db = get_db_connection()
    
    # ============================================================================
    # SECTION 1 : KPIs GLOBAUX (30 derniers jours)
    # ============================================================================
    st.header("🎯 Métriques Globales (30 derniers jours)")
    
    kpis_query = """
        SELECT 
            COALESCE(SUM(i.spend), 0) as total_spend,
            COALESCE(SUM(i.conversions), 0) as total_conversions,
            CASE 
                WHEN SUM(i.conversions) > 0 
                THEN ROUND(SUM(i.spend) / SUM(i.conversions), 2)
                ELSE NULL 
            END as avg_cpr,
            ROUND(AVG(i.cpc), 2) as avg_cpc
        FROM meta_insights i
        WHERE i.date >= CURRENT_DATE - INTERVAL '30 days'
    """
    
    df_kpis = db.fetch_df(kpis_query)
    
    if not df_kpis.empty:
        kpi = df_kpis.iloc[0]
        
        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric(
            "💰 Dépenses Totales",
            f"{kpi['total_spend']:,.2f} €" if pd.notna(kpi['total_spend']) else "0 €"
        )
        
        col2.metric(
            "🎯 Conversions Totales",
            f"{int(kpi['total_conversions']):,}" if pd.notna(kpi['total_conversions']) else "0"
        )
        
        col3.metric(
            "📊 CPR Moyen",
            f"{kpi['avg_cpr']:.2f} €" if pd.notna(kpi['avg_cpr']) else "N/A"
        )
        
        col4.metric(
            "🖱️ CPC Moyen",
            f"{kpi['avg_cpc']:.2f} €" if pd.notna(kpi['avg_cpc']) else "N/A"
        )
    else:
        st.warning("⚠️ Aucune donnée disponible pour les 30 derniers jours")
    
    st.markdown("---")
    
    # ============================================================================
    # SECTION 2 : TABLEAU DES CAMPAGNES
    # ============================================================================
    st.header("📋 Performance des Campagnes")
    
    # Filtre de date pour le tableau
    st.subheader("🔍 Filtres")
    start_date_table, end_date_table = get_date_range_filter(key_suffix="table")
    
    st.markdown("---")
    
    # Requête pour le tableau
    campaigns_query = """
        SELECT 
            c.campaign_name,
            c.status,
            COALESCE(SUM(i.conversions), 0) as total_conversions,
            CASE 
                WHEN SUM(i.conversions) > 0 
                THEN ROUND(SUM(i.spend) / SUM(i.conversions), 2)
                ELSE NULL 
            END as cpr,
            ROUND(COALESCE(SUM(i.spend), 0), 2) as total_spend,
            ROUND(AVG(i.cpc), 2) as avg_cpc
        FROM meta_campaigns c
        LEFT JOIN meta_ads a ON c.campaign_id = a.campaign_id
        LEFT JOIN meta_insights i ON a.ad_id = i.ad_id 
            AND i.date >= %s 
            AND i.date <= %s
        GROUP BY c.campaign_id, c.campaign_name, c.status
        ORDER BY total_spend DESC
    """
    
    df_campaigns = db.fetch_df(campaigns_query, (start_date_table, end_date_table))
    
    if not df_campaigns.empty:
        # Formater les valeurs pour l'affichage
        df_display = df_campaigns.copy()
        
        # Remplacer NULL par "N/A" pour CPR
        df_display['cpr'] = df_display['cpr'].apply(
            lambda x: f"{x:.2f} €" if pd.notna(x) else "N/A"
        )
        
        # Formater les autres colonnes
        df_display['total_conversions'] = df_display['total_conversions'].apply(
            lambda x: f"{int(x):,}"
        )
        df_display['total_spend'] = df_display['total_spend'].apply(
            lambda x: f"{x:,.2f} €"
        )
        df_display['avg_cpc'] = df_display['avg_cpc'].apply(
            lambda x: f"{x:.2f} €" if pd.notna(x) else "N/A"
        )
        
        # Renommer les colonnes
        df_display = df_display.rename(columns={
            'campaign_name': 'Nom Campagne',
            'status': 'Statut',
            'total_conversions': 'Résultat',
            'cpr': 'CPR',
            'total_spend': 'Montant Dépensé',
            'avg_cpc': 'CPC'
        })
        
        st.dataframe(
            df_display,
            hide_index=True,
            width='stretch',
            height=400
        )
        
        st.caption(f"📊 {len(df_campaigns)} campagne(s) • Période : {start_date_table} → {end_date_table}")
    else:
        st.warning("⚠️ Aucune campagne trouvée pour cette période")
    
    st.markdown("---")
    
    # ============================================================================
    # SECTION 3 : GRAPHIQUE COMBINÉ (Évolution temporelle)
    # ============================================================================
    st.header("📈 Évolution des Performances")
    
    # Filtres pour le graphique
    st.subheader("🔍 Filtres")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Récupérer la liste des campagnes pour le multi-sélecteur
        campaigns_list_query = """
            SELECT campaign_id, campaign_name, created_time
            FROM meta_campaigns
            ORDER BY created_time DESC
        """
        df_campaigns_list = db.fetch_df(campaigns_list_query)
        
        if not df_campaigns_list.empty:
            # Par défaut : dernière campagne créée
            default_campaign = df_campaigns_list.iloc[0]['campaign_name']
            
            selected_campaigns = st.multiselect(
                "🎯 Sélectionner les campagnes",
                options=df_campaigns_list['campaign_name'].tolist(),
                default=[default_campaign],
                key="campaigns_multiselect"
            )
        else:
            st.warning("⚠️ Aucune campagne disponible")
            selected_campaigns = []
    
    with col2:
        # Sélecteur de date compact
        start_date_graph, end_date_graph = get_date_range_filter(key_suffix="graph")
    
    st.markdown("---")
    
    if selected_campaigns:
        # Récupérer les IDs des campagnes sélectionnées
        selected_campaign_ids = df_campaigns_list[
            df_campaigns_list['campaign_name'].isin(selected_campaigns)
        ]['campaign_id'].tolist()
        
        # Requête pour le graphique combiné
        graph_query = """
            SELECT 
                i.date,
                SUM(i.conversions) as daily_conversions,
                CASE 
                    WHEN SUM(i.conversions) > 0 
                    THEN ROUND(SUM(i.spend) / SUM(i.conversions), 2)
                    ELSE NULL 
                END as daily_cpr,
                SUM(i.spend) as daily_spend
            FROM meta_insights i
            JOIN meta_ads a ON i.ad_id = a.ad_id
            WHERE a.campaign_id = ANY(%s)
              AND i.date >= %s 
              AND i.date <= %s
            GROUP BY i.date
            ORDER BY i.date
        """
        
        df_graph = db.fetch_df(
            graph_query, 
            (selected_campaign_ids, start_date_graph, end_date_graph)
        )
        
        if not df_graph.empty:
            df_graph['date'] = pd.to_datetime(df_graph['date'])
            
            # Calculer les dépenses cumulées
            df_graph['cumulative_spend'] = df_graph['daily_spend'].cumsum()
            
            # Créer le graphique combiné
            fig = go.Figure()
            
            # 1. BARRES : Conversions quotidiennes
            fig.add_trace(go.Bar(
                x=df_graph['date'],
                y=df_graph['daily_conversions'],
                name='Conversions',
                marker_color='#1DB954',
                yaxis='y',
                hovertemplate='<b>Conversions</b><br>%{y:,.0f}<extra></extra>'
            ))
            
            # 2. LIGNE : CPR quotidien
            fig.add_trace(go.Scatter(
                x=df_graph['date'],
                y=df_graph['daily_cpr'],
                name='CPR',
                mode='lines+markers',
                line=dict(color='#FF6B6B', width=2),
                yaxis='y2',
                hovertemplate='<b>CPR</b><br>%{y:.2f} €<extra></extra>'
            ))
            
            # 3. AIRE : Dépenses cumulées
            fig.add_trace(go.Scatter(
                x=df_graph['date'],
                y=df_graph['cumulative_spend'],
                name='Dépenses Cumulées',
                mode='lines',
                fill='tozeroy',
                fillcolor='rgba(100, 149, 237, 0.2)',
                line=dict(color='#6495ED', width=2),
                yaxis='y3',
                hovertemplate='<b>Dépenses Cumulées</b><br>%{y:,.2f} €<extra></extra>'
            ))
            
            # Configuration des axes
            fig.update_layout(
                title=f"Performance : {', '.join(selected_campaigns)}",
                xaxis=dict(title='Date'),
                yaxis=dict(
                    title='Conversions',
                    side='left',
                    showgrid=True
                ),
                yaxis2=dict(
                    title='CPR (€)',
                    side='right',
                    overlaying='y',
                    showgrid=False
                ),
                yaxis3=dict(
                    title='Dépenses Cumulées (€)',
                    side='right',
                    overlaying='y',
                    anchor='free',
                    position=0.95,
                    showgrid=False
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
            
            st.plotly_chart(fig, width='stretch')
            
            # Statistiques de la période
            col1, col2, col3 = st.columns(3)
            
            col1.metric(
                "📊 Conversions Totales",
                f"{df_graph['daily_conversions'].sum():,.0f}"
            )
            
            avg_cpr = df_graph['daily_cpr'].mean()
            col2.metric(
                "💰 CPR Moyen",
                f"{avg_cpr:.2f} €" if pd.notna(avg_cpr) else "N/A"
            )
            
            col3.metric(
                "💸 Total Dépensé",
                f"{df_graph['daily_spend'].sum():,.2f} €"
            )
            
        else:
            st.info("ℹ️ Aucune donnée disponible pour les campagnes sélectionnées sur cette période")
    else:
        st.info("👆 Sélectionnez au moins une campagne pour afficher le graphique")
    
    st.markdown("---")
    
    # ============================================================================
    # SECTION 4 : DISTRIBUTION CPR PAR ADSET
    # ============================================================================
    st.header("📊 Distribution CPR par AdSet")
    
    st.subheader("🔍 Filtres")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Filtre campagne (optionnel)
        campaign_filter = st.selectbox(
            "🎯 Filtrer par campagne (optionnel)",
            options=['Toutes les campagnes'] + df_campaigns_list['campaign_name'].tolist() if not df_campaigns_list.empty else ['Toutes les campagnes'],
            key="adset_campaign_filter"
        )
    
    with col2:
        # Sélecteur de date pour AdSets
        start_date_adset, end_date_adset = get_date_range_filter(key_suffix="adset")
    
    st.markdown("---")
    
    # Requête pour la distribution CPR des AdSets
    adset_query = """
        SELECT 
            ads.adset_name,
            c.campaign_name,
            SUM(i.conversions) as total_conversions,
            SUM(i.spend) as total_spend,
            CASE 
                WHEN SUM(i.conversions) > 0 
                THEN ROUND(SUM(i.spend) / SUM(i.conversions), 2)
                ELSE NULL 
            END as cpr
        FROM meta_adsets ads
        JOIN meta_ads a ON ads.adset_id = a.adset_id
        JOIN meta_insights i ON a.ad_id = i.ad_id
        JOIN meta_campaigns c ON ads.campaign_id = c.campaign_id
        WHERE i.date >= %s AND i.date <= %s
    """
    
    # Ajouter le filtre de campagne si nécessaire
    params = [start_date_adset, end_date_adset]
    if campaign_filter != 'Toutes les campagnes':
        adset_query += " AND c.campaign_name = %s"
        params.append(campaign_filter)
    
    adset_query += """
        GROUP BY ads.adset_id, ads.adset_name, c.campaign_name
        HAVING SUM(i.conversions) > 0
        ORDER BY cpr ASC
    """
    
    df_adsets = db.fetch_df(adset_query, tuple(params))
    
    if not df_adsets.empty:
        # Calculer le CPR moyen
        avg_cpr_adsets = df_adsets['cpr'].mean()
        
        # Créer le graphique en barres horizontales
        fig_adsets = go.Figure()
        
        # Barres : CPR par AdSet
        fig_adsets.add_trace(go.Bar(
            y=df_adsets['adset_name'],
            x=df_adsets['cpr'],
            orientation='h',
            marker=dict(
                color=df_adsets['cpr'],
                colorscale='RdYlGn_r',  # Rouge (mauvais) à vert (bon)
                showscale=True,
                colorbar=dict(title="CPR (€)")
            ),
            text=df_adsets['cpr'].apply(lambda x: f"{x:.2f} €"),
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>CPR: %{x:.2f} €<br>Conversions: %{customdata[0]:,.0f}<br>Dépenses: %{customdata[1]:,.2f} €<extra></extra>',
            customdata=df_adsets[['total_conversions', 'total_spend']].values
        ))
        
        # Ligne verticale : CPR moyen
        fig_adsets.add_vline(
            x=avg_cpr_adsets,
            line_dash="dash",
            line_color="red",
            line_width=2,
            annotation_text=f"CPR Moyen: {avg_cpr_adsets:.2f} €",
            annotation_position="top right"
        )
        
        fig_adsets.update_layout(
            title=f"Distribution CPR par AdSet ({campaign_filter})",
            xaxis_title="CPR (€)",
            yaxis_title="AdSet",
            height=max(400, len(df_adsets) * 30),  # Hauteur dynamique
            showlegend=False,
            hovermode='y'
        )
        
        st.plotly_chart(fig_adsets, width='stretch')
        
        # Statistiques
        col1, col2, col3 = st.columns(3)
        
        col1.metric(
            "📊 Nombre d'AdSets",
            f"{len(df_adsets)}"
        )
        
        col2.metric(
            "💰 CPR Moyen",
            f"{avg_cpr_adsets:.2f} €"
        )
        
        best_adset = df_adsets.iloc[0]
        col3.metric(
            "🏆 Meilleur AdSet",
            f"{best_adset['adset_name'][:20]}...",
            f"CPR: {best_adset['cpr']:.2f} €"
        )
        
    else:
        st.info("ℹ️ Aucun AdSet avec conversions pour cette période/campagne")
    
    st.markdown("---")
    
    # Footer
    st.caption(f"📊 Dernière mise à jour : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    db.close()


if __name__ == "__main__":
    show()