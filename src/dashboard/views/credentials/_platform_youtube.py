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
        if not channel_id:
            # Key-only green is the same lie as Meta's /me: the admin key is shared by
            # every tenant. Without the artist's own channel there is nothing to collect.
            return False, t("credentials.youtube.channel_missing",
                            "Clé API valide, mais ton **Channel ID** n'est pas renseigné — "
                            "sans lui aucune vidéo ne peut être collectée. Il se lit dans "
                            "YouTube Studio → Paramètres → Chaîne → Paramètres avancés "
                            "(commence par `UC…`).")
        rc = requests.get(
            'https://www.googleapis.com/youtube/v3/channels',
            params={'part': 'contentDetails,statistics', 'id': channel_id, 'key': api_key},
            timeout=10,
            allow_redirects=False,
        )
        cd = rc.json()
        items = cd.get('items') or []
        if not (rc.status_code == 200 and items):
            return False, t("credentials.youtube.channel_not_found",
                            "Channel ID introuvable : « {cid} ». Vérifier qu'il commence "
                            "par UC… (Paramètres avancés de la chaîne).").format(cid=channel_id)
        # An empty channel resolves fine and then collects 0 videos forever — the Benken
        # case. Say so at connect time instead of leaving an eternally empty view.
        video_count = int((items[0].get('statistics') or {}).get('videoCount') or 0)
        if video_count == 0:
            return False, t(
                "credentials.youtube.channel_empty",
                "Chaîne « {cid} » trouvée, mais elle ne contient **aucune vidéo** — il n'y "
                "aura rien à collecter. Si ta musique est distribuée, c'est souvent la "
                "chaîne **« … - Topic »** générée automatiquement qu'il faut renseigner, "
                "pas ta chaîne personnelle."
            ).format(cid=channel_id)
        return True, t("credentials.youtube.test_ok_channel",
                       "Clé API valide — chaîne trouvée, {n} vidéo(s) ✅").format(n=video_count)
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
