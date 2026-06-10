"""Data Wrapped — annual Spotify for Artists metrics entry and evolution charts."""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.kpi_helpers import (
    get_instagram_followers,
    get_roi_data,
    get_soundcloud_likes,
    get_source_freshness,
    get_spotify_popularity,
    get_total_plays_apple,
    get_total_plays_soundcloud,
    get_total_streams_s4a,
    get_total_views_youtube,
)

_ARTIST_FILTER = "%1x7xxxxxxx%"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _load_wrapped(db, artist_id):
    if artist_id is None:
        query = """
            SELECT w.*, s.name AS artist_name
            FROM artist_wrapped w
            JOIN saas_artists s ON s.id = w.artist_id
            ORDER BY w.year DESC
        """
        return db.fetch_df(query)
    query = """
        SELECT * FROM artist_wrapped
        WHERE artist_id = %s
        ORDER BY year DESC
    """
    return db.fetch_df(query, (artist_id,))


def _load_row_for_year(db, artist_id, year):
    """Return existing row as dict (keyed by column name), or empty dict if not found."""
    df = db.fetch_df(
        "SELECT * FROM artist_wrapped WHERE artist_id = %s AND year = %s",
        (artist_id, year)
    )
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


def _upsert_wrapped(db, artist_id, year, values: dict):
    db.execute_query(
        """
        INSERT INTO artist_wrapped (
            artist_id, year,
            listeners, streams, hours_listened, countries,
            listener_gain_pct, stream_gain_pct, save_gain_pct, playlist_add_gain_pct,
            saves, playlist_adds,
            top_fans_count, top_fans_rank,
            updated_at
        ) VALUES (
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s,
            NOW()
        )
        ON CONFLICT (artist_id, year) DO UPDATE SET
            listeners           = EXCLUDED.listeners,
            streams             = EXCLUDED.streams,
            hours_listened      = EXCLUDED.hours_listened,
            countries           = EXCLUDED.countries,
            listener_gain_pct       = EXCLUDED.listener_gain_pct,
            stream_gain_pct         = EXCLUDED.stream_gain_pct,
            save_gain_pct           = EXCLUDED.save_gain_pct,
            playlist_add_gain_pct   = EXCLUDED.playlist_add_gain_pct,
            saves               = EXCLUDED.saves,
            playlist_adds       = EXCLUDED.playlist_adds,
            top_fans_count      = EXCLUDED.top_fans_count,
            top_fans_rank       = EXCLUDED.top_fans_rank,
            updated_at          = NOW()
        """,
        (
            artist_id, year,
            values['listeners'], values['streams'], values['hours_listened'],
            values['countries'],
            values['listener_gain_pct'], values['stream_gain_pct'],
            values['save_gain_pct'], values['playlist_add_gain_pct'],
            values['saves'], values['playlist_adds'],
            values['top_fans_count'], values['top_fans_rank'],
        )
    )


def _delete_wrapped(db, artist_id, year):
    db.execute_query(
        "DELETE FROM artist_wrapped WHERE artist_id = %s AND year = %s",
        (artist_id, year)
    )


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _fmt_big(n):
    if n is None:
        return "—"
    n = int(n)
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _fmt_pct(v):
    if v is None:
        return "—"
    return f"{float(v):+.1f}%"


def _line_chart(df, col, title, color="#1DB954", fmt_fn=None):
    df_plot = df[['year', col]].dropna().sort_values('year')
    if df_plot.empty:
        return None
    fig = px.line(
        df_plot, x='year', y=col,
        markers=True,
        title=title,
        color_discrete_sequence=[color],
        labels={'year': '', col: ''},
    )
    fig.update_traces(
        mode='lines+markers',
        line=dict(width=2.5),
        marker=dict(size=8),
    )
    if fmt_fn:
        fig.update_traces(
            text=[fmt_fn(v) for v in df_plot[col]],
            textposition='top center',
            mode='lines+markers+text',
        )
    fig.update_layout(
        xaxis=dict(dtick=1, tickformat='d'),
        yaxis_title='',
        showlegend=False,
        hovermode='x unified',
        margin=dict(t=40, b=20),
        height=260,
    )
    return fig


