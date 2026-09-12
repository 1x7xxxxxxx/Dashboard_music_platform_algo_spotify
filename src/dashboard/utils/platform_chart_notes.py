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
`unmeasured_spans` et `_hatch_traces` ne sont pas ici : une bande hachurée est un
pixel, pas une note. C'est précisément l'échange du 2026-09-12 — la phrase
`t_missing` a été supprimée parce que la hachure dit la même chose, mieux. Elles
vivent depuis le même jour dans `platform_absence.py`, avec `known` et les deux
surfaces de préhistoire ; ce fichier ne garde que ce qui s'ÉCRIT.

L'exception assumée est `render_collection_start_note` : elle écrit une phrase, donc
elle est une note — mais elle existe parce que la hachure NE PEUT PAS porter son
fait. Une hachure est pleine hauteur, donc elle parle de toutes les plateformes à la
fois, alors que « YouTube n'était pas encore collectée » n'en concerne qu'une.
"""
from __future__ import annotations

import streamlit as st

from src.dashboard.utils.platform_timeseries import MISSING_HISTORY, PLATFORM_LABELS


# Le mot qui suit le nombre, dans le sous-titre. Il compte des SEAUX, pas des unités
# de temps écoulé — et la nuance n'est pas de la pédanterie : sur une fenêtre de 12 mois
# à cheval sur deux années civiles, la figure a 2 seaux annuels et disait « sur
# 2 années », ce qui se lit comme deux ans d'historique. Vu au rendu le 2026-09-10.
_STEP_UNITS = {"day": "jours", "week": "semaines", "month": "mois", "year": "années"}

# `_STEP_BUCKETS` VIVAIT ICI et a été RETIRÉE le 2026-09-12, avec son dernier
# lecteur. Elle disait « points annuels » là où `_STEP_UNITS` dit « années », pour
# une raison juste : une fenêtre de 12 mois donne DEUX seaux annuels, et écrire
# « sur 2 années » se lit comme deux ans d'historique.
#
# Le seul endroit qui comptait encore des seaux était la cellule « 181 semaines » de
# la ligne Total du récapitulatif, partie avec la colonne d'unité (« enlève l'unité
# également inutile »). Une constante gardée sans lecteur est « du code correct que
# rien n'atteint » ; lui inventer un lecteur pour la sauver est pire — c'est ajouter
# une phrase à l'écran pour faire taire un test.
#
# Ce qui reste tenu : `_STEP_UNITS` est lue par `t_too_coarse`, et son pluriel vient
# de la table et non d'un « s » collé (le « moiss » du 2026-09-12). Si une surface
# recommence un jour à COMPTER des seaux, c'est là que la distinction revient.



def _render_recap(slot, span: list, aligned: dict, aligned_raw: dict, order: list,
                  thin: dict, mode: str, step: str, extra=None,
                  metrics=None) -> None:
    """Les INDICATEURS DÉRIVÉS, en boîtes, sous la figure qui les a produits.

    ── CE QUI A CHANGÉ LE 2026-09-12, ET POURQUOI CE N'EST PAS UNE SUPPRESSION ──

    Cette fonction rendait une TABLE MARKDOWN à droite de la figure : totaux par
    plateforme, Instagram, Apple, Meta, puis les indicateurs. Retirée sur demande —
    « supprime-le et remplace-le par celui qu'on a validé qui est actuellement placé
    en haut du graphique ». Il y avait deux récapitulatifs sur le même écran, et ils
    répondaient à la même question avec deux mises en page.

    **Les totaux sont partis dans les boîtes du haut, pas à la poubelle** : chaque
    plateforme y a sa boîte, avec en plus l'écart contre la période précédente que
    la table ne portait pas, et Meta Ads y porte sa dépense ET son meilleur CPR avec
    le budget associé. Ce qui reste ici est ce qu'AUCUNE de ces boîtes ne peut
    porter : les chiffres qui dépendent de ce que la figure a RÉELLEMENT dessiné, au
    grain qu'elle a retenu — meilleur pas, coût par écoute, plateforme dominante,
    périodes mesurées, probabilité de déclenchement.

    C'est la seule raison pour laquelle cette surface survit. Une vue ne peut pas
    les recalculer : « Automatique » peut descendre au pas semaine sans la prévenir,
    et deux chemins de calcul pour la même période finissent par diverger — le
    défaut exact qui avait fait retirer les tuiles le 2026-09-10.

    **`slot` n'est plus une colonne.** Sans conteneur, l'écriture tombe là où
    `_render_recap` est appelée, c'est-à-dire juste APRÈS `st.plotly_chart` : sous
    la figure, dans l'ordre de lecture. Un slot reste accepté pour les appelants qui
    en passent un (le mode facettes), mais l'accueil n'en passe plus.

    **Les aides ne sont plus une ligne de prose.** Elles étaient concaténées en un
    `st.caption` que l'artiste a nommé inutile — « 🔮 probabilité PRÉDITE … · ↔️
    écart avec la fenêtre de MÊME LONGUEUR … ». Chacune est maintenant l'infobulle
    de SA boîte : disponible pour qui la cherche, invisible pour qui ne la cherche
    pas. Une explication qui s'impose à tous les lecteurs pour servir le premier
    d'entre eux est un coût permanent pour un bénéfice unique.
    """
    from src.dashboard.utils.i18n import t

    rows = [r for r in (metrics or []) if r and r[1]]
    if not rows:
        return

    import contextlib
    # `True` VEUT DIRE « rends-les, sans conteneur ». L'accueil le passe pour que
    # les boîtes tombent sous la figure ; le mode facettes passe une vraie colonne.
    # Distinguer « pas de récapitulatif » (`None`) de « un récapitulatif sans
    # colonne » (`True`) est ce qui évite un booléen implicite sur un objet
    # Streamlit, dont la véracité n'est pas garantie.
    ctx = (contextlib.nullcontext() if slot is None or slot is True else slot)
    with ctx:
        st.caption(t("platform_chart.recap_metrics", "Indicateurs"))
        # QUATRE PAR RANGÉE AU PLUS. À cinq, les libellés — « 🔮 Proba.
        # déclenchement prédite » est le plus long — passent à la ligne au milieu
        # d'un mot sur un écran de portable, et une boîte dont le titre est coupé
        # se lit plus lentement qu'une ligne de table.
        for i in range(0, len(rows), 4):
            chunk = rows[i:i + 4]
            cols = st.columns(4)
            for col, (label, value, help_text) in zip(cols, chunk):
                with col.container(border=True):
                    st.metric(label, value, help=help_text)


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
    # LA MENTION DU REPLI A ÉTÉ RÉDUITE LE 2026-09-12, PAS SUPPRIMÉE — et la
    # nuance est tout le sujet.
    #
    # Elle disait : « **Par année** ne donne qu'un seul point sur cette période —
    # une aire a besoin d'au moins deux. Affiché **Par mois**. 🎎 Apple Music
    # n'existe qu'au pas Par année : élargis la période pour le retrouver. » Nommée
    # inutile par l'artiste, et elle l'était : trois phrases pour s'excuser d'un
    # choix que la barre venait elle-même d'offrir.
    #
    # La CAUSE a été retirée à la source — la barre de l'accueil ne propose plus
    # qu'un pas rendant au moins deux seaux (`_offers`, `views/home.py`). Sur
    # l'accueil, cette ligne ne peut donc plus s'afficher.
    #
    # ⚠️ MAIS `render_platform_chart` A D'AUTRES APPELANTS — l'export PDF et les
    # vues qui lui passent un pas fixe — et là le repli reste possible. La retirer
    # entièrement l'aurait rendu SILENCIEUX chez eux : un réglage changé sans le
    # dire se lit comme une panne, et c'est exactement ce que
    # `test_a_step_that_yields_one_bucket_falls_back` garde depuis le 2026-09-08.
    # Ce test m'a arrêté ; sans lui la régression partait en production.
    #
    # Ce qui reste est le FAIT, sans l'excuse : quel pas est affiché.
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
    """Le pas réellement appliqué, quand ce n'est pas celui qui a été demandé.

    UNE PHRASE, ET RIEN D'AUTRE. La version longue expliquait la règle des deux
    points et rappelait où trouver Apple Music — deux informations vraies dont
    personne n'avait besoin à cet instant, sous une figure qui, elle, se dessinait
    correctement. Le lecteur a besoin de savoir QUEL pas il regarde ; pourquoi
    l'autre était impossible ne change aucune de ses décisions.
    """
    from src.dashboard.utils.i18n import t
    names = {"day": "Par jour", "week": "Par semaine", "month": "Par mois",
             "year": "Par année"}
    # LES DEUX PAS, PAS UN SEUL. « Affiché **Par mois**. » dit ce qu'on regarde mais
    # pas qu'un choix a été repris : l'artiste qui a cliqué « Par année » doit faire
    # le rapprochement lui-même. Nommer les deux coûte trois mots et supprime
    # l'inférence — c'est ce que garde
    # `test_a_step_that_yields_one_bucket_falls_back` depuis le 2026-09-08, et il a
    # attrapé la version à un seul pas avant qu'elle parte.
    return t("platform_chart.coarsened", "**{asked}** → affiché **{used}**.").format(
        asked=names.get(asked, asked), used=names.get(used, used))


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


_MONTHS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
              "août", "septembre", "octobre", "novembre", "décembre")


def _bucket_label(day, step: str) -> str:
    """Le seau, nommé comme un seau — jamais comme une date qu'on n'a pas mesurée.

    ⚠️ `span[i]` est le DÉBUT DU SEAU, pas la date de la mesure. Au pas mois, la
    première mesure YouTube du 30/11/2025 tombe dans le seau `2025-12-01`, et
    l'écrire « depuis le 01/12/2025 » invente un jour. C'est le même piège qu'un
    seuil écrit au pas jour et relu au pas semaine, ici sur un LIBELLÉ : la valeur
    est juste, l'unité est fausse.
    """
    from src.dashboard.utils.i18n import t

    if step == "month":
        return f"{_MONTHS_FR[day.month - 1]} {day.year}"
    if step == "year":
        return str(day.year)
    if step == "week":
        return t("platform_chart.week_of", "la semaine du {d}").format(
            d=day.strftime("%d/%m/%Y"))
    return t("platform_chart.day_of", "le {d}").format(d=day.strftime("%d/%m/%Y"))


def render_collection_start_note(starts: list, step: str = "day") -> None:
    """« Mesurée depuis le … », une ligne par plateforme arrivée après la fenêtre.

    La hachure ne peut pas porter ce fait : elle est pleine hauteur, donc elle parle
    de toutes les plateformes à la fois, alors que la préhistoire est individuelle —
    Spotify mesure depuis 2023 pendant que SoundCloud n'existe pas encore. Tenter de
    le dire en hachurant faisait passer **1 185 jours sur 1 350** sous les hachures
    pour l'artiste 1, et affirmait que rien n'avait été mesuré depuis 2023.

    Le survol le dit aussi, plateforme par plateforme. Cette note existe parce qu'un
    fait qui ne se lit qu'au survol ne se lit pas : « ça a l'air de commencer en
    novembre et décembre 2025 » a été écrit en REGARDANT la figure, pas en la
    survolant.
    """
    from src.dashboard.utils.i18n import t

    if not starts:
        return
    st.caption(" · ".join(
        t("platform_chart.collected_since", "{label} mesurée depuis {since}")
        .format(label=label, since=_bucket_label(since, step))
        for label, since in starts))


def render_missing_history_note() -> None:
    """Nomme ce qui n'a PAS de série, plutôt que de le dessiner à zéro.

    Une plateforme absente sans explication se lit comme une panne — c'est la leçon
    de `_silence_reason` et de la matrice d'état, appliquée à une figure.
    """
    for label, why in MISSING_HISTORY.values():
        st.caption(f"{label} — {why}.")
