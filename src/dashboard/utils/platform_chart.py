"""La courbe « écoutes par jour, par plateforme » — un seul rendu, deux surfaces.

Type: Utility
Uses: plotly, streamlit, platform_timeseries
Triggers: views/home._section_streams, views/onboarding._step_welcome
Persists in: nothing

La FORME : des aires empilées, comme l'illustration
---------------------------------------------------
Signalé le 2026-09-08 : « ce n'est plus le même graphique, tu m'avais fait un plot qui
montre des courbes superposées des différentes plateformes avec différentes
couleurs ». C'est exact — la figure d'exemple committée
(`assets/examples/dashboard-global.png`, `tools/dev/make_example_charts.py`) est un
`stackplot`, et le premier jet live était fait de lignes qui se croisent. Deux formes
différentes pour la même promesse : l'artiste voyait l'illustration puis autre chose.

L'empilement répond en plus à la question qu'on se pose ici — « combien AU TOTAL, et
qui y contribue » — là où des lignes superposées répondent « laquelle est la plus
haute », qui n'est pas la question de l'accueil.

Les couleurs ne sont pas choisies à l'œil
-----------------------------------------
Ce sont celles de l'illustration, et elles sortent du validateur de la skill `dataviz`
(`node scripts/validate_palette.js "<hex,…>" --mode light|dark`). Le premier jet live
avait pris les couleurs de MARQUE, et il a été **refusé** :

    #1DB954, #FF0000, #FF5500
    [FAIL] CVD separation      #FF5500 ↔ #FF0000  ΔE 4.5 (deutan)
    [FAIL] Normal-vision floor #FF5500 ↔ #FF0000  ΔE 7.4 — en dessous de 15

Le rouge YouTube et l'orange SoundCloud sont indiscernables **même en vision
normale** : deux aires qu'on ne peut pas attribuer, ce qui est la définition d'une
figure illisible.

Le mode sombre a ses PROPRES pas — la bande de clarté y est 0,48–0,67 contre
0,43–0,77 en clair. Seul l'orange bouge (`#eb6834` → `#e05f2b`) : la figure reste la
même d'un thème à l'autre. L'avertissement de contraste du vert oblige un **relief** —
d'où l'étiquette posée sur chaque aire, qui n'est pas décorative.

Un trou est un trou
-------------------
`platform_timeseries` ne produit AUCUN point pour un jour qu'il n'a pas mesuré. La
courbe doit donc être réindexée sur un axe de jours continu avec des `None`, et
`connectgaps=False` : sans ça Plotly relie les deux bords du trou et dessine une
droite qui affirme une continuité qu'on n'a pas mesurée.
"""
from __future__ import annotations

import datetime as _dt
import logging

import streamlit as st

from src.dashboard.utils.platform_timeseries import MISSING_HISTORY, PLATFORM_LABELS

logger = logging.getLogger(__name__)

# Les couleurs de l'illustration committée, validées le 2026-09-08 — « ALL CHECKS
# PASS » sur les six contrôles, dans les deux modes.
_PALETTE_LIGHT = {"spotify": "#2a78d6", "youtube": "#eb6834", "soundcloud": "#1baf7a"}
_PALETTE_DARK = {"spotify": "#2a78d6", "youtube": "#e05f2b", "soundcloud": "#1baf7a"}

# Aucune fenêtre par défaut : « depuis le début » est le choix par défaut du sélecteur
# de l'accueil (`utils/date_range`), et la figure doit dire la même chose que lui.
_DEFAULT_DAYS = None


def _is_dark() -> bool:
    """Le thème du VISITEUR, avec un repli clair — jamais une exception."""
    try:
        theme = getattr(st.context, "theme", None)
        if theme is not None and getattr(theme, "type", None):
            return str(theme.type).lower() == "dark"
    except Exception:      # noqa: BLE001 — versions de Streamlit sans st.context
        pass
    try:
        return str(st.get_option("theme.base") or "").lower() == "dark"
    except Exception:      # noqa: BLE001
        return False


def _continuous(rows: list[tuple], days: list) -> list:
    """La série alignée sur `days`, avec `None` là où rien n'a été mesuré."""
    by_day = dict(rows)
    return [by_day.get(d) for d in days]


