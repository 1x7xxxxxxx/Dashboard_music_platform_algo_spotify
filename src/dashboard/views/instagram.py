import streamlit as st
import pandas as pd
import plotly.express as px
from src.dashboard.utils import get_db_connection
from src.dashboard.utils.period_filter import smart_period_filter
from src.dashboard.auth import get_artist_id, is_admin

def show():
    st.title("📸 Instagram - Performance")
    st.markdown("---")

    db = get_db_connection()
    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin():
            st.error("Session invalide."); st.stop()
        artist_id = 1  # admin: defaults to artist 1 — full cross-tenant view in Admin panel

    try:
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
                followers = df_latest['followers_count'].iloc[0]
                media = df_latest['media_count'].iloc[0]
                username = df_latest['username'].iloc[0]
                last_date = pd.to_datetime(df_latest['collected_at'].iloc[0]).strftime('%d/%m/%Y')

                st.subheader(f"Compte : @{username}")

                c1, c2, c3 = st.columns(3)
                c1.metric("👥 Abonnés", f"{int(followers):,}")
                c2.metric("📸 Publications", f"{int(media):,}")
                c3.metric("📅 Mise à jour", last_date)
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
                SELECT collected_at, followers_count, media_count
                FROM instagram_daily_stats
                WHERE artist_id = %s {frag}
                ORDER BY collected_at ASC
            """
            df_hist = db.fetch_df(query, (artist_id, *frag_params))

            if not df_hist.empty:
                df_hist['collected_at'] = pd.to_datetime(df_hist['collected_at'])

                # Graphique Abonnés
                fig = px.area(
                    df_hist,
                    x='collected_at',
                    y='followers_count',
                    title=f"Évolution des Abonnés ({window.label})",
                    markers=True,
                    color_discrete_sequence=['#E1306C']  # Couleur Insta
                )
                fig.update_layout(yaxis_title="Nombre d'abonnés")
                st.plotly_chart(fig, width="stretch")

        except Exception as e:
            st.error(f"Erreur historique : {e}")

        # 3. PUBLICATIONS RÉCENTES (posts + insights)
        st.markdown("---")
        st.subheader("📝 Publications récentes")

        win_m = smart_period_filter(
            db, table="instagram_media", date_column="timestamp",
            artist_id=artist_id, key="ig_media",
        )
        try:
            frag_m, params_m = win_m.sql_between("timestamp")
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
            df_media = db.fetch_df(q_media, (artist_id, *params_m))

            if df_media.empty:
                st.info("Aucune publication collectée pour cette période.")
            else:
                st.dataframe(
                    df_media,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "media_url": st.column_config.ImageColumn("Aperçu"),
                        "permalink": st.column_config.LinkColumn(
                            "Lien", display_text="Ouvrir"),
                        "caption": st.column_config.TextColumn(
                            "Légende", width="medium"),
                        "timestamp": st.column_config.DatetimeColumn(
                            "Publié le", format="DD/MM/YYYY"),
                        "like_count": "❤️ Likes",
                        "comments_count": "💬 Comm.",
                    },
                )
        except Exception as e:
            st.error(f"Erreur publications : {e}")

    finally:
        db.close()

if __name__ == "__main__":
    show()
