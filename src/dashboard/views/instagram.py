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
`instagram_media_insights` est **vide** (0 ligne, mesuré le 2026-09-21) : Meta ne
sert impressions/reach/saved/partages que pour des posts de moins de 90 jours,
avec le scope `instagram_manage_insights`. Le dernier post de ce compte date du
**07/11/2025**. Aucune recollecte ne les fera apparaître tant qu'il n'y a pas de
publication récente — et le dire ainsi vaut mieux que de renvoyer l'artiste vers
un bouton qui ne changera rien.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t
from src.dashboard.utils.period_filter import (
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

# Instagram n'a PAS de couleur mesurée : sept teintes attribuables sont impossibles
# dans cette palette (recherche conjointe du 2026-09-21, ΔE 9,6 en clair contre un
# plancher de 15 — la deutéranopie fait converger un cyan et un violet vers le même
# bleu). Le détail est dans `platform_colors`. Sa page n'affiche qu'UNE plateforme :
# la question de l'attribution ne s'y pose pas, et on garde donc sa teinte de marque.
_IG = "#E1306C"

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
            default_override="last_release",
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
            default_override="last_release",
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
                df_long = df_eng.melt(
                    id_vars=['mois', 'posts'], value_vars=['likes', 'comments'],
                    var_name='Type', value_name='Total',
                )
                fig_e = px.bar(
                    df_long, x='mois', y='Total', color='Type',
                    title=t("instagram.engagement_by_cohort",
                            "Likes et commentaires ACQUIS À CE JOUR, par mois de "
                            "publication ({label})").format(label=win_m.label),
                    hover_data=['posts'],
                    labels={'mois': t("instagram.month_published",
                                      "Mois de publication"),
                            'Total': t("common.total", "Total")},
                )
                fig_e.update_layout(
                    barmode='stack', hovermode="x unified",
                    yaxis_title=t("instagram.likes_comments_axis", "Likes + commentaires"),
                )
                st.plotly_chart(fig_e, width="stretch")
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
                            color_discrete_sequence=['#E1306C'],
                            labels={'mois': t("common.month", "Mois")},
                        )
                        fig_r.update_layout(
                            hovermode="x unified", yaxis_title=t("instagram.rate_axis", "Taux (%)"),
                        )
                        st.plotly_chart(fig_r, width="stretch")
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
                # ⚠️ CE MESSAGE ENVOYAIT VERS UN GESTE INUTILE. Il disait
                # « recollecte après une publication récente » — or une recollecte
                # ne peut RIEN changer tant qu'aucun post n'a moins de 90 jours,
                # et le dernier de ce compte date du 07/11/2025. Il nomme donc
                # maintenant la seule chose qui débloque : publier.
                _dp = db.fetch_df("SELECT MAX(timestamp) AS last FROM instagram_media "
                                  "WHERE artist_id = %s", (artist_id,))
                _dl = None if _dp.empty else _dp.iloc[0]["last"]
                _age = None if _dl is None else (pd.Timestamp.now() - pd.to_datetime(_dl)).days
                st.info(t(
                    "instagram.insights_unavailable",
                    "**Impressions, portée, enregistrements et partages ne sont "
                    "pas disponibles.** Meta ne les sert que pour les posts de "
                    "moins de **90 jours**, et ta publication la plus récente date "
                    "de **{j} jours**. Ce n'est pas un défaut de collecte : "
                    "relancer une collecte ne les fera pas apparaître. Ils "
                    "reviendront d'eux-mêmes après ta prochaine publication."
                ).format(j="—" if _age is None else _age)
                    if _age is not None and _age > 90 else t(
                    "instagram.insights_unavailable_scope",
                    "**Impressions, portée, enregistrements et partages ne sont "
                    "pas disponibles.** Meta les réserve aux posts de moins de "
                    "90 jours ET au scope `instagram_manage_insights` — vérifie "
                    "l'autorisation dans **🔑 Credentials**."))
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
                cfg = base_cfg

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
    """Abonnés, abonnements et publications — trois cadres, une horloge.

    REMPLACE DEUX FIGURES PAR UNE, et répond à la demande du 2026-09-21 : « si on
    peut mettre sur un axe temporel le nombre d'abonnés et d'abonnement et de
    publication », et « supprimer le graphique base 100 ».

    ⚠️ POURQUOI PAS UN SEUL CADRE. Les trois séries sont dans un rapport de 30
    (1 522 / 621 / 51) : sur un repère commun, les deux dernières sont deux lignes
    plates au fond du cadre. C'est exactement le problème que la base 100 résolvait
    — en payant les CHIFFRES, puisqu'on y lit « 103 » au lieu de « 1 525 abonnés ».
    Les petits multiples le résolvent sans rien normaliser : chaque série garde son
    échelle ET ses valeurs.

    ⚠️ ET POURQUOI PAS UN DOUBLE AXE. Trois séries, trois ordres de grandeur : un
    axe secondaire n'en sauverait qu'une, et leur croisement serait un artefact de
    cadrage. La règle du dépôt est constante là-dessus.

    L'AXE DE CHAQUE CADRE EST RESSERRÉ sur la plage réelle, pas ancré à zéro : à
    1 522 abonnés, une variation de 3 est invisible sur un axe qui part de 0 — et
    c'est pourtant toute l'information d'une semaine.
    """
    from plotly.subplots import make_subplots

    series = (
        ("followers_count", t("instagram.followers", "Abonnés"), _IG),
        ("follows_count", t("instagram.follows", "Abonnements"), _IG),
        ("media_count", t("instagram.publications", "Publications"), _IG),
    )
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.07,
                        subplot_titles=[lbl for _, lbl, _ in series])
    for i, (col, lbl, ink) in enumerate(series, start=1):
        fig.add_trace(go.Scatter(
            x=df_hist["collected_at"], y=df_hist[col], mode="lines+markers",
            name=lbl, line=dict(color=ink, width=2), marker=dict(size=6),
            hovertemplate=f"{lbl} : %{{y:,.0f}}<extra></extra>"), row=i, col=1)
        # L'axe suit la plage RÉELLE : à 1 522 abonnés, +3 est invisible depuis 0.
        vmin, vmax = float(df_hist[col].min()), float(df_hist[col].max())
        marge = max((vmax - vmin) * 0.15, 1)
        fig.update_yaxes(range=[vmin - marge, vmax + marge], row=i, col=1)

    fig.update_layout(
        height=640, hovermode="x unified", showlegend=False, margin=dict(t=90),
        title_text=t("instagram.community_title",
                     "Ma communauté dans le temps ({label})").format(label=window.label))
    st.plotly_chart(fig, width="stretch")

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
