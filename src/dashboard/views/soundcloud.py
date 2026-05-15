import streamlit as st
import pandas as pd
import plotly.express as px
from src.dashboard.utils import view_session
from src.dashboard.utils.period_filter import EntitySpec, entity_period_filter

def show():
    st.title("☁️ SoundCloud - Performance")
    st.markdown("---")

    with view_session() as (db, artist_id):
        # =========================================================================
        # 1. KPIs GLOBAUX (Dernière date connue)
        # =========================================================================
        try:
            df_latest = db.fetch_df("""
                SELECT DISTINCT ON (track_id)
                    track_id, title, permalink_url, playback_count,
                    likes_count, reposts_count, comment_count,
                    track_created_at, collected_at
                FROM soundcloud_tracks_daily
                WHERE artist_id = %s
                ORDER BY track_id, collected_at DESC
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

                # Calculs
                total_plays = df_latest['playback_count'].sum()
                total_likes = df_latest['likes_count'].sum()
                total_reposts = df_latest['reposts_count'].sum()
                total_comments = df_latest['comment_count'].sum()
                total_tracks = len(df_latest)

                # Récupération de la dernière date de collecte
                last_date_str = pd.to_datetime(df_latest['collected_at']).max().strftime('%d/%m/%Y')

                # Affichage sur 2 lignes
                c1, c2, c3 = st.columns(3)
                c1.metric("🎧 Total Écoutes", f"{int(total_plays):,}")
                c2.metric("❤️ Total Likes", f"{int(total_likes):,}")
                c3.metric("🔄 Total Reposts", f"{int(total_reposts):,}")

                c4, c5, c6 = st.columns(3)
                c4.metric("💬 Total Commentaires", f"{int(total_comments):,}")
                c5.metric("🎵 Titres en ligne", total_tracks)
                c6.metric("📅 Dernière mise à jour", last_date_str)

                st.caption(
                    "ℹ️ Likes & historique fiables depuis le 15/05/2026 "
                    "(collecte OAuth user-token). Sources CSV S4A/Apple non "
                    "liées — autre sujet."
                )

            else:
                st.warning("Aucune donnée SoundCloud trouvée. Lancez le collecteur.")
                return

        except Exception as e:
            st.error(f"Erreur SQL (KPIs) : {e}")
            return

        st.markdown("---")

        # =========================================================================
        # 2. ANALYSE TEMPORELLE (Filtres Dynamiques)
        # =========================================================================
        st.subheader("📈 Évolution des écoutes")

        # --- FILTRES --- (entity + smart period, factorisés)
        with st.expander("⚙️ Filtres du graphique", expanded=True):
            selected_tracks, window = entity_period_filter(
                db,
                spec=EntitySpec("soundcloud_tracks_daily", "title", "collected_at",
                                multi=True, default_count=1,
                                release_column="track_created_at"),
                artist_id=artist_id, key_prefix="sc",
                label="Filtrer par titres",
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
                df_history['collected_at'] = pd.to_datetime(df_history['collected_at']).dt.date

                # APPLICATION DES FILTRES
                mask_date = (df_history['collected_at'] >= start_d) & (df_history['collected_at'] <= end_d)
                mask_track = df_history['title'].isin(selected_tracks)

                df_filtered = df_history[mask_date & mask_track]

                if not df_filtered.empty:
                    # Graphique linéaire
                    fig = px.line(
                        df_filtered,
                        x='collected_at',
                        y='playback_count',
                        color='title',
                        title=f"Croissance ({start_d.strftime('%d/%m')} - {end_d.strftime('%d/%m')})",
                        markers=True
                    )
                    fig.update_layout(
                        xaxis_title="Date",
                        yaxis_title="Écoutes Cumulées",
                        hovermode="x unified",
                        legend=dict(orientation="h", y=-0.2)  # Légende en bas pour ne pas cacher
                    )
                    st.plotly_chart(fig, width="stretch")

                    # --- Évolution des métriques (base 100, échelles comparables) ---
                    st.subheader("📈 Évolution des métriques (base 100)")
                    _m = {'playback_count': 'Écoutes', 'likes_count': 'Likes',
                          'reposts_count': 'Reposts', 'comment_count': 'Commentaires'}
                    agg = (df_filtered.groupby('collected_at')[list(_m)]
                           .sum().sort_index())
                    norm_rows = []
                    for col, lbl in _m.items():
                        s = agg[col].astype('float')
                        if col == 'likes_count':
                            # pre-fix client_credentials 0s = not collected
                            s = s[s > 0]
                        s = s.dropna()
                        if len(s) < 2 or not s.iloc[0]:
                            continue
                        base = s.iloc[0]
                        for d, v in s.items():
                            norm_rows.append({'date': d, 'Métrique': lbl,
                                              'Base 100': round(v / base * 100, 2)})
                    if norm_rows:
                        df_norm = pd.DataFrame(norm_rows)
                        fig_n = px.line(
                            df_norm, x='date', y='Base 100', color='Métrique',
                            title=f"Évolution des métriques — base 100 ({window.label})",
                            markers=True,
                        )
                        fig_n.update_layout(
                            hovermode="x unified",
                            yaxis_title="Base 100 (1er pt = 100)",
                        )
                        st.plotly_chart(fig_n, width="stretch")
                        st.caption(
                            "Likes : fiables à partir du 15/05/2026 (collecte "
                            "OAuth user-token) — points antérieurs masqués."
                        )
                    else:
                        st.info("Pas assez d'historique pour une évolution "
                                "(≥2 collectes par métrique).")
                else:
                    st.info("Aucune donnée pour cette sélection (Vérifiez les dates ou les titres).")
            else:
                st.info("Historique vide pour le moment.")

        except Exception as e:
            st.error(f"Erreur historique : {e}")

        st.markdown("---")

        # =========================================================================
        # 3. TOP TITRES (Tableau épuré)
        # =========================================================================
        st.subheader("🏆 Top Titres")
        if not df_latest.empty:
            df_top = df_latest.copy()
            _eng = (df_top['likes_count'] + df_top['reposts_count']
                    + df_top['comment_count'])
            df_top['eng_total'] = _eng
            _pc = df_top['playback_count'].replace(0, pd.NA)
            df_top['eng_rate'] = (_eng / _pc * 100).round(1)
            df_top['days_since'] = (
                pd.Timestamp.now() - pd.to_datetime(df_top['track_created_at'])
            ).dt.days

            sort_by = st.segmented_control(
                "Trier par", ["Écoutes", "Engagement"],
                default="Écoutes", key="sc_sort",
            ) or "Écoutes"
            sort_col = 'playback_count' if sort_by == "Écoutes" else 'eng_total'
            df_top = df_top.sort_values(by=sort_col, ascending=False)

            cols_to_show = ['title', 'playback_count', 'likes_count',
                            'reposts_count', 'comment_count', 'eng_rate',
                            'days_since']
            st.dataframe(
                df_top[cols_to_show],
                column_config={
                    "title": "Titre",
                    "playback_count": st.column_config.NumberColumn("Écoutes", format="%d"),
                    "likes_count": st.column_config.NumberColumn("❤️ Likes", format="%d"),
                    "reposts_count": st.column_config.NumberColumn("🔄 Reposts", format="%d"),
                    "comment_count": st.column_config.NumberColumn("💬 Coms", format="%d"),
                    "eng_rate": st.column_config.NumberColumn("💯 Engagement %", format="%.1f"),
                    "days_since": st.column_config.NumberColumn("📅 Sorti il y a (j)", format="%d"),
                },
                hide_index=True,
                width="stretch",
            )

if __name__ == "__main__":
    show()
