"""Vue Streamlit pour YouTube (Optimisée Dark Mode & Multi-Axes)."""
import streamlit as st
import plotly.graph_objects as go
import isodate
from datetime import datetime, timedelta
from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t
from src.dashboard.utils.period_filter import smart_period_filter

def parse_duration(duration_str):
    """Convertit 'PT1M30S' en secondes."""
    try:
        if not duration_str: return 0
        td = isodate.parse_duration(duration_str)
        return td.total_seconds()
    except:
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
            hist_query = f"""
                SELECT date(collected_at) as date,
                       MAX(subscriber_count) as subs,
                       MAX(view_count) as views
                FROM youtube_channel_history
                WHERE artist_id = %s {frag}
                GROUP BY date(collected_at)
                ORDER BY date
            """
            df_hist = db.fetch_df(hist_query, (artist_id, *frag_params))

            if not df_hist.empty:
                fig_channel = go.Figure()

                # Axe Y1 (Gauche) : Abonnés (ligne + marqueurs, PAS de remplissage)
                # fill='tozeroy' ancrait la bande à 0 → avec des comptes absolus élevés,
                # les variations quotidiennes paraissaient plates. On garde une ligne
                # simple et on resserre l'axe sur la plage réelle (voir update_layout).
                fig_channel.add_trace(go.Scatter(
                    x=df_hist['date'], y=df_hist['subs'],
                    name=t("youtube.subscribers", "Abonnés"),
                    mode='lines+markers',
                    line=dict(color='#FF0000', width=2),
                    yaxis='y'
                ))

                # Axe Y2 (Droite) : Vues Totales (Blanc/Gris clair pour Dark Mode)
                # ✅ CORRECTION COULEUR (Visible sur fond noir)
                fig_channel.add_trace(go.Scatter(
                    x=df_hist['date'], y=df_hist['views'],
                    name=t("youtube.total_views", "Vues Totales"),
                    mode='lines+markers',
                    line=dict(color='#E0E0E0', width=2, dash='dot'),
                    yaxis='y2'
                ))

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

                fig_channel.update_layout(
                    title=t("youtube.channel_chart_title", "Croissance : Abonnés vs Vues Totales"),
                    xaxis=dict(title=t("common.date", "Date")),
                    yaxis=dict(
                        title=dict(text=t("youtube.subscribers", "Abonnés"), font=dict(color="#FF0000")),
                        tickfont=dict(color="#FF0000"),
                        range=subs_range,
                        tickformat="~s",  # SI suffix (1.2k, 3.4M) — legible at any scale
                    ),
                    yaxis2=dict(
                        title=dict(text=t("youtube.cumulative_views", "Vues Cumulées"), font=dict(color="#E0E0E0")),
                        tickfont=dict(color="#E0E0E0"),
                        overlaying='y',
                        side='right',
                        showgrid=False,
                        tickformat="~s",
                    ),
                    hovermode='x unified',
                    legend=dict(orientation="h", y=1.1),
                    height=450
                )
                st.plotly_chart(fig_channel, width="stretch")

                # KPIs actuels
                latest = df_hist.iloc[-1]
                c1, c2 = st.columns(2)
                c1.metric(t("youtube.kpi_current_subs", "👥 Abonnés Actuels"), f"{int(latest['subs']):,}")
                c2.metric(t("youtube.kpi_total_views", "👁️ Vues Totales"), f"{int(latest['views']):,}")

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
                    # GRAPHIQUE 4 AXES (Vues, Likes, Coms, Ratio)
                    fig_top = go.Figure()

                    # 1. Vues (Barres - Axe Gauche)
                    fig_top.add_trace(go.Bar(
                        x=df_top['title'],
                        y=df_top['view_count'],
                        name=t("youtube.views", "Vues"),
                        marker_color='#FF0000', # Rouge
                        yaxis='y'
                    ))

                    # 2. Likes (Ligne - Axe Droit 1)
                    fig_top.add_trace(go.Scatter(
                        x=df_top['title'],
                        y=df_top['like_count'],
                        name='Likes',
                        mode='lines+markers',
                        line=dict(color='#2ECC71', width=3), # Vert
                        yaxis='y2'
                    ))

                    # 3. Commentaires (Ligne - Axe Droit 2 - Décalé)
                    fig_top.add_trace(go.Scatter(
                        x=df_top['title'],
                        y=df_top['comment_count'],
                        name=t("youtube.comments", "Commentaires"),
                        mode='lines+markers',
                        line=dict(color='#9B59B6', width=2), # Violet
                        yaxis='y3'
                    ))

                    # 4. Ratio Vues/Like (Ligne - Axe Droit 3 - Décalé)
                    # Note : Plus c'est bas, meilleur c'est
                    fig_top.add_trace(go.Scatter(
                        x=df_top['title'],
                        y=df_top['ratio_views_like'],
                        name=t("youtube.ratio_views_like", "Ratio Vues/Like"),
                        mode='lines',
                        line=dict(color='#F1C40F', width=2, dash='dot'), # Jaune
                        yaxis='y4'
                    ))

                    fig_top.update_layout(
                        title=t("youtube.top_chart_title", "Top {n} {type}").format(n=top_n, type=selected_type),
                        xaxis=dict(title="", tickangle=45),

                        # Axe 1 : Vues (Gauche)
                        yaxis=dict(
                            title=dict(text=t("youtube.views", "Vues"), font=dict(color="#FF0000")),
                            tickfont=dict(color="#FF0000"),
                            side='left',
                            showgrid=True
                        ),

                        # Axe 2 : Likes (Droite)
                        yaxis2=dict(
                            title=dict(text="Likes", font=dict(color="#2ECC71")),
                            tickfont=dict(color="#2ECC71"),
                            side='right',
                            overlaying='y',
                            showgrid=False
                        ),

                        # Axe 3 : Commentaires (Droite décalée)
                        yaxis3=dict(
                            title=dict(text=t("youtube.coms_axis", "Coms"), font=dict(color="#9B59B6")),
                            tickfont=dict(color="#9B59B6"),
                            anchor="free",
                            overlaying='y',
                            side='right',
                            position=0.94, # Décalage vers la gauche
                            showgrid=False
                        ),

                        # Axe 4 : Ratio (Droite décalée)
                        yaxis4=dict(
                            title=dict(text=t("youtube.ratio_axis", "Ratio V/L"), font=dict(color="#F1C40F")),
                            tickfont=dict(color="#F1C40F"),
                            anchor="free",
                            overlaying='y',
                            side='right',
                            position=0.88, # Décalage encore plus à gauche
                            showgrid=False
                        ),

                        hovermode='x unified',
                        # Légende en haut pour ne pas gêner
                        legend=dict(orientation="h", y=1.15, x=0.5, xanchor='center'),
                        height=650,
                        margin=dict(b=100, r=50) # Marges pour les axes multiples
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
