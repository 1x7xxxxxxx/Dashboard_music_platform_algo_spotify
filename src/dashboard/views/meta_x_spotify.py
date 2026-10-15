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

from src.dashboard.utils import charts
from src.dashboard.utils.formats import eur, num
from src.dashboard.utils.i18n import t
from plotly.subplots import make_subplots

from src.dashboard.utils.campaign_funnel import (
    BASELINE_DAYS, BASELINE_MIN_DAYS, MIN_PAIRED_DAYS, campaign_treasury,
    shazam_stream_lag, streams_gained,
)
from src.dashboard.utils.platform_colors import PALETTE_DARK, PALETTE_LIGHT
from src.dashboard.utils.ratios import per, per_series
from src.dashboard.utils.date_format import format_date

# L'encre du TROISIÈME axe — le coût par écoute, qui n'appartient à aucune
# plateforme. Elle n'est utilisée par aucune série de l'axe principal : c'est ce
# qui permet de voir, sans lire la légende, quelle marque se lit à droite.
_CROSS_INK = "#6d4c41"

def _palette() -> dict:
    """La palette du thème du VISITEUR, avec un repli clair — jamais une exception.

    Même forme que `platform_colors.is_dark()`, et pour la même raison : un thème
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

    _collect_apple(db, artist_id, s4a_song, d0, d1, frames, absences)

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


def _collect_apple(db, artist_id, s4a_song, d0, d1, frames: list, absences: list) -> None:
    """Apple plays and Shazams of the linked track, on the days they are DAILY (R213 e).

    One query: the Apple leg of the same confirmed `match_key` as the S4A title, EVERY
    reading — not only those before d1: readings that start after the window are the
    answer « too late », and filtering them in SQL turned it into « no reading ». Only readings one day after the previous one enter the figure — a
    gap of six months is not « per day ». Otherwise the absence says which case it is:
    no Apple link, readings that start after the window, or readings too far apart."""
    if not s4a_song:
        return
    rows = _df(db, """
        SELECT d.day AS date, d.daily_plays AS apple_plays,
               d.daily_shazams AS apple_shazams, d.days_since_previous
          FROM track_platform_link s
          JOIN track_platform_link a
            ON a.artist_id = s.artist_id AND a.match_key = s.match_key
           AND a.platform = 'apple' AND a.status = 'confirmed'
          JOIN v_apple_song_daily d
            ON d.artist_id = a.artist_id AND d.song_name = a.platform_title
         WHERE s.artist_id = %s AND s.platform = 's4a' AND s.status = 'confirmed'
           AND s.platform_title = %s
    """, (artist_id, s4a_song))
    if rows.empty:
        absences.append(("apple_none", None))
        return
    rows['date'] = pd.to_datetime(rows['date'])
    window = rows[(rows['date'] >= pd.Timestamp(d0)) & (rows['date'] <= pd.Timestamp(d1))]
    daily = window[pd.to_numeric(window['days_since_previous'], errors='coerce') == 1]
    if not daily.empty:
        frames.append(daily[['date', 'apple_plays', 'apple_shazams']])
    elif window.empty:
        absences.append(("apple_late", rows['date'].min().date()))
    else:
        absences.append(("apple_sparse", None))


def _first_day(df: pd.DataFrame):
    return _day_of(df, "d")


def _day_of(df: pd.DataFrame, column: str):
    """La date de `column` sur la 1ʳᵉ ligne, ou None — jamais une exception."""
    if df.empty or column not in df.columns or pd.isna(df.iloc[0][column]):
        return None
    return pd.to_datetime(df.iloc[0][column]).date()


# ── Les chiffres qui TRAVERSENT les deux plateformes ───────────────────────────
def _render_tiles(db, artist_id, master: pd.DataFrame, d0, d1) -> None:
    """Dépense · streams · € par stream · CPR moyen · abonnés Instagram.

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
              eur(spend, 2))
    days = (d1 - d0).days + 1
    c2.metric(t("meta_x_spotify.tile_streams_days", "🎵 Streams sur les {n} jours").format(
              n=days), num(streams, 0) if streams else "—")
    # ⚠️ Un dénominateur nul rend « — », jamais 0 ni l'infini : « 0 € le stream »
    # se lirait comme une acquisition gratuite, ce qui est l'inverse du fait.
    c3.metric(t("meta_x_spotify.tile_cost_per_stream", "🎯 Coût par stream"),
              eur(spend / streams_paid, 3) if streams_paid else "—",
              help=t("meta_x_spotify.tile_cps_help",
                     "Dépense ÷ écoutes des **jours où la campagne a payé** — pas "
                     "de la fenêtre affichée : diviser une dépense de 31 jours par "
                     "les écoutes de deux ans donnerait un prix qui ne décrit "
                     "rien. À ne pas confondre avec le CPR de Meta, qui est le "
                     "prix d'un RÉSULTAT (clic, vue de page) et jamais celui d'une "
                     "écoute."))
    # R567 — « streams par résultat » read as a cost; the owner asked for the CPR itself.
    cpr = per(spend, results)
    c4.metric(t("meta_x_spotify.tile_cpr", "🎯 CPR moyen"),
              eur(cpr, 3) if cpr is not None else "—",
              help=t("meta_x_spotify.tile_cpr_help",
                     "Dépense ÷ résultats (clics sortants) sur la période."))

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
                   .format(f=num(int(row['f1']), 0),
                           d=f"{delta:+d}"))
    else:
        st.caption(t("meta_x_spotify.insta_none",
                     "📸 **Instagram** : aucun relevé d'abonnés sur cette fenêtre."))


