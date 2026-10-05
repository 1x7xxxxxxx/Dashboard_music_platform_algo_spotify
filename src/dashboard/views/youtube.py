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


def like_ratio_ranking(videos: pd.DataFrame) -> pd.DataFrame:
    """Videos ranked by likes per 1 000 views, best first. Pure (R384).

    A video without a single view has no ratio and is left out: 0 likes on 0 views is
    not a video nobody liked. Comments per 1 000 views ride along, same denominator."""
    from src.dashboard.utils.ratios import per_series

    out = videos.assign(
        likes_per_k=per_series(videos["like_count"], videos["view_count"], 1000),
        comments_per_k=per_series(videos["comment_count"], videos["view_count"], 1000))
    out = out.dropna(subset=["likes_per_k"]).sort_values(
        ["likes_per_k", "view_count"], ascending=False, kind="stable")
    return out.assign(label=_labels(out["title"]))


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


def views_gained_figure(gained: pd.DataFrame, top: int = 10) -> go.Figure:
    """The videos that gained the most views over the period, horizontal bars."""
    d = gained.head(top).iloc[::-1]
    labels = _labels(gained.head(top)["title"])[::-1]
    fig = go.Figure(go.Bar(x=d["gained"], y=labels, orientation="h", marker_color=_YT,
                           text=[num(int(v), 0) for v in d["gained"]],
                           textposition="outside", cliponaxis=False))
    fig.update_layout(title=t("youtube.gained_title",
                              "Vues gagnées sur la période, par vidéo"),
                      height=120 + 28 * len(d), showlegend=False,
                      margin=dict(l=10, r=40, t=50, b=30))
    fig.update_yaxes(automargin=True)
    return fig


def ratio_ranking_figure(ranked: pd.DataFrame, title: str) -> go.Figure:
    """Likes and comments per 1 000 views, one row per video, best ratio on top."""
    from plotly.subplots import make_subplots

    d = ranked.iloc[::-1]
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, column_widths=[0.65, 0.35],
                        horizontal_spacing=0.08,
                        subplot_titles=(t("youtube.likes_per_k", "Likes pour 1 000 vues"),
                                        t("youtube.comments_per_k",
                                          "Commentaires pour 1 000 vues")))
    hover = [f"{num(int(v), 0)} vues" for v in d["view_count"]]
    for col, field in ((1, "likes_per_k"), (2, "comments_per_k")):
        fig.add_trace(go.Bar(x=d[field].fillna(0), y=d["label"], orientation="h",
                             marker_color=_YT, opacity=1 if col == 1 else 0.55,
                             text=[f"{v:.1f}" for v in d[field].fillna(0)],
                             textposition="outside", cliponaxis=False,
                             customdata=hover,
                             hovertemplate="%{y}<br>%{x:.1f} · %{customdata}<extra></extra>"),
                      row=1, col=col)
    fig.update_layout(title=title, height=140 + 28 * len(d), showlegend=False,
                      margin=dict(l=10, r=40, t=80, b=30))
    fig.update_yaxes(automargin=True)
    fig.update_xaxes(rangemode="tozero")
    return fig


def age_views_figure(videos: pd.DataFrame, today: date | None = None) -> go.Figure:
    """Age of each video (days since publication) against its views, both on log axes."""
    today = today or date.today()
    pub = pd.to_datetime(videos["published_at"], utc=True).dt.date
    age = [max((today - d).days, 1) for d in pub]
    fig = go.Figure(go.Scatter(
        x=age, y=videos["view_count"], mode="markers",
        marker=dict(color=_YT, size=9, opacity=0.75),
        text=[str(x) for x in videos["title"]],
        hovertemplate="%{text}<br>%{x} j · %{y:,.0f} vues<extra></extra>"))
    fig.update_layout(title=t("youtube.age_title",
                              "Âge de la vidéo et vues acquises à ce jour"),
                      xaxis_title=t("youtube.age_days", "Jours depuis la publication"),
                      yaxis_title=t("youtube.views", "Vues"),
                      height=380, showlegend=False, margin=dict(t=50, b=40))
    fig.update_xaxes(type="log")
    fig.update_yaxes(type="log", tickformat="~s")
    return fig


