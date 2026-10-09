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
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from src.dashboard.utils import view_session, charts
from src.dashboard.utils.formats import num
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

            # ============================================================
            # 3. DEUX SORTIES, UNE HORLOGE (R351)
            # ============================================================
            # Les sorties, la plus récente d'abord — UNE lecture, servie à la
            # comparaison ci-dessous ET à la présélection de la série d'un titre.
            # R476 (W7) : « Shazam depuis la sortie » + Meta moved to the cross view
            # (section « Sorties »). The launches still pick the series default below.
            launches = _launches(db, artist_id)

            # ============================================================
            # 4. GRAPHIQUE DYNAMIQUE (CALCUL DIFFÉRENTIEL)
            # ============================================================
            # « Quotidienne » est parti du titre le 2026-09-21 : les relevés Apple sont
            # espacés de 12 à 179 jours chez le locataire 1, et promettre un quotidien
            # qu'on ne mesure pas est ce qui a fait jeter 100 % des points.
            st.subheader(t("apple_music.daily_growth",
                           "📈 Le rythme d'un titre"))

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


def _top10_figure(df_top, total_plays: str = "—", total_shazams: str = "—"):
    """Top 10 by cumulative streams, Shazams on the right on the same rows (R383, R484).

    One figure, two panels sharing the y axis: a title is written once and reads across
    both. Each total is the title of its panel (owner W7 II), the colour scale is gone —
    it repeated the bar length."""
    from plotly.subplots import make_subplots

    from src.dashboard.utils.platform_colors import PALETTE_LIGHT

    df = df_top.sort_values("plays")
    fig = make_subplots(
        rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.06, column_widths=[0.6, 0.4],
        subplot_titles=(
            t("apple_music.top10_title", "Top 10 — streams cumulés · total {n}").format(n=total_plays),
            t("apple_music.shazams_title", "⚡ Shazams · total {n}").format(n=total_shazams)))
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
    for col, field in ((1, "plays"), (2, "shazam_count")):
        top = float(pd.to_numeric(df[field], errors="coerce").max() or 1)
        fig.update_xaxes(range=[0, top * 1.3], nticks=4, row=1, col=col)
    fig.update_yaxes(automargin=True)   # the titles were cut at the left edge
    fig.update_layout(height=460, showlegend=False, margin=dict(l=10, r=30, t=60))
    return fig


def rate_per_30_days(gains: "pd.Series", days: "pd.Series") -> "pd.Series":
    """A gain between two readings, as a pace per 30 days. Pure (R484).

    Comparable across intervals of 12 and 179 days, which raw gains are not; the hover keeps
    the raw gain and its duration, so the average is never mistaken for a daily count."""
    import pandas as pd

    d = pd.to_numeric(days, errors="coerce")
    return (pd.to_numeric(gains, errors="coerce") / d.where(d > 0) * 30).round(0)


def pace_verdict(rates: "pd.Series") -> str:
    """« accélère / ralentit / stable » from the last two paces; "" below two. Pure (R484)."""
    r = rates.dropna()
    if len(r) < 2:
        return ""
    if r.iloc[-2] <= 0:
        return t("apple_music.pace_start", "↗ démarre") if r.iloc[-1] > 0 else ""
    change = r.iloc[-1] / r.iloc[-2] - 1
    if change > 0.10:
        return t("apple_music.pace_up", "↗ accélère ({p:+.0%})").format(p=change)
    if change < -0.10:
        return t("apple_music.pace_down", "↘ ralentit ({p:+.0%})").format(p=change)
    return t("apple_music.pace_flat", "→ stable")


def _render_song_series(df, song: str, window) -> None:
    """The pace of one title between readings — and whether it speeds up (R484).

    Owner W7 II : « je ne comprends pas quelle décision prendre → redesign ». The cumulative
    curve and the raw gains (« +36 / 179 j ») only said that a title grew. The decision is
    whether to push it again: each interval becomes a pace per 30 days, comparable across
    readings 12 or 179 days apart, and the title states the verdict from the last two paces.
    Streams and Shazams keep two panels: their orders of magnitude are not comparable.
    """
    from plotly.subplots import make_subplots

    from src.dashboard.utils.platform_colors import PALETTE_LIGHT

    apple = PALETTE_LIGHT["apple"]
    gains = df[df["daily_plays"].notna()].copy()
    gains["plays_pace"] = rate_per_30_days(gains["daily_plays"], gains["days_since_previous"])
    gains["shazam_pace"] = rate_per_30_days(gains["daily_shazams"],
                                            gains["days_since_previous"])
    if gains["plays_pace"].dropna().empty:
        st.info(t("apple_music.not_enough_history",
                  "📉 Un seul relevé pour ce titre : il faut deux dépôts "
                  "d'export pour mesurer un gain."))
        return
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.14, row_heights=[0.6, 0.4],
        subplot_titles=[t("apple_music.pace_plays", "Écoutes / 30 jours"),
                        t("apple_music.pace_shazams", "Shazams / 30 jours")])
    hover = t("apple_music.pace_hover",
              "≈ %{y:,.0f} / 30 j<br>+%{customdata[0]:,.0f} sur %{customdata[1]} j"
              "<extra></extra>")
    days = pd.to_numeric(gains["days_since_previous"], errors="coerce").fillna(1)
    mid = pd.to_datetime(gains["day"]) - pd.to_timedelta(days / 2, unit="D")
    span_ms = (days * 86_400_000 * 0.96).tolist()
    for row, pace, raw, opacity in ((1, "plays_pace", "daily_plays", 0.9),
                                    (2, "shazam_pace", "daily_shazams", 0.5)):
        # Each bar spans ITS interval, from the previous reading to this one: the pace
        # holds over those days, not on the reading date.
        fig.add_trace(go.Bar(
            x=mid, width=span_ms, y=gains[pace], marker_color=apple, opacity=opacity,
            text=[num(v, 0) if v == v else "" for v in gains[pace]],
            textposition="outside", cliponaxis=False,
            customdata=gains[[raw, "days_since_previous"]].values,
            hovertemplate=hover, showlegend=False), row=row, col=1)
        top = gains[pace].max()
        fig.update_yaxes(range=[0, (top if top == top and top > 0 else 1) * 1.25],
                         row=row, col=1)
    verdict = pace_verdict(gains["plays_pace"])
    fig.update_layout(height=520, margin=dict(t=90),
                      title_text=" · ".join(x for x in (song, verdict, window.label) if x))
    charts.plotly_chart(fig, width="stretch")


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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), margin=dict(t=60))
    return fig
