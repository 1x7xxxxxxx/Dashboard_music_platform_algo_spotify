"""La langue choisie par un utilisateur, retenue d'une session à l'autre.

Type: Utility
Uses: PostgresHandler (via project_db), saas_users.lang
Triggers: le sélecteur de langue (écriture), la connexion (lecture)
Persists in: saas_users.lang

Pourquoi un module séparé de `i18n.py`
--------------------------------------
`i18n.py` est appelé par des surfaces sans base de données — l'export PDF headless,
les DAGs, les tests. Y mettre une écriture SQL ferait dépendre la traduction d'une
connexion, et casserait précisément les appelants qui n'en ont pas. Le choix
persistant est donc ici, et `i18n` reste pur.

Ce que la persistance ajoute, et ce qu'elle ne remplace pas
-----------------------------------------------------------
Avant : `st.session_state['lang']` + le paramètre d'URL `?lang=`. Ce couple existe
pour une raison qui n'a pas disparu — le login appelle `session_state.clear()`
(correctif de fixation de session MEDIUM-01), donc un choix fait AVANT connexion
serait effacé sans l'URL. Il survit à la connexion, pas à la fermeture de l'onglet.

Cette couche ajoute la mémoire longue, pour un utilisateur connecté seulement : un
visiteur anonyme n'a pas de ligne où l'écrire, et son choix continue de vivre dans
l'URL. Les deux mécanismes se complètent, aucun ne remplace l'autre.

NULL ≠ 'fr' : NULL veut dire « n'a jamais choisi », et permet au défaut de l'app de
changer un jour sans écraser une décision explicite.
"""
from __future__ import annotations

import logging

import streamlit as st

logger = logging.getLogger(__name__)

_LANGS = ("fr", "en")

# Ce que cette session a DÉJÀ écrit en base, par utilisateur. Voir `remember_lang`.
_WROTE_KEY = "_lang_persisted"


def load_preferred_lang(user_id: int | None) -> str | None:
    """La langue enregistrée pour cet utilisateur, ou None. Ne lève jamais."""
    if not user_id:
        return None
    try:
        from src.dashboard.utils import project_db
        with project_db() as db:
            row = db.fetch_query("SELECT lang FROM saas_users WHERE id = %s", (user_id,))
        value = row[0][0] if row else None
        return value if value in _LANGS else None
    except Exception as e:  # noqa: BLE001 — une préférence absente n'empêche pas d'entrer
        logger.warning("could not read the language preference for %s: %s",
                       user_id, type(e).__name__)
        return None


def mark_lang_persisted(user_id: int, lang: str) -> None:
    """Déclare qu'une valeur est DÉJÀ en base — au login, après lecture."""
    if lang in _LANGS and user_id:
        st.session_state[_WROTE_KEY] = (user_id, lang)


def remember_lang(lang: str) -> None:
    """Enregistre le choix pour l'utilisateur connecté. Sans effet si anonyme.

    Best-effort de bout en bout : un échec d'écriture ne doit pas empêcher la langue
    de changer à l'écran, qui est ce que la personne vient de demander.
    """
    if lang not in _LANGS:
        return
    user_id = st.session_state.get("user_id")
    if not user_id:
        return

    # ÉCRIRE SEULEMENT QUAND LE CHOIX CHANGE.
    #
    # Le sélecteur est re-rendu à CHAQUE rerun Streamlit — donc à chaque clic, chaque
    # changement de filtre, chaque navigation — et il appelait cette fonction sans
    # rien comparer. Mesuré le 2026-09-10 en production : 932 UPDATE sur `saas_users`
    # pour 447 vues de page, soit deux écritures par page pour une valeur qui n'avait
    # pas bougé. Chacune ouvre une connexion, prend un verrou de ligne et produit une
    # version morte que l'autovacuum devra reprendre.
    #
    # Le repère vit dans la session, pas dans un cache : `session_state.clear()` au
    # login (correctif de fixation de session) le remet à zéro, ce qui est le
    # comportement voulu — une session neuve réécrit une fois, puis se tait.
    already = st.session_state.get(_WROTE_KEY)
    if already == (user_id, lang):
        return

    try:
        from src.dashboard.utils import project_db
        with project_db() as db:
            db.execute_query("UPDATE saas_users SET lang = %s WHERE id = %s",
                             (lang, user_id))
        # Marqué APRÈS le succès : une écriture qui a échoué doit être retentée au
        # rerun suivant, sinon le choix serait perdu sans que rien ne le dise.
        st.session_state[_WROTE_KEY] = (user_id, lang)
    except Exception as e:  # noqa: BLE001
        logger.warning("could not remember the language for %s: %s",
                       user_id, type(e).__name__)
