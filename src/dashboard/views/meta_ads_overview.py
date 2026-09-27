import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.dashboard.utils import view_session, charts
from src.dashboard.utils.meta_accounts import account_clause, account_scope
from src.dashboard.utils.i18n import t
from src.dashboard.utils.proxy_disclosure import disclosure_caption
from src.dashboard.utils.ui import secondary_analyses
from src.dashboard.utils.date_format import format_date

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

def _render_scope_notice(db, artist_id) -> None:
    """Ce que CE compte permet de répondre, et ce qu'il ne permet pas. Mesuré.

    Arbitrage R107 §3, tranché le 2026-09-14. La question posée était « faut-il faire
    apparaître les 24 % de dépense que Meta n'attribue à aucune dimension ». La mesure
    a déplacé la question : la couverture des breakdowns est DÉJÀ recalculée et
    expliquée à chaque rendu (`meta_breakdowns._render_coverage`), alors qu'un trou
    plus grand n'était dit nulle part.

    Mesuré sur l'artiste 1 le 2026-09-14 : **zéro** campagne rattachée à un titre,
    quand six plateformes sur sept portent leurs onze titres liés. La section ne peut
    donc pas répondre à « combien ce titre m'a coûté » — et rien ne le disait. Un
    lecteur qui voit des campagnes nommées comme ses morceaux suppose l'inverse.

    Le compte vient de `v_meta_track_attribution` (migration 116) : le prédicat qui
    décide qu'un lien compte est une règle métier, pas une requête d'affichage.

    Le constat est CALCULÉ par locataire, jamais écrit en dur : un artiste dont les
    campagnes sont rattachées doit lire l'autre phrase, pas celle-ci. C'est la même
    règle que la couverture des breakdowns — une constante deviendrait fausse à la
    première campagne étiquetée.
    """
    row = db.fetch_query(
        "SELECT COALESCE(SUM(spend), 0), MIN(first_day), MAX(last_day) "
        "FROM v_meta_spend_totals WHERE artist_id = %s", (artist_id,))
    if not row or not row[0] or not row[0][2]:
        return                     # aucune dépense connue : rien à cadrer
    spend, first_day, last_day = float(row[0][0] or 0), row[0][1], row[0][2]

    # `v_meta_track_attribution` (migration 116), pas deux COUNT(*) ici. La première
    # version lisait `track_platform_link` en brut et le cliquet du bronze l'a
    # refusée dans l'heure — à raison : « rattachable » est une définition métier
    # (quel statut de lien compte, comment on rapproche une campagne d'un lien), et
    # une définition écrite dans une page diverge de celle écrite dans la suivante.
    attrib = db.fetch_query(
        "SELECT campaigns, linked_campaigns FROM v_meta_track_attribution "
        "WHERE artist_id = %s", (artist_id,))
    campaigns, linked = (attrib[0][0], attrib[0][1]) if attrib else (0, 0)

    # L'espace fine sur le SEUL nombre. Appliquée à la phrase entière, elle mangeait
    # aussi la virgule de « campagne(s), du … » — un remplacement de séparateur qui
    # déborde sur la ponctuation est la version typographique du garde textuel.
    period = t("meta_ads_overview.scope_period",
               "**{spend} €** sur **{campaigns}** campagne(s), du {start} au {end}."
               ).format(spend=f"{spend:,.0f}".replace(",", "\u202f"),
                        campaigns=campaigns,
                        start=format_date(first_day) if first_day else "?",
                        end=format_date(last_day))

    if linked:
        answer = t("meta_ads_overview.scope_linked",
                   " **{linked}** campagne(s) sont rattachées à un titre : le coût par "
                   "titre est lisible pour celles-là, et pour elles seules.")\
            .format(linked=linked)
    else:
        answer = t("meta_ads_overview.scope_unlinked",
                   " Aucune campagne n'est rattachée à un titre — cette section répond "
                   "donc à « combien ai-je dépensé, et qui cela a-t-il touché », pas à "
                   "« combien ce titre m'a coûté ». Un nom de campagne qui ressemble à "
                   "un morceau n'est pas un rattachement.")

    st.caption(f"ⓘ {period}{answer}")


