"""
Type: Utility
Uses: streamlit
Depends on: i18n (t)
Persists in: nothing

Generic Streamlit UI helpers shared across views.

`show_empty_state` factors the early-exit pattern repeated ~20+ times across
views:  `if df.empty: st.info(...); return`  →  `if show_empty_state(df, msg): return`

`secondary_analyses` implements the one-decision-per-screen rule: a view opens on
the single chart that answers "should I do something?", and everything that only
refines that answer lives one click away. Beta feedback (Grinch, 2026-08-12):
"réduire le nombre de graphs qui permettent de prendre décision" — the charts were
not wrong, there were simply too many competing for the same decision.
"""
from __future__ import annotations

from datetime import date as _date

import streamlit as st

from src.dashboard.utils.i18n import t

_LEVELS = frozenset({"info", "warning", "error"})


def smart_date_range(label, min_date, max_date, *, key):
    """Data-bounded period selector. Returns (from_date, to_date) as date objects.

    "Smart" = the choices are derived from the actual data span [min_date, max_date],
    so the user can never land on an empty window (the classic "last 6 months" trap
    when the data is older). Presets: full history, one entry per calendar year
    actually covered, and a custom range bounded to [min, max]. Default = full span.

    Returns (None, None) when min/max are None (no data). Accepts date or datetime.
    """
    if min_date is None or max_date is None:
        return None, None
    min_d = min_date.date() if hasattr(min_date, "date") else min_date
    max_d = max_date.date() if hasattr(max_date, "date") else max_date
    if min_d > max_d:
        min_d, max_d = max_d, min_d

    custom_label = t("ui.custom_range", "Plage personnalisée")
    presets = {t("ui.full_history", "Tout l'historique"): (min_d, max_d)}
    for y in range(min_d.year, max_d.year + 1):
        start, end = max(_date(y, 1, 1), min_d), min(_date(y, 12, 31), max_d)
        if start <= end:
            presets[t("ui.year_n", "Année {y}").format(y=y)] = (start, end)
    presets[custom_label] = None

    choice = st.selectbox(label, list(presets.keys()), key=f"{key}_preset")
    if choice != custom_label:
        return presets[choice]

    rng = st.date_input(
        t("ui.range", "Plage"), value=(min_d, max_d), min_value=min_d, max_value=max_d,
        key=f"{key}_range",
    )
    if isinstance(rng, (tuple, list)) and len(rng) == 2:
        return rng[0], rng[1]
    return min_d, max_d  # single-date mid-selection → fall back to full span


def show_empty_state(df, message: str, *, level: str = "info") -> bool:
    """Render `message` and return True when `df` is empty/None.

    Caller stays in control of the early return:
        if show_empty_state(df, "Aucune donnée."): return

    `level` ∈ {info, warning, error} (validated — never arbitrary attr).
    """
    if level not in _LEVELS:
        raise ValueError(f"show_empty_state: level '{level}' not in {sorted(_LEVELS)}")
    if df is None or getattr(df, "empty", True):
        getattr(st, level)(message)
        return True
    return False


def say_why_it_is_empty(last_measure, window, *, empty_window: str,
                        no_history: str) -> None:
    """Rendre CELUI des deux silences qui est vrai, jamais l'autre.

    Une figure vide a deux causes qui demandent des gestes OPPOSÉS :

      * la fenêtre ne contient rien, alors que la série existe ailleurs — l'artiste
        doit déposer un export récent, ou élargir la fenêtre ;
      * il n'y a pas assez de points, où qu'on regarde — l'artiste doit attendre.

    Les confondre envoie chercher le mauvais geste, et rien sur la figure ne détrompe.
    Vu au navigateur le 2026-09-12 sur l'accueil : « pas encore assez d'historique » à
    un locataire qui a QUATRE ANS de mesures, parce que le CSV Spotify n'avait pas été
    déposé depuis 92 jours.

    Cette fonction existe parce que le correctif du 2026-09-12 n'a été appliqué qu'à
    `home.py`. Un balayage du 2026-09-17 a trouvé la même phrase, sous une requête
    aussi fenêtrée, dans `apple_music`, `instagram` et `soundcloud` — trois vues que
    personne n'avait relues parce que la classe portait le nom de l'accueil. Une règle
    extraite dont un seul appelant est recâblé est une règle qu'on réécrira.

    `last_measure` est la dernière mesure de la série SANS la fenêtre (`None` si la
    série est vide partout). `window` est la `PeriodWindow` affichée.
    """
    hors = (last_measure is not None
            and not getattr(window, "is_all_history", False)
            and window is not None
            and last_measure < window.start)
    if hors:
        st.warning(empty_window)
    else:
        st.info(no_history)


