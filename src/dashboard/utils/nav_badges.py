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

⚠️ LA COULEUR PASSE PAR L'EMOJI, PAS PAR DU MARKDOWN. Les options d'un `st.radio`
acceptent du markdown, mais `:green[…]` teinte le TEXTE du libellé entier, pas la
seule pastille — et un libellé de menu coloré se lit comme un état d'erreur. Le
cadenas porte donc sa couleur lui-même.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable

LOCKED = "🔒 "
PAID_AND_OPEN = "🔓 "
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
