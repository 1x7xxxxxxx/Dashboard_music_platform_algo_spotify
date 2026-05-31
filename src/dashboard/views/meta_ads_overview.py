import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.dashboard.utils import get_db_connection
from src.dashboard.utils.charts import pareto_spend_cpr
from src.dashboard.auth import get_artist_id, is_admin

# Meta gender targeting codes → labels (empty = no restriction = everyone).
_GENDER_LABELS = {'1': 'Hommes', '2': 'Femmes', '': 'Tous', '1,2': 'Tous', '2,1': 'Tous'}
# Adset targeting attribute the user can slice performance by (#9 Ciblage vs perf).
_TARGETING_DIMS = {
    "Objectif d'optimisation": "optimization_goal",
    "Genre ciblé": "gender",
    "Plateformes": "publisher_platforms",
    "Tranche d'âge": "age_band",
}

def show():
    st.title("📱 Méta Ads - Analyse Stratégique")

    # --- 1. CONNEXION & FILTRES ---
    db = get_db_connection()
    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin():
            st.error("Session invalide."); st.stop()
        artist_id = 1  # admin: defaults to artist 1 — full cross-tenant view in Admin panel

    try:
        _show_meta_ads(db, artist_id)
    finally:
        db.close()


def _show_meta_ads(db, artist_id):
    try:
        # Sort campaigns by launch date (MIN(day_date)) descending — most recent release first.
        # LEFT JOIN keeps campaigns without day-level data, sorted to the end via NULLS LAST.
        df_list = db.fetch_df(
            """
            SELECT p.campaign_name, MIN(d.day_date) AS first_day
            FROM meta_insights_performance p
            LEFT JOIN meta_insights_performance_day d
              ON d.campaign_name = p.campaign_name AND d.artist_id = p.artist_id
            WHERE p.artist_id = %s
            GROUP BY p.campaign_name
            ORDER BY first_day DESC NULLS LAST, p.campaign_name DESC
            """,
            (artist_id,)
        )
        all_campaigns = df_list['campaign_name'].dropna().tolist()
    except Exception as e:
        st.error(f"Erreur connexion BDD: {e}")
        return

    # Default selection: latest release (most recently launched campaign).
    default_main = all_campaigns[:1]

    # --- FILTRE PRINCIPAL ---
    st.subheader("🎯 Périmètre d'Analyse")
    selected_campaigns = st.multiselect(
        "Sélectionnez les campagnes à analyser :",
        options=all_campaigns,
        default=default_main
    )

    # CRITICAL-04: selected_campaigns values come from a DB-sourced multiselect.
    # The IN-clause placeholder count is derived from len() (code-controlled).
    # Values are always passed as %s parameters — never interpolated into the SQL string.
    # Validate that selected_campaigns is a subset of all_campaigns (allowlist check).
    selected_campaigns = [c for c in selected_campaigns if c in set(all_campaigns)]
    _campaign_in = (
        " AND campaign_name IN ({})".format(','.join(['%s'] * len(selected_campaigns)))
        if selected_campaigns else ""
    )
    params = (artist_id, *selected_campaigns)

    # ==============================================================================
    # 🟢 SECTION 1 : VUE MACRO (KPIS)
    # ==============================================================================

    query_perf = (
        "SELECT campaign_name, spend, results, custom_conversions, lp_views, "
        "impressions, reach, frequency, link_clicks "
        f"FROM meta_insights_performance WHERE artist_id = %s{_campaign_in} ORDER BY spend DESC"
    )
    df_perf = db.fetch_df(query_perf, params)

    query_eng = (
        "SELECT campaign_name, page_interactions, post_reactions, comments, saves, shares "
        f"FROM meta_insights_engagement WHERE artist_id = %s{_campaign_in}"
    )
    df_eng = db.fetch_df(query_eng, params)

    if not df_perf.empty:
        # Nettoyage
        for c in ['spend', 'results', 'custom_conversions', 'lp_views', 'impressions', 'link_clicks']:
            df_perf[c] = pd.to_numeric(df_perf[c], errors='coerce').fillna(0)

        # Totaux
        tot_spend   = df_perf['spend'].sum()
        tot_conv    = df_perf['custom_conversions'].sum()
        tot_lp      = df_perf['lp_views'].sum()
        tot_clicks  = df_perf['link_clicks'].sum()
        tot_impr    = df_perf['impressions'].sum()

        cpm = (tot_spend / tot_impr * 1000) if tot_impr > 0 else 0
        cpc = (tot_spend / tot_clicks)       if tot_clicks > 0 else 0
        cpr = (tot_spend / tot_conv)         if tot_conv > 0 else 0

        st.markdown("### 🚀 Performance Globale")
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Dépenses", f"{tot_spend:,.0f} €")
        k2.metric("Impressions", f"{tot_impr:,.0f}")
        k3.metric("Clics Lien", f"{tot_clicks:,.0f}")
        k4.metric("CPM", f"{cpm:.2f} €")
        k5.metric("CPC", f"{cpc:.2f} €")
        k6.metric("CPR (Clics Spotify)", f"{cpr:.2f} €" if tot_conv > 0 else "— (CAPI requis)", delta_color="inverse")

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
    # 🔽 SECTION 1b : FUNNEL HYPEDDIT (Impressions → Clics → LP → Spotify)
    # ==============================================================================
    st.subheader("🔽 Funnel de conversion Hypeddit")

    if not df_perf.empty:
        has_capi = tot_conv > 0
        if not has_capi:
            st.info(
                "Les clics Spotify (CAPI) seront visibles ici une fois le "
                "Conversions API configuré sur Hypeddit. "
                "Les 3 premières étapes du funnel sont déjà disponibles."
            )

        # Taux de conversion à chaque étape
        ctr_pct       = (tot_clicks / tot_impr * 100) if tot_impr > 0 else 0
        lp_open_pct   = (tot_lp / tot_clicks * 100)   if tot_clicks > 0 else 0
        spotify_pct   = (tot_conv / tot_lp * 100)      if tot_lp > 0 else 0

        # KPIs d'étape
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Impressions",   f"{tot_impr:,.0f}")
        f2.metric("Clics sur pub", f"{tot_clicks:,.0f}", help=f"CTR : {ctr_pct:.2f} %")
        f3.metric("Vues LP",       f"{tot_lp:,.0f}",     help=f"LP open rate : {lp_open_pct:.1f} % des clics")
        if has_capi:
            f4.metric("Clics Spotify", f"{tot_conv:,.0f}", help=f"Taux LP→Spotify : {spotify_pct:.1f} %")
        else:
            f4.metric("Clics Spotify", "— (CAPI)")

        # Funnel chart
        funnel_labels  = ["Impressions", "Clics pub", "Vues LP"]
        funnel_values  = [tot_impr, tot_clicks, tot_lp]
        funnel_colors  = ["#636efa", "#00cc96", "#EF553B"]
        if has_capi:
            funnel_labels.append("Clics Spotify")
            funnel_values.append(tot_conv)
            funnel_colors.append("#1DB954")

        fig_funnel = go.Figure(go.Funnel(
            y=funnel_labels,
            x=funnel_values,
            textinfo="value+percent initial",
            marker=dict(color=funnel_colors),
            connector=dict(line=dict(color="royalblue", dash="dot", width=2)),
        ))
        fig_funnel.update_layout(
            height=320,
            margin=dict(t=10, b=10, l=0, r=0),
        )
        st.plotly_chart(fig_funnel, width="stretch")

        # Taux de conversion par campagne
        if len(df_perf) > 1:
            df_rates = df_perf[['campaign_name', 'impressions', 'link_clicks', 'lp_views', 'custom_conversions', 'spend']].copy()
            df_rates['CTR (%)']          = (df_rates['link_clicks'] / df_rates['impressions'] * 100).round(2)
            df_rates['LP open (%)']      = (df_rates['lp_views'] / df_rates['link_clicks'] * 100).where(df_rates['link_clicks'] > 0).round(1)
            df_rates['Spotify click (%)'] = (df_rates['custom_conversions'] / df_rates['lp_views'] * 100).where(df_rates['lp_views'] > 0).round(1)
            df_rates['CPR (€)']          = (df_rates['spend'] / df_rates['custom_conversions']).where(df_rates['custom_conversions'] > 0).round(2)

            display_cols = ['campaign_name', 'impressions', 'link_clicks', 'lp_views',
                            'CTR (%)', 'LP open (%)', 'Spotify click (%)', 'CPR (€)']
            if has_capi:
                display_cols.insert(4, 'custom_conversions')

            st.dataframe(
                df_rates[display_cols].rename(columns={
                    'campaign_name': 'Campagne',
                    'impressions': 'Impressions',
                    'link_clicks': 'Clics pub',
                    'lp_views': 'Vues LP',
                    'custom_conversions': 'Clics Spotify',
                }),
                width="stretch",
                hide_index=True,
            )

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
            name='Résultats natifs Meta (selon objectif)', marker_color='rgba(0, 63, 92, 0.9)',
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
            yaxis=dict(title=dict(text="Budget (€)", font=dict(color="#ff6361"))),
            yaxis2=dict(title=dict(text="Volumes", font=dict(color="#003f5c")), anchor="x", overlaying="y", side="right"),
            yaxis3=dict(title=dict(text="Ratios (€)", font=dict(color="#bc5090")), anchor="free", overlaying="y", side="right", position=0.92),
            legend=dict(orientation="h", y=1.12),
            hovermode="x unified",
            barmode='group'
        )
        st.plotly_chart(fig, width="stretch")

    st.markdown("---")

    # ==============================================================================
    # 📊 SECTION 2b : COMPARAISON MULTI-MÉTRIQUES PAR CAMPAGNE
    # ==============================================================================
    st.subheader("📊 Comparaison multi-métriques par campagne")
    st.caption("Une rangée par métrique, échelles indépendantes. Cliquez une entrée de légende pour la masquer.")

    if not df_perf.empty:
        df_multi = df_perf[['campaign_name', 'spend', 'impressions',
                            'link_clicks', 'lp_views', 'custom_conversions']].copy()
        if not df_eng.empty:
            df_multi = df_multi.merge(
                df_eng[['campaign_name', 'saves', 'shares', 'page_interactions']],
                on='campaign_name', how='left',
            )
        else:
            df_multi[['saves', 'shares', 'page_interactions']] = 0
        df_multi = df_multi.fillna(0)

        metric_labels = {
            'spend':              'Dépenses (€)',
            'impressions':        'Impressions',
            'link_clicks':        'Clics pub',
            'lp_views':           'Vues LP',
            'custom_conversions': 'Clics Spotify',
            'saves':              'Saves',
            'shares':             'Shares',
            'page_interactions':  'Interactions',
        }
        df_multi = df_multi.rename(columns=metric_labels)
        df_long = df_multi.melt(
            id_vars='campaign_name',
            value_vars=list(metric_labels.values()),
            var_name='Métrique',
            value_name='Valeur',
        )

        fig_multi = px.bar(
            df_long,
            x='campaign_name', y='Valeur',
            facet_row='Métrique',
            color='Métrique',
            category_orders={'Métrique': list(metric_labels.values())},
            height=130 * len(metric_labels),
            labels={'campaign_name': 'Campagne'},
        )
        # Independent Y-axis per metric so volumes (impressions) and small counts (shares) both visible
        fig_multi.update_yaxes(matches=None, showticklabels=True, title_text="")
        # Clean facet labels: "Métrique=Dépenses (€)" → "Dépenses (€)"
        fig_multi.for_each_annotation(lambda a: a.update(text=a.text.split("=", 1)[-1]))
        fig_multi.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=40, b=40, l=10, r=10),
            bargap=0.3,
        )
        st.plotly_chart(fig_multi, width="stretch")
    else:
        st.info("Aucune donnée de campagne pour les filtres sélectionnés.")

    st.markdown("---")

    # ==============================================================================
    # ⏳ SECTION 3 : ÉVOLUTION TEMPORELLE
    # ==============================================================================
    st.subheader("⏳ Évolution Temporelle (Budget vs Résultat vs CPR)")

    query_day = (
        "SELECT day_date, SUM(spend) as spend, SUM(results) as results, "
        "SUM(custom_conversions) as custom_conversions "
        f"FROM meta_insights_performance_day WHERE artist_id = %s{_campaign_in} "
        "GROUP BY day_date ORDER BY day_date ASC"
    )
    df_day = db.fetch_df(query_day, params)

    if not df_day.empty:
        for c in ['spend', 'results', 'custom_conversions']:
            df_day[c] = pd.to_numeric(df_day[c], errors='coerce').fillna(0)
        df_day['cpr'] = (df_day['spend'] / df_day['custom_conversions']).where(df_day['custom_conversions'] > 0).fillna(0)

        fig_time = go.Figure()
        fig_time.add_trace(go.Bar(x=df_day['day_date'], y=df_day['spend'], name='Dépenses (€)', marker_color='rgba(255, 99, 97, 0.4)', yaxis='y'))
        fig_time.add_trace(go.Scatter(x=df_day['day_date'], y=df_day['custom_conversions'], name='Clics Spotify', mode='lines', line=dict(color='#1DB954', width=3), yaxis='y2'))
        fig_time.add_trace(go.Scatter(x=df_day['day_date'], y=df_day['cpr'], name='CPR (€)', mode='lines+markers', line=dict(color='#bc5090', width=2, dash='dot'), yaxis='y3'))

        fig_time.update_layout(
            height=500, title="Dynamique Quotidienne", hovermode="x unified",
            xaxis=dict(domain=[0, 0.9]),
            yaxis=dict(title=dict(text="Budget (€)", font=dict(color="#ff6361")), showgrid=False),
            yaxis2=dict(title=dict(text="Résultats", font=dict(color="#003f5c")), anchor="x", overlaying="y", side="right", showgrid=False),
            yaxis3=dict(title=dict(text="CPR (€)", font=dict(color="#bc5090")), anchor="free", overlaying="y", side="right", position=0.95, showgrid=False),
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig_time, width="stretch")
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

    query_country = (
        "SELECT country, SUM(spend) as spend, SUM(results) as results "
        f"FROM meta_insights_performance_country WHERE artist_id = %s{_campaign_in} GROUP BY country"
    )
    df_country = db.fetch_df(query_country, params)

    query_place = (
        "SELECT placement, SUM(spend) as spend, SUM(results) as results "
        f"FROM meta_insights_performance_placement WHERE artist_id = %s{_campaign_in} GROUP BY placement"
    )
    df_place = db.fetch_df(query_place, params)

    query_age = (
        "SELECT age_range, SUM(spend) as spend, SUM(results) as results "
        f"FROM meta_insights_performance_age WHERE artist_id = %s{_campaign_in} GROUP BY age_range"
    )
    df_age = db.fetch_df(query_age, params)

    c1, c2 = st.columns(2)
    with c1:
        if fig_country := create_pareto_chart(df_country, 'country', "Pays (Top Dépenses)"): st.plotly_chart(fig_country, width="stretch")
    with c2:
        if fig_place := create_pareto_chart(df_place, 'placement', "Placements"): st.plotly_chart(fig_place, width="stretch")

    if fig_age := create_pareto_chart(df_age, 'age_range', "Performance par Âge"): st.plotly_chart(fig_age, width="stretch")

    st.markdown("---")

    # ==============================================================================
    # 📋 SECTION 5 : DONNÉES BRUTES (TABLEAU COMPLET)
    # ==============================================================================
    st.subheader("🗃️ Tableau Récapitulatif")

    # ⚠️ %% in CTR column alias avoids Python IndexError in format strings
    _campaign_in_p = (
        f" AND p.campaign_name IN ({','.join(['%s'] * len(selected_campaigns))})"
        if selected_campaigns else ""
    )
    query_full = (
        'SELECT p.campaign_name, p.spend as "Dépenses", p.custom_conversions as "Clics Spotify",'
        ' p.lp_views as "Vues LP", p.link_clicks as "Clics pub",'
        ' p.cpr as "CPR", p.impressions as "Impressions", p.cpm as "CPM",'
        ' p.ctr as "CTR (%%)",'
        ' e.saves as "Saves", e.shares as "Shares", e.page_interactions as "Interactions",'
        ' p.collected_at as "Mise à jour"'
        " FROM meta_insights_performance p"
        " LEFT JOIN meta_insights_engagement e ON p.campaign_name = e.campaign_name"
        f" WHERE p.artist_id = %s{_campaign_in_p}"
        " ORDER BY p.spend DESC"
    )
    df_full = db.fetch_df(query_full, params)

    if not df_full.empty:
        st.dataframe(
            df_full.style.format({
                "Dépenses": "{:,.2f} €", "CPR": "{:,.2f} €", "CPM": "{:,.2f} €",
                "CTR (%)": "{:,.2f}",
                "Saves": "{:,.0f}", "Shares": "{:,.0f}", "Interactions": "{:,.0f}",
                "Clics Spotify": "{:,.0f}", "Clics pub": "{:,.0f}",
            }, na_rep="—"),
            width="stretch",
        )

    # ==============================================================================
    # 🎯 SECTION 6 : CIBLAGE vs PERFORMANCE (#9) — quel ciblage adset performe
    # ==============================================================================
    st.markdown("---")
    st.subheader("🎯 Ciblage vs Performance")
    st.caption("Dépense & CPR agrégés par attribut de ciblage des ad sets (résultats ad-level).")

    df_tgt = db.fetch_df(
        """
        SELECT s.optimization_goal, s.gender, s.publisher_platforms,
               s.age_min, s.age_max,
               SUM(mi.spend) AS spend, SUM(mi.conversions) AS results
        FROM meta_adsets s
        JOIN meta_ads a ON a.adset_id = s.adset_id
        JOIN meta_insights mi ON mi.ad_id = a.ad_id
        WHERE s.artist_id = %s
        GROUP BY s.optimization_goal, s.gender, s.publisher_platforms, s.age_min, s.age_max
        """,
        (artist_id,),
    )
    if df_tgt.empty:
        st.info("Aucune donnée de ciblage ad set disponible.")
    else:
        df_tgt['gender'] = df_tgt['gender'].fillna('').astype(str).map(
            lambda g: _GENDER_LABELS.get(g, g or 'Tous'))
        df_tgt['publisher_platforms'] = df_tgt['publisher_platforms'].fillna('').replace('', 'Toutes')
        df_tgt['optimization_goal'] = df_tgt['optimization_goal'].fillna('Inconnu')
        df_tgt['age_band'] = (
            df_tgt['age_min'].fillna('').astype(str) + '–' + df_tgt['age_max'].fillna('').astype(str)
        ).str.strip('–').replace('', 'Non spécifié')

        dim_label = st.selectbox("Découper par", list(_TARGETING_DIMS.keys()), key="tgt_dim")
        dim_col = _TARGETING_DIMS[dim_label]
        agg = df_tgt.groupby(dim_col, as_index=False).agg(spend=('spend', 'sum'),
                                                          results=('results', 'sum'))
        fig_tgt = pareto_spend_cpr(agg, dim_col, f"Dépense & CPR par {dim_label.lower()}")
        if fig_tgt is not None:
            st.plotly_chart(fig_tgt, width="stretch")
