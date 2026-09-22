"""SoundCloud — le catalogue dans le temps, et la collecte qui a menti.

Type: Feature
Uses: view_session, entity_period_filter, platform_colors, i18n
Depends on: v_soundcloud_catalog_daily / v_soundcloud_track_daily (132),
            v_soundcloud_track_latest (107), soundcloud_tracks_daily
Persists in: — (lecture seule)

LE « BUMP DU 1er JUIN », rapporté le 2026-09-21
------------------------------------------------
Il est réel, il est en base, et ce n'est pas une baisse d'audience :

    19 lignes à `playback_count = 0`, TOUTES datées du 2026-06-01,
    et aucune autre date sur tout l'historique.

Les 19 titres étaient présents ce jour-là, tous à zéro sur les quatre compteurs.
Une collecte a répondu faux et le zéro a été ÉCRIT. Sur des compteurs CUMULÉS, la
courbe plonge à zéro puis remonte : le « bump ».

La règle « un cumul qui redescend est une panne » existait déjà — en PANDAS, dans
une seule figure de cette page. La figure principale, les tuiles et le tableau ne
l'avaient pas. Elle vit maintenant dans la couche or (migration 132), donc pour
toutes les surfaces à la fois. Mesuré : **19 jours de collecte, 1 écarté**.

ET « LE MÊME COMPTE DE STREAM » N'EST PAS UN BUG
-------------------------------------------------
« Chokbar de bezed » porte **4 écoutes** et n'en gagne pas. Ce qui était un défaut,
c'est qu'il soit le titre sélectionné D'OFFICE : `entity_period_filter` triait sur
`track_created_at`, la date d'upload SoundCloud, et ce titre est le plus récemment
uploadé du compte. La page s'ouvrait donc sur le titre le plus vide du catalogue —
4 écoutes, 0 like, 0 repost, 0 commentaire — ce qui explique aussi le message
« pas assez d'historique » : les trois quarts des métriques y valent zéro partout.

LE TOTAL DES QUATRE COMPTEURS SUR UN AXE TEMPOREL
---------------------------------------------------
Demandé le 2026-09-21, et il n'existait nulle part : la page ne savait montrer
qu'un TITRE à la fois. `v_soundcloud_catalog_daily` somme le catalogue par jour —
en prenant le DERNIER relevé de chaque titre dans la journée, parce que les titres
d'une même nuit ne sont pas écrits au même instant (317 horodatages pour 19 jours,
mesuré).
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from src.dashboard.utils import view_session
from src.dashboard.utils.ui import secondary_analyses
from src.dashboard.utils.i18n import t
from src.dashboard.utils.period_filter import EntitySpec, entity_period_filter
from src.dashboard.utils.tz import to_local_datetime, to_local_naive
from src.dashboard.utils.platform_colors import PALETTE_LIGHT
from src.dashboard.views.soundcloud_claims import render_claimed_tracks

# L'orange MESURÉ de SoundCloud — pas `#FF5500`, la teinte de marque exacte, que
# le balayage du 2026-09-08 a refusée (ΔE 4,6 contre YouTube en deutéranopie).
# C'est la meilleure position DANS la famille orange, pas une autre couleur.
_SC = PALETTE_LIGHT["soundcloud"]


def show():
    # ⚠️ NI TITRE NI SOUS-TITRE — retirés le 2026-09-21, même geste que sur Apple
    # et YouTube : « ☁️ SoundCloud - Performance » répétait l'entrée de menu qu'on
    # vient de cliquer.

    with view_session() as (db, artist_id):
        # =========================================================================
        # 1. KPIs GLOBAUX (Dernière date connue)
        # =========================================================================
        try:
            # Les quatre tuiles ci-dessous somment ces lignes EN PANDAS. Aucun garde
            # SQL ne peut les voir — il n'y a pas de `SUM(` dans la requête — et le
            # `DISTINCT ON (track_id)` qui vivait ici oubliait le locataire : deux
            # artistes qui repostent le même titre n'en gardaient qu'un.
            # `v_soundcloud_track_latest` (migration 107) porte la règle, locataire
            # compris, et c'est la même que celle des totaux de l'accueil.
            df_latest = db.fetch_df("""
                SELECT track_id, title, permalink_url, playback_count,
                       likes_count, reposts_count, comment_count,
                       track_created_at, collected_at
                FROM v_soundcloud_track_latest
                WHERE artist_id = %s
                ORDER BY track_id
            """, (artist_id,))

            if not df_latest.empty:
                # Enrichir avec first_seen pour tri "dernière release en premier"
                try:
                    df_first = db.fetch_df(
                        """SELECT track_id, MIN(collected_at) AS first_seen
                           FROM soundcloud_tracks_daily WHERE artist_id = %s
                           GROUP BY track_id""",
                        (artist_id,),
                    )
                    df_latest = df_latest.merge(df_first, on="track_id", how="left")
                except Exception:
                    df_latest["first_seen"] = df_latest["collected_at"]

                # LES TUILES LISENT LE DERNIER JOUR **LISIBLE**, pas le dernier
                # relevé — corrigé le 2026-09-21, sur une mutation.
                #
                # `v_soundcloud_track_latest` ne porte aucun verdict : elle rend le
                # dernier relevé, quel qu'il soit. Mesuré en simulant une dernière
                # collecte ratée (19 lignes à zéro, transaction annulée) : les
                # quatre tuiles affichent **0** quand le dernier jour lisible vaut
                # **23 486**. Ce n'est pas arrivé à l'artiste — sa dernière
                # collecte est bonne — mais ça arrive le jour où la prochaine rate,
                # et rien ne l'aurait dit.
                #
                # Le repli sur les sommes du dernier relevé reste en place : une
                # base sans vue or (un déploiement en retard de migration) doit
                # afficher des chiffres, pas une page vide.
                _dernier = db.fetch_df("""
                    SELECT plays, likes, reposts, comments, tracks, day
                      FROM v_soundcloud_catalog_daily
                     WHERE artist_id = %s AND lisible
                     ORDER BY day DESC LIMIT 1
                """, (artist_id,))
                if not _dernier.empty:
                    _r = _dernier.iloc[0]
                    total_plays, total_likes = int(_r["plays"]), int(_r["likes"])
                    total_reposts, total_comments = int(_r["reposts"]), int(_r["comments"])
                    total_tracks = int(_r["tracks"])
                else:
                    total_plays = df_latest['playback_count'].sum()
                    total_likes = df_latest['likes_count'].sum()
                    total_reposts = df_latest['reposts_count'].sum()
                    total_comments = df_latest['comment_count'].sum()
                    total_tracks = len(df_latest)

                # Récupération de la dernière date de collecte
                # timestamptz across a DST change → mixed offsets (utils/tz.py).
                last_date_str = to_local_datetime(df_latest['collected_at']).max().strftime('%d/%m/%Y')

                # Affichage sur 2 lignes
                c1, c2, c3 = st.columns(3)
                c1.metric(t("soundcloud.kpi_plays", "🎧 Total Écoutes"), f"{int(total_plays):,}")
                c2.metric(t("soundcloud.kpi_likes", "❤️ Total Likes"), f"{int(total_likes):,}")
                c3.metric(t("soundcloud.kpi_reposts", "🔄 Total Reposts"), f"{int(total_reposts):,}")

                # ⚠️ QUATRE TUILES, PAS SIX — 2026-09-21, à la demande du
                # propriétaire. « 🎵 Titres en ligne » et « 📅 Dernière mise à
                # jour » ne décident rien : le nombre de titres se lit dans le
                # classement juste en dessous, et une date de collecte est un
                # fait de PLOMBERIE. Elle n'est pas perdue pour autant — elle
                # descend dans la légende, avec ce qu'elle veut dire.
                c4, = st.columns(1)
                c4.metric(t("soundcloud.kpi_comments", "💬 Total Commentaires"),
                          f"{int(total_comments):,}")

                st.caption(t(
                    "soundcloud.likes_caption",
                    "ℹ️ **{n} titres**, dernier relevé le **{d}**. Likes et "
                    "historique fiables depuis le 15/05/2026 (collecte OAuth "
                    "user-token). Sources CSV S4A/Apple non liées — autre sujet."
                ).format(n=total_tracks, d=last_date_str))

            else:
                st.warning(t("soundcloud.no_data", "Aucune donnée SoundCloud trouvée. Lancez le collecteur."))
                # Un profil vide n'est pas toujours une panne : pour un artiste
                # signé sur un label, il l'est par construction et le restera. Le
                # panneau de déclaration est donc rendu ICI aussi, avant le
                # `return` — sinon la seule page où il compte vraiment est celle
                # qui n'y arrive jamais.
                st.caption(t(
                    "soundcloud.no_data_claim_hint",
                    "Tes sorties paraissent sous le compte d'un label ou d'un "
                    "collectif ? Déclare-les ci-dessous : on collectera leurs "
                    "écoutes même hébergées ailleurs."))
                render_claimed_tracks(db, artist_id)
                return

        except Exception as e:
            st.error(t("soundcloud.sql_error_kpi", "Erreur SQL (KPIs) : {err}").format(err=e))
            return

        st.markdown("---")

        # =========================================================================
        # 1bis. LE CATALOGUE DANS LE TEMPS — les quatre compteurs, une horloge
        # =========================================================================
        _render_catalog_series(db, artist_id)

        st.markdown("---")

        # =========================================================================
        # 2. ANALYSE TEMPORELLE (Filtres Dynamiques)
        # =========================================================================
        st.subheader(t("soundcloud.plays_evolution", "📈 Évolution des écoutes"))

        # --- FILTRES --- (entity + smart period, factorisés)
        # LE TITRE PROPOSÉ D'OFFICE NE PEUT PAS ÊTRE LE PLUS VIDE — 2026-09-21.
        #
        # `entity_period_filter` classe par date de sortie décroissante, et sur
        # SoundCloud cette date est `track_created_at`, l'UPLOAD. La page s'ouvrait
        # donc sur « Chokbar de bezed » — **4 écoutes, 0 like, 0 repost,
        # 0 commentaire** — le titre le plus récemment uploadé et le plus vide du
        # catalogue. Trois des quatre courbes y sont nulles partout, d'où le
        # message « pas assez d'historique » que l'artiste a rapporté : il
        # accusait l'historique quand la vérité est « ce titre n'a rien à
        # montrer ».
        #
        # On pré-remplit donc la sélection avec le titre LE PLUS ÉCOUTÉ, une seule
        # fois. Un choix ultérieur de l'artiste persiste en session — c'est le même
        # geste que la page Apple pour sa dernière sortie.
        #
        # ⚠️ Il passe par `preferred_default=`, PAS par `st.session_state` : le
        # widget reçoit déjà un `default=`, et poser les deux déclenche
        # l'avertissement Streamlit « created with a default value but also had
        # its value set via the Session State API ». Vu au premier rendu.
        _defaut = (df_latest.sort_values("playback_count", ascending=False)
                   .iloc[0]["title"]) if not df_latest.empty else None

        with st.expander(t("soundcloud.chart_filters", "⚙️ Filtres du graphique"), expanded=True):
            selected_tracks, window = entity_period_filter(
                db,
                spec=EntitySpec("soundcloud_tracks_daily", "title", "collected_at",
                                multi=True, default_count=1,
                                release_column="track_created_at"),
                artist_id=artist_id, key_prefix="sc",
                label=t("soundcloud.filter_by_tracks", "Filtrer par titres"),
                preferred_default=_defaut,
            )

        # --- REQUÊTE & AFFICHAGE ---
        try:
            start_d, end_d = window.start, window.end

            # On récupère l'historique large (on filtre en Pandas pour plus de souplesse UI)
            query_hist = """
                SELECT collected_at, title, playback_count,
                       likes_count, reposts_count, comment_count
                FROM soundcloud_tracks_daily
                WHERE artist_id = %s
                ORDER BY collected_at ASC
            """
            df_history = db.fetch_df(query_hist, (artist_id,))

            if not df_history.empty:
                # Conversion types
                df_history['collected_at'] = to_local_naive(df_history['collected_at']).dt.date

                # APPLICATION DES FILTRES
                mask_date = (df_history['collected_at'] >= start_d) & (df_history['collected_at'] <= end_d)
                mask_track = df_history['title'].isin(selected_tracks)

                df_filtered = df_history[mask_date & mask_track]

                if not df_filtered.empty:
                    # Graphique linéaire
                    # DES NUANCES D'ORANGE, PAS UNE PALETTE QUALITATIVE.
                    #
                    # `px.line(color='title')` tirait des teintes arbitraires dans
                    # la palette Plotly par défaut : un titre en bleu, un autre en
                    # rouge, sur une page SoundCloud. Ici toutes les séries sont
                    # de la MÊME plateforme — leur donner des familles de teinte
                    # différentes invente une distinction qui n'existe pas.
                    #
                    # Elles se distinguent donc par la CLARTÉ à l'intérieur de la
                    # famille orange, ce qui survit en plus à la deutéranopie là
                    # où une différence de teinte ne survit pas.
                    fig = px.line(
                        df_filtered,
                        x='collected_at',
                        y='playback_count',
                        color='title',
                        color_discrete_sequence=_nuances(
                            df_filtered['title'].nunique()),
                        title=t("soundcloud.growth_title", "Croissance ({start} - {end})").format(
                            start=start_d.strftime('%d/%m'), end=end_d.strftime('%d/%m')),
                        markers=True
                    )
                    fig.update_layout(
                        xaxis_title=t("common.date", "Date"),
                        yaxis_title=t("soundcloud.cumulative_plays", "Écoutes Cumulées"),
                        hovermode="x unified",
                        legend=dict(orientation="h", y=-0.2)  # Légende en bas pour ne pas cacher
                    )
                    st.plotly_chart(fig, width="stretch")

                    # Secondaire : compare des métriques entre elles — n'ouvre pas d'action.
                    # ⚠️ LE `st.plotly_chart` EST LEXICALEMENT DANS LE `with`.
                    #
                    # Ce n'est pas un détail de style : `test_chart_budget` et
                    # `test_a_view_opens_on_one_decision` lisent la STRUCTURE du
                    # fichier pour compter ce qui s'affiche au premier écran. Une
                    # figure tracée dans une fonction APPELÉE depuis le `with`
                    # leur est indistinguable d'une figure principale — et ils ont
                    # raison de refuser : un lecteur du code ne peut pas le savoir
                    # non plus.
                    #
                    # Le premier jet de cette réécriture faisait exactement ça, et
                    # les deux cliquets l'ont attrapé. `_render_base100` RETOURNE
                    # donc sa figure ; c'est la même règle que
                    # `spotify_s4a_combined._render_secondary`, dont le docstring
                    # l'annonçait déjà.
                    with secondary_analyses(t("soundcloud.base100_header",
                                              "📈 Évolution des métriques (base 100)")):
                        _fig_b100, _note_b100 = _base100_figure(
                            db, artist_id, selected_tracks, window)
                        if _fig_b100 is not None:
                            st.plotly_chart(_fig_b100, width="stretch")
                            st.caption(_note_b100)
                        elif _note_b100:
                            st.info(_note_b100)

                else:
                    st.info(t("soundcloud.no_data_selection",
                              "Aucune donnée pour cette sélection (Vérifiez les dates ou les titres)."))
            else:
                st.info(t("soundcloud.empty_history", "Historique vide pour le moment."))

        except Exception as e:
            st.error(t("soundcloud.history_error", "Erreur historique : {err}").format(err=e))

        st.markdown("---")

        # =========================================================================
        # 3. TOP TITRES (Tableau épuré)
        # =========================================================================
        st.subheader(t("soundcloud.top_tracks", "🏆 Top Titres"))
        if not df_latest.empty:
            df_top = df_latest.copy()
            # Coerce to numeric first: a NULL in any count makes the column object dtype,
            # so the raw arithmetic + .round(1) raised "Expected numeric dtype, got object".
            _likes = pd.to_numeric(df_top['likes_count'], errors='coerce').fillna(0)
            _reposts = pd.to_numeric(df_top['reposts_count'], errors='coerce').fillna(0)
            _comments = pd.to_numeric(df_top['comment_count'], errors='coerce').fillna(0)
            _pc = pd.to_numeric(df_top['playback_count'], errors='coerce')
            _eng = _likes + _reposts + _comments
            df_top['eng_total'] = _eng.astype(int)
            df_top['eng_rate'] = (_eng / _pc.where(_pc != 0) * 100).round(1)
            df_top['days_since'] = (
                pd.Timestamp.now() - pd.to_datetime(df_top['track_created_at'])
            ).dt.days

            _plays_lbl = t("soundcloud.plays", "Écoutes")
            _eng_lbl = t("soundcloud.engagement", "Engagement")
            sort_by = st.segmented_control(
                t("soundcloud.sort_by", "Trier par"), [_plays_lbl, _eng_lbl],
                default=_plays_lbl, key="sc_sort",
            ) or _plays_lbl
            sort_col = 'playback_count' if sort_by == _plays_lbl else 'eng_total'
            df_top = df_top.sort_values(by=sort_col, ascending=False)

            _render_top_chart(df_top, sort_col, sort_by, _plays_lbl)

        # Les titres sortis sous le compte d'un label ou d'un collectif — déclarés
        # ICI depuis le 2026-09-04, et plus dans Credentials. C'est en lisant ce
        # tableau qu'on s'aperçoit qu'une sortie manque ; c'est donc ici qu'on la
        # réclame. Replié : le cas ne concerne pas la majorité.
        st.markdown("---")
        render_claimed_tracks(db, artist_id)


if __name__ == "__main__":
    show()


def _render_catalog_series(db, artist_id) -> None:
    """Les quatre compteurs du CATALOGUE sur un axe de temps.

    Demandé le 2026-09-21 — « il n'y a pas un moyen pour mettre le total écoute
    like repost & commentaire sur un axe temporel ? » — et la réponse est oui : la
    donnée existe depuis toujours, la page ne savait montrer qu'un TITRE à la fois.

    DEUX CADRES, PAS UN. Les écoutes valent 23 486 quand les commentaires valent
    412 : sur un repère commun, trois des quatre courbes sont plates au fond. Un
    second axe superposé ferait pire — leur croisement serait un artefact de
    cadrage. Les petits multiples sont la seule alternative admise ici, et c'est
    la même décision que la figure de l'accueil.

    ⚠️ LES JOURS NON LISIBLES SONT ÉCARTÉS ET COMPTÉS. La vue or (migration 132)
    marque `lisible = FALSE` quand le cumul du catalogue redescend sous son
    maximum — une collecte ratée persistée, pas une baisse d'audience. Les taire
    serait inventer un zéro ; les tracer serait inventer une chute. On les écarte
    et on DIT combien, avec la date.
    """
    df = db.fetch_df("""
        SELECT day, tracks, plays, likes, reposts, comments, lisible
          FROM v_soundcloud_catalog_daily
         WHERE artist_id = %s
         ORDER BY day
    """, (artist_id,))
    if df.empty:
        return

    st.subheader(t("soundcloud.catalog_header",
                   "📊 Tout le catalogue — écoutes, likes, reposts, commentaires"))

    ecartes = df[~df["lisible"]]
    ok = df[df["lisible"]]
    if ok.empty:
        st.info(t("soundcloud.catalog_unreadable",
                  "Aucun relevé lisible : tous les jours collectés portent un "
                  "cumul en recul, ce qui signale une collecte en panne."))
        return

    from plotly.subplots import make_subplots
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
        row_heights=[0.55, 0.45],
        subplot_titles=[t("soundcloud.panel_plays", "Écoutes cumulées"),
                        t("soundcloud.panel_engagement",
                          "Engagement cumulé — likes, reposts, commentaires")])

    fig.add_trace(go.Scatter(
        x=ok["day"], y=ok["plays"], mode="lines+markers",
        name=t("soundcloud.plays", "Écoutes"),
        line=dict(color=_SC, width=2.5)), row=1, col=1)

    # UNE SEULE TEINTE, TROIS TRAITS. Les trois séries du bas sont de la même
    # plateforme : leur donner trois couleurs inventerait trois familles là où il
    # y en a une. Le trait distingue, et il survit à la deutéranopie.
    for col, lbl, dash in (
        ("likes", t("soundcloud.likes", "Likes"), None),
        ("reposts", t("soundcloud.reposts", "Reposts"), "dash"),
        ("comments", t("soundcloud.comments", "Commentaires"), "dot"),
    ):
        fig.add_trace(go.Scatter(
            x=ok["day"], y=ok[col], mode="lines+markers", name=lbl,
            line=dict(color=_SC, width=2, dash=dash)), row=2, col=1)

    fig.update_layout(height=560, hovermode="x unified",
                      legend=dict(orientation="h", y=1.10),
                      margin=dict(t=90))
    fig.update_yaxes(tickformat="~s", row=1, col=1)
    fig.update_yaxes(tickformat="~s", row=2, col=1)
    st.plotly_chart(fig, width="stretch")

    legende = t("soundcloud.catalog_caption",
                "**{n} relevé(s)** sur {t} titre(s). Ces compteurs sont des CUMULS "
                "à vie : la courbe monte ou reste plate, elle ne redescend jamais.")\
        .format(n=len(ok), t=int(ok.iloc[-1]["tracks"]))
    if not ecartes.empty:
        legende += " " + t(
            "soundcloud.catalog_dropped",
            "⚠️ **{k} jour(s) écarté(s)** ({d}) : le cumul y redescendait sous son "
            "maximum — une collecte qui a répondu faux, pas une perte d'audience. "
            "Les tracer dessinerait une chute qui n'a pas eu lieu.").format(
                k=len(ecartes),
                d=", ".join(pd.to_datetime(ecartes["day"]).dt.strftime("%d/%m/%Y")))
    st.caption(legende)


def _render_top_chart(df_top, sort_col: str, sort_by: str, plays_lbl: str) -> None:
    """Le classement des titres, en FIGURE — demandé le 2026-09-21.

    Le tableau de sept colonnes était exact et ne se lisait pas : pour savoir quel
    titre sur-performe, il fallait comparer mentalement une colonne d'écoutes en
    milliers à un taux d'engagement en pourcents, ligne à ligne, sur dix-neuf
    lignes.

    DEUX CADRES QUI RÉPONDENT À DEUX QUESTIONS :

      · à gauche, le VOLUME — barres horizontales, la longueur se compare d'un
        coup d'œil et le tri suit le sélecteur ;
      · à droite, le TAUX d'engagement — parce qu'un titre peu écouté mais très
        réagi est précisément ce qu'un classement par volume enterre. Mesuré sur
        ce catalogue : le titre le plus écouté (3 794 écoutes) engage à 8,1 %
        quand un autre à 1 389 écoutes engage à 16,8 % — deux fois mieux, et
        invisible dans un tri par écoutes.

    UNE SEULE TEINTE. Les deux cadres parlent de la même plateforme ; leur donner
    deux couleurs inventerait deux familles. L'intensité porte la valeur.
    """
    n = min(len(df_top), 15)
    d = df_top.head(n).iloc[::-1]      # plotly empile de bas en haut

    from plotly.subplots import make_subplots
    fig = make_subplots(
        rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.04,
        subplot_titles=[
            t("soundcloud.top_volume", "Volume — {m}").format(m=sort_by),
            t("soundcloud.top_rate", "Taux d'engagement (%)")])

    _valeurs = pd.to_numeric(d[sort_col], errors="coerce").fillna(0)
    fig.add_trace(go.Bar(
        y=d["title"], x=_valeurs, orientation="h", name=sort_by,
        marker_color=_SC, opacity=0.9,
        text=[f"{int(v):,}".replace(",", " ") for v in _valeurs],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>%{x:,.0f}<extra></extra>"), row=1, col=1)

    _taux = pd.to_numeric(d["eng_rate"], errors="coerce")
    fig.add_trace(go.Bar(
        y=d["title"], x=_taux, orientation="h",
        name=t("soundcloud.eng_rate", "Engagement %"),
        marker_color=_SC, opacity=0.45,
        text=[("—" if pd.isna(v) else f"{v:.1f} %") for v in _taux],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>%{x:.1f} %<extra></extra>"), row=1, col=2)

    fig.update_layout(
        height=max(380, 34 * n), showlegend=False, bargap=0.25,
        margin=dict(l=10, r=70, t=70),
        yaxis=dict(automargin=True))
    st.plotly_chart(fig, width="stretch")

    st.caption(t(
        "soundcloud.top_caption",
        "Les {n} premiers titres, triés par **{m}**. À droite, le **taux "
        "d'engagement** — (likes + reposts + commentaires) ÷ écoutes : c'est lui "
        "qui distingue un titre beaucoup diffusé d'un titre qui fait RÉAGIR, et "
        "un tri par volume l'enterre. Le détail chiffré reste dans le tiroir "
        "ci-dessous.").format(n=n, m=sort_by))

    # Le tableau n'est pas SUPPRIMÉ, il descend d'un cran : on y revient pour
    # chercher une valeur précise, pas pour comparer.
    with secondary_analyses(t("soundcloud.top_table", "🔢 Le détail chiffré")):
        st.dataframe(
            df_top[['title', 'playback_count', 'likes_count', 'reposts_count',
                    'comment_count', 'eng_rate', 'days_since']],
            column_config={
                "title": t("soundcloud.col_title", "Titre"),
                "playback_count": st.column_config.NumberColumn(plays_lbl, format="%d"),
                "likes_count": st.column_config.NumberColumn("❤️ Likes", format="%d"),
                "reposts_count": st.column_config.NumberColumn("🔄 Reposts", format="%d"),
                "comment_count": st.column_config.NumberColumn(
                    t("soundcloud.col_comments", "💬 Coms"), format="%d"),
                "eng_rate": st.column_config.NumberColumn(
                    t("soundcloud.col_eng_rate", "💯 Engagement %"), format="%.1f"),
                "days_since": st.column_config.NumberColumn(
                    t("soundcloud.col_days_since", "📅 Sorti il y a (j)"), format="%d"),
            },
            hide_index=True, width="stretch")


def _base100_figure(db, artist_id, selected_tracks, window):
    """(figure, légende) des quatre métriques ramenées à 100 — ou (None, message).

    ⚠️ ELLE REND une figure, elle ne la POSE pas : son appelant l'affiche dans le
    `with secondary_analyses(...)`, lexicalement, pour que les cliquets de budget
    puissent la compter comme abritée. Voir le commentaire du site d'appel.


    ⚠️ CETTE FIGURE PORTAIT SA PROPRE RÈGLE, EN PANDAS, ET ELLE ÉTAIT FAUSSE POUR
    TROIS MÉTRIQUES SUR QUATRE. Elle écartait tout point dont la valeur passait
    sous le maximum déjà vu (`s[s.cummax() == s]`) — juste pour des ÉCOUTES, qui
    ne décroissent pas, et faux pour les likes, reposts et commentaires, qui se
    retirent. Mesuré le 2026-09-21 sur le titre le plus écouté : les likes passent
    de 179 à 178, un désabonnement ordinaire, et ce seul recul disqualifiait tous
    les points suivants — **10 relevés écartés sur 18**, plus de la moitié de la
    série, avec une légende qui annonçait fièrement le nettoyage.

    La règle vit maintenant dans `v_soundcloud_track_daily` (migration 132), par
    MÉTRIQUE : un compteur à vie qui vaut exactement 0 après avoir été positif est
    une lecture ratée ; un compteur qui recule d'une unité est un auditeur qui a
    changé d'avis. Deux faits différents, deux traitements.

    Et elle y vit UNE fois : la figure principale, les tuiles et le classement
    lisent la même définition. C'est ce que « couche or » veut dire.
    """
    if not selected_tracks:
        return None, None
    frag, params = window.sql_between("day")
    df = db.fetch_df(f"""
        SELECT day, plays, likes, reposts, comments,
               lisible, likes_lisibles, reposts_lisibles, comments_lisibles
          FROM v_soundcloud_track_daily
         WHERE artist_id = %s AND title = ANY(%s) {frag}
         ORDER BY day
    """, (artist_id, list(selected_tracks), *params))
    if df.empty:
        return None, t("soundcloud.base100_empty",
                       "Aucun relevé sur cette période pour la sélection.")

    # Plusieurs titres sélectionnés : on somme le jour, en ne gardant que les
    # relevés lisibles de chaque métrique.
    _M = (("plays", t("soundcloud.plays", "Écoutes"), "lisible"),
          ("likes", t("soundcloud.likes", "Likes"), "likes_lisibles"),
          ("reposts", t("soundcloud.reposts", "Reposts"), "reposts_lisibles"),
          ("comments", t("soundcloud.comments", "Commentaires"), "comments_lisibles"))

    lignes, ecartes = [], 0
    total_points = 0
    for col, lbl, flag in _M:
        ok = df[df["lisible"] & df[flag]]
        total_points += len(df["day"].unique())
        serie = ok.groupby("day")[col].sum().sort_index()
        serie = serie[serie > 0]
        ecartes += len(df["day"].unique()) - len(serie)
        if len(serie) < 2 or not serie.iloc[0]:
            continue
        base = float(serie.iloc[0])
        for d, v in serie.items():
            lignes.append({"date": d, "Métrique": lbl,
                           "Base 100": round(float(v) / base * 100, 2)})

    if not lignes:
        # DEUX SILENCES, DEUX GESTES OPPOSÉS — et le garde
        # `test_a_silence_names_its_own_cause` a raison de l'exiger.
        #
        # « Rien dans CETTE fenêtre » fait ÉLARGIR ; « ce titre n'a rien à
        # montrer » fait CHANGER DE TITRE. Les confondre envoie chercher le
        # mauvais geste. On relit donc la même série SANS la fenêtre — deux
        # lectures au lieu d'une, et seulement dans la branche vide, où l'on a le
        # temps de le dire juste.
        hors = db.fetch_df("""
            SELECT MAX(day) AS last FROM v_soundcloud_track_daily
             WHERE artist_id = %s AND title = ANY(%s) AND lisible
        """, (artist_id, list(selected_tracks)))
        dernier = None if hors.empty else hors.iloc[0]["last"]
        if dernier is not None and (window.is_all_history or dernier < window.start):
            return None, t(
                "soundcloud.base100_out_of_window",
                "Aucun relevé de **{tracks}** dans cette fenêtre. Le dernier "
                "remonte au **{last}** — élargis la période pour revoir "
                "l'historique."
            ).format(tracks=", ".join(selected_tracks),
                     last=pd.to_datetime(dernier).strftime("%d/%m/%Y"))
        # LE MESSAGE NOMME LA VRAIE CAUSE. Celui d'avant accusait l'historique
        # (« ≥2 collectes par métrique ») alors que, sur le titre proposé
        # d'office, trois métriques sur quatre valaient ZÉRO partout.
        return None, t("soundcloud.base100_nothing",
                       "Rien à normaliser pour **{tracks}** : il faut au moins deux "
                       "relevés avec une valeur non nulle sur une même métrique. Un "
                       "titre sans like n'a pas d'évolution de likes.")\
            .format(tracks=", ".join(selected_tracks))

    fig = px.line(pd.DataFrame(lignes), x="date", y="Base 100", color="Métrique",
                  markers=True,
                  title=t("soundcloud.base100_title",
                          "Évolution des métriques — base 100 ({label})")
                  .format(label=window.label))
    fig.update_layout(hovermode="x unified",
                      yaxis_title=t("soundcloud.base100_axis",
                                    "Base 100 (1er pt = 100)"))
    return fig, t("soundcloud.base100_caption",
                 "Chaque métrique vaut 100 à son premier relevé lisible : c'est ce "
                 "qui permet de comparer des écoutes en milliers à des commentaires "
                 "en dizaines. Les relevés dont un compteur vaut 0 APRÈS avoir été "
                 "positif sont écartés — c'est une lecture ratée, pas une "
                  "désaffection. Un simple recul, lui, est CONSERVÉ : un like se "
                  "retire.")


def _nuances(n: int) -> list[str]:
    """`n` nuances de l'orange SoundCloud, de la plus sombre à la plus claire.

    Les séries d'une même plateforme se distinguent par la CLARTÉ, pas par la
    teinte : c'est la règle que `platform_colors` applique entre plateformes, et
    elle vaut à l'intérieur de l'une. Un écart de clarté survit à la
    deutéranopie ; un écart de teinte dans l'arc chaud n'y survit pas — c'est la
    mesure du 2026-09-08 (ΔE 4,6 entre les teintes de marque).

    La bande est volontairement étroite (0,35 → 0,80 de mélange vers le blanc) :
    au-delà, les dernières séries deviennent illisibles sur un fond clair.
    """
    import colorsys
    r, g, b = (int(_SC.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, li, sa = colorsys.rgb_to_hls(r, g, b)
    if n <= 1:
        return [_SC]
    out = []
    for i in range(n):
        # De `li` (la clarté mesurée) vers 0,80, réparti uniformément.
        clarte = li + (0.80 - li) * (i / (n - 1))
        rr, gg, bb = colorsys.hls_to_rgb(h, clarte, sa)
        out.append("#%02x%02x%02x" % (round(rr * 255), round(gg * 255), round(bb * 255)))
    return out