# Au-delà de ce nombre de jours, on agrège par SEMAINE. Ce n'est pas un réglage
# esthétique : mesuré sur les séries réelles de l'artiste 1 le 2026-09-08, nos sources
# n'ont pas la même cadence de collecte — Spotify 1 344 mesures sur 1 344 jours (100 %),
# SoundCloud 92 sur 162 (56 %), YouTube 112 sur 283 (39 %). Une bande empilée exige que
# toutes soient mesurées le MÊME jour ; au pas quotidien, « Depuis le début » perdait
# YouTube entièrement et « Cette année » ne dessinait que 165 jours sur 251.
#
# Au pas hebdomadaire, les mêmes données donnent 90 % de semaines complètes sur tout
# l'historique, 100 % sur 30 et 90 jours, et les trois plateformes sont TOUJOURS
# présentes — une plateforme qui apparaît et disparaît selon la période choisie est
# plus déroutante qu'une courbe un peu lissée.
_WEEKLY_ABOVE_DAYS = 92


def margin_labels(order: list, ink: str) -> list:
    """Les étiquettes, espacées dans la marge droite, dans l'ordre visuel de la pile.

    Exportée pour que son garde l'APPELLE : `annotations=` peut être passé avec
    n'importe quoi, et vérifier qu'un mot-clé existe ne dit rien de ce qu'il porte.
    """
    top_first = list(reversed(order))      # l'ordre visuel de la pile, de haut en bas
    step = 1.0 / (len(top_first) + 1)
    return [
        dict(x=1.0, y=1.0 - step * (n + 1), xref="paper", yref="paper",
             xanchor="left", xshift=12,
             text=f"<b>{PLATFORM_LABELS[pkey]}</b>", showarrow=False,
             font=dict(color=ink, size=12), align="left")
        for n, pkey in enumerate(top_first)
    ]


def _monday(day):
    """Le lundi de la semaine de `day` — la clé d'agrégation, écrite une seule fois."""
    return day - _dt.timedelta(days=day.weekday())


def _weekly(series: dict) -> dict:
    """La même série, sommée par semaine (lundi), sans rien inventer.

    Une semaine ne porte que ce qui a été MESURÉ dedans : c'est une somme partielle
    quand un jour manque, jamais une extrapolation. Une semaine sans aucune mesure
    reste absente, donc inconnue, donc elle coupe la bande comme un jour manquant.
    """
    out: dict = {}
    for key, rows in (series or {}).items():
        weeks: dict = {}
        for day, value in rows:
            monday = _monday(day)
            weeks[monday] = weeks.get(monday, 0) + value
        out[key] = sorted(weeks.items())
    return out


def _window(series: dict, days: int | None,
            since=None, until=None, step_days: int = 1) -> tuple:
    """(jours continus, séries alignées).

    `since`/`until` bornent explicitement — c'est le sélecteur de période de l'accueil.
    Sans eux, on retombe sur les `days` derniers jours mesurés ; `days=None` prend tout
    l'historique, ce qui est le défaut « depuis le début ».
    """
    all_days = sorted({d for rows in series.values() for d, _ in rows})
    if not all_days:
        return [], {}
    first, last = all_days[0], all_days[-1]
    if since is not None:
        first = max(first, since)
    if until is not None:
        last = min(last, until)
    if days is not None and since is None:
        first = max(first, last - _dt.timedelta(days=days - 1))
    if first > last:
        return [], {}
    span = [first + _dt.timedelta(days=i)
            for i in range(0, (last - first).days + 1, step_days)]
    return span, {k: _continuous(rows, span) for k, rows in series.items() if rows}


def _measured_range(values: list) -> tuple:
    """(premier, dernier) index mesuré d'une série, ou `(None, None)`."""
    seen = [i for i, v in enumerate(values) if v is not None]
    return (seen[0], seen[-1]) if seen else (None, None)