def show():
    # ⚠️ NI TITRE NI SOUS-TITRE — retirés le 2026-09-21, même geste que la page
    # Apple : « 🎬 YouTube Analytics » répétait l'entrée de menu qu'on vient de
    # cliquer, et « Analyse de la Chaîne et des Vidéos » décrivait la page au lieu
    # de la commencer.

    with view_session() as (db, artist_id):
        try:
            # ============================================================================
            # 1. ANALYSE GLOBALE (CHAÎNE)
            # ============================================================================
            st.subheader(t("youtube.channel_header", "📈 Évolution de la Chaîne"))

            # « DEPUIS LA DERNIÈRE SORTIE » par défaut — 2026-09-21, demandé
            # explicitement, et c'est un REVIREMENT assumé. Le défaut valait
            # `"all"` depuis que les abonnés n'existent que sur cette table ; le
            # motif écrit alors portait sur la SOURCE des abonnés, pas sur la
            # fenêtre. Les deux questions sont distinctes, et la seconde appartient
            # au propriétaire : toute l'app s'ancre sur la dernière sortie.
            window = smart_period_filter(
                db, table="youtube_channel_history", date_column="collected_at",
                artist_id=artist_id, key="yt_channel",
                latest_release_resolver=lambda: latest_release_date(db, artist_id),
            )
            frag, frag_params = window.sql_between("collected_at")
            # Les ABONNÉS n'existent que sur la chaîne — cette table est leur seule
            # source. Les VUES, non : le compteur de chaîne porte des vidéos absentes
            # du catalogue et avance par paliers. Il est lu plus bas, sous son propre
            # nom, et la courbe vient de la couche or. Voir
            # `platform_timeseries.youtube_cumulative_views`.
            hist_query = f"""
                SELECT date(collected_at) as date,
                       MAX(subscriber_count) as subs
                FROM youtube_channel_history
                WHERE artist_id = %s {frag}
                GROUP BY date(collected_at)
                ORDER BY date
            """
            df_hist = db.fetch_df(hist_query, (artist_id, *frag_params))

            views_series = [
                (d, v) for d, v in pts.youtube_cumulative_views(db, artist_id)
                if window.is_all_history or window.start <= d <= window.end
            ]

            if not df_hist.empty:
                from plotly.subplots import make_subplots
                fig_channel = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                            vertical_spacing=0.09,
                                            subplot_titles=[
                                                t("youtube.subscribers", "Abonnés"),
                                                t("youtube.cumulative_views",
                                                  "Vues Cumulées")])

                # Axe Y1 (Gauche) : Abonnés (ligne + marqueurs, PAS de remplissage)
                # fill='tozeroy' ancrait la bande à 0 → avec des comptes absolus élevés,
                # les variations quotidiennes paraissaient plates. On garde une ligne
                # simple et on resserre l'axe sur la plage réelle (voir update_layout).
                # UN ESCALIER, PAS UNE COURBE — 2026-09-21.
                #
                # `subscriberCount` est arrondi à trois chiffres significatifs par la
                # Data API : mesuré ici, **2 valeurs distinctes sur 34 jours** (10 600
                # et 10 700). Tracée en `lines+markers` avec l'axe resserré sur la
                # plage réelle, cette marche de 100 prenait l'allure d'une pente
                # continue — l'artiste lisait une progression jour par jour là où il
                # n'y a que deux mesures.
                #
                # `line_shape="hv"` dit la vérité de la donnée : la valeur tient, puis
                # saute. C'est la même discipline que « l'absence devient un pixel »,
                # appliquée à la PRÉCISION plutôt qu'à l'absence.
                fig_channel.add_trace(go.Scatter(
                    x=df_hist['date'], y=df_hist['subs'],
                    name=t("youtube.subscribers", "Abonnés"),
                    mode='lines+markers', line_shape='hv',
                    line=dict(color=_YT, width=2),
                ), row=1, col=1)

                # Axe Y2 (Droite) : Vues Totales (Blanc/Gris clair pour Dark Mode)
                # ✅ CORRECTION COULEUR (Visible sur fond noir)
                fig_channel.add_trace(go.Scatter(
                    x=[d for d, _ in views_series], y=[v for _, v in views_series],
                    name=t("youtube.total_views", "Vues Totales"),
                    mode='lines+markers',
                    line=dict(color=_YT, width=2, dash='dot'),
                ), row=2, col=1)

                # Smart range: zoom the subscriber axis onto the actual data band
                # with a small margin, instead of starting at 0. Makes day-to-day
                # evolution visible even when absolute counts are large. Falls back
                # to autorange when the series is flat (min == max).
                subs_min, subs_max = float(df_hist['subs'].min()), float(df_hist['subs'].max())
                subs_span = subs_max - subs_min
                if subs_span > 0:
                    margin = max(subs_span * 0.10, 1)
                    subs_range = [subs_min - margin, subs_max + margin]
                else:
                    subs_range = None  # flat series → let Plotly autorange

                # DEUX CADRES. Des abonnés (milliers) et un compteur de vues cumulées
                # (centaines de milliers) sur un repère commun rendent la première
                # courbe plate ; sur deux axes superposés, leur croisement est un
                # artefact de cadrage. La plage resserrée des abonnés — écrite pour
                # rendre l'évolution quotidienne visible — garde tout son sens dans son
                # propre cadre.
                fig_channel.update_yaxes(title_text=t("youtube.subscribers", "Abonnés"),
                                         range=subs_range, tickformat="~s", row=1, col=1)
                fig_channel.update_yaxes(
                    title_text=t("youtube.cumulative_views", "Vues Cumulées"),
                    tickformat="~s", row=2, col=1)
                fig_channel.update_xaxes(title_text=t("common.date", "Date"), row=2, col=1)
                fig_channel.update_layout(
                    title=t("youtube.channel_chart_title",
                            "Croissance : Abonnés vs Vues Totales"),
                    hovermode='x unified', showlegend=False, height=480,
                )
                charts.plotly_chart(fig_channel, width="stretch")

                # R384 (V39, owner 2026-10-05) : la légende explicative est retirée.
                # Les trois tuiles étaient déjà parties le 2026-09-21 ; l'escalier des
                # abonnés et l'écart des deux compteurs de vues sont dits dans le
                # docstring de ce module, pas à l'écran.
                gained = views_gained(pd.DataFrame(
                    pts.youtube_video_readings(
                        db, artist_id,
                        None if window.is_all_history else window.start,
                        None if window.is_all_history else window.end),
                    columns=["video_id", "title", "collected_at", "view_count"]))
                if not gained.empty:
                    charts.plotly_chart(views_gained_figure(gained), width="stretch")

            else:
                st.info(t("youtube.no_channel_history", "Pas encore d'historique pour la chaîne."))

            st.markdown("---")

            # ============================================================================
            # 2. ANALYSE VIDÉOS (TOP & SHORTS)
            # ============================================================================

            # ── Release-date filter (mirrors S4A / Apple / SoundCloud / Meta) ────
            st.subheader(t("youtube.top_header", "🏆 Top Contenus"))

            _all_lbl = t("common.all", "Tous")

            # LE FILTRE CANONIQUE, PAS UN DE PLUS — 2026-09-21.
            #
            # Cette section portait son propre sélecteur : cinq préréglages écrits à
            # la main (« 12 derniers mois », « 30 derniers jours »…) convertis en
            # `timedelta`. Il ne partageait rien avec le reste de l'app : ni les
            # mêmes intitulés, ni la plage personnalisée, ni l'ancrage sur la
            # dernière sortie, ni la borne sur l'étendue RÉELLE des données — un
            # artiste pouvait donc y choisir une fenêtre vide, ce que
            # `smart_period_filter` rend impossible par construction.
            #
            # Un sélecteur par page, c'est une définition de « période » par page.
            # Garde : `test_a_period_selector_is_the_shared_one.py`.
            c_period, c_filter1, c_filter2 = st.columns(3)
            with c_period:
                win_pub = smart_period_filter(
                    db, table="youtube_videos", date_column="published_at",
                    artist_id=artist_id, key="yt_videos",
                    latest_release_resolver=lambda: latest_release_date(db, artist_id),
                )
            # Récupération des vidéos + stats, bornée par LA fenêtre partagée.
            #
            # `published_at` est la date de PUBLICATION : la fenêtre choisit donc les
            # vidéos SORTIES dans la période, pas les vues qu'elles ont faites
            # pendant. C'est ce que « Top Contenus » veut dire, et le libellé le dit.
            pub_frag, pub_params = win_pub.sql_between("published_at")
            # R289 — the latest reading of each video, from the gold view (migration 144).
            videos_query = f"""
                SELECT title, duration, published_at, thumbnail_url,
                       view_count, like_count, comment_count
                FROM v_youtube_video_latest
                WHERE artist_id = %s {pub_frag}
                ORDER BY published_at DESC
            """
            df_videos = db.fetch_df(videos_query, (artist_id, *pub_params))

            # ⚠️ CETTE FENÊTRE EST UNE COHORTE : elle choisit les vidéos SORTIES dans la
            # période, avec les chiffres acquis à ce jour. La légende qui le disait est
            # partie avec R384 (V39) ; les TITRES des figures le disent — le garde
            # `test_a_cohort_bound_figure_says_so` lit les textes vus par l'artiste.
            if not df_videos.empty:
                # Traitement
                _short_lbl = t("youtube.type_short", "Short 📱")
                _video_lbl = t("youtube.type_video", "Vidéo 📹")
                df_videos['seconds'] = df_videos['duration'].apply(parse_duration)
                df_videos['type'] = df_videos['seconds'].apply(lambda x: _short_lbl if 0 < x <= 60 else _video_lbl)

                with c_filter1:
                    selected_type = st.selectbox(t("youtube.content_type", "Type de contenu"), [_all_lbl, _video_lbl, _short_lbl])
                with c_filter2:
                    top_n = st.slider(t("youtube.n_videos", "Nombre de vidéos"), 5, 50, 10)

                # Application filtres
                df_filtered = df_videos.copy()
                if selected_type != _all_lbl:
                    df_filtered = df_filtered[df_filtered['type'] == selected_type]

                df_top = df_filtered.head(top_n)

                if not df_top.empty:
                    # R384 (V40, owner 2026-10-05) : « voir d'un coup d'œil la meilleure
                    # vidéo ». Le nuage vues × likes demandait de chercher le point le plus
                    # haut ; un CLASSEMENT par likes pour 1 000 vues le met en tête.
                    charts.plotly_chart(ratio_ranking_figure(
                        like_ratio_ranking(df_top),
                        t("youtube.ranking_title", "Classement des vidéos publiées sur la "
                          "période, par date de publication — chiffres acquis à ce jour")),
                        width="stretch")
                    charts.plotly_chart(age_views_figure(df_top), width="stretch")

                else:
                    st.info(t("youtube.no_video_category", "Aucune vidéo dans cette catégorie."))
            else:
                st.warning(t("youtube.no_video_db", "Aucune vidéo trouvée en base."))

        except Exception as e:
            st.error(t("youtube.error", "Erreur : {err}").format(err=e))

if __name__ == "__main__":
    show()
