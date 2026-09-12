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
0,43–0,77 en clair. Seuls l'orange et l'ambre bougent (`#eb6834` → `#e05f2b`,
`#eda100` → `#c08400`) : la figure reste la même d'un thème à l'autre. Le quatrième
emplacement, l'ambre, est celui d'Apple, et c'est le même que la quatrième série de
l'illustration. L'avertissement de contraste du vert oblige un **relief** —
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

from src.dashboard.utils.platform_chart_notes import (      # noqa: F401
    _STEP_BUCKETS, _STEP_UNITS, _render_notes, _render_recap,
    render_missing_history_note, t_coarsened, t_too_coarse, t_too_thin,
)
from src.dashboard.utils.platform_timeseries import (
    PLATFORM_LABELS,
    STEP_ONLY,
)

logger = logging.getLogger(__name__)

# Les couleurs de l'illustration committée, validées le 2026-09-08 — « ALL CHECKS
# PASS » sur les six contrôles, dans les deux modes.
# LA PALETTE SUIT LA MARQUE, autant que la lisibilité le permet — « mets à jour les
# couleurs en fonction de chaque plateforme (youtube rouge…) » (2026-09-12).
#
# Les couleurs de marque EXACTES restent refusées, et c'est mesurable :
#
#     #1DB954 · #FF0000 · #FF5500 · #FA243C
#     youtube ↔ soundcloud   ΔE  9.6 normale ·  4.6 deutan
#     youtube ↔ apple        ΔE  9.0 normale ·  3.0 deutan
#
# Quatre teintes dont trois dans l'arc chaud : un deutéranope ne peut attribuer
# aucune des trois aires. Ce qui a été fait à la place n'est pas « d'autres
# couleurs », c'est la MEILLEURE position dans chaque famille de marque, cherchée
# par balayage sur ~1,7 M de combinaisons sous les contraintes du validateur
# (CIEDE2000 + simulation deutan/protan, bande de clarté par thème) :
#
#     clair   ΔE 16.9  ✅ au-dessus du plancher de 15
#     sombre  ΔE 13.9  ⚠️ EN DESSOUS, et c'est le maximum atteignable
#
# ⚠️ LE MODE SOMBRE NE PEUT PAS TENIR LE PLANCHER, et il faut l'écrire plutôt que
# de le découvrir plus tard : sa bande de clarté est 0,48–0,67 contre 0,43–0,77 en
# clair, soit 0,19 de latitude pour séparer trois teintes chaudes. Le maximum est
# 13,9 avec Apple, 14,6 sans elle. Ce n'est pas un choix de confort — c'est la
# borne, et la rechercher à nouveau redonnera le même nombre.
#
# APPLE EST EN MAGENTA, PAS EN ROUGE, et c'est une conséquence, pas un goût : sa
# marque est un rouge-rose, YouTube prend le rouge, et deux rouges dans la même
# pile sont indiscernables (ΔE 3,0 en deutan avec les teintes exactes). La teinte
# libre la plus proche de sa famille est le magenta.
_PALETTE_LIGHT = {"spotify": "#3acf84", "youtube": "#bd354b", "soundcloud": "#e0631b",
                  "apple": "#bd00a4"}
_PALETTE_DARK = {"spotify": "#268756", "youtube": "#e01b2b", "soundcloud": "#f28100",
                 "apple": "#cf19b6"}

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

# Vers quoi descendre quand le pas demandé ne produit pas assez de seaux pour dessiner
# quoi que ce soit. Du plus grossier au plus fin, en s'arrêtant au premier qui tient.
# Le MOIS est arrivé le 2026-09-12 avec la barre de pas : le sélecteur n'offrait que
# `auto / semaine / année`, et le mois — le pas qu'un artiste demande en premier —
# n'existait nulle part dans ce module.
_FINER_STEPS = {
    "year": ["year", "month", "week", "day"],
    "month": ["month", "week", "day"],
    "week": ["week", "day"],
    "day": ["day"],
}


# `margin_labels` a été RETIRÉE le 2026-09-12. Elle posait dans la marge droite une
# étiquette par plateforme — les mêmes noms que la boîte de légende, qui avait été
# réintroduite en bas le 2026-09-11 pour servir de filtre cliquable. Deux légendes
# disant la même chose, dont une seule est actionnable : « tu peux supprimer la
# légende en doublon car on a déjà la légende cliquable que je préfère ».
#
# La marge droite retombe donc de 132 px à 24 : c'est de la place rendue à la figure.


def unmeasured_spans(aligned: dict, order: list) -> list:
    """Les intervalles d'indices où une plateforme DÉJÀ APPARUE n'a pas de mesure.

    C'est la réponse en PIXELS à « on ne voit pas la différence entre zéro et pas de
    donnée ». Jusqu'ici la bande se coupait — bien — mais `stackgroup` infère zéro
    pour la plateforme manquante, donc **le total empilé redescend** et se lit comme
    une chute. Le seul rattrapage était une phrase sous la figure.

    `known()` fait déjà la distinction qui compte : avant la première mesure d'une
    plateforme, zéro est vrai (elle n'existait pas dans nos données) ; entre deux
    mesures et après la dernière, on ne sait pas. On ne hachure que le second cas.

    Rend des intervalles FERMÉS `(début, fin)` sur les indices de `span`, fusionnés :
    trois jours manquants d'affilée font une bande, pas trois.
    """
    holes = sorted({
        i for pkey in order
        for i in range(len(aligned.get(pkey) or []))
        if not known(aligned[pkey], i)
    })
    if not holes:
        return []
    spans, start, prev = [], holes[0], holes[0]
    for i in holes[1:]:
        if i == prev + 1:
            prev = i
            continue
        spans.append((start, prev))
        start = prev = i
    spans.append((start, prev))
    return spans


def _hatch_traces(spans: list, span: list, ceiling: float, ink: str,
                  legend: bool = True) -> list:
    """Une trace hachurée par intervalle non mesuré, posée SOUS les aires.

    ⚠️ Pourquoi une trace et pas un `add_vrect` : une SHAPE Plotly ne supporte pas
    `fillpattern` — vérifié le 2026-09-12 sur la version de production (5.24.1) et en
    local (6.5.2). `Scatter.fillpattern`, lui, est supporté des deux côtés. Le
    rectangle est donc une trace fermée, hors `stackgroup` pour ne pas entrer dans la
    pile, et `hoverinfo="skip"` pour ne rien affirmer au survol.
    """
    import plotly.graph_objects as go      # paresseux, comme dans la figure

    from src.dashboard.utils.i18n import t
    label = t("platform_chart.unmeasured", "▨ Aucune mesure")
    out = []
    for n, (a, b) in enumerate(spans):
        # Le seau est élargi d'un demi-pas de chaque côté quand c'est possible : un
        # trou d'un seul jour doit rester visible, et un rectangle de largeur nulle
        # ne se voit pas.
        x0 = span[max(a - 1, 0)] if a > 0 else span[a]
        x1 = span[min(b + 1, len(span) - 1)] if b < len(span) - 1 else span[b]
        out.append(go.Scatter(
            x=[x0, x1, x1, x0, x0],
            y=[0, 0, ceiling, ceiling, 0],
            mode="lines",
            line=dict(width=0),
            fill="toself",
            fillcolor="rgba(0,0,0,0)",
            fillpattern=dict(shape="/", size=7, solidity=0.12,
                             fgcolor=ink, bgcolor="rgba(0,0,0,0)"),
            hoverinfo="skip",
            # UNE SEULE entrée, et elle n'est pas cliquable en mode « part » : la
            # légende y est désactivée en entier, parce qu'un clic masquerait une
            # trace sans recalculer les parts.
            showlegend=legend and n == 0,
            name=label,
            legendgroup="__unmeasured__",
        ))
    return out