def known(values: list, index: int) -> bool:
    """Sait-on ce que cette plateforme a fait ce jour-là ?

    Deux absences très différentes se ressemblent dans une liste de `None`, et les
    confondre coûtait tout l'historique :

    * **avant sa première mesure (ou après la dernière)** — la plateforme n'était pas
      encore collectée. Elle n'a rien apporté à ce qu'on peut montrer, et 0 est la
      bonne valeur. Sans cette distinction, SoundCloud — collectée depuis le
      2026-03-31 — coupait la bande sur les 1 142 jours de Spotify qui la précèdent,
      et « Depuis le début » n'affichait plus qu'une seule plateforme ;
    * **entre les deux** — un jour où la collecte n'a pas tourné. Là on ne sait pas, et
      la bande se coupe.
    """
    first, last = _measured_range(values)
    if first is None:
        return False
    if index < first or index > last:
        return True
    return values[index] is not None


def stackable(span: list, aligned: dict) -> tuple:
    """(plateformes empilables, plateformes trop clairsemées) — la règle, une fois.

    « A-t-elle au moins un point ? » était le premier critère, et il était faux : la
    bande se coupe dès qu'UNE plateforme manque, donc une source mesurée deux jours sur
    quatre-vingt-dix vétait les quatre-vingt-sept jours des autres. Mesuré le
    2026-09-08 juste après déploiement — le bac à sable n'avait plus AUCUNE figure
    alors qu'il a 87 jours de Spotify.

    Le critère est donc la COUVERTURE sur la fenêtre, et les distributions réelles ne
    laissent pas d'ambiguïté : 87/90, 90/90 et 82/90 d'un côté ; 2/90 et 4/90 de
    l'autre. Une source trop clairsemée est NOMMÉE plutôt qu'empilée — la même règle
    qu'Apple, qui n'a pas d'historique du tout.

    Exportée, et non repliée dans le rendu, parce que son garde doit l'APPELER : une
    règle recopiée dans un test est une deuxième règle, qui diverge au premier
    changement — c'est exactement ce que ce module reproche à la figure d'exemple.
    """
    order, thin = [], {}
    for key in PLATFORM_LABELS:
        values = aligned.get(key) or []
        first, last = _measured_range(values)
        if first is None:
            continue
        measured = sum(1 for v in values if v is not None)
        own = last - first + 1
        # La couverture se juge sur la plage où la plateforme EXISTE. La juger sur
        # toute la fenêtre punissait une source récente : sur « Depuis le début »
        # (1 254 jours), YouTube et SoundCloud tombaient sous la moitié et
        # disparaissaient d'une figure qu'ils avaient pourtant le droit d'habiter.
        if measured * 2 >= own:
            order.append(key)
        else:
            thin[key] = (PLATFORM_LABELS[key], measured, own)
    return order, thin


