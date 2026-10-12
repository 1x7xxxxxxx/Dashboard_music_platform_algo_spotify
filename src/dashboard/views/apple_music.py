"""Apple Music — ce que le catalogue a gagné, et sur combien de jours.

Type: Feature
Uses: view_session, platform_colors, i18n,
      utils.apple_launches (R351 — two releases aligned on J0)
Depends on: v_apple_song_cumulative (131),
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

R518 (2026-10-11, owner X7 II) : CETTE FIGURE EST RETIRÉE. Même devenue un rythme
par 30 jours (R484), elle ne menait à aucune décision. À la place, un classement :
« Shazams pour 1 000 écoutes », un titre par barre — le titre que les gens CHERCHENT
après l'avoir entendu est celui à pousser en pub. Cumul de vie, pas 30 jours : les
relevés Apple sont espacés de 12 à 179 jours, une fenêtre de 30 jours serait vide.

R546 (2026-10-12, note vocale du propriétaire) : « le titre à pousser » et « Shazam
gagnés par jour » sont retirés. Restent le top 10 en streams cumulés et ses Shazams.
"""
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from src.dashboard.utils import view_session, charts
from src.dashboard.utils.formats import num
from src.dashboard.utils.i18n import t
from src.dashboard.utils.release_picker import release_picker


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
            # R484 (owner W7 II : « total streams cumulés intégré au graphique top 10 ; total
            # Shazam intégré au graphique Shazam ; retirer la barre de séparation ») — the
            # two tiles and both separators are gone; the totals are the chart titles.
            from src.dashboard.utils.platform_timeseries import (
                apple_lifetime_plays, apple_lifetime_shazams,
            )
            # Les DEUX métriques suivent la même règle à trois branches, et cette
            # page en portait une copie Python pour les Shazams. Elle lit désormais
            # la même porte que l'accueil et le PDF (migration 103).
            total_plays = apple_lifetime_plays(db, artist_id)
            total_shazams = apple_lifetime_shazams(db, artist_id)

            # `None` = pas de mesure : the title says « — », never « 0 ». Since 2026-09-12 the
            # gates tell no row / measured zero / failed read apart, and `f"{None:,}"` raises.
            _total = lambda v: "—" if v is None else num(v, 0)      # noqa: E731

            # ============================================================
            # 2. TOP CHANSONS (Barres)
            # ============================================================
            # UN TITRE, UNE LIGNE. Sans le relevé le plus récent, le classement
            # listait le même titre une fois par dépôt de CSV, et plaçait son export
            # « depuis le début » au-dessus de l'année d'un autre titre.
            top_query = TOP_QUERY
            df_top = db.fetch_df(top_query, (artist_id,))

            if not df_top.empty:
                # R383 then R484 (W7 II) : the Shazams sit on the right of the top 10, in
                # ONE figure whose two panels share the titles — on two half-page charts
                # the names were written twice and took half of each frame.
                charts.plotly_chart(_top10_figure(df_top, _total(total_plays),
                                                  _total(total_shazams)), width="stretch")

            # R546 (owner, 2026-10-12) : « le titre à pousser » and « Shazam gagnés par jour »
            # are gone — the top 10 and its Shazams panel are the page.
            if df_top.empty:
                # No Apple reading at all: name the absence and the gesture, never a bare page.
                st.info(t("apple_music.no_data",
                          "Aucun relevé Apple Music pour l'instant : importe ton export "
                          "Apple Music for Artists depuis **Import CSV** pour voir tes "
                          "titres."))

        except Exception as e:
            st.error(t("apple_music.error", "❌ Erreur : {err}").format(err=e))


if __name__ == "__main__":
    show()


def _top10_figure(df_top, total_plays: str = "—", total_shazams: str = "—"):
    """Top 10 by cumulative streams, Shazams on the right on the same rows (R383, R484).

    One figure, two panels sharing the y axis: a title is written once and reads across
    both. Each total is the title of its panel (owner W7 II), the colour scale is gone —
    it repeated the bar length."""
    from plotly.subplots import make_subplots

    from src.dashboard.utils.platform_colors import PALETTE_LIGHT

    df = df_top.sort_values("plays")
    total_row = t("apple_music.total_row", "Total")
    fig = make_subplots(
        rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.06, column_widths=[0.6, 0.4],
        subplot_titles=(
            t("apple_music.top10_title", "Top 10 — streams cumulés"),
            t("apple_music.shazams_title", "⚡ Shazams")))
    fig.add_trace(go.Bar(
        y=df["song_name"], x=df["plays"], orientation="h", marker_color="#C62828",
        text=[num(v, 0) for v in df["plays"]], textposition="outside", cliponaxis=False,
        customdata=df[["shazam_count"]].values,
        hovertemplate=t("apple_music.top_hover",
                        "%{y}<br>Streams : %{x:,.0f}<br>⚡ Shazams : %{customdata[0]:,.0f}"
                        "<extra></extra>")), row=1, col=1)
    fig.add_trace(go.Bar(
        y=df["song_name"], x=df["shazam_count"], orientation="h",
        marker_color=PALETTE_LIGHT["apple"],
        text=[num(v, 0) for v in df["shazam_count"]], textposition="outside",
        cliponaxis=False,
        hovertemplate=t("apple_music.shazams_hover",
                        "%{y}<br>⚡ Shazams : %{x:,.0f}<extra></extra>")), row=1, col=2)
    # R534 (owner, 2026-10-12) : « Total » on the FIRST row, labelled, then the titles. A
    # text, not a bar: a bar ten times the longest title would crush the ten below it.
    for col, total in ((1, total_plays), (2, total_shazams)):
        fig.add_trace(go.Scatter(
            y=[total_row], x=[0], mode="text", text=[f"  <b>{total}</b>"],
            textposition="middle right", hoverinfo="skip"), row=1, col=col)
    for col, field in ((1, "plays"), (2, "shazam_count")):
        top = float(pd.to_numeric(df[field], errors="coerce").max() or 1)
        fig.update_xaxes(range=[0, top * 1.3], nticks=4, row=1, col=col)
    fig.update_yaxes(automargin=True, categoryorder="array",   # the titles were cut at the
                     categoryarray=[*df["song_name"], total_row])   # left edge; Total on top
    fig.update_layout(height=490, showlegend=False, margin=dict(l=10, r=30, t=60))
    return fig


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


