"""Apple Music — ce que le catalogue a gagné, et sur combien de jours.

Type: Feature
Uses: view_session, entity_period_filter, platform_colors, i18n,
      utils.apple_launches (R351 — two releases aligned on J0)
Depends on: v_apple_song_cumulative / v_apple_song_daily (131),
            apple_songs_performance, gold_apple_lifetime (103/113/114),
            track_release_reference (release dates = J0)
Persists in: — (lecture seule)

LE DÉFAUT QUE CETTE PAGE PORTAIT, rapporté par l'artiste le 2026-09-21
------------------------------------------------------------------------
« J'avais pourtant download les derniers csv de apple music mais j'ai l'info
"Aucune mesure Apple Music sur cette période. La dernière remonte au
2025-12-11". » Il avait raison, et le message aussi : ils parlaient de DEUX
TABLES DIFFÉRENTES.

L'import CSV écrit `apple_songs_performance`. La croissance quotidienne lisait
`apple_songs_history`, que **rien n'écrit** — déclarée, autorisée, lue par trois
surfaces, alimentée par personne. Migration 131 les réunit dans
`v_apple_song_cumulative` ; les deux portent le même cumul, vérifié valeur par
valeur.

⚠️ ET UN SECOND DÉFAUT VIVAIT SOUS LE PREMIER. La requête gardait
`WHERE jours_ecoules = 1`, et son propre commentaire mesurait le résultat :
« 11 paires, 0 consécutive ». **Cent pour cent des points étaient écartés.** Même
alimentée, la figure n'aurait rien dessiné. Apple est nourri par un dépôt de CSV
à la main : deux relevés consécutifs n'existent essentiellement jamais, et
attendre un pas d'un jour revient à attendre une donnée que ce produit ne produit
pas.

CE QUI EST TRACÉ À LA PLACE, ET POURQUOI C'EST PLUS HONNÊTE
------------------------------------------------------------
Deux choses mesurées, aucune inférée :

  · le CUMUL (écoutes, Shazams) à chaque relevé — c'est ce qu'Apple rend, sans
    transformation ;
  · le GAIN entre deux relevés, en barres, avec le nombre de jours qu'il couvre
    écrit dessus. 36 écoutes gagnées sur 179 jours restent 36 écoutes gagnées ;
    les diviser par 179 pour obtenir « 0,2 par jour » inventerait une régularité
    que personne n'a mesurée.

La question « et sur combien de jours ? » devient donc une information de la
figure, au lieu d'être le motif qui faisait jeter la ligne.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from src.dashboard.utils import view_session, charts
from src.dashboard.utils.i18n import t
from src.dashboard.utils.release_picker import release_picker
from src.dashboard.utils.filters import EntitySpec, entity_period_filter
from src.dashboard.utils.ui import say_why_it_is_empty


# R289 — the latest level of each title, from the gold view, then the 10 MOST PLAYED. The
# raw query put `LIMIT 10` after `ORDER BY song_name` (DISTINCT ON needs it as the prefix):
# it showed the 10 alphabetically-first titles, not the top 10 (code-critic, 2026-09-28).
TOP_QUERY = """
                SELECT song_name, plays, shazam_count FROM (
                    SELECT DISTINCT ON (song_name) song_name, plays, shazam_count
                    FROM v_apple_song_cumulative
                    WHERE artist_id = %s
                    ORDER BY song_name, day DESC
                ) latest
                ORDER BY plays DESC NULLS LAST
                LIMIT 10
            """

def show():
    """Affiche la vue Apple Music."""
    # ⚠️ NI TITRE NI SOUS-TITRE — retirés le 2026-09-21 à la demande du
    # propriétaire. « 🍎 Apple Music Analytics » répétait l'entrée de menu qui
    # vient d'être cliquée, et « Analyse des performances et croissance
    # quotidienne » décrivait la page au lieu de la commencer. La première chose
    # à l'écran est désormais un chiffre.

    with view_session() as (db, artist_id):
        try:
            # ============================================================
            # 1. KPIs GLOBAUX
            # ============================================================
            st.subheader(t("apple_music.overview", "📊 Vue d'ensemble"))

            # DEUX TUILES, PAS TROIS — « 🎵 Chansons Suivies » est partie le
            # 2026-09-21. Elle comptait les LIGNES d'`apple_songs_performance`,
            # donc un titre une fois par dépôt de CSV : le nombre grandissait à
            # chaque import sans qu'un titre soit ajouté. Et la question qu'elle
            # prétendait poser — « ai-je le bon nombre de titres ? » — n'a de
            # réponse que croisée avec les autres plateformes. Elle vit donc
            # désormais dans **🔗 Mapping cross-plateforme**, où la grille de
            # couverture la confronte au catalogue canonique, en vert et rouge.
            col2, col3 = st.columns(2)

            # LE TOTAL PASSE PAR LA RÈGLE COMMUNE, pas par un SUM nu.
            #
            # `SUM(plays)` sur toute la table était juste tant qu'un artiste n'avait
            # qu'UN relevé — ce que la clé lui imposait avant la migration 093. Depuis
            # qu'il peut déposer un export « depuis le début » ET un export par année,
            # la somme brute compte deux fois les années contenues dans le cumul. Cette
            # page affichait donc un total Apple différent de celui de l'accueil, pour
            # le même artiste au même instant.
            from src.dashboard.utils.platform_timeseries import (
                apple_lifetime_plays, apple_lifetime_shazams,
            )
            # Les DEUX métriques suivent la même règle à trois branches, et cette
            # page en portait une copie Python pour les Shazams. Elle lit désormais
            # la même porte que l'accueil et le PDF (migration 103).
            total_plays = apple_lifetime_plays(db, artist_id)
            total_shazams = apple_lifetime_shazams(db, artist_id)

            # `None` = pas de mesure, et une tuile doit le DIRE plutôt que d'écrire
            # « 0 ». Depuis le 2026-09-12 les portes distinguent les trois cas —
            # aucune ligne, mesuré à zéro, lecture échouée — et `f"{None:,}"` lève.
            # Un artiste sans import Apple lit « — », pas « 0 écoute ».
            _tile = lambda v: "—" if v is None else f"{v:,}"      # noqa: E731
            col2.metric(t("apple_music.kpi_streams", "▶️ Total Streams (Cumul)"),
                        _tile(total_plays))
            col3.metric(t("apple_music.kpi_shazams", "⚡ Total Shazams (Cumul)"),
                        _tile(total_shazams))

            st.markdown("---")

            # ============================================================
            # 2. TOP CHANSONS (Barres)
            # ============================================================
            st.subheader(t("apple_music.top_header", "🏆 Top Chansons (Cumulé)"))

            # UN TITRE, UNE LIGNE. Sans le relevé le plus récent, le classement
            # listait le même titre une fois par dépôt de CSV, et plaçait son export
            # « depuis le début » au-dessus de l'année d'un autre titre.
            top_query = TOP_QUERY
            df_top = db.fetch_df(top_query, (artist_id,))

            if not df_top.empty:
                fig = px.bar(
                    df_top,
                    x='plays',
                    y='song_name',
                    orientation='h',
                    text='plays',
                    # R209 — say what this is: a CUMULATIVE snapshot, not a period.
                    title=t("apple_music.top10_title",
                            "Top 10 — streams cumulés au dernier relevé"),
                    labels={'plays': t("common.streams", "Streams"), 'song_name': ''},
                    color='plays',
                    color_continuous_scale='Reds',
                    custom_data=['shazam_count'],
                )
                fig.update_traces(
                    texttemplate='%{text:,.0f}', textposition='outside',
                    hovertemplate=t("apple_music.top_hover",
                                    '%{y}<br>Streams : %{x:,.0f}<br>⚡ Shazams : %{customdata[0]:,.0f}<extra></extra>'),
                )
                # automargin: the titles were cut at the left edge (« en le français »).
                fig.update_layout(yaxis={'categoryorder': 'total ascending', 'automargin': True},
                                  height=500, margin=dict(l=10, r=40))
                # R383 (V37) : les Shazams étaient un tableau replié sous le graphique ;
                # ils sont un second graphique, à droite, dans l'ordre des écoutes —
                # un titre se lit sur la même ligne dans les deux cadres.
                col_streams, col_shazams = st.columns(2)
                with col_streams:
                    charts.plotly_chart(fig, width="stretch")
                with col_shazams:
                    charts.plotly_chart(_shazam_bar(df_top), width="stretch")

            st.markdown("---")

            # ============================================================
            # 3. DEUX SORTIES, UNE HORLOGE (R351)
            # ============================================================
            # Les sorties, la plus récente d'abord — UNE lecture, servie à la
            # comparaison ci-dessous ET à la présélection de la série d'un titre.
            launches = _launches(db, artist_id)
            _render_shazam_launches(db, artist_id, launches)

            st.markdown("---")

            # ============================================================
            # 4. GRAPHIQUE DYNAMIQUE (CALCUL DIFFÉRENTIEL)
            # ============================================================
            # « Quotidienne » est parti du titre le 2026-09-21 : les relevés Apple sont
            # espacés de 12 à 179 jours chez le locataire 1, et promettre un quotidien
            # qu'on ne mesure pas est ce qui a fait jeter 100 % des points.
            st.subheader(t("apple_music.daily_growth",
                           "📈 Écoutes & Shazams dans le temps"))

            # LA DERNIÈRE SORTIE, D'OFFICE — et elle lit la vue OR.
            #
            # La version d'avant interrogeait `apple_songs_history`, la table que
            # rien n'écrit : pour un artiste dont les seuls imports sont récents,
            # la liste était VIDE et aucune présélection n'avait lieu. Le défaut
            # de la page (mauvaise table) se propageait jusqu'à son confort.
            #
            # Apple n'expose pas de date de sortie : on passe par la référence
            # canonique (`track_release_reference`, nourrie par les dates S4A),
            # titre Apple → match_key → release_date, passée en `preferred_default`
            # (R478 : plus d'écriture directe en session, le filtre commun décide).

            selected_song, window = entity_period_filter(
                db,
                spec=EntitySpec("v_apple_song_cumulative", "song_name", "day",
                                multi=False, default_count=1),
                artist_id=artist_id, key_prefix="apple_daily",
                preferred_default=launches[0].song if launches else None,
                label=t("apple_music.song_select",
                        "🔍 Chanson (dernière sortie par défaut)"),
            )
            selected_songs = [selected_song] if selected_song else []

            if selected_songs:
                frag, frag_params = window.sql_between("day")
                df_daily = db.fetch_df(f"""
                    SELECT day, song_name, plays, shazam_count,
                           daily_plays, daily_shazams, days_since_previous
                      FROM v_apple_song_daily
                     WHERE artist_id = %s AND song_name = %s {frag}
                     ORDER BY day
                """, (artist_id, selected_songs[0], *frag_params))

                if not df_daily.empty:
                    _render_song_series(df_daily, selected_songs[0], window)
                else:
                    # DEUX SILENCES, DEUX GESTES OPPOSÉS. « Rien dans cette
                    # fenêtre » fait ÉLARGIR ; « aucun relevé » fait IMPORTER.
                    # Envoyer l'artiste chercher le mauvais geste est le coût réel
                    # de la confusion — et c'est exactement ce qui lui est arrivé
                    # le 2026-09-21, avec en plus une date qui venait d'une table
                    # morte. On relit donc la série SANS la fenêtre.
                    _hors = db.fetch_df(
                        "SELECT MAX(day) AS last FROM v_apple_song_cumulative "
                        "WHERE artist_id = %s AND song_name = %s",
                        (artist_id, selected_songs[0]))
                    _last = None if _hors.empty else _hors.iloc[0]["last"]
                    say_why_it_is_empty(
                        _last, window,
                        empty_window=t(
                            "apple_music.nothing_in_window",
                            "Aucun relevé Apple Music pour **{song}** sur cette "
                            "période. Le dernier date du **{last}** — élargis la "
                            "fenêtre, ou dépose un export plus récent."
                        ).format(song=selected_songs[0],
                                 last="—" if _last is None else _last),
                        no_history=t(
                            "apple_music.not_enough_history",
                            "📉 Un seul relevé pour ce titre : il faut deux dépôts "
                            "d'export pour mesurer un gain."))
            else:
                st.info(t("apple_music.select_prompt",
                          "👈 Sélectionnez une chanson — ou importez des CSV Apple Music plusieurs jours de suite."))

        except Exception as e:
            st.error(t("apple_music.error", "❌ Erreur : {err}").format(err=e))


if __name__ == "__main__":
    show()


def _shazam_bar(df_top):
    """Shazams of the top-10 titles, in the streams order of the chart beside it (R383)."""
    from src.dashboard.utils.platform_colors import PALETTE_LIGHT

    order = df_top.sort_values("plays")["song_name"].tolist()
    fig = px.bar(
        df_top, x="shazam_count", y="song_name", orientation="h", text="shazam_count",
        title=t("apple_music.shazams_title", "⚡ Shazams — mêmes titres, même ordre"),
        labels={"shazam_count": "Shazams", "song_name": ""},
        color_discrete_sequence=[PALETTE_LIGHT["apple"]],
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside",
                      hovertemplate=t("apple_music.shazams_hover",
                                      "%{y}<br>⚡ Shazams : %{x:,.0f}<extra></extra>"))
    fig.update_layout(yaxis={"categoryorder": "array", "categoryarray": order,
                             "automargin": True},
                      height=500, margin=dict(l=10, r=40))
    return fig


def _render_song_series(df, song: str, window) -> None:
    """Le cumul et le gain d'un titre — deux cadres, une horloge.

    DEUX CADRES ET NON DEUX AXES. Les Shazams se comptent en unités quand les
    écoutes se comptent en centaines : sur un repère commun la barre est
    invisible, sur un second axe son croisement avec la courbe est un artefact de
    cadrage et non un fait. La règle du dépôt est que deux séries d'ordres
    incomparables prennent deux petits multiples.

    ⚠️ LE GAIN PORTE SA DURÉE, écrite sur la barre. C'est la correction du
    2026-09-21 : la version d'avant écartait toute paire dont l'écart n'était pas
    d'UN jour — « 11 paires, 0 consécutive », donc zéro point dessiné. Un gain de
    36 écoutes sur 179 jours est un fait ; le diviser par 179 pour afficher « 0,2
    par jour » inventerait une régularité que personne n'a mesurée.
    """
    import pandas as pd
    from plotly.subplots import make_subplots

    from src.dashboard.utils.platform_colors import PALETTE_LIGHT

    apple = PALETTE_LIGHT["apple"]
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
        row_heights=[0.55, 0.45],
        subplot_titles=[
            t("apple_music.cumulative_panel", "Cumul à chaque relevé"),
            t("apple_music.gain_panel", "Gagné entre deux relevés")])

    fig.add_trace(go.Scatter(
        x=df["day"], y=df["plays"], mode="lines+markers",
        name=t("common.streams", "Écoutes"),
        line=dict(color=apple, width=2.5), marker=dict(size=7)), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df["day"], y=df["shazam_count"], mode="lines+markers",
        name=t("apple_music.shazams", "Shazams"),
        line=dict(color=apple, width=2, dash="dot"), marker=dict(size=6)), row=1, col=1)

    # L'étiquette DIT la durée : « +36 / 179 j ». Sans elle, deux barres de même
    # hauteur couvrant 12 et 179 jours se lisent comme deux faits comparables.
    gains = df[df["daily_plays"].notna()]
    etiquettes = [
        t("apple_music.gain_label", "+{n} / {d} j").format(
            n=int(g), d=int(j) if pd.notna(j) else "?")
        for g, j in zip(gains["daily_plays"], gains["days_since_previous"])]
    fig.add_trace(go.Bar(
        x=gains["day"], y=gains["daily_plays"],
        name=t("apple_music.gain_plays", "Écoutes gagnées"),
        marker_color=apple, opacity=0.85,
        text=etiquettes, textposition="outside", cliponaxis=False,
        customdata=gains["days_since_previous"],
        hovertemplate=t("apple_music.gain_hover",
                        "%{y:,.0f} écoute(s) gagnée(s) sur %{customdata} jour(s)"
                        "<extra></extra>")), row=2, col=1)
    fig.add_trace(go.Bar(
        x=gains["day"], y=gains["daily_shazams"],
        name=t("apple_music.gain_shazams", "Shazams gagnés"),
        marker_color=apple, opacity=0.4,
        hovertemplate=t("apple_music.gain_sh_hover",
                        "%{y:,.0f} Shazam(s) gagné(s)<extra></extra>")), row=2, col=1)

    fig.update_layout(
        height=620, hovermode="x unified", barmode="group",
        margin=dict(t=90),
        legend=dict(orientation="h", y=1.10),
        title_text=t("apple_music.series_title", "{song} · {label}")
        .format(song=song, label=window.label))
    charts.plotly_chart(fig, width="stretch")

    # CE QUE LA FIGURE NE DIT PAS, dit ici : sur quoi les gains sont étalés.
    if not gains.empty:
        jours = gains["days_since_previous"].dropna()
        st.caption(t("apple_music.series_caption",
                     "**{n} relevé(s)** sur la période. Un export Apple se dépose à "
                     "la main : les relevés ne sont pas quotidiens, et l'écart entre "
                     "deux va de **{mini} à {maxi} jours** ici. Chaque barre porte "
                     "donc sa durée — un gain n'est comparable à un autre qu'à durée "
                     "égale.")
                   .format(n=len(df), mini=int(jours.min()) if len(jours) else "—",
                           maxi=int(jours.max()) if len(jours) else "—"))


def _launches(db, artist_id: int) -> list:
    """The artist's dated Apple titles, newest release first (R351)."""
    from src.dashboard.utils.apple_launches import release_launches
    from src.utils.track_matching import get_release_dates

    rel_by_key = get_release_dates(db, artist_id)
    if not rel_by_key:
        return []
    songs = db.fetch_query(
        "SELECT DISTINCT song_name FROM v_apple_song_cumulative WHERE artist_id = %s",
        (artist_id,))
    return release_launches([sn for (sn,) in (songs or [])], rel_by_key)