def _render_shazam_lag(master: pd.DataFrame) -> None:
    """R235 — do Shazams turn into streams, and after how long? Said in one line."""
    if "apple_shazams" not in master.columns:
        return
    got = shazam_stream_lag(master)
    if got is None:
        st.caption(t("meta_x_spotify.shazam_lag_thin",
                     "🎎 Shazam → écoutes : pas assez de jours relevés en même temps (il en "
                     "faut {n}). Exporte chaque jour « hier » depuis Apple Music for Artists "
                     "pendant la campagne.").format(n=MIN_PAIRED_DAYS))
        return
    st.caption(t("meta_x_spotify.shazam_lag",
                 "🎎 Shazam → écoutes : les Shazams d'un jour suivent le mieux les écoutes "
                 "**{lag} jour(s) plus tard** (corrélation {c}, sur {n} jours). Une "
                 "corrélation n'est pas une cause : une sortie ou une playlist fait monter "
                 "les deux.").format(lag=got["lag"], c=f"{got['corr']:.2f}".replace(".", ","),
                                     n=got["days"]))


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

        # APPLE / SHAZAM (R213 e) — the old line said « not traceable by construction »
        # on every campaign. Since `v_apple_song_daily` (migration 131) derives a daily
        # quantity from consecutive snapshots, it IS traceable when readings are daily;
        # the absence now says which of the three cases holds.
        elif quoi == "apple_none":
            lignes.append(t("meta_x_spotify.abs_apple_none",
                            "🎎 **Apple Music / Shazam** — aucun relevé Apple pour ce "
                            "titre (ou pas de lien Apple confirmé dans **🔗 Mapping "
                            "cross-plateforme**)."))
        elif quoi == "apple_late":
            lignes.append(_late(
                t("meta_x_spotify.abs_apple_late",
                  "🎎 **Apple Music / Shazam** — les relevés Apple de ce titre "
                  "commencent le **{d}**, après cette fenêtre."),
                t("meta_x_spotify.abs_apple_none", "🎎 **Apple Music / Shazam** — aucun relevé."),
                first, d1))
        elif quoi == "apple_sparse":
            lignes.append(t("meta_x_spotify.abs_apple_sparse",
                            "🎎 **Apple Music / Shazam** — des relevés existent sur cette "
                            "fenêtre, mais espacés de plus d'un jour : un écart entre deux "
                            "relevés n'est pas une quantité quotidienne. Importe l'export "
                            "Apple chaque jour de campagne pour qu'il se trace ici."))

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
                "hypeddit_clicks", "hypeddit_visits", "apple_plays", "apple_shazams"):
        if col in master.columns:
            master[col] = pd.to_numeric(master[col], errors="coerce").astype(float)

    # Le CPR vient du collecteur, qui le supprime (NULL) pour un objectif sans
    # conversion. On ne le RECALCULE pas depuis spend/results : ce serait
    # fabriquer un CPR que Meta a délibérément caché.
    master["cpr_display"] = pd.to_numeric(master.get("cpr"), errors="coerce") \
        if "cpr" in master.columns else pd.NA
    return master


