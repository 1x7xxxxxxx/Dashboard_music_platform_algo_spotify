"""Page Spotify & S4A - Vue consolidée et nettoyée."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.utils.period_filter import smart_period_filter
from src.dashboard.auth import artist_id_sql_filter, get_artist_id

# ⚠️ IMPORTANT : Le nom exact tel qu'il apparaît dans tes CSV pour la ligne "Total"
ARTIST_NAME_FILTER = "1x7xxxxxxx"

def show():
    """Affiche la page Spotify & S4A combinée."""
    st.title(t("spotify_s4a_combined.title", "🎵 Spotify & S4A"))
    st.markdown(t("spotify_s4a_combined.subtitle",
                  "### Analyse des performances (Source : Timeline CSV)"))
    st.markdown("---")

    db = get_db_connection()
    artist_frag, artist_params = artist_id_sql_filter()

    # `tracks` is keyed by the SaaS integer `saas_artist_id` (migration 039), a
    # different column than the generic `artist_id` filter above. Admin (None) =
    # no filter (sees all tenants).
    _aid = get_artist_id()
    _track_frag = "AND saas_artist_id = %s" if _aid is not None else ""
    _track_join_frag = "AND tk.saas_artist_id = %s" if _aid is not None else ""
    _track_params = (_aid,) if _aid is not None else ()

    # ============================================================================
    # 1. RÉCUPÉRATION DES DONNÉES GLOBALES (DÉDUPLIQUÉES)
    # ============================================================================

    # A. Date de mise à jour
    update_query = f"SELECT MAX(collected_at) FROM s4a_song_timeline WHERE 1=1 {artist_frag}"
    last_update_res = db.fetch_query(update_query, artist_params)
    last_update = last_update_res[0][0] if last_update_res and last_update_res[0][0] else None

    # B. KPIs (Dédupliqués)
    # On calcule la somme des streams en ne prenant que la ligne la plus récente pour chaque jour/chanson
    kpi_query = f"""
        SELECT
            COUNT(DISTINCT song),
            SUM(streams)
        FROM (
            SELECT DISTINCT ON (date, song) song, streams
            FROM s4a_song_timeline
            WHERE song NOT ILIKE %s
            {artist_frag}
            ORDER BY date, song, collected_at DESC
        ) sub
    """
    stats_res = db.fetch_query(kpi_query, (f"%{ARTIST_NAME_FILTER}%", *artist_params))
    songs_count = stats_res[0][0] or 0
    total_streams_individual = stats_res[0][1] or 0

    # ============================================================================
    # 2. AFFICHAGE DES MÉTRIQUES (3 COLONNES)
    # ============================================================================
    st.header(t("spotify_s4a_combined.metrics_header", "🎯 Métriques Globales"))
    col1, col2, col3 = st.columns(3)

    col1.metric(t("spotify_s4a_combined.kpi_active_songs", "🎵 Chansons Actives"), f"{songs_count}")
    col2.metric(t("spotify_s4a_combined.kpi_total_streams", "🎧 Cumul Streams (Titres)"), f"{total_streams_individual:,}")

    # C. Affichage intelligent de la date
    if last_update:
        time_diff = datetime.now() - last_update
        hours_ago = int(time_diff.total_seconds() / 3600)

        # Calcul du petit texte "delta" (ex: -2h)
        if hours_ago < 1:
            delta_str = t("spotify_s4a_combined.just_now", "À l'instant")
            delta_color = "normal"
        elif hours_ago < 24:
            delta_str = t("spotify_s4a_combined.hours_ago", "Il y a {h}h").format(h=hours_ago)
            delta_color = "off"
        else:
            days = int(hours_ago / 24)
            delta_str = t("spotify_s4a_combined.days_ago", "Il y a {d}j").format(d=days)
            delta_color = "off"

        col3.metric(
            t("spotify_s4a_combined.kpi_last_update", "🕐 Dernière MàJ"),
            last_update.strftime('%d/%m %H:%M'),
            delta=delta_str,
            delta_color=delta_color
        )
    else:
        col3.metric(t("spotify_s4a_combined.kpi_last_update", "🕐 Dernière MàJ"),
                    t("spotify_s4a_combined.no_data_value", "Aucune donnée"))

    st.markdown("---")

    # ============================================================================
    # 3. TOP CHANSONS (Dédupliqué)
    # ============================================================================
    st.header(t("spotify_s4a_combined.top_header", "🏆 Top Chansons"))

    df_top = db.fetch_df(f"""
        SELECT
            song,
            SUM(streams) as total_streams
        FROM (
            SELECT DISTINCT ON (date, song) song, streams
            FROM s4a_song_timeline
            WHERE song NOT ILIKE %s
            {artist_frag}
            ORDER BY date, song, collected_at DESC
        ) sub
        GROUP BY song
        ORDER BY total_streams DESC
        LIMIT 10
    """, (f"%{ARTIST_NAME_FILTER}%", *artist_params))

    if not df_top.empty:
        fig_top = px.bar(
            df_top,
            x='total_streams',
            y='song',
            orientation='h',
            text='total_streams',
            labels={'total_streams': t("common.streams", "Streams"), 'song': ''},
            color='total_streams',
            color_continuous_scale='viridis'
        )
        fig_top.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
        fig_top.update_layout(
            height=500,
            showlegend=False,
            xaxis_title=t("spotify_s4a_combined.axis_total_streams", "Total Streams"),
            yaxis={'categoryorder':'total ascending'}
        )
        st.plotly_chart(fig_top, width="stretch")
    else:
        st.info(t("spotify_s4a_combined.no_data", "Pas de données disponibles."))

    st.markdown("---")

    # ============================================================================
    # 4. ÉVOLUTION DE L'AUDIENCE GLOBALE (Dédupliqué)
    # ============================================================================
    st.header(t("spotify_s4a_combined.audience_header", "📈 Évolution de l'Audience Globale"))
    st.caption(t("spotify_s4a_combined.audience_caption",
                 "Calculé : Somme des streams dédupliqués jour par jour"))

    col1, col2 = st.columns(2)
    today = datetime.now().date()
    try:
        _rd_rows = db.fetch_query(
            f"SELECT MAX(release_date) FROM tracks WHERE 1=1 {_track_frag}", _track_params
        )
        _latest_release = _rd_rows[0][0] if _rd_rows and _rd_rows[0][0] else (today - timedelta(days=365))
    except Exception:
        _latest_release = today - timedelta(days=365)
    start_date_aud = col1.date_input(t("spotify_s4a_combined.start", "Début"), value=_latest_release, key="date_aud_start")
    end_date_aud = col2.date_input(t("spotify_s4a_combined.end", "Fin"), value=today, key="date_aud_end")

    audience_query = f"""
        SELECT date, SUM(streams) as daily_streams
        FROM (
            SELECT DISTINCT ON (date, song) date, streams
            FROM s4a_song_timeline
            WHERE song NOT ILIKE %s
            {artist_frag}
              AND date >= %s
              AND date <= %s
            ORDER BY date, song, collected_at DESC
        ) sub
        GROUP BY date
        ORDER BY date
    """
    df_audience = db.fetch_df(audience_query, (f"%{ARTIST_NAME_FILTER}%", *artist_params, start_date_aud, end_date_aud))

    if not df_audience.empty:
        fig_aud = go.Figure()

        fig_aud.add_trace(go.Scatter(
            x=df_audience['date'],
            y=df_audience['daily_streams'],
            name=t("spotify_s4a_combined.total_streams_trace", "Streams Totaux"),
            mode='lines',
            fill='tozeroy',
            line=dict(color='#1DB954', width=3)
        ))

        fig_aud.update_layout(
            height=400,
            hovermode='x unified',
            yaxis_title=t("spotify_s4a_combined.streams_per_day", "Streams / Jour")
        )
        st.plotly_chart(fig_aud, width="stretch")
    else:
        st.info(t("spotify_s4a_combined.no_data_period", "Pas de données pour cette période."))

    # ============================================================================
    # 4b. ÉVOLUTION CUMULÉE (Spotify S4A)
    # ============================================================================
    st.markdown("---")
    st.header(t("spotify_s4a_combined.cumulative_header", "📈 Évolution cumulée (Spotify S4A)"))
    try:
        cum_query = f"""
            SELECT date, SUM(daily_max) AS value
            FROM (
                SELECT date, song, MAX(streams) AS daily_max
                FROM s4a_song_timeline
                WHERE song NOT ILIKE %s
                {artist_frag}
                GROUP BY date, song
            ) sub
            GROUP BY date ORDER BY date ASC
        """
        df_cum = db.fetch_df(cum_query, (f"%{ARTIST_NAME_FILTER}%", *artist_params))
        if not df_cum.empty:
            df_cum['date'] = pd.to_datetime(df_cum['date'])
            df_cum['value'] = df_cum['value'].cumsum()
            # Downsample very long series before plotting (cumulative is monotonic,
            # so every-Nth-point preserves the shape). Always keep the last point
            # so the final cumulative total is never understated.
            if len(df_cum) > 500:
                step = len(df_cum) // 500
                df_cum = pd.concat(
                    [df_cum.iloc[::step], df_cum.iloc[[-1]]]
                ).drop_duplicates(subset='date')
            fig_cum = px.area(
                df_cum, x='date', y='value',
                color_discrete_sequence=['#1DB954'],
                labels={'value': t("spotify_s4a_combined.cumulative_streams", "Streams cumulés"), 'date': ''}
            )
            fig_cum.update_layout(
                yaxis_title=t("spotify_s4a_combined.cumulative_streams", "Streams cumulés"),
                hovermode="x unified",
                showlegend=False
            )
            st.plotly_chart(fig_cum, width="stretch")
        else:
            st.info(t("spotify_s4a_combined.no_data_yet", "Pas encore de données Spotify S4A."))
    except Exception as e:
        st.warning(t("spotify_s4a_combined.chart_unavailable", "Graphique indisponible : {err}").format(err=e))

    # ============================================================================
    # 5. DÉTAIL PAR CHANSON
    # ============================================================================
    st.markdown("---")
    st.header(t("spotify_s4a_combined.detail_header", "🎸 Détail par Chanson"))

    songs_list = db.fetch_df(f"""
        SELECT t.song
        FROM (
            SELECT song FROM s4a_song_timeline
            WHERE song NOT ILIKE %s {artist_frag}
            GROUP BY song
        ) t
        LEFT JOIN tracks tk ON REPLACE(tk.track_name, '?', '_') = t.song {_track_join_frag}
        ORDER BY tk.release_date DESC NULLS LAST, t.song
    """, (f"%{ARTIST_NAME_FILTER}%", *artist_params, *_track_params))

    if not songs_list.empty:
        col1, col2 = st.columns([2, 3])

        with col1:
            selected_song = st.selectbox(t("spotify_s4a_combined.select_song", "Sélectionner une chanson"), songs_list['song'])

        try:
            _sr = db.fetch_query(
                f"SELECT release_date FROM tracks WHERE REPLACE(track_name, '?', '_') = %s {_track_frag} LIMIT 1",
                (selected_song, *_track_params)
            )
            song_release_date = _sr[0][0] if _sr and _sr[0][0] else (today - timedelta(days=365))
        except Exception:
            song_release_date = today - timedelta(days=365)

        with col2:
            window = smart_period_filter(
                db, table="s4a_song_timeline", date_column="date",
                artist_id=get_artist_id(), key=f"s4a_song_{selected_song}",
                latest_release=song_release_date, default_override="last_release",
            )
        frag, frag_params = window.sql_between("date")

        # Même logique de déduplication ici aussi pour être cohérent
        df_song = db.fetch_df(f"""
            SELECT DISTINCT ON (date) date, streams
            FROM s4a_song_timeline
            WHERE song = %s
            {artist_frag}
            {frag}
            ORDER BY date, collected_at DESC
        """, (selected_song, *artist_params, *frag_params))

        if not df_song.empty:
            fig_song = px.line(
                df_song,
                x='date',
                y='streams',
                title=t("spotify_s4a_combined.song_evolution", "Évolution Streams : {song}").format(song=selected_song),
                markers=False
            )
            fig_song.update_traces(line_color='#1DB954', line_width=2)
            st.plotly_chart(fig_song, width="stretch")
        else:
            st.info(t("spotify_s4a_combined.no_data_period", "Pas de données pour cette période."))

    db.close()

if __name__ == "__main__":
    show()
