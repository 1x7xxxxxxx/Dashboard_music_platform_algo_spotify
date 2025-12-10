import streamlit as st
import pandas as pd
import plotly.express as px
from src.dashboard.utils.airflow_monitor import AirflowMonitor

def show():
    st.title("🏗️ Monitoring ETL (Airflow)")
    st.markdown("---")
    
    monitor = AirflowMonitor()
    
    with st.spinner("Récupération des stats Airflow..."):
        data = monitor.get_kpis()
    
    if data is None:
        st.error("❌ Impossible de joindre l'API Airflow. Vérifiez que le conteneur tourne.")
        return

    # 1. KPIs GLOBAUX
    c1, c2, c3 = st.columns(3)
    
    c1.metric("Exécutions (24h)", data['total_runs_24h'])
    
    rate = data['success_rate']
    color = "normal" if rate > 90 else "inverse"
    c2.metric("Taux de Succès Global", f"{rate:.1f}%", delta_color=color)
    
    fails = data['failed_count']
    c3.metric("Échecs récents", fails, delta_color="inverse" if fails > 0 else "off")

    st.markdown("---")

    # 2. ALERTES (Si échecs)
    if not data['recent_failures'].empty:
        st.error("🚨 DAGs en échec récemment :")
        st.dataframe(
            data['recent_failures'][['dag_id', 'start_date', 'state']],
            width='stretch',
            hide_index=True
        )
    else:
        st.success("✅ Aucun échec récent détecté. Tout fonctionne !")

    # 3. GRAPHIQUE GANTT (Timeline)
    st.subheader("⏱️ Chronologie des exécutions")
    df = data['raw_data'].copy()
    
    if not df.empty:
        df = df.sort_values('start_date', ascending=False).head(20) # 20 derniers runs
        
        fig = px.timeline(
            df, 
            x_start="start_date", 
            x_end="end_date", 
            y="dag_id", 
            color="state",
            color_discrete_map={"success": "#00CC96", "failed": "#EF553B", "running": "#636EFA"},
            title="Dernières tâches (Gantt)",
            hover_data=["duration_sec"]
        )
        fig.update_yaxes(autorange="reversed") # Plus récent en haut
        st.plotly_chart(fig, width='stretch')

    # 4. TABLEAU DÉTAILLÉ
    with st.expander("🔎 Voir l'historique complet"):
        st.dataframe(
            data['raw_data'][['start_date', 'dag_id', 'state', 'duration_sec']].sort_values('start_date', ascending=False),
            column_config={
                "start_date": st.column_config.DatetimeColumn("Date Début", format="DD/MM HH:mm"),
                "duration_sec": st.column_config.NumberColumn("Durée (s)", format="%.1f")
            },
            width='stretch',
            hide_index=True
        )

if __name__ == "__main__":
    show()