def _render_shazam_launches(db, artist_id: int, launches: list) -> None:
    """Two releases, one clock: Shazams since J0 (R351)."""
    from src.dashboard.utils.apple_launches import align_on_j0
    from src.dashboard.utils.platform_timeseries import apple_launch_readings
    from src.dashboard.utils.date_format import format_date

    st.subheader(t("apple_music.launches_header",
                   "⚡ Shazams depuis la sortie — deux sorties comparées"))
    if not launches:
        st.info(t("apple_music.launches_none",
                  "Aucune date de sortie connue pour tes titres Apple Music : la "
                  "comparaison se cale sur le jour de sortie. Les dates viennent de "
                  "Spotify for Artists — relie tes titres dans **🔗 Mapping "
                  "cross-plateforme**."))
        return
    label = lambda lc: f"{lc.song} · {format_date(lc.j0)}"      # noqa: E731
    chosen = release_picker(t("apple_music.launch_pick", "Sorties à comparer"),
                            launches, key="apple_launch_pick", format_func=label)
    if not chosen:
        st.info(t("apple_music.launch_pick_none", "Choisis au moins une sortie."))
        return
    readings = apple_launch_readings(db, artist_id, [lc.song for lc in chosen])
    aligned = align_on_j0(readings, chosen)
    if not aligned["measured"].any():
        st.info(t("apple_music.launches_no_reading",
                  "Aucun relevé Apple Music couvrant ces titres depuis leur sortie : "
                  "dépose un export « depuis le début » pour les voir ici."))
        return
    charts.plotly_chart(_launches_figure(aligned, chosen), width="stretch")
    st.caption(t("apple_music.launches_caption",
                 "J0 = le jour de sortie de chaque titre, donc deux sorties d'années "
                 "différentes se lisent côte à côte. Chaque point est un relevé CUMULÉ : "
                 "les Shazams du titre depuis sa sortie. Le point creux à J0 vaut 0 par "
                 "construction (aucun Shazam avant la sortie). Entre deux relevés, le "
                 "trait relie deux mesures — ce n'est pas un rythme quotidien. Cette "
                 "figure ne suit pas le sélecteur de période plus bas."))
    if len(chosen) < 2:
        st.caption(t("apple_music.launches_single",
                     "Une seule sortie datée : il en faut deux pour comparer."))


def _launches_figure(aligned, chosen: list):
    """One line per release, x = days since J0, the J0 anchor drawn hollow."""
    from src.dashboard.utils.platform_colors import DISTINCT

    fig = go.Figure()
    for i, lc in enumerate(chosen):
        s = aligned[aligned["song"] == lc.song]
        color = DISTINCT[i % len(DISTINCT)]
        fig.add_trace(go.Scatter(
            x=s["offset"], y=s["shazams"], mode="lines+markers", name=lc.song[:40],
            line=dict(color=color, width=2.5),
            marker=dict(size=8, color=color,
                        symbol=["circle" if m else "circle-open" for m in s["measured"]]),
            hovertemplate=t("apple_music.launch_hover",
                            "J+%{x} · %{y:,.0f} Shazam(s) depuis la sortie"
                            "<extra></extra>")))
    fig.update_layout(
        height=420, hovermode="closest",
        xaxis_title=t("apple_music.launch_x", "Jours depuis la sortie (J0)"),
        yaxis_title=t("apple_music.launch_y", "Shazams cumulés depuis J0"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), margin=dict(t=60))
    return fig