def _unmeasured_hover(spans: list, span: list) -> object:
    """Une trace invisible qui DIT, au survol, que le pas n'a pas été mesuré.

    La hachure se voit, elle ne se survole pas : un rectangle n'a que quatre coins,
    donc en `hovermode="x unified"` il ne contribue à aucune des colonnes entre les
    deux. L'artiste survolait un trou et lisait « 0 » — le chiffre qu'on avait
    justement cessé de dessiner. « Clarifier le 0 » (2026-09-12).

    Cette trace porte un point à CHAQUE pas non mesuré, à hauteur zéro, invisible
    (`marker` transparent, taille nulle) et hors `stackgroup` pour ne rien ajouter à
    la pile. Son seul travail est d'exister sous le curseur.
    """
    import plotly.graph_objects as go

    from src.dashboard.utils.i18n import t
    holes = sorted({i for a, b in spans for i in range(a, b + 1)})
    return go.Scatter(
        x=[span[i] for i in holes], y=[0] * len(holes),
        mode="markers", marker=dict(size=0.1, color="rgba(0,0,0,0)"),
        showlegend=False, legendgroup="__unmeasured__",
        hovertemplate="<b>" + t("platform_chart.no_data_hover",
                                "Pas de donnée récoltée sur cette période")
                      + "</b><extra></extra>",
    )


def _monday(day):
    """Le lundi de la semaine de `day` — la clé d'agrégation, écrite une seule fois."""
    return day - _dt.timedelta(days=day.weekday())


def _bucket_key(day, step: str):
    """Le point auquel ce jour appartient, selon le pas."""
    if step == "year":
        return _dt.date(day.year, 1, 1)
    if step == "month":
        return _dt.date(day.year, day.month, 1)
    if step == "week":
        return _monday(day)
    return day


# Un seau (semaine, année) doit être mesuré sur AU MOINS cette part des jours qu'il
# contient pour être tracé. En dessous, on ne sait pas ce qu'il vaut.
#
# Calibré sur les distributions réelles de l'artiste 1, mesurées le 2026-09-08, et non
# choisi d'instinct — c'est la leçon du plancher de 30 lignes/jour écrit à l'aveugle,
# qui rendait un détecteur aveugle à deux locataires sur trois :
#
#   spotify     180 semaines · 179 à 7 jours sur 7, 1 à 1 jour (la semaine tronquée du
#               bord de fenêtre, donc complète pour ce qu'elle peut contenir) → 100 %
#   youtube      10 semaines · 1,1,1,1,2,2,2,3,5,6 jours — AUCUNE à 7
#   soundcloud    5 semaines · 1,1,2,3,5 jours
#
# Une semaine YouTube mesurée 1 jour sur 7 était tracée comme une semaine pleine :
# elle sous-estime d'un facteur ~7, et rien ne le disait. À 50 %, Spotify garde ses
# 180 semaines, YouTube en garde 2 et SoundCloud 1 — ce qu'ils ont vraiment.
_BUCKET_FLOOR = 0.5


def _bucket_days(key, step: str, lo, hi) -> int:
    """Combien de jours ce seau CONTIENT, dans la plage utile.

    Les bords comptent pour ce qu'ils peuvent : la première semaine d'une plateforme
    branchée un jeudi, ou la dernière semaine d'une fenêtre qui s'arrête un mardi, ne
    sont pas incomplètes — elles sont courtes. Les punir supprimerait un seau juste à
    chaque extrémité de chaque série.
    """
    if step == "year":
        start, end = _dt.date(key.year, 1, 1), _dt.date(key.year, 12, 31)
    elif step == "month":
        # 28, 29, 30 ou 31 : le mois est le seul pas dont la longueur dépend du mois
        # lui-même. Le dernier jour se trouve en reculant d'un jour depuis le 1ᵉʳ du
        # suivant, ce qui est juste aussi en février d'une année bissextile.
        nxt = (_dt.date(key.year + 1, 1, 1) if key.month == 12
               else _dt.date(key.year, key.month + 1, 1))
        start, end = key, nxt - _dt.timedelta(days=1)
    else:
        start, end = key, key + _dt.timedelta(days=6)
    start, end = max(start, lo), min(end, hi)
    return (end - start).days + 1 if end >= start else 0


def _aggregate(series: dict, step: str, since=None, until=None) -> dict:
    """La même série, sommée par semaine ou par année, sans rien inventer.

    Un seau ne porte que ce qui a été MESURÉ dedans. Il était donc tracé comme un seau
    plein alors qu'il pouvait n'en couvrir qu'un septième — **38 %** des semaines
    YouTube et **31 %** des semaines SoundCloud étaient dans ce cas au 2026-09-08, et
    la figure ne le disait nulle part. Sous `_BUCKET_FLOOR`, le seau est rendu INCONNU
    (absent) plutôt que faux : l'aire s'y interrompt, comme un jour non mesuré.

    C'est aussi pourquoi la conversion cumul → quotidien ne rattrape rien : un delta
    n'est calculé qu'entre deux jours CONSÉCUTIFS, donc les jours sautés ne sont pas
    reportés sur le suivant — ils manquent pour de bon.
    """
    def _in_window(rows):
        """Les lignes de la FENÊTRE, et rien d'autre.

        Le défaut que cette fonction retire, mesuré le 2026-09-10 : la boucle ci-dessous
        sommait TOUTE la série dans ses seaux, `since`/`until` ne servant qu'au plancher.
        Combiné au ramenage des bornes au lundi ou au 1ᵉʳ janvier (`_bucket_key` sur
        `since`, qui recule), la fenêtre s'élargissait au lieu que le seau se découpe :

            « 12 mois » au pas annuel  →  seau 2025-01-01  →  TOUTE l'année 2025
            8 490 écoutes mesurées dans la fenêtre, 23 251 dessinées — ×2,7

        Découper ici corrige aussi le plancher : `counts[k]` comptait des jours hors
        fenêtre, donc un seau de bord paraissait plus rempli qu'il ne l'est.
        """
        return [(d, v) for d, v in rows
                if (since is None or d >= since) and (until is None or d <= until)]

    if step == "day":
        return {k: _in_window(rows) for k, rows in (series or {}).items()}
    out: dict = {}
    for key, rows in (series or {}).items():
        rows = _in_window(rows)
        if not rows:
            out[key] = []
            continue
        if STEP_ONLY.get(key) == step:
            # Sa série EST déjà au grain du seau : Apple ne produit pas des jours qu'on
            # somme, il produit un total par année. Lui appliquer le plancher
            # supprimerait chacun de ses points (1 « jour » mesuré sur 365) — la mesure
            # est complète, c'est l'unité qui diffère.
            out[key] = sorted(rows)
            continue
        days = [d for d, _ in rows]
        lo, hi = min(days), max(days)
        if since is not None:
            lo = max(lo, since)
        if until is not None:
            hi = min(hi, until)
        sums: dict = {}
        counts: dict = {}
        for day, value in rows:
            k = _bucket_key(day, step)
            sums[k] = sums.get(k, 0) + value
            counts[k] = counts.get(k, 0) + 1
        out[key] = [(k, sums[k]) for k in sorted(sums)
                    if (n := _bucket_days(k, step, lo, hi))
                    and counts[k] >= n * _BUCKET_FLOOR]
    return out