def _segments(span: list, aligned: dict, order: list) -> list:
    """Les tranches de jours CONSÉCUTIFS où toutes les aires ont une mesure.

    Une aire empilée n'a pas de trou : le jour où une plateforme n'a pas été mesurée,
    la compter pour zéro ferait plonger le TOTAL, ce qui se lit comme une chute
    d'écoutes. On coupe donc la bande, et le blanc dit « on ne sait pas ».

    Mesuré sur l'artiste 1 le 2026-09-08 : 79 jours complets sur 90, en 2 tranches —
    la bande reste lisible, et les 11 jours manquants ne mentent pas.
    """
    ok = [all(known(aligned[k], i) for k in order) for i in range(len(span))]
    out, cur = [], []
    for i, good in enumerate(ok):
        if good:
            cur.append(i)
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def render_platform_chart(series: dict, *, title: str = "", days=_DEFAULT_DAYS,
                          since=None, until=None,
                          key: str = "platform_chart") -> bool:
    """Empile une aire par plateforme. Rend False si rien n'est traçable.

    L'appelant décide quoi dire quand c'est False — cette fonction n'écrit ni
    « aucune donnée » ni un exemple à la place : les deux se sont déjà lus comme une
    panne ailleurs dans ce dépôt.
    """
    span, aligned = _window(series or {}, days, since, until)
    if not span or not aligned:
        return False
    # Le PAS suit la largeur de la fenêtre, décidée sur la fenêtre réellement obtenue
    # et non sur celle demandée : « depuis le début » n'a pas de nombre de jours.
    weekly = len(span) > _WEEKLY_ABOVE_DAYS
    if weekly:
        # LES BORNES SONT RAMENÉES AU LUNDI, sinon rien ne s'aligne : les semaines sont
        # clavées au lundi et « Cette année » commence un 1ᵉʳ janvier — un jeudi en
        # 2026. La fenêtre parcourait jeudi, jeudi+7, … et ne tombait sur AUCUNE clé.
        # Vu au rendu le 2026-09-08 : « Cette année » et « 12 mois » n'empilaient plus
        # aucune plateforme, tandis que « Depuis le début » (sans borne, donc calée sur
        # une clé existante) fonctionnait. Deux périodes muettes pour un décalage de
        # trois jours.
        w_since = _monday(since) if since is not None else None
        w_until = _monday(until) if until is not None else None
        span, aligned = _window(_weekly(series), None, w_since, w_until, step_days=7)
        if not span or not aligned:
            return False
    try:
        import plotly.graph_objects as go
    except Exception:      # noqa: BLE001 — l'app rend Plotly nativement, mais on ne parie pas
        logger.warning("plotly unavailable — chart skipped")
        return False

    # Ordre FIXE, jamais cyclé, et restreint à ce qui peut ÊTRE EMPILÉ.
    #
    # « A-t-elle au moins un point ? » était le premier critère, et il était faux : la
    # bande se coupe dès qu'UNE plateforme manque, donc une source mesurée deux jours
    # sur quatre-vingt-dix vétait les quatre-vingt-sept jours des autres. Mesuré le
    # 2026-09-08 juste après déploiement — le bac à sable n'avait plus AUCUNE figure
    # alors qu'il a 87 jours de Spotify.
    #
    # Le critère est donc la COUVERTURE sur la fenêtre. Les distributions réelles ne
    # laissent pas d'ambiguïté : 87/90, 90/90 et 82/90 d'un côté ; 2/90 et 4/90 de
    # l'autre. Une source trop clairsemée est NOMMÉE plutôt qu'empilée — la même règle
    # qu'Apple, qui n'a pas d'historique du tout.
    order, thin = stackable(span, aligned)
    if not order:
        return False
    segments = _segments(span, aligned, order)
    if not segments:
        return False

    palette = _PALETTE_DARK if _is_dark() else _PALETTE_LIGHT
    ink = "#E6E6E6" if _is_dark() else "#1a1a19"
    muted = "#9a9a97" if _is_dark() else "#6b6b68"
    surface = "#1a1a19" if _is_dark() else "#fcfcfb"
    grid = "rgba(150,150,150,0.20)"

    fig = go.Figure()
    for pkey in order:
        for n, seg in enumerate(segments):
            fig.add_trace(go.Scatter(
                x=[span[i] for i in seg],
                y=[aligned[pkey][i] or 0 for i in seg],
                name=PLATFORM_LABELS[pkey],
                legendgroup=pkey,
                showlegend=False,             # étiquettes directes — voir plus bas
                mode="lines",
                stackgroup=f"g{n}",           # une pile PAR TRANCHE : la bande se coupe
                line=dict(width=1.6, color=surface),   # le filet de 2 px entre les aires
                fillcolor=palette[pkey],
                # `0` VEUT DIRE ZÉRO ÉCOUTE CE JOUR-LÀ, et rien d'autre : un jour
                # non mesuré n'a pas de point du tout, la bande y est coupée. Le
                # survol le dit, parce que les deux se ressemblent à l'œil —
                # « on a des 0 sur youtube et soundcloud, je pense qu'on a tout
                # simplement pas la data » (2026-09-08). Ici, si : le compteur de la
                # chaîne n'a pas bougé de la journée.
                customdata=[["compteur inchangé" if (aligned[pkey][i] or 0) == 0
                             else ""] for i in seg],
                hovertemplate=("%{y:,} %{customdata[0]}<extra>"
                               + PLATFORM_LABELS[pkey] + "</extra>"),
            ))

    # LES ÉTIQUETTES SONT POSÉES SUR LA FIGURE, pas dans une boîte de légende.
    #
    # C'est la forme de l'illustration, et c'est aussi le correctif du 2026-09-08 :
    # « sur le graphique évolution par plateforme, la légende est masquée, c'est assez
    # moche ». La légende horizontale était ancrée à `y=1.0`, c'est-à-dire dans la
    # marge où vit déjà le titre sur deux lignes — les deux se recouvraient.
    #
    # Une étiquette collée à la bande qu'elle nomme n'a rien à recouvrir, et elle porte
    # le RELIEF qu'exige l'avertissement de contraste du validateur : l'identité d'une
    # aire ne repose alors plus sur sa seule couleur.
    # Espacées dans la MARGE, pas collées au milieu de leur bande.
    #
    # La première version les ancrait au centre de l'aire, ce qui les empilait les unes
    # sur les autres dès qu'une bande devenait fine — vu au rendu : « SoundCloud » et
    # « Spotify » se recouvraient sur la vue « Depuis le début », où YouTube et
    # SoundCloud pèsent quelques écoutes contre plusieurs milliers.
    #
    # C'est aussi ce que fait l'illustration : ses quatre étiquettes sont à des
    # hauteurs fixes à droite, dans l'ordre de la pile. Une étiquette n'a pas à
    # désigner une épaisseur, elle a à nommer une couleur.
    annotations = margin_labels(order, ink)

    total = sum(v for rows in series.values() for d, v in rows if d in set(span))
    fig.update_layout(
        annotations=annotations,
        title=dict(
            # Le `.replace(",", " ")` portait sur TOUT le titre, et mangeait la virgule
            # de « Toutes tes plateformes, un seul écran » — vu au rendu le 2026-09-08.
            # Il ne s'applique qu'au nombre.
            text=(f"<b>{title}</b><br><span style='font-size:12px;color:{muted}'>"
                  f"{format(total, ',').replace(',', chr(8239))} écoutes sur "
                  f"{len(span)} {'semaines' if weekly else 'jours'}</span>"
                  if title else None),
            x=0, xanchor="left"),
        hovermode="x unified",
        height=340,
        # De la place À DROITE pour les étiquettes, et plus de marge haute réservée à
        # une légende qui n'existe plus.
        margin=dict(l=8, r=132, t=58 if title else 12, b=8),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=ink),
        xaxis=dict(showgrid=False, linecolor=grid, title=None),
        yaxis=dict(gridcolor=grid, zeroline=False, title=None, rangemode="tozero"),
    )
    st.plotly_chart(fig, width="stretch", key=key)
    if len(segments) > 1 or len(span) > sum(len(s) for s in segments):
        missing = len(span) - sum(len(s) for s in segments)
        st.caption(t_missing(missing, len(span)))
    for label, measured, total in thin.values():
        st.caption(t_too_thin(label, measured, total))
    return True


