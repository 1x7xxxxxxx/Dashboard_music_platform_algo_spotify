"""Meta multi-comptes — le sélecteur de compte publicitaire, une seule fois.

Type: Utility
Uses: streamlit, PostgresHandler (via l'appelant), src.utils.tenant_identity
Triggers: les 5 vues Meta + l'export PDF
Persists in: rien — pure lecture

Pourquoi ce module (R53 / ADR-013, 2026-08-24).

Un artiste passant par une agence a N comptes publicitaires, et la décision produit
est qu'ils sont **séparés** : chacun a son budget, son CPR, ses campagnes, et un
total cumulé ne veut rien dire. Deux comptes peuvent parfaitement avoir une campagne
« Release FR » — c'est même le cas nominal — donc filtrer sur le seul nom de campagne
additionnerait les deux sans le dire. Le filtre est un **prédicat SQL**, jamais une
restriction de la liste de campagnes.

Deux propriétés que le sélecteur doit tenir, et qui expliquent sa forme :

  * **Il ne s'affiche pas en dessous de deux comptes.** Toute la flotte est
    mono-compte aujourd'hui ; un sélecteur à une seule option est du bruit sur
    cinq pages, et un artiste qui ne comprend pas un widget suppose qu'il lui manque
    quelque chose. `account_scope` rend alors `("", ())` — la requête est
    littéralement celle d'avant.
  * **Le prédicat est `= %s`, pas `IS NOT DISTINCT FROM %s`.** Choisir un compte
    veut dire « ce compte » ; les lignes historiques restées à NULL (locataire sans
    credentials au moment de la migration 077) n'appartiennent à aucun compte
    nommé et ne doivent pas apparaître sous celui qu'on a choisi. Elles restent
    visibles sous « Tous les comptes », qui n'ajoute aucun prédicat.
"""
from __future__ import annotations

import streamlit as st

from src.dashboard.utils.i18n import t

# Tables Meta portant la colonne `ad_account_id` (migrations 076/077). Dérivée du
# collecteur : une seconde liste tapée ici divergerait de la première le jour où une
# table est ajoutée, et la divergence se lirait comme « colonne inconnue » en pleine
# page — ou pire, comme un filtre qui ne filtre rien.
from src.collectors._meta_constants import _ACCOUNT_STAMPED_TABLES

ALL_ACCOUNTS = "__all__"


def table_carries_account(table: str) -> bool:
    """La table porte-t-elle `ad_account_id` ? Sinon aucun filtre n'est applicable."""
    return table in _ACCOUNT_STAMPED_TABLES


def tenant_ad_accounts(db, artist_id: int) -> list[str]:
    """Les comptes publicitaires de ce locataire, déclarés ou présents en données.

    L'union des deux est délibérée : un compte déclaré mais jamais collecté doit
    apparaître (sinon l'artiste ne comprend pas pourquoi son deuxième compte est
    invisible), et un compte présent en données mais retiré des credentials aussi
    (sinon son historique devient inatteignable).
    """
    from src.utils.tenant_identity import meta_ad_account_ids

    declared: list[str] = []
    try:
        rows = db.fetch_query(
            "SELECT extra_config FROM artist_credentials "
            "WHERE artist_id = %s AND platform = 'meta'",
            (artist_id,),
        )
        if rows:
            raw = rows[0][0] if isinstance(rows[0], (tuple, list)) else rows[0]['extra_config']
            declared = meta_ad_account_ids(raw or {})
    except Exception:
        # Lecture facultative : l'absence de credentials n'est pas une panne de page.
        declared = []

    seen = list(declared)
    try:
        rows = db.fetch_query(
            "SELECT DISTINCT ad_account_id FROM meta_campaigns "
            "WHERE artist_id = %s AND ad_account_id IS NOT NULL ORDER BY 1",
            (artist_id,),
        )
        for r in rows or []:
            value = r[0] if isinstance(r, (tuple, list)) else r['ad_account_id']
            if value and value not in seen:
                seen.append(value)
    except Exception:
        pass
    return seen


def account_scope(db, artist_id: int, *, key: str) -> str | None:
    """Rend le sélecteur (si ≥2 comptes) et renvoie le compte choisi, ou `None`.

    `None` veut dire « pas de filtre » — soit parce que le locataire n'a qu'un
    compte et que le widget n'est pas rendu, soit parce qu'il a explicitement
    demandé le cumul. Les deux cas produisent la requête d'avant, à l'identique.
    """
    accounts = tenant_ad_accounts(db, artist_id)
    if len(accounts) < 2:
        return None

    chosen = st.selectbox(
        t("meta.account_filter", "🏦 Compte publicitaire"),
        options=[ALL_ACCOUNTS, *accounts],
        format_func=lambda a: (t("meta.account_all", "Tous les comptes (cumulé)")
                               if a == ALL_ACCOUNTS else a),
        # Index 1 : le PREMIER COMPTE, pas le cumul. La décision produit est
        # « séparés » — ouvrir sur un total qui mélange les budgets de deux
        # annonceurs est exactement ce qu'elle refuse.
        index=1,
        key=key,
    )
    return None if chosen == ALL_ACCOUNTS else chosen


def account_clause(account: str | None, alias: str = "") -> tuple[str, tuple]:
    """`(fragment_sql, params)` à coller juste après `WHERE artist_id = %s`.

    Le fragment prend la même place que le filtre de campagnes existant, donc ses
    paramètres se placent juste après `artist_id` : l'ordre des `%s` est l'ordre du
    tuple, et c'est la seule règle à retenir au moment de l'appel.

    `alias` porte le préfixe de table (`"p."`) pour les requêtes jointes, où un
    `ad_account_id` nu serait ambigu — Postgres refuse la requête, ce qui est le bon
    échec : bruyant, immédiat, jamais un filtre qui ne filtre rien.

    Le prédicat est `= %s`, pas `IS NOT DISTINCT FROM %s` : choisir un compte veut
    dire « ce compte », et les lignes historiques restées à NULL (locataire sans
    credentials au moment de la migration 077) n'appartiennent à aucun compte nommé.
    Elles restent visibles sous « Tous les comptes », qui n'ajoute aucun prédicat.
    """
    if not account:
        return "", ()
    return f" AND {alias}ad_account_id = %s", (account,)
