"""SoundCloud — le catalogue dans le temps, et la collecte qui a menti.

Type: Feature
Uses: view_session, age_aligned (shared with Spotify), platform_colors, i18n
Depends on: v_soundcloud_catalog_daily / v_soundcloud_track_daily (132),
            v_soundcloud_track_latest (107), soundcloud_tracks_daily
Persists in: — (lecture seule)

LE « BUMP DU 1er JUIN », rapporté le 2026-09-21
------------------------------------------------
Il est réel, il est en base, et ce n'est pas une baisse d'audience :

    19 lignes à `playback_count = 0`, TOUTES datées du 2026-06-01,
    et aucune autre date sur tout l'historique.

Les 19 titres étaient présents ce jour-là, tous à zéro sur les quatre compteurs.
Une collecte a répondu faux et le zéro a été ÉCRIT. Sur des compteurs CUMULÉS, la
courbe plonge à zéro puis remonte : le « bump ».

La règle « un cumul qui redescend est une panne » existait déjà — en PANDAS, dans
une seule figure de cette page. La figure principale, les tuiles et le tableau ne
l'avaient pas. Elle vit maintenant dans la couche or (migration 132), donc pour
toutes les surfaces à la fois. Mesuré : **19 jours de collecte, 1 écarté**.

ET « LE MÊME COMPTE DE STREAM » N'EST PAS UN BUG
-------------------------------------------------
« Chokbar de bezed » porte **4 écoutes** et n'en gagne pas. Ce qui était un défaut,
c'est qu'il soit le titre sélectionné D'OFFICE : le sélecteur triait sur
`track_created_at`, la date d'upload SoundCloud, et ce titre est le plus récemment
uploadé du compte. La page s'ouvrait donc sur le titre le plus vide du catalogue —
4 écoutes, 0 like, 0 repost, 0 commentaire. R385 avait ouvert la comparaison à âge
égal sur les deux titres les plus ÉCOUTÉS ; depuis R460 (demande du propriétaire,
2026-10-07) elle s'ouvre sur les DEUX DERNIÈRES SORTIES — c'est la question qu'elle pose.

LE TOTAL DES QUATRE COMPTEURS SUR UN AXE TEMPOREL
---------------------------------------------------
Demandé le 2026-09-21, et il n'existait nulle part : la page ne savait montrer
qu'un TITRE à la fois. `v_soundcloud_catalog_daily` somme le catalogue par jour —
en prenant le DERNIER relevé de chaque titre dans la journée, parce que les titres
d'une même nuit ne sont pas écrits au même instant (317 horodatages pour 19 jours,
mesuré).
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from src.dashboard.utils import view_session, charts
from src.dashboard.utils.age_aligned import age_aligned_traces
from src.dashboard.utils.formats import num
from src.dashboard.utils.ui import secondary_analyses
from src.dashboard.utils.i18n import t
from src.dashboard.utils.release_picker import release_picker
from src.dashboard.utils.tz import to_local_datetime
from src.dashboard.utils.platform_colors import DISTINCT, PALETTE_LIGHT
from src.dashboard.views.soundcloud_claims import render_claimed_tracks
from src.dashboard.utils.date_format import format_date, format_serie

# L'orange MESURÉ de SoundCloud — pas `#FF5500`, la teinte de marque exacte, que
# le balayage du 2026-09-08 a refusée (ΔE 4,6 contre YouTube en deutéranopie).
# C'est la meilleure position DANS la famille orange, pas une autre couleur.
_SC = PALETTE_LIGHT["soundcloud"]
_ENGAGEMENT_INK = DISTINCT[0]   # R290 — the engagement axis, apart from the plays area


def show():
    # ⚠️ NI TITRE NI SOUS-TITRE — retirés le 2026-09-21, même geste que sur Apple
    # et YouTube : « ☁️ SoundCloud - Performance » répétait l'entrée de menu qu'on
    # vient de cliquer.

    with view_session() as (db, artist_id):
        # =========================================================================
        # 1. KPIs GLOBAUX (Dernière date connue)
        # =========================================================================
        try:
            # Les quatre tuiles ci-dessous somment ces lignes EN PANDAS. Aucun garde
            # SQL ne peut les voir — il n'y a pas de `SUM(` dans la requête — et le
            # `DISTINCT ON (track_id)` qui vivait ici oubliait le locataire : deux
            # artistes qui repostent le même titre n'en gardaient qu'un.
            # `v_soundcloud_track_latest` (migration 107) porte la règle, locataire
            # compris, et c'est la même que celle des totaux de l'accueil.
            df_latest = db.fetch_df("""
                SELECT track_id, title, permalink_url, playback_count,
                       likes_count, reposts_count, comment_count,
                       track_created_at, collected_at
                FROM v_soundcloud_track_latest
                WHERE artist_id = %s
                ORDER BY track_id
            """, (artist_id,))

            if not df_latest.empty:
                # Enrichir avec first_seen pour tri "dernière release en premier"
                try:
                    df_first = db.fetch_df(      # R289 — gold (migration 144)
                        """SELECT track_id, first_seen
                           FROM v_soundcloud_track_latest WHERE artist_id = %s""",
                        (artist_id,),
                    )
                    df_latest = df_latest.merge(df_first, on="track_id", how="left")
                except Exception:
                    df_latest["first_seen"] = df_latest["collected_at"]

                # LES TUILES LISENT LE DERNIER JOUR **LISIBLE**, pas le dernier
                # relevé — corrigé le 2026-09-21, sur une mutation.
                #
                # `v_soundcloud_track_latest` ne porte aucun verdict : elle rend le
                # dernier relevé, quel qu'il soit. Mesuré en simulant une dernière
                # collecte ratée (19 lignes à zéro, transaction annulée) : les
                # quatre tuiles affichent **0** quand le dernier jour lisible vaut
                # **23 486**. Ce n'est pas arrivé à l'artiste — sa dernière
                # collecte est bonne — mais ça arrive le jour où la prochaine rate,
                # et rien ne l'aurait dit.
                #
                # Le repli sur les sommes du dernier relevé reste en place : une
                # base sans vue or (un déploiement en retard de migration) doit
                # afficher des chiffres, pas une page vide.
                _dernier = db.fetch_df("""
                    SELECT plays, likes, reposts, comments, tracks, day
                      FROM v_soundcloud_catalog_daily
                     WHERE artist_id = %s AND lisible
                     ORDER BY day DESC LIMIT 1
                """, (artist_id,))
                if not _dernier.empty:
                    _r = _dernier.iloc[0]
                    total_plays, total_likes = int(_r["plays"]), int(_r["likes"])
                    total_reposts, total_comments = int(_r["reposts"]), int(_r["comments"])
                    total_tracks = int(_r["tracks"])
                else:
                    total_plays = df_latest['playback_count'].sum()
                    total_likes = df_latest['likes_count'].sum()
                    total_reposts = df_latest['reposts_count'].sum()
                    total_comments = df_latest['comment_count'].sum()
                    total_tracks = len(df_latest)

                # Récupération de la dernière date de collecte
                # timestamptz across a DST change → mixed offsets (utils/tz.py).
                last_date_str = format_date(to_local_datetime(df_latest['collected_at']).max())

                # ⚠️ QUATRE TUILES, PAS SIX — 2026-09-21, à la demande du
                # propriétaire. « 🎵 Titres en ligne » et « 📅 Dernière mise à
                # jour » ne décident rien : le nombre de titres se lit dans le
                # classement juste en dessous, et une date de collecte est un
                # fait de PLOMBERIE. Elle descend dans la légende.
                # R385 (V42) : les quatre sur UNE ligne — elles étaient sur deux.
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(t("soundcloud.kpi_plays", "🎧 Total Écoutes"), f"{int(total_plays):,}")
                c2.metric(t("soundcloud.kpi_likes", "❤️ Total Likes"), f"{int(total_likes):,}")
                c3.metric(t("soundcloud.kpi_reposts", "🔄 Total Reposts"), f"{int(total_reposts):,}")
                c4.metric(t("soundcloud.kpi_comments", "💬 Total Commentaires"),
                          f"{int(total_comments):,}")

                st.caption(t(
                    "soundcloud.likes_caption",
                    "ℹ️ **{n} titres**, dernier relevé le **{d}**. Likes et "
                    "historique fiables depuis le 15/05/2026 (collecte OAuth "
                    "user-token). Sources CSV S4A/Apple non liées — autre sujet."
                ).format(n=total_tracks, d=last_date_str))

            else:
                st.warning(t("soundcloud.no_data", "Aucune donnée SoundCloud trouvée. Lancez le collecteur."))
                # Un profil vide n'est pas toujours une panne : pour un artiste
                # signé sur un label, il l'est par construction et le restera. Le
                # panneau de déclaration est donc rendu ICI aussi, avant le
                # `return` — sinon la seule page où il compte vraiment est celle
                # qui n'y arrive jamais.
                st.caption(t(
                    "soundcloud.no_data_claim_hint",
                    "Tes sorties paraissent sous le compte d'un label ou d'un "
                    "collectif ? Déclare-les ci-dessous : on collectera leurs "
                    "écoutes même hébergées ailleurs."))
                render_claimed_tracks(db, artist_id)
                return

        except Exception as e:
            st.error(t("soundcloud.sql_error_kpi", "Erreur SQL (KPIs) : {err}").format(err=e))
            return

        st.markdown("---")

        # R385 (V46) : peu de figures, la plus utile en haut — comparer les sorties,
        # puis les comparer à âge égal, puis le catalogue dans le temps.
        # =========================================================================
        # 1. LES SORTIES COMPARÉES SUR LES QUATRE COMPTEURS (V43, V45)
        # =========================================================================
        st.subheader(t("soundcloud.top_tracks", "🏆 Mes titres comparés"))
        df_top = _with_engagement(df_latest)
        _metrics = _metric_labels()
        sort_by = st.segmented_control(
            t("soundcloud.sort_by", "Comparer sur"), list(_metrics.values()),
            default=_metrics["playback_count"], key="sc_sort",
        ) or _metrics["playback_count"]
        sort_col = next(c for c, lbl in _metrics.items() if lbl == sort_by)
        df_top = df_top.sort_values(by=sort_col, ascending=False)
        _render_top_chart(df_top, sort_col, sort_by, _metrics["playback_count"])

        st.markdown("---")

        # =========================================================================
        # 2. TOUT LE CATALOGUE, À ÂGE ÉGAL (V44)
        # =========================================================================
        _render_age_comparison(db, artist_id, df_top)

        st.markdown("---")

        # =========================================================================
        # 3. LE CATALOGUE DANS LE TEMPS — les quatre compteurs, une horloge
        # =========================================================================
        _render_catalog_series(db, artist_id)

        # Les titres sortis sous le compte d'un label ou d'un collectif — déclarés
        # ICI depuis le 2026-09-04, et plus dans Credentials. C'est en lisant ce
        # tableau qu'on s'aperçoit qu'une sortie manque ; c'est donc ici qu'on la
        # réclame. Replié : le cas ne concerne pas la majorité.
        st.markdown("---")
        render_claimed_tracks(db, artist_id)


if __name__ == "__main__":
    show()


def _metric_labels() -> dict[str, str]:
    """{column of `v_soundcloud_track_latest`: label} — the four counters, in order."""
    return {"playback_count": t("soundcloud.plays", "Écoutes"),
            "likes_count": t("soundcloud.likes", "Likes"),
            "reposts_count": t("soundcloud.reposts", "Reposts"),
            "comment_count": t("soundcloud.comments", "Commentaires")}


# The same counters in `v_soundcloud_track_daily`, with the flag that says a reading
# of THAT counter is readable (migration 138).
_DAILY = {"playback_count": ("plays", "lisible"),
          "likes_count": ("likes", "likes_lisibles"),
          "reposts_count": ("reposts", "reposts_lisibles"),
          "comment_count": ("comments", "comments_lisibles")}


def _with_engagement(df_latest: pd.DataFrame) -> pd.DataFrame:
    """The latest counters, numeric, plus the engagement rate (%) and the age in days."""
    df = df_latest.copy()
    # Coerce to numeric first: a NULL in any count makes the column object dtype,
    # so the raw arithmetic + .round(1) raised "Expected numeric dtype, got object".
    for col in _DAILY:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    eng = df["likes_count"] + df["reposts_count"] + df["comment_count"]
    plays = df["playback_count"]
    df["eng_rate"] = (eng / plays.where(plays != 0) * 100).round(1)
    df["days_since"] = (pd.Timestamp.now()
                        - pd.to_datetime(df["track_created_at"])).dt.days
    return df


def _age_frame(db, artist_id, chosen: pd.DataFrame, metric: str) -> pd.DataFrame:
    """(title, age, value): each chosen title's READABLE readings of `metric`, placed
    at the title's age in days since upload. Pure past the one read."""
    col, flag = _DAILY[metric]
    df = db.fetch_df("""
        SELECT track_id, day, plays, likes, reposts, comments,
               lisible, likes_lisibles, reposts_lisibles, comments_lisibles
          FROM v_soundcloud_track_daily
         WHERE artist_id = %s AND track_id = ANY(%s)
         ORDER BY track_id, day
    """, (artist_id, [str(x) for x in chosen["track_id"]]))
    return age_aligned_readings(df, chosen, col, flag)