def _show_body(db, artist_id, bar, funnel: bool = True) -> None:
    """Le corps — la connexion est tenue par la page, les filtres par sa barre (R399)."""
    # Le compte et la campagne viennent de la barre : le même nom de campagne peut
    # exister dans deux comptes, et cette page raconte l'histoire d'UNE campagne.
    acct, acct_p = bar.acct()
    campaign = bar.campaign
    if not bar.campaigns:
        st.info(t("meta_x_spotify.no_campaign",
                  "Aucune campagne Meta Ads sur ce compte. Branche-le depuis "
                  "**🔑 Credentials API + imports CSV**."))
        return
    if campaign is None or bar.window is None:
        st.info(t("meta_x_spotify.pick_one_campaign",
                  "Le parcours se lit campagne par campagne : choisis-en une dans la barre "
                  "de filtres ci-dessus."))
        return

    display_track, s4a_song = _resolve_track(db, artist_id, campaign)
    # La fenêtre SUIT la campagne (`meta_filter_bar.campaign_window`) : jamais un
    # préréglage qui finit aujourd'hui sur une campagne de 31 jours.
    d0, d1 = bar.window.start, bar.window.end

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

    # R476 (owner W2 : « tout mon funnel … c'est flou → déplacer le contenu dans les vues
    # pertinentes ») — the four tabs are gone. This section tells ONE campaign's journey,
    # top to bottom; « par pays » moved to « Qui a vu tes pubs », « comparer mes
    # campagnes » to « Performance des campagnes » (ADR-032).
    # R555 — the index-100 journey (fiche 43) merged into the Chronologie's figure.
    _render_shazam_lag(master)
    _render_absences(absences, d0, d1)
    if funnel:
        _render_funnel(db, artist_id, acct, acct_p, campaign, d0, d1, s4a_song)


def show():
    # Gratuite depuis le 2026-09-26 (ADR-029) : cette page lit tes données, elle ne prédit
    # rien. Le verrou `require_plan('premium')` est retiré avec la ligne de `_FREE_FEATURES`.

    # R399 — the funnel is a section of the cross view, under its one filter bar.
    from src.dashboard.views.meta_ads_overview import show as show_cross_view
    show_cross_view("entonnoir")


def render_funnel(db, artist_id, bar) -> None:
    """The funnel section of the cross view (R348), read through its filter bar (R399)."""
    # R555 — the listener verdict (fiche 42) moved to the Chronologie, above its one figure.
    # R556 — a second campaign in the bar: two funnels on one row (fiches 23, 26).
    if bar.campaign and bar.second:
        _render_pair(db, artist_id, bar)
    _show_body(db, artist_id, bar, funnel=not bar.second)