def _bar_gain_chart(df, col, title, pos_color="#1DB954", neg_color="#e63946",
                    fmt_fn=_fmt_big):
    df_plot = df[['year', col]].dropna().sort_values('year')
    if df_plot.empty:
        return None
    colors = [pos_color if v >= 0 else neg_color for v in df_plot[col]]
    fig = go.Figure(go.Bar(
        x=df_plot['year'],
        y=df_plot[col],
        marker_color=colors,
        text=[fmt_fn(v) for v in df_plot[col]],
        textposition='outside',
    ))
    fig.update_layout(
        title=title,
        xaxis=dict(dtick=1, tickformat='d'),
        yaxis_title='',
        showlegend=False,
        hovermode='x unified',
        margin=dict(t=40, b=20),
        height=260,
    )
    return fig


def _multi_line_chart(df, series, title, log_scale=False):
    """Combine several volume metrics on one chart. series: list of (col, label, color)."""
    df_s = df.sort_values('year')
    fig = go.Figure()
    has_data = False
    for col, label, color in series:
        if col not in df_s.columns:
            continue
        sub = df_s[['year', col]].dropna()
        if sub.empty:
            continue
        has_data = True
        fig.add_trace(go.Scatter(
            x=sub['year'], y=sub[col],
            mode='lines+markers', name=label,
            line=dict(width=2.5, color=color), marker=dict(size=8),
            hovertemplate=f"{label}: %{{y:,.0f}}<extra></extra>",
        ))
    if not has_data:
        return None
    fig.update_layout(
        title=title,
        xaxis=dict(dtick=1, tickformat='d'),
        yaxis=dict(title='', type='log' if log_scale else 'linear'),
        hovermode='x unified',
        margin=dict(t=60, b=20),
        height=400,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
    )
    return fig


# ---------------------------------------------------------------------------
# Recap auto — all-time multi-platform bilan (read-only, reuses kpi_helpers)
# ---------------------------------------------------------------------------

def _recap_spotify(db, aid):
    st.subheader(t("data_wrapped.recap_spotify_header", "🎧 Spotify"))
    total = get_total_streams_s4a(db, aid)
    pop = get_spotify_popularity(db, aid)
    try:
        arow = db.fetch_query(
            "SELECT listeners, followers FROM s4a_audience WHERE artist_id = %s "
            "ORDER BY date DESC LIMIT 1", (aid,))
        followers = int(arow[0][1]) if arow and arow[0][1] is not None else None
    except Exception:
        followers = None
    c1, c2, c3 = st.columns(3)
    c1.metric(t("data_wrapped.recap_total_streams", "Streams totaux (S4A)"),
              _fmt_big(total) if total else "—")
    c2.metric(t("data_wrapped.recap_spotify_popularity", "Popularité Spotify"),
              pop["score"] if pop else "—",
              help=t("data_wrapped.recap_popularity_help", "Titre : {track}").format(
                  track=pop['track']) if pop else None)
    c3.metric(t("data_wrapped.recap_followers", "Followers (dernier relevé)"),
              _fmt_big(followers) if followers is not None else "—")

    st.markdown(t("data_wrapped.recap_top5_header", "#### 🏆 Top 5 titres (streams cumulés)"))
    try:
        df_top = db.fetch_df(
            "SELECT song, SUM(daily_max) AS streams FROM ("
            "  SELECT song, date, MAX(streams) AS daily_max FROM s4a_song_timeline"
            "  WHERE artist_id = %s AND song NOT ILIKE %s GROUP BY song, date) t "
            "GROUP BY song ORDER BY streams DESC LIMIT 5", (aid, _ARTIST_FILTER))
        if df_top is not None and not df_top.empty:
            fig = go.Figure(go.Bar(
                x=df_top["streams"], y=df_top["song"], orientation="h",
                marker_color="#1DB954"))
            fig.update_layout(height=240, margin=dict(t=10, b=10),
                              yaxis=dict(autorange="reversed"),
                              xaxis_title=t("data_wrapped.recap_cumulative_streams",
                                            "Streams cumulés"))
            st.plotly_chart(fig, width="stretch")
        else:
            st.caption(t("data_wrapped.recap_no_s4a_track", "Aucun titre S4A pour cet artiste."))
    except Exception:
        st.caption(t("data_wrapped.recap_top_unavailable", "Top titres indisponible."))


