"""L'invalidation de cache traverse les instances — un compteur par locataire.

Type: Utility
Uses: src.database.postgres_handler (via l'appelant), streamlit (cache court)
Triggers: view_session() au seuil de chaque rendu ; clear_kpi_caches() à chaque écriture
Persists in: saas_artists.cache_epoch (migration 123)

Le défaut que ce module ferme
-----------------------------
`kpi_helpers.clear_kpi_caches()` purge onze `@st.cache_data(ttl=600)` — DANS LE
PROCESSUS QUI L'APPELLE, et nulle part ailleurs. Tant qu'il y a une instance, la phrase
« la purge est immédiate » est vraie. À deux instances elle devient fausse **sans
qu'une ligne de cache ne change** : un artiste déclenche une collecte sur A, voit ses
nouveaux chiffres, recharge, tombe sur B, et revoit les anciens pendant dix minutes.

C'est la même forme que les limiteurs de l'étape 1 — un état de processus dont
l'exactitude reposait sur le fait qu'il n'y avait qu'un processus.

Pourquoi un compteur relu, et pas une clé de cache
---------------------------------------------------
La solution « propre » consiste à faire entrer l'époque dans la CLÉ de chaque fonction
cachée. Elle a été écartée après lecture du code : les dix fonctions de `kpi_helpers`
et le cache de séries auraient changé de signature, et avec eux une quarantaine de
sites d'appel — pour un gain identique. Un correctif dont le diff est quarante fois
plus large qu'il ne doit l'être se relit mal et se révoque mal.

Ici, une seule couture (`view_session()`) lit l'époque et purge LOCALEMENT quand elle a
bougé. Les caches gardent leur signature ; `clear_kpi_caches()` reste l'unique porte de
purge, et vide aussi le cache de séries.

Ce que ça garantit, et ce que ça ne garantit PAS
-------------------------------------------------
Garantie : après une écriture sur l'instance A, toute autre instance manque son cache
au plus tard `_EPOCH_TTL` secondes plus tard — 30 s, contre les 600 s du TTL.
L'instance qui écrit, elle, purge immédiatement (elle appelle `clear_kpi_caches()`).

Non garanti : la cohérence à la seconde entre deux instances. Obtenir cela demanderait
une lecture par rendu, donc une requête de plus sur un chemin que
`tests/test_a_page_asks_the_same_question_once.py` tient à un plafond qui NE MONTE PAS.
Trente secondes d'écart contre une requête par rendu : le compromis est écrit ici pour
qu'on puisse le rouvrir avec un chiffre plutôt qu'une impression.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Fenêtre pendant laquelle une instance peut ignorer une invalidation venue d'ailleurs.
# 30 s : assez court pour qu'un artiste qui recharge ne voie pas d'ancien chiffre, assez
# long pour que la lecture soit négligeable (une requête par processus par demi-minute,
# pas une par rendu).
_EPOCH_TTL = int(os.getenv("DASHBOARD_CACHE_EPOCH_TTL", "30"))

# La dernière époque que CE processus a vue, par locataire. C'est bien un état de
# processus, et c'est correct ici : chaque instance a le sien et doit l'avoir.
_SEEN: dict[int, int] = {}


def bump(artist_id: int | None = None, db=None) -> None:
    """Signale que les compteurs de ce locataire sont devenus faux. Ne lève jamais.

    Une seule instruction, `cache_epoch = cache_epoch + 1` : deux écritures
    concurrentes sur le même locataire ne peuvent pas se perdre l'une l'autre, ce
    qu'un `SELECT` puis `UPDATE` ne garantirait pas.

    Les deux arguments sont facultatifs, et c'est ce qui rend ce correctif petit :
    sans `artist_id` le locataire se résout de la session, sans `db` la fonction ouvre
    et referme la sienne. Les trente appelants de `clear_kpi_caches()` n'ont donc rien
    à changer. Le coût — une connexion — est payé sur un CLIC, pas sur un rendu.

    Ne lève jamais parce que l'appelant est un clic : échouer ici transformerait une
    invalidation ratée — dont la conséquence est un chiffre périmé 30 s de plus — en
    page d'erreur.
    """
    try:
        if not artist_id:
            from src.dashboard.auth import get_artist_id
            artist_id = get_artist_id()
        if not artist_id:
            # Session admin sans locataire résolu : il n'y a pas d'époque à
            # incrémenter, et en choisir une au hasard ferait manquer son cache à un
            # artiste qui n'a rien demandé. On ne devine pas un locataire (règle du
            # dépôt sur l'identité).
            return
        owned = db is None
        if owned:
            from src.dashboard.utils import get_db_connection
            db = get_db_connection()
        if db is None:
            return
        try:
            db.execute_query(
                "UPDATE saas_artists SET cache_epoch = cache_epoch + 1 WHERE id = %s",
                (artist_id,))
        finally:
            if owned:
                db.close()
    except Exception as exc:  # noqa: BLE001 — voir la docstring
        logger.warning("époque de cache non incrémentée pour %s (%s)",
                       artist_id, type(exc).__name__)


def _read(db, artist_id: int):
    """L'époque du locataire, mémorisée `_EPOCH_TTL` secondes. None si illisible.

    ⚠️ `db` est FOURNI par l'appelant et n'est jamais ouvert ici. La première version
    appelait `get_db_connection()` et ouvrait donc une SECONDE connexion par rendu —
    ce que la règle transverse #9 interdit (« les vues ouvrent exactement une
    connexion via `view_session()` ») et que
    `tests/test_a_render_opens_one_connection.py` a signalé sur quatre vues. Le
    préfixe `_` le sort du hachage de `st.cache_data`, comme dans `kpi_helpers`.
    """
    import streamlit as st

    @st.cache_data(ttl=_EPOCH_TTL, show_spinner=False)
    def _cached(_db, aid: int):
        if _db is None:
            return None
        rows = _db.fetch_query(
            "SELECT cache_epoch FROM saas_artists WHERE id = %s", (aid,))
        return int(rows[0][0]) if rows and rows[0][0] is not None else None

    return _cached(db, artist_id)


def honour_remote_invalidation(artist_id: int, db=None) -> bool:
    """Purge les caches de CE processus si une autre instance a écrit. Ne lève jamais.

    Rend True quand une purge a eu lieu — le booléen sert aux tests, pas à l'appelant.

    `db` est la connexion DÉJÀ ouverte par le rendu : cette fonction n'en ouvre
    jamais une seconde (règle transverse #9).

    La première observation n'est PAS une purge : un processus qui vient de démarrer
    n'a rien en cache, et purger à l'amorçage ferait payer une purge inutile à chaque
    rendu de chaque worker au démarrage.
    """
    try:
        epoch = _read(db, artist_id)
        if epoch is None:
            return False
        previous = _SEEN.get(artist_id)
        _SEEN[artist_id] = epoch
        if previous is None or previous == epoch:
            return False

        from src.dashboard.utils.kpi_helpers import clear_kpi_caches
        clear_kpi_caches()
        logger.info("caches purgés : époque du locataire %s passée de %s à %s "
                    "(écriture faite par une autre instance)", artist_id, previous, epoch)
        return True
    except Exception as exc:  # noqa: BLE001 — un rendu ne tombe pas sur une purge
        logger.warning("invalidation distante ignorée (%s)", type(exc).__name__)
        return False