def _weekly(series: dict) -> dict:
    """Conservée : `_aggregate(series, "week")`, sous son ancien nom."""
    return _aggregate(series, "week")


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

    * **avant sa première mesure** — la plateforme n'était pas encore collectée. Elle
      n'a rien apporté à ce qu'on peut montrer, et 0 est la bonne valeur. Sans cette
      distinction, SoundCloud — collectée depuis le 2026-03-31 — coupait la bande sur
      les 1 142 jours de Spotify qui la précèdent, et « Depuis le début » n'affichait
      plus qu'une seule plateforme ;
    * **entre les deux** — un jour où la collecte n'a pas tourné. Là on ne sait pas, et
      la bande se coupe ;
    * **après la dernière mesure** — on ne sait pas non plus, et c'est le cas que cette
      fonction traitait comme le premier.

    Les deux extrémités ne sont PAS symétriques, et la version précédente les traitait
    du même argument. Avant la première mesure, zéro est vrai : la plateforme n'existait
    pas dans nos données. Après la dernière, la plateforme existe toujours — c'est NOUS
    qui avons cessé de la mesurer. Prouvé par exécution le 2026-09-10 : YouTube mesurée
    les 5 premiers jours d'une fenêtre de 20 donnait, en mode Cumulé (le défaut),

        cumulé  [10, 20, 30, 40, 50, None × 15]
        TRACÉ   [10, 20, 30, 40, 50,   0 × 15]   ← une seule tranche continue

    c'est-à-dire une bande qui monte puis **retombe à zéro** — « YouTube a perdu toutes
    ses écoutes ». En mode Par période, les mêmes jours étaient tracés `0` avec
    l'infobulle « compteur inchangé », qui affirme une mesure qu'on n'a pas faite.
    """
    first, last = _measured_range(values)
    if first is None:
        return False
    if index < first:
        return True
    if index > last:
        return False
    return values[index] is not None


# Une aire a besoin de DEUX points consécutifs pour exister : entre eux il y a une
# surface, sous un point isolé il n'y a rien. C'est le seul seuil qui reste, et il
# n'est pas un jugement de qualité — c'est une contrainte de la forme.
_MIN_POINTS = 2


def stackable(span: list, aligned: dict) -> tuple:
    """(plateformes traçables, plateformes qui ne peuvent rien dessiner).

    Cette fonction a porté deux règles fausses coup sur coup, et la seconde était une
    conséquence de la première.

    1. « A-t-elle au moins un point ? » — faux tant que la bande était COMMUNE : une
       source mesurée 2 jours sur 90 vétait les 87 jours des autres.
    2. « Couvre-t-elle la moitié de sa plage ? » — le correctif de (1), et il exclut
       YouTube (24 jours mesurés sur 195) et SoundCloud (12 sur 74) de TOUTES les vues.
       C'est précisément la plainte du 2026-09-08 : « je ne vois que Spotify ».

    Les deux existaient pour la même raison : un trou coupait tout le monde. Depuis que
    `_segments` coupe PAR PLATEFORME, un trou n'appartient plus qu'à sa source — la
    clairsemée ne coûte plus rien à personne, et l'écarter ne protège plus rien. Il ne
    reste donc que la contrainte de forme : deux points, sinon il n'y a pas d'aire.

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
        if measured >= _MIN_POINTS:
            order.append(key)
        else:
            thin[key] = (PLATFORM_LABELS[key], measured, last - first + 1)
    return order, thin


def _segments(span: list, aligned: dict, order: list) -> dict:
    """Les tranches de pas consécutifs mesurés, **par plateforme**.

    Elles étaient communes, et c'est le défaut que l'artiste a signalé le 2026-09-08 :
    « il y a un gros trou dans les données de S4A ». Il n'y en a aucun — mesuré le même
    jour, S4A a 365 / 366 / 365 / 248 jours consécutifs depuis le 2023-01-01, pas un
    seul manquant. Le trou était dans la FIGURE : une seule tranche commune signifie
    qu'un jour où YouTube n'a pas tourné coupe aussi Spotify. Sur la fenêtre
    hebdomadaire, **19 semaines** de Spotify disparaissaient ainsi, dont **13** dont
    YouTube était le seul responsable, et **0** où Spotify lui-même manquait.

    Chaque plateforme porte donc ses propres coupures. La contrepartie est assumée et
    doit être DITE : Plotly empile par `stackgroup`, donc le total d'un jour incomplet
    est celui des plateformes présentes ce jour-là — la bande y descend sans qu'aucune
    écoute ait disparu. C'est la BANDE HACHURÉE qui le montre (`unmeasured_spans`), et
    le récapitulatif qui le chiffre. `t_missing` le disait en prose jusqu'au
    2026-09-12.
    """
    out = {}
    for key in order:
        values = aligned.get(key) or []
        runs, cur = [], []
        for i in range(len(span)):
            if known(values, i):
                cur.append(i)
            elif cur:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        out[key] = runs
    return out


def gap_counts(span: list, aligned: dict, order: list) -> dict:
    """Combien de pas chaque plateforme empilée ne peut pas renseigner, dans sa plage.

    Séparée du rendu parce que son garde doit l'APPELER : recopier la règle dans un
    test en ferait une seconde règle, qui diverge au premier changement.
    """
    return {key: sum(1 for i in range(len(span)) if not known(aligned.get(key) or [], i))
            for key in order}


# Les quatre façons de lire la même donnée. Chacune répond à une question différente,
# et les deux dernières existent pour une raison MESURÉE : sur l'artiste 1, Spotify
# pèse 99,74 % du total, YouTube 0,22 %, SoundCloud 0,04 %. À l'échelle linéaire, deux
# plateformes sur trois sont sous le pixel — « je ne vois que Spotify » n'était pas un
# bug d'affichage, c'était l'échelle.
#
# `share` a d'abord été présenté comme la réponse (« une part de 100 % le fait par
# construction »). C'était faux, et il a fallu REGARDER la figure pour le voir : une
# part de 0,26 % occupe 0,26 % de la hauteur, en pourcentage comme en écoutes. Le mode
# reste utile pour lire une bascule entre plateformes comparables ; il ne rend rien
# visible ici.
#
# La forme qui répond vraiment est celle que la littérature de dataviz prescrit pour
# des séries d'ampleurs incomparables — les PETITS MULTIPLES : une facette par
# plateforme, chacune sur SA propre échelle. On perd la lecture du total (c'est
# précisément le mode « Cumulé ») et on gagne la seule chose que les trois autres ne
# peuvent pas donner : voir bouger une plateforme mille fois plus petite. C'est aussi
# la seule alternative admissible au double axe, que ce module n'utilisera jamais.
MODES = {
    "cumulative": "Cumulé",
    "absolute": "Par période",
    "share": "Part de chaque plateforme",
    "facets": "Chacune à son échelle",
}

