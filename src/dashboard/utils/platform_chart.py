"""La courbe « écoutes par jour, par plateforme » — un seul rendu, deux surfaces.

Type: Utility
Uses: plotly, streamlit, platform_timeseries
Triggers: views/home._section_streams, views/onboarding._step_welcome
Persists in: nothing

Les couleurs ne sont pas choisies à l'œil
-----------------------------------------
Elles sortent du validateur de la skill `dataviz`
(`node scripts/validate_palette.js "<hex,…>" --mode light|dark`), et le premier jet
— les couleurs de marque exactes — a été **refusé** :

    #1DB954, #FF0000, #FF5500
    [FAIL] CVD separation      #FF5500 ↔ #FF0000  ΔE 4.5 (deutan)
    [FAIL] Normal-vision floor #FF5500 ↔ #FF0000  ΔE 7.4 — en dessous de 15

Le rouge YouTube et l'orange SoundCloud sont indiscernables **même en vision
normale**, et c'est exactement ce qui rend une courbe « pas belle » : deux traits
qu'on ne peut pas attribuer. Le vert Spotify est conservé tel quel ; le rouge est
assombri et l'orange décalé vers l'ambre jusqu'à ce que les six contrôles passent.

Le mode sombre a ses PROPRES pas — la bande de clarté y est 0,48–0,67 contre
0,43–0,77 en clair, donc un simple éclaircissement ne passe pas. Les deux jeux sont
validés séparément, et le jeu sombre porte un avertissement (ΔE 6,9 en deutan) qui
n'est *légal qu'avec un second encodage* : d'où les étiquettes en bout de courbe et
les motifs de trait distincts, qui ne sont pas décoratifs.

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

# Validées le 2026-09-08 — « ALL CHECKS PASS » sur les six contrôles.
_PALETTE_LIGHT = {"spotify": "#1DB954", "youtube": "#CC0000", "soundcloud": "#FF9500"}
_PALETTE_DARK = {"spotify": "#15803D", "youtube": "#DC2626", "soundcloud": "#B8860B"}

# Le second encodage qu'exige l'avertissement CVD du jeu sombre : l'identité d'une
# courbe ne repose jamais sur sa seule couleur.
_DASH = {"spotify": "solid", "youtube": "dash", "soundcloud": "dot"}

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


def render_platform_chart(series: dict, *, title: str = "", days: int = _DEFAULT_DAYS,
                          key: str = "platform_chart") -> bool:
    """Trace une courbe par plateforme. Rend False si rien n'est traçable.

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

    palette = _PALETTE_DARK if _is_dark() else _PALETTE_LIGHT
    ink = "#E6E6E6" if _is_dark() else "#31333F"
    grid = "rgba(150,150,150,0.18)"

    fig = go.Figure()
    for pkey in PLATFORM_LABELS:              # ordre FIXE : jamais recalculé, jamais cyclé
        values = aligned.get(pkey)
        if not values or not any(v is not None for v in values):
            continue
        fig.add_trace(go.Scatter(
            x=span, y=values, name=PLATFORM_LABELS[pkey], mode="lines",
            connectgaps=False,                # un trou reste un trou
            line=dict(color=palette[pkey], width=2, dash=_DASH[pkey]),
            hovertemplate="%{y:,} écoutes<extra>" + PLATFORM_LABELS[pkey] + "</extra>",
        ))
    if not fig.data:
        return False

    fig.update_layout(
        title=title or None,
        hovermode="x unified",                # une seule lecture verticale, pas trois
        height=320,
        margin=dict(l=8, r=8, t=36 if title else 12, b=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=ink),
        xaxis=dict(showgrid=False, linecolor=grid, title=None),
        yaxis=dict(gridcolor=grid, zeroline=False, title=None, rangemode="tozero"),
    )
    st.plotly_chart(fig, width="stretch", key=key)
    return True


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
