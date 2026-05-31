"""Page d'accueil — KPI globaux, fraîcheur des sources, statut des pipelines."""
import html as _html
import streamlit as st
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import project_db
from src.dashboard.auth import get_artist_id
from src.dashboard.utils.airflow_monitor import AirflowMonitor
from src.dashboard.utils.kpi_helpers import (
    get_source_freshness, freshness_status,
    get_total_streams_s4a, get_total_views_youtube,
    get_total_plays_soundcloud, get_total_plays_apple,
    get_instagram_followers,
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
            # HIGH-07: html.escape() on all interpolated values — defence-in-depth
            # against stored XSS if a DB-sourced value ever reaches these variables.
            st.markdown(
                f"""<div style="border:1px solid {_html.escape(color)}; border-radius:8px;
                    padding:8px 6px; background:{_html.escape(color)}18; text-align:center;">
                    <div style="font-size:1.2em;">{_html.escape(str(info['icon']))}</div>
                    <div style="font-weight:600; font-size:0.8em; white-space:nowrap;">{_html.escape(label)}</div>
                    <div style="font-size:0.75em; color:{_html.escape(color)};">{_html.escape(emoji)} {_html.escape(age_label)}</div>
                    <div style="font-size:0.65em; color:#888;">{_html.escape(date_str)}</div>
                </div>""",
                unsafe_allow_html=True
            )


def _section_streams(db, artist_id):
    st.subheader("🎧 Streams totaux")
    s4a = get_total_streams_s4a(db, artist_id)
    yt = get_total_views_youtube(db, artist_id)
    sc = get_total_plays_soundcloud(db, artist_id)
    apple = get_total_plays_apple(db, artist_id)
    ig = get_instagram_followers(db, artist_id)
    ig_count = ig['followers'] if ig else 0
    grand_total = s4a + yt + sc + apple  # Instagram followers ≠ streams, not summed

    st.markdown(
        f"""<div style="text-align:center; padding:16px; background:#f0f2f6;
            border-radius:10px; margin-bottom:16px;">
            <div style="color:#555; font-size:1em; font-weight:600;">🎧 Total streams toutes plateformes</div>
            <div style="font-size:3em; color:#1DB954; font-weight:800;">{grand_total:,}</div>
        </div>""",
        unsafe_allow_html=True
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🎵 Spotify S4A", f"{s4a:,}")
    c2.metric("🎬 YouTube", f"{yt:,}")
    c3.metric("☁️ SoundCloud", f"{sc:,}")
    c4.metric("🍎 Apple Music", f"{apple:,}")
    # Instagram followers — colour-differentiated from stream platforms (rose Instagram)
    c5.markdown(
        f"""<div style="border:1px solid #E4405F; background:#E4405F18;
            border-radius:8px; padding:10px 12px; text-align:center;
            margin-top:4px;">
            <div style="color:#666; font-size:0.85em;">📸 Instagram Followers</div>
            <div style="font-size:1.75em; color:#E4405F; font-weight:700;">{ig_count:,}</div>
        </div>""",
        unsafe_allow_html=True
    )


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
            except ImportError as e:
                st.error(
                    f"WeasyPrint non disponible : {e}. "
                    "Installer : `pip install weasyprint` + libs système "
                    "(libcairo2, libpango-1.0-0, libgdk-pixbuf-2.0-0)."
                )
                return

            with project_db() as db2:
                try:
                    with st.spinner("Génération…"):
                        pdf_bytes = generate_pdf(db2, artist_id, months=12)
                    st.session_state['_home_pdf_bytes'] = pdf_bytes
                except Exception as e:
                    st.error(f"Erreur : {e}")

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
    "meta_ads_api_daily":       ("📊", "Meta Ads"),
    "ml_scoring_daily":         ("🤖", "ML Scoring"),
    "data_quality_check":       ("🔍", "Qualité données"),
}

_STATE_COLOR = {
    "success": ("#00CC96", "🟢"),
    "failed":  ("#EF553B", "🔴"),
    "running": ("#636EFA", "🔵"),
    "queued":  ("#FFA500", "🟡"),
}


def _section_onboarding(db, artist_id: int) -> None:
    """Brick 29 — Onboarding progress tracker for new artists."""
    # Run all four checks in one round-trip using UNION ALL
    rows = db.fetch_query(
        """
        SELECT
            (SELECT COUNT(*) FROM artist_credentials  WHERE artist_id = %s) AS has_creds,
            (SELECT COUNT(*) FROM etl_run_log         WHERE artist_id = %s AND status = 'success') AS has_runs,
            (SELECT COUNT(*) FROM s4a_song_timeline   WHERE artist_id = %s LIMIT 1) AS has_csv,
            (SELECT COUNT(*) FROM apple_songs_performance WHERE artist_id = %s LIMIT 1) AS has_apple
        """,
        (artist_id, artist_id, artist_id, artist_id),
    )
    if not rows:
        return

    has_creds, has_runs, has_csv, has_apple = rows[0]
    steps = [
        (bool(has_creds), "🔑 Configure API credentials", "credentials"),
        (bool(has_csv),   "📂 Upload a Spotify for Artists CSV", "upload_csv"),
        (bool(has_apple), "🍎 Upload an Apple Music CSV", "upload_csv"),
        (bool(has_runs),  "🚀 Run your first data collection", "trigger_algo"),
    ]
    completed = sum(1 for done, *_ in steps if done)
    all_done = completed == len(steps)

    if all_done:
        st.markdown("#### ✅ Getting started — configuration terminée")
        st.success("Toutes les étapes de mise en route sont complètes. 🎉")
    else:
        st.markdown(f"#### 🚀 Getting started — {completed}/{len(steps)} steps completed")
        st.progress(completed / len(steps))

    for done, label, _page in steps:
        icon = "✅" if done else "⬜"
        st.markdown(f"{icon} {label}")

    st.markdown("---")


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
    st.title("🎵 streaMLytics — Music platform dashboard")
    st.markdown("---")

    artist_id = get_artist_id()  # None si admin

    with project_db() as db:
        try:
            # Onboarding tracker — only shown to artists with incomplete setup
            if artist_id is not None:
                _section_onboarding(db, artist_id)

            _section_streams(db, artist_id)
            st.markdown("---")
            _section_pdf_export(artist_id)
            st.markdown("---")
            _section_dag_status()
            st.markdown("---")
            _section_freshness(db, artist_id)
        except Exception as e:
            st.error(f"Erreur d'affichage : {e}")