def _recap_platforms(db, aid):
    st.subheader(t("data_wrapped.recap_platforms_header", "📺 Autres plateformes"))
    yt = get_total_views_youtube(db, aid)
    apple = get_total_plays_apple(db, aid)
    sc = get_total_plays_soundcloud(db, aid)
    sc_likes = get_soundcloud_likes(db, aid)
    ig = get_instagram_followers(db, aid)
    p1, p2, p3, p4 = st.columns(4)
    p1.metric(t("data_wrapped.recap_youtube_views", "YouTube — vues"),
              _fmt_big(yt) if yt else "—")
    p2.metric(t("data_wrapped.recap_apple_plays", "Apple Music — plays"),
              _fmt_big(apple) if apple else "—")
    p3.metric(t("data_wrapped.recap_soundcloud_plays", "SoundCloud — plays"),
              _fmt_big(sc) if sc else "—",
              help=t("data_wrapped.recap_soundcloud_likes", "{likes} likes").format(
                  likes=_fmt_big(sc_likes)) if sc_likes else None)
    p4.metric(t("data_wrapped.recap_instagram_followers", "Instagram — followers"),
              _fmt_big(ig["followers"]) if ig else "—")


def _recap_revenue(db, aid):
    st.subheader(t("data_wrapped.recap_revenue_header", "💶 Revenus & publicité (carrière)"))
    roi = get_roi_data(db, aid, date(2000, 1, 1), date.today())
    r1, r2, r3 = st.columns(3)
    r1.metric(t("data_wrapped.recap_imusician_revenue", "Revenu iMusician"),
              f"{roi['revenue_eur']:,.0f} €")
    r2.metric(t("data_wrapped.recap_meta_spend", "Dépense Meta Ads"),
              f"{roi['meta_spend']:,.0f} €")
    roi_pct = roi.get("roi_pct")
    r3.metric(t("data_wrapped.recap_roi", "ROI"),
              f"{roi_pct:.0f} %" if roi_pct is not None else "—",
              delta=t("data_wrapped.recap_profitable", "rentable")
              if roi.get("profitable") else None)


def _recap_ml(db, aid):
    st.subheader(t("data_wrapped.recap_ml_header", "🔮 Highlight ML"))
    try:
        df_ml = db.fetch_df(
            "SELECT song, dw_probability, rr_probability, radio_probability "
            "FROM ml_song_predictions WHERE artist_id = %s AND song NOT ILIKE %s "
            "AND prediction_date = (SELECT MAX(prediction_date) FROM ml_song_predictions "
            "WHERE artist_id = %s)", (aid, _ARTIST_FILTER, aid))
    except Exception:
        df_ml = None
    if df_ml is None or df_ml.empty:
        st.caption(t("data_wrapped.recap_no_ml",
                     "Aucune prédiction ML — lance le DAG `ml_scoring_daily`."))
        return
    cols = ["dw_probability", "rr_probability", "radio_probability"]
    df_ml["best"] = df_ml[cols].max(axis=1)
    top = df_ml.sort_values("best", ascending=False).iloc[0]
    labels = {"dw_probability": "Discover Weekly", "rr_probability": "Release Radar",
              "radio_probability": "Radio"}
    probs = {labels[c]: (top[c] or 0) for c in cols}
    best_algo = max(probs, key=probs.get)
    st.success(t("data_wrapped.recap_ml_best",
                 "🔮 Titre le plus prometteur : **{song}** — {algo} **{pct}%**").format(
                     song=top['song'], algo=best_algo,
                     pct=f"{probs[best_algo] * 100:.0f}"))
    st.caption(t("data_wrapped.recap_ml_caption",
                 "Probabilité absolue de déclenchement (sortie calibrée du modèle). "
                 "Voir « 🚀 Road to Algo (ML) » pour le détail."))


def _recap_freshness(db, aid):
    st.subheader(t("data_wrapped.recap_freshness_header", "🩺 Fraîcheur des données"))
    try:
        fresh = get_source_freshness(db, aid)
    except Exception:
        st.caption(t("data_wrapped.recap_freshness_unavailable", "Fraîcheur indisponible."))
        return
    items = list(fresh.items())
    cols = st.columns(4)
    for i, (label, info) in enumerate(items):
        dt = info.get("last_dt")
        cols[i % 4].caption(
            f"{info.get('icon', '')} {label} : "
            f"{dt.strftime('%Y-%m-%d') if dt else '—'}")


