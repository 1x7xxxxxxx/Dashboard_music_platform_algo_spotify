import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.dashboard.utils import view_session
from src.dashboard.utils.meta_accounts import account_clause, account_scope
from src.dashboard.utils.charts import pareto_spend_cpr
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import secondary_analyses

# Meta gender targeting codes → labels (empty = no restriction = everyone).
_GENDER_LABELS = {'1': 'Hommes', '2': 'Femmes', '': 'Tous', '1,2': 'Tous', '2,1': 'Tous'}
_GENDER_SLUGS = {'Hommes': 'men', 'Femmes': 'women', 'Tous': 'all'}


def _gender_label(code: str) -> str:
    fr = _GENDER_LABELS.get(code, code or 'Tous')
    slug = _GENDER_SLUGS.get(fr)
    return t(f"meta_ads_overview.gender.{slug}", fr) if slug else fr
# Adset targeting attribute the user can slice performance by (#9 Ciblage vs perf).
_TARGETING_DIMS = {
    "Objectif d'optimisation": "optimization_goal",
    "Genre ciblé": "gender",
    "Plateformes": "publisher_platforms",
    "Tranche d'âge": "age_band",
}

def show():
    st.title(t("meta_ads_overview.title", "📱 Méta Ads - Analyse Stratégique"))

    # --- 1. CONNEXION & FILTRES ---
    with view_session() as (db, artist_id):
        _show_meta_ads(db, artist_id)
        # Les comptes d'agence se déclarent ICI depuis le 2026-09-05, plus dans
        # Credentials : cette page répond à « que veux-tu suivre », l'autre à
        # « comment te connecter ». Même mouvement que les titres SoundCloud
        # hébergés ailleurs, partis sur leur page de performance le 2026-09-04.
        from src.dashboard.views.meta_extra_accounts import render_extra_ad_accounts
        render_extra_ad_accounts(db, artist_id)