def render_shazam_launches(db, artist_id: int) -> None:
    """Releases on one clock: Shazams since J0 (R351), Meta € per day on the right (R476).

    R476 (owner W7 : « ce graphique + dépenses Meta (comme Spotify) → vue croisée ») —
    rendered by the cross view's « Sorties » section only. The spend is drawn PER DAY,
    the R459 convention of the Spotify releases chart, so both read the same way.
    """
    from src.dashboard.utils.apple_launches import align_on_j0
    from src.dashboard.utils.platform_timeseries import apple_launch_readings
    from src.dashboard.utils.date_format import format_date

    launches = _launches(db, artist_id)
    st.subheader(t("apple_music.launches_header_cross", "⚡ Shazams depuis la sortie"))
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
    horizon = int(aligned["offset"].max()) + 1
    meta = _launch_spend(db, artist_id, chosen, horizon)
    charts.plotly_chart(_launches_figure(aligned, chosen, meta), width="stretch")


def _launch_spend(db, artist_id: int, chosen: list, horizon: int) -> pd.DataFrame:
    """Meta € per day by Apple title and day since J0 — through the CONFIRMED link (R476).

    The release of an Apple title is the `normalize_track_title` key `_launches` already
    resolved its J0 with; the campaign reaches it by the same confirmed-link join as the
    Spotify releases chart (`release_spend`), never by a name.
    """
    from src.dashboard.views.spotify_s4a_combined import load_release_spend
    from src.utils.track_matching import normalize_track_title

    releases = pd.DataFrame(
        [(artist_id, normalize_track_title(lc.song), lc.song, lc.j0) for lc in chosen],
        columns=["artist_id", "match_key", "title", "release_date"])
    return load_release_spend(db, releases, horizon, " AND artist_id = %s", (artist_id,))


def _launches_figure(aligned, chosen: list, meta: pd.DataFrame | None = None):
    """One line per release, x = days since J0, the J0 anchor drawn hollow; Meta € per
    day as a dotted area of the release's colour on the right axis (R476). Pure."""
    from plotly.subplots import make_subplots
    from src.dashboard.utils.platform_colors import DISTINCT
    from src.dashboard.views.spotify_s4a_combined import meta_legend_trace, meta_spend_traces

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colour = {lc.song: DISTINCT[i % len(DISTINCT)] for i, lc in enumerate(chosen)}
    has_meta = meta is not None and not meta.empty
    # The area takes the BASE axis (right), the Shazams the overlaying one (left): plotly
    # draws the overlaying axis on top, so the lines stay above the area (R436).
    if has_meta:
        for trace in meta_spend_traces(meta, colour):
            fig.add_trace(trace, secondary_y=False)
        fig.add_trace(meta_legend_trace(), secondary_y=False)
    for lc in chosen:
        s = aligned[aligned["song"] == lc.song]
        color = colour[lc.song]
        fig.add_trace(go.Scatter(
            x=s["offset"], y=s["shazams"], mode="lines+markers", name=lc.song[:40],
            line=dict(color=color, width=2.5),
            marker=dict(size=8, color=color,
                        symbol=["circle" if m else "circle-open" for m in s["measured"]]),
            hovertemplate=t("apple_music.launch_hover",
                            "J+%{x} · %{y:,.0f} Shazam(s) depuis la sortie"
                            "<extra></extra>")), secondary_y=True)
    fig.update_yaxes(title_text=t("apple_music.launch_y", "Shazams cumulés depuis J0"),
                     rangemode="tozero", side="left", secondary_y=True)
    fig.update_yaxes(title_text=(t("spotify_s4a_combined.meta_spend_axis", "Meta € / jour")
                                 if has_meta else None),
                     rangemode="tozero", side="right", showgrid=False,
                     showticklabels=has_meta, secondary_y=False)
    fig.update_layout(
        height=420, hovermode="closest",
        xaxis_title=t("apple_music.launch_x", "Jours depuis la sortie (J0)"),
        margin=dict(t=60))
    return fig
