"""Impact d'une campagne — toutes plateformes, sur une seule horloge.

Type: Feature
Uses: view_session, meta_accounts, smart_period_filter, platform_colors, i18n
Depends on: meta_insights_performance_day, v_s4a_song_daily (105),
            v_spotify_track_pi_daily (130), v_hypeddit_daily,
            v_instagram_followers_daily, track_platform_link (049)
Persists in: — (lecture seule)

⚠️ LA ROUTE S'APPELLE TOUJOURS `meta_x_spotify`, LA PAGE NON
--------------------------------------------------------------
La page ne croise plus deux plateformes mais six, et son nom affiché le dit. La
CLÉ DE ROUTE, elle, ne change pas — c'est un identifiant, et le dépôt en connaît
le coût : `nav_sections` écrit « l'identifiant est stable […] le renommer casse la
sélection en cours des utilisateurs », et `process_guide` est gardée dans
`ALWAYS_ACCESSIBLE` pour la même raison (des liens la visent). Le renommer
toucherait 79 références Python, les clés i18n, la carte du PDF et l'état de
session de chaque artiste connecté, sans rien apporter à personne.

CE QUE CETTE PAGE ÉTAIT, ET LE DÉFAUT QU'ELLE CACHAIT
------------------------------------------------------
Elle s'appelait « Performance 360° » et traçait six séries. Mesuré le 2026-09-21
sur le locataire 1 : **elle ne pouvait en dessiner que deux.**

  · La courbe de STREAMS était vide pour 3 des 7 titres cartographiés — dont la
    campagne à **684,98 €**. La requête comparait `s4a_song_timeline.song`, épelé
    depuis un NOM DE FICHIER (`_`), à `campaign_track_mapping.track_name`, épelé
    par l'API (`?`). Zéro ligne, aucune erreur, aucun message. C'est la classe
    `song-name-convention-mismatch`, et le garde écrit pour elle
    (`test_a_song_join_normalises_both_sides`) ne la voyait pas : il cherche la
    forme `track_name = %s`, or ici la colonne nommée est `song` et c'est la
    VALEUR liée qui vient de l'API. Le prédicat cherchait une forme d'écriture, la
    classe est une propriété — règle 20 de CLAUDE.md.
  · La courbe de POPULARITÉ n'a JAMAIS eu un seul point sur aucune campagne : le
    relevé commence le 23/11/2025, la dernière campagne s'est terminée le
    30/09/2024. Une entrée de légende qui ne peut rien dessiner.

Le rattachement passe donc par `track_platform_link` — le LIEN CONFIRMÉ, comme en
migration 119 — et plus jamais par un nom.

CE QUI EST TRACÉ, ET CE QUI NE PEUT PAS L'ÊTRE
-----------------------------------------------
Six sources, groupées par plateforme. La COULEUR dit la plateforme, le TRAIT dit
la série : c'est ce qui permet d'en lire six sans six teintes, et un trait survit
à la deutéranopie là où une teinte ne survit pas.

  Meta (bleu)      budget · résultats · CPR · impressions · couverture
  Spotify (vert)   streams/jour · indice de popularité
  Hypeddit (cyan)  visites · clics vers les stores
  Instagram (violet) abonnés — ⚠️ AU NIVEAU DU COMPTE, pas de la campagne
  Apple/Shazam     ne peut pas être tracé : `apple_songs_performance` est un
                   INSTANTANÉ cumulé par titre, pas une série quotidienne. Le
                   locataire 1 n'en porte qu'UN, daté du 08/06/2026. Le dire est
                   le travail ; inventer une série ne l'est pas.

⚠️ Instagram compte les abonnés du COMPTE ENTIER. Les poser sur l'axe d'UNE
campagne invite à lire « cette campagne m'a fait gagner des abonnés » d'une série
qui compte tout ce qui en fait gagner. La figure les dessine parce qu'ils
renseignent le contexte, et sa légende dit ce qu'ils ne prouvent pas.

CE QUE LA PAGE AJOUTE, ET QUI N'EXISTAIT NULLE PART
----------------------------------------------------
Le **coût par stream** (`dépense ÷ streams`) et la **conversion résultat → stream**
(`streams ÷ résultats`). Le CPR que Meta rend est le prix d'un RÉSULTAT — un clic,
une vue de page — jamais celui d'une écoute. Aucune surface du produit ne disait
ce qu'une écoute coûte réellement, alors que c'est la seule question qui traverse
les deux plateformes. Ce sont des tuiles et non des courbes : un PRIX indexé en
base 100 ne veut rien dire, et la figure a son budget.
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t
from src.dashboard.utils.meta_accounts import account_clause, account_scope
from plotly.subplots import make_subplots

from src.dashboard.utils.platform_colors import PALETTE_DARK, PALETTE_LIGHT
from src.dashboard.utils.date_format import format_date

# L'encre du TROISIÈME axe — le coût par écoute, qui n'appartient à aucune
# plateforme. Elle n'est utilisée par aucune série de l'axe principal : c'est ce
# qui permet de voir, sans lire la légende, quelle marque se lit à droite.
_CROSS_INK = "#6d4c41"

# La rémanence se juge sur 28 jours — la fenêtre de Spotify for Artists elle-même,
# déjà reprise par `spotify_s4a_combined`. On parle la langue de la source plutôt
# que d'inventer un horizon.
_TAIL_DAYS = 28


def _palette() -> dict:
    """La palette du thème du VISITEUR, avec un repli clair — jamais une exception.

    Même forme que `platform_chart._is_dark()`, et pour la même raison : un thème
    illisible ne doit pas casser une page, il doit rendre la palette claire.
    """
    dark = False
    try:
        theme = getattr(st.context, "theme", None)
        if theme is not None and getattr(theme, "type", None):
            dark = str(theme.type).lower() == "dark"
    except Exception:      # noqa: BLE001 — versions de Streamlit sans st.context
        pass
    return PALETTE_DARK if dark else PALETTE_LIGHT


def _df(db, sql: str, params: tuple) -> pd.DataFrame:
    try:
        return db.fetch_df(sql, params)
    except Exception:      # noqa: BLE001 — une source absente ne casse pas la page
        return pd.DataFrame()


# ── Le rattachement : par le LIEN CONFIRMÉ, jamais par un nom ──────────────────
def _resolve_track(db, artist_id, campaign: str) -> tuple:
    """(titre affiché, titre S4A) de la campagne — ou (None, None).

    LES DEUX JAMBES SONT ESSAYÉES, et la mesure dit pourquoi.
    `campaign_track_mapping.track_name` porte tantôt l'orthographe de l'API
    (`Qui a bu le crachoir du saloon ?`), tantôt celle du fichier S4A
    (`Qui a sali mon slip avec de la gadoue_`) — les deux existent en base chez le
    locataire 1, selon l'époque de la saisie. On rapproche donc ce nom du
    `platform_title` de N'IMPORTE QUELLE plateforme liée, puis on redescend vers
    la jambe `s4a` du même `match_key`.

    Mesuré le 2026-09-21 : la jointure d'avant (`TRIM(song) = track_name` sur
    `s4a_song_timeline`) résolvait **4 titres sur 7** ; celle-ci en résout **7**.
    """
    rows = _df(db, """
        SELECT DISTINCT m.track_name, s4a.platform_title AS s4a_song
          FROM campaign_track_mapping m
          JOIN track_platform_link any_l
            ON any_l.artist_id = m.artist_id AND any_l.status = 'confirmed'
           AND TRIM(any_l.platform_title) = TRIM(m.track_name)
          JOIN track_platform_link s4a
            ON s4a.artist_id = any_l.artist_id AND s4a.match_key = any_l.match_key
           AND s4a.platform = 's4a' AND s4a.status = 'confirmed'
         WHERE m.artist_id = %s AND m.campaign_name = %s
         LIMIT 1
    """, (artist_id, campaign))
    if not rows.empty:
        return rows.iloc[0]["track_name"], rows.iloc[0]["s4a_song"]

    # Cartographié, mais sans lien confirmé : on connaît le nom, pas la série.
    named = _df(db, "SELECT track_name FROM campaign_track_mapping "
                    "WHERE artist_id = %s AND campaign_name = %s LIMIT 1",
                (artist_id, campaign))
    return (named.iloc[0]["track_name"], None) if not named.empty else (None, None)


# ── Les sources, une par plateforme ────────────────────────────────────────────
def _collect(db, artist_id, acct, acct_p, campaign, s4a_song, d0, d1) -> tuple:
    """(séries alignées sur une date, absences expliquées).

    Chaque source rend un `DataFrame` à colonne `date`, ou vide. Une source vide
    n'est PAS un zéro : elle entre dans `absences` avec la raison lisible par
    l'artiste — c'est la règle du dépôt (`platform_absence`), et c'est ce qui
    manquait ici : six séries promises, deux dessinables, rien qui le dise.
    """
    frames, absences = [], []

    meta = _df(db, f"""
        SELECT day_date AS date, spend, results, cpr, impressions, reach
          FROM meta_insights_performance_day
         WHERE artist_id = %s{acct} AND campaign_name = %s
           AND day_date BETWEEN %s AND %s
    """, (artist_id, *acct_p, campaign, d0, d1))
    if not meta.empty:
        frames.append(meta)

    # SPOTIFY — par le lien confirmé. `s4a_song` est déjà l'orthographe du
    # fichier : aucune comparaison de nom ne subsiste ici.
    if s4a_song:
        streams = _df(db, """
            SELECT day AS date, streams FROM v_s4a_song_daily
             WHERE artist_id = %s AND song = %s AND day BETWEEN %s AND %s
        """, (artist_id, s4a_song, d0, d1))
        frames.append(streams) if not streams.empty else absences.append(
            ("spotify_streams", None))

        pi = _df(db, """
            SELECT day AS date, popularity FROM v_spotify_track_pi_daily
             WHERE artist_id = %s AND song = %s AND day BETWEEN %s AND %s
        """, (artist_id, s4a_song, d0, d1))
        if not pi.empty:
            frames.append(pi)
        else:
            # LA DATE DU PREMIER RELEVÉ EST LA RÉPONSE, pas « pas de données ».
            first = _df(db, "SELECT MIN(day) AS d FROM v_spotify_track_pi_daily "
                            "WHERE artist_id = %s", (artist_id,))
            absences.append(("popularity", _first_day(first)))
    else:
        absences.append(("spotify_unlinked", None))

    hyp = _df(db, """
        SELECT day AS date, clicks AS hypeddit_clicks, visits AS hypeddit_visits
          FROM v_hypeddit_daily
         WHERE artist_id = %s AND campaign_name = %s AND day BETWEEN %s AND %s
    """, (artist_id, campaign, d0, d1))
    if not hyp.empty:
        frames.append(hyp)
    else:
        first = _df(db, "SELECT MIN(day) AS d FROM v_hypeddit_daily WHERE artist_id = %s",
                    (artist_id,))
        absences.append(("hypeddit", _first_day(first)))

    return frames, absences


def _first_day(df: pd.DataFrame):
    return _day_of(df, "d")


def _day_of(df: pd.DataFrame, column: str):
    """La date de `column` sur la 1ʳᵉ ligne, ou None — jamais une exception."""
    if df.empty or column not in df.columns or pd.isna(df.iloc[0][column]):
        return None
    return pd.to_datetime(df.iloc[0][column]).date()


# ── Les chiffres qui TRAVERSENT les deux plateformes ───────────────────────────
def _render_tiles(db, artist_id, master: pd.DataFrame, d0, d1) -> None:
    """Dépense · streams · € par stream · streams par résultat · abonnés Instagram.

    Les deux du milieu n'existaient nulle part dans le produit. Le CPR que Meta
    rend est le prix d'un RÉSULTAT (un clic, une vue de page) ; il ne dit pas ce
    qu'une ÉCOUTE coûte. C'est pourtant la seule question qui traverse les deux
    plateformes, et celle qu'on se pose en regardant cette page.

    Des tuiles, pas des courbes : un PRIX indexé en base 100 ne veut rien dire, et
    la figure a son budget (`tests/test_chart_budget.py`).
    """
    spend = float(pd.to_numeric(master.get("spend"), errors="coerce").sum()) \
        if "spend" in master else 0.0
    results = float(pd.to_numeric(master.get("results"), errors="coerce").sum()) \
        if "results" in master else 0.0

    # LES DEUX DÉNOMINATEURS NE SONT PAS LE MÊME, et c'est tout le sujet.
    #
    # `streams_window` = les écoutes de la FENÊTRE affichée, ce que montre la
    # figure. `streams_paid` = les écoutes des seuls jours où la campagne a
    # PAYÉ — c'est le seul dénominateur qui donne un sens à « coût par stream ».
    #
    # Mesuré le 2026-09-21 avant cette distinction : la fenêtre par défaut allait
    # jusqu'à aujourd'hui, donc 31 jours de dépense se divisaient par 646 jours
    # d'écoutes et la tuile affichait **0,057 € le stream**. Le nombre était
    # calculé correctement et ne décrivait rien.
    streams_window = float(pd.to_numeric(master.get("streams"), errors="coerce").sum()) \
        if "streams" in master else 0.0
    paid = master[pd.to_numeric(master.get("spend"), errors="coerce").fillna(0) > 0] \
        if "spend" in master else master.iloc[0:0]
    streams_paid = float(pd.to_numeric(paid.get("streams"), errors="coerce").sum()) \
        if "streams" in paid else 0.0
    streams = streams_window

    # QUATRE TUILES, PAS CINQ — plafond de premier écran (Few : un tableau de bord
    # tient dans un coup d'œil ; `test_the_first_screen_counts_its_gauges` compte les
    # jauges AVEC les figures, et la page en rendait 7 pour un plafond de 5).
    # Celle qui sort est Instagram, et ce n'est pas un tirage au sort : c'est la
    # seule qui ne mesure pas CETTE campagne. Elle descend en ligne de contexte,
    # ce qui est de toute façon sa vraie nature.
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("meta_x_spotify.tile_spend", "💸 Dépense"),
              f"{spend:,.2f} €".replace(",", " "))
    c2.metric(t("meta_x_spotify.tile_streams", "🎵 Streams sur la période"),
              f"{streams:,.0f}".replace(",", " ") if streams else "—")
    # ⚠️ Un dénominateur nul rend « — », jamais 0 ni l'infini : « 0 € le stream »
    # se lirait comme une acquisition gratuite, ce qui est l'inverse du fait.
    c3.metric(t("meta_x_spotify.tile_cost_per_stream", "🎯 Coût par stream"),
              f"{spend / streams_paid:,.3f} €".replace(",", " ") if streams_paid else "—",
              help=t("meta_x_spotify.tile_cps_help",
                     "Dépense ÷ écoutes des **jours où la campagne a payé** — pas "
                     "de la fenêtre affichée : diviser une dépense de 31 jours par "
                     "les écoutes de deux ans donnerait un prix qui ne décrit "
                     "rien. À ne pas confondre avec le CPR de Meta, qui est le "
                     "prix d'un RÉSULTAT (clic, vue de page) et jamais celui d'une "
                     "écoute."))
    c4.metric(t("meta_x_spotify.tile_conversion", "🔁 Streams par résultat"),
              f"{streams_paid / results:,.2f}".replace(",", " ")
              if results and streams_paid else "—",
              help=t("meta_x_spotify.tile_conv_help",
                     "Écoutes ÷ résultats, sur les jours payés. Combien d'écoutes "
                     "pour un clic facturé."))

    # INSTAGRAM EN CHIFFRE, PAS EN COURBE — et c'est une décision, pas un repli.
    # Le compteur porte les abonnés du COMPTE ENTIER : posé sur l'axe d'UNE
    # campagne, il invite à lire « cette campagne m'a fait gagner des abonnés »
    # d'une série qui compte tout ce qui en fait gagner. (Et la mesure du
    # 2026-09-21 dit qu'il n'a de toute façon pas de teinte attribuable à côté du
    # cyan d'Hypeddit — voir `platform_colors`.)
    insta = _df(db, """
        SELECT MIN(followers) AS f0, MAX(day) AS dmax,
               (ARRAY_AGG(followers ORDER BY day DESC))[1] AS f1
          FROM v_instagram_followers_daily
         WHERE artist_id = %s AND day BETWEEN %s AND %s
    """, (artist_id, d0, d1))
    if not insta.empty and pd.notna(insta.iloc[0]["f1"]):
        row = insta.iloc[0]
        delta = int(row["f1"]) - int(row["f0"])
        st.caption(t("meta_x_spotify.insta_line",
                     "📸 **Instagram** : {f} abonné(s) ({d} sur la fenêtre) — du "
                     "**compte entier**, pas de cette campagne : tout ce que tu "
                     "publies y contribue. Un contexte, pas un résultat.")
                   .format(f=f"{int(row['f1']):,}".replace(",", " "),
                           d=f"{delta:+d}"))
    else:
        st.caption(t("meta_x_spotify.insta_none",
                     "📸 **Instagram** : aucun relevé d'abonnés sur cette fenêtre."))


# ── La figure : la COULEUR dit la plateforme, le TRAIT dit la série ────────────
#
# (colonne, libellé, plateforme, tiret, format du survol)
#
# Six séries, QUATRE teintes. C'est une contrainte mesurée, pas une préférence :
# sept teintes attribuables sont impossibles dans cette palette (recherche
# conjointe du 2026-09-21, détail dans `platform_colors`). Le tiret porte donc la
# distinction À L'INTÉRIEUR d'une plateforme — et il la porte MIEUX qu'une teinte,
# parce qu'un tiret survit à la deutéranopie.
_SERIES = [
    # R146 — résidu dans un fichier par ailleurs corrigé le 2026-09-21 : la page
    # porte la meilleure info-bulle du dépôt sur ce sujet (tuile « Coût par
    # stream ») et sa propre légende de figure disait encore « Résultats ».
    ("results",         "Clics sortants",       "meta",     None,     ",.0f"),
    ("impressions",     "Impressions",          "meta",     "dashdot", ",.0f"),
    ("reach",           "Couverture (personnes)", "meta",   "longdash", ",.0f"),
    ("cpr_display",     "CPR (€/clic sortant)", "meta",     "dot",    ",.2f"),
    ("streams",         "Streams / jour",       "spotify",  None,     ",.0f"),
    ("popularity",      "Indice de popularité", "spotify",  "dot",    ",.0f"),
    ("hypeddit_visits", "Visites Hypeddit",     "hypeddit", None,     ",.0f"),
    ("hypeddit_clicks", "Clics vers les stores", "hypeddit", "dash",  ",.0f"),
]


def _index100(master: pd.DataFrame, col: str):
    """(série indexée à 100, série brute) ou (None, None) si aucune base positive."""
    if col not in master.columns:
        return None, None
    raw = pd.to_numeric(master[col], errors="coerce")
    positive = raw[raw > 0]
    if positive.empty:
        return None, None
    return raw / positive.iloc[0] * 100, raw


def _render_chart(master: pd.DataFrame, campaign: str) -> None:
    pal = _palette()
    fig = go.Figure()

    # Le budget en AIRE PÂLE — un contexte, pas une série qu'on lit point à point.
    idx, raw = _index100(master, "spend")
    if idx is not None:
        r, g, b = (int(pal["meta"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        fig.add_trace(go.Scatter(
            x=master["date"], y=idx, mode="lines", connectgaps=False,
            name=t("meta_x_spotify.budget_eur", "Budget (€)"),
            line=dict(color=pal["meta"], width=0), fill="tozeroy",
            fillcolor=f"rgba({r},{g},{b},0.13)", customdata=raw,
            hovertemplate=t("meta_x_spotify.budget_hover",
                            "Budget : %{customdata:,.2f} €<extra></extra>")))

    for col, default_label, platform, dash, fmt in _SERIES:
        idx, raw = _index100(master, col)
        if idx is None:
            continue
        label = t(f"meta_x_spotify.series_{col}", default_label)
        fig.add_trace(go.Scatter(
            x=master["date"], y=idx, mode="lines", connectgaps=False,
            name=label, customdata=raw,
            line=dict(color=pal[platform], width=2, dash=dash),
            hovertemplate=f"{label} : %{{customdata:{fmt}}} (idx %{{y:.0f}})<extra></extra>"))

    # LE JOUR OÙ LA DÉPENSE S'ARRÊTE — la question « ça tient après ? » se lisait
    # jusqu'ici en comparant deux courbes à l'œil, sans repère.
    last_spend = _last_spend_day(master)
    if last_spend is not None:
        # ⚠️ PAS `add_vline`. Son assistant d'annotation fait la MOYENNE des
        # bornes en x pour placer le texte, et cette moyenne est une addition
        # d'horodatages : « Addition/subtraction of integers and integer-arrays
        # with Timestamp is no longer supported » (levé au premier rendu,
        # 2026-09-21, plotly 6 / pandas 2). La forme d'avant — une ligne et une
        # annotation posées séparément — ne calcule rien sur les dates.
        x = last_spend.isoformat()
        fig.add_shape(type="line", xref="x", yref="paper", x0=x, x1=x, y0=0, y1=1,
                      line=dict(color=pal["meta"], width=1.5, dash="dash"))
        fig.add_annotation(x=x, xref="x", y=1.0, yref="paper", yanchor="bottom",
                           showarrow=False, font=dict(color=pal["meta"], size=11),
                           text=t("meta_x_spotify.spend_ends", "fin de la dépense"))

    fig.update_layout(
        height=560, hovermode="x unified", showlegend=True, separators=", ",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        title_text=t("meta_x_spotify.chart_title",
                     "Analyse détaillée : {campaign}").format(campaign=campaign),
        xaxis=dict(title=t("common.date", "Date"), type="date"),
        yaxis=dict(title=t("meta_x_spotify.index_axis",
                           "Indice (base 100 = début de période)"), rangemode="tozero"))
    fig.add_hline(y=100, line_dash="dot", line_color="rgba(128,128,128,0.35)",
                  annotation_text="base 100", annotation_position="top left")
    st.plotly_chart(fig, width="stretch")

    st.caption(t("meta_x_spotify.index_caption",
                 "Séries indexées (base 100 = 1ᵉʳ jour non nul de la période) : c'est "
                 "ce qui permet de comparer des €, des écoutes et un indice 0-100 sur "
                 "un seul axe. Valeurs absolues au survol. **La couleur dit la "
                 "plateforme** — Meta en bleu, Spotify en vert, Hypeddit en cyan — "
                 "**et le trait dit la série** : un trait se distingue encore quand on "
                 "ne distingue pas les couleurs."))


def _last_spend_day(master: pd.DataFrame):
    if "spend" not in master.columns:
        return None
    spent = master[pd.to_numeric(master["spend"], errors="coerce").fillna(0) > 0]
    return None if spent.empty else spent["date"].max()


# ── Ce qui n'a pas pu être tracé, et POURQUOI ──────────────────────────────────
def _render_absences(absences: list, d0, d1) -> None:
    """Une ligne par source absente. Jamais « pas de données ».

    C'est la règle du dépôt (`utils/platform_absence`) appliquée ici, et elle
    manquait : la page promettait six séries et en dessinait deux, sans que rien
    ne dise laquelle manquait ni pourquoi. Une légende qui ne peut rien dessiner
    est pire qu'une phrase qui dit pourquoi.
    """
    lignes = []
    for quoi, first in absences:
        if quoi == "spotify_unlinked":
            lignes.append(t("meta_x_spotify.abs_unlinked",
                            "🎵 **Streams Spotify** — cette campagne n'a pas de titre "
                            "rattaché par un lien confirmé. Le rattachement se fait "
                            "dans **🔗 Mapping cross-plateforme**."))
        elif quoi == "spotify_streams":
            lignes.append(t("meta_x_spotify.abs_streams",
                            "🎵 **Streams Spotify** — le titre est rattaché, mais "
                            "aucun import Spotify for Artists ne couvre cette "
                            "période. Le CSV s'importe au moment d'une sortie."))
        elif quoi == "popularity":
            lignes.append(_late(
                t("meta_x_spotify.abs_pi",
                  "🎵 **Indice de popularité** — le relevé quotidien commence le "
                  "**{d}**, après la fin de cette campagne ({fin})."),
                t("meta_x_spotify.abs_pi_never",
                  "🎵 **Indice de popularité** — aucun relevé pour ce compte."),
                first, d1))
        elif quoi == "hypeddit":
            # ⚠️ Hypeddit est indexé par CAMPAGNE, pas seulement par date : son
            # absence ne s'explique donc pas par « la collecte a commencé plus
            # tard ». Le premier jet écrivait « le premier relevé date du
            # 22/09/2023 ; cette campagne s'est terminée le 21/09/2026 » — deux
            # dates justes et une explication fausse, la campagne s'étant
            # terminée en 2024 et le relevé de 2023 la PRÉCÉDANT. La phrase dit
            # maintenant ce qui est vrai : rien pour CETTE campagne.
            lignes.append(_late(
                t("meta_x_spotify.abs_hyp",
                  "📱 **Hypeddit** — aucune statistique pour cette campagne sur "
                  "cette fenêtre (premier relevé au dossier : {d})."),
                t("meta_x_spotify.abs_hyp_never",
                  "📱 **Hypeddit** — aucune statistique pour cette campagne."),
                first, d1))

    # APPLE / SHAZAM : ce n'est pas une absence de données, c'est une absence de
    # SÉRIE. `apple_songs_performance` est un instantané cumulé par titre, sans
    # grain quotidien — il ne peut pas se poser sur un axe de temps, quelle que
    # soit la période. Le dire une fois vaut mieux que le redécouvrir.
    lignes.append(t("meta_x_spotify.abs_apple",
                    "🎎 **Apple Music / Shazam** — non traçable ici par "
                    "construction : l'export Apple est un **instantané cumulé par "
                    "titre**, pas une série quotidienne. Ses totaux vivent sur "
                    "**🎎 Apple Music**."))

    if lignes:
        with st.expander(t("meta_x_spotify.absences_header",
                           "ℹ️ Ce qui n'est pas sur la figure, et pourquoi "
                           "({n})").format(n=len(lignes))):
            for ligne in lignes:
                st.markdown(f"- {ligne}")


def _late(modele: str, jamais: str, first, fin) -> str:
    """Le modèle daté, ou la phrase « jamais » quand il n'y a aucune date.

    `{fin}` est optionnel dans le modèle : toutes les absences ne s'expliquent
    pas par une collecte qui commence trop tard, et forcer une date de fin dans
    chacune produisait une phrase juste dans ses chiffres et fausse dans son sens.
    """
    if first is None:
        return jamais
    return modele.format(d=format_date(first),
                         fin=format_date(pd.to_datetime(fin)))


def _merge(frames: list) -> pd.DataFrame:
    """L'UNION des dates des sources, chacune ramenée par un `how='left'`.

    ⚠️ UN JOUR NON MESURÉ N'EST PAS UN JOUR À ZÉRO, et cette figure en fabriquait
    cinq à la fois avant le 2026-09-12. `NaN` est CONSERVÉ : Plotly coupe alors la
    ligne (`connectgaps=False`, posé explicitement sur chaque trace pour qu'un
    garde puisse le lire). Aucun `fillna(0)`, aucun `ffill` — les deux inventent
    une mesure, et la page l'a fait pour les streams comme pour la popularité.
    """
    dates = pd.concat([f["date"] for f in frames if "date" in f.columns]).dropna().unique()
    master = pd.DataFrame({"date": sorted(pd.to_datetime(dates))})
    for f in frames:
        if f.empty or "date" not in f.columns:
            continue
        f = f.copy()
        f["date"] = pd.to_datetime(f["date"])
        master = pd.merge(master, f, on="date", how="left")

    for col in ("spend", "results", "impressions", "reach", "streams", "popularity",
                "hypeddit_clicks", "hypeddit_visits"):
        if col in master.columns:
            master[col] = pd.to_numeric(master[col], errors="coerce").astype(float)

    # Le CPR vient du collecteur, qui le supprime (NULL) pour un objectif sans
    # conversion. On ne le RECALCULE pas depuis spend/results : ce serait
    # fabriquer un CPR que Meta a délibérément caché.
    master["cpr_display"] = pd.to_numeric(master.get("cpr"), errors="coerce") \
        if "cpr" in master.columns else pd.NA
    return master


def _show_body(db, artist_id) -> None:
    """Le corps — `db.close()` est tenu par `show()`."""
    # Compte publicitaire d'abord : le même nom de campagne peut exister dans deux
    # comptes, et cette page raconte l'histoire d'UNE campagne (R53 / ADR-013).
    acct, acct_p = account_clause(
        account_scope(db, artist_id, key="meta_x_spotify_acct"))

    camps = _df(db, f"""
        SELECT campaign_name FROM meta_insights_performance_day
         WHERE artist_id = %s{acct}
         GROUP BY campaign_name ORDER BY MAX(day_date) DESC NULLS LAST
    """, (artist_id, *acct_p))
    available = camps["campaign_name"].tolist() if not camps.empty else []
    if not available:
        st.info(t("meta_x_spotify.no_campaign",
                  "Aucune campagne Meta Ads sur ce compte. Branche-le depuis "
                  "**🔑 Credentials API + imports CSV**."))
        return

    col_camp, col_date = st.columns([1, 2])
    with col_camp:
        campaign = st.selectbox(
            t("meta_x_spotify.choose_campaign", "Choisir la campagne"),
            options=available, index=0)

    display_track, s4a_song = _resolve_track(db, artist_id, campaign)

    bornes = _df(db, f"""
        SELECT MIN(day_date) AS d, MAX(day_date) AS f
          FROM meta_insights_performance_day
         WHERE artist_id = %s{acct} AND campaign_name = %s
    """, (artist_id, *acct_p, campaign))
    # ⚠️ PAS de `rename(columns={"f": "d"})` ici : `bornes` porte DÉJÀ une colonne
    # `d`, donc le renommage en créait une seconde du même nom et `iloc[0]["d"]`
    # rendait une Series — « The truth value of a Series is ambiguous », levé au
    # rendu le 2026-09-21. On lit chaque colonne par son nom.
    camp_start = _day_of(bornes, "d")
    camp_end = _day_of(bornes, "f")
    if camp_start is None or camp_end is None:
        st.info(t("meta_x_spotify.no_data", "Aucune donnée sur cette période."))
        return

    with col_date:
        d0, d1, fenetre = _campaign_window(camp_start, camp_end, campaign)
        st.caption(t("meta_x_spotify.window_caption",
                     "{f} — campagne du {a} au {b}, {n} jour(s) de diffusion.")
                   .format(f=fenetre, a=format_date(camp_start),
                           b=format_date(camp_end),
                           n=(camp_end - camp_start).days + 1))

    # LE TITRE LIÉ, ET SUR QUELLE PLATEFORME — demandé le 2026-09-21. « Titre
    # lié » seul ne disait pas de quel catalogue venait ce nom, alors que c'est
    # exactement ce qui se perd entre l'API (« ? ») et le fichier S4A (« _ »).
    if display_track and s4a_song:
        st.caption(t("meta_x_spotify.linked_track",
                     "🎵 Titre lié sur Spotify : **{track}**").format(track=display_track))
    elif display_track:
        st.warning(t("meta_x_spotify.linked_unconfirmed",
                     "🎵 Titre lié sur Spotify : **{track}** — mais sans lien "
                     "CONFIRMÉ, donc ses écoutes ne peuvent pas être rattachées. "
                     "Confirme-le dans **🔗 Mapping cross-plateforme**.")
                   .format(track=display_track))
    else:
        st.warning(t("meta_x_spotify.no_linked_track",
                     "⚠️ Aucun titre lié sur Spotify pour cette campagne. "
                     "L'association se fait dans **🔗 Mapping cross-plateforme**."))

    frames, absences = _collect(db, artist_id, acct, acct_p, campaign, s4a_song, d0, d1)
    if not frames:
        st.warning(t("meta_x_spotify.no_data", "Aucune donnée sur cette période."))
        return

    master = _merge(frames)
    _render_tiles(db, artist_id, master, d0, d1)

    # TROIS ONGLETS, ET C'EST UN CHOIX DE CADRAGE — 2026-09-21.
    #
    # La page répond désormais à trois questions distinctes : « qu'a fait cette
    # campagne dans le temps », « où se perdent les gens entre la pub et
    # l'écoute », « dans quel pays l'euro rapporte le plus ». Les empiler
    # donnerait sept figures au premier écran, au-dessus du plafond de cinq que
    # `test_the_first_screen_counts_its_gauges` tient (Few : un tableau de bord
    # tient dans un coup d'œil).
    #
    # Un onglet BORNE un écran — c'est la sortie que ce garde nomme lui-même.
    #
    # ⚠️ Le coût est réel et vaut d'être écrit : `st.tabs` exécute le corps de
    # TOUS ses onglets à chaque rendu. Trois onglets, c'est trois fois le travail
    # pour un seul regardé. On l'accepte ici parce que les trois sections lisent
    # des tables différentes et qu'aucune n'est la plus chère de la page ; on l'a
    # refusé sur `data_wrapped`, où le quatrième onglet interrogeait cinq
    # domaines.
    tab_impact, tab_funnel, tab_pays = st.tabs([
        t("meta_x_spotify.tab_impact", "📈 Impact dans le temps"),
        t("meta_x_spotify.tab_funnel", "🔽 Le parcours complet"),
        t("meta_x_spotify.tab_countries", "🌍 Par pays"),
    ])
    with tab_impact:
        _render_chart(master, campaign)
        _render_absences(absences, d0, d1)
    with tab_funnel:
        _render_funnel(db, artist_id, acct, acct_p, campaign, d0, d1)
    with tab_pays:
        _render_countries(db, artist_id, acct, acct_p)


def show():
    from src.dashboard.auth import require_plan
    if not require_plan('premium'):
        return

    st.title(t("meta_x_spotify.title",
               "🔀 Impact de mes campagnes — toutes plateformes"))
    st.markdown("---")

    with view_session() as (db, artist_id):
        _show_body(db, artist_id)


def _campaign_window(camp_start, camp_end, campaign: str) -> tuple:
    """La fenêtre de CETTE campagne — pas une période générique.

    ⚠️ `smart_period_filter` a été retiré d'ici le 2026-09-21, et c'est une
    correction, pas une simplification. Tous ses préréglages se terminent
    AUJOURD'HUI (`_resolve_window` : `return PeriodWindow(start, today, …)`), et
    « depuis la dernière release » était ancré au début de la campagne. Mesuré ce
    jour-là sur « O chiotte l'arbitre Tucome Back » : l'axe couvrait **662 jours**
    pour une campagne de **31** — les séries Meta occupaient 5 % de la largeur, et
    les deux tuiles croisées divisaient 31 jours de dépense par 646 jours
    d'écoutes. Le chiffre affiché, « 0,057 € le stream », ne décrivait rien.

    Une page qui raconte UNE campagne a besoin de la fenêtre de cette campagne.
    Les trois choix ci-dessous sont ceux qu'on se pose réellement, et le défaut
    est le deuxième : ce qui compte n'est pas ce que la campagne a fait pendant
    qu'elle payait, c'est ce qui RESTE quand elle s'arrête.

    ⚠️ Cette fonction est nommée dans `_MAKERS` de
    `tests/test_a_chart_is_bounded_by_the_period_it_announces.py` : sans ça, ce
    fichier cesserait d'avoir une « fenêtre » aux yeux du garde, et ses requêtes
    ne seraient plus vérifiées comme bornées. Retirer un sélecteur ne doit pas
    retirer un contrôle.
    """
    choix = {
        "tail": t("meta_x_spotify.win_tail", "📈 Campagne + {n} j (rémanence)")
                .format(n=_TAIL_DAYS),
        "camp": t("meta_x_spotify.win_camp", "🎯 La campagne seule"),
        "all": t("meta_x_spotify.win_all", "♾️ Jusqu'à aujourd'hui"),
    }
    key = st.segmented_control(
        t("meta_x_spotify.window", "Fenêtre"), list(choix),
        key=f"mxs_win_{campaign}", format_func=lambda k: choix[k],
        default="tail") or "tail"

    if key == "camp":
        return camp_start, camp_end, choix["camp"]
    if key == "all":
        return camp_start, _dt.date.today(), choix["all"]
    return camp_start, camp_end + _dt.timedelta(days=_TAIL_DAYS), choix["tail"]


# ── Le funnel, rapatrié de « Publicité Meta Ads » et CORRIGÉ ───────────────────
def _render_funnel(db, artist_id, acct, acct_p, campaign, d0, d1) -> None:
    """Meta × Spotify × Hypeddit — et l'incohérence que l'artiste a vue.

    Rapportée le 2026-09-21 : « 643 vues de LP pour 5972 clics Spotify, on devrait
    avoir une valeur inférieure ». C'est exact, et ce n'est pas une erreur de
    fenêtre — mesuré sur tout l'historique du locataire 1 :

        les deux métriques sont mesurées ensemble sur **91 jours**
        `lp_views < custom_conversions` sur **91 jours sur 91**

    Zéro jour cohérent. Le défaut n'est donc pas dans les chiffres, il est dans le
    MODÈLE : `lp_views` et `custom_conversions` ne sont pas deux étapes
    successives, ce sont **deux mesures de la même étape**, prises par deux
    instruments différents.

      · `lp_views` — le `landing_page_view` de Meta, qui exige que le pixel se
        déclenche au CHARGEMENT de la page. Un visiteur qui clique plus vite que
        le pixel, ou qui le bloque, n'y est jamais compté.
      · `custom_conversions` — l'évènement que Hypeddit renvoie par sa CAPI,
        côté SERVEUR. Il ne dépend d'aucun pixel.

    Le second voit donc ce que le premier rate, et l'empiler SOUS lui affirmait un
    emboîtement que la donnée contredit tous les jours. `lp_views` descend au rang
    de note de qualité sur l'étape, à sa place.

    LE FUNNEL RÉEL TRAVERSE TROIS SOURCES, d'où le nom :

        Meta      impressions → clics sur la pub
        Hypeddit  visites du smart link → clics vers les plateformes
        Spotify   les écoutes qui suivent (mesurées ailleurs sur cette page)
    """
    st.subheader(t("meta_x_spotify.funnel_header",
                   "🔽 Meta × Spotify × Hypeddit — le parcours complet"))

    meta = _df(db, f"""
        SELECT COALESCE(SUM(impressions), 0) AS impressions,
               COALESCE(SUM(link_clicks), 0) AS link_clicks,
               COALESCE(SUM(lp_views), 0)    AS lp_views,
               COALESCE(SUM(custom_conversions), 0) AS capi
          FROM v_meta_campaign_daily
         WHERE artist_id = %s{acct} AND campaign_name = %s AND day BETWEEN %s AND %s
    """, (artist_id, *acct_p, campaign, d0, d1))
    hyp = _df(db, """
        SELECT COALESCE(SUM(visits), 0) AS visits, COALESCE(SUM(clicks), 0) AS clicks
          FROM v_hypeddit_daily
         WHERE artist_id = %s AND campaign_name = %s AND day BETWEEN %s AND %s
    """, (artist_id, campaign, d0, d1))

    if meta.empty:
        st.info(t("meta_x_spotify.funnel_none", "Aucune donnée Meta sur cette fenêtre."))
        return
    m = meta.iloc[0]
    impressions, clics = int(m["impressions"]), int(m["link_clicks"])
    lp, capi = int(m["lp_views"]), int(m["capi"])
    visites = int(hyp.iloc[0]["visits"]) if not hyp.empty else 0
    clics_store = int(hyp.iloc[0]["clicks"]) if not hyp.empty else 0

    # L'ARRIVÉE SUR LE SMART LINK : deux instruments, on prend le PLUS COMPLET et
    # on dit lequel. `max` n'est pas un arrangement — un évènement serveur ne peut
    # pas être moins fiable qu'un pixel qu'un navigateur peut bloquer.
    arrivees = max(capi, visites, lp)
    source_arrivee = (t("meta_x_spotify.src_capi", "CAPI Hypeddit") if arrivees == capi
                      else t("meta_x_spotify.src_hyp", "saisie Hypeddit") if arrivees == visites
                      else t("meta_x_spotify.src_pixel", "pixel Meta"))

    etapes, valeurs = [], []
    for lbl, v in (
        (t("meta_x_spotify.f_impressions", "Impressions"), impressions),
        (t("meta_x_spotify.f_clicks", "Clics sur la pub"), clics),
        (t("meta_x_spotify.f_landing", "Arrivées sur le smart link"), arrivees),
        (t("meta_x_spotify.f_store", "Clics vers les plateformes"), clics_store),
    ):
        # ⚠️ UNE ÉTAPE À ZÉRO N'EST PAS UNE ÉTAPE PERDUE, c'est une étape NON
        # MESURÉE. La tracer à 0 dessinerait un effondrement qui n'a pas eu lieu.
        if v > 0:
            etapes.append(lbl)
            valeurs.append(v)

    if len(etapes) < 2:
        st.info(t("meta_x_spotify.funnel_thin",
                  "Pas assez d'étapes mesurées pour dessiner un parcours."))
        return

    pal = _palette()
    fig = go.Figure(go.Funnel(
        y=etapes, x=valeurs, textposition="inside",
        textinfo="value+percent previous",
        marker=dict(color=[pal["meta"], pal["meta"], pal["hypeddit"], pal["hypeddit"]][:len(etapes)]),
    ))
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=30))
    st.plotly_chart(fig, width="stretch")

    note = t("meta_x_spotify.funnel_caption",
             "Les deux premières étapes viennent de **Meta**, les deux suivantes de "
             "**Hypeddit**. L'arrivée sur le smart link est mesurée par « {src} » : "
             "c'est la source la plus complète des trois disponibles.").format(
                 src=source_arrivee)
    if lp and capi and lp < capi:
        # LE FAIT QUE L'ARTISTE A VU, expliqué là où il le verra.
        note += " " + t(
            "meta_x_spotify.funnel_lp_note",
            "⚠️ Le pixel Meta ne compte que **{lp}** vues de page pour **{capi}** "
            "évènements renvoyés par la CAPI. Ce n'est pas une contradiction : le "
            "pixel doit se déclencher au chargement, l'évènement serveur non. Le "
            "pixel SOUS-COMPTE, il ne mesure pas une étape suivante — les empiler "
            "l'un sous l'autre affirmait un emboîtement faux **91 jours sur 91**."
        ).format(lp=f"{lp:,}".replace(",", " "), capi=f"{capi:,}".replace(",", " "))
    st.caption(note)


# ── Le croisement PAYS — où l'euro rapporte le plus d'écoutes ──────────────────
def _render_countries(db, artist_id, acct, acct_p) -> None:
    """Dépense Meta par pays × écoutes du distributeur par pays.

    Rapatrié de « Publicité Meta Ads » le 2026-09-21, à la demande du
    propriétaire — « ça va être de la grosse valeur ajoutée sur le croisement des
    données ». La mesure lui donne raison, et de loin :

        Colombie   110,22 € dépensés →  56 300 écoutes →  **0,002 € / écoute**
        Mexique    844,33 € dépensés →  30 820 écoutes →   0,027 € / écoute

    **Quatorze fois** d'écart, et aucune surface ne le montrait. Le pays où l'on
    dépense le plus n'est pas celui où l'euro rapporte le plus.

    ⚠️ LES ÉCOUTES NE VIENNENT PAS DE SPOTIFY, ET IL FAUT LE DIRE. L'export
    Spotify for Artists ne donne aucune ventilation par pays — ni le CSV de
    timeline, ni celui d'audience que nous importons. Le seul compte d'écoutes
    par pays du produit est celui du DISTRIBUTEUR (`imusician_sales_detail`,
    colonne `quantity`), qui agrège toutes les plateformes et arrive avec le
    décalage d'un relevé comptable. C'est une approximation ASSUMÉE, et la
    légende la nomme — la prendre pour du Spotify serait la seule erreur ici.

    ⚠️ ET LE « MEILLEUR PAYS » N'EST PAS LE PLUS PETIT CPR. Un pays où l'on a
    dépensé trois euros peut afficher un CPR flatteur sans rien prouver. Le
    classement porte donc sur le coût par ÉCOUTE, et il n'admet que les pays au-
    dessus d'un plancher de dépense — sans quoi le conseil serait « dépense là où
    tu n'as pas dépensé ».
    """
    from src.dashboard.utils.geo import iso2_to_name

    st.subheader(t("meta_x_spotify.countries_header",
                   "🌍 Où l'euro rapporte le plus d'écoutes"))

    meta = _df(db, f"""
        SELECT country, SUM(spend) AS spend, SUM(results) AS results
          FROM meta_insights_performance_country
         WHERE artist_id = %s{acct}
         GROUP BY country
    """, (artist_id, *acct_p))
    streams = _df(db, """
        SELECT country, SUM(quantity) AS streams
          FROM imusician_sales_detail
         WHERE artist_id = %s AND country IS NOT NULL
         GROUP BY country
    """, (artist_id,))
    if meta.empty:
        st.info(t("meta_x_spotify.countries_none",
                  "Aucune ventilation par pays sur ce compte publicitaire."))
        return

    meta = meta.copy()
    meta["pays"] = meta["country"].map(iso2_to_name)
    meta["spend"] = pd.to_numeric(meta["spend"], errors="coerce")
    meta["results"] = pd.to_numeric(meta["results"], errors="coerce")
    if not streams.empty:
        streams = streams.copy()
        streams["streams"] = pd.to_numeric(streams["streams"], errors="coerce")
        # Le distributeur nomme les pays en toutes lettres, Meta en ISO2 : on
        # rapproche sur le NOM, produit par la même table de correspondance que
        # la carte de `meta_breakdowns`. Un pays qu'elle ne sait pas nommer ne se
        # rapproche pas, et sort du croisement plutôt que d'être rattaché au
        # hasard.
        meta = meta.merge(streams.rename(columns={"country": "pays"}), on="pays", how="left")
    else:
        meta["streams"] = pd.NA

    meta["cout_par_ecoute"] = meta["spend"] / pd.to_numeric(
        meta["streams"], errors="coerce").where(lambda s: s > 0)
    meta = meta.sort_values("spend", ascending=False).head(15)

    pal = _palette()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=meta["pays"], y=meta["spend"], name=t("meta_x_spotify.c_spend", "Dépense (€)"),
        marker_color=pal["meta"], opacity=0.85), secondary_y=False)
    fig.add_trace(go.Bar(
        x=meta["pays"], y=meta["streams"], name=t("meta_x_spotify.c_streams", "Écoutes"),
        marker_color=pal["spotify"], opacity=0.85), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=meta["pays"], y=meta["cout_par_ecoute"], mode="markers",
        name=t("meta_x_spotify.c_cost", "€ par écoute"),
        marker=dict(color=_CROSS_INK, size=11, symbol="diamond")), secondary_y=True)
    fig.update_yaxes(title_text=t("meta_x_spotify.c_axis_left", "Dépense (€) · écoutes"),
                     type="log", secondary_y=False)
    fig.update_yaxes(title_text=t("meta_x_spotify.c_axis_right", "€ par écoute"),
                     showgrid=False, title_font=dict(color=_CROSS_INK),
                     tickfont=dict(color=_CROSS_INK), secondary_y=True)
    fig.update_layout(height=500, barmode="group", hovermode="x unified",
                      legend=dict(orientation="h", y=1.12), margin=dict(b=110))
    fig.update_xaxes(tickangle=-35)
    st.plotly_chart(fig, width="stretch")

    # LE MEILLEUR PAYS, avec son plancher de dépense écrit.
    _PLANCHER = 50.0
    eligibles = meta[(meta["spend"] >= _PLANCHER) & meta["cout_par_ecoute"].notna()]
    if not eligibles.empty:
        best = eligibles.loc[eligibles["cout_par_ecoute"].idxmin()]
        pire = eligibles.loc[eligibles["cout_par_ecoute"].idxmax()]
        st.success(t(
            "meta_x_spotify.best_country",
            "🏆 **{pays}** est ton meilleur rapport : **{c:.3f} € par écoute** "
            "({s:,.0f} € dépensés, {e:,.0f} écoutes). Le moins bon est **{pp}** à "
            "**{cc:.3f} €** — soit **{ratio:.0f}×** plus cher pour la même écoute. "
            "Seuls les pays au-dessus de **{plancher:.0f} €** de dépense entrent "
            "dans ce classement : sous ce seuil, un bon ratio ne prouve rien."
        ).format(pays=best["pays"], c=best["cout_par_ecoute"],
                 s=best["spend"], e=best["streams"], pp=pire["pays"],
                 cc=pire["cout_par_ecoute"],
                 ratio=pire["cout_par_ecoute"] / best["cout_par_ecoute"],
                 plancher=_PLANCHER).replace(",", " "))

    st.caption(t(
        "meta_x_spotify.countries_caption",
        "⚠️ **Les écoutes ne viennent pas de Spotify.** L'export Spotify for "
        "Artists ne donne aucune ventilation par pays : le seul compte du produit "
        "est celui du **distributeur** (iMusician), qui agrège toutes les "
        "plateformes et arrive avec le décalage d'un relevé comptable. La dépense, "
        "elle, vient de Meta. L'échelle de gauche est **logarithmique** — sans "
        "elle, un pays à 56 000 écoutes écrase tous les autres."))
