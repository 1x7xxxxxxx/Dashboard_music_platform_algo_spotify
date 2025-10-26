"""Page Hypeddit - Saisie manuelle des statistiques."""
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


def add_campaign_stats(campaign_name: str, date, visits: int, clicks: int, budget: float):
    """Ajoute ou met à jour les statistiques d'une campagne."""
    db = get_db()
    
    try:
        # D'abord, s'assurer que la campagne existe
        campaign_data = [{
            'campaign_name': campaign_name,
            'is_active': True
        }]
        
        db.upsert_many(
            table='hypeddit_campaigns',
            data=campaign_data,
            conflict_columns=['campaign_name'],
            update_columns=['is_active', 'updated_at']
        )

        # ✅ AJOUT : Commit explicite après campagne
        db.conn.commit()
        
        count_stats = db.upsert_many(
            table='hypeddit_daily_stats',
            data=stats_data,
            conflict_columns=['campaign_name', 'date'],
            update_columns=['visits', 'clicks', 'budget', 'updated_at']
        )
        
        # ✅ AJOUT : Commit explicite après stats
        db.conn.commit()
        
        db.close()
        return True, "✅ Données enregistrées avec succès"
        
    except Exception as e:
        db.conn.rollback()  # ✅ Rollback en cas d'erreur
        db.close()
        return False, f"❌ Erreur: {str(e)}"
        
        # Ensuite, ajouter les stats
        stats_data = [{
            'campaign_name': campaign_name,
            'date': date,
            'visits': visits,
            'clicks': clicks,
            'budget': budget
        }]
        
        db.upsert_many(
            table='hypeddit_daily_stats',
            data=stats_data,
            conflict_columns=['campaign_name', 'date'],
            update_columns=['visits', 'clicks', 'budget', 'updated_at']
        )
        
        db.close()
        return True, "✅ Données enregistrées avec succès"
        
    except Exception as e:
        db.close()
        return False, f"❌ Erreur: {str(e)}"


def get_campaigns_list():
    """Récupère la liste des campagnes actives."""
    db = get_db()
    
    query = """
        SELECT campaign_name, created_at
        FROM hypeddit_campaigns
        WHERE is_active = true
        ORDER BY created_at DESC
    """
    
    df = db.fetch_df(query)
    db.close()
    
    return df['campaign_name'].tolist() if not df.empty else []


def get_campaign_stats(campaign_name: str, start_date, end_date):
    """Récupère les statistiques d'une campagne."""
    db = get_db()
    
    query = """
        SELECT 
            date,
            visits,
            clicks,
            budget,
            ctr,
            cost_per_click
        FROM hypeddit_daily_stats
        WHERE campaign_name = %s
          AND date >= %s
          AND date <= %s
        ORDER BY date
    """
    
    df = db.fetch_df(query, (campaign_name, start_date, end_date))
    db.close()
    
    return df


