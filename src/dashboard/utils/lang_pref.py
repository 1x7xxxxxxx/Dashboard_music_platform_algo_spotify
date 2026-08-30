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
    try:
        from src.dashboard.utils import project_db
        with project_db() as db:
            db.execute_query("UPDATE saas_users SET lang = %s WHERE id = %s",
                             (lang, user_id))
    except Exception as e:  # noqa: BLE001
        logger.warning("could not remember the language for %s: %s",
                       user_id, type(e).__name__)
