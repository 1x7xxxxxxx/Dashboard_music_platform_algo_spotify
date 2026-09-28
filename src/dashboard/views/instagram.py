"""Instagram — la communauté dans le temps, en vraies valeurs.

Type: Feature
Uses: view_session, smart_period_filter, platform_absence, i18n
Depends on: instagram_daily_stats, instagram_media,
            v_instagram_media_monthly, v_instagram_followers_daily
Persists in: — (lecture seule)

LA BASE 100 EST PARTIE, ET C'EST UN ARBITRAGE ASSUMÉ
------------------------------------------------------
Demandé le 2026-09-21 : « supprimer le graphique base 100, si on arrive tout
mettre mais pas en base 100 ».

La base 100 existait pour une raison réelle : abonnés (1 522), abonnements (621)
et publications (51) sont dans un rapport de 30, et sur un repère commun les deux
dernières séries sont écrasées au fond. Ce qu'elle coûtait, en revanche, c'est
les CHIFFRES : un artiste y lit « 103 » là où il veut lire « 1 525 abonnés ».

Les trois séries sont donc en PETITS MULTIPLES — trois cadres, une horloge
commune, chacun sur son échelle, avec ses vraies valeurs. C'est la forme que ce
dépôt admet déjà partout ailleurs pour des ordres de grandeur incomparables, et
elle répond à la demande sans rien inventer : rien n'est normalisé, rien n'est
caché.

Conséquence : la figure « Évolution des Abonnés » seule disparaît aussi — elle
était le premier des trois cadres, dessiné deux fois.

CE QUE LA PAGE NE PEUT PAS MONTRER, ET POURQUOI
-------------------------------------------------
`instagram_media_insights` était **vide** (0 ligne, local et production) : la
collecte demandait `impressions`, que Meta a retirée le 2025-04-21 pour toutes les
versions de l'API, et une seule métrique retirée fait refuser toute la requête. La
page disait « posts de plus de 90 jours, pas un défaut de collecte » — une cause
écrite sans avoir lu la réponse de Meta. Corrigé par R273 : `views` et
`total_interactions` remplissent les colonnes `impressions` et `engagement`.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from src.dashboard.utils import view_session, charts
from src.dashboard.utils.i18n import t
from src.dashboard.utils.filters import (
    latest_release_date,
    smart_period_filter,
)
from src.dashboard.utils.ui import (
    say_why_it_is_empty,
    secondary_analyses,
    show_empty_state,
)
from src.dashboard.utils.tz import to_local_naive
from src.dashboard.utils.date_format import format_date
from src.dashboard.utils.platform_colors import UNMEASURED_BRAND, platform_color

# Instagram n'a PAS de couleur mesurée : sept teintes attribuables sont impossibles
# dans cette palette (recherche conjointe du 2026-09-21, ΔE 9,6 en clair contre un
# plancher de 15 — la deutéranopie fait converger un cyan et un violet vers le même
# bleu). Le détail est dans `platform_colors`. Sa page n'affiche qu'UNE plateforme :
# la question de l'attribution ne s'y pose pas, et on garde donc sa teinte de marque.
_IG = platform_color("instagram", default=UNMEASURED_BRAND["instagram"])
_IG_DEEP = "#833AB4"   # R290 — engagement per post, the deeper Instagram ink

def show():
    # ⚠️ NI TITRE NI SOUS-TITRE — retirés le 2026-09-21, même geste que sur Apple,
    # YouTube et SoundCloud : « 📸 Instagram - Performance » répétait l'entrée de
    # menu qu'on vient de cliquer.

    with view_session() as (db, artist_id):
        # 1. KPIs (Dernier Snapshot)
        try:
            df_latest = db.fetch_df("""
                SELECT DISTINCT ON (ig_user_id)
                    ig_user_id, username, followers_count, follows_count,
                    media_count, collected_at
                FROM instagram_daily_stats
                WHERE artist_id = %s
                ORDER BY ig_user_id, collected_at DESC
            """, (artist_id,))

            if not df_latest.empty:
                followers = int(df_latest['followers_count'].iloc[0] or 0)
                follows = int(df_latest['follows_count'].iloc[0] or 0)
                media = int(df_latest['media_count'].iloc[0] or 0)
                username = df_latest['username'].iloc[0]
                last_date = format_date(pd.to_datetime(df_latest['collected_at'].iloc[0]))

                st.subheader(t("instagram.account", "Compte : @{username}").format(username=username))

                # ⚠️ TROIS TUILES, PAS QUATRE — « 📅 Mise à jour » est partie le
                # 2026-09-21. Une date de collecte est un fait de PLOMBERIE : elle
                # ne décide rien et occupait le quart du bandeau. Elle descend dans
                # la légende, avec ce qu'elle veut dire.
                c1, c2, c3 = st.columns(3)
                c1.metric(t("instagram.kpi_followers", "👥 Abonnés"), f"{followers:,}")
                c2.metric(t("instagram.kpi_follows", "➡️ Abonnements"), f"{follows:,}")
                c3.metric(t("instagram.kpi_media", "📸 Publications"), f"{media:,}")
            else:
                st.warning(t("instagram.no_data", "Aucune donnée Instagram. Lancez le collecteur."))
                return

        except Exception as e:
            st.error(e)
            return

        st.markdown("---")

        # 2. GRAPHIQUE D'ÉVOLUTION
        st.subheader(t("instagram.community_growth", "📈 Croissance de la communauté"))

        # DÉFAUT « DEPUIS LA DERNIÈRE SORTIE » — 2026-09-21, appliqué à toute
        # l'app. « En cours » (l'année civile) est un cadre de calendrier posé sur
        # une donnée qui suit des SORTIES : en janvier, il rend une page quasi vide
        # pour un artiste dont la dernière sortie date de novembre.
        window = smart_period_filter(
            db, table="instagram_daily_stats", date_column="collected_at",
            artist_id=artist_id, key="ig_community",
            latest_release_resolver=lambda: latest_release_date(db, artist_id),
        )

        try:
            frag, frag_params = window.sql_between("collected_at")
            query = f"""
                SELECT collected_at, followers_count, follows_count, media_count
                FROM instagram_daily_stats
                WHERE artist_id = %s {frag}
                ORDER BY collected_at ASC
            """
            df_hist = db.fetch_df(query, (artist_id, *frag_params))

            if df_hist.empty:
                # DEUX SILENCES, DEUX GESTES. « Rien dans CETTE fenêtre » fait
                # élargir ; « aucun relevé » fait brancher le collecteur. Le
                # message d'avant disait « aucune donnée d'historique pour cette
                # période » — une phrase qui mélange les deux, et le garde
                # `test_a_silence_names_its_own_cause` la refuse à raison.
                _tout = db.fetch_df(
                    "SELECT MAX(collected_at) AS last FROM instagram_daily_stats "
                    "WHERE artist_id = %s", (artist_id,))
                _last = None if _tout.empty else _tout.iloc[0]["last"]
                say_why_it_is_empty(
                    None if _last is None else to_local_naive(
                        pd.Series([_last])).iloc[0].date(),
                    window,
                    empty_window=t(
                        "instagram.nothing_in_window",
                        "Aucun relevé Instagram sur cette période. Le dernier "
                        "remonte au **{last}** — élargis la fenêtre pour revoir "
                        "l'historique."
                    ).format(last="—" if _last is None else format_date(_last)),
                    no_history=t(
                        "instagram.not_enough_history",
                        "Aucun relevé Instagram pour ce compte. Branche-le depuis "
                        "**🔑 Credentials API + imports CSV**."))
            else:
                # timestamptz across a DST change → mixed offsets (utils/tz.py).
                df_hist['collected_at'] = to_local_naive(df_hist['collected_at'])
                _render_community(df_hist, window, last_date)

        except Exception as e:
            st.error(t("instagram.history_error", "Erreur historique : {err}").format(err=e))

        # 3. ENGAGEMENT & PUBLICATIONS
        st.markdown("---")
        st.subheader(t("instagram.engagement_header", "📝 Engagement & publications"))

        win_m = smart_period_filter(
            db, table="instagram_media", date_column="timestamp",
            artist_id=artist_id, key="ig_media",
            latest_release_resolver=lambda: latest_release_date(db, artist_id),
        )
        try:
            frag_m, params_m = win_m.sql_between("timestamp")
            # La requête d'engagement lit `v_instagram_media_monthly`, dont la colonne
            # de date s'appelle `month` — la table, elle, a `timestamp`, et le second
            # usage de `frag_m` plus bas la lit encore. Deux fragments, une seule
            # fenêtre : c'est la même période, exprimée dans les deux vocabulaires.
            frag_month, params_month = win_m.sql_between("month")

            # CE N'EST PAS UN ENGAGEMENT PAR MOIS. C'EST UNE COHORTE DE PUBLICATION.
            #
            # `like_count` est le compteur CUMULÉ d'un post, tel qu'il est aujourd'hui ;
            # `timestamp` est sa date de PUBLICATION. Grouper l'un par l'autre range donc
            # les likes dans le mois où le post est SORTI, quelle que soit la date à
            # laquelle ils ont été donnés. Un post de janvier qui décolle en juin met ses
            # likes de juin dans la barre de janvier.
            #
            # Il n'existe aucun flux mensuel à calculer, et c'est mesuré, pas supposé :
            # `instagram_media` porte **51 lignes pour 51 posts** — un instantané par
            # post, pas un historique — et `instagram_media_insights` est **vide**.
            # Fabriquer une courbe d'engagement mensuel demanderait d'inventer une
            # répartition que personne n'a mesurée.
            #
            # Le correctif est donc de NOMMER ce que la barre porte, comme pour Apple :
            # un chiffre juste sous un mauvais titre est un chiffre faux.
            df_eng = db.fetch_df(f"""
                SELECT month AS mois,
                       SUM(likes) AS likes,
                       SUM(comments) AS comments,
                       SUM(posts) AS posts
                FROM v_instagram_media_monthly
                WHERE artist_id = %s {frag_month}
                GROUP BY 1 ORDER BY 1
            """, (artist_id, *params_month))

            # ⚠️ LE SILENCE NOMME SA CAUSE — 2026-09-21, rapporté par l'artiste :
            # « pour engagement et publi je n'ai aucune data ». Le message disait
            # « Aucun post sur cette période » et s'arrêtait là. Mesuré : le
            # compte porte **51 publications**, la dernière du **07/11/2025**. Il
            # n'y a donc pas « aucun post » — il n'y en a aucun DANS CETTE
            # FENÊTRE, ce qui appelle un geste tout différent : élargir la
            # période, ou publier.
            if df_eng.empty:
                _dernier = db.fetch_df(
                    "SELECT MAX(timestamp) AS last, COUNT(*) AS n "
                    "FROM instagram_media WHERE artist_id = %s", (artist_id,))
                _last = None if _dernier.empty else _dernier.iloc[0]["last"]
                if _last is not None:
                    _jours = (pd.Timestamp.now() - pd.to_datetime(_last)).days
                    st.info(t(
                        "instagram.no_posts_in_window",
                        "Aucune publication dans cette fenêtre. Le compte en porte "
                        "**{n}** au total, la dernière du **{d}** — il y a "
                        "**{j} jours**. Élargis la période pour revoir "
                        "l'historique."
                    ).format(n=int(_dernier.iloc[0]["n"]),
                             d=format_date(pd.to_datetime(_last)), j=_jours))
                else:
                    st.info(t("instagram.no_posts",
                              "Aucune publication collectée pour ce compte."))
            else:
                df_eng['mois'] = pd.to_datetime(df_eng['mois'])
                # R290 (owner, fiche 15, 2026-09-28 : « l'ergonomie n'est pas ouf ») — the
                # decision is « publish MORE or publish BETTER »: bars = how many posts that
                # month (a volume, left), line = engagement PER POST (a ratio, right). Two
                # natures, declared in the visual-rules gate; likes and comments stay in
                # the hover, where the per-post ratio comes from.
                from plotly.subplots import make_subplots

                from src.dashboard.utils.ratios import per_series
                df_eng['per_post'] = per_series(df_eng['likes'] + df_eng['comments'],
                                                df_eng['posts'])
                fig_e = make_subplots(specs=[[{"secondary_y": True}]])
                fig_e.add_trace(go.Bar(
                    x=df_eng['mois'], y=df_eng['posts'], marker_color=_IG, opacity=0.35,
                    name=t("instagram.posts_per_month", "Publications du mois")),
                    secondary_y=False)
                fig_e.add_trace(go.Scatter(
                    # POINTS, not a line: a month without a post has no engagement per
                    # post, and a line would draw one through it.
                    x=df_eng['mois'], y=df_eng['per_post'], mode="markers+text",
                    marker=dict(color=_IG_DEEP, size=11),
                    text=[f"{v:.0f}" if pd.notna(v) else "" for v in df_eng['per_post']],
                    textposition="top center", textfont=dict(color=_IG_DEEP),
                    name=t("instagram.engagement_per_post", "Engagement par publication"),
                    customdata=df_eng[['likes', 'comments']].values,
                    hovertemplate="%{y:.0f} par publication<br>%{customdata[0]:,.0f} likes · "
                                  "%{customdata[1]:,.0f} commentaires<extra></extra>"),
                    secondary_y=True)
                fig_e.update_layout(
                    title=t("instagram.engagement_by_cohort",
                            "Likes et commentaires ACQUIS À CE JOUR, par mois de "
                            "publication ({label})").format(label=win_m.label),
                    hovermode="x unified",
                    legend=dict(orientation="h", y=-0.2, x=0))
                fig_e.update_yaxes(title_text=t("instagram.posts_axis", "Publications"),
                                   title_font_color=_IG, secondary_y=False,
                                   dtick=1, tickformat="d")
                fig_e.update_yaxes(title_text=t("instagram.per_post_axis",
                                                "Likes + commentaires par publication"),
                                   title_font_color=_IG_DEEP, rangemode="tozero",
                                   secondary_y=True)
                charts.plotly_chart(fig_e, width="stretch")
                st.caption(t(
                    "instagram.engagement_cohort_note",
                    "Chaque barre regroupe les posts **publiés** ce mois-là et montre "
                    "les likes qu'ils ont accumulés **jusqu'à aujourd'hui** — pas ceux "
                    "reçus pendant ce mois. Instagram ne nous donne qu'un compteur "
                    "courant par post : il n'y a pas d'historique d'où tirer un "
                    "engagement mensuel, et l'inventer serait pire que de ne pas le "
                    "montrer. Le filtre de période porte donc sur la date de "
                    "**publication**."))

                # Secondaire : dérivé des mêmes chiffres, sur une base indicative.
                with secondary_analyses(t("instagram.rate_expander",
                                          "📈 Taux d'engagement (indicatif)")):
                    # Taux d'engagement (indicatif — abonnés = snapshot actuel)
                    if followers:
                        # ⚠️ `pd.to_numeric` SUR LES TROIS COLONNES — vu au rendu
                        # le 2026-09-21 : « unsupported operand type(s) for /:
                        # 'decimal.Decimal' and 'float' ».
                        #
                        # `SUM(...)` en Postgres sur une colonne entière rend un
                        # NUMERIC, que psycopg2 traduit en `decimal.Decimal`. Un
                        # `Decimal` se divise par un `Decimal` sans broncher — et
                        # lève dès qu'on le divise par un `float`. La section
                        # entière tombait alors dans son `except` et l'artiste
                        # lisait « Erreur publications » à la place de ses
                        # publications.
                        #
                        # C'est la même classe que le `.round(1)` sur une colonne
                        # `object` déjà corrigé dans `soundcloud.py` : une colonne
                        # venue de SQL n'a pas le dtype qu'on croit, et on la
                        # coerce AVANT d'arithmétiser.
                        dfr = df_eng.copy()
                        _l = pd.to_numeric(dfr['likes'], errors='coerce')
                        _c = pd.to_numeric(dfr['comments'], errors='coerce')
                        _p = pd.to_numeric(dfr['posts'], errors='coerce')
                        dfr['taux'] = (
                            (_l + _c) / _p.where(_p != 0) / float(followers) * 100
                        ).round(2)
                        fig_r = px.line(
                            dfr, x='mois', y='taux', markers=True,
                            title=t("instagram.engagement_rate_title",
                                    "Taux d'engagement ≈ (eng. moyen/post) ÷ abonnés — indicatif"),
                            color_discrete_sequence=[_IG],
                            labels={'mois': t("common.month", "Mois")},
                        )
                        fig_r.update_layout(
                            hovermode="x unified", yaxis_title=t("instagram.rate_axis", "Taux (%)"),
                        )
                        charts.plotly_chart(fig_r, width="stretch")
                        st.caption(t(
                            "instagram.rate_caption",
                            "Indicatif : abonnés = dernier snapshot (historique "
                            "d'abonnés peu dense vs étendue des posts)."
                        ))

            # Publications récentes — insights indispo ⇒ note + colonnes masquées
            st.markdown(t("instagram.recent_posts", "#### Publications récentes"))
            _ins = db.fetch_query(
                "SELECT COUNT(*) FROM instagram_media_insights WHERE artist_id = %s",
                (artist_id,),
            )
            insights_empty = not _ins or (_ins[0][0] or 0) == 0

            base_cfg = {
                "media_url": st.column_config.ImageColumn(t("instagram.col_preview", "Aperçu")),
                "permalink": st.column_config.LinkColumn(
                    t("instagram.col_link", "Lien"),
                    display_text=t("instagram.col_open", "Ouvrir")),
                "caption": st.column_config.TextColumn(t("instagram.col_caption", "Légende"), width="medium"),
                "timestamp": st.column_config.DatetimeColumn(
                    t("instagram.col_published", "Publié le"), format="DD/MM/YYYY"),
                "like_count": "❤️ Likes",
                "comments_count": t("instagram.col_comments", "💬 Comm."),
            }

            if insights_empty:
                # R273 (2026-09-27) — ce message affirmait « Meta ne les sert que pour
                # les posts de moins de 90 jours ; ce n'est pas un défaut de collecte ».
                # C'en était un : la collecte demandait `impressions`, retirée par Meta
                # le 2025-04-21, et une seule métrique retirée fait refuser TOUTE la
                # requête — 51 publications sur 51, en local comme en production. La
                # collecte demande désormais `views`/`total_interactions`, et lève si
                # toutes les publications sont refusées : le silence ne dit plus rien.
                st.info(t(
                    "instagram.insights_pending",
                    "**Vues, portée, interactions, enregistrements et partages par "
                    "publication** ne sont pas encore collectés. Ils arrivent avec la "
                    "prochaine collecte Instagram ; si Meta les refuse, la collecte "
                    "échoue et l'administrateur est prévenu."))
                q_media = f"""
                    SELECT media_url, caption, media_type, permalink,
                           timestamp, like_count, comments_count
                    FROM instagram_media
                    WHERE artist_id = %s {frag_m}
                    ORDER BY timestamp DESC
                """
                cfg = base_cfg
            else:
                q_media = f"""
                    SELECT m.media_url, m.caption, m.media_type, m.permalink,
                           m.timestamp, m.like_count, m.comments_count,
                           i.impressions, i.reach, i.engagement, i.saved, i.shares
                    FROM instagram_media m
                    LEFT JOIN LATERAL (
                        SELECT impressions, reach, engagement, saved, shares
                        FROM instagram_media_insights ii
                        WHERE ii.artist_id = m.artist_id
                          AND ii.media_id = m.media_id
                        ORDER BY ii.date DESC LIMIT 1
                    ) i ON TRUE
                    WHERE m.artist_id = %s {frag_m}
                    ORDER BY m.timestamp DESC
                """
                # `impressions` carries Meta's `views`, `engagement` its
                # `total_interactions` since R273 — the labels say what the numbers are.
                cfg = {**base_cfg,
                       "impressions": t("instagram.col_views", "👁️ Vues"),
                       "reach": t("instagram.col_reach", "Portée"),
                       "engagement": t("instagram.col_interactions", "Interactions"),
                       "saved": t("instagram.col_saved", "Enregistrés"),
                       "shares": t("instagram.col_shares", "Partages")}

            df_media = db.fetch_df(q_media, (artist_id, *params_m))
            if not show_empty_state(
                df_media, t("instagram.no_media", "Aucune publication collectée pour cette période.")
            ):
                st.dataframe(
                    df_media, width="stretch", hide_index=True,
                    column_config=cfg,
                )
        except Exception as e:
            st.error(t("instagram.media_error", "Erreur publications : {err}").format(err=e))

if __name__ == "__main__":
    show()


def _render_community(df_hist, window, last_date: str) -> None:
    """Abonnés, abonnements et publications — UN cadre, une horloge (R210, 2026-09-27).

    Le propriétaire, devant le dossier : « abonnés, abonnements et publications sur un
    même graphique ». La version d'avant empilait trois cadres, et pour une raison
    réelle : les NIVEAUX sont dans un rapport de 30 (1 522 / 621 / 51), donc sur un
    repère commun deux séries sont des lignes plates au fond. La base 100, qui résolvait
    ce rapport, a été refusée le 2026-09-21 : on y lit « 103 » au lieu d'un nombre.

    LA VARIATION DEPUIS LE PREMIER RELEVÉ résout les deux. Les trois séries partagent
    alors une unité — un compte gagné ou perdu — et des ordres de grandeur voisins
    (+12 abonnés, +3 abonnements, +2 publications). Chaque point garde sa VALEUR au
    survol. Aucun double axe : la règle du dépôt est constante là-dessus.
    """
    series = (
        ("followers_count", t("instagram.followers", "Abonnés"), "solid"),
        ("follows_count", t("instagram.follows", "Abonnements"), "dash"),
        ("media_count", t("instagram.publications", "Publications"), "dot"),
    )
    fig = go.Figure()
    for col, lbl, dash in series:
        values = pd.to_numeric(df_hist[col], errors="coerce")
        first = values.dropna().iloc[0] if values.notna().any() else None
        if first is None:
            continue
        fig.add_trace(go.Scatter(
            x=df_hist["collected_at"], y=values - first, mode="lines+markers",
            name=lbl, customdata=values, connectgaps=False,
            line=dict(color=_IG, width=2, dash=dash), marker=dict(size=6),
            hovertemplate=f"{lbl} : %{{customdata:,.0f}} (%{{y:+,.0f}})<extra></extra>"))
    fig.add_hline(y=0, line=dict(color="#888", width=1, dash="dot"))
    fig.update_layout(
        height=460, hovermode="x unified", margin=dict(t=70, b=80),
        legend=dict(orientation="h", yanchor="top", y=-0.15, x=0),
        yaxis_title=t("instagram.community_axis", "Gagnés depuis le premier relevé"),
        title_text=t("instagram.community_title",
                     "Ma communauté dans le temps ({label})").format(label=window.label))
    charts.plotly_chart(fig, width="stretch")

    # LA DATE DE COLLECTE EST ICI, plus dans une tuile : c'est une note de bas de
    # figure, pas un indicateur.
    gagnes = int(df_hist["followers_count"].iloc[-1] - df_hist["followers_count"].iloc[0])
    st.caption(t(
        "instagram.community_caption",
        "**{n} relevé(s)**, dernier le **{d}**. Sur la période : **{g:+d} abonné(s)**. "
        "Chaque cadre a sa propre échelle, resserrée sur ses valeurs — un axe ancré à "
        "zéro rendrait invisible un gain de trois abonnés sur mille cinq cents. Les "
        "trois courbes portent leurs VRAIES valeurs : rien n'est ramené à une base."
    ).format(n=len(df_hist), d=last_date, g=gagnes))
