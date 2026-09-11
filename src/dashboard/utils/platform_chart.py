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

from src.dashboard.utils.platform_timeseries import (
    MISSING_HISTORY,
    PLATFORM_LABELS,
    STEP_ONLY,
)

logger = logging.getLogger(__name__)

# Les couleurs de l'illustration committée, validées le 2026-09-08 — « ALL CHECKS
# PASS » sur les six contrôles, dans les deux modes.
_PALETTE_LIGHT = {"spotify": "#2a78d6", "youtube": "#eb6834", "soundcloud": "#1baf7a",
                  "apple": "#eda100"}
_PALETTE_DARK = {"spotify": "#2a78d6", "youtube": "#e05f2b", "soundcloud": "#1baf7a",
                 "apple": "#c08400"}

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
_FINER_STEPS = {"year": ["year", "week", "day"], "week": ["week", "day"], "day": ["day"]}

# Le mot qui suit le nombre, dans le sous-titre. Il compte des SEAUX, pas des unités
# de temps écoulé — et la nuance n'est pas de la pédanterie : sur une fenêtre de 12 mois
# à cheval sur deux années civiles, la figure a 2 seaux annuels et disait « sur
# 2 années », ce qui se lit comme deux ans d'historique. Vu au rendu le 2026-09-10.
_STEP_UNITS = {"day": "jours", "week": "semaines", "year": "années"}

# Le mot juste quand le seau peut être PLUS LARGE que la fenêtre. Au pas jour et au pas
# semaine, un seau vaut à peu près son unité et la confusion n'existe pas ; au pas
# annuel, un seau peut ne couvrir qu'un mois de la fenêtre demandée.
_STEP_BUCKETS = {"day": "jours", "week": "semaines", "year": "points annuels"}


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