# ── Le funnel, rapatrié de « Publicité Meta Ads » et CORRIGÉ ───────────────────
def funnel_measures(db, artist_id, acct, acct_p, campaign, d0, d1, s4a_song=None) -> dict:
    """Each step's volume over [d0, d1] — the database half of `full_funnel.steps`.

    Rapportée le 2026-09-21 : « 643 vues de LP pour 5972 clics Spotify, on devrait avoir
    une valeur inférieure ». `lp_views < custom_conversions` sur **91 jours sur 91** :
    ce ne sont pas deux étapes successives, ce sont **deux mesures de la même étape** —
    le pixel Meta (au chargement, bloquable) et l'évènement serveur de Hypeddit (CAPI).
    L'arrivée prend la plus complète des trois sources et dit laquelle.
    """
    meta = _df(db, f"""
        SELECT COALESCE(SUM(impressions), 0) AS impressions,
               COALESCE(SUM(link_clicks), 0) AS link_clicks,
               COALESCE(SUM(lp_views), 0)    AS lp_views,
               COALESCE(SUM(custom_conversions), 0) AS capi,
               SUM(spend) AS spend
          FROM v_meta_campaign_daily
         WHERE artist_id = %s{acct} AND campaign_name = %s AND day BETWEEN %s AND %s
    """, (artist_id, *acct_p, campaign, d0, d1))
    hyp = _df(db, """
        SELECT COALESCE(SUM(visits), 0) AS visits, COALESCE(SUM(clicks), 0) AS clicks
          FROM v_hypeddit_daily
         WHERE artist_id = %s AND campaign_name = %s AND day BETWEEN %s AND %s
    """, (artist_id, campaign, d0, d1))
    m = meta.iloc[0] if not meta.empty else {}
    h = hyp.iloc[0] if not hyp.empty else {}
    out = {k: int(m.get(k, 0) or 0) for k in ("impressions", "link_clicks", "lp_views", "capi")}
    out["spend"] = float(m["spend"]) if len(m) and pd.notna(m["spend"]) else None
    out["visits"], out["store_clicks"] = int(h.get("visits", 0) or 0), int(h.get("clicks", 0) or 0)
    out["arrivals"] = max(out["capi"], out["visits"], out["lp_views"])
    out["source"] = (t("meta_x_spotify.src_capi", "CAPI Hypeddit") if out["arrivals"] == out["capi"]
                     else t("meta_x_spotify.src_hyp", "saisie Hypeddit")
                     if out["arrivals"] == out["visits"]
                     else t("meta_x_spotify.src_pixel", "pixel Meta"))
    # THE STREAMS STEP (R213 lot b): the linked track above its pre-campaign level. Absent
    # without a confirmed link or `BASELINE_MIN_DAYS` days of baseline — never a 0 step.
    out["gain"] = None
    if s4a_song:
        daily = _df(db, """
            SELECT day AS date, streams FROM v_s4a_song_daily
             WHERE artist_id = %s AND song = %s AND day BETWEEN %s AND %s
        """, (artist_id, s4a_song, d0 - _dt.timedelta(days=BASELINE_DAYS), d1))
        out["gain"] = streams_gained(daily, d0, d1)
    out["streams"] = out["gain"]["gained"] if out["gain"] else None
    return out


def _funnel_figure(db, artist_id, m: dict, d0, d1, height: int = 460):
    """The seven steps of `m`, revenue priced at the artist's measured €/stream, the
    cheapest age / country / placement of [d0, d1] on the Meta steps (R567)."""
    from src.dashboard.utils import full_funnel
    from src.dashboard.utils.artist_cashflow import stream_rate
    from src.dashboard.utils.period_side_metrics import period_side_metrics
    from src.dashboard.views.home_meta_advice import best_by_step
    rate = (stream_rate(db, artist_id) or {}).get("eur_par_stream")
    best = best_by_step(period_side_metrics(db, artist_id, d0, d1))
    return full_funnel.figure(full_funnel.steps(m, rate, best), height=height), rate