def show():
    """Affiche la page Hypeddit."""
    st.title("📱 Hypeddit - Saisie Manuelle")
    st.markdown("### Gestion des campagnes Hypeddit")
    st.markdown("---")
    
    # Vérifier si les tables existent
    db = get_db()
    
    if not db.table_exists('hypeddit_campaigns'):
        st.error("❌ Tables Hypeddit non trouvées")
        st.info("""
        **Pour utiliser cette page, créez d'abord les tables:**
```bash
        python src/database/hypeddit_schema.py
```
        """)
        db.close()
        return
    
    db.close()
    
    # ============================================================================
    # ONGLETS
    # ============================================================================
    tab1, tab2, tab3 = st.tabs(["📝 Saisie", "📊 Statistiques", "📋 Historique"])
    
    # ============================================================================
    # ONGLET 1 : SAISIE DES DONNÉES
    # ============================================================================
    with tab1:
        st.header("📝 Saisir les données quotidiennes")
        
        st.markdown("---")
        
        # Formulaire de saisie
        with st.form("hypeddit_entry_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Liste des campagnes existantes
                existing_campaigns = get_campaigns_list()
                
                # Choix : nouvelle campagne ou existante
                campaign_type = st.radio(
                    "Type de campagne",
                    ["Campagne existante", "Nouvelle campagne"],
                    horizontal=True
                )
                
                if campaign_type == "Campagne existante":
                    if existing_campaigns:
                        campaign_name = st.selectbox(
                            "🎯 Campagne",
                            options=existing_campaigns
                        )
                    else:
                        st.warning("Aucune campagne existante. Créez-en une nouvelle.")
                        campaign_name = st.text_input(
                            "🎯 Nom de la campagne",
                            placeholder="Ex: Pre-save Mon Titre"
                        )
                else:
                    campaign_name = st.text_input(
                        "🎯 Nom de la nouvelle campagne",
                        placeholder="Ex: Pre-save Mon Titre"
                    )
                
                # Date
                entry_date = st.date_input(
                    "📅 Date",
                    value=datetime.now().date() - timedelta(days=1),
                    max_value=datetime.now().date()
                )
            
            with col2:
                # Visites
                visits = st.number_input(
                    "👁️ Visites",
                    min_value=0,
                    value=0,
                    step=1,
                    help="Nombre de visites de la page"
                )
                
                # Clicks
                clicks = st.number_input(
                    "🖱️ Clicks",
                    min_value=0,
                    value=0,
                    step=1,
                    help="Nombre de clicks sur le lien"
                )
                
                # Budget
                budget = st.number_input(
                    "💰 Budget (€)",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    help="Budget dépensé pour cette journée"
                )
            
            st.markdown("---")
            
            # Boutons
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col2:
                submit_button = st.form_submit_button(
                    "💾 Enregistrer",
                    type="primary",
                    use_container_width=True
                )
            
            with col3:
                clear_button = st.form_submit_button(
                    "🔄 Réinitialiser",
                    use_container_width=True
                )
        
        # Traitement du formulaire
        if submit_button:
            # Validation
            if not campaign_name or campaign_name.strip() == "":
                st.error("❌ Veuillez entrer un nom de campagne")
            elif visits == 0 and clicks == 0 and budget == 0:
                st.warning("⚠️ Aucune donnée saisie")
            else:
                # Enregistrement
                with st.spinner('Enregistrement en cours...'):
                    success, message = add_campaign_stats(
                        campaign_name=campaign_name.strip(),
                        date=entry_date,
                        visits=visits,
                        clicks=clicks,
                        budget=budget
                    )
                
                if success:
                    st.success(message)
                    
                    # Afficher un récapitulatif
                    st.markdown("---")
                    st.subheader("📊 Récapitulatif")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    col1.metric("Visites", f"{visits:,}")
                    col2.metric("Clicks", f"{clicks:,}")
                    col3.metric("Budget", f"{budget:.2f} €")
                    
                    if visits > 0:
                        ctr = (clicks / visits) * 100
                        col4.metric("CTR", f"{ctr:.2f}%")
                    
                    # Métriques calculées
                    if clicks > 0:
                        st.markdown("**Métriques calculées :**")
                        
                        col1, col2 = st.columns(2)
                        
                        cpc = budget / clicks
                        col1.metric("💰 Coût par Click", f"{cpc:.2f} €")
                    
                    st.balloons()
                else:
                    st.error(message)
        
        if clear_button:
            st.rerun()
    
    # ============================================================================
    # ONGLET 2 : STATISTIQUES
    # ============================================================================
    with tab2:
        st.header("📊 Statistiques des Campagnes")
        
        # Filtres
        st.subheader("🔍 Filtres")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            campaigns_list = get_campaigns_list()
            
            if campaigns_list:
                selected_campaign = st.selectbox(
                    "🎯 Sélectionner une campagne",
                    options=campaigns_list
                )
            else:
                st.warning("Aucune campagne disponible. Saisissez des données dans l'onglet 'Saisie'.")
                return
        
        with col2:
            start_date_stats = st.date_input(
                "📅 Date début",
                value=datetime(2023, 1, 1).date(),
                key="stats_start_date"
            )
        
        with col3:
            end_date_stats = st.date_input(
                "📅 Date fin",
                value=datetime.now().date(),
                key="stats_end_date"
            )
        
        st.markdown("---")
        
        # Récupérer les données
        df_stats = get_campaign_stats(selected_campaign, start_date_stats, end_date_stats)
        
        if not df_stats.empty:
            df_stats['date'] = pd.to_datetime(df_stats['date'])
            
            # KPIs de la période
            st.subheader(f"🎯 {selected_campaign}")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            total_visits = df_stats['visits'].sum()
            col1.metric("Visites", f"{int(total_visits):,}")
            
            total_clicks = df_stats['clicks'].sum()
            col2.metric("Clicks", f"{int(total_clicks):,}")
            
            total_budget = df_stats['budget'].sum()
            col3.metric("Budget", f"{total_budget:.2f} €")
            
            avg_ctr = df_stats['ctr'].mean()
            col4.metric("CTR Moy.", f"{avg_ctr:.2f}%")
            
            avg_cpc = df_stats['cost_per_click'].mean()
            col5.metric("CPC Moy.", f"{avg_cpc:.2f} €" if pd.notna(avg_cpc) else "N/A")
            
            st.markdown("---")
            
            # Graphique d'évolution
            st.subheader("📈 Évolution dans le temps")
            
            fig = go.Figure()
            
            # Visites (barres)
            fig.add_trace(go.Bar(
                x=df_stats['date'],
                y=df_stats['visits'],
                name='Visites',
                marker_color='lightblue',
                yaxis='y'
            ))
            
            # Clicks (ligne)
            fig.add_trace(go.Scatter(
                x=df_stats['date'],
                y=df_stats['clicks'],
                name='Clicks',
                mode='lines+markers',
                line=dict(color='#1DB954', width=2),
                yaxis='y'
            ))
            
            # Budget (ligne)
            fig.add_trace(go.Scatter(
                x=df_stats['date'],
                y=df_stats['budget'],
                name='Budget (€)',
                mode='lines+markers',
                line=dict(color='#FF6B6B', width=2),
                yaxis='y2'
            ))
            
            fig.update_layout(
                title="Visites, Clicks et Budget",
                xaxis_title="Date",
                yaxis=dict(title="Visites / Clicks"),
                yaxis2=dict(
                    title="Budget (€)",
                    overlaying='y',
                    side='right'
                ),
                height=500,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Graphique CTR
            st.markdown("---")
            st.subheader("📊 CTR (Click-Through Rate)")
            
            fig_ctr = go.Figure()
            
            fig_ctr.add_trace(go.Scatter(
                x=df_stats['date'],
                y=df_stats['ctr'],
                mode='lines+markers',
                line=dict(color='#FFD700', width=2),
                fill='tozeroy',
                fillcolor='rgba(255, 215, 0, 0.2)'
            ))
            
            fig_ctr.update_layout(
                title="",
                xaxis_title="Date",
                yaxis_title="CTR (%)",
                height=400
            )
            
            st.plotly_chart(fig_ctr, use_container_width=True)
            
        else:
            st.info(f"ℹ️ Aucune donnée pour '{selected_campaign}' sur cette période")
    
    # ============================================================================
    # ONGLET 3 : HISTORIQUE
    # ============================================================================
    with tab3:
        st.header("📋 Historique des Saisies")
        
        # Filtres
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            campaigns_list = get_campaigns_list()
            
            if campaigns_list:
                filter_campaign = st.selectbox(
                    "🎯 Filtrer par campagne",
                    options=['Toutes'] + campaigns_list,
                    key="history_campaign_filter"
                )
            else:
                st.warning("Aucune campagne disponible")
                return
        
        with col2:
            start_date_history = st.date_input(
                "📅 Date début",
                value=datetime(2023, 1, 1).date(),
                key="history_start_date"
            )
        
        with col3:
            end_date_history = st.date_input(
                "📅 Date fin",
                value=datetime.now().date(),
                key="history_end_date"
            )
        
        st.markdown("---")
        
        # Requête historique
        db = get_db()
        
        if filter_campaign == 'Toutes':
            query = """
                SELECT 
                    campaign_name,
                    date,
                    visits,
                    clicks,
                    budget,
                    ctr,
                    cost_per_click,
                    updated_at
                FROM hypeddit_daily_stats
                WHERE date >= %s AND date <= %s
                ORDER BY date DESC, campaign_name
            """
            params = (start_date_history, end_date_history)
        else:
            query = """
                SELECT 
                    campaign_name,
                    date,
                    visits,
                    clicks,
                    budget,
                    ctr,
                    cost_per_click,
                    updated_at
                FROM hypeddit_daily_stats
                WHERE campaign_name = %s
                  AND date >= %s 
                  AND date <= %s
                ORDER BY date DESC
            """
            params = (filter_campaign, start_date_history, end_date_history)
        
        df_history = db.fetch_df(query, params)
        db.close()
        
        if not df_history.empty:
            # Formater pour affichage
            df_display = df_history.copy()
            
            df_display['date'] = pd.to_datetime(df_display['date']).dt.strftime('%d/%m/%Y')
            df_display['updated_at'] = pd.to_datetime(df_display['updated_at']).dt.strftime('%d/%m/%Y %H:%M')
            
            df_display = df_display.rename(columns={
                'campaign_name': 'Campagne',
                'date': 'Date',
                'visits': 'Visites',
                'clicks': 'Clicks',
                'budget': 'Budget',
                'ctr': 'CTR (%)',
                'cost_per_click': 'CPC',
                'updated_at': 'Modifié le'
            })
            
            # Formater les valeurs
            df_display['Visites'] = df_display['Visites'].apply(lambda x: f"{int(x):,}")
            df_display['Clicks'] = df_display['Clicks'].apply(lambda x: f"{int(x):,}")
            df_display['Budget'] = df_display['Budget'].apply(lambda x: f"{x:.2f} €")
            df_display['CTR (%)'] = df_display['CTR (%)'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
            df_display['CPC'] = df_display['CPC'].apply(lambda x: f"{x:.2f} €" if pd.notna(x) else "N/A")
            
            st.dataframe(
                df_display,
                hide_index=True,
                use_container_width=True,
                height=600
            )
            
            st.caption(f"📊 {len(df_history)} enregistrement(s) • Période : {start_date_history} → {end_date_history}")
            
            # Option d'export
            st.markdown("---")
            
            if st.button("📥 Exporter en CSV", type="secondary"):
                csv = df_display.to_csv(index=False)
                st.download_button(
                    label="Télécharger le CSV",
                    data=csv,
                    file_name=f"hypeddit_export_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        
        else:
            st.info("ℹ️ Aucun historique disponible pour cette période/campagne")
    
    # Footer
    st.markdown("---")
    st.caption(f"📊 Dernière mise à jour : {datetime.now().strftime('%d/%m/%Y %H:%M')}")


if __name__ == "__main__":
    show()