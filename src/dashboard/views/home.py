"""Page d'accueil — KPI globaux, fraîcheur des sources, ROI Breakheaven."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.airflow_monitor import AirflowMonitor
from src.dashboard.utils.kpi_helpers import (
    get_source_freshness, freshness_status,
    get_total_streams_s4a, get_total_views_youtube,
    get_total_plays_soundcloud, get_total_plays_apple,
    get_spotify_popularity, get_instagram_followers, get_soundcloud_likes,
    get_roi_data, get_monthly_roi_series,
    ARTIST_NAME_FILTER,
)


def _freshness_badge(label, icon, last_dt):
    """Génère une carte de fraîcheur HTML."""
    emoji, color, age_label = freshness_status(last_dt)
    date_str = last_dt.strftime("%d/%m %H:%M") if last_dt else "—"
    return f"""
    <div style="border:1px solid {color}; border-radius:8px; padding:8px 12px;
                background:{color}18; text-align:center; min-width:110px;">
        <div style="font-size:1.3em;">{icon}</div>
        <div style="font-weight:600; font-size:0.85em;">{label}</div>
        <div style="font-size:0.75em; color:{color};">{emoji} {age_label}</div>
        <div style="font-size:0.65em; color:#888;">{date_str}</div>
    </div>
    """


def _section_freshness(db, artist_id):
    st.subheader("📡 Fraîcheur des données")
    freshness = get_source_freshness(db, artist_id)
    cols = st.columns(len(freshness))
    for col, (label, info) in zip(cols, freshness.items()):
        emoji, color, age_label = freshness_status(info['last_dt'])
        date_str = info['last_dt'].strftime("%d/%m %H:%M") if info['last_dt'] else "—"
        with col:
            st.markdown(
                f"""<div style="border:1px solid {color}; border-radius:8px;
                    padding:8px 6px; background:{color}18; text-align:center;">
                    <div style="font-size:1.2em;">{info['icon']}</div>
                    <div style="font-weight:600; font-size:0.8em; white-space:nowrap;">{label}</div>
                    <div style="font-size:0.75em; color:{color};">{emoji} {age_label}</div>
                    <div style="font-size:0.65em; color:#888;">{date_str}</div>
                </div>""",
                unsafe_allow_html=True
            )


def _section_streams(db, artist_id):
    st.subheader("🎧 Streams totaux")
    s4a = get_total_streams_s4a(db, artist_id)
    yt = get_total_views_youtube(db, artist_id)
    sc = get_total_plays_soundcloud(db, artist_id)
    apple = get_total_plays_apple(db, artist_id)
    grand_total = s4a + yt + sc + apple

    st.markdown(
        f"""<div style="text-align:center; padding:16px; background:#f0f2f6;
            border-radius:10px; margin-bottom:16px;">
            <div style="color:#555; font-size:1em; font-weight:600;">🎧 Total toutes plateformes</div>
            <div style="font-size:3em; color:#1DB954; font-weight:800;">{grand_total:,}</div>
        </div>""",
        unsafe_allow_html=True
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎵 Spotify S4A", f"{s4a:,}")
    c2.metric("🎬 YouTube", f"{yt:,}")
    c3.metric("☁️ SoundCloud", f"{sc:,}")
    c4.metric("🍎 Apple Music", f"{apple:,}")


def _section_kpi_ml(db, artist_id):
    st.subheader("📊 KPI")
    c1, c2, c3 = st.columns(3)

    # Spotify popularity
    with c1:
        pop = get_spotify_popularity(db, artist_id)
        if pop:
            delta_color = "normal" if pop['score'] >= 50 else "inverse"
            st.metric(
                "🎵 Spotify Popularity",
                f"{pop['score']} / 100",
                help=f"Track : {pop['track']}"
            )
            st.progress(pop['score'] / 100)
        else:
            st.metric("🎵 Spotify Popularity", "—")

    # Instagram followers
    with c2:
        ig = get_instagram_followers(db, artist_id)
        if ig:
            st.metric(
                "📸 Instagram Followers",
                f"{ig['followers']:,}",
                help=f"Collecté le {ig['date']}"
            )
        else:
            st.metric("📸 Instagram Followers", "—")

    # SoundCloud likes
    with c3:
        likes = get_soundcloud_likes(db, artist_id)
        sc_plays = get_total_plays_soundcloud(db, artist_id)
        st.metric("☁️ SoundCloud Plays", f"{sc_plays:,}")
        if likes:
            st.caption(f"❤️ {likes:,} likes")


def _section_spotify_chart(db, artist_id):
    st.subheader("📈 Évolution cumulée (Spotify S4A)")
    try:
        if artist_id is not None:
            query = f"""
                SELECT date, SUM(daily_max) AS value
                FROM (
                    SELECT date, song, MAX(streams) AS daily_max
                    FROM s4a_song_timeline
                    WHERE song NOT ILIKE %s AND artist_id = %s
                    GROUP BY date, song
                ) sub
                GROUP BY date ORDER BY date ASC
            """
            df = db.fetch_df(query, (f"%{ARTIST_NAME_FILTER}%", artist_id))
        else:
            query = f"""
                SELECT date, SUM(daily_max) AS value
                FROM (
                    SELECT date, song, MAX(streams) AS daily_max
                    FROM s4a_song_timeline
                    WHERE song NOT ILIKE %s
                    GROUP BY date, song
                ) sub
                GROUP BY date ORDER BY date ASC
            """
            df = db.fetch_df(query, (f"%{ARTIST_NAME_FILTER}%",))

        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df['value'] = df['value'].cumsum()
            fig = px.area(
                df, x='date', y='value',
                color_discrete_sequence=['#1DB954'],
                labels={'value': 'Streams cumulés', 'date': ''}
            )
            fig.update_layout(yaxis_title="Streams cumulés", hovermode="x unified", showlegend=False)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Pas encore de données Spotify S4A.")
    except Exception as e:
        st.warning(f"Graphique indisponible : {e}")


def _section_roi(db, artist_id):
    st.subheader("💹 ROI Breakheaven")
    st.caption("Revenus iMusician vs dépenses Meta Ads sur la période sélectionnée")

    # Sélecteur de période
    now = datetime.now()
    period_options = {
        "3 derniers mois": 3,
        "6 derniers mois": 6,
        "12 derniers mois": 12,
        "Cette année": None,
    }
    period_label = st.selectbox(
        "Période", list(period_options.keys()), index=1, label_visibility="collapsed"
    )
    n_months = period_options[period_label]
    if n_months is not None:
        from_date = (now - relativedelta(months=n_months)).replace(day=1).date()
    else:
        from_date = date(now.year, 1, 1)
    to_date = now.date()

    roi = get_roi_data(db, artist_id, from_date, to_date)

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Revenus iMusician", f"{roi['revenue_eur']:,.2f} €")
    c2.metric("📱 Dépenses Meta", f"{roi['meta_spend']:,.2f} €")

    if roi['roi_pct'] is not None:
        roi_label = f"{roi['roi_pct']:.1f} %"
        roi_delta = "✅ Rentable" if roi['profitable'] else "⚠️ Déficitaire"
        c3.metric("📊 ROI", roi_label, roi_delta,
                  delta_color="normal" if roi['profitable'] else "inverse")
    else:
        c3.metric("📊 ROI", "—", help="Requires Meta Ads spend data")

    # Graphique mensuel si données
    df_series = get_monthly_roi_series(db, artist_id, from_date, to_date)
    if not df_series.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_series['period_date'], y=df_series['revenue_eur'],
            name="Revenus (€)", marker_color="#1DB954"
        ))
        fig.add_trace(go.Bar(
            x=df_series['period_date'], y=df_series['meta_spend'],
            name="Dépenses Meta (€)", marker_color="#FF4444"
        ))
        fig.update_layout(
            barmode='group',
            xaxis_tickformat='%b %Y',
            yaxis_title="Euros (€)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Aucune donnée de revenus ou dépenses sur cette période.")


def _section_pdf_export(artist_id):
    """Raccourci vers la page Export PDF + génération rapide (toutes sections, 12 mois)."""
    st.subheader("📄 Rapport PDF")
    col_btn, col_full, col_info = st.columns([1, 1, 2])

    with col_info:
        st.caption("Rapport rapide (12 mois, toutes sections). "
                   "Pour personnaliser : **📄 Export PDF** dans le menu.")

    with col_btn:
        if st.button("⚡ Rapport rapide", type="primary"):
            try:
                from src.dashboard.utils.pdf_exporter import generate_pdf
            except ImportError:
                st.error("WeasyPrint non installé : `pip install weasyprint`")
                return

            db2 = get_db_connection()
            if db2 is None:
                return
            try:
                with st.spinner("Génération…"):
                    pdf_bytes = generate_pdf(db2, artist_id, months=12)
                st.session_state['_home_pdf_bytes'] = pdf_bytes
            except Exception as e:
                st.error(f"Erreur : {e}")
            finally:
                db2.close()

    if st.session_state.get('_home_pdf_bytes'):
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        col_full.download_button(
            label="⬇️ Télécharger",
            data=st.session_state['_home_pdf_bytes'],
            file_name=f"rapport_{now_str}.pdf",
            mime="application/pdf",
        )


_DAG_LABELS = {
    "spotify_api_daily":        ("🎵", "Spotify API"),
    "youtube_daily":            ("🎬", "YouTube"),
    "soundcloud_daily":         ("☁️", "SoundCloud"),
    "instagram_daily":          ("📸", "Instagram"),
    "s4a_csv_watcher":          ("📂", "CSV S4A"),
    "apple_music_csv_watcher":  ("🍎", "Apple Music"),
    "meta_csv_watcher_config":  ("📊", "Meta Config"),
    "meta_insights_watcher":    ("📊", "Meta Insights"),
    "ml_scoring_daily":         ("🤖", "ML Scoring"),
    "data_quality_check":       ("🔍", "Qualité données"),
}

_STATE_COLOR = {
    "success": ("#00CC96", "🟢"),
    "failed":  ("#EF553B", "🔴"),
    "running": ("#636EFA", "🔵"),
    "queued":  ("#FFA500", "🟡"),
}


def _section_dag_status():
    """Résumé du dernier run de chaque DAG."""
    st.subheader("🚦 Statut des pipelines")

    monitor = AirflowMonitor()
    try:
        dag_list = monitor.get_dag_list()
    except Exception:
        st.warning("API Airflow inaccessible — démarrer Docker.")
        return

    if not dag_list:
        st.warning("Aucun DAG trouvé. Vérifier que Airflow est lancé.")
        return

    rows = []
    for dag_id in dag_list:
        runs = monitor.get_runs_for_dag(dag_id, limit=1)
        if not runs:
            rows.append((dag_id, None, None, None))
        else:
            r = runs[0]
            rows.append((dag_id, r['state'], r['start_date'], r['end_date']))

    # Grille responsive : 5 colonnes
    n_cols = 5
    cols = st.columns(n_cols)
    for i, (dag_id, state, start, end) in enumerate(rows):
        icon_dag, label = _DAG_LABELS.get(dag_id, ("⚙️", dag_id))
        color, state_icon = _STATE_COLOR.get(state, ("#888888", "⚫"))
        state_label = state or "jamais lancé"
        date_str = start[:16].replace("T", " ") if start else "—"

        with cols[i % n_cols]:
            st.markdown(
                f"""<div style="border:1px solid {color};border-radius:8px;
                    padding:8px 10px;background:{color}18;text-align:center;margin-bottom:8px;">
                    <div style="font-size:1.4em">{icon_dag}</div>
                    <div style="font-weight:600;font-size:0.8em;white-space:nowrap">{label}</div>
                    <div style="font-size:0.85em">{state_icon} {state_label}</div>
                    <div style="font-size:0.65em;color:#888">{date_str}</div>
                </div>""",
                unsafe_allow_html=True,
            )


def show():
    st.title("🎵 Music Platform Dashboard")
    st.markdown("---")

    db = get_db_connection()
    if db is None:
        return

    artist_id = get_artist_id()  # None si admin

    try:
        _section_dag_status()
        st.markdown("---")
        _section_freshness(db, artist_id)
        st.markdown("---")
        _section_streams(db, artist_id)
        st.markdown("---")
        _section_kpi_ml(db, artist_id)
        st.markdown("---")
        _section_roi(db, artist_id)
        st.markdown("---")
        _section_spotify_chart(db, artist_id)

    except Exception as e:
        st.error(f"Erreur d'affichage : {e}")
    finally:
        db.close()

    st.markdown("---")
    _section_pdf_export(artist_id)

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔗 Airflow UI"):
            st.markdown("[Ouvrir](http://localhost:8080)")
    with c2:
        st.code("docker-compose up -d")