# `_UNSTACKED = {"share", "facets"}` vivait ici, déclarée pour piloter le sous-titre et
# LUE NULLE PART — la logique a fini écrite en ligne (`mode == "share"`). Retirée le
# 2026-09-10, et pas seulement parce qu'elle était morte : son contenu était FAUX.
# `share` empile, à 100 % même ; seul `facets` n'empile pas. Une constante morte est du
# bruit, une constante morte et fausse enseigne quelque chose de faux au premier lecteur
# qui la croit. Le seul mode qui n'empile pas se lit désormais où il est utilisé.


def _carry_forward(span: list, rows: list, step: str) -> list:
    """Le niveau cumulé connu à chaque point de l'axe. `None` avant la 1ʳᵉ mesure.

    `rows` est une série CUMULÉE — pas des quantités à sommer. Un seau prend donc le
    DERNIER relevé qui y tombe, et un seau sans relevé garde celui d'avant : entre
    deux collectes, le compteur n'est pas inconnu, il n'a simplement pas été relu.
    Les relevés antérieurs à la fenêtre comptent aussi — ils fixent le niveau de
    départ, sans quoi une fenêtre bornée ferait repartir le cumul de zéro.
    """
    pairs = [(_bucket_key(d, step), v) for d, v in sorted(rows)]
    out, i, last = [], 0, None
    for key in span:
        while i < len(pairs) and pairs[i][0] <= key:
            last = pairs[i][1]
            i += 1
        out.append(last)
    return out


def _as_mode(aligned: dict, order: list, mode: str,
             cumulative: dict | None = None, span: list | None = None,
             step: str = "day") -> dict:
    """Les mêmes séries, lues selon le mode. `None` reste `None` : on n'invente rien.

    LE CUMUL NE SE DÉDUIT PAS TOUJOURS DU QUOTIDIEN, et c'est le défaut que l'artiste
    a signalé le 2026-09-11 : « j'ai le cumulé pour Spotify mais YouTube j'ai des
    valeurs incohérentes et idem pour SoundCloud ».

    Pour Spotify, la somme courante des jours EST le cumul : S4A livre des quantités
    quotidiennes, toutes les journées sont là. Pour YouTube et SoundCloud, non. Leur
    série quotidienne est une DIFFÉRENCE de compteurs, et cette différence n'est
    honnête qu'entre deux jours consécutifs (`_SQL_YOUTUBE`) — les 61 % de journées
    non collectées sont jetées pour de bon, pour ne pas inventer un pic. Les cumuler
    revient donc à additionner ce qui reste : **136** affichés pour l'artiste 1 quand
    le produit en compte **118 219** partout ailleurs. Un facteur 870.

    La couche or sait, elle, ce que vaut le compteur à chaque date
    (`platform_timeseries.youtube_cumulative_views`). Quand l'appelant la fournit, le
    mode cumulé la LIT au lieu de la reconstruire — c'est ADR-019 appliqué aux séries.
    Sans elle, on retombe sur la somme courante, correcte pour les sources
    véritablement quotidiennes.
    """
    if mode == "cumulative":
        out = {}
        for key, values in aligned.items():
            gold = (cumulative or {}).get(key)
            if gold and span is not None:
                out[key] = _carry_forward(span, gold, step)
                continue
            total, acc = 0, []
            for v in values:
                if v is None:
                    # Un trou ne remet pas le cumul à zéro et n'invente pas de valeur :
                    # la courbe s'interrompt, le total reprend où il en était.
                    acc.append(None)
                    continue
                total += v
                acc.append(total)
            out[key] = acc
        return out
    if mode == "share":
        out = {k: list(v) for k, v in aligned.items()}
        for i in range(len(next(iter(aligned.values()), []))):
            # UNE PART SE CALCULE SUR UN TOUT CONNU. Compter une plateforme non
            # mesurée pour 0 au dénominateur gonfle la part des présentes — elles se
            # partagent 100 % sans que rien ne le dise. Si une plateforme attendue
            # manque à ce pas, le pas entier est inconnu, pour tout le monde.
            if any(not known(aligned[k], i) for k in order):
                for k in order:
                    out[k][i] = None
                continue
            total = sum(aligned[k][i] or 0 for k in order)
            for k in order:
                out[k][i] = None if aligned[k][i] is None else (
                    100.0 * aligned[k][i] / total if total else 0.0)
        return out
    return aligned


