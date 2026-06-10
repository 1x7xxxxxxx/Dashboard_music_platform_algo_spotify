"""Usage Analytics — admin view over the first-party usage_events log.

Type: Feature
Uses: usage_events
Depends on: get_db_connection, is_admin
"""
import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.auth import is_admin


def show():
    st.title(t("usage_analytics.title", "📈 Usage Analytics"))
    st.caption(t("usage_analytics.caption",
                 "Suivi first-party de l'usage de l'app (page_view + actions clés). "
                 "Données internes — aucune sortie vers un tiers."))

    if not is_admin():
        st.error(t("usage_analytics.admin_only", "Réservé aux administrateurs."))
        st.stop()

    db = get_db_connection()
    if db is None:
        return
    try:
        days = st.selectbox(t("usage_analytics.window", "Fenêtre"), [7, 30, 90, 365], index=2,
                            format_func=lambda d: t("usage_analytics.window_days",
                                                    "{d} derniers jours").format(d=d))
        since = f"now() - interval '{int(days)} days'"

        totals = db.fetch_query(
            f"SELECT COUNT(*), COUNT(DISTINCT session_id), COUNT(DISTINCT artist_id) "
            f"FROM usage_events WHERE ts >= {since}")
        n_events, n_sessions, n_artists = (totals[0] if totals else (0, 0, 0))
        c1, c2, c3 = st.columns(3)
        c1.metric(t("usage_analytics.kpi_events", "Événements"), f"{int(n_events or 0):,}")
        c2.metric(t("usage_analytics.kpi_sessions", "Sessions"), f"{int(n_sessions or 0):,}")
        c3.metric(t("usage_analytics.kpi_active_artists", "Artistes actifs"), f"{int(n_artists or 0):,}")

        if not n_events:
            st.info(t("usage_analytics.no_events",
                      "Aucun événement sur la fenêtre — clique dans l'app pour en générer."))
            return

        st.markdown("---")
        df_day = db.fetch_df(
            f"SELECT ts::date AS jour, COUNT(*) AS events "
            f"FROM usage_events WHERE ts >= {since} GROUP BY 1 ORDER BY 1")
        if df_day is not None and not df_day.empty:
            st.subheader(t("usage_analytics.events_per_day", "📅 Événements par jour"))
            st.plotly_chart(px.line(df_day, x="jour", y="events", markers=True,
                                    labels={"jour": t("usage_analytics.axis_day", "jour"),
                                            "events": t("usage_analytics.axis_events", "événements")}),
                            width="stretch")

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader(t("usage_analytics.top_pages", "📄 Pages les plus vues"))
            df_pages = db.fetch_df(
                f"SELECT COALESCE(page, '—') AS page, COUNT(*) AS vues "
                f"FROM usage_events WHERE event = 'page_view' AND ts >= {since} "
                f"GROUP BY page ORDER BY vues DESC LIMIT 20")
            if df_pages is not None and not df_pages.empty:
                st.plotly_chart(
                    px.bar(df_pages.sort_values("vues"), x="vues", y="page",
                           orientation="h",
                           labels={"vues": t("usage_analytics.axis_views", "vues"),
                                   "page": t("usage_analytics.axis_page", "page")}),
                    width="stretch")
                st.caption(t("usage_analytics.dead_feature_hint",
                             "Les pages absentes ou en bas de liste = candidates « dead feature »."))
        with col_b:
            st.subheader(t("usage_analytics.event_breakdown", "⚡ Répartition par type d'événement"))
            df_evt = db.fetch_df(
                f"SELECT event, COUNT(*) AS n FROM usage_events WHERE ts >= {since} "
                f"GROUP BY event ORDER BY n DESC")
            if df_evt is not None and not df_evt.empty:
                st.plotly_chart(px.bar(df_evt, x="event", y="n",
                                       labels={"event": t("usage_analytics.axis_event", "événement"),
                                               "n": t("usage_analytics.axis_count", "nombre")}),
                                width="stretch")

        st.markdown("---")
        st.subheader(t("usage_analytics.activity_per_artist", "👤 Activité par artiste"))
        df_artist = db.fetch_df(
            f"SELECT COALESCE(artist_id::text, 'admin/anon') AS artiste, "
            f"COUNT(*) AS events, COUNT(DISTINCT session_id) AS sessions, MAX(ts) AS derniere "
            f"FROM usage_events WHERE ts >= {since} GROUP BY artist_id ORDER BY events DESC")
        if df_artist is not None and not df_artist.empty:
            st.dataframe(df_artist, hide_index=True, width="stretch")
    finally:
        db.close()