def _bucket_key(day, step: str):
    """Le point auquel ce jour appartient, selon le pas."""
    if step == "year":
        return _dt.date(day.year, 1, 1)
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
    écoute ait disparu. C'est `t_missing` qui le nomme, avec le compte par plateforme.
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
            if candidate == "year":
                # Un pas ANNUEL ne se parcourt pas en jours fixes : 365 ou 366. On
                # construit donc l'axe sur les 1ᵉʳ janvier réellement présents.
                agg = _aggregate(series, candidate, since, until)
                years = sorted({d for rows in agg.values() for d, _ in rows
                                if (w_since is None or d >= w_since)
                                and (w_until is None or d <= w_until)})
                span = years
                aligned = {k: _continuous(rows, span) for k, rows in agg.items() if rows}
            else:
                span, aligned = _window(_aggregate(series, candidate, since, until),
                                        None, w_since, w_until, step_days=7)
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
        # niveau à la fin du précédent. Le premier seau n'a pas de prédécesseur, donc
        # sa croissance est inconnue — `None`, jamais 0, qui affirmerait l'immobilité.
        for k in served:
            levels = _carry_forward(span, cumulative[k], step)
            growth = [None]
            for prev, cur in zip(levels, levels[1:]):
                growth.append(None if prev is None or cur is None
                              else max(cur - prev, 0))
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
        _render_notes(span, aligned_raw, order, thin, coarse, step,
                      stacked=False, coarsened=coarsened, mode=mode, served=served,
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
    for pkey in order:
        for seg in segments[pkey]:
            first = pkey not in legend_done
            legend_done.add(pkey)
            fig.add_trace(go.Scatter(
                x=[span[i] for i in seg],
                y=[aligned[pkey][i] or 0 for i in seg],
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
                # simplement pas la data » (2026-09-08). Ici, si : le compteur de la
                # chaîne n'a pas bougé de la journée.
                customdata=[["compteur inchangé" if (aligned[pkey][i] or 0) == 0
                             else ""] for i in seg],
                hovertemplate=(("%{y:.1f} %<extra>" if mode == "share"
                                else "%{y:,} %{customdata[0]}<extra>")
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
        title=dict(
            # Le `.replace(",", " ")` portait sur TOUT le titre, et mangeait la virgule
            # de « Toutes tes plateformes, un seul écran » — vu au rendu le 2026-09-08.
            # Il ne s'applique qu'au nombre.
            text=(f"<b>{title}</b><br><span style='font-size:12px;color:{muted}'>"
                  + (f"{len(span)} {_STEP_BUCKETS[step]} · part de chaque plateforme"
                     if mode == "share" else
                     f"{format(total, ',').replace(',', chr(8239))} écoutes "
                     + ("cumulées · " if mode == "cumulative" else "sur ")
                     + f"{len(span)} {_STEP_BUCKETS[step]}")
                  + "</span>" if title else None),
            x=0, xanchor="left"),
        hovermode="x unified",
        height=340,
        # De la place À DROITE pour les étiquettes, et plus de marge haute réservée à
        # une légende qui n'existe plus.
        # Assez de place à GAUCHE pour les graduations et EN BAS pour les dates : à
        # 8 px, le rendu du 2026-09-08 coupait « 150 k » en « k » et mangeait la moitié
        # des libellés de l'axe des temps. La marge droite, elle, porte les étiquettes.
        margin=dict(l=56, r=132, t=58 if title else 12,
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
    _render_notes(span, aligned_raw, order, thin, coarse, step,
                  coarsened=coarsened, mode=mode, served=served, discarded=discarded)
    return True


# Ce que porte un point, selon le pas — et ce qu'un blanc veut dire au même pas.
_STEP_POINT = {
    "day": ("du jour", "ce jour-là"),
    "week": ("de la semaine", "cette semaine-là"),
    "year": ("de l'année", "cette année-là"),
}

# La forme que le lecteur a sous les yeux, selon le mode. Un « blanc dans la bande »
# n'a aucun sens quand il n'y a pas de bande.
_MODE_SHAPE = {
    "cumulative": "la courbe",
    "absolute": "la bande",
    "share": "la courbe",
    "facets": "la facette",
}


def t_trend_caption(step: str, mode: str) -> str:
    """La légende sous la figure, DÉRIVÉE de ce que la figure fait.

    Elle était fixe dans `views/home.py` et disait « Écoutes **du jour** […] un blanc
    dans la bande […] pas de mesure ce jour-là » — sous TOUS les modes et TOUS les pas.
    Vu au rendu le 2026-09-10 en « Chacune à son échelle · Par année » : trois
    affirmations fausses d'un coup, sur une figure qui montrait des totaux ANNUELS en
    facettes séparées.

    C'est la cause (E) de l'audit du 2026-09-10 — « le texte est écrit à côté du
    comportement, pas dérivé de lui » — et c'est pourquoi la fonction vit ICI : le
    module de la figure est le seul endroit qui connaisse le pas EFFECTIF. `views/home.py`
    ne connaît que le pas demandé, et « Automatique » n'en est pas un.

    En mode cumulé, un point ne porte pas la quantité d'une période mais le total
    depuis le début : la phrase change de sujet, pas seulement d'unité.
    """
    from src.dashboard.utils.i18n import t
    unit, when = _STEP_POINT.get(step, _STEP_POINT["day"])
    shape = _MODE_SHAPE.get(mode, "la bande")
    if mode == "cumulative":
        return t(
            "platform_chart.caption_cumulative",
            "Total **depuis le début de la période**, plateforme par plateforme. Une "
            "interruption dans {shape} veut dire qu'on n'a pas de mesure — pas que le "
            "compteur est retombé."
        ).format(shape=shape)
    return t(
        "platform_chart.caption_period",
        "Écoutes **{unit}**, plateforme par plateforme. Un blanc dans {shape} veut "
        "dire qu'on n'a pas de mesure {when} — pas zéro écoute."
    ).format(unit=unit, shape=shape, when=when)


def _render_notes(span: list, aligned_raw: dict, order: list, thin: dict,
                  coarse: list, step: str, *, stacked: bool = True,
                  coarsened=None, mode: str = "absolute", served=(),
                  discarded: dict | None = None) -> None:
    """Ce que la figure ne peut pas dessiner, écrit sous elle. Jamais tu.

    Une plateforme qui manque sans explication se lit comme une panne — la leçon de la
    matrice d'état, appliquée à une figure.

    UNE NOTE QUI DÉCRIT UNE AUTRE FIGURE QUE CELLE AFFICHÉE EST PIRE QUE PAS DE NOTE.
    Signalé le 2026-09-11 : « je n'ai aucune data sur YouTube depuis le début ». La
    figure traçait pourtant YouTube à 118 334, et c'est la PROSE qui disait le
    contraire — « 🎬 YouTube 26 [semaines non mesurées], leur aire s'interrompt là ».
    Ces notes sont calculées sur `aligned_raw`, la série QUOTIDIENNE, et elles étaient
    exactes tant que la courbe en venait. Depuis que le mode cumulé lit la couche or,
    une plateforme à compteur n'a plus de trou : entre deux relevés son niveau est
    connu, la courbe est continue, et l'annoncer interrompue fait lire une panne là où
    il y a une mesure. `served` nomme ces plateformes, et elles sortent de la note.
    """
    # La légende générale d'abord : elle dit ce que la figure MONTRE. Les notes qui
    # suivent disent ce qu'elle ne peut pas montrer.
    st.caption(t_trend_caption(step, mode))
    if coarsened:
        st.caption(t_coarsened(*coarsened))
    _no_gaps = set(served) if mode == "cumulative" else set()
    gaps = {k: n for k, n in gap_counts(span, aligned_raw, order).items()
            if n and k not in _no_gaps}
    if gaps:
        st.caption(t_missing(gaps, len(span), step, stacked=stacked))
    for label, measured, total in thin.values():
        st.caption(t_too_thin(label, measured, total))
    for pkey in coarse:
        st.caption(t_too_coarse(PLATFORM_LABELS[pkey], step))

    # « ÉCOUTES NON TRAÇABLES » — seulement quand la figure trace vraiment les écarts
    # quotidiens, c'est-à-dire au pas du JOUR et hors mode cumulé.
    #
    # Elle vivait dans l'accueil, et elle ne pouvait pas y être juste : cette vue
    # connaît le pas DEMANDÉ, et « Automatique » n'en est pas un — seul ce module sait
    # lequel a été retenu. C'est exactement l'argument qui avait déjà fait descendre
    # `t_trend_caption` ici le 2026-09-10 ; la note voisine était restée en haut.
    #
    # Depuis que le seau plus large qu'un jour porte la CROISSANCE du compteur, ces
    # écoutes sont dans la figure dès le pas hebdomadaire. Les annoncer perdues sous
    # une figure qui les montre est le défaut qu'on vient de corriger, dans l'autre
    # sens.
    if discarded and mode != "cumulative" and step == "day":
        from src.dashboard.utils.i18n import t

        parts = ", ".join(
            f"{PLATFORM_LABELS.get(k, k)} {v[2]:,}".replace(",", "\u202f")
            for k, v in sorted(discarded.items(), key=lambda kv: -kv[1][2]) if v[2])
        if parts:
            st.caption(t(
                "home.trend_discarded",
                "⏸️ Écoutes mesurées mais **non traçables** : {parts}. Elles se sont "
                "produites entre deux collectes espacées de plus d'un jour — on sait "
                "combien, jamais quel jour. Les attribuer à une date inventerait un "
                "pic. **Par semaine** ou **Par année**, elles sont comptées."
            ).format(parts=parts))


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
        for seg in segments[pkey]:
            fig.add_trace(go.Scatter(
                x=[fig_span[i] for i in seg],
                y=[aligned[pkey][i] or 0 for i in seg],
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
        title=dict(text=(f"<b>{title}</b><br><span style='font-size:12px;color:"
                         f"{muted}'>{format(total, ',').replace(',', chr(8239))} "
                         f"écoutes sur {len(fig_span)} {_STEP_BUCKETS[step]} · chaque "
                         "plateforme a sa propre échelle, elles ne se comparent pas"
                         "</span>") if title else None,
                   x=0, xanchor="left"),
        height=140 * len(order) + 60,
        # Le titre tient sur DEUX lignes, et le titre de la première facette est posé
        # juste sous la marge : à 64 px, « Spotify » s'imprimait par-dessus le
        # sous-titre. Vu au rendu le 2026-09-08.
        margin=dict(l=56, r=24, t=96 if title else 20, b=32),
        showlegend=False, hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=ink),
    )
    st.plotly_chart(fig, width="stretch", key=key)


def t_too_thin(label: str, measured: int, total: int) -> str:
    """Pourquoi une plateforme n'est pas dans la pile — nommée, jamais tue."""
    from src.dashboard.utils.i18n import t
    return t("platform_chart.too_thin",
             "{label} n'est pas tracée : **{measured} mesure(s)** seulement, et il en "
             "faut deux pour dessiner une aire. Ses chiffres restent dans le tableau "
             "ci-dessous."
             ).format(label=label, measured=measured, total=total)


def t_coarsened(asked: str, used: str) -> str:
    """Le pas demandé ne dessinait rien ; on le dit, et on dit ce que ça coûte."""
    from src.dashboard.utils.i18n import t
    names = {"day": "Par jour", "week": "Par semaine", "year": "Par année"}
    return t("platform_chart.coarsened",
             "**{asked}** ne donne qu'un seul point sur cette période — une aire a "
             "besoin d'au moins deux. Affiché **{used}**. 🎎 Apple Music n'existe "
             "qu'au pas Par année : élargis la période pour le retrouver."
             ).format(asked=names.get(asked, asked), used=names.get(used, used))


def t_too_coarse(label: str, step: str) -> str:
    """Pourquoi une plateforme disparaît à CE pas, alors qu'elle existe au pas du jour."""
    from src.dashboard.utils.i18n import t
    unit = {"week": "semaine", "year": "année"}.get(step, "période")
    return t("platform_chart.too_coarse",
             "{label} n'apparaît pas à ce pas : aucune de ses {unit}s n'est mesurée "
             "sur assez de jours pour en faire un total honnête. Choisis un pas plus "
             "fin pour la voir."
             ).format(label=label, unit=unit)


def t_missing(gaps: dict, total: int, step: str = "day", *,
              stacked: bool = True) -> str:
    """Le blanc n'est plus commun : chaque plateforme dit ce qu'elle n'a pas mesuré.

    L'ancienne phrase comptait les pas où **au moins une** plateforme manquait, et
    c'était la formulation d'une figure où une source absente coupait tout le monde.
    Maintenant que les autres continuent, il faut dire deux choses : qui manque, et que
    le total de ces pas-là est plus bas SANS qu'une écoute ait disparu.

    Sauf quand la figure n'empile pas — en petits multiples il n'y a pas de total à
    faire baisser, et le dire quand même ferait chercher au lecteur une chute qui
    n'existe nulle part sur l'image.
    """
    from src.dashboard.utils.i18n import t
    unit = _STEP_UNITS.get(step, "jours")
    who = " · ".join(f"{PLATFORM_LABELS.get(k, k)} {n}" for k, n in sorted(
        gaps.items(), key=lambda kv: -kv[1]))
    if not stacked:
        return t("platform_chart.gaps_unstacked",
                 "Sur {total} {unit}, certaines plateformes n'ont pas été mesurées "
                 "partout ({who}). Leur courbe s'interrompt là — un blanc, jamais un "
                 "zéro : un zéro dirait « aucune écoute »."
                 ).format(total=total, unit=unit, who=who)
    return t("platform_chart.gaps",
             "Sur {total} {unit}, certaines plateformes n'ont pas été mesurées "
             "partout ({who}). Leur aire s'interrompt là ; les autres continuent, et "
             "le total de ces {unit}-là est donc plus bas — aucune écoute n'a "
             "disparu."
             ).format(total=total, unit=unit, who=who)


def render_missing_history_note() -> None:
    """Nomme ce qui n'a PAS de série, plutôt que de le dessiner à zéro.

    Une plateforme absente sans explication se lit comme une panne — c'est la leçon
    de `_silence_reason` et de la matrice d'état, appliquée à une figure.
    """
    for label, why in MISSING_HISTORY.values():
        st.caption(f"{label} — {why}.")