def _show_recap_tab(db, aid):
    st.caption(t(
        "data_wrapped.recap_intro",
        "Bilan **automatique** toutes plateformes (carrière / all-time), calculé "
        "depuis tes données collectées. « — » = source non connectée ou vide."))
    _recap_spotify(db, aid)
    st.markdown("---")
    _recap_platforms(db, aid)
    st.markdown("---")
    _recap_revenue(db, aid)
    st.markdown("---")
    _recap_ml(db, aid)
    st.markdown("---")
    _recap_freshness(db, aid)


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------

def show():
    st.title(t("data_wrapped.title", "🎁 Data Wrapped — Bilan"))
    st.markdown(t(
        "data_wrapped.intro",
        "**Recap auto** toutes plateformes (carrière) + saisie manuelle des métriques "
        "annuelles Spotify for Artists et évolution année par année."
    ))

    tab_recap, tab_form, tab_charts, tab_data = st.tabs([
        t("data_wrapped.tab_recap", "🎁 Recap auto"),
        t("data_wrapped.tab_form", "✏️ Saisie"),
        t("data_wrapped.tab_charts", "📊 Évolution"),
        t("data_wrapped.tab_data", "🗃️ Données"),
    ])

    db = get_db_connection()
    if db is None:
        st.error(t("data_wrapped.db_unreachable", "Base de données inaccessible."))
        return

    try:
        # Resolve artist context — include inactive artists (historical data entry)
        if is_admin():
            artists_df = db.fetch_df(
                "SELECT id, name FROM saas_artists ORDER BY name"
            )
            if artists_df.empty:
                st.warning(t("data_wrapped.no_artist", "Aucun artiste en base."))
                return
            artist_options = {row['name']: row['id'] for _, row in artists_df.iterrows()}
        else:
            aid = get_artist_id()
            name_row = db.fetch_query("SELECT name FROM saas_artists WHERE id = %s", (aid,))
            name = name_row[0][0] if name_row else f"Artiste {aid}"
            artist_options = {name: aid}

        # ── Onglet 0 : Recap auto ───────────────────────────────────────────
        with tab_recap:
            recap_name = st.selectbox(
                t("data_wrapped.artist_label", "Artiste"),
                list(artist_options.keys()), key="recap_artist"
            )
            _show_recap_tab(db, artist_options[recap_name])

        # ── Onglet 1 : Formulaire ───────────────────────────────────────────
        with tab_form:
            st.subheader(t("data_wrapped.form_header", "Ajouter / modifier une année"))

            col_a, col_b = st.columns(2)
            with col_a:
                selected_name = st.selectbox(
                    t("data_wrapped.artist_label", "Artiste"),
                    list(artist_options.keys()), key="form_artist"
                )
                target_artist_id = artist_options[selected_name]
            with col_b:
                year = st.number_input(
                    t("data_wrapped.year_label", "Année"),
                    min_value=2015, max_value=datetime.now().year,
                    value=datetime.now().year - 1, step=1, key="form_year"
                )

            # Pre-fill from DB if row exists
            existing = _load_row_for_year(db, target_artist_id, int(year))
            g = existing.get  # shorthand

            st.markdown("---")
            st.markdown(t("data_wrapped.section_audience", "**Audience**"))
            c1, c2, c3 = st.columns(3)
            with c1:
                listeners = st.number_input(
                    t("data_wrapped.field_listeners", "Listeners"),
                    min_value=0, value=int(g('listeners') or 0), step=1000
                )
            with c2:
                listener_gain_pct = st.number_input(
                    t("data_wrapped.field_listener_gain", "Gain listeners (%)"),
                    value=float(g('listener_gain_pct') or 0.0),
                    step=0.1, format="%.1f",
                    help=t("data_wrapped.gain_help", "Croissance annuelle en %, ex: 45.3")
                )
            with c3:
                countries = st.number_input(
                    t("data_wrapped.field_countries", "Pays"),
                    min_value=0, value=int(g('countries') or 0), step=1
                )

            st.markdown(t("data_wrapped.section_streams", "**Streams**"))
            c4, c5, c6 = st.columns(3)
            with c4:
                streams = st.number_input(
                    t("data_wrapped.field_total_streams", "Streams totaux"),
                    min_value=0, value=int(g('streams') or 0), step=10000
                )
            with c5:
                stream_gain_pct = st.number_input(
                    t("data_wrapped.field_stream_gain", "Gain streams (%)"),
                    value=float(g('stream_gain_pct') or 0.0),
                    step=0.1, format="%.1f",
                    help=t("data_wrapped.gain_help", "Croissance annuelle en %, ex: 45.3")
                )
            with c6:
                hours_listened = st.number_input(
                    t("data_wrapped.field_hours_listened", "Heures d'écoute"),
                    min_value=0.0,
                    value=float(g('hours_listened') or 0.0), step=100.0, format="%.1f"
                )

            st.markdown(t("data_wrapped.section_engagement", "**Engagement**"))
            c7, c8, c9, c10 = st.columns(4)
            with c7:
                saves = st.number_input(
                    t("data_wrapped.field_saves", "Saves"),
                    min_value=0, value=int(g('saves') or 0), step=100
                )
            with c8:
                save_gain_pct = st.number_input(
                    t("data_wrapped.field_save_gain", "Gain saves (%)"),
                    value=float(g('save_gain_pct') or 0.0),
                    step=0.1, format="%.1f",
                    help=t("data_wrapped.gain_help", "Croissance annuelle en %, ex: 45.3")
                )
            with c9:
                playlist_adds = st.number_input(
                    t("data_wrapped.field_playlist_adds", "Playlist adds"),
                    min_value=0, value=int(g('playlist_adds') or 0), step=100
                )
            with c10:
                playlist_add_gain_pct = st.number_input(
                    t("data_wrapped.field_playlist_add_gain", "Gain playlist adds (%)"),
                    value=float(g('playlist_add_gain_pct') or 0.0),
                    step=0.1, format="%.1f",
                    help=t("data_wrapped.gain_help", "Croissance annuelle en %, ex: 45.3")
                )

            st.markdown(t("data_wrapped.section_superfans",
                          "**Super-fans (vous dans leur top artistes)**"))
            ct1, ct2 = st.columns(2)
            with ct1:
                top_fans_count = st.number_input(
                    t("data_wrapped.field_fans_count", "Nombre de fans"),
                    min_value=0,
                    value=int(g('top_fans_count') or 0), step=1,
                    help=t("data_wrapped.fans_count_help",
                           "Fans qui vous avaient en top artiste, ex: 11")
                )
            with ct2:
                top_fans_rank = st.number_input(
                    t("data_wrapped.field_fans_rank", "Rang (vous dans leur top N)"),
                    min_value=1,
                    value=int(g('top_fans_rank') or 5), step=1,
                    help=t("data_wrapped.fans_rank_help", "Ex: 5 = vous étiez dans leur top 5")
                )

            st.markdown("---")
            if st.button(t("data_wrapped.btn_save", "💾 Enregistrer"), type="primary"):
                try:
                    _upsert_wrapped(db, target_artist_id, int(year), {
                        'listeners': listeners, 'streams': streams,
                        'hours_listened': hours_listened, 'countries': countries,
                        'listener_gain_pct': listener_gain_pct,
                        'stream_gain_pct': stream_gain_pct,
                        'save_gain_pct': save_gain_pct,
                        'playlist_add_gain_pct': playlist_add_gain_pct,
                        'saves': saves, 'playlist_adds': playlist_adds,
                        'top_fans_count': top_fans_count,
                        'top_fans_rank': top_fans_rank,
                    })
                    st.success(t("data_wrapped.save_success",
                                 "✅ Données {year} enregistrées.").format(year=int(year)))
                    st.rerun()
                except Exception as e:
                    st.error(t("data_wrapped.error_generic", "Erreur : {err}").format(err=e))

            # Delete expander
            with st.expander(t("data_wrapped.expander_delete", "🗑️ Supprimer une année")):
                del_name = st.selectbox(
                    t("data_wrapped.artist_label", "Artiste"),
                    list(artist_options.keys()), key="del_artist"
                )
                del_artist_id = artist_options[del_name]
                del_year = st.number_input(
                    t("data_wrapped.year_label", "Année"),
                    min_value=2015, max_value=datetime.now().year,
                    value=datetime.now().year - 1, step=1, key="del_year"
                )
                if st.button(t("data_wrapped.btn_delete", "🗑️ Supprimer"), type="secondary"):
                    try:
                        _delete_wrapped(db, del_artist_id, int(del_year))
                        st.success(t("data_wrapped.delete_success",
                                     "Année {year} supprimée.").format(year=int(del_year)))
                        st.rerun()
                    except Exception as e:
                        st.error(t("data_wrapped.error_generic",
                                   "Erreur : {err}").format(err=e))

        # ── Onglet 2 : Évolution ────────────────────────────────────────────
        with tab_charts:
            # Artist selector (separate from form tab)
            chart_name = st.selectbox(
                t("data_wrapped.artist_label", "Artiste"),
                list(artist_options.keys()), key="chart_artist"
            )
            chart_artist_id = artist_options[chart_name]
            df = _load_wrapped(db, chart_artist_id)

            if df.empty:
                st.info(t("data_wrapped.charts_no_data",
                          "Aucune donnée. Renseignez au moins deux années via l'onglet Saisie."))
            else:
                # KPI row — latest year
                latest = df.iloc[0]
                k1, k2, k3, k4 = st.columns(4)
                k1.metric(t("data_wrapped.field_listeners", "Listeners"),
                          _fmt_big(latest.get('listeners')),
                          delta=_fmt_pct(latest.get('listener_gain_pct')))
                k2.metric(t("data_wrapped.col_streams", "Streams"),
                          _fmt_big(latest.get('streams')),
                          delta=_fmt_pct(latest.get('stream_gain_pct')))
                k3.metric(t("data_wrapped.field_saves", "Saves"),
                          _fmt_big(latest.get('saves')),
                          delta=_fmt_pct(latest.get('save_gain_pct')))
                k4.metric(t("data_wrapped.kpi_countries", "Pays"),
                          _fmt_big(latest.get('countries')))

                st.markdown("---")

                # Combined evolution — listeners / streams / saves / playlist adds
                st.markdown(t("data_wrapped.combined_header", "#### Évolution combinée"))
                log_scale = st.toggle(
                    t("data_wrapped.log_scale", "Échelle logarithmique"),
                    value=False, key="wrapped_log_scale",
                    help=t("data_wrapped.log_scale_help",
                           "Recommandé si les volumes diffèrent fortement "
                           "(ex: streams ≫ saves), pour voir toutes les courbes."),
                )
                fig = _multi_line_chart(
                    df,
                    [
                        ('listeners', 'Listeners', '#1DB954'),
                        ('streams', 'Streams', '#457b9d'),
                        ('saves', 'Saves', '#e9c46a'),
                        ('playlist_adds', 'Playlist adds', '#f4a261'),
                    ],
                    t("data_wrapped.chart_combined_title",
                      "Listeners · Streams · Saves · Playlist adds"),
                    log_scale=log_scale,
                )
                if fig:
                    st.plotly_chart(fig, width="stretch")

                # Secondary volumes — countries & hours
                st.markdown(t("data_wrapped.countries_listening_header", "#### Pays & écoute"))
                col_c, col_h = st.columns(2)
                with col_c:
                    fig = _line_chart(df, 'countries',
                                      t("data_wrapped.chart_countries_reached", "Pays touchés"),
                                      color="#457b9d", fmt_fn=_fmt_big)
                    if fig:
                        st.plotly_chart(fig, width="stretch")
                with col_h:
                    fig = _line_chart(df, 'hours_listened',
                                      t("data_wrapped.chart_hours_listened", "Heures d'écoute"),
                                      color="#e9c46a", fmt_fn=_fmt_big)
                    if fig:
                        st.plotly_chart(fig, width="stretch")

                # Annual gains (%)
                st.markdown(t("data_wrapped.annual_gains_header", "#### Gains annuels (%)"))
                col_lg, col_stg = st.columns(2)
                with col_lg:
                    fig = _bar_gain_chart(df, 'listener_gain_pct',
                                          t("data_wrapped.chart_listener_gain",
                                            "Gain listeners / an (%)"), fmt_fn=_fmt_pct)
                    if fig:
                        st.plotly_chart(fig, width="stretch")
                with col_stg:
                    fig = _bar_gain_chart(df, 'stream_gain_pct',
                                          t("data_wrapped.chart_stream_gain",
                                            "Gain streams / an (%)"), fmt_fn=_fmt_pct)
                    if fig:
                        st.plotly_chart(fig, width="stretch")

                col_sg, col_pg = st.columns(2)
                with col_sg:
                    fig = _bar_gain_chart(df, 'save_gain_pct',
                                          t("data_wrapped.chart_save_gain",
                                            "Gain saves / an (%)"), fmt_fn=_fmt_pct)
                    if fig:
                        st.plotly_chart(fig, width="stretch")
                with col_pg:
                    fig = _bar_gain_chart(df, 'playlist_add_gain_pct',
                                          t("data_wrapped.chart_playlist_gain",
                                            "Gain playlist adds / an (%)"), fmt_fn=_fmt_pct)
                    if fig:
                        st.plotly_chart(fig, width="stretch")

                # Super-fans — fans who ranked the artist in their top N
                top_rows = df[df['top_fans_count'].notna()][
                    ['year', 'top_fans_count', 'top_fans_rank']
                ].sort_values('year')
                if not top_rows.empty:
                    st.markdown(t("data_wrapped.superfans_header",
                                  "#### Super-fans (vous dans leur top artistes)"))
                    fig = _line_chart(df, 'top_fans_count',
                                      t("data_wrapped.chart_superfans",
                                        "Fans vous ayant en top artiste"),
                                      color="#9d4edd", fmt_fn=_fmt_big)
                    if fig:
                        st.plotly_chart(fig, width="stretch")
                    st.dataframe(
                        top_rows.rename(columns={
                            'year': t("data_wrapped.col_year", "Année"),
                            'top_fans_count': t("data_wrapped.col_fans_count", "Nb fans"),
                            'top_fans_rank': t("data_wrapped.col_fans_rank", "Rang (top N)"),
                        }),
                        hide_index=True,
                        width="stretch",
                    )

        # ── Onglet 3 : Données brutes ────────────────────────────────────────
        with tab_data:
            data_name = st.selectbox(
                t("data_wrapped.artist_label", "Artiste"),
                list(artist_options.keys()), key="data_artist"
            )
            data_artist_id = artist_options[data_name]
            df_raw = _load_wrapped(db, data_artist_id)

            if df_raw.empty:
                st.info(t("data_wrapped.data_no_data", "Aucune donnée enregistrée."))
            else:
                display_cols = [
                    'year', 'listeners', 'listener_gain_pct', 'streams', 'stream_gain_pct',
                    'hours_listened', 'countries', 'saves', 'save_gain_pct',
                    'playlist_adds', 'playlist_add_gain_pct',
                    'top_fans_count', 'top_fans_rank',
                ]
                rename_map = {
                    'year': t("data_wrapped.col_year", "Année"),
                    'listeners': t("data_wrapped.col_listeners", "Listeners"),
                    'listener_gain_pct': t("data_wrapped.col_listener_gain", "△ Listeners %"),
                    'streams': t("data_wrapped.col_streams", "Streams"),
                    'stream_gain_pct': t("data_wrapped.col_stream_gain", "△ Streams %"),
                    'hours_listened': t("data_wrapped.col_hours", "Heures écoute"),
                    'countries': t("data_wrapped.col_countries", "Pays"),
                    'saves': t("data_wrapped.col_saves", "Saves"),
                    'save_gain_pct': t("data_wrapped.col_save_gain", "△ Saves %"),
                    'playlist_adds': t("data_wrapped.col_playlist_adds", "Playlist adds"),
                    'playlist_add_gain_pct': t("data_wrapped.col_playlist_gain", "△ PL adds %"),
                    'top_fans_count': t("data_wrapped.col_superfans", "Super-fans"),
                    'top_fans_rank': t("data_wrapped.col_fans_rank", "Rang (top N)"),
                }
                existing_cols = [c for c in display_cols if c in df_raw.columns]
                st.dataframe(
                    df_raw[existing_cols].rename(columns=rename_map),
                    hide_index=True,
                    width="stretch",
                )

    finally:
        db.close()