def age_aligned_readings(daily: pd.DataFrame, chosen: pd.DataFrame, col: str,
                         flag: str) -> pd.DataFrame:
    """Pure: the readings of `col` that are readable, with `age` = days since upload,
    in the order of `chosen` (so colours and legend follow the picker).

    No reading is invented: SoundCloud only gives today's counter, so a curve starts
    at the title's age on its first COLLECTED day — never at a made-up (0, 0)."""
    if daily.empty:
        return pd.DataFrame(columns=["title", "day", "age", "value"])
    ok = daily[daily["lisible"].fillna(False).astype(bool)
               & daily[flag].fillna(True).astype(bool)]
    meta = chosen[["track_id", "title", "track_created_at"]].astype({"track_id": str})
    out = ok.astype({"track_id": str}).merge(meta, on="track_id", validate="many_to_one")
    upload = pd.to_datetime(out["track_created_at"]).dt.normalize()
    out["age"] = (pd.to_datetime(out["day"]) - upload).dt.days
    out["value"] = pd.to_numeric(out[col], errors="coerce")
    order = {title: i for i, title in enumerate(chosen["title"])}
    out = out.dropna(subset=["value", "age"]).assign(_o=out["title"].map(order))
    return out.sort_values(["_o", "age"])[["title", "day", "age", "value"]]


