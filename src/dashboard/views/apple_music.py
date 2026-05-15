"""Vue Streamlit pour Apple Music."""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.period_filter import smart_period_filter
from src.dashboard.auth import get_artist_id, is_admin

def show():
    """Affiche la vue Apple Music."""
    st.title("🍎 Apple Music Analytics")
    st.markdown("### Analyse des performances et croissance quotidienne")
    st.markdown("---")

    db = get_db_connection()
    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin():
            st.error("Session invalide."); st.stop()
        artist_id = 1  # admin: defaults to artist 1 — full cross-tenant view in Admin panel

    try:
        # ============================================================
        # 1. KPIs GLOBAUX
        # ============================================================
        st.subheader("📊 Vue d'ensemble")

        col1, col2, col3 = st.columns(3)

        # Total des chansons
        songs_count = db.get_table_count('apple_songs_performance')
        col1.metric("🎵 Chansons Suivies", f"{songs_count:,}")

        # Total Shazams et Plays (Dernier état connu)
        totals_query = """
            SELECT
                COALESCE(SUM(plays), 0) as total_plays,
                COALESCE(SUM(shazam_count), 0) as total_shazams
            FROM apple_songs_performance
            WHERE artist_id = %s
        """
        result = db.fetch_query(totals_query, (artist_id,))
        total_plays, total_shazams = result[0] if result else (0, 0)

        col2.metric("▶️ Total Streams (Cumul)", f"{total_plays:,}")
        col3.metric("⚡ Total Shazams (Cumul)", f"{total_shazams:,}")

        st.markdown("---")

        # ============================================================
        # 2. TOP CHANSONS (Barres)
        # ============================================================
        st.subheader("🏆 Top Chansons (Cumulé)")

        top_query = """
            SELECT song_name, plays
            FROM apple_songs_performance
            WHERE artist_id = %s
            ORDER BY plays DESC
            LIMIT 10
        """
        df_top = db.fetch_df(top_query, (artist_id,))

        if not df_top.empty:
            fig = px.bar(
                df_top,
                x='plays',
                y='song_name',
                orientation='h',
                text='plays',
                title="Top 10 par Streams",
                labels={'plays': 'Streams', 'song_name': ''},
                color='plays',
                color_continuous_scale='Reds'
            )
            fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
            fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=500)
            st.plotly_chart(fig, width="stretch")

        st.markdown("---")

        # ============================================================
        # 3. GRAPHIQUE DYNAMIQUE (CALCUL DIFFÉRENTIEL)
        # ============================================================
        st.subheader("📈 Croissance Quotidienne (Streams & Shazams)")

        # Récupérer la liste des chansons — triée par dernière release (MIN date DESC)
        songs_list = db.fetch_df("""
            SELECT song_name FROM apple_songs_history
            WHERE artist_id = %s
            GROUP BY song_name ORDER BY MIN(date) DESC
        """, (artist_id,))

        if not songs_list.empty:
            # Filtre dynamique — défaut : 3 premières (= 3 dernières releases)
            selected_songs = st.multiselect(
                "🔍 Filtrer par chanson(s)",
                options=songs_list['song_name'].tolist(),
                default=songs_list['song_name'].tolist()[:3]
            )

            if selected_songs:
                placeholders = ','.join(['%s'] * len(selected_songs))

                def _apple_release():
                    rows = db.fetch_query(
                        f"SELECT MIN(date) FROM apple_songs_history "
                        f"WHERE artist_id = %s AND song_name IN ({placeholders})",
                        (artist_id, *selected_songs),
                    )
                    return rows[0][0] if rows and rows[0][0] else None

                window = smart_period_filter(
                    db, table="apple_songs_history", date_column="date",
                    artist_id=artist_id, key="apple_daily",
                    latest_release_resolver=_apple_release,
                )
                frag, frag_params = window.sql_between("date")

                # Requête SQL avec LAG() : Valeur Aujourd'hui - Valeur Hier
                daily_calc_query = f"""
                    WITH daily_diff AS (
                        SELECT
                            date,
                            song_name,
                            plays,
                            shazam_count,
                            plays - LAG(plays) OVER (PARTITION BY song_name ORDER BY date) as daily_streams,
                            shazam_count - LAG(shazam_count) OVER (PARTITION BY song_name ORDER BY date) as daily_shazams
                        FROM apple_songs_history
                        WHERE artist_id = %s AND song_name IN ({placeholders})
                    )
                    SELECT * FROM daily_diff
                    WHERE daily_streams IS NOT NULL {frag}
                    ORDER BY date
                """

                df_daily = db.fetch_df(
                    daily_calc_query, (artist_id, *selected_songs, *frag_params)
                )

                if not df_daily.empty:
                    # Nettoyage des valeurs négatives (si Apple corrige ses chiffres à la baisse)
                    df_daily['daily_streams'] = df_daily['daily_streams'].apply(lambda x: max(0, x))
                    df_daily['daily_shazams'] = df_daily['daily_shazams'].apply(lambda x: max(0, x))

                    fig = go.Figure()
                    for song in df_daily['song_name'].unique():
                        d = df_daily[df_daily['song_name'] == song]
                        fig.add_trace(go.Scatter(
                            x=d['date'], y=d['daily_streams'],
                            name=f"🎧 {song}", mode='lines+markers', yaxis='y',
                        ))
                        fig.add_trace(go.Bar(
                            x=d['date'], y=d['daily_shazams'],
                            name=f"⚡ {song}", opacity=0.4, yaxis='y2',
                        ))
                    fig.update_layout(
                        title=f"Croissance quotidienne — Streams (lignes) & "
                              f"Shazams (barres) · {window.label}",
                        hovermode='x unified',
                        yaxis=dict(title="Streams / jour"),
                        yaxis2=dict(title="Shazams / jour", overlaying='y',
                                    side='right', showgrid=False),
                        barmode='group',
                        legend=dict(orientation='h'),
                    )
                    st.plotly_chart(fig, width="stretch")

                else:
                    st.info("📉 Pas assez d'historique pour calculer la croissance (besoin de min. 2 jours de données).")
            else:
                st.info("👈 Sélectionnez des chansons.")
        else:
            st.warning("⚠️ L'historique est vide. Importez des CSV plusieurs jours de suite pour voir les courbes.")

    except Exception as e:
        st.error(f"❌ Erreur : {e}")

    finally:
        db.close()

if __name__ == "__main__":
    show()
