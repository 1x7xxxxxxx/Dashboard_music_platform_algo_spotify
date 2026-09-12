"""Ce qui s'écrit À CÔTÉ de la figure : le récapitulatif chiffré et les notes.

Type: Sub
Uses: streamlit, i18n, platform_timeseries
Depends on: src/dashboard/utils/platform_timeseries.py
Persists in: nothing — rendu seulement

Pourquoi un module séparé
-------------------------
Extrait de `platform_chart.py` le 2026-09-12, quand le cliquet de longueur a refusé
de le laisser franchir 1 200 lignes. Le découpage n'est pas arbitraire : il suit la
frontière que la figure elle-même trace depuis le 2026-09-10.

`platform_chart` répond à « que dessine-t-on ? » — des seaux, des tranches, une pile,
des facettes. Ce module répond à « que dit-on à côté ? » — le tableau des totaux de
la période, et les phrases qui nomment ce que la figure NE PEUT PAS montrer : un seau
élargi faute de points, une plateforme trop mince pour une aire, un pas trop grossier
pour elle, des écoutes mesurées qu'aucune date ne peut porter.

Le vocabulaire des pas vit ici et non là-bas, et c'est le sens de la dépendance : il
sert à ÉCRIRE (« sur 2 points annuels »), la figure ne fait que l'emprunter pour son
sous-titre. L'import va donc dans un seul sens — `platform_chart` importe ce module,
jamais l'inverse.

Ce qui N'EST PAS ici
--------------------
`unmeasured_spans` et `_hatch_traces` sont restés dans la figure : une bande hachurée
est un pixel, pas une note. C'est précisément l'échange du 2026-09-12 — la phrase
`t_missing` a été supprimée parce que la hachure dit la même chose, mieux.
"""
from __future__ import annotations

import streamlit as st

from src.dashboard.utils.platform_timeseries import MISSING_HISTORY, PLATFORM_LABELS


# Le mot qui suit le nombre, dans le sous-titre. Il compte des SEAUX, pas des unités
# de temps écoulé — et la nuance n'est pas de la pédanterie : sur une fenêtre de 12 mois
# à cheval sur deux années civiles, la figure a 2 seaux annuels et disait « sur
# 2 années », ce qui se lit comme deux ans d'historique. Vu au rendu le 2026-09-10.
_STEP_UNITS = {"day": "jours", "week": "semaines", "month": "mois", "year": "années"}

# Le mot juste quand le seau peut être PLUS LARGE que la fenêtre. Au pas jour et au pas
# semaine, un seau vaut à peu près son unité et la confusion n'existe pas ; au pas
# annuel, un seau peut ne couvrir qu'un mois de la fenêtre demandée.
_STEP_BUCKETS = {"day": "jours", "week": "semaines", "month": "mois",
                 "year": "points annuels"}



def _render_recap(slot, span: list, aligned: dict, aligned_raw: dict, order: list,
                  thin: dict, mode: str, step: str) -> None:
    """Le tableau à droite de la figure, DÉRIVÉ des séries que la figure trace.

    Il avait été retiré le 2026-09-10 pour une raison qui tient toujours : les tuiles
    d'alors montraient le total DEPUIS LE DÉBUT à côté d'une courbe bornée à la
    période, et les deux chiffres ne pouvaient pas se répondre. « Où est passé le
    tableau juste à côté du graphique qui montre les métriques » (2026-09-12) —
    remis, mais construit autrement : il ne pose AUCUNE requête et ne relit AUCUNE
    table. Il somme `aligned`/`aligned_raw`, c'est-à-dire exactement les listes
    remises à Plotly. Les deux nombres ne peuvent donc pas diverger : ce sont les
    mêmes.

    La colonne « mesurés » est ce qui remplace `t_missing` : elle dit COMBIEN de pas
    chaque plateforme a réellement renseignés, là où la hachure dit seulement OÙ le
    trou se trouve. Une plateforme sans mesure porte « — », jamais « 0 » — un zéro
    affirmerait une écoute comptée.

    Les plateformes trop minces pour une aire (`thin`) y figurent aussi : `t_too_thin`
    promet « ses chiffres restent dans le tableau ci-dessous » depuis le 2026-09-08, et
    la phrase était fausse depuis que le tableau avait disparu.
    """
    from src.dashboard.utils.i18n import t

    def _num(v) -> str:
        return f"{int(round(v)):,}".replace(",", "\u202f")

    unit = _STEP_BUCKETS.get(step, "points")
    rows, grand = [], 0
    for pkey in order:
        drawn = aligned.get(pkey) or []
        measured = sum(1 for v in drawn if v is not None)
        if mode == "cumulative":
            # Un cumul ne se somme pas : le total de la période est le DERNIER niveau
            # atteint. Additionner des cumuls avait produit 16 568 594 écoutes pour un
            # artiste qui en a 186 000.
            value = next((v for v in reversed(drawn) if v is not None), None)
        elif mode == "share":
            # `aligned` porte des pourcentages ici ; le total en écoutes se lit sur la
            # série d'avant conversion, sinon la colonne additionnerait des parts.
            value = sum(v for v in (aligned_raw.get(pkey) or []) if v) or None
        else:
            value = sum(v for v in drawn if v) or None
        # La ligne Total est celle du sous-titre de la figure, par construction :
        # somme des derniers niveaux en cumulé, somme des seaux sinon.
        grand += value or 0
        rows.append((PLATFORM_LABELS[pkey], value, measured))
    for label, measured, _plage in thin.values():
        rows.append((label, None, measured))

    with slot:
        st.markdown("**" + t("platform_chart.recap_title", "Sur la période") + "**")
        head = (t("platform_chart.recap_platform", "Plateforme"),
                t("platform_chart.recap_total", "Total"),
                t("platform_chart.recap_measured", "Mesurés"))
        lines = [f"| {head[0]} | {head[1]} | {head[2]} |", "|:--|--:|--:|"]
        for label, value, measured in rows:
            lines.append(
                f"| {label} | {_num(value) if value is not None else '—'} "
                f"| {measured if measured else '—'} / {len(span)} |")
        lines.append(
            f"| **{t('platform_chart.recap_all', 'Total')}** | **{_num(grand)}** "
            f"| {len(span)} {unit} |")
        st.markdown("\n".join(lines))