def latest_first(df: pd.DataFrame) -> pd.DataFrame:
    """Titles newest release first — the upload date, then plays to break ties."""
    return df.sort_values(["track_created_at", "playback_count"],
                          ascending=[False, False], na_position="last")


def _render_age_comparison(db, artist_id, df_top: pd.DataFrame) -> None:
    """Choose titles, compare their cumulative counter at EQUAL AGE (R385, V44).

    The drawing is Spotify's « Mes sorties, à âge égal » — the same function,
    `age_aligned_traces`, not a copy. The default is the two LATEST releases (R460,
    owner, 2026-10-07: « d'office les deux dernières sorties »), which reverses R385's
    most-played default: the question this chart answers is « how is my new release
    doing against the previous one ».
    """
    st.subheader(t("soundcloud.age_header", "📈 Tout le catalogue, à âge égal"))
    by_release = latest_first(df_top)
    titles = by_release["title"].tolist()
    metrics = _metric_labels()
    c1, c2 = st.columns([3, 1])
    picked = release_picker(t("soundcloud.age_pick", "Titres à comparer"), titles,
                            key=f"sc_age_pick_{artist_id}", container=c1)
    metric_lbl = c2.selectbox(t("soundcloud.age_metric", "Compteur"),
                              list(metrics.values()), key=f"sc_age_metric_{artist_id}")
    metric = next(c for c, lbl in metrics.items() if lbl == metric_lbl)
    if not picked:
        st.info(t("soundcloud.age_pick_one", "Choisis au moins un titre."))
        return
    chosen = by_release.set_index("title").loc[picked].reset_index()
    frame = _age_frame(db, artist_id, chosen, metric)
    if frame.empty:
        st.info(t("soundcloud.age_empty",
                  "Aucun relevé lisible de ce compteur pour ces titres."))
        return
    colour = dict(zip(picked, _nuances(len(picked))))
    fig = go.Figure(age_aligned_traces(frame, x="age", y="value", series="title",
                                       colour=colour, markers=True))
    fig.update_layout(height=420, margin=dict(r=90, t=30),
                      legend=dict(orientation="h", y=-0.2, x=0),
                      xaxis_title=t("soundcloud.age_axis", "Jours depuis la mise en ligne"),
                      yaxis_title=t("soundcloud.age_value_axis", "{m} cumulés")
                      .format(m=metric_lbl))
    fig.update_yaxes(tickformat="~s", rangemode="tozero")
    charts.plotly_chart(fig, width="stretch")
    st.caption(t("soundcloud.age_caption",
                 "SoundCloud ne donne que le compteur du jour : chaque courbe commence à "
                 "l'âge qu'avait le titre au premier relevé collecté, pas à sa mise en "
                 "ligne. Deux titres se comparent là où leurs courbes se recouvrent."))