def _render_funnel(db, artist_id, acct, acct_p, campaign, d0, d1,
                   s4a_song=None) -> None:
    """Budget → impressions → clics → smart link → plateformes → écoutes → revenus (R556).

    LE FUNNEL RÉEL TRAVERSE QUATRE SOURCES : Meta (budget, impressions, clics),
    Hypeddit (visites, clics vers les plateformes), Spotify (écoutes gagnées), le
    distributeur (le €/écoute qui chiffre les revenus).
    """
    st.subheader(t("meta_x_spotify.funnel_header",
                   "🔽 Du budget aux revenus — le parcours complet"))
    m = funnel_measures(db, artist_id, acct, acct_p, campaign, d0, d1, s4a_song)
    fig, rate = _funnel_figure(db, artist_id, m, d0, d1)
    if fig is None:
        st.info(t("meta_x_spotify.funnel_thin",
                  "Pas assez d'étapes mesurées pour dessiner un parcours."))
        return
    charts.plotly_chart(fig, width="stretch")
    st.caption(_funnel_note(db, artist_id, m, rate, d0, d1, s4a_song))


def _funnel_note(db, artist_id, m: dict, rate, d0, d1, s4a_song) -> str:
    note = t("meta_x_spotify.funnel_caption",
             "**% de l'étape d'avant** : sur 100 personnes à l'étape du dessus, combien "
             "passent à celle-ci. **€ l'unité** : le budget divisé par le volume de l'étape — "
             "ce qu'a coûté UN clic, UNE visite. L'arrivée sur le smart link est mesurée par "
             "« {src} », la plus complète des sources disponibles.").format(src=m["source"])
    if m["lp_views"] and m["capi"] and m["lp_views"] < m["capi"]:
        note += " " + t(
            "meta_x_spotify.funnel_lp_note",
            "⚠️ Le pixel Meta ne compte que **{lp}** vues de page pour **{capi}** "
            "évènements renvoyés par la CAPI : le pixel SOUS-COMPTE, il ne mesure pas une "
            "étape suivante.").format(lp=num(m["lp_views"], 0), capi=num(m["capi"], 0))
    if m["gain"] and m["gain"]["gained"] >= 1:
        note += " " + t("meta_x_spotify.funnel_gain_note",
                        "🎧 Les **écoutes gagnées** sont comparées à la moyenne des {n} jours "
                        "d'avant ({b} écoutes/jour) : une hausse qui aurait eu lieu sans la pub "
                        "y est comptée aussi, et un même visiteur écoute plusieurs fois — d'où "
                        "« écoutes par clic » et pas un %.").format(
            n=m["gain"]["baseline_days"],
            b=f"{m['gain']['baseline_per_day']:.1f}".replace(".", ","))
        if rate:
            note += " " + t("meta_x_spotify.funnel_rate_note",
                            "💶 Revenus = écoutes gagnées × **{r} €**, ton revenu par écoute "
                            "mesuré sur les ventes du distributeur.").format(r=num(rate, 5))
    elif s4a_song:
        note += " " + t("meta_x_spotify.funnel_no_gain",
                        "Pas d'étape « écoutes gagnées » : il faut au moins {n} jours "
                        "d'écoutes relevés avant la campagne, et une hausse mesurable.").format(
            n=BASELINE_MIN_DAYS)
    return note + campaign_treasury(db, artist_id, d0, d1, m["spend"])


def _render_pair(db, artist_id, bar) -> None:
    """Two campaigns, two funnels on one row, each on its own dates (fiches 23, 26)."""
    from src.dashboard.utils.full_funnel import indicators
    acct, acct_p = bar.acct()
    st.subheader(t("meta_x_spotify.pair_header", "⚖️ Deux campagnes, deux entonnoirs"))
    for i, (col, campaign) in enumerate(zip(st.columns(2), (bar.campaign, bar.second))):
        with col:
            st.markdown(f"**{campaign}**")
            span = _df(db, "SELECT MIN(day) AS d0, MAX(day) AS d1 FROM v_meta_campaign_daily "
                           f"WHERE artist_id = %s{acct} AND campaign_name = %s AND spend > 0",
                       (artist_id, *acct_p, campaign))
            if span.empty or pd.isna(span.iloc[0]["d0"]):
                st.info(t("meta_x_spotify.pair_none", "Aucune dépense relevée."))
                continue
            d0, d1 = span.iloc[0]["d0"], span.iloc[0]["d1"]
            m = funnel_measures(db, artist_id, acct, acct_p, campaign, d0, d1,
                                _resolve_track(db, artist_id, campaign)[1])
            fig, _ = _funnel_figure(db, artist_id, m, d0, d1, height=400)
            if fig is not None:
                charts.plotly_chart(fig, width="stretch", key=f"pair_funnel_{i}")
            st.caption(f"{format_date(d0)} → {format_date(d1)} · " + " · ".join(
                f"**{k}** {v}" for k, v in indicators(m)))
    st.caption(t("meta_x_spotify.pair_caption",
                 "Chaque campagne sur ses propres dates, du premier au dernier euro dépensé. "
                 "CPM = coût des 1 000 impressions, CPC = coût d'un clic sur la pub, CPR = "
                 "coût d'un clic sortant vers les plateformes."))