def _render_notes(thin: dict, coarse: list, step: str, *, coarsened=None,
                  mode: str = "absolute", discarded: dict | None = None) -> None:
    """Ce que la figure ne peut pas dessiner, écrit sous elle. Jamais tu.

    UNE NOTE QUI DÉCRIT UNE AUTRE FIGURE QUE CELLE AFFICHÉE EST PIRE QUE PAS DE NOTE.
    Signalé le 2026-09-11 : « je n'ai aucune data sur YouTube depuis le début ». La
    figure traçait pourtant YouTube à 118 334, et c'est la PROSE qui disait le
    contraire — « 🎬 YouTube 26 [semaines non mesurées], leur aire s'interrompt là ».
    Cette note-là (`t_missing`) est partie le 2026-09-12 : la bande hachurée montre le
    trou à sa place, et le récapitulatif le chiffre. Avec elle sont partis les cinq
    paramètres qu'elle seule lisait — `span`, `aligned_raw`, `order`, `stacked`,
    `served`. Un paramètre que plus personne ne lit est une invitation à recalculer
    quelque chose pour rien.

    Ce qui reste dit ce que la figure NE PEUT PAS montrer : un seau élargi, une
    plateforme trop mince pour un total honnête, un pas trop grossier pour elle, et
    des écoutes mesurées qu'aucune date ne peut porter.
    """
    if coarsened:
        st.caption(t_coarsened(*coarsened))
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
    names = {"day": "Par jour", "week": "Par semaine", "month": "Par mois",
             "year": "Par année"}
    return t("platform_chart.coarsened",
             "**{asked}** ne donne qu'un seul point sur cette période — une aire a "
             "besoin d'au moins deux. Affiché **{used}**. 🎎 Apple Music n'existe "
             "qu'au pas Par année : élargis la période pour le retrouver."
             ).format(asked=names.get(asked, asked), used=names.get(used, used))


def t_too_coarse(label: str, step: str) -> str:
    """Pourquoi une plateforme disparaît à CE pas, alors qu'elle existe au pas du jour."""
    from src.dashboard.utils.i18n import t
    # Le pluriel vient de `_STEP_UNITS` et n'est plus fabriqué en collant un « s » :
    # la table locale qui vivait ici disait « mois » au singulier, et le pas MOIS,
    # ouvert le 2026-09-12, aurait affiché « aucune de ses moiss ».
    unit = _STEP_UNITS.get(step, "périodes")
    return t("platform_chart.too_coarse",
             "{label} n'apparaît pas à ce pas : aucune de ses {unit} n'est mesurée "
             "sur assez de jours pour en faire un total honnête. Choisis un pas plus "
             "fin pour la voir."
             ).format(label=label, unit=unit)


# `t_missing` VIVAIT ICI — « Sur 194 semaines, certaines plateformes n'ont pas été
# mesurées partout (🎵 Spotify 1). Leur aire s'interrompt là… ». Retirée le 2026-09-12.
#
# Elle nommait en prose ce que la figure ne savait pas montrer : OÙ la mesure manque.
# La bande hachurée le montre maintenant, au bon endroit de l'axe, et son entrée de
# légende « ▨ Aucune mesure » le nomme. Le COMBIEN par plateforme, que la hachure ne
# porte pas, est passé dans le récapitulatif à droite de la figure — colonne « jours
# mesurés », avec un « — » là où il n'y a pas de mesure.
#
# `gap_counts` reste : c'est le calcul, et il alimente désormais le récapitulatif.


def render_missing_history_note() -> None:
    """Nomme ce qui n'a PAS de série, plutôt que de le dessiner à zéro.

    Une plateforme absente sans explication se lit comme une panne — c'est la leçon
    de `_silence_reason` et de la matrice d'état, appliquée à une figure.
    """
    for label, why in MISSING_HISTORY.values():
        st.caption(f"{label} — {why}.")