def _render_catalog_series(db, artist_id) -> None:
    """Les quatre compteurs du CATALOGUE sur un axe de temps.

    Demandé le 2026-09-21 — « il n'y a pas un moyen pour mettre le total écoute
    like repost & commentaire sur un axe temporel ? » — et la réponse est oui : la
    donnée existe depuis toujours, la page ne savait montrer qu'un TITRE à la fois.

    DEUX CADRES, PAS UN. Les écoutes valent 23 486 quand les commentaires valent
    412 : sur un repère commun, trois des quatre courbes sont plates au fond. Un
    second axe superposé ferait pire — leur croisement serait un artefact de
    cadrage. Les petits multiples sont la seule alternative admise ici, et c'est
    la même décision que la figure de l'accueil.

    ⚠️ LES JOURS NON LISIBLES SONT ÉCARTÉS ET COMPTÉS. La vue or (migration 132)
    marque `lisible = FALSE` quand le cumul du catalogue redescend sous son
    maximum — une collecte ratée persistée, pas une baisse d'audience. Les taire
    serait inventer un zéro ; les tracer serait inventer une chute. On les écarte
    et on DIT combien, avec la date.
    """
    df = db.fetch_df("""
        SELECT day, tracks, plays, likes, reposts, comments, lisible,
               likes_lisibles, reposts_lisibles, comments_lisibles
          FROM v_soundcloud_catalog_daily
         WHERE artist_id = %s
         ORDER BY day
    """, (artist_id,))
    if df.empty:
        return

    st.subheader(t("soundcloud.catalog_header",
                   "📊 Tout le catalogue — écoutes, likes, reposts, commentaires"))

    ecartes = df[~df["lisible"]]
    ok = df[df["lisible"]]
    if ok.empty:
        st.info(t("soundcloud.catalog_unreadable",
                  "Aucun relevé lisible : tous les jours collectés portent un "
                  "cumul en recul, ce qui signale une collecte en panne."))
        return

    # R290 (owner, fiche 10, 2026-09-28 : « fusionne tout sur un même graphique, pas en
    # base 100 ») — ONE frame, two axes, declared in the visual-rules gate: the AUDIENCE
    # counter (plays, an area on the left) and the ENGAGEMENT counters (likes, reposts,
    # comments, lines on the right). Two natures and two magnitudes (23 486 plays against
    # 412 comments): on one axis three curves were flat at the bottom. The crossing of
    # the two families is an artefact of framing, and the right axis says so by its title.
    from plotly.subplots import make_subplots
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(
        x=ok["day"], y=ok["plays"], mode="lines+markers", marker=dict(size=4),
        name=t("soundcloud.plays", "Écoutes"),
        # Small markers: each is a READING. Between two of them (no reading from
        # December to April) the line is a join, not a measure.
        line=dict(color=_SC, width=3)), secondary_y=False)

    # UNE SEULE TEINTE, TROIS TRAITS. Les trois séries du bas sont de la même
    # plateforme : leur donner trois couleurs inventerait trois familles là où il
    # y en a une. Le trait distingue, et il survit à la deutéranopie.
    #
    # ⚠️ EACH SERIES KEEPS ONLY ITS OWN READABLE DAYS (migration 138). `lisible`
    # is decided on PLAYS: it said nothing about likes, and the panel drew the
    # likes of 2026-03-30 → 05-14, read as 0 before the OAuth switch, as a
    # collapse 1 333 → 0 → 1 309 that never happened.
    for col, lbl, dash, flag in (
        ("likes", t("soundcloud.likes", "Likes"), None, "likes_lisibles"),
        ("reposts", t("soundcloud.reposts", "Reposts"), "dash", "reposts_lisibles"),
        ("comments", t("soundcloud.comments", "Commentaires"), "dot",
         "comments_lisibles"),
    ):
        serie = ok[ok[flag].fillna(True).astype(bool)]
        fig.add_trace(go.Scatter(
            x=serie["day"], y=serie[col], mode="lines", name=lbl,
            line=dict(color=_ENGAGEMENT_INK, width=2, dash=dash)), secondary_y=True)

    fig.update_layout(height=460, hovermode="x unified",
                      legend=dict(orientation="h", y=-0.15, x=0),
                      margin=dict(t=30))
    fig.update_yaxes(tickformat="~s", secondary_y=False,
                     title_text=t("soundcloud.plays_axis", "Écoutes cumulées"),
                     title_font_color=_SC)
    fig.update_yaxes(tickformat="~s", secondary_y=True,
                     title_text=t("soundcloud.engagement_axis",
                                  "Likes, reposts, commentaires (cumul)"),
                     title_font_color=_ENGAGEMENT_INK)
    charts.plotly_chart(fig, width="stretch")

    legende = t("soundcloud.catalog_caption",
                "**{n} relevé(s)** sur {t} titre(s). Ces compteurs sont des CUMULS "
                "à vie : la courbe monte ou reste plate, elle ne redescend jamais.")\
        .format(n=len(ok), t=int(ok.iloc[-1]["tracks"]))
    if not ecartes.empty:
        legende += " " + t(
            "soundcloud.catalog_dropped",
            "⚠️ **{k} jour(s) écarté(s)** ({d}) : le cumul y redescendait sous son "
            "maximum — une collecte qui a répondu faux, pas une perte d'audience. "
            "Les tracer dessinerait une chute qui n'a pas eu lieu.").format(
                k=len(ecartes),
                d=", ".join(format_serie(pd.to_datetime(ecartes["day"]))))
    _likes_ko = ok[~ok["likes_lisibles"].fillna(True).astype(bool)]
    if not _likes_ko.empty:
        legende += " " + t(
            "soundcloud.catalog_likes_dropped",
            "⚠️ **{k} jour(s) sans likes lisibles** : un titre au moins y lisait 0 "
            "like après en avoir compté — une lecture ratée, pas des likes "
            "retirés. La courbe des likes les saute.").format(k=len(_likes_ko))
    st.caption(legende)


