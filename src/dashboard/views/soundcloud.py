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
from src.dashboard.utils.i18n import t
from src.dashboard.utils.release_picker import release_picker
from src.dashboard.utils.platform_colors import DISTINCT, PALETTE_LIGHT
from src.dashboard.views.soundcloud_claims import render_claimed_tracks
from src.dashboard.utils.date_format import format_serie

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
                else:
                    total_plays = df_latest['playback_count'].sum()
                    total_likes = df_latest['likes_count'].sum()
                    total_reposts = df_latest['reposts_count'].sum()
                    total_comments = df_latest['comment_count'].sum()

                # R486 (W9, 2026-10-09) : « les totaux du haut se retrouvent dans les
                # graphiques (on gagne une ligne) » — the four tiles and their caption
                # are gone ; the totals ride in the figure titles below.
                totals = {"playback_count": int(total_plays), "likes_count": int(total_likes),
                          "reposts_count": int(total_reposts),
                          "comment_count": int(total_comments)}

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

        # R385 (V46), R486 (W9) : the most useful first — every title on the five
        # counters, then the titles at equal age, then the catalogue in time.
        df_top = _with_engagement(df_latest).sort_values("playback_count", ascending=False)
        st.subheader(t("soundcloud.top_tracks", "🏆 Mes titres comparés"))
        charts.plotly_chart(top_figure(df_top, totals), width="stretch", decision=False)

        _render_age_comparison(db, artist_id, df_top)
        _render_catalog_series(db, artist_id, totals)

        # Les titres sortis sous le compte d'un label ou d'un collectif — déclarés
        # ICI depuis le 2026-09-04 : c'est en lisant le classement qu'on s'aperçoit
        # qu'une sortie manque.
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


_LABELLED_CURVES = 4   # past this, end labels collide (PNG read, R486)


def _render_age_comparison(db, artist_id, df_top: pd.DataFrame) -> None:
    """Choose titles, compare their cumulative counter at EQUAL AGE (R385, V44).

    The drawing is Spotify's « Mes sorties, à âge égal » — the same function,
    `age_aligned_traces`, not a copy. The default is the two LATEST releases (R460,
    owner, 2026-10-07: « d'office les deux dernières sorties »), which reverses R385's
    most-played default: the question this chart answers is « how is my new release
    doing against the previous one ».

    R486 (W9, 2026-10-09) : « n'a que deux titres → toutes les tracks ». The page has
    one catalogue and this chart is titled « tout le catalogue » : every title opens
    selected, newest first, through the same shared picker (n = all).
    """
    st.subheader(t("soundcloud.age_header", "📈 Tout le catalogue, à âge égal"))
    by_release = latest_first(df_top)
    titles = by_release["title"].tolist()
    metrics = _metric_labels()
    c1, c2 = st.columns([3, 1])
    picked = release_picker(t("soundcloud.age_pick", "Titres à comparer"), titles,
                            key=f"sc_age_pick_{artist_id}", n=len(titles), container=c1)
    metric_lbl = c2.selectbox(t("soundcloud.age_metric", "Compteur"),
                              list(metrics.values()), key=f"sc_age_metric_{artist_id}")
    metric = next(c for c, lbl in metrics.items() if lbl == metric_lbl)
    if not picked:
        return
    chosen = by_release.set_index("title").loc[picked].reset_index()
    frame = _age_frame(db, artist_id, chosen, metric)
    if frame.empty:
        st.info(t("soundcloud.age_empty",
                  "Aucun relevé lisible de ce compteur pour ces titres."))
        return
    colour = dict(zip(picked, _nuances(len(picked))))
    traces = age_aligned_traces(frame, x="age", y="value", series="title",
                                colour=colour, markers=True)
    crowded = len(traces) > _LABELLED_CURVES
    if crowded:
        # R486 : the whole catalogue is ~20 curves. End labels stack on each other and a
        # legend of twenty oranges maps nothing — the title rides in the hover instead,
        # and the shade still says recency (newest darkest).
        for tr in traces:
            tr.update(mode="lines+markers", text=None, showlegend=False,
                      hovertemplate=f"{tr.name}<br>%{{x}} j · %{{y:,.0f}}<extra></extra>")
    fig = go.Figure(traces)
    fig.update_layout(height=420, margin=dict(r=90, t=30),
                      legend=dict(orientation="h", y=-0.2, x=0),
                      xaxis_title=t("soundcloud.age_axis", "Jours depuis la mise en ligne"),
                      yaxis_title=t("soundcloud.age_value_axis", "{m} cumulés")
                      .format(m=metric_lbl))
    fig.update_yaxes(tickformat="~s", rangemode="tozero")
    charts.plotly_chart(fig, width="stretch", decision=False)


