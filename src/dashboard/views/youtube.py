"""YouTube — la chaîne, et ce que YouTube accepte de nous dire d'elle.

Type: Feature
Uses: view_session, smart_period_filter, platform_timeseries, i18n
Depends on: youtube_channel_history, youtube_videos, youtube_video_stats
Persists in: — (lecture seule)

LES ABONNÉS SONT ARRONDIS À LA SOURCE, et ce n'est pas un défaut d'ici
----------------------------------------------------------------------
Rapporté le 2026-09-21 : « il n'y a pas moyen de retrouver une meilleure
granularité pour les abonnés car ça passe de 10,6k à 10,7k ». C'est exact, et la
cause est chez YouTube.

`youtube_collector` interroge la **Data API v3** avec une CLÉ D'API
(`developerKey=`), et `channels.list(part='statistics')` y rend un
`subscriberCount` **arrondi à trois chiffres significatifs** pour toute lecture
publique. Mesuré en base sur ce locataire :

    34 jours de relevés · **2 valeurs distinctes** : 10 600 et 10 700

Il n'y a rien à corriger dans cette page : la marche de 100 EST la donnée. Ce que
la page peut faire — et fait maintenant — c'est cesser de la dessiner comme une
courbe continue et le DIRE.

Le chemin vers l'exact existe, et il est nommé plutôt que supposé : la **YouTube
Analytics API** (`youtubeAnalytics.reports.query`, métriques `subscribersGained`
et `subscribersLost`) rend le quotidien exact — mais elle exige un OAuth de
PROPRIÉTAIRE de chaîne, pas une clé d'API. C'est une brique de credentials, du
même genre que le jeton de rafraîchissement SoundCloud.

LES VUES, ELLES, ONT DÉJÀ LEUR GRANULARITÉ FINE
-------------------------------------------------
Et c'est la moitié contre-intuitive de la réponse. Deux compteurs coexistent :

    youtube_channel_history.view_count   2 valeurs distinctes sur 34 jours
    somme de youtube_video_stats         99 770 → 99 775 → 99 777 → 99 778 → …

Le second bouge à l'unité, jour après jour. C'est lui que trace la courbe (via
`platform_timeseries.youtube_cumulative_views`) et lui qui porte les totaux du
produit. Le compteur de chaîne, lui, inclut des vidéos absentes du catalogue et
avance par paliers.
"""
from datetime import date

import isodate
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils import view_session, charts
from src.dashboard.utils.formats import num
from src.dashboard.utils.i18n import t
from src.dashboard.utils.labels import unique_short_labels
from src.dashboard.utils.filters import (
    latest_release_date,
    smart_period_filter,
)
from src.dashboard.utils import platform_timeseries as pts
from src.dashboard.utils.platform_colors import PALETTE_LIGHT

# La couleur MESURÉE de YouTube — pas `#FF0000`, que le balayage du 2026-09-08 a
# refusé (ΔE 4,6 contre SoundCloud en deutéranopie avec les teintes de marque).
_YT = PALETTE_LIGHT["youtube"]

def parse_duration(duration_str):
    """Convertit 'PT1M30S' en secondes."""
    try:
        if not duration_str: return 0
        td = isodate.parse_duration(duration_str)
        return td.total_seconds()
    except Exception:
        return 0

def _labels(titles, n: int = 40) -> list[str]:
    """« 1. Title », ranked in order. `unique_short_labels` cuts a series that differs
    only at its end (« DJ Set … Detroit 17 », « … 16 ») in the middle, keeping it apart."""
    return [f"{i}. {x}" for i, x in enumerate(unique_short_labels(list(titles), n), 1)]


