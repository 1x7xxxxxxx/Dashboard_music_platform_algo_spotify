"""Le cadenas du menu — ce qu'il dit, et ce qu'il ne disait pas.

Type: Sub
Uses: rien (une fonction pure)
Depends on: rien — le PLAN et l'ensemble des pages payantes lui sont PASSÉS
Persists in: nothing

Pourquoi ce module existe
-------------------------
Deux raisons, et la seconde est celle qui l'a rendu obligatoire.

**Le fond.** Avant le 2026-09-21, un 🔒 marquait « verrouillé » et l'absence de 🔒
marquait TOUT le reste : une page gratuite et une page Premium que l'artiste PAIE
s'écrivaient exactement pareil dans le menu. Un abonné n'avait donc aucun moyen de
voir ce que son abonnement lui ouvre — c'est-à-dire ce qu'on lui facture. Deux
faits différents demandent deux marques :

    🔒  ce plan ne l'ouvre pas          (cadenas fermé)
    🔓  ce plan l'ouvre, et c'est payant (cadenas ouvert)
    —   gratuit, aucune marque

**La forme.** `app.py` est à son plafond de longueur (cliquet
`tests/test_a_file_only_gets_shorter.py`), et l'ajout du second cadenas l'a fait
passer de 997 à 1 017 lignes. Le cliquet a fait son travail : il a refusé la dette
et rendu l'extraction obligatoire, au lieu d'être relevé. C'est le même geste que
`nav_sections.py` le 2026-09-12, et pour la même raison.

En sortant, la règle devient TESTABLE sans rendre une page : `badge()` ne touche
ni Streamlit, ni la session, ni la base. C'est le gain réel de l'extraction, pas
un effet de bord.

⚠️ LA COULEUR ENVELOPPE LE SEUL CADENAS, JAMAIS LE LIBELLÉ.

Ce fichier a affirmé l'inverse jusqu'au 2026-09-22 — « la couleur passe par
l'emoji, pas par du markdown », au motif que `:green[…]` teindrait le libellé
entier. C'était un mauvais diagnostic d'un vrai symptôme : la source de Streamlit
1.63 dit, pour le paramètre `options` de `st.radio`, **« Labels can include
markdown as described in the label parameter »**
(`streamlit/elements/widgets/radio.py:261`). Le markdown fonctionne ; ce qui
teignait tout, c'était d'envelopper la chaîne ENTIÈRE.

Le fragment coloré s'arrête donc au cadenas — `:red[🔒] Mon libellé` — et le
libellé reste neutre. Un libellé de menu entièrement rouge se lit comme une page
en panne, pas comme une page à vendre.

Demandé le 2026-09-22 : « rouge et vert mais léger ». Les teintes de thème
Streamlit sont plus douces qu'un carré plein 🟥/🟩 — un menu n'est pas un tableau
d'alarmes, et un cadenas qui crie se fait ignorer comme tout ce qui crie.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable

# ── LES COULEURS — demandées le 2026-09-22 : « rouge et vert mais léger » ────
#
# Streamlit teinte un fragment de markdown par `:red[…]` / `:green[…]`. Ce sont
# des teintes de thème, plus douces qu'un carré 🟥/🟩 plein — c'est ce que « léger »
# demandait, et c'est aussi ce qui évite qu'un menu ressemble à un tableau
# d'alarmes.
#
# ⚠️ La couleur enveloppe **le seul cadenas**, jamais le libellé. Un libellé de menu
# entièrement rouge se lit comme une page en panne, pas comme une page à vendre.
LOCKED = ":red[🔒] "
PAID_AND_OPEN = ":green[🔓] "
FREE = ""


def badge(page_key: str, *, is_locked: Callable[[str], bool],
          paid_pages: Iterable[str]) -> str:
    """La marque qui précède le libellé de `page_key` dans le menu.

    `is_locked` est la question « CE plan interdit-il cette page ? », qui n'a
    qu'une définition (`stripe_schema.page_is_locked`) et qu'on ne recopie pas
    ici. `paid_pages` est l'ensemble des pages qu'un plan GRATUIT n'ouvre pas —
    c'est-à-dire « ce qui se vend », indépendamment du plan du visiteur.

    Les deux arguments sont injectés plutôt qu'importés : c'est ce qui permet de
    vérifier les quatre cas (gratuit/payant × Free/Premium) sans base ni session.
    """
    if is_locked(page_key):
        return LOCKED
    return PAID_AND_OPEN if page_key in set(paid_pages) else FREE


# ── LE CADENAS DE SECTION — 2026-09-22 ────────────────────────────────────────
#
# Le cadenas par PAGE existait depuis le 2026-09-21. Il manquait celui de la
# SECTION, et l'écart se voit sur le menu d'un abonné : la section « 💎 Premium —
# ce que l'abonnement ouvre » portait six 🔓 sous un titre muet. Le titre est
# pourtant ce qu'on lit en premier, et c'est lui qui devrait dire « cette partie
# t'est ouverte ».
#
# Trois états, et le troisième est celui qui demande de réfléchir :
#
#   🔒        aucune page de la section n'est ouverte à ce plan
#   🔓 vert   la section est ENTIÈREMENT payante ET entièrement ouverte
#   (rien)    la section est gratuite, ou MIXTE
#
# ⚠️ **Une section mixte ne porte aucune marque, et c'est délibéré.** Lui donner le
# cadenas de sa majorité ferait dire au titre quelque chose de faux pour la
# minorité — un artiste Free lisant 🔓 sur une section dont deux pages sur cinq
# lui sont fermées conclurait que tout est ouvert. Les pastilles par page disent
# déjà la vérité ligne à ligne ; le titre ne parle que quand il peut parler pour
# toutes.
VERT_OUVERT = ":green[🔓]"
ROUGE_FERME = ":red[🔒]"
SECTION_AUCUNE = ""


def section_badge(page_keys: Iterable[str], *, is_locked: Callable[[str], bool],
                  paid_pages: Iterable[str]) -> str:
    """La marque d'un EN-TÊTE de section, ou la chaîne vide.

    ⚠️ Elle rend du markdown coloré (`:green[…]`), ce que la pastille par page ne
    peut pas faire : une option de `st.radio` teinte le libellé ENTIER, et un
    libellé de menu coloré se lit comme un état d'erreur. Un en-tête de section,
    lui, est un `st.markdown` à part — la couleur n'y déborde sur rien.
    """
    cles = [k for k in (page_keys or [])]
    if not cles:
        return SECTION_AUCUNE
    payantes = set(paid_pages)
    if not all(k in payantes for k in cles):
        return SECTION_AUCUNE                    # gratuite ou mixte : on se tait
    if all(is_locked(k) for k in cles):
        return ROUGE_FERME
    if any(is_locked(k) for k in cles):
        return SECTION_AUCUNE                    # payante mais partiellement ouverte
    return VERT_OUVERT


def _neighbour_pages(rendered, current: str, is_locked) -> tuple:
    """(page précédente, page suivante) dans l'ordre du menu — ou None de chaque côté.

    Les pages VERROUILLÉES sont sautées : une flèche est un geste d'exploration, et
    l'envoyer buter sur le paywall une entrée sur deux transforme l'exploration en
    parcours d'obstacles. Elles restent atteignables par le menu, avec leur 🔒, qui
    est le bon endroit pour proposer une montée en gamme — le clic y est délibéré.

    Pure : elle ne lit ni Streamlit ni la session, donc l'ordre se teste sans rendre
    une page.

    ⚠️ Descendue d'`app.py` le 2026-09-22, et pas par goût de ranger : ce fichier
    est gelé à 997 lignes par `tests/test_a_file_only_gets_shorter.py`, et le
    cadenas de section l'a fait passer à 1 006. Le cliquet a refusé la dette —
    « ce qui entre dans ce fichier doit en faire sortir autant ». Cette fonction
    était le meilleur candidat : purement navigationnelle, sans Streamlit, et
    déjà testée hors rendu.
    """
    order = [key for _, _, items in rendered for _, key in items
             if not is_locked(key)]
    if current not in order:
        return None, None
    i = order.index(current)
    return (order[i - 1] if i > 0 else None,
            order[i + 1] if i < len(order) - 1 else None)
