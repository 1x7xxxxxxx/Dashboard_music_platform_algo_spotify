"""Vue Streamlit pour Apple Music."""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t
from src.dashboard.utils.period_filter import EntitySpec, entity_period_filter

def show():
    """Affiche la vue Apple Music."""
    st.title(t("apple_music.title", "🍎 Apple Music Analytics"))
    st.markdown(t("apple_music.subtitle",
                  "### Analyse des performances et croissance quotidienne"))
    st.markdown("---")

    with view_session() as (db, artist_id):
        try:
            # ============================================================
            # 1. KPIs GLOBAUX
            # ============================================================
            st.subheader(t("apple_music.overview", "📊 Vue d'ensemble"))

            col1, col2, col3 = st.columns(3)

            # Total des chansons (scoped to the tenant — get_table_count() is global
            # and would leak the cross-tenant song count on this per-artist metric).
            _songs_row = db.fetch_query(
                "SELECT COUNT(*) FROM apple_songs_performance WHERE artist_id = %s",
                (artist_id,),
            )
            songs_count = _songs_row[0][0] if _songs_row else 0
            col1.metric(t("apple_music.kpi_songs", "🎵 Chansons Suivies"), f"{songs_count:,}")

            # LE TOTAL PASSE PAR LA RÈGLE COMMUNE, pas par un SUM nu.
            #
            # `SUM(plays)` sur toute la table était juste tant qu'un artiste n'avait
            # qu'UN relevé — ce que la clé lui imposait avant la migration 093. Depuis
            # qu'il peut déposer un export « depuis le début » ET un export par année,
            # la somme brute compte deux fois les années contenues dans le cumul. Cette
            # page affichait donc un total Apple différent de celui de l'accueil, pour
            # le même artiste au même instant.
            from src.dashboard.utils.platform_timeseries import (
                apple_lifetime_plays, non_overlapping_cover,
            )
            total_plays = apple_lifetime_plays(db, artist_id)
            # Les Shazams suivent la même règle : on ne somme que le découpage non
            # chevauchant, sinon une année comptée dans le cumul l'est deux fois.
            _shazam_rows = db.fetch_query(
                "SELECT period_start, period_end, COALESCE(SUM(shazam_count), 0)::bigint "
                "FROM apple_songs_performance WHERE artist_id = %s "
                "  AND period_start IS NOT NULL AND period_end IS NOT NULL "
                "GROUP BY 1, 2", (artist_id,)) or []
            if _shazam_rows:
                total_shazams = sum(
                    v for _s, _e, v in non_overlapping_cover(
                        [(r[0], r[1], int(r[2] or 0)) for r in _shazam_rows]))
            else:
                _row = db.fetch_query(
                    "SELECT COALESCE(SUM(shazam_count), 0)::bigint "
                    "FROM apple_songs_performance WHERE artist_id = %s "
                    "  AND period_start IS NULL AND snapshot_date = ("
                    "    SELECT MAX(snapshot_date) FROM apple_songs_performance "
                    "     WHERE artist_id = %s AND period_start IS NULL)",
                    (artist_id, artist_id))
                total_shazams = int(_row[0][0] or 0) if _row else 0

            col2.metric(t("apple_music.kpi_streams", "▶️ Total Streams (Cumul)"), f"{total_plays:,}")
            col3.metric(t("apple_music.kpi_shazams", "⚡ Total Shazams (Cumul)"), f"{total_shazams:,}")

            st.markdown("---")

            # ============================================================
            # 2. TOP CHANSONS (Barres)
            # ============================================================
            st.subheader(t("apple_music.top_header", "🏆 Top Chansons (Cumulé)"))

            # UN TITRE, UNE LIGNE. Sans le relevé le plus récent, le classement
            # listait le même titre une fois par dépôt de CSV, et plaçait son export
            # « depuis le début » au-dessus de l'année d'un autre titre.
            top_query = """
                SELECT DISTINCT ON (song_name) song_name, plays, shazam_count
                FROM apple_songs_performance
                WHERE artist_id = %s
                ORDER BY song_name, snapshot_date DESC, plays DESC
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
                    title=t("apple_music.top10_title", "Top 10 par Streams"),
                    labels={'plays': t("common.streams", "Streams"), 'song_name': ''},
                    color='plays',
                    color_continuous_scale='Reds',
                    custom_data=['shazam_count'],
                )
                fig.update_traces(
                    texttemplate='%{text:,.0f}', textposition='outside',
                    hovertemplate=t("apple_music.top_hover",
                                    '%{y}<br>Streams : %{x:,.0f}<br>⚡ Shazams : %{customdata[0]:,.0f}<extra></extra>'),
                )
                fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=500)
                st.plotly_chart(fig, width="stretch")
                with st.expander(t("apple_music.shazams_expander", "⚡ Shazams par chanson (Top 10)")):
                    _df_sh = df_top[['song_name', 'shazam_count']].rename(
                        columns={'song_name': t("common.song", "Chanson"), 'shazam_count': 'Shazams'})
                    st.dataframe(_df_sh, hide_index=True, width="stretch")

            st.markdown("---")

            # ============================================================
            # 3. GRAPHIQUE DYNAMIQUE (CALCUL DIFFÉRENTIEL)
            # ============================================================
            st.subheader(t("apple_music.daily_growth", "📈 Croissance Quotidienne (Streams & Shazams)"))

            # Pre-select the latest *real* release using the canonical reference
            # (track_release_reference, fed by S4A release dates). Apple's CSV has no
            # release date, so we map each Apple song_name → match_key → release_date
            # and pre-seed the selectbox with the most recently released track. Only
            # on first load — a user's later choice persists via session_state.
            _ent_key = "apple_daily_ent"
            if _ent_key not in st.session_state:
                from src.utils.track_matching import normalize_track_title, get_release_dates
                rel_by_key = get_release_dates(db, artist_id)
                if rel_by_key:
                    songs = db.fetch_query(
                        "SELECT DISTINCT song_name FROM apple_songs_history WHERE artist_id = %s",
                        (artist_id,),
                    )
                    best_song, best_date = None, None
                    for (sn,) in (songs or []):
                        rd = rel_by_key.get(normalize_track_title(sn))
                        if rd and (best_date is None or rd > best_date):
                            best_song, best_date = sn, rd
                    if best_song is not None:
                        st.session_state[_ent_key] = best_song
                        st.caption(t("apple_music.latest_release",
                                     "Dernière sortie détectée : **{song}** ({date}).")
                                   .format(song=best_song, date=best_date))

            # Sélecteur chanson + filtre période (factorisés via entity_period_filter).
            selected_song, window = entity_period_filter(
                db,
                spec=EntitySpec("apple_songs_history", "song_name", "date",
                                multi=False, default_count=1),
                artist_id=artist_id, key_prefix="apple_daily",
                label=t("apple_music.song_select", "🔍 Chanson (dernière release par défaut)"),
            )
            # Normalise scalar → list so the IN (...) fragment below stays valid.
            selected_songs = [selected_song] if selected_song else []

            if selected_songs:
                placeholders = ','.join(['%s'] * len(selected_songs))
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
                    SELECT date, song_name, plays, shazam_count, daily_streams, daily_shazams
                    FROM daily_diff
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

                    # DEUX CADRES PARTAGÉS EN X, pas deux axes superposés.
                    #
                    # Les Shazams se comptent en unités quand les streams se comptent en
                    # centaines : sur un repère commun, la barre est invisible ; sur un
                    # second axe décalé, son croisement avec la courbe est un artefact de
                    # cadrage et non un fait. Les deux cadres gardent la lecture
                    # chronologique et rendent chaque série lisible sur son échelle.
                    from plotly.subplots import make_subplots
                    fig = make_subplots(
                        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=[
                            t("apple_music.streams_per_day", "Streams / jour"),
                            t("apple_music.shazams_per_day", "Shazams / jour")])
                    for song in df_daily['song_name'].unique():
                        d = df_daily[df_daily['song_name'] == song]
                        fig.add_trace(go.Scatter(
                            x=d['date'], y=d['daily_streams'],
                            name=f"🎧 {song}", mode='lines+markers',
                        ), row=1, col=1)
                        fig.add_trace(go.Bar(
                            x=d['date'], y=d['daily_shazams'],
                            name=f"⚡ {song}", opacity=0.6, showlegend=False,
                        ), row=2, col=1)
                    fig.update_layout(
                        title=t("apple_music.daily_chart_title",
                                "Streams & Shazams par jour · {label}").format(label=window.label),
                        hovermode='x unified',
                        barmode='group',
                        height=520,
                        legend=dict(orientation='h'),
                    )
                    st.plotly_chart(fig, width="stretch")

                else:
                    st.info(t("apple_music.not_enough_history",
                              "📉 Pas assez d'historique pour calculer la croissance (besoin de min. 2 jours de données)."))
            else:
                st.info(t("apple_music.select_prompt",
                          "👈 Sélectionnez une chanson — ou importez des CSV Apple Music plusieurs jours de suite."))

        except Exception as e:
            st.error(t("apple_music.error", "❌ Erreur : {err}").format(err=e))


if __name__ == "__main__":
    show()