# ── Un message qui SURVIT au rerun qui le suit ───────────────────────────────
#
# ⚠️ **Signalé par le propriétaire le 2026-09-20, et c'est un défaut de PRODUIT, pas de
# confort.** Il a saisi ses écoutes réalisées dans « Saisie S4A », pressé
# « 💾 Enregistrer », et rapporté : « rien n'a fonctionné ou rien ne m'a communiqué que
# ça avait été enregistré ».
#
# **L'enregistrement avait fonctionné** — 33 lignes écrites en production, vérifiées. Le
# code faisait :
#
#     st.success("… enregistrés …")
#     st.rerun()
#
# `st.rerun()` JETTE le rendu en cours : le message n'est jamais peint. L'utilisateur
# voit la page se recharger sans un mot, exactement comme si rien ne s'était passé — et
# la réaction naturelle est de recommencer, ou de conclure que c'est cassé.
#
# Balayé le 2026-09-20 : **23 sites** dans `src/dashboard/`, dont les QUATRE boutons de
# `saisie_s4a.py`. Ce n'est donc pas un oubli, c'est un motif qu'on recopie.
#
# Le remède tient dans l'ordre : on DÉPOSE le message dans l'état de session AVANT le
# rerun, et le rendu suivant le ramasse. `st.toast` existe et survit aussi, mais il
# s'efface tout seul en quelques secondes — pour une confirmation d'écriture, on veut
# quelque chose qui reste à l'écran jusqu'à l'action suivante.
_CLE_MESSAGE = "_message_apres_rerun"


def flash(message: str, *, level: str = "success") -> None:
    """Dépose un message que le PROCHAIN rendu affichera. À appeler avant `st.rerun()`."""
    st.session_state[_CLE_MESSAGE] = (level, message)


def show_flash() -> None:
    """Affiche et CONSOMME le message déposé. À appeler en tête de page.

    Consommé, pas seulement lu : sans le `pop`, le message resterait affiché à chaque
    rendu suivant et deviendrait le bruit qu'on apprend à ignorer.
    """
    depose = st.session_state.pop(_CLE_MESSAGE, None)
    if not depose:
        return
    level, message = depose
    {"success": st.success, "info": st.info,
     "warning": st.warning, "error": st.error}.get(level, st.info)(message)


def secondary_analyses(label: str | None = None, *, expanded: bool = False):
    """Collapsed container for charts that refine a decision but never make one.

    Used as a context manager, exactly like st.expander:

        with secondary_analyses():
            st.plotly_chart(fig_detail, width="stretch")

    Collapsed BY DEFAULT: the point is the first screen. Charts moved in here are
    still one click away — nothing is deleted, so a view can be re-balanced later
    without recovering lost code.

    `expanded=True` is an opt-in, per view, for the case where the refining figure
    is the one the artist actually came for. It changes only what is VISIBLE: a
    Streamlit expander always executes its body, so an opened drawer costs no extra
    query. ⚠️ The two chart-budget guards
    (`test_chart_budget`, `test_a_view_opens_on_one_decision`) shield a
    `secondary_analyses(...)` block by NAME, not by its `expanded` value — an opened
    drawer is therefore invisible to them. Opening one is a deliberate act whose
    first-screen cost has to be counted by hand.
    """
    return st.expander(
        label or t("ui.secondary_analyses", "📊 Analyses détaillées"),
        expanded=expanded,
    )
