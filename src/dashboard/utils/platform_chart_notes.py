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
    """UN tableau à droite de la figure, DÉRIVÉ des séries qu'elle trace.

    Il avait été retiré le 2026-09-10 pour une raison qui tient toujours : les tuiles
    d'alors montraient le total DEPUIS LE DÉBUT à côté d'une courbe bornée à la
    période, et les deux chiffres ne pouvaient pas se répondre. Remis le 2026-09-12,
    mais construit autrement : il ne pose AUCUNE requête et ne relit AUCUNE table. Il
    somme `aligned`/`aligned_raw`, c'est-à-dire exactement les listes remises à
    Plotly. Les deux nombres ne peuvent donc pas diverger : ce sont les mêmes.

    UN SEUL TABLEAU, DEUX COLONNES — et trois choses en moins, toutes demandées le
    2026-09-12 après lecture à l'écran :

    * « À quoi correspond la colonne mesurés ? Enlève-la. » Elle disait `171 / 181`,
      c'est-à-dire le nombre de pas réellement renseignés. L'information est réelle,
      mais elle répond à une question que le lecteur ne se pose pas devant un
      récapitulatif — et la hachure de la figure la porte déjà, à l'endroit exact où
      le trou se trouve. Une question à laquelle il faut demander la réponse n'est
      pas une colonne.
    * « Fais uniquement 1 tableau. » Il y en avait deux, séparés parce qu'on
      n'additionne pas des abonnés avec des euros. La séparation reste — mais par une
      ligne de section DANS le tableau, pas par une seconde table. La ligne « Total »
      ne compte toujours que les écoutes, et elle est posée AVANT la section suivante
      pour qu'on voie ce qu'elle somme.
    * « Enlève "Sur la période" en haut et l'unité. » Le titre redisait le filtre qui
      est juste au-dessus. L'unité redevient un suffixe du LIBELLÉ (`📸 Instagram
      (abonnés)`) : elle coûtait une colonne entière pour trois lignes, et c'est la
      colonne qui empêchait la table d'être étroite.

    `metrics` — LES LIGNES QUI NE SONT PAS DES PLATEFORMES. Meilleur jour, coût par
    écoute, meilleur CPR, probabilité de déclenchement. Elles arrivent déjà formatées
    en `(libellé, valeur, aide)` : cette fonction ne calcule pas de métrique, elle
    dessine un tableau.
    """
    from src.dashboard.utils.i18n import t

    def _num(v) -> str:
        return f"{int(round(v)):,}".replace(",", "\u202f")

    rows, grand = [], 0
    for pkey in order:
        drawn = aligned.get(pkey) or []
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
        grand += value or 0
        rows.append((PLATFORM_LABELS[pkey], value))
    # Les plateformes trop minces pour une aire y figurent aussi : `t_too_thin` promet
    # « ses chiffres restent dans le tableau ci-dessous » depuis le 2026-09-08, et la
    # phrase était fausse depuis que le tableau avait disparu.
    for label, _measured, _plage in thin.values():
        rows.append((label, None))

    with slot:
        lines = [f"| {t('platform_chart.recap_platform', 'Plateforme')} "
                 f"| {t('platform_chart.recap_total', 'Total')} |", "|:--|--:|"]
        lines += [f"| {lab} | {_num(v) if v is not None else '—'} |"
                  for lab, v in rows]
        # « TOTAL TRACÉ » ET NON « TOTAL », parce que les deux nombres DIFFÈRENT et
        # que le lecteur les voit ensemble. La bannière au-dessus de la figure porte
        # `combined_total`, qui compte TOUTES les plateformes de la période — Apple
        # comprise. Cette ligne-ci ne somme que les séries que la figure DESSINE, et
        # Apple n'en est pas : ses relevés sont des totaux de dépôt, traçables au
        # seul pas annuel. Mesuré à l'écran le 2026-09-12 : 308 060 en bannière,
        # 304 793 ici, l'écart valant exactement les 3 267 écoutes Apple listées
        # deux lignes plus bas.
        #
        # Nommer la portée coûte un mot ; ne pas la nommer, c'est remettre en place
        # la contradiction pour laquelle les tuiles avaient été retirées le
        # 2026-09-10 — deux nombres justes, côte à côte, qu'aucun titre ne distingue.
        lines.append(f"| **{t('platform_chart.recap_all', 'Total tracé')}** "
                     f"| **{_num(grand)}** |")
        # LA SECTION SUIVANTE EST SOUS LE TOTAL, jamais dedans. On n'additionne pas
        # des abonnés avec des euros ; une ligne de section le dit sans qu'il faille
        # une seconde table ni une colonne d'unité.
        rows_x = [(lab, val) for lab, val, _u in (extra or []) if val]
        if rows_x:
            lines.append(f"| *{t('platform_chart.recap_other', 'Autres plateformes')}"
                         f"* | |")
            lines += [f"| {lab} | {val} |" for lab, val in rows_x]
        rows_m = [r for r in (metrics or []) if r and r[1]]
        if rows_m:
            # « INDICATEURS » ET NON « SUR LA PÉRIODE » — demandé le 2026-09-12, et
            # le titre a d'abord disparu du HAUT de la table sans que cet intitulé
            # de section change. C'était la même faute deux fois : *tout* ce tableau
            # est sur la période, donc le dire ici ne distingue pas cette section
            # des deux autres — ça répète le filtre qui est trois lignes plus haut.
            # Une ligne de section doit nommer ce que la section EST : au-dessus des
            # plateformes et des écoutes, en dessous des chiffres DÉRIVÉS.
            lines.append(f"| *{t('platform_chart.recap_metrics', 'Indicateurs')}"
                         f"* | |")
            lines += [f"| {lab} | {val} |" for lab, val, _h in rows_m]
        st.markdown("\n".join(lines))
        # Les aides des métriques ne tiennent pas dans une cellule markdown : elles
        # vivent sous la table, en une seule ligne discrète. Sans elles, « 0,011 € »
        # et « 11,8 % » sont deux nombres dont on ne sait pas ce qu'ils mesurent.
        helps = [h for _l, _v, h in rows_m if h]
        if helps:
            st.caption(" · ".join(helps))


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
