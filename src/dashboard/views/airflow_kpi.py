import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from src.dashboard.utils.airflow_monitor import AirflowMonitor
from src.dashboard.utils import get_db_connection

def get_quality_metrics():
    """Récupère les KPIs métiers depuis PostgreSQL."""
    db = get_db_connection()
    try:
        # On récupère la moyenne des 7 derniers jours par DAG
        query = """
            SELECT 
                dag_id,
                SUM(total_rows) as total_rows,
                SUM(invalid_rows) as total_invalid,
                SUM(anomalies_confirmed) as total_anomalies,
                AVG(alert_delay_seconds) as avg_alert_delay,
                COUNT(*) as days_count
            FROM etl_daily_metrics
            WHERE run_date >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY dag_id
        """
        df = db.fetch_df(query)
        return df
    except Exception as e:
        st.error(f"Erreur DB Metrics: {e}")
        return pd.DataFrame()
    finally:
        db.close()

def show():
    st.title("🏗️ Monitoring ETL & Qualité (Global)")
    st.markdown("---")
    
    # 1. Récupération des Données (Airflow + DB)
    monitor = AirflowMonitor()
    
    with st.spinner("Analyse des performances (API + BDD)..."):
        # A. Données Techniques (Airflow)
        af_data = monitor.get_kpis()
        
        # B. Données Métiers (Postgres)
        df_quality = get_quality_metrics()
    
    if af_data is None:
        st.error("❌ API Airflow injoignable.")
        return

    df_runs = af_data['raw_data']
    
    # =========================================================================
    # 2. CALCUL DES KPIS PAR DAG
    # =========================================================================
    if not df_runs.empty:
        # Agrégation technique par DAG
        stats_tech = []
        for dag_id in df_runs['dag_id'].unique():
            subset = df_runs[df_runs['dag_id'] == dag_id]
            
            total = len(subset)
            success = len(subset[subset['state'] == 'success'])
            duration = subset['duration_sec'].mean()
            
            # Uptime API = Taux de succès technique
            uptime = (success / total * 100) if total > 0 else 0
            
            stats_tech.append({
                'dag_id': dag_id,
                'Taux Succès': uptime,
                'Temps Exec Moyen (s)': duration,
                'Uptime API': uptime # On considère l'API "UP" si le DAG réussit
            })
            
        df_tech = pd.DataFrame(stats_tech)
        
        # Fusion avec les données Qualité (SQL)
        if not df_quality.empty:
            df_final = pd.merge(df_tech, df_quality, on='dag_id', how='left').fillna(0)
            
            # Calcul des % Qualité
            df_final['% Invalide'] = df_final.apply(
                lambda x: (x['total_invalid'] / x['total_rows'] * 100) if x['total_rows'] > 0 else 0, axis=1
            )
            df_final['Taux Anomalie'] = df_final.apply(
                lambda x: (x['total_anomalies'] / x['total_rows'] * 100) if x['total_rows'] > 0 else 0, axis=1
            )
        else:
            # Si pas de données DB, on met des 0
            df_final = df_tech
            df_final['% Invalide'] = 0.0
            df_final['Taux Anomalie'] = 0.0
            df_final['avg_alert_delay'] = 0.0

        # Renommage final
        df_display = df_final[[
            'dag_id', 
            'Taux Succès', 
            'Temps Exec Moyen (s)', 
            '% Invalide', 
            'Taux Anomalie', 
            'Uptime API', 
            'avg_alert_delay'
        ]].rename(columns={'avg_alert_delay': 'Délai Moy. Alerte (s)'})

        # =========================================================================
        # 3. AFFICHAGE TABLEAU DE BORD
        # =========================================================================
        
        # A. KPIs GLOBAUX
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Exécutions (24h)", af_data['total_runs_24h'])
        c2.metric("Taux Succès Global", f"{af_data['success_rate']:.1f}%")
        
        avg_inv = df_display['% Invalide'].mean()
        c3.metric("% Invalide Moyen", f"{avg_inv:.2f}%", delta_color="inverse")
        
        failures = af_data['failed_count']
        c4.metric("Échecs (7j)", failures, delta_color="inverse")
        
        st.markdown("---")
        
        # B. TABLEAU DÉTAILLÉ PAR DAG
        st.subheader("📊 Performance par Pipeline")
        
        # Mise en forme conditionnelle
        st.dataframe(
            df_display.set_index('dag_id'),
            column_config={
                "Taux Succès": st.column_config.ProgressColumn(
                    "Succès", format="%.1f%%", min_value=0, max_value=100
                ),
                "Uptime API": st.column_config.ProgressColumn(
                    "Dispo API", format="%.1f%%", min_value=0, max_value=100
                ),
                "% Invalide": st.column_config.NumberColumn(
                    format="%.2f %%"
                ),
                "Temps Exec Moyen (s)": st.column_config.NumberColumn(
                    format="%.1f s"
                ),
                "Délai Moy. Alerte (s)": st.column_config.NumberColumn(
                    format="%d s"
                )
            },
            width='stretch'
        )
        
        # C. TIMELINE GANTT
        st.markdown("---")
        st.subheader("⏱️ Chronologie des dernières exécutions")
        
        gantt_df = df_runs.head(20).copy()
        fig = px.timeline(
            gantt_df, 
            x_start="start_date", 
            x_end="end_date", 
            y="dag_id", 
            color="state",
            color_discrete_map={"success": "#00CC96", "failed": "#EF553B", "running": "#636EFA"},
            hover_data=["duration_sec"]
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, width='stretch')

    else:
        st.info("Aucune donnée d'exécution trouvée dans Airflow.")

if __name__ == "__main__":
    show()