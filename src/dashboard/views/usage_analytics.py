"""Usage Analytics — admin view over the first-party usage_events log.

Type: Feature
Uses: usage_events
Depends on: get_db_connection, is_admin
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import project_db, charts
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

    with project_db() as db:
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
        # R244 (fiches 67-69 « fusionner sur un même graphique admin, deux légendes ») : les
        # évènements par jour, les pages vues et les types d'évènement étaient trois
        # figures. Une seule : chaque jour empile ses pages vues (légende « Pages vues ») et
        # ses autres évènements (légende « Évènements »).
        df = db.fetch_df(
            f"SELECT ts::date AS jour, event, COALESCE(page, '—') AS page, COUNT(*) AS n "
            f"FROM usage_events WHERE ts >= {since} GROUP BY 1, 2, 3 ORDER BY 1")
        if df is not None and not df.empty:
            st.subheader(t("usage_analytics.events_per_day", "📅 Événements par jour"))
            charts.plotly_chart(usage_figure(df), width="stretch")
            st.caption(t("usage_analytics.dead_feature_hint",
                         "Les pages absentes ou en bas de liste = candidates « dead feature »."))

        st.markdown("---")
        st.subheader(t("usage_analytics.activity_per_artist", "👤 Activité par artiste"))
        df_artist = db.fetch_df(
            f"SELECT COALESCE(artist_id::text, 'admin/anon') AS artiste, "
            f"COUNT(*) AS events, COUNT(DISTINCT session_id) AS sessions, MAX(ts) AS derniere "
            f"FROM usage_events WHERE ts >= {since} GROUP BY artist_id ORDER BY events DESC")
        if df_artist is not None and not df_artist.empty:
            st.dataframe(df_artist, hide_index=True, width="stretch")


_TOP_PAGES = 8


def usage_figure(df):
    """One stacked bar per day: page views by page, then the other events by type. Pure.

    Two legend groups (Plotly `legendgrouptitle`), because the owner reads two questions in
    it: which PAGES are seen, and which EVENTS happen. Pages beyond the top eight by views
    are summed as « autres pages » — named, never dropped."""
    import plotly.graph_objects as go
    views = df[df["event"] == "page_view"]
    others = df[df["event"] != "page_view"]
    top = views.groupby("page")["n"].sum().sort_values(ascending=False).head(_TOP_PAGES).index
    views = views.assign(page=views["page"].where(views["page"].isin(top), t(
        "usage_analytics.other_pages", "autres pages")))
    from plotly.colors import sample_colorscale
    fig = go.Figure()
    # One colour FAMILY per legend group — blues for pages, oranges for events: twelve
    # series cannot all get a distinct hue (the default palette repeated « login » and
    # « credentials » in the same red), but the group reads at a glance, the page on hover.
    groups = ((views, "page", "pages", t("usage_analytics.legend_pages", "Pages vues"), "Blues"),
              (others, "event", "events", t("usage_analytics.legend_events", "Évènements"),
               "Oranges"))
    for part, col, group, title, scale in groups:
        names = list(part.groupby(col, sort=False).groups)
        shades = sample_colorscale(scale, [0.4 + 0.55 * i / max(1, len(names) - 1)
                                           for i in range(len(names))])
        for i, name in enumerate(names):
            daily = part[part[col] == name].groupby("jour")["n"].sum()
            fig.add_trace(go.Bar(x=daily.index, y=daily.values, name=str(name),
                                 marker_color=shades[i], legendgroup=group,
                                 legendgrouptitle_text=title if i == 0 else None))
    fig.update_layout(barmode="stack", hovermode="x unified", height=460,
                      yaxis_title=t("usage_analytics.axis_events", "événements"),
                      legend=dict(orientation="v", x=1.02, y=1, groupclick="toggleitem"),
                      margin=dict(t=20))
    return fig
