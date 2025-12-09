"""Page META ADS - Vue d'ensemble intelligente."""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
from src.dashboard.utils import get_db_connection

def get_date_range_filter(key_suffix=""):
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("📅 Date début", value=date(2023, 1, 1), key=f"start_{key_suffix}")
    with col2:
        end_date = st.date_input("📅 Date fin", value=datetime.now().date(), key=f"end_{key_suffix}")
    return start_date, end_date

def show():
    st.title("📱 META ADS - Performance")
    st.markdown("---")
    
    db = get_db_connection()
    
    try:
        st.header("📊 Vue d'ensemble")
        start, end = get_date_range_filter("global")
        
        # Récupération des données brutes
        camp_query = """
            SELECT 
                c.campaign_name,
                c.status,
                c.objective,
                COALESCE(SUM(i.spend), 0) as spend,
                COALESCE(SUM(i.clicks), 0) as clicks,
                COALESCE(SUM(i.impressions), 0) as impressions,
                COALESCE(SUM(i.conversions), 0) as conversions -- Clics sur liens (Smartlinks)
            FROM meta_campaigns c
            LEFT JOIN meta_ads a ON c.campaign_id = a.campaign_id
            LEFT JOIN meta_insights i ON a.ad_id = i.ad_id AND i.date >= %s AND i.date <= %s
            GROUP BY c.campaign_id, c.campaign_name, c.status, c.objective
            ORDER BY spend DESC
        """
        df = db.fetch_df(camp_query, (start, end))
        
        if not df.empty:
            # Conversion types
            df['spend'] = pd.to_numeric(df['spend']).fillna(0.0)
            df['clicks'] = pd.to_numeric(df['clicks']).fillna(0)
            df['conversions'] = pd.to_numeric(df['conversions']).fillna(0)
            df['impressions'] = pd.to_numeric(df['impressions']).fillna(0)

            # --- LOGIQUE INTELLIGENTE ---
            # On définit le "Résultat Principal" selon l'objectif
            def get_main_result(row):
                if row['objective'] in ['OUTCOME_TRAFFIC', 'OUTCOME_ENGAGEMENT', 'CONVERSIONS']:
                    return row['conversions'] # Pour Hypeddit, c'est le clic sur lien
                elif row['objective'] in ['OUTCOME_AWARENESS', 'BRAND_AWARENESS']:
                    return row['impressions']
                else:
                    return row['clicks'] # Fallback

            df['Resultat'] = df.apply(get_main_result, axis=1)
            
            # Calcul CPR intelligent
            df['Coût/Res. (€)'] = df.apply(lambda x: x['spend'] / x['Resultat'] if x['Resultat'] > 0 else 0, axis=1)
            df['CPC (€)'] = df.apply(lambda x: x['spend'] / x['clicks'] if x['clicks'] > 0 else 0, axis=1)

            # KPIs GLOBAUX
            total_spend = df['spend'].sum()
            total_smartlinks = df['conversions'].sum() # Clics sortants
            avg_cpc = total_spend / df['clicks'].sum() if df['clicks'].sum() > 0 else 0
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💰 Dépenses Totales", f"{total_spend:,.2f} €")
            c2.metric("🎯 Clics SmartLinks", f"{int(total_smartlinks):,}")
            c3.metric("🖱️ CPC Moyen", f"{avg_cpc:.2f} €")
            c4.metric("👁️ Impressions", f"{int(df['impressions'].sum()):,}")
            
            st.markdown("---")

            # FILTRE PAR OBJECTIF
            objectives = ["Tous"] + list(df['objective'].unique())
            selected_obj = st.selectbox("🎯 Filtrer par Objectif", objectives)
            
            df_filtered = df if selected_obj == "Tous" else df[df['objective'] == selected_obj]

            # TABLEAU DÉTAILLÉ
            st.subheader(f"🏆 Performance par Campagne ({selected_obj})")
            
            st.dataframe(
                df_filtered,
                column_order=("campaign_name", "status", "objective", "spend", "Resultat", "Coût/Res. (€)", "clicks", "CPC (€)"),
                column_config={
                    "campaign_name": "Campagne",
                    "status": "Statut",
                    "objective": "Objectif",
                    "spend": st.column_config.NumberColumn("Dépenses", format="%.2f €"),
                    "Resultat": st.column_config.NumberColumn("Résultats", help="Dépend de l'objectif (Clics ou Vues)"),
                    "Coût/Res. (€)": st.column_config.NumberColumn("CPR", format="%.2f €"),
                    "clicks": st.column_config.NumberColumn("Clics Totaux"),
                    "CPC (€)": st.column_config.NumberColumn("CPC", format="%.2f €"),
                },
                width="stretch",
                hide_index=True
            )
            
        else:
            st.info("Aucune donnée disponible.")

    except Exception as e:
        st.error(f"Erreur : {e}")
    finally:
        db.close()

if __name__ == "__main__":
    show()