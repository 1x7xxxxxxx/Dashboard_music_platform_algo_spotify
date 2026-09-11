"""Le cache des lectures de séries — côté Streamlit, et seulement là.

Type: Utility
Uses: streamlit, platform_timeseries
Triggers: installé par `get_db_connection()` au premier besoin du processus
Persists in: nothing

Pourquoi il vit ICI et pas dans `platform_timeseries`
-----------------------------------------------------
`platform_timeseries` est délibérément SANS Streamlit : l'export PDF headless
(`pdf_exporter/_report.py`) et les tests l'appellent. Un décorateur y casserait
ces deux chemins.

Pourquoi il enveloppe la REQUÊTE et pas la fonction
---------------------------------------------------
C'est le point critique qui a fait refuser la première conception, le
2026-09-11. Les fonctions publiques de `platform_timeseries` sont écrites pour
**ne jamais lever** : sur une panne de base elles rendent vide, indiscernable de
« rien à lire ». Les mettre en cache mettrait la PANNE en cache — une coupure
d'une seconde deviendrait « aucune donnée » pendant 600 s, pour tous les
spectateurs à la fois, et sur la classe de défaut que ce dépôt paie le plus
cher : une lecture ratée déguisée en absence.

Le crochet `platform_timeseries.set_fetch()` place ce cache **à l'intérieur** de
l'avalement. Si la lecture lève, `st.cache_data` ne mémorise rien, le `except`
du module dégrade comme avant, et le rendu suivant réessaie.

Isolation entre locataires
--------------------------
La clé est `(sql, params)`, et `params` porte **toujours** `artist_id` — toutes
les requêtes du module sont scopées. L'isolation est donc structurelle : elle ne
dépend pas de se souvenir d'ajouter le locataire à une clé, ce qui est la façon
dont ce genre de cache fuit.

Le poignet de la base est passé en `_db` : le tiret bas dit à Streamlit de
l'exclure du hachage (il n'est pas hachable, et deux connexions différentes vers
la même base doivent partager la même entrée).

Durée et invalidation
---------------------
600 s, comme `kpi_helpers`, et pour la même raison : les tables sont écrites une
fois par nuit par les DAGs. Les moments où elles changent en pleine journée sont
connus, et `clear_kpi_caches()` les couvre déjà — `clear()` s'y greffe, de sorte
qu'un dépôt de CSV, un import admin, une saisie de revenu ou un déclenchement de
collecte vident les deux caches ensemble. « On ne fait pas confiance à
l'horloge, on écoute l'événement. »
"""
from __future__ import annotations

import logging

import streamlit as st

logger = logging.getLogger(__name__)

_TTL_SECONDS = 600


@st.cache_data(ttl=_TTL_SECONDS, show_spinner=False)
def _cached_rows(sql: str, params: tuple, _db):
    """Une lecture mémorisée. LÈVE sur échec — c'est ce qui évite de cacher une panne."""
    return _db.fetch_query(sql, params)


def _fetch(db, sql: str, params):
    """Ce que `platform_timeseries` appellera à la place de `db.fetch_query`.

    `params` est ramené à un tuple : `st.cache_data` hache ses arguments, et une
    liste ne l'est pas. Deux sites du module passent déjà `tuple(params)`, deux
    autres un tuple littéral — la coercition ici évite que le troisième venu
    fasse tomber la page sur un `UnhashableParamError` au lieu de lire.
    """
    return _cached_rows(sql, tuple(params or ()), _db=db)


def install() -> None:
    """Branche le cache sur le module de séries. Idempotent."""
    from src.dashboard.utils import platform_timeseries as pt
    if pt._FETCH is _fetch:
        return
    pt.set_fetch(_fetch)


def clear() -> None:
    """Vide le cache. Appelé par `kpi_helpers.clear_kpi_caches()`."""
    try:
        _cached_rows.clear()
    except Exception:      # noqa: BLE001 — une purge ratée ne casse pas l'appelant
        logger.warning("purge du cache de séries impossible")