# ── Le croisement PAYS — où l'euro rapporte le plus d'écoutes ──────────────────
_PLANCHER = 50.0


def countries_order(meta: pd.DataFrame, top: int = 15) -> pd.DataFrame:
    """R558 — the `top` most spent countries, cheapest listen first, unpriced last. Pure."""
    return (meta.sort_values("spend", ascending=False).head(top)
                .sort_values("cout_par_ecoute", na_position="last"))


def render_countries(db, artist_id, acct, acct_p) -> None:
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

    meta["cout_par_ecoute"] = per_series(
        meta["spend"], pd.to_numeric(meta["streams"], errors="coerce"))
    meta["cpr"] = per_series(meta["spend"], meta["results"])
    # R558 (fiche 45, owner 2026-10-13 : « me placer par Pareto en fonction de l'euro par
    # écoute, comme ça ce serait le premier facteur à focus ») — the 15 most spent
    # countries, CHEAPEST STREAM FIRST; the CPR rides along as a line. A country under the
    # spend floor keeps its place in the order but is drawn grey: its ratio proves nothing.
    meta = countries_order(meta)
    sur = meta["spend"] >= _PLANCHER
    pal = _palette()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=[p if ok else f"{p} ⚠️" for p, ok in zip(meta["pays"], sur)],
        y=meta["cout_par_ecoute"], name=t("meta_x_spotify.c_cost", "€ par écoute"),
        marker_color=[pal["meta"] if ok else "#bdbdbd" for ok in sur],
        customdata=meta[["spend", "streams"]].values,
        hovertemplate=t("meta_x_spotify.c_hover",
                        "%{x}<br>%{y:.4f} € par écoute<br>%{customdata[0]:,.0f} € dépensés"
                        " · %{customdata[1]:,.0f} écoutes<extra></extra>")),
        secondary_y=False)
    fig.add_trace(go.Scatter(
        x=[p if ok else f"{p} ⚠️" for p, ok in zip(meta["pays"], sur)], y=meta["cpr"],
        mode="lines+markers", name=t("meta_x_spotify.c_cpr", "CPR (€/clic sortant)"),
        line=dict(color=_CROSS_INK, width=2), connectgaps=False), secondary_y=True)
    # R568 : the banner and the caption are gone — the axis names the stream source
    # (the distributor: S4A has no country split) and grey bars carry the spend floor.
    fig.update_yaxes(title_text=t("meta_x_spotify.c_cost_src",
                                  "€ par écoute (écoutes iMusician, toutes plateformes)"),
                     rangemode="tozero", secondary_y=False)
    fig.update_yaxes(title_text=t("meta_x_spotify.c_cpr", "CPR (€/clic sortant)"),
                     showgrid=False, rangemode="tozero", title_font=dict(color=_CROSS_INK),
                     tickfont=dict(color=_CROSS_INK), secondary_y=True)
    fig.update_layout(height=480, hovermode="x unified", margin=dict(b=110))
    fig.update_xaxes(tickangle=-35)
    charts.plotly_chart(fig, width="stretch")
