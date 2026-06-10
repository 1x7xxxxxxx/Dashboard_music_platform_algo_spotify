"""Credentials — YouTube connection test + setup guide.

Type: Sub
Uses: requests, streamlit
Pure relocation from the former credentials.py — no logic change.
"""
import requests
import streamlit as st

from src.dashboard.utils.i18n import t


def _test_youtube(fields: dict) -> tuple:
    # Validate the Data-API key the collector actually uses (developerKey),
    # via a key-only endpoint (no channel needed). i18nLanguages is the
    # cheapest read that exercises the key.
    api_key = fields.get('api_key', '')
    if not api_key:
        return False, t("credentials.youtube.test_key_required",
                        "API Key requise pour tester YouTube.")
    try:
        r = requests.get(
            'https://www.googleapis.com/youtube/v3/i18nLanguages',
            params={'part': 'snippet', 'key': api_key},
            timeout=10,
            allow_redirects=False,  # INFO-04
        )
        data = r.json()
        if r.status_code == 200 and data.get('items'):
            return True, t("credentials.youtube.test_ok", "Clé API valide ✅")
        err = data.get('error', {})
        return False, err.get('message', r.text[:150]) if isinstance(err, dict) else str(err)
    except Exception as e:
        return False, str(e)


def _guide_youtube():
    with st.expander(t("credentials.youtube.guide_title",
                       "🎬 Comment obtenir les credentials YouTube ?"), expanded=False):
        st.markdown(t(
            "credentials.youtube.guide_steps",
            "1. **[console.cloud.google.com](https://console.cloud.google.com)** → créer/choisir un projet\n"
            "2. **APIs & Services → Bibliothèque** → activer **YouTube Data API v3**\n"
            "3. **APIs & Services → Identifiants → Créer des identifiants → Clé API**\n"
            "4. (recommandé) Restreindre la clé à **YouTube Data API v3**\n"
            "5. Coller la clé dans **API Key** ci-dessous\n"
            "6. **Channel ID** : sur la chaîne YouTube → *Paramètres avancés* "
            "→ ID de chaîne (commence par `UC…`)\n"
        ))
        st.info(t("credentials.youtube.guide_info",
                  "Le collecteur utilise une **clé API statique** (pas d'OAuth) : "
                  "la clé n'expire pas, aucun refresh à gérer."))