def render_platform_chart(series: dict, *, title: str = "", days=_DEFAULT_DAYS,
                          since=None, until=None, only=None, step=None,
                          mode: str = "cumulative",
                          cumulative: dict | None = None,
                          discarded: dict | None = None,
                          recap=None, recap_extra=None,
                          key: str = "platform_chart") -> bool:
    """Empile une aire par plateforme. Rend False si rien n'est traçable.

    L'appelant décide quoi dire quand c'est False — cette fonction n'écrit ni
    « aucune donnée » ni un exemple à la place : les deux se sont déjà lus comme une
    panne ailleurs dans ce dépôt.
    """
    span, aligned = _window(series or {}, days, since, until)
    if not span or not aligned:
        return False
    # LE VERDICT D'EMPILEMENT SE PREND SUR LES JOURS, avant toute agrégation.
    #
    # Il se prenait sur la série agrégée, et il annonçait alors autre chose que ce
    # qu'il faisait : « mesurée 5 semaines sur 26 » quand la couverture réelle en jours
    # valait 43 %. Pire, un seau partiel comptait pour un seau mesuré — la couverture
    # paraissait meilleure au pas hebdomadaire qu'au pas quotidien, sur exactement les
    # mêmes données.
    order, thin = stackable(span, aligned)
    # Le PAS suit la largeur de la fenêtre, décidée sur la fenêtre réellement obtenue
    # et non sur celle demandée : « depuis le début » n'a pas de nombre de jours.
    # Le pas : imposé par l'appelant, sinon déduit de la largeur de la fenêtre.
    step = step or ("week" if len(span) > _WEEKLY_ABOVE_DAYS else "day")
    daily_span, daily_aligned = span, aligned
    coarsened = None
    # UN PAS QUI NE PRODUIT QU'UN SEUL SEAU NE PEUT RIEN DESSINER, et on descend.
    #
    # Signalé au rendu : « cumulé, par année, cette année — je ne vois aucune data pour
    # Spotify, YouTube, SoundCloud ». Reproduit : le pas annuel sur une période d'un an
    # rend UN point par plateforme, et sous un point isolé il n'y a pas de surface. Les
    # séries se voyaient déjà refuser une aire à moins de deux mesures (`_MIN_POINTS`) ;
    # la même contrainte de forme n'était pas appliquée à l'AXE, et la figure sortait
    # vide sans rien dire.
    #
    # On descend donc au pas immédiatement plus fin plutôt que de rendre une page
    # muette — au pas hebdomadaire, la même période porte 24 points sur les trois
    # plateformes. Le choix de l'utilisateur n'est pas ignoré en silence : `t_coarsened`
    # le dit, et nomme ce que le pas plus fin coûte (Apple n'existe qu'au pas annuel).
    # ⚠️ LE SEAU D'UNE PLATEFORME SERVIE PAR LA COUCHE OR EXISTE MÊME SANS SÉRIE
    # QUOTIDIENNE — et l'oublier annule tout le correctif ci-dessous.
    #
    # Mesuré le 2026-09-12 sur l'artiste 471 : sept collectes YouTube réparties sur
    # 24 jours, dont DEUX consécutives. La série quotidienne ne porte donc que deux
    # points, le seau hebdomadaire n'en fait qu'un, `len(span) >= _MIN_POINTS` échoue,
    # le pas DÉGRADE vers le jour — et au pas jour la dérivation par les niveaux est
    # désactivée par construction. Résultat : la figure totalise **11 053** là où le
    # compteur a gagné **33 697 394**. Facteur **3 049**, sur une plateforme dont les
    # niveaux sont pourtant denses tous les jours depuis la première mesure.
    #
    # C'est le même défaut que celui corrigé trente lignes plus bas, à un étage de
    # plus : un verdict pris sur la série QUOTIDIENNE appliqué à une plateforme dont
    # la forme de mesure est un NIVEAU. Ici il ne vidait pas le seau, il supprimait
    # le pas tout entier.
    #
    # Les dates des niveaux entrent donc dans le calcul du span. Elles n'ajoutent
    # aucune donnée — `_continuous` et `_carry_forward` remplissent ensuite — elles
    # disent seulement « ce pas a de quoi être tracé ».
    _level_days = sorted({d for rows in (cumulative or {}).values() for d, _ in rows})
    for candidate in _FINER_STEPS.get(step, [step]):
        span, aligned = daily_span, daily_aligned
        if candidate != "day":
            # LES BORNES SONT RAMENÉES AU LUNDI, sinon rien ne s'aligne : les semaines
            # sont clavées au lundi et « Cette année » commence un 1ᵉʳ janvier — un jeudi
            # en 2026. La fenêtre parcourait jeudi, jeudi+7, … et ne tombait sur AUCUNE
            # clé. Vu au rendu le 2026-09-08 : « Cette année » et « 12 mois »
            # n'empilaient plus aucune plateforme, tandis que « Depuis le début » (sans
            # borne, donc calée sur une clé existante) fonctionnait. Deux périodes
            # muettes pour un décalage de trois jours.
            w_since = _bucket_key(since, candidate) if since is not None else None
            w_until = _bucket_key(until, candidate) if until is not None else None
            if candidate in ("year", "month"):
                # Un pas ANNUEL ou MENSUEL ne se parcourt pas en jours fixes : 365 ou
                # 366, 28 à 31. On construit donc l'axe sur les clés de seau
                # réellement présentes, jamais par incréments.
                agg = _aggregate(series, candidate, since, until)
                years = sorted({d for rows in agg.values() for d, _ in rows
                                if (w_since is None or d >= w_since)
                                and (w_until is None or d <= w_until)})
                span = sorted(set(years) | {
                    _bucket_key(d, candidate) for d in _level_days
                    if (w_since is None or _bucket_key(d, candidate) >= w_since)
                    and (w_until is None or _bucket_key(d, candidate) <= w_until)})
                aligned = {k: _continuous(rows, span) for k, rows in agg.items() if rows}
            else:
                bucketed = _aggregate(series, candidate, since, until)
                if _level_days:
                    # Une entrée à ZÉRO aux bornes des niveaux : elle n'affirme rien —
                    # `_as_mode` réécrit entièrement la bande des plateformes servies
                    # à partir de leurs niveaux — elle étend seulement l'axe pour que
                    # le pas demandé ait de quoi exister.
                    edge = "__levels__"
                    bucketed = dict(bucketed)
                    bucketed[edge] = [(_bucket_key(d, candidate), 0)
                                      for d in (_level_days[0], _level_days[-1])]
                span, aligned = _window(bucketed, None, w_since, w_until, step_days=7)
                aligned.pop("__levels__", None)
        if span and aligned and len(span) >= _MIN_POINTS:
            if candidate != step:
                coarsened = (step, candidate)
            step = candidate
            break
    else:
        return False
    if not span or not aligned:
        return False
    try:
        import plotly.graph_objects as go
    except Exception:      # noqa: BLE001 — l'app rend Plotly nativement, mais on ne parie pas
        logger.warning("plotly unavailable — chart skipped")
        return False

    # Ordre FIXE, jamais cyclé, et restreint à ce qui peut ÊTRE EMPILÉ (`order`/`thin`
    # ont été décidés plus haut, sur les JOURS). Une plateforme trop clairsemée est
    # NOMMÉE plutôt qu'empilée — la même règle qu'Apple, qui n'a pas d'historique.
    # Une plateforme qui ne vit QU'À CE PAS n'a pas de couverture quotidienne à juger :
    # Apple n'a que 3 points sur 1 254 jours, ce qui la ferait écarter comme
    # clairsemée alors qu'au pas annuel elle est complète. Elle rejoint la pile ici.
    # Une plateforme peut avoir assez de jours et AUCUN seau assez rempli : YouTube a
    # 24 jours mesurés, répartis sur deux années civiles dont aucune n'atteint la
    # moitié — un total annuel bâti sur 15 jours sur 163 serait ~10× trop bas. Elle
    # disparaît alors de CE pas, et il faut le dire plutôt que la laisser manquer.
    coarse = [k for k in order if k not in aligned]

    # UNE PLATEFORME SERVIE PAR LA COUCHE OR EST JUGÉE SUR LA COURBE QU'ON TRACE.
    #
    # Les deux verdicts ci-dessus portent sur la série QUOTIDIENNE : `stackable` écarte
    # ce qui est trop clairsemé pour faire une aire, et `_aggregate` vide un seau
    # mesuré à moins de la moitié. Les deux sont justes pour des quantités — un jour
    # non collecté est une ignorance. Ils ne le sont pas pour un NIVEAU : entre deux
    # relevés le compteur est connu, donc la courbe cumulée a un point à chaque pas
    # depuis sa première mesure, et elle est dense par construction.
    #
    # Sans cette admission, le correctif du cumul ne serait jamais visible là où il
    # compte : YouTube est relevée 39 % des jours, donc elle est écartée comme
    # clairsemée ou vidée par le plancher de seau — « je n'ai aucune data pour les
    # autres plateformes », signalé le 2026-09-11 sur « Par période », « par année » et
    # « par semaine ». C'est le même geste que pour Apple juste en dessous : une
    # plateforme dont la forme de mesure diffère n'a pas à passer l'examen des autres.
    # « PAR PÉRIODE » AUSSI, DÈS QUE LE SEAU EST PLUS LARGE QU'UN JOUR.
    #
    # Mesuré le 2026-09-11 sur l'artiste 1, « Depuis le début » (pas hebdomadaire) :
    # la somme des seaux YouTube vaut **124** quand le compteur a gagné **18 740**.
    # Facteur **151**. La bande est alors à 0,14 % de Spotify, c'est-à-dire sous le
    # pixel — « je n'ai aucune data sur YouTube ».
    #
    # La raison est celle du cumulé : un écart quotidien n'existe qu'entre deux jours
    # CONSÉCUTIFS, et YouTube n'est relevée que 39 % des jours. Mais la croissance
    # d'un compteur sur un SEAU est dérivable de ses niveaux, exactement comme elle
    # l'est sur une fenêtre — c'est la même règle que `platform_totals` borné.
    #
    # ⚠️ PAS AU PAS QUOTIDIEN, et c'est la limite du raisonnement. Entre deux relevés
    # distants de neuf jours, attribuer tout l'écart au jour du second relevé
    # inventerait un pic. À la semaine, l'écart est attribué à la semaine où il a été
    # OBSERVÉ, ce qui est une approximation qu'on assume : l'alternative mesurée est
    # de sous-déclarer d'un facteur 151. Au jour, on garde les écarts honnêtes, et la
    # note « écoutes non traçables » continue de dire ce qui manque.
    _has_gold = [k for k, rows in (cumulative or {}).items() if rows]
    served = _has_gold if (mode == "cumulative" or step != "day") else []
    for k in served:
        aligned.setdefault(k, [None] * len(span))

    if served and mode != "cumulative":
        # Le seau porte la CROISSANCE du compteur : niveau à la fin du seau moins
        # niveau à la fin du précédent.
        #
        # LE PREMIER SEAU A UN PRÉDÉCESSEUR, et le nier coûtait de vraies écoutes.
        # Il était rendu `None` — « pas de seau avant, donc croissance inconnue » —
        # ce qui est faux dès que la série cumulée commence DANS ce seau : entre son
        # premier relevé et la fin du seau, la croissance est observée. Tant que la
        # dégradation tombait sur la semaine, le manque restait sous le pour-cent et
        # personne ne le voyait ; en ouvrant le pas MOIS le 2026-09-12 il est passé
        # à **12 %** sur un locataire réel — 182 432 dessinés contre 206 555 gagnés,
        # et `test_every_way_of_asking_gives_one_answer` l'a nommé.
        #
        # Le niveau d'entrée est donc le dernier relevé à ou avant le début de la
        # fenêtre ; à défaut, le premier relevé de la série, qui tombe alors dans le
        # premier seau. Reste `None` quand la série commence APRÈS le premier seau —
        # là, la croissance y est réellement inconnue.
        for k in served:
            levels = _carry_forward(span, cumulative[k], step)
            rows = sorted(cumulative[k])
            earlier = [v for d, v in rows if d < span[0]]
            base = earlier[-1] if earlier else (rows[0][1] if rows else None)
            growth, prev = [], base
            for cur in levels:
                growth.append(None if prev is None or cur is None
                              else max(cur - prev, 0))
                prev = cur
            aligned[k] = growth

    order = [k for k in PLATFORM_LABELS
             if k in aligned and (k in order or k in served or STEP_ONLY.get(k) == step)]
    thin = {k: v for k, v in thin.items() if k in aligned and k not in order}
    # `coarse` a été décidé AVANT l'admission, donc il nomme encore les plateformes
    # qu'on vient de réintégrer. Mesuré le 2026-09-11 au pas ANNUEL : la figure traçait
    # YouTube et SoundCloud, et affichait sous elle « 🎬 YouTube n'apparaît pas à ce
    # pas ». Une note qui nie la bande qu'on regarde est le défaut de
    # `a-note-outlives-the-figure-it-explains`, une ligne plus bas.
    coarse = [k for k in coarse if k not in served]
    if only:
        # Le filtre de SOURCES, demandé le 2026-09-08 : « il faudrait pouvoir
        # sélectionner différentes sources, par exemple afficher que YouTube sur la
        # période sélectionnée ». Il s'applique APRÈS `stackable` : une plateforme
        # écartée pour cause de couverture le reste, sinon cocher une case ferait
        # réapparaître une bande qu'on a décidé de ne pas empiler.
        order = [k for k in order if k in only]
        thin = {k: v for k, v in thin.items() if k in only}
    if not order:
        return False
    segments = _segments(span, aligned, order)
    if not any(segments.values()):
        return False

    palette = _PALETTE_DARK if _is_dark() else _PALETTE_LIGHT
    ink = "#E6E6E6" if _is_dark() else "#1a1a19"
    muted = "#9a9a97" if _is_dark() else "#6b6b68"
    surface = "#1a1a19" if _is_dark() else "#fcfcfb"
    grid = "rgba(150,150,150,0.20)"

    # `_as_mode` réécrit les valeurs ; les TROUS se lisent sur la série d'origine.
    aligned_raw = aligned
    aligned = _as_mode(aligned, order, mode, cumulative, span, step)

    # LES TRANCHES SUIVENT LA SÉRIE QU'ON TRACE. Elles sont décidées plus haut sur la
    # série quotidienne, dont les trous sont réels : un jour non collecté est un jour
    # dont on ignore les écoutes. Un NIVEAU cumulé, lui, reste connu entre deux
    # relevés — c'est le dernier compteur lu. Garder les coupures du quotidien
    # découperait la courbe de YouTube en 39 % de fragments pour cacher une valeur
    # qu'on connaît, et la bande empilée retomberait à chaque trou.
    drawn = [k for k in order if k in served]
    if drawn:
        segments = {**segments, **_segments(span, aligned, drawn)}
        # Admise plus haut, mais toujours rien à tracer : sa première mesure est
        # POSTÉRIEURE à la fenêtre. On la retire plutôt que de lui laisser une
        # étiquette dans la marge — une étiquette qui ne nomme aucune bande se lit
        # comme une bande disparue.
        order = [k for k in order if k not in drawn or segments.get(k)]
        if not order:
            return False

    if mode == "cumulative":
        # Le sous-titre annonce le NIVEAU où la courbe finit, pas une somme de pas :
        # additionner des cumuls avait déjà produit 16 568 594 écoutes pour un artiste
        # qui en a 186 000. Avec la couche or, la somme des derniers points est aussi
        # le total que les tuiles affichent — c'est la propriété qu'on veut visible.
        total = sum(next((v for v in reversed(aligned[k]) if v is not None), 0)
                    for k in order)
    else:
        total = sum(v for pkey in order for v in aligned_raw[pkey] if v)
    if mode == "facets":
        _render_facets(fig_span=span, aligned=aligned, order=order, segments=segments,
                       palette=palette, ink=ink, muted=muted, surface=surface,
                       grid=grid, title=title, step=step, total=total, key=key)
        if recap is not None:
            _render_recap(recap, span, aligned, aligned_raw, order, thin, mode,
                          step, extra=recap_extra)
        _render_notes(thin, coarse, step, coarsened=coarsened, mode=mode,
                      discarded=discarded)
        return True

    # LA LÉGENDE EST LE FILTRE DE SOURCES, et c'est ce qui retire un widget.
    #
    # Demandé le 2026-09-11 : « peut-on intégrer le clickage des plateformes
    # directement sur le graphique plutôt qu'avec le filtre qui doit sélectionner ? ça
    # enlèverait de la complexité ». Un clic de légende est côté navigateur : il ne
    # relance pas le script, donc il est instantané là où le `multiselect` coûtait un
    # rendu complet — 287 ms mesurés en production.
    #
    # Une plateforme est découpée en TRANCHES (une par plage continue), donc plusieurs
    # traces. Seule la première porte l'entrée de légende, et `legendgroup` +
    # `groupclick="togglegroup"` font que le clic les bascule toutes ensemble : sans
    # ça, masquer YouTube n'en masquerait qu'un morceau.
    legend_done: set = set()
    fig = go.Figure()

    # LA BANDE HACHURÉE D'ABORD : une trace ajoutée avant les autres passe dessous.
    #
    # Elle répond à « ne pas visualiser 0 mais (absence de data) ». Couper la bande
    # ne suffisait pas : `stackgroup` infère zéro pour la plateforme manquante, donc
    # le TOTAL empilé redescend et se lit comme une chute d'audience. Le rattrapage
    # était une phrase sous la figure ; c'est maintenant un pixel dans la figure.
    _gaps = unmeasured_spans(aligned, order)
    if _gaps:
        _stack = [
            sum(aligned[k][i] for k in order
                if i < len(aligned.get(k) or []) and aligned[k][i] is not None)
            for i in range(len(span))
        ]
        _ceiling = (max(_stack) if _stack else 0) or 1
        for _hatch in _hatch_traces(_gaps, span, _ceiling * 1.02, muted,
                                    legend=mode != "share"):
            fig.add_trace(_hatch)
        # Et le porteur de survol : la hachure montre OÙ, celui-ci dit QUOI.
        fig.add_trace(_unmeasured_hover(_gaps, span))

    # Les plateformes dont la série vient d'un COMPTEUR : leur zéro dit « rien
    # n'a bougé », pas « personne n'a écouté ». `served` les nomme déjà quand la
    # couche or les sert ; sinon on retombe sur celles qui ont une série cumulée.
    _COUNTERS = set(served) | {k for k, rows in (cumulative or {}).items() if rows}
    for pkey in order:
        for seg in segments[pkey]:
            first = pkey not in legend_done
            legend_done.add(pkey)
            fig.add_trace(go.Scatter(
                x=[span[i] for i in seg],
                # PAS de `or 0` : un `None` reste un `None`. Les segments sont
                # déjà découpés sur les trous, donc les seules valeurs qui
                # restaient à écraser ici étaient les indices ANTÉRIEURS à la
                # première mesure — dessinés à 0 avec l'infobulle « compteur
                # inchangé », c'est-à-dire une mesure affirmée sans mesure.
                y=[aligned[pkey][i] for i in seg],
                name=PLATFORM_LABELS[pkey],
                legendgroup=pkey,
                showlegend=first and mode != "share",
                mode="lines",
                # UNE SEULE pile pour tout le monde. Les tranches étant désormais
                # propres à chaque plateforme, deux morceaux d'une même source ne se
                # recouvrent jamais en x, et `stackgaps` (« infer zero » par défaut)
                # laisse les autres plateformes continuer là où celle-ci s'arrête.
                stackgroup="g",
                line=dict(width=1.6, color=surface),   # le filet de 2 px entre les aires
                fillcolor=palette[pkey],
                # `0` VEUT DIRE ZÉRO ÉCOUTE CE JOUR-LÀ, et rien d'autre : un jour
                # non mesuré n'a pas de point du tout, la bande y est coupée. Le
                # survol le dit, parce que les deux se ressemblent à l'œil —
                # « on a des 0 sur youtube et soundcloud, je pense qu'on a tout
                # simplement pas la data » (2026-09-08). Ici, si.
                #
                # ET LE MOT DÉPEND DE LA NATURE DE LA SOURCE. Sur un COMPTEUR
                # (YouTube, SoundCloud), zéro veut dire « le compteur n'a pas bougé ».
                # Sur une source QUOTIDIENNE (Spotify), il veut dire « personne n'a
                # écouté ». Le même chiffre, deux faits différents ; les confondre
                # laissait l'artiste devant un « 0 » nu — « clarifier le 0 »
                # (2026-09-12).
                customdata=[[("compteur inchangé" if pkey in _COUNTERS
                              else "aucune écoute ce jour-là")
                             if aligned[pkey][i] == 0 else ""] for i in seg],
                hovertemplate=(("%{y:.1f} %<extra>" if mode == "share"
                                else "%{y:,} %{customdata[0]}<extra>")
                               + PLATFORM_LABELS[pkey] + "</extra>"),
            ))

    # PLUS D'ÉTIQUETTES DE MARGE. La boîte de légende, en bas, nomme les mêmes
    # plateformes ET les fait disparaître d'un clic ; les étiquettes ne faisaient que
    # répéter. Retirées le 2026-09-12 — « on a déjà la légende cliquable ».
    #
    # Ce qui reste ici : la bande hachurée des périodes non mesurées, qui n'est pas
    # une annotation mais une trace (une shape Plotly ne sait pas hachurer).
    annotations: list = []

    # LE TOTAL DU SOUS-TITRE SE LIT SUR LES QUANTITÉS, jamais sur le mode d'affichage.
    #
    # Il comptait `series` — la série BRUTE — et se trompait de trois façons à la fois :
    # il ignorait le filtre de sources (décocher YouTube le laissait dans le total),
    # ignorait les plateformes écartées, et comparait des dates du JOUR à un `span` qui
    # porte des clés de SEAU après agrégation.
    #
    # Corrigé une première fois en lisant `aligned`… c'est-à-dire la série APRÈS
    # `_as_mode`. En mode cumulé, chaque point porte alors le total depuis le début, et
    # les additionner somme des cumuls : **16 568 594 écoutes** affichées au rendu du
    # 2026-09-08 pour un artiste qui en a 186 000. Le nombre était faux d'un facteur 89
    # et aucun test ne le voyait — il a fallu REGARDER la figure.
    #
    # `aligned_raw` est la quantité par pas, la seule forme qu'on ait le droit de
    # sommer. C'est l'invariant de tout ce module : on n'additionne pas deux formes.
    fig.update_layout(
        annotations=annotations,
        # PLUS DE TITRE NI DE SOUS-TITRE SUR LA PILE. Retirés le 2026-09-12 —
        # « redondant avec le tableau […] car on a déjà les valeurs sur les filtres ».
        #
        # Le titre répétait la période (« — 12 mois »), que la barre de filtres porte
        # juste au-dessus et qui est le contrôle par lequel on l'a choisie. Le
        # sous-titre répétait le total (« 304 793 écoutes cumulées · 181 semaines »),
        # que le récapitulatif à droite donne en le DÉTAILLANT par plateforme. Deux
        # répétitions d'un réglage visible et d'un chiffre voisin, au prix de 58 px
        # de marge haute pris à la figure.
        #
        # Le mode « part » n'annonce plus non plus « part de chaque plateforme » : la
        # case du même nom est allumée dans la barre, et l'axe est en pourcentage.
        # `title=None` NE RETIRE PAS LE TITRE : Plotly rend alors la chaîne
        # « undefined » à sa place — vu au navigateur le 2026-09-12, pas en lisant le
        # code. Il faut un texte VIDE, pas une absence.
        title=dict(text=""),
        hovermode="x unified",
        height=340,
        # De la place À DROITE pour les étiquettes, et plus de marge haute réservée à
        # une légende qui n'existe plus.
        # Assez de place à GAUCHE pour les graduations et EN BAS pour les dates : à
        # 8 px, le rendu du 2026-09-08 coupait « 150 k » en « k » et mangeait la moitié
        # des libellés de l'axe des temps. La marge droite, elle, porte les étiquettes.
        # `t=12` : les 58 px réservés au titre sur deux lignes sont rendus à la figure.
        margin=dict(l=56, r=24, t=12,
                    b=62 if mode != "share" else 32),
        # EN BAS, jamais en haut. La version de 2026-09-08 l'ancrait à `y=1.0`,
        # c'est-à-dire dans la marge où vit le titre sur deux lignes : les deux se
        # recouvraient — « la légende est masquée, c'est assez moche ». Sous la figure,
        # elle n'a rien à recouvrir. Les étiquettes de marge restent : elles nomment la
        # bande à hauteur d'œil, la légende sert à la faire disparaître.
        #
        # PAS EN MODE « PART ». Les pourcentages y sont calculés sur l'ensemble
        # affiché ; un clic de légende masque une trace SANS recalculer les autres, et
        # la pile ne ferait plus 100 %. C'est le seul mode où le `multiselect` reste.
        showlegend=mode != "share",
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0,
                    groupclick="togglegroup", bgcolor="rgba(0,0,0,0)",
                    font=dict(size=11, color=muted)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=ink),
        xaxis=dict(showgrid=False, linecolor=grid, title=None),
        yaxis=dict(gridcolor=grid, zeroline=False, title=None, rangemode="tozero",
                   range=[0, 100] if mode == "share" else None,
                   ticksuffix=" %" if mode == "share" else None),
    )
    st.plotly_chart(fig, width="stretch", key=key)
    if recap is not None:
        _render_recap(recap, span, aligned, aligned_raw, order, thin, mode,
                          step, extra=recap_extra)
    _render_notes(thin, coarse, step, coarsened=coarsened, mode=mode,
                  discarded=discarded)
    return True


