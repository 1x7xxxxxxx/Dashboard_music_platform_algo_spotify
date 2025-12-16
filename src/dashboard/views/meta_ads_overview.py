import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.dashboard.utils import get_db_connection

def show():
    st.title("📱 Méta Ads - Analyse Stratégique")

    # --- 1. CONNEXION & FILTRES ---
    db = get_db_connection()
    
    try:
        df_list = db.fetch_df("SELECT DISTINCT campaign_name FROM meta_insights_performance ORDER BY campaign_name DESC")
        all_campaigns = df_list['campaign_name'].dropna().tolist()
    except Exception as e:
        st.error(f"Erreur connexion BDD: {e}")
        return

    # Configuration des sélections par défaut
    default_main = [all_campaigns[1]] if len(all_campaigns) > 1 else all_campaigns[:1]

    # --- FILTRE PRINCIPAL ---
    st.subheader("🎯 Périmètre d'Analyse")
    selected_campaigns = st.multiselect(
        "Sélectionnez les campagnes à analyser :",
        options=all_campaigns,
        default=default_main
    )

    # Construction de la clause WHERE
    if selected_campaigns:
        placeholders = ', '.join(['%s'] * len(selected_campaigns))
        where_clause = f"WHERE campaign_name IN ({placeholders})"
        params = tuple(selected_campaigns)
    else:
        where_clause = ""
        params = ()

    # ==============================================================================
    # 🟢 SECTION 1 : VUE MACRO (KPIS)
    # ==============================================================================
    
    query_perf = f"""
        SELECT campaign_name, spend, results, impressions, reach, frequency, link_clicks 
        FROM meta_insights_performance {where_clause} ORDER BY spend DESC
    """
    df_perf = db.fetch_df(query_perf, params)

    query_eng = f"""
        SELECT campaign_name, page_interactions, post_reactions, comments, saves, shares 
        FROM meta_insights_engagement {where_clause}
    """
    df_eng = db.fetch_df(query_eng, params)

    if not df_perf.empty:
        # Nettoyage
        for c in ['spend', 'results', 'impressions', 'link_clicks']: 
            df_perf[c] = pd.to_numeric(df_perf[c], errors='coerce').fillna(0)
        
        # Totaux
        tot_spend = df_perf['spend'].sum()
        tot_res = df_perf['results'].sum()
        tot_clicks = df_perf['link_clicks'].sum()
        tot_impr = df_perf['impressions'].sum()
        
        cpm = (tot_spend / tot_impr * 1000) if tot_impr > 0 else 0
        cpc = (tot_spend / tot_clicks) if tot_clicks > 0 else 0
        cpr = (tot_spend / tot_res) if tot_res > 0 else 0

        st.markdown("### 🚀 Performance Globale")
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Dépenses", f"{tot_spend:,.0f} €")
        k2.metric("Impressions", f"{tot_impr:,.0f}")
        k3.metric("Clics Lien", f"{tot_clicks:,.0f}")
        k4.metric("CPM", f"{cpm:.2f} €")
        k5.metric("CPC", f"{cpc:.2f} €")
        k6.metric("CPR (Coût/Résultat)", f"{cpr:.2f} €", delta_color="inverse")

        # Engagement
        if not df_eng.empty:
            for c in ['saves', 'shares', 'page_interactions']: df_eng[c] = pd.to_numeric(df_eng[c], errors='coerce').fillna(0)
            st.markdown("##### ❤️ Engagement")
            e1, e2, e3 = st.columns(3)
            e1.metric("💾 Saves", f"{df_eng['saves'].sum():,.0f}")
            e2.metric("🔄 Shares", f"{df_eng['shares'].sum():,.0f}")
            e3.metric("⚡ Interactions Totales", f"{df_eng['page_interactions'].sum():,.0f}")

    st.markdown("---")

    # ==============================================================================
    # 📈 SECTION 2 : PERFORMANCE PAR CAMPAGNE (GRAPHIQUE PRINCIPAL)
    # ==============================================================================
    st.subheader("📊 Performance par Campagne")
    
    if not df_perf.empty:
        df_chart = df_perf.copy()
        if not df_eng.empty:
            df_chart = pd.merge(df_chart, df_eng[['campaign_name', 'page_interactions']], on='campaign_name', how='left').fillna(0)
        else:
            df_chart['page_interactions'] = 0

        # Ratios
        df_chart['cpr'] = df_chart.apply(lambda x: x['spend']/x['results'] if x['results']>0 else 0, axis=1)
        df_chart['cpm'] = df_chart.apply(lambda x: x['spend']/x['impressions']*1000 if x['impressions']>0 else 0, axis=1)
        df_chart['cpc'] = df_chart.apply(lambda x: x['spend']/x['link_clicks'] if x['link_clicks']>0 else 0, axis=1)

        fig = go.Figure()

        # Axe Y1 (Gauche - Barres)
        fig.add_trace(go.Bar(
            x=df_chart['campaign_name'], y=df_chart['spend'],
            name='Budget (€)', marker_color='rgba(255, 99, 97, 0.5)',
            yaxis='y', offsetgroup=1
        ))

        # Axe Y2 (Droite 1 - Barres fines)
        fig.add_trace(go.Bar(
            x=df_chart['campaign_name'], y=df_chart['results'],
            name='Résultats (Vol)', marker_color='rgba(0, 63, 92, 0.9)',
            yaxis='y2', offsetgroup=2
        ))
        fig.add_trace(go.Bar(
            x=df_chart['campaign_name'], y=df_chart['link_clicks'],
            name='Clics Lien', marker_color='rgba(88, 80, 141, 0.7)',
            yaxis='y2', offsetgroup=2, visible=True
        ))
        fig.add_trace(go.Bar(
            x=df_chart['campaign_name'], y=df_chart['page_interactions'],
            name='Interactions', marker_color='rgba(255, 166, 0, 0.7)',
            yaxis='y2', offsetgroup=2, visible=True
        ))
        
        # Impressions
        fig.add_trace(go.Scatter(
            x=df_chart['campaign_name'], y=df_chart['impressions'],
            name='Impressions', mode='markers', marker=dict(symbol='star', size=10, color='#333'),
            yaxis='y2', visible='legendonly' 
        ))

        # Axe Y3 (Droite 2 - Ratios) - ACTIVÉS
        fig.add_trace(go.Scatter(
            x=df_chart['campaign_name'], y=df_chart['cpr'],
            name='CPR (€)', mode='lines+markers+text',
            text=df_chart['cpr'].apply(lambda x: f"{x:.2f}€"), textposition="top center",
            line=dict(color='#bc5090', width=2), marker=dict(size=8),
            yaxis='y3', visible=True
        ))
        fig.add_trace(go.Scatter(
            x=df_chart['campaign_name'], y=df_chart['cpm'],
            name='CPM (€)', mode='lines+markers',
            line=dict(color='#ffa600', width=2), marker=dict(size=8),
            yaxis='y3', visible=True
        ))
        fig.add_trace(go.Scatter(
            x=df_chart['campaign_name'], y=df_chart['cpc'],
            name='CPC (€)', mode='lines+markers',
            line=dict(color='#ff6361', width=2), marker=dict(size=8),
            yaxis='y3', visible=True
        ))

        fig.update_layout(
            height=600,
            title="Vue 360° : Budget vs Volumes vs Ratios",
            xaxis=dict(title="Campagnes", domain=[0, 0.85]),
            yaxis=dict(title="Budget (€)", titlefont=dict(color="#ff6361")),
            yaxis2=dict(title="Volumes", titlefont=dict(color="#003f5c"), anchor="x", overlaying="y", side="right"),
            yaxis3=dict(title="Ratios (€)", titlefont=dict(color="#bc5090"), anchor="free", overlaying="y", side="right", position=0.92),
            legend=dict(orientation="h", y=1.12),
            hovermode="x unified",
            barmode='group'
        )
        st.plotly_chart(fig, width='stretch')

    st.markdown("---")

    # ==============================================================================
    # ⏳ SECTION 3 : ÉVOLUTION TEMPORELLE
    # ==============================================================================
    st.subheader("⏳ Évolution Temporelle (Budget vs Résultat vs CPR)")

    query_day = f"""
        SELECT day_date, SUM(spend) as spend, SUM(results) as results
        FROM meta_insights_performance_day
        {where_clause}
        GROUP BY day_date
        ORDER BY day_date ASC
    """
    df_day = db.fetch_df(query_day, params)

    if not df_day.empty:
        df_day['spend'] = pd.to_numeric(df_day['spend'], errors='coerce').fillna(0)
        df_day['results'] = pd.to_numeric(df_day['results'], errors='coerce').fillna(0)
        df_day['cpr'] = df_day.apply(lambda x: x['spend'] / x['results'] if x['results'] > 0 else 0, axis=1)

        fig_time = go.Figure()
        fig_time.add_trace(go.Bar(x=df_day['day_date'], y=df_day['spend'], name='Dépenses (€)', marker_color='rgba(255, 99, 97, 0.4)', yaxis='y'))
        fig_time.add_trace(go.Scatter(x=df_day['day_date'], y=df_day['results'], name='Résultats (Vol)', mode='lines', line=dict(color='#003f5c', width=3), yaxis='y2'))
        fig_time.add_trace(go.Scatter(x=df_day['day_date'], y=df_day['cpr'], name='CPR (€)', mode='lines+markers', line=dict(color='#bc5090', width=2, dash='dot'), yaxis='y3'))

        fig_time.update_layout(
            height=500, title="Dynamique Quotidienne", hovermode="x unified",
            xaxis=dict(domain=[0, 0.9]),
            yaxis=dict(title="Budget (€)", titlefont=dict(color="#ff6361"), showgrid=False),
            yaxis2=dict(title="Résultats", titlefont=dict(color="#003f5c"), anchor="x", overlaying="y", side="right", showgrid=False),
            yaxis3=dict(title="CPR (€)", titlefont=dict(color="#bc5090"), anchor="free", overlaying="y", side="right", position=0.95, showgrid=False),
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig_time, width='stretch')
    else:
        st.info("Pas de données temporelles.")

    st.markdown("---")

    # ==============================================================================
    # 🌍 SECTION 4 : PARETOS (PAYS, PLACEMENT, AGE)
    # ==============================================================================
    st.subheader("🎯 Répartitions & Efficacité (Pareto CPR)")

    def create_pareto_chart(df, x_col, title):
        if df.empty: return None
        df['spend'] = pd.to_numeric(df['spend'], errors='coerce').fillna(0)
        df['results'] = pd.to_numeric(df['results'], errors='coerce').fillna(0)
        df['cpr'] = df.apply(lambda x: x['spend'] / x['results'] if x['results'] > 0 else 0, axis=1)
        df = df.sort_values('spend', ascending=False).head(15)

        fig = go.Figure()
        fig.add_trace(go.Bar(x=df[x_col], y=df['spend'], name='Dépenses (€)', marker_color='rgba(0, 63, 92, 0.6)', yaxis='y'))
        fig.add_trace(go.Scatter(x=df[x_col], y=df['cpr'], name='CPR (€)', mode='lines+markers+text', text=df['cpr'].apply(lambda x: f"{x:.2f}€"), textposition="top center", line=dict(color='#ff6361', width=3), yaxis='y2'))

        fig.update_layout(
            title=title, yaxis=dict(title="Dépenses (€)", showgrid=False),
            yaxis2=dict(title="CPR (€)", overlaying='y', side='right', showgrid=False),
            showlegend=False, height=400
        )
        return fig

    query_country = f"SELECT country, SUM(spend) as spend, SUM(results) as results FROM meta_insights_performance_country {where_clause} GROUP BY country"
    df_country = db.fetch_df(query_country, params)
    
    query_place = f"SELECT placement, SUM(spend) as spend, SUM(results) as results FROM meta_insights_performance_placement {where_clause} GROUP BY placement"
    df_place = db.fetch_df(query_place, params)

    query_age = f"SELECT age_range, SUM(spend) as spend, SUM(results) as results FROM meta_insights_performance_age {where_clause} GROUP BY age_range"
    df_age = db.fetch_df(query_age, params)

    c1, c2 = st.columns(2)
    with c1:
        if fig_country := create_pareto_chart(df_country, 'country', "Pays (Top Dépenses)"): st.plotly_chart(fig_country, width='stretch')
    with c2:
        if fig_place := create_pareto_chart(df_place, 'placement', "Placements"): st.plotly_chart(fig_place, width='stretch')

    if fig_age := create_pareto_chart(df_age, 'age_range', "Performance par Âge"): st.plotly_chart(fig_age, width='stretch')

    st.markdown("---")

    # ==============================================================================
    # 📋 SECTION 5 : DONNÉES BRUTES (TABLEAU COMPLET)
    # ==============================================================================
    st.subheader("🗃️ Tableau Récapitulatif")
    
    # ⚠️ FIX : On remplace campaign_name par p.campaign_name pour éviter l'ambiguïté dans le JOIN
    where_clause_full = where_clause.replace("campaign_name", "p.campaign_name")
    
    # ⚠️ FIX : On double le % dans CTR (%%) pour éviter l'IndexError python
    query_full = f"""
        SELECT 
            p.campaign_name, p.spend as "Dépenses", p.results as "Résultats",
            p.cpr as "CPR", p.impressions as "Impressions", p.cpm as "CPM",
            p.link_clicks as "Clics", p.ctr as "CTR (%%)", 
            e.saves as "Saves", e.shares as "Shares", e.page_interactions as "Interactions",
            p.collected_at as "Mise à jour"
        FROM meta_insights_performance p
        LEFT JOIN meta_insights_engagement e ON p.campaign_name = e.campaign_name
        {where_clause_full}
        ORDER BY p.spend DESC
    """
    df_full = db.fetch_df(query_full, params)
    
    if not df_full.empty:
        st.dataframe(
            df_full.style.format({
                "Dépenses": "{:,.2f} €", "CPR": "{:,.2f} €", "CPM": "{:,.2f} €",
                "CTR (%)": "{:,.2f}", "Saves": "{:,.0f}", "Clics": "{:,.0f}",
                "Interactions": "{:,.0f}", "Shares": "{:,.0f}"
            }), 
            width='stretch'
        )