"""Vue Streamlit pour YouTube (Optimisée Dark Mode & Multi-Axes)."""
import streamlit as st
import plotly.graph_objects as go
import isodate
from datetime import datetime, timedelta
from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t
from src.dashboard.utils.period_filter import smart_period_filter
from src.dashboard.utils import platform_timeseries as pts

def parse_duration(duration_str):
    """Convertit 'PT1M30S' en secondes."""
    try:
        if not duration_str: return 0
        td = isodate.parse_duration(duration_str)
        return td.total_seconds()
    except Exception:
        return 0

def show():
    st.title(t("youtube.title", "🎬 YouTube Analytics"))
    st.markdown(t("youtube.subtitle", "### Analyse de la Chaîne et des Vidéos"))
    st.markdown("---")

    with view_session() as (db, artist_id):
        try:
            # ============================================================================
            # 1. ANALYSE GLOBALE (CHAÎNE)
            # ============================================================================
            st.subheader(t("youtube.channel_header", "📈 Évolution de la Chaîne"))

            window = smart_period_filter(
                db, table="youtube_channel_history", date_column="collected_at",
                artist_id=artist_id, key="yt_channel", default_override="all",
            )
            frag, frag_params = window.sql_between("collected_at")
            # Les ABONNÉS n'existent que sur la chaîne — cette table est leur seule
            # source. Les VUES, non : le compteur de chaîne porte des vidéos absentes
            # du catalogue et avance par paliers. Il est lu plus bas, sous son propre
            # nom, et la courbe vient de la couche or. Voir
            # `platform_timeseries.youtube_cumulative_views`.
            hist_query = f"""
                SELECT date(collected_at) as date,
                       MAX(subscriber_count) as subs,
                       MAX(view_count) as channel_views
                FROM youtube_channel_history
                WHERE artist_id = %s {frag}
                GROUP BY date(collected_at)
                ORDER BY date
            """
            df_hist = db.fetch_df(hist_query, (artist_id, *frag_params))

            views_series = [
                (d, v) for d, v in pts.youtube_cumulative_views(db, artist_id)
                if window.is_all_history or window.start <= d <= window.end
            ]

            if not df_hist.empty:
                from plotly.subplots import make_subplots
                fig_channel = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                            vertical_spacing=0.09,
                                            subplot_titles=[
                                                t("youtube.subscribers", "Abonnés"),
                                                t("youtube.cumulative_views",
                                                  "Vues Cumulées")])

                # Axe Y1 (Gauche) : Abonnés (ligne + marqueurs, PAS de remplissage)
                # fill='tozeroy' ancrait la bande à 0 → avec des comptes absolus élevés,
                # les variations quotidiennes paraissaient plates. On garde une ligne
                # simple et on resserre l'axe sur la plage réelle (voir update_layout).
                fig_channel.add_trace(go.Scatter(
                    x=df_hist['date'], y=df_hist['subs'],
                    name=t("youtube.subscribers", "Abonnés"),
                    mode='lines+markers',
                    line=dict(color='#FF0000', width=2),
                ), row=1, col=1)

                # Axe Y2 (Droite) : Vues Totales (Blanc/Gris clair pour Dark Mode)
                # ✅ CORRECTION COULEUR (Visible sur fond noir)
                fig_channel.add_trace(go.Scatter(
                    x=[d for d, _ in views_series], y=[v for _, v in views_series],
                    name=t("youtube.total_views", "Vues Totales"),
                    mode='lines+markers',
                    line=dict(color='#E0E0E0', width=2, dash='dot'),
                ), row=2, col=1)

                # Smart range: zoom the subscriber axis onto the actual data band
                # with a small margin, instead of starting at 0. Makes day-to-day
                # evolution visible even when absolute counts are large. Falls back
                # to autorange when the series is flat (min == max).
                subs_min, subs_max = float(df_hist['subs'].min()), float(df_hist['subs'].max())
                subs_span = subs_max - subs_min
                if subs_span > 0:
                    margin = max(subs_span * 0.10, 1)
                    subs_range = [subs_min - margin, subs_max + margin]
                else:
                    subs_range = None  # flat series → let Plotly autorange

                # DEUX CADRES. Des abonnés (milliers) et un compteur de vues cumulées
                # (centaines de milliers) sur un repère commun rendent la première
                # courbe plate ; sur deux axes superposés, leur croisement est un
                # artefact de cadrage. La plage resserrée des abonnés — écrite pour
                # rendre l'évolution quotidienne visible — garde tout son sens dans son
                # propre cadre.
                fig_channel.update_yaxes(title_text=t("youtube.subscribers", "Abonnés"),
                                         range=subs_range, tickformat="~s", row=1, col=1)
                fig_channel.update_yaxes(
                    title_text=t("youtube.cumulative_views", "Vues Cumulées"),
                    tickformat="~s", row=2, col=1)
                fig_channel.update_xaxes(title_text=t("common.date", "Date"), row=2, col=1)
                fig_channel.update_layout(
                    title=t("youtube.channel_chart_title",
                            "Croissance : Abonnés vs Vues Totales"),
                    hovermode='x unified', showlegend=False, height=480,
                )
                st.plotly_chart(fig_channel, width="stretch")

                # KPIs actuels. Les deux compteurs de vues sont affichés côte à
                # côte et nommés : celui du CATALOGUE est celui de la courbe et des
                # totaux du produit, celui de la CHAÎNE est ce qu'annonce YouTube.
                # Les voir diverger est une information ; en voir un sans savoir
                # lequel est ce qui a produit 120 627 ici et 118 219 ailleurs.
                latest = df_hist.iloc[-1]
                c1, c2, c3 = st.columns(3)
                c1.metric(t("youtube.kpi_current_subs", "👥 Abonnés Actuels"),
                          f"{int(latest['subs']):,}")
                c2.metric(t("youtube.kpi_total_views", "👁️ Vues Totales"),
                          f"{views_series[-1][1]:,}" if views_series else "—")
                c3.metric(t("youtube.kpi_channel_views", "📺 Vues de la chaîne"),
                          f"{int(latest['channel_views']):,}",
                          help=t("youtube.kpi_channel_views_help",
                                 "Compteur annoncé par YouTube pour la chaîne entière : "
                                 "il inclut les vidéos privées, supprimées et les "
                                 "agrégats internes, absents du catalogue analysé ici."))

            else:
                st.info(t("youtube.no_channel_history", "Pas encore d'historique pour la chaîne."))

            st.markdown("---")

            # ============================================================================
            # 2. ANALYSE VIDÉOS (TOP & SHORTS)
            # ============================================================================

            # ── Release-date filter (mirrors S4A / Apple / SoundCloud / Meta) ────
            st.subheader(t("youtube.top_header", "🏆 Top Contenus (Analyse Multi-Axes)"))

            _all_lbl = t("common.all", "Tous")
            _PERIOD_OPTIONS = {
                _all_lbl: None,
                t("youtube.period_12m", "12 derniers mois"): 365,
                t("youtube.period_6m", "6 derniers mois"): 180,
                t("youtube.period_3m", "3 derniers mois"): 90,
                t("youtube.period_30d", "30 derniers jours"): 30,
            }
            c_period, c_filter1, c_filter2 = st.columns(3)
            with c_period:
                period_label = st.selectbox(t("youtube.publish_period", "Période de publication"), list(_PERIOD_OPTIONS.keys()))
            days_back = _PERIOD_OPTIONS[period_label]
            published_since = (
                datetime.now() - timedelta(days=days_back) if days_back else None
            )

            # Récupération des vidéos + stats
            if published_since:
                videos_query = """
                    SELECT
                        v.title, v.duration, v.published_at, v.thumbnail_url,
                        vs.view_count, vs.like_count, vs.comment_count
                    FROM youtube_videos v
                    JOIN (
                        SELECT video_id, MAX(collected_at) as max_date
                        FROM youtube_video_stats
                        WHERE artist_id = %s
                        GROUP BY video_id
                    ) latest ON v.video_id = latest.video_id
                    JOIN youtube_video_stats vs
                        ON vs.video_id = latest.video_id AND vs.collected_at = latest.max_date
                    WHERE v.artist_id = %s
                      AND v.published_at >= %s
                    ORDER BY v.published_at DESC
                """
                df_videos = db.fetch_df(videos_query, (artist_id, artist_id, published_since))
            else:
                videos_query = """
                    SELECT
                        v.title, v.duration, v.published_at, v.thumbnail_url,
                        vs.view_count, vs.like_count, vs.comment_count
                    FROM youtube_videos v
                    JOIN (
                        SELECT video_id, MAX(collected_at) as max_date
                        FROM youtube_video_stats
                        WHERE artist_id = %s
                        GROUP BY video_id
                    ) latest ON v.video_id = latest.video_id
                    JOIN youtube_video_stats vs
                        ON vs.video_id = latest.video_id AND vs.collected_at = latest.max_date
                    WHERE v.artist_id = %s
                    ORDER BY v.published_at DESC
                """
                df_videos = db.fetch_df(videos_query, (artist_id, artist_id))

            if not df_videos.empty:
                # Traitement
                _short_lbl = t("youtube.type_short", "Short 📱")
                _video_lbl = t("youtube.type_video", "Vidéo 📹")
                df_videos['seconds'] = df_videos['duration'].apply(parse_duration)
                df_videos['type'] = df_videos['seconds'].apply(lambda x: _short_lbl if 0 < x <= 60 else _video_lbl)

                # Calcul Ratio Vues/Like (Combien de vues pour 1 like ?)
                df_videos['ratio_views_like'] = df_videos.apply(
                    lambda x: x['view_count'] / x['like_count'] if x['like_count'] > 0 else 0, axis=1
                )

                with c_filter1:
                    selected_type = st.selectbox(t("youtube.content_type", "Type de contenu"), [_all_lbl, _video_lbl, _short_lbl])
                with c_filter2:
                    top_n = st.slider(t("youtube.n_videos", "Nombre de vidéos"), 5, 50, 10)

                # Application filtres
                df_filtered = df_videos.copy()
                if selected_type != _all_lbl:
                    df_filtered = df_filtered[df_filtered['type'] == selected_type]

                df_top = df_filtered.head(top_n)

                if not df_top.empty:
                    # QUATRE MESURES, QUATRE CADRES — plus quatre axes superposés.
                    #
                    # Cette figure empilait `yaxis` à `yaxis4` : des vues (dizaines de
                    # milliers), des likes (centaines), des commentaires (dizaines) et
                    # un ratio sans unité, forcés à partager un même repère par simple
                    # décalage de côté. Un lecteur ne peut pas comparer deux courbes qui
                    # n'ont ni la même unité ni la même échelle ; il lit une forme, et
                    # cette forme ne veut rien dire.
                    #
                    # Les petits multiples sont la seule alternative admise dans ce
                    # produit — la figure de l'accueil porte la même décision, écrite le
                    # 2026-09-08. On perd la superposition, on gagne quatre séries
                    # réellement lisibles, chacune sur SON échelle.
                    from plotly.subplots import make_subplots

                    _panels = [
                        (t("youtube.views", "Vues"), "view_count", "#2a78d6", "bar"),
                        ("Likes", "like_count", "#1baf7a", "line"),
                        (t("youtube.comments", "Commentaires"), "comment_count",
                         "#eb6834", "line"),
                        (t("youtube.ratio_views_like", "Ratio Vues/Like"),
                         "ratio_views_like", "#eda100", "line"),
                    ]
                    fig_top = make_subplots(
                        rows=len(_panels), cols=1, shared_xaxes=True,
                        vertical_spacing=0.05,
                        subplot_titles=[lbl for lbl, _, _, _ in _panels],
                    )
                    for _row, (_lbl, _col, _colour, _kind) in enumerate(_panels, start=1):
                        _trace = (go.Bar(x=df_top['title'], y=df_top[_col],
                                         name=_lbl, marker_color=_colour)
                                  if _kind == "bar" else
                                  go.Scatter(x=df_top['title'], y=df_top[_col],
                                             name=_lbl, mode='lines+markers',
                                             line=dict(color=_colour, width=2)))
                        fig_top.add_trace(_trace, row=_row, col=1)

                    fig_top.update_layout(
                        title=t("youtube.top_chart_title", "Top {n} {type}").format(
                            n=top_n, type=selected_type),
                        showlegend=False,          # chaque cadre porte son propre titre
                        hovermode='x unified',
                        height=180 * len(_panels),
                        margin=dict(b=90, r=20),
                    )

                    st.plotly_chart(fig_top, width="stretch")

                else:
                    st.info(t("youtube.no_video_category", "Aucune vidéo dans cette catégorie."))
            else:
                st.warning(t("youtube.no_video_db", "Aucune vidéo trouvée en base."))

        except Exception as e:
            st.error(t("youtube.error", "Erreur : {err}").format(err=e))

if __name__ == "__main__":
    show()