def views_gained(readings: pd.DataFrame) -> pd.DataFrame:
    """(title, gained) — last minus first reading of each video in the window. Pure (R384).

    YouTube publishes COUNTERS: a video's views over a period are a DIFFERENCE of two
    readings, never a sum of them (`cumulative-counter-drawn-as-its-own-history`). A
    video read once in the window gained nothing measurable and is left out."""
    cols = ["title", "gained"]
    if readings.empty:
        return pd.DataFrame(columns=cols)
    r = readings.sort_values(["video_id", "collected_at"])
    g = r.groupby("video_id", sort=False)
    out = pd.DataFrame({"title": g["title"].last(),
                        "gained": g["view_count"].last() - g["view_count"].first(),
                        "n": g.size()})
    out = out[(out["n"] > 1) & (out["gained"] > 0)]
    return out.sort_values("gained", ascending=False)[cols].reset_index(drop=True)


_REDS = [[0.0, "#FFCDD2"], [1.0, "#B71C1C"]]
_SECOND = "#455A64"   # blue-grey — the second series beside YouTube's red (W8 « tout rouge = moche »)


def channel_figure(df_hist: pd.DataFrame, views_series: list) -> go.Figure:
    """Subscribers (top, step) and cumulative views (bottom), two panels on one time axis
    (R485, W8 « deux axes superposés, couleurs différentes »).

    Stacked, not overlaid on a twin y axis: two units on one frame make their crossing
    look meaningful (ceiling `test_no_new_secondary_axis`). Each panel's axis is titled
    in its series' colour."""
    from plotly.subplots import make_subplots

    subs = t("youtube.subscribers", "Abonnés")
    views = t("youtube.cumulative_views", "Vues cumulées")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06)
    fig.add_trace(go.Scatter(x=df_hist["date"], y=df_hist["subs"], name=subs,
                             mode="lines+markers", line_shape="hv",
                             line=dict(color=_YT, width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=[d for d, _ in views_series], y=[v for _, v in views_series],
                             name=views, mode="lines",
                             line=dict(color=_SECOND, width=2)), row=2, col=1)
    lo, hi = float(df_hist["subs"].min()), float(df_hist["subs"].max())
    pad = max((hi - lo) * 0.10, 1) if hi > lo else None
    fig.update_yaxes(title=dict(text=subs, font=dict(color=_YT)), tickformat="~s",
                     tickfont=dict(color=_YT), row=1, col=1,
                     range=[lo - pad, hi + pad] if pad else None)
    fig.update_yaxes(title=dict(text=views, font=dict(color=_SECOND)), tickformat="~s",
                     tickfont=dict(color=_SECOND), row=2, col=1)
    fig.update_layout(title=t("youtube.channel_chart_title", "Abonnés et vues cumulées"),
                      hovermode="x unified", height=460, showlegend=False,
                      margin=dict(t=60, b=40))
    return fig


def views_gained_figure(gained: pd.DataFrame, top: int = 10) -> go.Figure:
    """The videos that gained the most views over the period — a red that deepens with the gain."""
    d = gained.head(top).iloc[::-1]
    labels = _labels(gained.head(top)["title"])[::-1]
    fig = go.Figure(go.Bar(x=d["gained"], y=labels, orientation="h",
                           marker=dict(color=d["gained"], colorscale=_REDS),
                           text=[num(int(v), 0) for v in d["gained"]],
                           textposition="outside", cliponaxis=False))
    fig.update_layout(title=t("youtube.gained_title",
                              "Vues gagnées sur la période, par vidéo"),
                      height=120 + 28 * len(d), showlegend=False,
                      margin=dict(l=10, r=40, t=50, b=30))
    fig.update_yaxes(automargin=True)
    return fig


def top_figure(videos: pd.DataFrame, top: int = 10, title: str = "") -> go.Figure:
    """Views and likes of the most-viewed videos, side by side on the same rows (R485, W8).

    « On ne voit pas d'un coup d'œil quelle vidéo marche » : the first panel answers by
    length, the second says whether people liked it. Likes per 1 000 views ride in the
    hover. Comments are not drawn: 63 over 67 videos, a panel of zeros."""
    from plotly.subplots import make_subplots

    d = videos.sort_values("view_count", ascending=False, kind="stable").head(top)
    labels = _labels(d["title"])[::-1]
    d = d.iloc[::-1]
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, column_widths=[0.6, 0.4],
                        horizontal_spacing=0.05,
                        subplot_titles=(t("youtube.views", "Vues"),
                                        t("youtube.likes", "Likes")))
    per_k = [f"{1000 * lk / v:.1f}" if v else "—"
             for lk, v in zip(d["like_count"].fillna(0), d["view_count"])]
    fig.add_trace(go.Bar(x=d["view_count"], y=labels, orientation="h",
                         marker=dict(color=d["view_count"], colorscale=_REDS),
                         text=[num(int(v), 0) for v in d["view_count"]],
                         textposition="outside", cliponaxis=False,
                         hovertemplate="%{y}<br>%{x:,.0f}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Bar(x=d["like_count"].fillna(0), y=labels, orientation="h",
                         marker_color=_SECOND, customdata=per_k,
                         text=[num(int(v), 0) for v in d["like_count"].fillna(0)],
                         textposition="outside", cliponaxis=False,
                         hovertemplate=t("youtube.likes_hover",
                                         "%{y}<br>%{x:,.0f} likes · %{customdata} pour "
                                         "1 000 vues") + "<extra></extra>"), row=1, col=2)
    fig.update_layout(title=title,
                      height=140 + 30 * len(d), showlegend=False,
                      margin=dict(l=10, r=40, t=80, b=30))
    fig.update_yaxes(automargin=True)
    return fig