def _render_catalog_series(db, artist_id, totals: dict | None = None) -> None:
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
                      title=totals_line(totals) if totals else None,
                      legend=dict(orientation="h", y=-0.15, x=0),
                      margin=dict(t=60 if totals else 30))
    fig.update_yaxes(tickformat="~s", secondary_y=False,
                     title_text=t("soundcloud.plays_axis", "Écoutes cumulées"),
                     title_font_color=_SC)
    fig.update_yaxes(tickformat="~s", secondary_y=True,
                     title_text=t("soundcloud.engagement_axis",
                                  "Likes, reposts, commentaires (cumul)"),
                     title_font_color=_ENGAGEMENT_INK)
    charts.plotly_chart(fig, width="stretch", decision=False)

    # R486 (W9) : « retirer tout le blabla (… 129 relevés …) » — the reading count is
    # gone. What stays is CONDITIONAL and is not help text : a day dropped from the
    # curve is a measure withheld, and the page says which one (P2 over P3).
    legende = ""
    if not ecartes.empty:
        legende += t(
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
    if legende:
        st.caption(legende.strip())


_ORANGES = [[0.0, "#FFE0CC"], [1.0, _SC]]   # R486 (W9) — « dégradé orange »


def engagement_rate(totals: dict) -> float | None:
    """(likes + reposts + comments) / plays, in %. Pure. None without a play."""
    plays = totals.get("playback_count") or 0
    eng = sum(totals.get(c) or 0 for c in ("likes_count", "reposts_count", "comment_count"))
    return 100.0 * eng / plays if plays else None


def totals_line(totals: dict) -> str:
    """« Écoutes 23 486 · Likes 1 309 · … » — the four totals the tiles used to carry."""
    return "  ·  ".join(f"{lbl} {num(int(totals.get(col) or 0), 0)}"
                        for col, lbl in _metric_labels().items())


def top_figure(df_top: pd.DataFrame, totals: dict) -> go.Figure:
    """Every title on the five counters, one row each, side by side (R486, W9).

    « Plusieurs Pareto sur une même ligne : écoutes, engagement, likes, reposts,
    commentaires par track. » One panel per counter, the rows SHARED and ordered by
    plays — a title reads across the row, a counter reads down its panel. Each panel's
    title carries its total (the tiles that sat above are gone) ; the engagement panel
    carries its definition, which the owner asked to see explained.
    """
    from plotly.subplots import make_subplots

    d = df_top.sort_values("playback_count", ascending=False, kind="stable").iloc[::-1]
    labels = metric_labels = _metric_labels()
    rate = engagement_rate(totals)
    panels = [("playback_count", metric_labels["playback_count"],
               num(totals.get("playback_count") or 0, 0)),
              ("eng_rate", t("soundcloud.eng_rate", "Engagement %"),
               "—" if rate is None else f"{rate:.1f} %"),
              ("likes_count", labels["likes_count"], num(totals.get("likes_count") or 0, 0)),
              ("reposts_count", labels["reposts_count"],
               num(totals.get("reposts_count") or 0, 0)),
              ("comment_count", labels["comment_count"],
               num(totals.get("comment_count") or 0, 0))]
    fig = make_subplots(rows=1, cols=len(panels), shared_yaxes=True,
                        horizontal_spacing=0.025,
                        column_widths=[0.28, 0.24, 0.16, 0.16, 0.16],
                        subplot_titles=[f"{lbl}<br><b>{tot}</b>" for _, lbl, tot in panels])
    for i, (col, lbl, _) in enumerate(panels, start=1):
        v = pd.to_numeric(d[col], errors="coerce")
        is_rate = col == "eng_rate"
        fig.add_trace(go.Bar(
            y=d["title"], x=v.fillna(0), orientation="h", name=lbl,
            marker=dict(color=v.fillna(0), colorscale=_ORANGES),
            text=[("—" if pd.isna(x) else (f"{x:.1f}" if is_rate else num(int(x), 0)))
                  for x in v],
            textposition="outside", cliponaxis=False,
            hovertemplate="%{y}<br>%{x:,.1f} %<extra></extra>" if is_rate
            else "%{y}<br>%{x:,.0f}<extra></extra>"), row=1, col=i)
        top = float(v.max()) if v.notna().any() else 0.0
        fig.update_xaxes(range=[0, top * 1.35 or 1], showticklabels=False,
                         showgrid=False, row=1, col=i)
    fig.update_annotations(font_size=12)
    fig.update_layout(title=dict(text=t("soundcloud.eng_rate_def",
                                        "Engagement % = (likes + reposts + commentaires) "
                                        "÷ écoutes"), font_size=13),
                      height=150 + 26 * len(d), showlegend=False, bargap=0.25,
                      margin=dict(l=10, r=10, t=100, b=10), yaxis=dict(automargin=True))
    return fig


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
