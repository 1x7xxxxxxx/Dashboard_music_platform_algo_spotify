"""Credentials — YouTube connection test + setup guide.

Type: Sub
Uses: requests, streamlit
Pure relocation from the former credentials.py — no logic change.
"""
import os

import requests
import streamlit as st

from src.dashboard.utils.i18n import t


def _test_youtube(fields: dict) -> tuple:
    # Validate the Data-API key the collector actually uses (developerKey),
    # via a key-only endpoint (no channel needed). i18nLanguages is the
    # cheapest read that exercises the key. The key is admin-owned (one Google
    # Cloud key serves all artists): fall back to the app-level env when the
    # artist leaves it blank, mirroring the collector's DB-then-env precedence.
    api_key = fields.get('api_key', '').strip() or os.getenv('YOUTUBE_API_KEY', '')
    if not api_key:
        return False, t("credentials.youtube.app_not_configured",
                        "App YouTube non configurée côté plateforme "
                        "(YOUTUBE_API_KEY) — contactez l'administrateur.")
    try:
        r = requests.get(
            'https://www.googleapis.com/youtube/v3/i18nLanguages',
            params={'part': 'snippet', 'key': api_key},
            timeout=10,
            allow_redirects=False,  # INFO-04
        )
        data = r.json()
        if not (r.status_code == 200 and data.get('items')):
            err = data.get('error', {})
            return False, err.get('message', r.text[:150]) if isinstance(err, dict) else str(err)

        # Key is valid — now validate the Channel ID actually resolves. A wrong/empty
        # channel passes the key test but 404s the collector (uploads playlist UC→UU
        # "playlistNotFound") — exactly Benken's failure. Catch it here, in the form.
        channel_id = fields.get('channel_id', '').strip()
        if channel_id:
            rc = requests.get(
                'https://www.googleapis.com/youtube/v3/channels',
                params={'part': 'contentDetails', 'id': channel_id, 'key': api_key},
                timeout=10,
                allow_redirects=False,
            )
            cd = rc.json()
            if not (rc.status_code == 200 and cd.get('items')):
                return False, t("credentials.youtube.channel_not_found",
                                "Channel ID introuvable : « {cid} ». Vérifier qu'il commence "
                                "par UC… (Paramètres avancés de la chaîne).").format(cid=channel_id)
        return True, t("credentials.youtube.test_ok", "Clé API valide ✅")
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