def pareto_share(views: pd.Series) -> list[float]:
    """Cumulative share (%) of views, biggest first — the Pareto line. Pure."""
    v = views.sort_values(ascending=False, kind="stable").fillna(0)
    total = float(v.sum())
    return [100.0 * c / total for c in v.cumsum()] if total > 0 else [0.0] * len(v)


def pareto_figure(videos: pd.DataFrame, title: str, top: int = 10) -> go.Figure:
    """One content type's views, biggest first, and the cumulative share in a panel of
    its own on the same rows — a line drawn over the bars hid their value labels."""
    from plotly.subplots import make_subplots

    d = videos.sort_values("view_count", ascending=False, kind="stable").head(top)
    share = pareto_share(videos["view_count"])[:len(d)]
    labels = _labels(d["title"], 28)
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, column_widths=[0.7, 0.3],
                        horizontal_spacing=0.08)
    fig.add_trace(go.Bar(x=d["view_count"], y=labels, orientation="h",
                         marker=dict(color=d["view_count"], colorscale=_REDS),
                         text=[num(int(v), 0) for v in d["view_count"]],
                         textposition="outside", cliponaxis=False,
                         hovertemplate="%{y}<br>%{x:,.0f}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=share, y=labels, mode="lines+markers",
                             line=dict(color=_SECOND, width=2),
                             hovertemplate="%{x:.0f} %<extra></extra>"), row=1, col=2)
    fig.update_layout(title=title, height=140 + 30 * len(d), showlegend=False,
                      margin=dict(l=10, r=20, t=60, b=30))
    fig.update_yaxes(autorange="reversed", automargin=True)
    top_views = float(d["view_count"].max() or 1)
    fig.update_xaxes(tickformat="~s", range=[0, top_views * 1.3], row=1, col=1)
    fig.update_xaxes(range=[0, 105], tickvals=[50, 100], ticktext=["50 %", "100 %"],
                     tickfont=dict(color=_SECOND), row=1, col=2)
    return fig