def show():
    st.title(t("meta_ads_overview.title", "📱 Méta Ads - Analyse Stratégique"))

    # --- 1. CONNEXION & FILTRES ---
    with view_session() as (db, artist_id):
        _render_scope_notice(db, artist_id)
        _show_meta_ads(db, artist_id)
        # Les comptes d'agence se déclarent ICI depuis le 2026-09-05, plus dans
        # Credentials : cette page répond à « que veux-tu suivre », l'autre à
        # « comment te connecter ». Même mouvement que les titres SoundCloud
        # hébergés ailleurs, partis sur leur page de performance le 2026-09-04.
        from src.dashboard.views.meta_extra_accounts import render_extra_ad_accounts
        render_extra_ad_accounts(db, artist_id)


# Les six mesures de la performance globale. (libellé, colonne ou calcul, format)
# `derive` reçoit la ligne agrégée d'une campagne et rend le ratio — jamais une
# moyenne de ratios : un CPM est `Σdépense / Σimpressions × 1000`, pas la moyenne
# des CPM quotidiens.
_PERF_PANNEAUX = [
    ("Dépenses (€)",  lambda r: r['spend'],                                      "{:,.0f}"),
    ("Impressions",   lambda r: r['impressions'],                                "{:,.0f}"),
    ("Clics lien",    lambda r: r['link_clicks'],                                "{:,.0f}"),
    ("CPM (€)",       lambda r: r['spend'] / r['impressions'] * 1000
                                if r['impressions'] > 0 else float("nan"),       "{:,.2f}"),
    ("CPC (€)",       lambda r: r['spend'] / r['link_clicks']
                                if r['link_clicks'] > 0 else float("nan"),       "{:,.2f}"),
    # R146 — « CPR » garde le mot de Meta (l'artiste le retrouve tel quel dans le
    # Gestionnaire de publicités) mais ne voyage plus jamais sans sa limite : la
    # légende sous la figure dit que le résultat est un clic sortant.
    ("CPR (€)",       lambda r: r['spend'] / r['custom_conversions']
                                if r['custom_conversions'] > 0 else float("nan"), "{:,.2f}"),
]


