import streamlit as st
import pandas as pd
import plotly.express as px
from src.dashboard.utils import view_session
from src.dashboard.utils.period_filter import smart_period_filter
from src.dashboard.utils.ui import show_empty_state

def show():
    st.title("📸 Instagram - Performance")
    st.markdown("---")

    with view_session() as (db, artist_id):
        # 1. KPIs (Dernier Snapshot)
        try:
            df_latest = db.fetch_df("""
                SELECT DISTINCT ON (ig_user_id)
                    ig_user_id, username, followers_count, follows_count,
                    media_count, collected_at
                FROM instagram_daily_stats
                WHERE artist_id = %s
                ORDER BY ig_user_id, collected_at DESC
            """, (artist_id,))

            if not df_latest.empty:
                followers = int(df_latest['followers_count'].iloc[0] or 0)
                follows = int(df_latest['follows_count'].iloc[0] or 0)
                media = int(df_latest['media_count'].iloc[0] or 0)
                username = df_latest['username'].iloc[0]
                last_date = pd.to_datetime(df_latest['collected_at'].iloc[0]).strftime('%d/%m/%Y')

                st.subheader(f"Compte : @{username}")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("👥 Abonnés", f"{followers:,}")
                c2.metric("➡️ Abonnements", f"{follows:,}")
                c3.metric("📸 Publications", f"{media:,}")
                c4.metric("📅 Mise à jour", last_date)
            else:
                st.warning("Aucune donnée Instagram. Lancez le collecteur.")
                return

        except Exception as e:
            st.error(e)
            return

        st.markdown("---")

        # 2. GRAPHIQUE D'ÉVOLUTION
        st.subheader("📈 Croissance de la communauté")

        window = smart_period_filter(
            db, table="instagram_daily_stats", date_column="collected_at",
            artist_id=artist_id, key="ig_community",
        )

        try:
            frag, frag_params = window.sql_between("collected_at")
            query = f"""
                SELECT collected_at, followers_count, follows_count, media_count
                FROM instagram_daily_stats
                WHERE artist_id = %s {frag}
                ORDER BY collected_at ASC
            """
            df_hist = db.fetch_df(query, (artist_id, *frag_params))

            if not show_empty_state(df_hist, "Aucune donnée d'historique pour cette période."):
                df_hist['collected_at'] = pd.to_datetime(df_hist['collected_at'])

                # Abonnés — px.line + axe Y serré : la variation macro doit
                # rester lisible (px.area pinnait l'axe à 0 → tendance écrasée).
                fig = px.line(
                    df_hist, x='collected_at', y='followers_count',
                    title=f"Évolution des Abonnés ({window.label})",
                    markers=True, color_discrete_sequence=['#E1306C'],
                )
                ymin = df_hist['followers_count'].min()
                ymax = df_hist['followers_count'].max()
                pad = max((ymax - ymin) * 0.15, 1)
                fig.update_layout(
                    yaxis=dict(range=[ymin - pad, ymax + pad]),
                    yaxis_title="Nombre d'abonnés", hovermode="x unified",
                )
                st.plotly_chart(fig, width="stretch")

                # Évolution relative base 100 : échelles comparables sur 1 axe.
                st.subheader("📈 Évolution relative (base 100)")
                if len(df_hist) < 2:
                    st.info("Pas assez d'historique pour une évolution (≥2 collectes).")
                else:
                    _metrics = {
                        'followers_count': 'Abonnés',
                        'follows_count': 'Abonnements',
                        'media_count': 'Publications',
                    }
                    rows = []
                    for col, lbl in _metrics.items():
                        s = df_hist[col].astype('float')
                        nonnull = s.dropna()
                        base = nonnull.iloc[0] if not nonnull.empty else 0
                        if not base:
                            continue
                        for d, v in zip(df_hist['collected_at'], s):
                            if pd.notna(v):
                                rows.append({'date': d, 'Métrique': lbl,
                                             'Base 100': round(v / base * 100, 2)})
                    if rows:
                        df_norm = pd.DataFrame(rows)
                        fig_n = px.line(
                            df_norm, x='date', y='Base 100', color='Métrique',
                            title=f"Évolution relative — base 100 ({window.label})",
                            markers=True,
                        )
                        fig_n.update_layout(
                            hovermode="x unified",
                            yaxis_title="Base 100 (1er point = 100)",
                        )
                        st.plotly_chart(fig_n, width="stretch")

        except Exception as e:
            st.error(f"Erreur historique : {e}")

        # 3. ENGAGEMENT & PUBLICATIONS
        st.markdown("---")
        st.subheader("📝 Engagement & publications")

        win_m = smart_period_filter(
            db, table="instagram_media", date_column="timestamp",
            artist_id=artist_id, key="ig_media",
        )
        try:
            frag_m, params_m = win_m.sql_between("timestamp")

            # Engagement par mois (likes + commentaires des posts réels)
            df_eng = db.fetch_df(f"""
                SELECT date_trunc('month', timestamp) AS mois,
                       SUM(like_count) AS likes,
                       SUM(comments_count) AS comments,
                       COUNT(*) AS posts
                FROM instagram_media
                WHERE artist_id = %s {frag_m}
                GROUP BY 1 ORDER BY 1
            """, (artist_id, *params_m))

            if not show_empty_state(df_eng, "Aucun post sur cette période."):
                df_eng['mois'] = pd.to_datetime(df_eng['mois'])
                df_long = df_eng.melt(
                    id_vars=['mois', 'posts'], value_vars=['likes', 'comments'],
                    var_name='Type', value_name='Total',
                )
                fig_e = px.bar(
                    df_long, x='mois', y='Total', color='Type',
                    title=f"Engagement par mois ({win_m.label})",
                    hover_data=['posts'],
                )
                fig_e.update_layout(
                    barmode='stack', hovermode="x unified",
                    yaxis_title="Likes + commentaires",
                )
                st.plotly_chart(fig_e, width="stretch")

                # Taux d'engagement (indicatif — abonnés = snapshot actuel)
                if followers:
                    dfr = df_eng.copy()
                    dfr['taux'] = (
                        (dfr['likes'] + dfr['comments']) / dfr['posts']
                        / float(followers) * 100
                    ).round(2)
                    fig_r = px.line(
                        dfr, x='mois', y='taux', markers=True,
                        title="Taux d'engagement ≈ (eng. moyen/post) ÷ abonnés — indicatif",
                        color_discrete_sequence=['#E1306C'],
                    )
                    fig_r.update_layout(
                        hovermode="x unified", yaxis_title="Taux (%)",
                    )
                    st.plotly_chart(fig_r, width="stretch")
                    st.caption(
                        "Indicatif : abonnés = dernier snapshot (historique "
                        "d'abonnés peu dense vs étendue des posts)."
                    )

            # Publications récentes — insights indispo ⇒ note + colonnes masquées
            st.markdown("#### Publications récentes")
            _ins = db.fetch_query(
                "SELECT COUNT(*) FROM instagram_media_insights WHERE artist_id = %s",
                (artist_id,),
            )
            insights_empty = not _ins or (_ins[0][0] or 0) == 0

            base_cfg = {
                "media_url": st.column_config.ImageColumn("Aperçu"),
                "permalink": st.column_config.LinkColumn("Lien", display_text="Ouvrir"),
                "caption": st.column_config.TextColumn("Légende", width="medium"),
                "timestamp": st.column_config.DatetimeColumn(
                    "Publié le", format="DD/MM/YYYY"),
                "like_count": "❤️ Likes",
                "comments_count": "💬 Comm.",
            }

            if insights_empty:
                st.info(
                    "Insights (impressions/reach/saved/partages) indisponibles : "
                    "l'API Meta ne les fournit que pour des posts < 90 jours avec "
                    "le scope instagram_manage_insights. Recollecte après une "
                    "publication récente."
                )
                q_media = f"""
                    SELECT media_url, caption, media_type, permalink,
                           timestamp, like_count, comments_count
                    FROM instagram_media
                    WHERE artist_id = %s {frag_m}
                    ORDER BY timestamp DESC
                """
                cfg = base_cfg
            else:
                q_media = f"""
                    SELECT m.media_url, m.caption, m.media_type, m.permalink,
                           m.timestamp, m.like_count, m.comments_count,
                           i.impressions, i.reach, i.engagement, i.saved, i.shares
                    FROM instagram_media m
                    LEFT JOIN LATERAL (
                        SELECT impressions, reach, engagement, saved, shares
                        FROM instagram_media_insights ii
                        WHERE ii.artist_id = m.artist_id
                          AND ii.media_id = m.media_id
                        ORDER BY ii.date DESC LIMIT 1
                    ) i ON TRUE
                    WHERE m.artist_id = %s {frag_m}
                    ORDER BY m.timestamp DESC
                """
                cfg = base_cfg

            df_media = db.fetch_df(q_media, (artist_id, *params_m))
            if not show_empty_state(
                df_media, "Aucune publication collectée pour cette période."
            ):
                st.dataframe(
                    df_media, width="stretch", hide_index=True,
                    column_config=cfg,
                )
        except Exception as e:
            st.error(f"Erreur publications : {e}")

if __name__ == "__main__":
    show()