def pace(videos: pd.DataFrame, readings: pd.DataFrame, days: int = 30,
         today: date | None = None) -> pd.DataFrame:
    """(title, lifetime, recent) views per day, by video. Pure (R485, W8).

    `lifetime` = views to date / days since publication ; `recent` = the counter's rise
    between the first and last reading of the window / the days between them. A video
    whose recent pace beats its lifetime pace is picking up — the one to promote.

    The window is the last `days` days BEFORE THE LAST READING, not before today: a
    collection that stopped a week ago still answers, instead of an empty chart."""
    cols = ["title", "lifetime", "recent"]
    if videos.empty or readings.empty:
        return pd.DataFrame(columns=cols)
    r = readings.assign(collected_at=pd.to_datetime(readings["collected_at"], utc=True))
    last = r["collected_at"].max()
    r = r[r["collected_at"] >= last - pd.Timedelta(days=days)]
    today = today or last.date()
    r = r.sort_values(["video_id", "collected_at"])
    g = r.groupby("video_id", sort=False)
    span = (g["collected_at"].last() - g["collected_at"].first()).dt.total_seconds() / 86400
    rise = g["view_count"].last() - g["view_count"].first()
    recent = (rise / span).where(span >= 1)
    v = videos.set_index("video_id")
    age = [max((today - d).days, 1)
           for d in pd.to_datetime(v["published_at"], utc=True).dt.date]
    out = pd.DataFrame({"title": v["title"], "lifetime": v["view_count"] / age})
    out["recent"] = recent.reindex(out.index)
    out = out.dropna(subset=["recent"])
    return out.sort_values("recent", ascending=False, kind="stable")[cols].reset_index(drop=True)


def pace_figure(paced: pd.DataFrame, top: int = 10) -> go.Figure:
    """Views over the last 30 days of readings, per video — who still draws. Drawn per
    30 days, not per day: 0.3 views a day reads « 0.0 » once rounded, 10 a month reads.

    The lifetime average is in the hover, not drawn: a launch spike makes it 100× the
    recent pace (43 against 0.3 on the owner's channel), and a shared axis flattened
    the one number that decides what to promote."""
    kept = paced[30 * paced["recent"] >= 0.5].head(top)
    d = kept.iloc[::-1]
    month = 30 * d["recent"]
    labels = _labels(kept["title"])[::-1]
    fig = go.Figure(go.Bar(
        x=month, y=labels, orientation="h",
        marker=dict(color=month, colorscale=_REDS),
        customdata=30 * d["lifetime"], text=[num(round(x), 0) for x in month],
        textposition="outside", cliponaxis=False,
        hovertemplate=t("youtube.pace_hover",
                        "%{y}<br>%{x:,.0f} vues / 30 j · %{customdata:,.0f} en moyenne "
                        "depuis la sortie")
        + "<extra></extra>"))
    fig.update_layout(title=t("youtube.pace_title",
                              "Qui prend encore des vues ? Vues des 30 derniers jours"),
                      height=120 + 28 * len(d), showlegend=False,
                      margin=dict(l=10, r=40, t=50, b=30))
    fig.update_yaxes(automargin=True)
    return fig


def _channel_section(db, artist_id: int) -> None:
    """Subscribers + cumulative views on one frame, then the views each video gained."""
    st.subheader(t("youtube.channel_header", "📈 Évolution de la Chaîne"))
    # « Depuis la dernière sortie » par défaut (2026-09-21) : toute l'app s'ancre sur
    # la dernière sortie.
    window = smart_period_filter(
        db, table="youtube_channel_history", date_column="collected_at",
        artist_id=artist_id, key="yt_channel",
        latest_release_resolver=lambda: latest_release_date(db, artist_id),
    )
    frag, frag_params = window.sql_between("collected_at")
    # Les ABONNÉS n'existent que sur la chaîne ; les VUES viennent de la couche or
    # (`platform_timeseries.youtube_cumulative_views`), pas du compteur de chaîne.
    df_hist = db.fetch_df(f"""
        SELECT date(collected_at) as date, MAX(subscriber_count) as subs
        FROM youtube_channel_history
        WHERE artist_id = %s {frag}
        GROUP BY date(collected_at)
        ORDER BY date
    """, (artist_id, *frag_params))
    if df_hist.empty:
        st.info(t("youtube.no_channel_history", "Pas encore d'historique pour la chaîne."))
        return
    views_series = [
        (d, v) for d, v in pts.youtube_cumulative_views(db, artist_id)
        if window.is_all_history or window.start <= d <= window.end
    ]
    charts.plotly_chart(channel_figure(df_hist, views_series), width="stretch")
    gained = views_gained(_readings(db, artist_id,
                                    None if window.is_all_history else window.start,
                                    None if window.is_all_history else window.end))
    if not gained.empty:
        charts.plotly_chart(views_gained_figure(gained), width="stretch")


