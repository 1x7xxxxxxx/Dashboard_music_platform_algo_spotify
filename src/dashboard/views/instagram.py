import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from src.dashboard.utils import get_db_connection

def show():
    st.title("📸 Instagram - Performance")
    st.markdown("---")

    db = get_db_connection()

    # 1. KPIs (Dernier Snapshot)
    try:
        df_latest = db.fetch_df("SELECT * FROM view_instagram_latest")
        
        if not df_latest.empty:
            followers = df_latest['followers_count'].iloc[0]
            media = df_latest['media_count'].iloc[0]
            username = df_latest['username'].iloc[0]
            last_date = pd.to_datetime(df_latest['collected_at'].iloc[0]).strftime('%d/%m/%Y')
            
            st.subheader(f"Compte : @{username}")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("👥 Abonnés", f"{int(followers):,}")
            c2.metric("📸 Publications", f"{int(media):,}")
            c3.metric("📅 Mise à jour", last_date)
        else:
            st.warning("Aucune donnée Instagram. Lancez le collecteur.")
            db.close()
            return
            
    except Exception as e:
        st.error(e)
        return

    st.markdown("---")

    # 2. GRAPHIQUE D'ÉVOLUTION
    st.subheader("📈 Croissance de la communauté")
    
    try:
        # Historique 90 jours
        query = """
            SELECT collected_at, followers_count, media_count 
            FROM instagram_daily_stats 
            WHERE collected_at >= CURRENT_DATE - INTERVAL '90 days'
            ORDER BY collected_at ASC
        """
        df_hist = db.fetch_df(query)
        
        if not df_hist.empty:
            df_hist['collected_at'] = pd.to_datetime(df_hist['collected_at'])
            
            # Graphique Abonnés
            fig = px.area(
                df_hist, 
                x='collected_at', 
                y='followers_count', 
                title="Évolution des Abonnés (90 jours)",
                markers=True,
                color_discrete_sequence=['#E1306C'] # Couleur Insta
            )
            fig.update_layout(yaxis_title="Nombre d'abonnés")
            st.plotly_chart(fig, width='stretch')
            
    except Exception as e:
        st.error(f"Erreur historique : {e}")

    db.close()

if __name__ == "__main__":
    show()