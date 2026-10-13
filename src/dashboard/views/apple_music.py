"""Apple Music — ce que le catalogue a gagné, et sur combien de jours.

Type: Feature
Uses: view_session, platform_colors, i18n
Depends on: v_apple_song_cumulative (131),
            apple_songs_performance, gold_apple_lifetime (103/113/114)
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