def _show_meta_ads(db, artist_id):
    # Le compte AVANT les campagnes : deux comptes peuvent porter la même campagne
    # « Release FR », donc la liste offerte dépend du compte choisi, jamais l'inverse.
    _account = account_scope(db, artist_id, key="meta_overview_acct")
    _acct, _acct_params = account_clause(_account)
    _acct_p, _ = account_clause(_account, "p.")
    _acct_s, _ = account_clause(_account, "s.")
    try:
        # Sort campaigns by launch date (MIN(day_date)) descending — most recent release first.
        # LEFT JOIN keeps campaigns without day-level data, sorted to the end via NULLS LAST.
        # `v_meta_campaign_daily` (migration 109) porte déjà le jour : la jointure
        # vers la table quotidienne servait uniquement à le retrouver.
        df_list = db.fetch_df(
            """
            SELECT campaign_name, MIN(day) AS first_day
            FROM v_meta_campaign_daily
            WHERE artist_id = %s"""
            f"{_acct}"
            """
            GROUP BY campaign_name
            ORDER BY first_day DESC NULLS LAST, campaign_name DESC
            """,
            (artist_id, *_acct_params)
        )
        all_campaigns = df_list['campaign_name'].dropna().tolist()
    except Exception as e:
        st.error(t("meta_ads_overview.db_error", "Erreur connexion BDD: {e}").format(e=e))
        return

    # Default selection: latest release (most recently launched campaign).
    default_main = all_campaigns[:1]

    # --- FILTRE PRINCIPAL ---
    st.subheader(t("meta_ads_overview.scope", "🎯 Périmètre d'Analyse"))
    selected_campaigns = st.multiselect(
        t("meta_ads_overview.select_campaigns", "Sélectionnez les campagnes à analyser :"),
        options=all_campaigns,
        default=default_main
    )

    # CRITICAL-04: selected_campaigns values come from a DB-sourced multiselect.
    # The IN-clause placeholder count is derived from len() (code-controlled).
    # Values are always passed as %s parameters — never interpolated into the SQL string.
    # Validate that selected_campaigns is a subset of all_campaigns (allowlist check).
    selected_campaigns = [c for c in selected_campaigns if c in set(all_campaigns)]
    # Le filtre de compte se colle AVANT celui des campagnes : ses paramètres se
    # placent donc juste après `artist_id`.
    _campaign_in = _acct + (
        " AND campaign_name IN ({})".format(','.join(['%s'] * len(selected_campaigns)))
        if selected_campaigns else ""
    )
    params = (artist_id, *_acct_params, *selected_campaigns)

    # ==============================================================================
    # 🟢 SECTION 1 : VUE MACRO (KPIS)
    # ==============================================================================

    # ⚠️ Les totaux de cette page se calculent EN PANDAS (`df_perf['spend'].sum()`).
    # Aucun garde SQL ne peut les voir : il n'y a pas de `SUM(` dans la requête. La
    # tuile « Dépenses » affichait donc 6 165,65 € pour l'artiste 1 là où la couche
    # or en compte 3 087,82 — `meta_insights_performance` porte, en plus de ses
    # lignes quotidiennes, 21 lignes de cumul à vie d'un collecteur antérieur.
    #
    # La vue les écarte ET rend une ligne par campagne, ce que le tableau des taux
    # plus bas supposait déjà : il affichait 252 lignes pour 21 campagnes.
    query_perf = (
        "SELECT campaign_name, SUM(spend) AS spend, SUM(results) AS results, "
        "SUM(custom_conversions) AS custom_conversions, SUM(lp_views) AS lp_views, "
        "SUM(impressions) AS impressions, SUM(reach) AS reach, "
        "AVG(frequency) AS frequency, SUM(link_clicks) AS link_clicks "
        f"FROM v_meta_campaign_daily WHERE artist_id = %s{_campaign_in} "
        "GROUP BY campaign_name ORDER BY SUM(spend) DESC"
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

        st.markdown(t("meta_ads_overview.global_perf", "### 🚀 Performance Globale"))
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric(t("meta_ads_overview.spend", "Dépenses"), f"{tot_spend:,.0f} €")
        k2.metric(t("meta_ads_overview.impressions", "Impressions"), f"{tot_impr:,.0f}")
        k3.metric(t("meta_ads_overview.link_clicks", "Clics Lien"), f"{tot_clicks:,.0f}")
        k4.metric("CPM", f"{cpm:.2f} €")
        k5.metric("CPC", f"{cpc:.2f} €")
        k6.metric(t("meta_ads_overview.cpr_spotify", "CPR (Clics Spotify)"),
                  f"{cpr:.2f} €" if tot_conv > 0 else t("meta_ads_overview.capi_required", "— (CAPI requis)"),
                  delta_color="inverse")

        # Engagement
        if not df_eng.empty:
            for c in ['saves', 'shares', 'page_interactions']: df_eng[c] = pd.to_numeric(df_eng[c], errors='coerce').fillna(0)
            st.markdown(t("meta_ads_overview.engagement", "##### ❤️ Engagement"))
            e1, e2, e3 = st.columns(3)
            e1.metric("💾 Saves", f"{df_eng['saves'].sum():,.0f}")
            e2.metric("🔄 Shares", f"{df_eng['shares'].sum():,.0f}")
            e3.metric(t("meta_ads_overview.total_interactions", "⚡ Interactions Totales"), f"{df_eng['page_interactions'].sum():,.0f}")

    st.markdown("---")

    # ==============================================================================
    # 🔽 SECTION 1b : FUNNEL HYPEDDIT (Impressions → Clics → LP → Spotify)
    # ==============================================================================
    st.subheader(t("meta_ads_overview.funnel_title", "🔽 Funnel de conversion Hypeddit"))

    if not df_perf.empty:
        has_capi = tot_conv > 0
        if not has_capi:
            st.info(t(
                "meta_ads_overview.capi_info",
                "Les clics Spotify (CAPI) seront visibles ici une fois le "
                "Conversions API configuré sur Hypeddit. "
                "Les 3 premières étapes du funnel sont déjà disponibles."
            ))

        # Taux de conversion à chaque étape
        ctr_pct       = (tot_clicks / tot_impr * 100) if tot_impr > 0 else 0
        lp_open_pct   = (tot_lp / tot_clicks * 100)   if tot_clicks > 0 else 0
        spotify_pct   = (tot_conv / tot_lp * 100)      if tot_lp > 0 else 0

        # KPIs d'étape
        f1, f2, f3, f4 = st.columns(4)
        f1.metric(t("meta_ads_overview.impressions", "Impressions"),   f"{tot_impr:,.0f}")
        f2.metric(t("meta_ads_overview.ad_clicks", "Clics sur pub"), f"{tot_clicks:,.0f}",
                  help=t("meta_ads_overview.ctr_help", "CTR : {v} %").format(v=f"{ctr_pct:.2f}"))
        f3.metric(t("meta_ads_overview.lp_views", "Vues LP"),       f"{tot_lp:,.0f}",
                  help=t("meta_ads_overview.lp_open_help", "LP open rate : {v} % des clics").format(v=f"{lp_open_pct:.1f}"))
        if has_capi:
            f4.metric(t("meta_ads_overview.spotify_clicks", "Clics Spotify"), f"{tot_conv:,.0f}",
                      help=t("meta_ads_overview.lp_spotify_help", "Taux LP→Spotify : {v} %").format(v=f"{spotify_pct:.1f}"))
        else:
            f4.metric(t("meta_ads_overview.spotify_clicks", "Clics Spotify"), "— (CAPI)")

        # Funnel chart
        funnel_labels  = [t("meta_ads_overview.impressions", "Impressions"),
                          t("meta_ads_overview.funnel_clicks", "Clics pub"),
                          t("meta_ads_overview.lp_views", "Vues LP")]
        funnel_values  = [tot_impr, tot_clicks, tot_lp]
        funnel_colors  = ["#636efa", "#00cc96", "#EF553B"]
        if has_capi:
            funnel_labels.append(t("meta_ads_overview.spotify_clicks", "Clics Spotify"))
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
                    'campaign_name': t("meta_ads_overview.col_campaign", "Campagne"),
                    'impressions': t("meta_ads_overview.impressions", "Impressions"),
                    'link_clicks': t("meta_ads_overview.funnel_clicks", "Clics pub"),
                    'lp_views': t("meta_ads_overview.lp_views", "Vues LP"),
                    'custom_conversions': t("meta_ads_overview.spotify_clicks", "Clics Spotify"),
                }),
                width="stretch",
                hide_index=True,
            )

    st.markdown("---")

    # ==============================================================================
    # 📈 SECTION 2 : PERFORMANCE PAR CAMPAGNE (GRAPHIQUE PRINCIPAL)
    # ==============================================================================
    st.subheader(t("meta_ads_overview.perf_by_campaign", "📊 Performance par Campagne"))

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

        # TROIS UNITÉS, TROIS CADRES — les six séries étaient réparties sur trois axes
        # superposés (budget en euros, volumes en unités, ratios en euros par résultat).
        # Un lecteur y voyait des courbes se croiser ; ces croisements ne sont que le
        # produit du cadrage choisi. Partagés en x, les cadres gardent la comparaison
        # campagne par campagne et rendent chaque grandeur lisible sur son échelle.
        from plotly.subplots import make_subplots
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.07,
                            row_heights=[0.4, 0.3, 0.3],
                            subplot_titles=[
                                t("meta_ads_overview.budget_eur", "Budget (€)"),
                                t("meta_ads_overview.volumes", "Volumes"),
                                t("meta_ads_overview.ratios_eur", "Ratios (€)")])

        # Axe Y1 (Gauche - Barres)
        fig.add_trace(go.Bar(
            x=df_chart['campaign_name'], y=df_chart['spend'],
            name=t("meta_ads_overview.budget_eur", "Budget (€)"), marker_color='rgba(255, 99, 97, 0.5)',
            yaxis='y', offsetgroup=1
        ))

        # Axe Y2 (Droite 1 - Barres fines)
        fig.add_trace(go.Bar(
            x=df_chart['campaign_name'], y=df_chart['results'],
            name=t("meta_ads_overview.native_results", "Résultats natifs Meta (selon objectif)"),
            marker_color='rgba(0, 63, 92, 0.9)',
            yaxis='y2', offsetgroup=2
        ))
        fig.add_trace(go.Bar(
            x=df_chart['campaign_name'], y=df_chart['link_clicks'],
            name=t("meta_ads_overview.link_clicks", "Clics Lien"), marker_color='rgba(88, 80, 141, 0.7)', offsetgroup=2, visible=True
        ), row=2, col=1)
        fig.add_trace(go.Bar(
            x=df_chart['campaign_name'], y=df_chart['page_interactions'],
            name=t("meta_ads_overview.interactions", "Interactions"), marker_color='rgba(255, 166, 0, 0.7)', offsetgroup=2, visible=True
        ), row=2, col=1)

        # Impressions
        fig.add_trace(go.Scatter(
            x=df_chart['campaign_name'], y=df_chart['impressions'],
            name=t("meta_ads_overview.impressions", "Impressions"), mode='markers',
            marker=dict(symbol='star', size=10, color='#333'), visible='legendonly'
        ), row=2, col=1)

        # Axe Y3 (Droite 2 - Ratios) - ACTIVÉS
        fig.add_trace(go.Scatter(
            x=df_chart['campaign_name'], y=df_chart['cpr'],
            name='CPR (€)', mode='lines+markers+text',
            text=df_chart['cpr'].apply(lambda x: f"{x:.2f}€"), textposition="top center",
            line=dict(color='#bc5090', width=2), marker=dict(size=8), visible=True
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df_chart['campaign_name'], y=df_chart['cpm'],
            name='CPM (€)', mode='lines+markers',
            line=dict(color='#ffa600', width=2), marker=dict(size=8), visible=True
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df_chart['campaign_name'], y=df_chart['cpc'],
            name='CPC (€)', mode='lines+markers',
            line=dict(color='#ff6361', width=2), marker=dict(size=8), visible=True
        ), row=3, col=1)

        fig.update_layout(
            height=600,
            title=t("meta_ads_overview.chart_360", "Vue 360° : Budget vs Volumes vs Ratios"),
            showlegend=False,
            hovermode="x unified",
            barmode='group'
        )
        st.plotly_chart(fig, width="stretch")

    st.markdown("---")

    # ==============================================================================
    # 📊 SECTION 2b : COMPARAISON MULTI-MÉTRIQUES PAR CAMPAGNE
    # ==============================================================================
    st.subheader(t("meta_ads_overview.multi_metric", "📊 Comparaison multi-métriques par campagne"))
    st.caption(t("meta_ads_overview.multi_metric_caption",
                 "Une rangée par métrique, échelles indépendantes. Cliquez une entrée de légende pour la masquer."))

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
            'spend':              t("meta_ads_overview.spend_eur", "Dépenses (€)"),
            'impressions':        t("meta_ads_overview.impressions", "Impressions"),
            'link_clicks':        t("meta_ads_overview.funnel_clicks", "Clics pub"),
            'lp_views':           t("meta_ads_overview.lp_views", "Vues LP"),
            'custom_conversions': t("meta_ads_overview.spotify_clicks", "Clics Spotify"),
            'saves':              'Saves',
            'shares':             'Shares',
            'page_interactions':  t("meta_ads_overview.interactions", "Interactions"),
        }
        var_col = t("meta_ads_overview.metric", "Métrique")
        val_col = t("meta_ads_overview.value", "Valeur")
        df_multi = df_multi.rename(columns=metric_labels)
        df_long = df_multi.melt(
            id_vars='campaign_name',
            value_vars=list(metric_labels.values()),
            var_name=var_col,
            value_name=val_col,
        )

        fig_multi = px.bar(
            df_long,
            x='campaign_name', y=val_col,
            facet_row=var_col,
            color=var_col,
            category_orders={var_col: list(metric_labels.values())},
            height=130 * len(metric_labels),
            labels={'campaign_name': t("meta_ads_overview.col_campaign", "Campagne")},
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
        st.info(t("meta_ads_overview.no_campaign_data", "Aucune donnée de campagne pour les filtres sélectionnés."))

    st.markdown("---")

    # ==============================================================================
    # ⏳ SECTION 3 : ÉVOLUTION TEMPORELLE
    # ==============================================================================
    st.subheader(t("meta_ads_overview.time_evolution", "⏳ Évolution Temporelle (Budget vs Résultat vs CPR)"))

    # `v_meta_daily` (migration 106) porte cette maille — (locataire, compte,
    # campagne, jour) — et dix surfaces la demandaient. Les colonnes gardent leurs
    # noms d'affichage (`day_date`) par un alias : la figure en aval les lit.
    query_day = (
        "SELECT day AS day_date, SUM(spend) as spend, SUM(results) as results, "
        "SUM(custom_conversions) as custom_conversions "
        f"FROM v_meta_daily WHERE artist_id = %s{_campaign_in} "
        "GROUP BY day ORDER BY day ASC"
    )
    df_day = db.fetch_df(query_day, params)

    if not df_day.empty:
        for c in ['spend', 'results', 'custom_conversions']:
            df_day[c] = pd.to_numeric(df_day[c], errors='coerce').fillna(0)
        df_day['cpr'] = (df_day['spend'] / df_day['custom_conversions']).where(df_day['custom_conversions'] > 0).fillna(0)

        # TROIS UNITÉS, TROIS CADRES. Des euros dépensés, un nombre de clics et un coût
        # par résultat n'ont ni la même unité ni le même ordre de grandeur ; trois axes
        # superposés donnaient à leurs croisements une apparence de sens qu'ils n'ont
        # pas. Partagés en x, les trois cadres gardent la lecture chronologique.
        from plotly.subplots import make_subplots
        fig_time = make_subplots(
            rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.07,
            row_heights=[0.4, 0.3, 0.3],
            subplot_titles=[t("meta_ads_overview.spend_eur", "Dépenses (€)"),
                            t("meta_ads_overview.spotify_clicks", "Clics Spotify"),
                            "CPR (€)"])
        fig_time.add_trace(go.Bar(
            x=df_day['day_date'], y=df_day['spend'],
            name=t("meta_ads_overview.spend_eur", "Dépenses (€)"),
            marker_color='#2a78d6'), row=1, col=1)
        fig_time.add_trace(go.Scatter(
            x=df_day['day_date'], y=df_day['custom_conversions'],
            name=t("meta_ads_overview.spotify_clicks", "Clics Spotify"),
            mode='lines', line=dict(color='#1baf7a', width=2)), row=2, col=1)
        fig_time.add_trace(go.Scatter(
            x=df_day['day_date'], y=df_day['cpr'], name='CPR (€)',
            mode='lines+markers', line=dict(color='#eda100', width=2)), row=3, col=1)
        fig_time.update_layout(
            height=560, title=t("meta_ads_overview.daily_dynamics", "Dynamique Quotidienne"),
            hovermode="x unified", showlegend=False)
        st.plotly_chart(fig_time, width="stretch")
    else:
        st.info(t("meta_ads_overview.no_time_data", "Pas de données temporelles."))

    st.markdown("---")

    # ==============================================================================
    # 🌍 SECTION 4 : PARETOS (PAYS, PLACEMENT, AGE)
    # ==============================================================================
    st.subheader(t("meta_ads_overview.pareto_section", "🎯 Répartitions & Efficacité (Pareto CPR)"))

    def create_pareto_chart(df, x_col, title):
        if df.empty: return None
        df['spend'] = pd.to_numeric(df['spend'], errors='coerce').fillna(0)
        df['results'] = pd.to_numeric(df['results'], errors='coerce').fillna(0)
        df['cpr'] = df.apply(lambda x: x['spend'] / x['results'] if x['results'] > 0 else 0, axis=1)
        df = df.sort_values('spend', ascending=False).head(15)

        # DEUX CADRES PARTAGÉS EN X. Cette fabrique est instanciée TROIS fois (pays,
        # placement, âge) : son axe secondaire comptait donc pour trois. Dépense totale
        # et coût par résultat sont tous deux en euros, mais séparés de deux ordres de
        # grandeur — superposés, le CPR est plat ; sur un second axe, son croisement
        # avec les barres est un artefact de cadrage. Les valeurs restent écrites sur
        # les points, donc rien n'est perdu à la lecture.
        from plotly.subplots import make_subplots
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.09,
                            row_heights=[0.62, 0.38],
                            subplot_titles=[t("meta_ads_overview.spend_eur",
                                              "Dépenses (€)"), "CPR (€)"])
        fig.add_trace(go.Bar(x=df[x_col], y=df['spend'],
                             name=t("meta_ads_overview.spend_eur", "Dépenses (€)"),
                             marker_color='#2a78d6'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df[x_col], y=df['cpr'], name='CPR (€)',
                                 mode='lines+markers+text',
                                 text=df['cpr'].apply(lambda x: f"{x:.2f}€"),
                                 textposition="top center",
                                 line=dict(color='#eb6834', width=2)), row=2, col=1)
        fig.update_layout(title=title, showlegend=False, height=460)
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

    # Trois Pareto de RÉPARTITION : ils expliquent d'où vient le CPR déjà vu plus haut,
    # ils ne le remplacent pas. Repliés, la première vue de la page perd trois figures
    # sur huit sans rien perdre du raisonnement. `secondary_analyses()` a été écrit le
    # 2026-08-12 pour la remarque « réduire le nombre de graphs qui permettent de
    # prendre décision », et n'était appliqué sur aucune des cinq vues les plus denses.
    with secondary_analyses(t("meta_ads_overview.pareto_expander",
                              "🎯 Répartitions (pays, placement, âge) — détail")):
        c1, c2 = st.columns(2)
        with c1:
            if fig_country := create_pareto_chart(df_country, 'country', t("meta_ads_overview.pareto_country", "Pays (Top Dépenses)")): st.plotly_chart(fig_country, width="stretch")
        with c2:
            if fig_place := create_pareto_chart(df_place, 'placement', t("meta_ads_overview.pareto_placement", "Placements")): st.plotly_chart(fig_place, width="stretch")

        if fig_age := create_pareto_chart(df_age, 'age_range', t("meta_ads_overview.pareto_age", "Performance par Âge")): st.plotly_chart(fig_age, width="stretch")

    st.markdown("---")

    # ==============================================================================
    # 📋 SECTION 5 : DONNÉES BRUTES (TABLEAU COMPLET)
    # ==============================================================================
    st.subheader(t("meta_ads_overview.summary_table", "🗃️ Tableau Récapitulatif"))

    # ⚠️ %% in CTR column alias avoids Python IndexError in format strings
    _campaign_in_p = _acct_p + (
        f" AND p.campaign_name IN ({','.join(['%s'] * len(selected_campaigns))})"
        if selected_campaigns else ""
    )
    # La jointure d'engagement ne nommait pas le locataire : deux artistes ayant une
    # campagne du même nom mélangeaient leurs saves et leurs partages.
    query_full = (
        'SELECT p.campaign_name, SUM(p.spend) as "Dépenses",'
        ' SUM(p.custom_conversions) as "Clics Spotify",'
        ' SUM(p.lp_views) as "Vues LP", SUM(p.link_clicks) as "Clics pub",'
        ' CASE WHEN SUM(p.custom_conversions) > 0'
        '      THEN SUM(p.spend) / SUM(p.custom_conversions) END as "CPR",'
        ' SUM(p.impressions) as "Impressions",'
        ' CASE WHEN SUM(p.impressions) > 0'
        '      THEN SUM(p.spend) / SUM(p.impressions) * 1000 END as "CPM",'
        ' CASE WHEN SUM(p.impressions) > 0'
        '      THEN SUM(p.link_clicks)::numeric / SUM(p.impressions) * 100 END as "CTR (%%)",'
        ' MAX(e.saves) as "Saves", MAX(e.shares) as "Shares",'
        ' MAX(e.page_interactions) as "Interactions",'
        ' MAX(p.collected_at) as "Mise à jour"'
        " FROM v_meta_campaign_daily p"
        " LEFT JOIN meta_insights_engagement e ON e.campaign_name = p.campaign_name"
        "                                     AND e.artist_id = p.artist_id"
        f" WHERE p.artist_id = %s{_campaign_in_p}"
        ' GROUP BY p.campaign_name ORDER BY SUM(p.spend) DESC'
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
    st.subheader(t("meta_ads_overview.targeting_perf", "🎯 Ciblage vs Performance"))
    st.caption(t("meta_ads_overview.targeting_caption",
                 "Dépense & CPR agrégés par attribut de ciblage des ad sets (résultats ad-level)."))

    # `v_meta_adset_daily` (migration 108) porte la chaîne adsets → ads → insights.
    # Celle qui vivait ici ne nommait le locataire que sur `meta_adsets` : deux
    # locataires partageant un `adset_id` ou un `ad_id` mélangeaient leurs dépenses.
    # C'est la classe que la migration 106 décrit, recopiée une quatrième fois.
    df_tgt = db.fetch_df(
        """
        SELECT optimization_goal, gender, publisher_platforms, age_min, age_max,
               SUM(spend) AS spend, SUM(conversions) AS results
        FROM v_meta_adset_daily
        WHERE artist_id = %s"""
        f"{_acct}"
        """
        GROUP BY optimization_goal, gender, publisher_platforms, age_min, age_max
        """,
        (artist_id, *_acct_params),
    )
    if df_tgt.empty:
        st.info(t("meta_ads_overview.no_targeting_data", "Aucune donnée de ciblage ad set disponible."))
    else:
        df_tgt['gender'] = df_tgt['gender'].fillna('').astype(str).map(_gender_label)
        df_tgt['publisher_platforms'] = df_tgt['publisher_platforms'].fillna('').replace(
            '', t("meta_ads_overview.all_platforms", 'Toutes'))
        df_tgt['optimization_goal'] = df_tgt['optimization_goal'].fillna(
            t("meta_ads_overview.unknown", 'Inconnu'))
        df_tgt['age_band'] = (
            df_tgt['age_min'].fillna('').astype(str) + '–' + df_tgt['age_max'].fillna('').astype(str)
        ).str.strip('–').replace('', t("meta_ads_overview.age_unspecified", 'Non spécifié'))

        dim_label = st.selectbox(
            t("meta_ads_overview.slice_by", "Découper par"), list(_TARGETING_DIMS.keys()),
            key="tgt_dim",
            format_func=lambda lbl: t(f"meta_ads_overview.dim.{_TARGETING_DIMS[lbl]}", lbl))
        dim_col = _TARGETING_DIMS[dim_label]
        dim_disp = t(f"meta_ads_overview.dim.{dim_col}", dim_label)
        agg = df_tgt.groupby(dim_col, as_index=False).agg(spend=('spend', 'sum'),
                                                          results=('results', 'sum'))
        fig_tgt = pareto_spend_cpr(
            agg, dim_col,
            t("meta_ads_overview.pareto_by_dim", "Dépense & CPR par {dim}").format(dim=dim_disp.lower()))
        if fig_tgt is not None:
            st.plotly_chart(fig_tgt, width="stretch")
