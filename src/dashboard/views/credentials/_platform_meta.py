"""Credentials — Meta / Instagram connection test + setup guide.

Type: Sub
Uses: requests, streamlit, META_GRAPH_BASE_URL
Pure relocation from the former credentials.py — no logic change.
"""
import os

import requests
import streamlit as st

from src.utils.meta_config import META_GRAPH_BASE_URL
from src.dashboard.utils.i18n import t


def _test_meta(fields: dict) -> tuple:
    # Shared System User token comes from the platform env; the artist only
    # provides their account_id. A stored per-artist token (if any) wins.
    token = fields.get('access_token', '').strip() or os.getenv('META_ACCESS_TOKEN', '')
    if not token:
        return False, t("credentials.meta.test_not_configured",
                        "App Meta non configurée côté plateforme (META_ACCESS_TOKEN) — "
                        "contactez l'administrateur.")
    try:
        r = requests.get(
            f'{META_GRAPH_BASE_URL}/me',
            params={'access_token': token, 'fields': 'id,name'},
            timeout=10,
            allow_redirects=False,  # INFO-04
        )
        data = r.json()
        if r.status_code == 200 and data.get('id'):
            return True, t("credentials.meta.test_ok", "Connecté : {name} ✅").format(
                name=data.get('name', data['id']))
        msg = data.get('error', {})
        if isinstance(msg, dict):
            msg = msg.get('message', r.text[:150])
        return False, str(msg)
    except Exception as e:
        return False, str(e)


def _guide_meta():
    with st.expander(t("credentials.meta.guide_title",
                       "📱 Où trouver chaque champ Meta / Instagram ?"), expanded=False):
        st.info(t(
            "credentials.meta.guide_info",
            "Ce dashboard utilise un **System User token** — jamais de token personnel. "
            "Les tokens System User n'expirent pas (sauf révocation manuelle). "
            "Tous les artistes utilisent la même app Meta : **ETL_DASHBOARD_SPOTIFY** — "
            "ne crée pas ta propre app."
        ))

        st.markdown(t("credentials.meta.steps_header", "### Étapes — Meta Ads"))
        st.markdown(t(
            "credentials.meta.steps_body",
            "1. **Business Manager → Paramètres → Utilisateurs → Utilisateurs système** → "
            "Créer un utilisateur système (rôle Admin).\n"
            "2. Cliquer sur l'utilisateur → **Générer un nouveau token** → sélectionner "
            "**ETL_DASHBOARD_SPOTIFY** → cocher les scopes `ads_read` + `ads_management` → "
            "**Générer le token**. *(C'est le champ **Access Token**.)*\n"
            "3. **Paramètres → Comptes publicitaires** → relever l'ID numérique "
            "(ex : `123456789`). **Ne pas ajouter le préfixe `act_`** — le dashboard l'ajoute "
            "automatiquement. *(C'est le champ **Ad Account ID**.)*\n"
            "4. **Paramètres → Apps → ETL_DASHBOARD_SPOTIFY → Business Assets → "
            "Ajouter des assets → Compte publicitaire** → sélectionner ton compte → "
            "permission Annonceur. *(Obligatoire — sans ça l'API renvoie \"Object does not exist\".)*\n"
            "5. **App ID** et **App Secret** : contacte l'administrateur de la plateforme "
            "— ils sont pré-remplis par défaut."
        ))

        st.markdown(t("credentials.meta.ig_header", "### Étapes supplémentaires — Instagram"))
        st.markdown(t(
            "credentials.meta.ig_body",
            "Si tu veux les stats Instagram, utilise le **même token** mais génère-le avec "
            "les scopes additionnels : `instagram_basic` + `instagram_manage_insights` + `pages_show_list`.\n\n"
            "Le DAG `meta_token_refresh` (hebdo) ne tente **pas** de renouveler les System User tokens "
            "(ils n'expirent pas) — aucune action périodique requise."
        ))

        st.markdown(t("credentials.meta.ig_id_header",
                      "### Instagram Business Account ID (optionnel)"))
        st.code(
            "https://graph.facebook.com/v24.0/me/accounts?access_token=TON_TOKEN\n"
            "# → noter l'id de ta Page Facebook\n"
            "https://graph.facebook.com/v24.0/PAGE_ID?fields=instagram_business_account&access_token=TON_TOKEN\n"
            "# → instagram_business_account.id",
            language="text"
        )

        st.markdown(t(
            "credentials.meta.table",
            "| Champ | Source | Secret |\n"
            "|---|---|---|\n"
            "| **Access Token** | Business Manager → Utilisateurs système → Générer token | Oui |\n"
            "| **App Secret** | developers.facebook.com → ETL_DASHBOARD_SPOTIFY → Paramètres → Général | Oui |\n"
            "| **App ID** | Même page que App Secret | Non |\n"
            "| **Ad Account ID** | Business Manager → Comptes publicitaires (numérique uniquement, sans `act_`) | Non |\n"
            "| **Instagram Business Account ID** | Appel Graph API ci-dessus | Non |\n"
        ))

        st.warning(t(
            "credentials.meta.warning",
            "⚠️ **Erreurs fréquentes** : "
            "(1) Token personnel depuis Graph API Explorer → expire en 60 jours, utiliser System User. "
            "(2) Préfixe `act_` dans Ad Account ID → supprimer, le dashboard l'ajoute. "
            "(3) Scope `read_insights` uniquement → relancer avec `ads_read` + `ads_management`."
        ))
