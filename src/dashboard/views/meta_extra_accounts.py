"""Les comptes publicitaires supplémentaires — sur la page Meta Ads, pas ailleurs.

Type: Sub
Uses: PostgresHandler, tenant_identity.with_meta_accounts
Triggers: views/meta_ads_overview.py
Depends on: artist_credentials['meta'].extra_config['account_ids']
Persists in: artist_credentials

Le champ vivait dans l'onglet Credentials, replié, sous les deux champs qui servent à
tout le monde. Déplacé le 2026-09-05 : « ça ne doit pas être dans l'onglet credential,
pour plus de simplicité et de navigation ».

C'est le même mouvement que « Mes titres hébergés sur d'autres comptes », parti sur
☁️ SoundCloud — Performance le 2026-09-04, et pour la même raison : **Credentials
répond à « comment te connecter », pas à « que veux-tu suivre »**. Un compte
publicitaire d'agence n'est pas une identité de connexion — l'identité est déjà là —
c'est une déclaration de périmètre, qu'on fait en regardant ses chiffres et en
constatant qu'une campagne manque.

Le compte PRINCIPAL n'est pas éditable ici : il reste dans Credentials, parce que lui
est bien l'identité, et parce que le vider casserait la collecte.
"""
from __future__ import annotations

import json

import streamlit as st

from src.dashboard.utils.i18n import t
from src.utils.tenant_identity import (
    META_ACCOUNTS_FIELD,
    malformed_meta_accounts,
    with_meta_accounts,
)


def _read(db, artist_id: int) -> tuple:
    """`(principal, supplémentaires)` — ne lève jamais."""
    try:
        rows = db.fetch_query(
            "SELECT extra_config FROM artist_credentials "
            "WHERE artist_id = %s AND platform = 'meta'", (artist_id,))
    except Exception:  # noqa: BLE001
        return "", []
    if not rows or not rows[0][0]:
        return "", []
    extra = rows[0][0]
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except ValueError:
            return "", []
    accounts = list(extra.get(META_ACCOUNTS_FIELD) or [])
    main = accounts[0] if accounts else (extra.get("account_id") or "")
    return main, accounts[1:]


def render_extra_ad_accounts(db, artist_id: int) -> None:
    """Le bloc, replié, en bas de la page Meta Ads. Ne lève jamais.

    Replié : il ne concerne que les agences. Ce n'est pas la même décision que dans
    Credentials — là-bas il était replié ET sur le chemin obligatoire de tout le
    monde ; ici il est replié sur une page qu'on ouvre pour regarder ses campagnes.
    """
    main, extras = _read(db, artist_id)
    if not main:
        return                      # pas de compte Meta déclaré : rien à compléter

    with st.expander(t("meta.extra_accounts_title",
                       "➕ Comptes ads supplémentaires - pour agence (optionnel)")):
        st.caption(t(
            "meta.extra_accounts_help",
            "Compte principal : **{main}** — il se change dans 🔑 Credentials API. "
            "Ajoute ici les autres comptes à suivre, **un par ligne**."
        ).format(main=main))
        typed = st.text_area(
            t("meta.extra_accounts_field", "Comptes supplémentaires"),
            value="\n".join(extras), height=90, label_visibility="collapsed",
            key=f"_meta_extra_{artist_id}")
        if not st.button(t("meta.extra_accounts_save", "💾 Enregistrer ces comptes"),
                         key=f"_meta_extra_save_{artist_id}"):
            return

        wanted = [main, *[line for line in (typed or "").splitlines()]]
        merged = with_meta_accounts({"account_id": main}, wanted)
        bad = malformed_meta_accounts(merged)
        if bad:
            st.error(t(
                "meta.extra_accounts_malformed",
                "❌ Compte(s) au mauvais format : {bad}. Chiffres uniquement, "
                "éventuellement préfixés par `act_`, un par ligne."
            ).format(bad=", ".join(bad)))
            return
        try:
            # Fusion JSONB : on ne réécrit QUE les deux clés de comptes. Un `SET
            # extra_config = %s` effacerait `ig_user_id`, qui vit dans la même ligne.
            db.execute_query(
                "UPDATE artist_credentials SET extra_config = extra_config || %s "
                "WHERE artist_id = %s AND platform = 'meta'",
                (json.dumps({META_ACCOUNTS_FIELD: merged[META_ACCOUNTS_FIELD],
                             "account_id": merged["account_id"]}), artist_id))
        except Exception:  # noqa: BLE001 — un échec d'écriture n'est pas une page morte
            st.error(t("meta.extra_accounts_failed",
                       "Enregistrement impossible — réessaie dans un instant."))
            return
        st.success(t("meta.extra_accounts_saved",
                     "✅ {n} compte(s) suivi(s).").format(
                         n=len(merged[META_ACCOUNTS_FIELD])))
        st.rerun()