def _render_top_chart(df_top, sort_col: str, sort_by: str, plays_lbl: str) -> None:
    """Le classement des titres, en FIGURE — demandé le 2026-09-21.

    Le tableau de sept colonnes était exact et ne se lisait pas : pour savoir quel
    titre sur-performe, il fallait comparer mentalement une colonne d'écoutes en
    milliers à un taux d'engagement en pourcents, ligne à ligne, sur dix-neuf
    lignes.

    DEUX CADRES QUI RÉPONDENT À DEUX QUESTIONS :

      · à gauche, le VOLUME — barres horizontales, la longueur se compare d'un
        coup d'œil et le tri suit le sélecteur ;
      · à droite, le TAUX d'engagement — parce qu'un titre peu écouté mais très
        réagi est précisément ce qu'un classement par volume enterre. Mesuré sur
        ce catalogue : le titre le plus écouté (3 794 écoutes) engage à 8,1 %
        quand un autre à 1 389 écoutes engage à 16,8 % — deux fois mieux, et
        invisible dans un tri par écoutes.

    UNE SEULE TEINTE. Les deux cadres parlent de la même plateforme ; leur donner
    deux couleurs inventerait deux familles. L'intensité porte la valeur.
    """
    n = min(len(df_top), 15)
    d = df_top.head(n).iloc[::-1]      # plotly empile de bas en haut

    from plotly.subplots import make_subplots
    fig = make_subplots(
        rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.04,
        subplot_titles=[
            t("soundcloud.top_volume", "Volume — {m}").format(m=sort_by),
            t("soundcloud.top_rate", "Taux d'engagement (%)")])

    _valeurs = pd.to_numeric(d[sort_col], errors="coerce").fillna(0)
    fig.add_trace(go.Bar(
        y=d["title"], x=_valeurs, orientation="h", name=sort_by,
        marker_color=_SC, opacity=0.9,
        text=[num(int(v), 0) for v in _valeurs],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>%{x:,.0f}<extra></extra>"), row=1, col=1)

    _taux = pd.to_numeric(d["eng_rate"], errors="coerce")
    fig.add_trace(go.Bar(
        y=d["title"], x=_taux, orientation="h",
        name=t("soundcloud.eng_rate", "Engagement %"),
        marker_color=_SC, opacity=0.45,
        text=[("—" if pd.isna(v) else f"{v:.1f} %") for v in _taux],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>%{x:.1f} %<extra></extra>"), row=1, col=2)

    fig.update_layout(
        height=max(380, 34 * n), showlegend=False, bargap=0.25,
        margin=dict(l=10, r=70, t=70),
        yaxis=dict(automargin=True))
    charts.plotly_chart(fig, width="stretch")

    st.caption(t(
        "soundcloud.top_caption",
        "Les {n} premiers titres, triés par **{m}**. À droite, le **taux "
        "d'engagement** — (likes + reposts + commentaires) ÷ écoutes : c'est lui "
        "qui distingue un titre beaucoup diffusé d'un titre qui fait RÉAGIR, et "
        "un tri par volume l'enterre. Le détail chiffré reste dans le tiroir "
        "ci-dessous.").format(n=n, m=sort_by))

    # Le tableau n'est pas SUPPRIMÉ, il descend d'un cran : on y revient pour
    # chercher une valeur précise, pas pour comparer.
    with secondary_analyses(t("soundcloud.top_table", "🔢 Le détail chiffré")):
        st.dataframe(
            df_top[['title', 'playback_count', 'likes_count', 'reposts_count',
                    'comment_count', 'eng_rate', 'days_since']],
            column_config={
                "title": t("soundcloud.col_title", "Titre"),
                "playback_count": st.column_config.NumberColumn(plays_lbl, format="%d"),
                "likes_count": st.column_config.NumberColumn("❤️ Likes", format="%d"),
                "reposts_count": st.column_config.NumberColumn("🔄 Reposts", format="%d"),
                "comment_count": st.column_config.NumberColumn(
                    t("soundcloud.col_comments", "💬 Coms"), format="%d"),
                "eng_rate": st.column_config.NumberColumn(
                    t("soundcloud.col_eng_rate", "💯 Engagement %"), format="%.1f"),
                "days_since": st.column_config.NumberColumn(
                    t("soundcloud.col_days_since", "📅 Sorti il y a (j)"), format="%d"),
            },
            hide_index=True, width="stretch")


def _nuances(n: int) -> list[str]:
    """`n` nuances de l'orange SoundCloud, de la plus sombre à la plus claire.

    Les séries d'une même plateforme se distinguent par la CLARTÉ, pas par la
    teinte : c'est la règle que `platform_colors` applique entre plateformes, et
    elle vaut à l'intérieur de l'une. Un écart de clarté survit à la
    deutéranopie ; un écart de teinte dans l'arc chaud n'y survit pas — c'est la
    mesure du 2026-09-08 (ΔE 4,6 entre les teintes de marque).

    La bande est volontairement étroite (0,35 → 0,80 de mélange vers le blanc) :
    au-delà, les dernières séries deviennent illisibles sur un fond clair.
    """
    import colorsys
    r, g, b = (int(_SC.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, li, sa = colorsys.rgb_to_hls(r, g, b)
    if n <= 1:
        return [_SC]
    out = []
    for i in range(n):
        # De `li` (la clarté mesurée) vers 0,80, réparti uniformément.
        clarte = li + (0.80 - li) * (i / (n - 1))
        rr, gg, bb = colorsys.hls_to_rgb(h, clarte, sa)
        out.append("#%02x%02x%02x" % (round(rr * 255), round(gg * 255), round(bb * 255)))
    return out