def _render_global_perf(df_perf: pd.DataFrame) -> None:
    """La performance globale, CAMPAGNE PAR CAMPAGNE — six cadres, une unité chacun.

    ⚠️ Remplace six `st.metric` qui affichaient la SOMME de la sélection. Demande
    du propriétaire le 2026-09-21 : « peut-on visualiser les datas de perf
    globales quand on compare 2 tracks avec des graphiques plutôt que des champs
    de valeur ? ».

    Il a raison au-delà de la forme : additionner deux campagnes pour en tirer un
    CPM unique répond à une question que personne ne pose. On sélectionne deux
    titres pour les COMPARER ; la somme efface exactement ce qu'on cherchait. Une
    seule campagne sélectionnée rend un cadre à une barre, qui porte sa valeur
    écrite — l'information est la même que celle de l'ancienne jauge.

    Six cadres et non six séries : des euros, des impressions, des clics et trois
    coûts n'ont ni la même unité ni le même ordre de grandeur. Le cliquet d'axes
    secondaires de ce dépôt (`_MAX_SECONDARY_AXES = 0`) dit la même chose.
    """
    from plotly.subplots import make_subplots

    d = df_perf.dropna(subset=['campaign_name']).copy()
    if d.empty:
        return
    d = d.sort_values('spend', ascending=True)          # plus gros budget EN HAUT
    noms = d['campaign_name'].tolist()
    # R209 — a cut label is a CATEGORY here: two names sharing 33 characters would
    # be one row (class a-truncated-label-that-merges-two-categories).
    from src.dashboard.utils.labels import unique_short_labels
    court = unique_short_labels(noms, 34)

    fig = make_subplots(
        rows=2, cols=3, shared_yaxes=True,
        horizontal_spacing=0.06, vertical_spacing=0.18,
        subplot_titles=[t(f"meta_ads_overview.perf.{i}", lab)
                        for i, (lab, _f, _fmt) in enumerate(_PERF_PANNEAUX)])
    for i, (lab, calc, fmt) in enumerate(_PERF_PANNEAUX):
        vals = [float(calc(r)) for _, r in d.iterrows()]
        fig.add_trace(go.Bar(
            x=vals, y=court, orientation='h', showlegend=False,
            marker={'color': "#1877F2" if i < 3 else "#7f7f7f"},
            text=[fmt.format(v).replace(",", " ") if pd.notna(v) else "—" for v in vals],
            textposition='outside', cliponaxis=False,
            customdata=noms,
            hovertemplate=f"%{{customdata}}<br>{lab} : %{{text}}<extra></extra>",
        ), row=i // 3 + 1, col=i % 3 + 1)
        fig.update_xaxes(showticklabels=False, row=i // 3 + 1, col=i % 3 + 1)
    fig.update_layout(height=max(360, 46 * len(noms) + 220), bargap=0.3,
                      margin={'l': 10, 'r': 40, 't': 60, 'b': 20})
    fig.update_yaxes(automargin=True)
    charts.plotly_chart(fig, width="stretch")

    if not (d['custom_conversions'] > 0).any():
        st.caption(t("meta_ads_overview.capi_required",
                     "CPR vide : il demande la CAPI (évènements serveur) — "
                     "aucune conversion personnalisée n'est remontée ici."))
    else:
        # R146 — la limite s'affiche quand le chiffre EST là. L'ancien message ne
        # parlait que du cas vide : la seule fois où le CPR ne trompait personne.
        st.caption(disclosure_caption())


# ═══════════════════════════════════════════════════════════════════════════
# UNE LIGNE PAR CAMPAGNE, des deux côtés d'une jointure — 2026-09-26.
# ═══════════════════════════════════════════════════════════════════════════
# L'engagement se lisait en brut dans `meta_insights_engagement`, une ligne par
# campagne ET PAR JOUR, plus 21 lignes de cumul à vie. Trois défauts, une cause :
#
#   * fusionné sur `campaign_name` avec un cadre d'une ligne par campagne, il
#     changeait 21 campagnes en 252 lignes ; « les 12 plus dépensières »
#     dessinaient 12 copies de la même campagne (12 × 755,52 €) ;
#   * les tuiles Saves / Shares / Interactions sommaient cumuls ET jours : le
#     double exact (1 094 saves pour 547) ;
#   * le tableau récapitulatif le joignait jour × jour sous `SUM(p.spend)` :
#     24 176,64 € pour une campagne de 755,52 € (× 32).
#
# La vue or `v_meta_engagement_daily` (migration 138) écarte les cumuls ; les
# requêtes ci-dessous REGROUPENT par campagne AVANT toute jointure. Classe :
# `a-join-that-multiplies-the-grain`. Garde :
# `tests/test_a_join_never_multiplies_the_grain.py`.
_ENG_COLS = ("page_interactions", "post_reactions", "comments", "saves", "shares")


def _perf_query(campaign_in: str) -> str:
    """Performance per campaign, from the gold view: one row per campaign_name."""
    return (
        "SELECT campaign_name, SUM(spend) AS spend, SUM(results) AS results, "
        "SUM(custom_conversions) AS custom_conversions, SUM(lp_views) AS lp_views, "
        "SUM(impressions) AS impressions, SUM(reach) AS reach, "
        "AVG(frequency) AS frequency, SUM(link_clicks) AS link_clicks "
        f"FROM v_meta_campaign_daily WHERE artist_id = %s{campaign_in} "
        "GROUP BY campaign_name ORDER BY SUM(spend) DESC"
    )


def _engagement_query(campaign_in: str) -> str:
    """Engagement per campaign, from the gold view: one row per campaign_name."""
    sums = ", ".join(f"SUM({c}) AS {c}" for c in _ENG_COLS)
    return (f"SELECT campaign_name, {sums} FROM v_meta_engagement_daily "
            f"WHERE artist_id = %s{campaign_in} GROUP BY campaign_name")


def _summary_query(campaign_in: str) -> str:
    """The summary table: both sides aggregated per campaign, THEN joined 1:1.

    Takes the (artist_id, *account, *campaigns) parameters twice, once per side.
    """
    # ⚠️ %% in the CTR alias: psycopg2 reads a lone % as a placeholder.
    return (
        'SELECT p.campaign_name, p.spend AS "Dépenses",'
        ' p.custom_conversions AS "Clics Hypeddit",'
        ' p.lp_views AS "Vues LP", p.link_clicks AS "Clics pub",'
        ' CASE WHEN p.custom_conversions > 0'
        '      THEN p.spend / p.custom_conversions END AS "CPR (€/clic sortant)",'
        ' p.impressions AS "Impressions",'
        ' CASE WHEN p.impressions > 0'
        '      THEN p.spend / p.impressions * 1000 END AS "CPM",'
        ' CASE WHEN p.impressions > 0'
        '      THEN p.link_clicks::numeric / p.impressions * 100 END AS "CTR (%%)",'
        ' e.saves AS "Saves", e.shares AS "Shares",'
        ' e.page_interactions AS "Interactions",'
        ' p.collected_at AS "Mise à jour"'
        " FROM (SELECT campaign_name, SUM(spend) AS spend,"
        "              SUM(custom_conversions) AS custom_conversions,"
        "              SUM(lp_views) AS lp_views, SUM(link_clicks) AS link_clicks,"
        "              SUM(impressions) AS impressions, MAX(collected_at) AS collected_at"
        "         FROM v_meta_campaign_daily"
        f"       WHERE artist_id = %s{campaign_in} GROUP BY campaign_name) p"
        f" LEFT JOIN ({_engagement_query(campaign_in)}) e"
        "        ON e.campaign_name = p.campaign_name"
        " ORDER BY p.spend DESC"
    )


def _campaign_frame(df_perf: pd.DataFrame) -> pd.DataFrame:
    """The chart frame: one row per campaign, with its three cost ratios. Pure.

    `df_perf` is already one row per campaign (GROUP BY in SQL). Nothing is merged
    into it: the engagement column the old merge brought in was never plotted, and
    it is the merge that multiplied the rows.
    """
    df = df_perf.copy()
    df['cpr'] = df.apply(lambda x: x['spend'] / x['results'] if x['results'] > 0 else 0, axis=1)
    df['cpm'] = df.apply(
        lambda x: x['spend'] / x['impressions'] * 1000 if x['impressions'] > 0 else 0, axis=1)
    df['cpc'] = df.apply(
        lambda x: x['spend'] / x['link_clicks'] if x['link_clicks'] > 0 else 0, axis=1)
    return df


def _add_streams_row(fig, db, artist_id: int, days) -> None:
    """Spotify streams per day of the whole artist, under the ad dynamics (R246, fiche 22).

    `v_s4a_song_daily` without the CSV « Total » row; a day not exported stays a gap."""
    if days is None or len(days) == 0:
        return
    rows = db.fetch_df(
        "SELECT day, SUM(streams) AS streams FROM v_s4a_song_daily WHERE artist_id = %s "
        "AND song NOT ILIKE '%%1x7xxxxxxx%%' AND day BETWEEN %s AND %s GROUP BY day ORDER BY day",
        (artist_id, pd.Timestamp(min(days)).date(), pd.Timestamp(max(days)).date()))
    if rows is None or rows.empty:
        return
    fig.add_trace(go.Scatter(
        x=pd.to_datetime(rows['day']), y=pd.to_numeric(rows['streams'], errors='coerce'),
        name=t("meta_ads_overview.streams_day", "Écoutes Spotify / jour"), mode='lines',
        connectgaps=False, line=dict(color="#1DB954", width=2)), row=2, col=1)
    fig.update_yaxes(title_text=t("meta_ads_overview.streams_axis", "Écoutes"), row=2, col=1)


def _show_meta_ads(db, artist_id):
    # Le compte AVANT les campagnes : deux comptes peuvent porter la même campagne
    # « Release FR », donc la liste offerte dépend du compte choisi, jamais l'inverse.
    _account = account_scope(db, artist_id, key="meta_overview_acct")
    _acct, _acct_params = account_clause(_account)
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
    df_perf = db.fetch_df(_perf_query(_campaign_in), params)

    df_eng = db.fetch_df(_engagement_query(_campaign_in), params)

    if not df_perf.empty:
        # Nettoyage
        for c in ['spend', 'results', 'custom_conversions', 'lp_views', 'impressions', 'link_clicks']:
            df_perf[c] = pd.to_numeric(df_perf[c], errors='coerce').fillna(0)

        st.markdown(t("meta_ads_overview.global_perf", "### 🚀 Performance Globale"))
        _render_global_perf(df_perf)

        # Engagement
        if not df_eng.empty:
            for c in ['saves', 'shares', 'page_interactions']: df_eng[c] = pd.to_numeric(df_eng[c], errors='coerce').fillna(0)
            st.markdown(t("meta_ads_overview.engagement", "##### ❤️ Engagement"))
            e1, e2, e3 = st.columns(3)
            e1.metric("💾 Saves", f"{df_eng['saves'].sum():,.0f}")
            e2.metric("🔄 Shares", f"{df_eng['shares'].sum():,.0f}")
            e3.metric(t("meta_ads_overview.total_interactions", "⚡ Interactions Totales"), f"{df_eng['page_interactions'].sum():,.0f}")

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # LE FUNNEL A DÉMÉNAGÉ le 2026-09-21 — et il était FAUX.
    # ═══════════════════════════════════════════════════════════════════════
    #
    # Il vit désormais dans « 🔀 Impact de mes campagnes », sous le nom
    # **Meta × Spotify × Hypeddit**, parce qu'il traverse trois sources et qu'il
    # appartient à la page qui les croise déjà.
    #
    # ⚠️ IL N'A PAS ÉTÉ DÉPLACÉ TEL QUEL. L'artiste avait signalé l'incohérence :
    # « 643 vues de LP pour 5972 clics Spotify, on devrait avoir une valeur
    # inférieure ». Mesuré sur tout l'historique du locataire 1 :
    #
    #     les deux métriques mesurées le même jour : **91 jours**
    #     `lp_views < custom_conversions` : **91 jours sur 91**
    #
    # Zéro jour cohérent. Le défaut n'était pas dans les chiffres mais dans le
    # MODÈLE : `lp_views` (le `landing_page_view` de Meta, qui exige que le pixel
    # se déclenche au chargement) et `custom_conversions` (l'évènement SERVEUR de
    # la CAPI Hypeddit) ne sont pas deux étapes successives — ce sont **deux
    # mesures de la même étape**, dont l'une sous-compte par construction.
    #
    # Les empiler affirmait un emboîtement que la donnée contredit tous les jours.
    # Dans sa nouvelle forme, `lp_views` est une note de QUALITÉ sur l'étape, et
    # les quatre étapes sont : impressions → clics pub → arrivées sur le smart
    # link → clics vers les plateformes.


    # ==============================================================================
    # 📈 SECTION 2 : PERFORMANCE PAR CAMPAGNE (GRAPHIQUE PRINCIPAL)
    # ==============================================================================
    st.subheader(t("meta_ads_overview.perf_by_campaign", "📊 Performance par Campagne"))

    if not df_perf.empty:
        df_chart = _campaign_frame(df_perf)
        if len(df_chart) == 1:
            # R246 (fiche 21 « je ne comprends pas quoi lire ») : une seule campagne sur la
            # période, il n'y a RIEN à comparer — le dire au lieu de laisser chercher.
            st.info(t("meta_ads_overview.one_campaign",
                      "Une seule campagne a dépensé sur la période choisie : élargis la "
                      "période pour comparer tes campagnes entre elles."))

        # UNE FIGURE, PAS DEUX — et des noms de campagne LISIBLES. 2026-09-21.
        #
        # Deux sections posaient la même question : « 📊 Performance par
        # Campagne » (trois cadres, huit séries, légende masquée) et
        # « 📊 Comparaison multi-métriques par campagne » (six métriques de
        # plus). Quatorze séries pour une seule question, et sur 21 campagnes.
        #
        # Le défaut de lecture n'était pas le nombre de cadres, c'était l'AXE :
        # les noms de campagne vivaient en x, pivotés, et ce compte en porte qui
        # font 90 caractères (« KSD - Kaiber 1_Ready for a total immersion… »).
        # Aucun n'était lisible.
        #
        # Les campagnes passent donc en Y — un axe vertical lit un nom long sans
        # le pivoter — et chaque métrique prend sa colonne, sur son échelle. C'est
        # la forme des petits multiples, appliquée à un classement.
        from plotly.subplots import make_subplots

        _top = df_chart.sort_values('spend', ascending=False).head(12).iloc[::-1]
        _colonnes = [
            ('spend', t("meta_ads_overview.budget_eur", "Budget (€)"), '#ff6361', ',.0f'),
            ('link_clicks', t("meta_ads_overview.link_clicks", "Clics Lien"), '#58508d', ',.0f'),
            ('cpr', 'CPR (€)', '#bc5090', '.3f'),
        ]
        fig = make_subplots(
            rows=1, cols=len(_colonnes), shared_yaxes=True, horizontal_spacing=0.05,
            subplot_titles=[lbl for _c, lbl, _k, _f in _colonnes])
        for i, (col, lbl, ink, fmt) in enumerate(_colonnes, start=1):
            vals = pd.to_numeric(_top[col], errors='coerce')
            fig.add_trace(go.Bar(
                y=_top['campaign_name'], x=vals, orientation='h', name=lbl,
                marker_color=ink, opacity=0.85,
                text=[("—" if pd.isna(v) else format(v, fmt)) for v in vals],
                textposition="outside", cliponaxis=False,
                hovertemplate="%{y}<br>%{x:,.3f}<extra></extra>"), row=1, col=i)
        fig.update_layout(
            height=max(420, 34 * len(_top)), showlegend=False, bargap=0.28,
            margin=dict(l=10, r=60, t=70),
            title=t("meta_ads_overview.chart_360",
                    "Mes campagnes, côte à côte — les 12 plus dépensières"))
        fig.update_yaxes(automargin=True)
        charts.plotly_chart(fig, width="stretch")
        st.caption(t(
            "meta_ads_overview.compare_caption",
            "Les campagnes sont en ORDONNÉE : un axe vertical lit un nom long sans "
            "le pivoter, et ce compte en porte qui font 90 caractères. Chaque "
            "colonne a son échelle — un budget en euros et un CPR à trois "
            "décimales ne se comparent pas sur le même repère. Trié par dépense : "
            "**le CPR de la colonne de droite se lit en regard du budget de "
            "gauche**, ce qui est la seule façon de voir si ce qu'on a le plus "
            "financé est aussi ce qui coûte le moins cher."))


    # ==============================================================================
    # ⏳ SECTION 3 : ÉVOLUTION TEMPORELLE
    # ==============================================================================
    st.subheader(t("meta_ads_overview.time_evolution",
                   "⏳ Dépense, clics et coût — sur une seule horloge"))

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
            df_day[c] = pd.to_numeric(df_day[c], errors='coerce')

        # UN JOUR SANS LIGNE N'EST PAS UN JOUR À ZÉRO, ET IL N'EST PAS NON PLUS UNE
        # LIGNE DROITE.
        #
        # `v_meta_daily` ne rend que les jours qui ont des lignes. Un jour manquant
        # sortait donc de l'axe entièrement, et la courbe des clics le TRAVERSAIT en
        # ligne droite — une interpolation que personne n'a mesurée, d'autant plus
        # trompeuse que le lecteur y cherche l'effet d'une dépense. On réindexe sur
        # le calendrier complet : le jour existe, sa valeur est `NaN`, la ligne s'y
        # coupe (`connectgaps=False`) et la barre n'y dessine rien.
        df_day['day_date'] = pd.to_datetime(df_day['day_date'])
        df_day = (df_day.set_index('day_date')
                  .reindex(pd.date_range(df_day['day_date'].min(),
                                         df_day['day_date'].max(), freq='D'))
                  .rename_axis('day_date').reset_index())

        # LE CPR D'UN JOUR SANS CONVERSION EST INDÉFINI, PAS NUL. `fillna(0)` le
        # traçait à 0 €, c'est-à-dire « ce jour-là les résultats étaient gratuits » —
        # l'inverse de la vérité, qui est qu'il n'y en a pas eu. Le collecteur fait
        # déjà ce choix pour les objectifs sans conversion (CPR NULL), et
        # `meta_x_spotify` le documente : « No recompute — that would fabricate a
        # CPR Meta hid. »
        df_day['cpr'] = (df_day['spend'] / df_day['custom_conversions']
                         ).where(df_day['custom_conversions'] > 0)

        # UN SEUL GRAPHIQUE — 2026-09-21, demandé : « essaye de tout mettre sur
        # un même graphique ». Les trois cadres empilés avaient une bonne raison
        # d'exister (trois unités, trois ordres de grandeur) et un vrai défaut :
        # sur une campagne de 31 jours, chaque cadre faisait 150 px de haut et
        # aucune des trois courbes ne se lisait.
        #
        # Ce qui rend la fusion honnête, et qui manquait à la version d'avant :
        #
        #   · la DÉPENSE et les CLICS partagent l'axe de GAUCHE — ce sont deux
        #     volumes, comparables entre eux ;
        #   · le CPR va seul à DROITE — c'est un PRIX, donc une autre nature.
        #     C'est le seul cas que ce dépôt admet pour un double axe, et celui
        #     que `charts.py` documente depuis le 2026-09-12 ;
        #   · l'axe de droite est TEINTÉ de la couleur de sa seule série, sans
        #     quoi deux échelles se lisent comme une.
        #
        # Un croisement reste visible à l'œil ; rien dans la figure ne le présente
        # comme un évènement.
        from plotly.subplots import make_subplots
        _INK_SPEND, _INK_CLICKS, _INK_CPR = "#2a78d6", "#1baf7a", "#eda100"
        # R246 (fiche 22) : les ÉCOUTES Spotify dans leur propre rangée, sur la même horloge
        # — sur l'axe des clics elles écrasaient la série (même règle que le double axe).
        fig_time = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28],
                                 vertical_spacing=0.08,
                                 specs=[[{"secondary_y": True}], [{}]])
        fig_time.add_trace(go.Bar(
            x=df_day['day_date'], y=df_day['spend'],
            name=t("meta_ads_overview.spend_eur", "Dépenses (€)"),
            marker_color=_INK_SPEND, opacity=0.55), row=1, col=1, secondary_y=False)
        fig_time.add_trace(go.Scatter(
            x=df_day['day_date'], y=df_day['custom_conversions'],
            name=t("meta_ads_overview.spotify_clicks", "Clics Hypeddit"),   # R246 fiche 22 : le clic sortant passe par le smart link
            mode='lines', connectgaps=False,
            line=dict(color=_INK_CLICKS, width=2)), row=1, col=1, secondary_y=False)
        fig_time.add_trace(go.Scatter(
            x=df_day['day_date'], y=df_day['cpr'],
            name=t("meta_ads_overview.cpr_series", "CPR (€/clic sortant)"),
            mode='lines+markers', connectgaps=False,
            line=dict(color=_INK_CPR, width=2, dash='dot'),
            marker=dict(size=6)), row=1, col=1, secondary_y=True)
        fig_time.update_yaxes(
            title_text=t("meta_ads_overview.axis_volume", "Dépense (€) · clics"),
            row=1, col=1, secondary_y=False)
        fig_time.update_yaxes(
            title_text="CPR (€)", showgrid=False, row=1, col=1, secondary_y=True,
            title_font=dict(color=_INK_CPR), tickfont=dict(color=_INK_CPR))
        _add_streams_row(fig_time, db, artist_id, df_day['day_date'])
        fig_time.update_layout(
            height=560, hovermode="x unified", barmode='overlay',
            legend=dict(orientation="h", y=1.12),
            title=t("meta_ads_overview.daily_dynamics", "Dynamique Quotidienne"))
        charts.plotly_chart(fig_time, width="stretch")
    else:
        st.info(t("meta_ads_overview.no_time_data", "Pas de données temporelles."))

    st.markdown("---")

    # ==============================================================================
    # 🌍 SECTION 4 — VIDE depuis le 2026-09-21, et son titre part avec elle.
    # ==============================================================================
    # Un en-tête sans contenu est pire qu'une section supprimée : il promet
    # quelque chose puis ne le livre pas. Le raisonnement du retrait est juste
    # en dessous ; il reste parce qu'il explique où la chose est ALLÉE.
    # ═══════════════════════════════════════════════════════════════════════
    # LES TROIS PARETO « pays / placement / âge » SONT PARTIS le 2026-09-21.
    # ═══════════════════════════════════════════════════════════════════════
    #
    # Question posée : « pour la view qui a vu tes pubs, ce n'est pas redondant
    # avec une autre view où on trace des placement pays âge ? » — oui, et c'est
    # vérifiable : les deux lisaient les MÊMES tables,
    # `meta_insights_performance_{country,placement,age}`.
    #
    # La différence n'était pas dans le sujet mais dans la portée, et celle d'ici
    # était strictement plus PETITE :
    #
    #     ici                 3 dimensions · grain CAMPAGNE · performance seule
    #     🌍 Qui a vu tes pubs 3 dimensions · 3 grains (campagne/adset/créative)
    #                          · 2 familles (performance ET engagement) · + carte
    #
    # Un sous-ensemble qui vit ailleurs n'est pas un raccourci, c'est une seconde
    # définition en attente de diverger. Elle part d'ici, où elle était repliée
    # dans un tiroir, et pas de la page qui la porte entièrement.
    #
    # ⚠️ Le croisement PAYS, lui, n'a pas disparu : il a été REFAIT ailleurs, avec
    # ce qui lui manquait. « 🔀 Impact de mes campagnes » croise désormais la
    # dépense Meta par pays avec les ÉCOUTES par pays du distributeur — mesuré le
    # 2026-09-21 : la Colombie rend 0,002 € par écoute contre 0,181 € au Brésil,
    # **93 fois** moins cher, et aucune des deux pages ne pouvait le dire.

    st.markdown("---")

    # ==============================================================================
    # 📋 SECTION 5 : DONNÉES BRUTES (TABLEAU COMPLET)
    # ==============================================================================
    # LE TABLEAU DESCEND DANS UN TIROIR — 2026-09-21.
    #
    # `test_the_dense_views_use_the_pattern_written_for_them` a rougi quand les
    # trois Pareto sont partis : ils étaient le SEUL `secondary_analyses` de cette
    # vue, et elle en porte huit figures. Le garde a raison, et son remède est le
    # bon : un tableau de 21 lignes et 9 colonnes RAFFINE une décision, il n'en
    # prend aucune — c'est la définition même du tiroir. La figure de comparaison
    # juste au-dessus répond à la question ; le tableau sert à retrouver une
    # valeur précise, et c'est un second geste.
    with secondary_analyses(t("meta_ads_overview.summary_table",
                              "🗃️ Tableau récapitulatif — le détail chiffré")):

        df_full = db.fetch_df(_summary_query(_campaign_in), params + params)

        if not df_full.empty:
            st.dataframe(
                df_full.style.format({
                    "Dépenses": "{:,.2f} €", "CPR": "{:,.2f} €", "CPM": "{:,.2f} €",
                    "CTR (%)": "{:,.2f}",
                    "Saves": "{:,.0f}", "Shares": "{:,.0f}", "Interactions": "{:,.0f}",
                    "Clics Hypeddit": "{:,.0f}", "Clics pub": "{:,.0f}",
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
        # R245 (fiche 23 « en rond pour la lisibilité ») : la part de la dépense, € et CPR
        # écrits sur chaque part.
        fig_tgt = charts.spend_ring(
            agg, dim_col,
            t("meta_ads_overview.pareto_by_dim", "Dépense & CPR par {dim}").format(dim=dim_disp.lower()))
        if fig_tgt is not None:
            charts.plotly_chart(fig_tgt, width="stretch")
