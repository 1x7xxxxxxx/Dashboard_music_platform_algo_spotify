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

from src.dashboard.utils.platform_timeseries import (
    MISSING_HISTORY,
    PLATFORM_LABELS,
    combined_daily_streams,
)

logger = logging.getLogger(__name__)

# Les couleurs de l'illustration committée, validées le 2026-09-08 — « ALL CHECKS
# PASS » sur les six contrôles, dans les deux modes.
_PALETTE_LIGHT = {"spotify": "#2a78d6", "youtube": "#eb6834", "soundcloud": "#1baf7a"}
_PALETTE_DARK = {"spotify": "#2a78d6", "youtube": "#e05f2b", "soundcloud": "#1baf7a"}

# Fenêtre par défaut. L'artiste 1 a 1 344 jours de série Spotify : tout afficher
# écrase les variations récentes, qui sont ce qu'on vient regarder.
_DEFAULT_DAYS = 90


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


def _window(series: dict, days: int) -> tuple:
    """(jours continus, séries alignées) sur les `days` derniers jours mesurés."""
    all_days = sorted({d for rows in series.values() for d, _ in rows})
    if not all_days:
        return [], {}
    last = all_days[-1]
    first = max(all_days[0], last - _dt.timedelta(days=days - 1))
    span = [first + _dt.timedelta(days=i) for i in range((last - first).days + 1)]
    return span, {k: _continuous(rows, span) for k, rows in series.items() if rows}


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
        measured = sum(1 for v in values if v is not None)
        if not measured:
            continue
        if measured * 2 >= len(span):
            order.append(key)
        else:
            thin[key] = (PLATFORM_LABELS[key], measured, len(span))
    return order, thin


def _segments(span: list, aligned: dict, order: list) -> list:
    """Les tranches de jours CONSÉCUTIFS où toutes les aires ont une mesure.

    Une aire empilée n'a pas de trou : le jour où une plateforme n'a pas été mesurée,
    la compter pour zéro ferait plonger le TOTAL, ce qui se lit comme une chute
    d'écoutes. On coupe donc la bande, et le blanc dit « on ne sait pas ».

    Mesuré sur l'artiste 1 le 2026-09-08 : 79 jours complets sur 90, en 2 tranches —
    la bande reste lisible, et les 11 jours manquants ne mentent pas.
    """
    ok = [all(aligned[k][i] is not None for k in order) for i in range(len(span))]
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


def render_platform_chart(series: dict, *, title: str = "", days: int = _DEFAULT_DAYS,
                          key: str = "platform_chart") -> bool:
    """Empile une aire par plateforme. Rend False si rien n'est traçable.

    L'appelant décide quoi dire quand c'est False — cette fonction n'écrit ni
    « aucune donnée » ni un exemple à la place : les deux se sont déjà lus comme une
    panne ailleurs dans ce dépôt.
    """
    span, aligned = _window(series or {}, days)
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
                y=[aligned[pkey][i] for i in seg],
                name=PLATFORM_LABELS[pkey],
                legendgroup=pkey,
                showlegend=(n == 0),          # une entrée de légende par plateforme
                mode="lines",
                stackgroup=f"g{n}",           # une pile PAR TRANCHE : la bande se coupe
                line=dict(width=1.6, color=surface),   # le filet de 2 px entre les aires
                fillcolor=palette[pkey],
                hovertemplate="%{y:,}<extra>" + PLATFORM_LABELS[pkey] + "</extra>",
            ))

    total = sum(v for rows in series.values() for d, v in rows if d in set(span))
    fig.update_layout(
        title=dict(
            text=(f"<b>{title}</b><br><span style='font-size:12px;color:{muted}'>"
                  f"{total:,} écoutes sur {len(span)} jours</span>".replace(",", " ")
                  if title else None),
            x=0, xanchor="left"),
        hovermode="x unified",
        height=340,
        margin=dict(l=8, r=8, t=64 if title else 12, b=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0,
                    font=dict(color=ink)),
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


def render_daily_table(series: dict, *, days: int = _DEFAULT_DAYS,
                       key: str = "platform_table") -> None:
    """Les chiffres, sous la courbe et repliés.

    Ce n'est pas un supplément : le validateur rend un avertissement de contraste sur
    le vert Spotify (2,52:1) et exige alors « visible labels or a table view ». C'est
    cette table.
    """
    span, aligned = _window(series or {}, days)
    if not span or not aligned:
        return
    try:
        import pandas as pd
    except Exception:      # noqa: BLE001
        return
    data = {"Jour": span}
    for pkey, values in aligned.items():
        data[PLATFORM_LABELS.get(pkey, pkey)] = values
    total = dict(combined_daily_streams(series))
    data["Total"] = [total.get(d) for d in span]
    with st.expander("🔢 Voir les chiffres jour par jour", expanded=False):
        st.dataframe(pd.DataFrame(data).iloc[::-1], hide_index=True,
                     width="stretch", key=key)