# `t_trend_caption` ET `_MODE_SHAPE` VIVAIENT ICI. Retirés le 2026-09-12, à la demande
# — « supprime-moi le texte inutile ».
#
# La légende disait deux choses. La première — « Total depuis le début de la période »,
# « Écoutes hebdomadaires » — est maintenant portée par la BARRE DE PAS et la barre de
# mode, visibles au-dessus de la figure : depuis que « Automatique » a disparu, le pas
# demandé EST le pas appliqué, donc l'unité se lit sur le contrôle qui la choisit.
# La seconde — « une interruption veut dire qu'on n'a pas de mesure, pas un zéro » —
# est exactement ce que la BANDE HACHURÉE dessine, avec son entrée de légende
# « ▨ Aucune mesure ». Une phrase qui paraphrase un pixel visible est du bruit ; c'est
# la même raison qui avait fait descendre cette fonction ici le 2026-09-10, poussée
# d'un cran de plus.
#
# Ce qui reste écrit sous la figure, ce sont les notes qui parlent de ce que la figure
# NE PEUT PAS montrer : un seau élargi (`t_coarsened`), une plateforme trop mince
# (`t_too_thin`), un pas trop grossier (`t_too_coarse`), des écoutes non traçables.



def _render_facets(*, fig_span: list, aligned: dict, order: list, segments: dict,
                   palette: dict, ink: str, muted: str, surface: str, grid: str,
                   title: str, step: str, total: int, key: str) -> None:
    """Petits multiples : une facette par plateforme, chacune sur SON échelle.

    La seule forme qui rende visible une plateforme mille fois plus petite qu'une
    autre, et la seule alternative admissible au double axe — que ce module n'utilisera
    jamais. Mesuré sur l'artiste 1 : Spotify 99,74 %, YouTube 0,22 %, SoundCloud
    0,04 %. Empilées ou en part, les deux dernières sont sous le pixel ; ici chacune
    remplit sa propre facette.

    Ce qu'on perd est dit franchement dans le sous-titre : il n'y a plus de total
    lisible d'un coup d'œil, parce que les échelles ne sont pas comparables. C'est le
    prix, et c'est pour cela que le mode est un CHOIX et pas le défaut.
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=len(order), cols=1, shared_xaxes=True,
                        vertical_spacing=0.06,
                        subplot_titles=[PLATFORM_LABELS[k] for k in order])
    for row, pkey in enumerate(order, start=1):
        # LA HACHURE EST PAR FACETTE, et c'est la différence avec la pile.
        #
        # Ici chaque plateforme a son cadre, donc le trou de l'une ne concerne
        # qu'elle : hachurer toute la colonne dirait que SoundCloud manque parce que
        # YouTube manque. En petits multiples il n'y a pas non plus de total qui
        # retombe — l'aire s'interrompt simplement — mais une interruption reste
        # muette sur sa raison, et c'est ce que la hachure dit.
        _gaps = unmeasured_spans({pkey: aligned[pkey]}, [pkey])
        if _gaps:
            _measured = [v for v in aligned[pkey] if v is not None]
            _ceiling = (max(_measured) if _measured else 0) or 1
            for _hatch in _hatch_traces(_gaps, fig_span, _ceiling * 1.02, muted,
                                        legend=False):
                fig.add_trace(_hatch, row=row, col=1)
            fig.add_trace(_unmeasured_hover(_gaps, fig_span), row=row, col=1)
        for seg in segments[pkey]:
            fig.add_trace(go.Scatter(
                x=[fig_span[i] for i in seg],
                y=[aligned[pkey][i] for i in seg],   # ni `or 0` ici
                name=PLATFORM_LABELS[pkey], mode="lines", fill="tozeroy",
                line=dict(width=1.6, color=palette[pkey]),
                fillcolor=palette[pkey], showlegend=False,
                hovertemplate="%{y:,}<extra>" + PLATFORM_LABELS[pkey] + "</extra>",
            ), row=row, col=1)
        fig.update_yaxes(gridcolor=grid, zeroline=False, rangemode="tozero",
                         row=row, col=1)
        fig.update_xaxes(showgrid=False, linecolor=grid, row=row, col=1)
    for note in fig.layout.annotations:
        note.update(font=dict(color=ink, size=12), x=0, xanchor="left")
    fig.update_layout(
        # Le titre et le total sont partis avec ceux de la pile (2026-09-12) : le
        # filtre porte la période, le récapitulatif porte les chiffres. Ce qui reste
        # est propre aux facettes et ne se lit nulle part ailleurs — les échelles ne
        # se comparent pas, et rien à l'écran ne le dirait sans cette ligne.
        title=dict(text=f"<span style='font-size:12px;color:{muted}'>"
                        "chaque plateforme a sa propre échelle, elles ne se "
                        "comparent pas</span>",
                   x=0, xanchor="left"),
        height=140 * len(order) + 60,
        # Le titre tient sur DEUX lignes, et le titre de la première facette est posé
        # juste sous la marge : à 64 px, « Spotify » s'imprimait par-dessus le
        # sous-titre. Vu au rendu le 2026-09-08.
        margin=dict(l=56, r=24, t=34, b=32),
        showlegend=False, hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=ink),
    )
    st.plotly_chart(fig, width="stretch", key=key)