def t_too_thin(label: str, measured: int, total: int) -> str:
    """Pourquoi une plateforme n'est pas dans la pile — nommée, jamais tue."""
    from src.dashboard.utils.i18n import t
    return t("platform_chart.too_thin",
             "{label} n'est pas dans la pile : mesurée **{measured} jour(s) sur "
             "{total}**, elle couperait la bande partout. Ses chiffres restent dans "
             "le tableau ci-dessous."
             ).format(label=label, measured=measured, total=total)


def t_missing(missing: int, total: int) -> str:
    """La phrase qui explique le blanc dans la bande — mesurée, pas décorative."""
    from src.dashboard.utils.i18n import t
    return t("platform_chart.gaps",
             "Les zones blanches sont **{missing} jour(s) sur {total}** où au moins "
             "une plateforme n'a pas été mesurée. On préfère un blanc à un zéro : "
             "un zéro dirait « aucune écoute »."
             ).format(missing=missing, total=total)


def render_missing_history_note() -> None:
    """Nomme ce qui n'a PAS de série, plutôt que de le dessiner à zéro.

    Une plateforme absente sans explication se lit comme une panne — c'est la leçon
    de `_silence_reason` et de la matrice d'état, appliquée à une figure.
    """
    for label, why in MISSING_HISTORY.values():
        st.caption(f"{label} — {why}.")
