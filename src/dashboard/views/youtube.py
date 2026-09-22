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
import streamlit as st
import plotly.graph_objects as go
import isodate
from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t
from src.dashboard.utils.period_filter import (
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
                default_override="last_release",
            )
            frag, frag_params = window.sql_between("collected_at")
            # Les ABONNÉS n'existent que sur la chaîne — cette table est leur seule
            # source. Les VUES, non : le compteur de chaîne porte des vidéos absentes
            # du catalogue et avance par paliers. Il est lu plus bas, sous son propre
            # nom, et la courbe vient de la couche or. Voir
            # `platform_timeseries.youtube_cumulative_views`.
            hist_query = f"""
                SELECT date(collected_at) as date,
                       MAX(subscriber_count) as subs,
                       MAX(view_count) as channel_views
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
                st.plotly_chart(fig_channel, width="stretch")

                # ⚠️ LES TROIS TUILES SONT PARTIES le 2026-09-21, à la demande du
                # propriétaire — « 👥 Abonnés Actuels / 👁️ Vues Totales / 📺 Vues de
                # la chaîne ». Elles répétaient en chiffre le dernier point des deux
                # courbes juste au-dessus, et la troisième demandait une bulle d'aide
                # pour expliquer pourquoi elle différait de la deuxième.
                #
                # Ce qu'elles portaient d'irremplaçable — que les deux compteurs de
                # vues ne sont pas le même — descend dans la légende, où il est LU au
                # lieu d'être survolé.
                _subs_paliers = int(df_hist['subs'].nunique())
                st.caption(t(
                    "youtube.channel_caption",
                    "**Abonnés** : YouTube arrondit ce compteur à trois chiffres "
                    "significatifs sur l'API publique — {n} valeur(s) distincte(s) "
                    "seulement sur {j} jours de relevés ici, d'où l'escalier. Le "
                    "quotidien exact existe, mais il demande un accès "
                    "**propriétaire de chaîne** (API YouTube Analytics), pas une clé "
                    "d'API.\n\n"
                    "**Vues** : la courbe additionne les compteurs PAR VIDÉO, qui "
                    "bougent à l'unité ({vues}). Le compteur que YouTube affiche pour "
                    "la chaîne vaut {chaine} — il inclut des vidéos privées, "
                    "supprimées et des agrégats absents du catalogue analysé ici. "
                    "Les voir diverger est une information, pas une erreur."
                ).format(
                    n=_subs_paliers, j=len(df_hist),
                    vues=f"{views_series[-1][1]:,}".replace(",", " ") if views_series else "—",
                    chaine=f"{int(df_hist.iloc[-1]['channel_views']):,}".replace(",", " ")))

            else:
                st.info(t("youtube.no_channel_history", "Pas encore d'historique pour la chaîne."))

            st.markdown("---")

            # ============================================================================
            # 2. ANALYSE VIDÉOS (TOP & SHORTS)
            # ============================================================================

            # ── Release-date filter (mirrors S4A / Apple / SoundCloud / Meta) ────
            st.subheader(t("youtube.top_header", "🏆 Top Contenus (Analyse Multi-Axes)"))

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
                    default_override="last_release",
                )
            # Récupération des vidéos + stats, bornée par LA fenêtre partagée.
            #
            # `published_at` est la date de PUBLICATION : la fenêtre choisit donc les
            # vidéos SORTIES dans la période, pas les vues qu'elles ont faites
            # pendant. C'est ce que « Top Contenus » veut dire, et le libellé le dit.
            pub_frag, pub_params = win_pub.sql_between("published_at")
            videos_query = f"""
                SELECT
                    v.title, v.duration, v.published_at, v.thumbnail_url,
                    vs.view_count, vs.like_count, vs.comment_count
                FROM youtube_videos v
                JOIN (
                    SELECT video_id, MAX(collected_at) as max_date
                    FROM youtube_video_stats
                    WHERE artist_id = %s
                    GROUP BY video_id
                ) latest ON v.video_id = latest.video_id
                JOIN youtube_video_stats vs
                    ON vs.video_id = latest.video_id AND vs.collected_at = latest.max_date
                WHERE v.artist_id = %s {pub_frag.replace('published_at', 'v.published_at')}
                ORDER BY v.published_at DESC
            """
            df_videos = db.fetch_df(videos_query, (artist_id, artist_id, *pub_params))

            # ⚠️ CETTE FENÊTRE EST UNE COHORTE, ET ÇA SE DIT À L'ARTISTE.
            #
            # Elle borne `published_at` : elle choisit les vidéos SORTIES dans la
            # période, pas l'activité qu'elles ont eue pendant. Les chiffres
            # affichés sont ceux acquis À CE JOUR, depuis la publication. « Top
            # contenus des 30 derniers jours » se lirait comme un flux ; c'est un
            # classement de cohorte.
            #
            # ⚠️ Et l'annonce vit APRÈS le bornage, pas avant : le garde
            # (`test_a_period_bound_is_on_the_right_column`) lit les textes des
            # 90 lignes qui SUIVENT le `sql_between`, parce qu'un texte placé
            # au-dessus du sélecteur ne décrit pas forcément la figure d'en
            # dessous. Posée près du sélecteur, la phrase était invisible au garde
            # — et, plus important, elle était loin de la figure qu'elle qualifie.
            st.caption(t("youtube.cohort_notice",
                         "Classement **par date de publication** : la fenêtre "
                         "choisit les vidéos SORTIES dans la période. Les chiffres "
                         "sont ceux **acquis à ce jour**, depuis leur publication — "
                         "pas l'activité de la période."))

            if not df_videos.empty:
                # Traitement
                _short_lbl = t("youtube.type_short", "Short 📱")
                _video_lbl = t("youtube.type_video", "Vidéo 📹")
                df_videos['seconds'] = df_videos['duration'].apply(parse_duration)
                df_videos['type'] = df_videos['seconds'].apply(lambda x: _short_lbl if 0 < x <= 60 else _video_lbl)

                # Calcul Ratio Vues/Like (Combien de vues pour 1 like ?)
                df_videos['ratio_views_like'] = df_videos.apply(
                    lambda x: x['view_count'] / x['like_count'] if x['like_count'] > 0 else 0, axis=1
                )

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
                    # QUATRE MESURES, QUATRE CADRES — plus quatre axes superposés.
                    #
                    # Cette figure empilait `yaxis` à `yaxis4` : des vues (dizaines de
                    # milliers), des likes (centaines), des commentaires (dizaines) et
                    # un ratio sans unité, forcés à partager un même repère par simple
                    # décalage de côté. Un lecteur ne peut pas comparer deux courbes qui
                    # n'ont ni la même unité ni la même échelle ; il lit une forme, et
                    # cette forme ne veut rien dire.
                    #
                    # Les petits multiples sont la seule alternative admise dans ce
                    # produit — la figure de l'accueil porte la même décision, écrite le
                    # 2026-09-08. On perd la superposition, on gagne quatre séries
                    # réellement lisibles, chacune sur SON échelle.
                    from plotly.subplots import make_subplots

                    _panels = [
                        (t("youtube.views", "Vues"), "view_count", "#2a78d6", "bar"),
                        ("Likes", "like_count", "#1baf7a", "line"),
                        (t("youtube.comments", "Commentaires"), "comment_count",
                         "#eb6834", "line"),
                        (t("youtube.ratio_views_like", "Ratio Vues/Like"),
                         "ratio_views_like", "#eda100", "line"),
                    ]
                    fig_top = make_subplots(
                        rows=len(_panels), cols=1, shared_xaxes=True,
                        vertical_spacing=0.05,
                        subplot_titles=[lbl for lbl, _, _, _ in _panels],
                    )
                    for _row, (_lbl, _col, _colour, _kind) in enumerate(_panels, start=1):
                        _trace = (go.Bar(x=df_top['title'], y=df_top[_col],
                                         name=_lbl, marker_color=_colour)
                                  if _kind == "bar" else
                                  go.Scatter(x=df_top['title'], y=df_top[_col],
                                             name=_lbl, mode='lines+markers',
                                             line=dict(color=_colour, width=2)))
                        fig_top.add_trace(_trace, row=_row, col=1)

                    fig_top.update_layout(
                        title=t("youtube.top_chart_title", "Top {n} {type}").format(
                            n=top_n, type=selected_type),
                        showlegend=False,          # chaque cadre porte son propre titre
                        hovermode='x unified',
                        height=180 * len(_panels),
                        margin=dict(b=90, r=20),
                    )

                    st.plotly_chart(fig_top, width="stretch")

                else:
                    st.info(t("youtube.no_video_category", "Aucune vidéo dans cette catégorie."))
            else:
                st.warning(t("youtube.no_video_db", "Aucune vidéo trouvée en base."))

        except Exception as e:
            st.error(t("youtube.error", "Erreur : {err}").format(err=e))

if __name__ == "__main__":
    show()
