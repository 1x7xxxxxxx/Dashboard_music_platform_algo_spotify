import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
from src.dashboard.utils import get_db_connection

def show():
    st.title("📱 META ADS - Analyse CSV")
    st.markdown("---")
    
    # Filtres Globaux
    col1, col2 = st.columns(2)
    # ✅ CORRECTION DATE : On remonte à 2022 pour inclure vos fichiers historiques
    start_date = col1.date_input("📅 Date début", value=date(2022, 1, 1))
    end_date = col2.date_input("📅 Date fin", value=datetime.now().date())
    
    db = get_db_connection()
    
    try:
        # Récupération pour le filtre campagne
        df_list = db.fetch_df("SELECT DISTINCT campaign_name FROM view_meta_global_perf")
        
        if not df_list.empty:
            all_campaigns = ["Toutes"] + sorted(df_list['campaign_name'].dropna().tolist())
        else:
            all_campaigns = ["Toutes"]
            
        selected_campaign = st.selectbox("Filtrer par Campagne", all_campaigns)
        
        # Clause WHERE dynamique
        where_clause = "WHERE date_start >= %s AND date_stop <= %s"
        params = [start_date, end_date]
        
        if selected_campaign != "Toutes":
            where_clause += " AND campaign_name = %s"
            params.append(selected_campaign)

        # --- TABS ---
        tab1, tab2, tab3, tab4 = st.tabs(["📈 Général", "🌍 Géographie", "👥 Démographie", "📱 Placements"])

        # 1. ONGLET GÉNÉRAL
        with tab1:
            query = f"""
                SELECT 
                    campaign_name, 
                    SUM(spend) as spend, 
                    SUM(clicks) as clicks, 
                    SUM(impressions) as impressions, 
                    SUM(results) as conversions
                FROM view_meta_global_perf {where_clause}
                GROUP BY campaign_name 
                ORDER BY spend DESC
            """
            df = db.fetch_df(query, tuple(params))
            
            if not df.empty:
                # Correction Types (Decimal -> Float)
                numeric_cols = ['spend', 'clicks', 'impressions', 'conversions']
                for col in numeric_cols:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

                # KPIs
                total_spend = df['spend'].sum()
                total_clicks = df['clicks'].sum()
                total_res = df['conversions'].sum()
                avg_cpr = total_spend / total_res if total_res > 0 else 0
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("💰 Dépenses", f"{total_spend:,.2f} €")
                c2.metric("🖱️ Clics", f"{int(total_clicks):,}")
                c3.metric("🎯 Résultats", f"{int(total_res):,}")
                c4.metric("📉 Coût/Résultat", f"{avg_cpr:.2f} €")
                
                # Graphique
                st.subheader("Performance par Campagne")
                df_chart = df[df['spend'] > 0].copy()
                
                if not df_chart.empty:
                    fig = px.scatter(
                        df_chart, 
                        x="spend", 
                        y="clicks", 
                        size="spend", 
                        color="campaign_name",
                        hover_data=['conversions'], 
                        title="Dépenses vs Clics"
                    )
                    st.plotly_chart(fig, width='stretch')
                
                # ✅ CORRECTION WARNING : width="stretch"
                st.dataframe(
                    df, 
                    column_config={
                        "campaign_name": "Campagne",
                        "spend": st.column_config.NumberColumn("Dépenses", format="%.2f €"),
                        "clicks": st.column_config.NumberColumn("Clics"),
                        "impressions": st.column_config.NumberColumn("Impressions"),
                        "conversions": st.column_config.NumberColumn("Résultats"),
                    },
                    width="stretch", 
                    hide_index=True
                )
            else:
                st.info("Aucune donnée générale. Vérifiez la période de dates ci-dessus.")

        # 2. ONGLET GÉOGRAPHIE
        with tab2:
            geo_query = "SELECT * FROM view_meta_country_perf"
            if selected_campaign != "Toutes":
                geo_query += " WHERE campaign_name = %s"
                df_geo = db.fetch_df(geo_query, (selected_campaign,))
            else:
                df_geo = db.fetch_df(geo_query)

            if not df_geo.empty:
                df_geo['total_clicks'] = pd.to_numeric(df_geo['total_clicks']).fillna(0).astype(float)
                
                st.subheader("Répartition par Pays")
                fig_map = px.choropleth(df_geo, locations="country", locationmode="country names",
                                        color="total_clicks", hover_name="country",
                                        title="Clics par Pays", color_continuous_scale="Viridis")
                st.plotly_chart(fig_map, width='stretch')
            else:
                st.info("Pas de données géographiques.")

        # 3. ONGLET DÉMOGRAPHIE
        with tab3:
            age_query = "SELECT * FROM view_meta_age_perf"
            if selected_campaign != "Toutes":
                age_query += " WHERE campaign_name = %s"
                df_age = db.fetch_df(age_query, (selected_campaign,))
            else:
                df_age = db.fetch_df(age_query)

            if not df_age.empty:
                for col in ['total_clicks', 'total_results']:
                    df_age[col] = pd.to_numeric(df_age[col]).fillna(0).astype(float)

                st.subheader("Performance par Âge")
                df_age = df_age.sort_values("age_range")
                fig_age = px.bar(df_age, x="age_range", y=["total_clicks", "total_results"], 
                                 barmode="group", title="Clics et Résultats par Âge")
                st.plotly_chart(fig_age, width='stretch')
            else:
                st.info("Pas de données démographiques.")

        # 4. ONGLET PLACEMENTS
        with tab4:
            plat_query = "SELECT * FROM view_meta_placement_perf"
            if selected_campaign != "Toutes":
                plat_query += " WHERE campaign_name = %s"
                df_plat = db.fetch_df(plat_query, (selected_campaign,))
            else:
                df_plat = db.fetch_df(plat_query)

            if not df_plat.empty:
                df_plat['total_spend'] = pd.to_numeric(df_plat['total_spend']).fillna(0).astype(float)
                df_plat['total_clicks'] = pd.to_numeric(df_plat['total_clicks']).fillna(0).astype(float)

                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("Par Plateforme")
                    df_pie = df_plat.groupby('platform')['total_spend'].sum().reset_index()
                    fig_pie = px.pie(df_pie, values='total_spend', names='platform', title="Dépenses par Plateforme")
                    st.plotly_chart(fig_pie, width='stretch')
                with c2:
                    st.subheader("Par Placement")
                    df_sun = df_plat[df_plat['total_clicks'] > 0]
                    if not df_sun.empty:
                        fig_sun = px.sunburst(df_sun, path=['platform', 'placement'], values='total_clicks', title="Clics par Placement")
                        st.plotly_chart(fig_sun, width='stretch')
            else:
                st.info("Pas de données de placement.")

    except Exception as e:
        st.error(f"Une erreur est survenue : {e}")
        
    finally:
        db.close()

if __name__ == "__main__":
    show()