def _readings(db, artist_id: int, since=None, until=None) -> pd.DataFrame:
    return pd.DataFrame(pts.youtube_video_readings(db, artist_id, since, until),
                        columns=["video_id", "title", "collected_at", "view_count"])


def _videos_section(db, artist_id: int) -> None:
    """The videos published in the window: what works, Pareto per type, who picks up."""
    st.subheader(t("youtube.top_header", "🏆 Top Contenus"))
    # LE filtre canonique (2026-09-21) — garde `test_a_period_selector_is_the_shared_one`.
    # La fenêtre est une COHORTE : les vidéos SORTIES dans la période, chiffres à ce jour.
    c_period, c_n = st.columns(2)
    with c_period:
        win_pub = smart_period_filter(
            db, table="youtube_videos", date_column="published_at",
            artist_id=artist_id, key="yt_videos",
            latest_release_resolver=lambda: latest_release_date(db, artist_id),
        )
    pub_frag, pub_params = win_pub.sql_between("published_at")
    # R289 — the latest reading of each video, from the gold view (migration 144).
    df_videos = db.fetch_df(f"""
        SELECT video_id, title, duration, published_at, view_count, like_count, comment_count
        FROM v_youtube_video_latest
        WHERE artist_id = %s {pub_frag}
        ORDER BY published_at DESC
    """, (artist_id, *pub_params))
    if df_videos.empty:
        st.warning(t("youtube.no_video_db", "Aucune vidéo trouvée en base."))
        return
    with c_n:
        top_n = st.slider(t("youtube.n_videos", "Nombre de vidéos"), 5, 50, 10)
    # The window is a publication cohort (`test_a_cohort_bound_figure_says_so`) : the
    # title says the counts are to date, in the chart, not in a caption under it (W8).
    charts.plotly_chart(top_figure(df_videos, top_n, t(
        "youtube.top_title", "Les vidéos sorties sur la période — vues et likes acquis à ce jour")),
        width="stretch")
    # W8 : « type de contenu » retiré — deux Pareto alignés, vidéos et shorts.
    seconds = df_videos["duration"].apply(parse_duration)
    is_short = (seconds > 0) & (seconds <= 60)
    col_v, col_s = st.columns(2)
    for col, part, title in (
            (col_v, df_videos[~is_short], t("youtube.pareto_videos", "Vidéos — part cumulée des vues")),
            (col_s, df_videos[is_short], t("youtube.pareto_shorts", "Shorts — part cumulée des vues"))):
        if not part.empty:
            charts.plotly_chart(pareto_figure(part, title, top_n), container=col,
                                width="stretch", pareto=False)
    paced = pace(df_videos, _readings(db, artist_id))
    if not paced.empty and (30 * paced["recent"] >= 0.5).any():
        charts.plotly_chart(pace_figure(paced, top_n), width="stretch", pareto=False)


def show():
    # ⚠️ NI TITRE NI SOUS-TITRE (2026-09-21) : le titre répétait l'entrée de menu.
    with view_session() as (db, artist_id):
        try:
            _channel_section(db, artist_id)
            _videos_section(db, artist_id)
        except Exception as e:
            st.error(t("youtube.error", "Erreur : {err}").format(err=e))


if __name__ == "__main__":
    show()
