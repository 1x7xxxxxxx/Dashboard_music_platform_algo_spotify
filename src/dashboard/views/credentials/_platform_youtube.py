"""Credentials — YouTube connection test + setup guide.

Type: Sub
Uses: requests, streamlit
Pure relocation from the former credentials.py — no logic change.
"""
import os

import requests
import streamlit as st

from src.dashboard.utils.i18n import t
from src.dashboard.utils.youtube_channel import (
    lookup_params, parse_channel_input,
)


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
        # Nobody knows their UC… id. What an artist has to hand is the address bar
        # or the handle under their name, and pasting either used to dead-end on
        # "Channel ID introuvable" at the very last step of the setup. Classify
        # first, and when the input is resolvable, resolve it and REPORT the id —
        # never substitute it silently: a tenant's identity is not inferred here.
        parsed = parse_channel_input(channel_id)

        if parsed.kind == "malformed":
            return False, t(
                "credentials.youtube.channel_malformed",
                "« {cid} » commence bien par `UC` mais n'a pas la bonne longueur — "
                "un identifiant de chaîne fait exactement 24 caractères. C'est "
                "presque toujours un copier-coller tronqué : recopie-le en entier "
                "depuis YouTube Studio → Paramètres → Chaîne → Paramètres avancés."
            ).format(cid=channel_id)

        if parsed.kind == "name":
            return False, t(
                "credentials.youtube.channel_vanity_url",
                "« {cid} » est une adresse personnalisée (`/c/…`) : YouTube ne "
                "permet pas de retrouver l'identifiant à partir d'elle. Lis-le "
                "directement dans YouTube Studio → Paramètres → Chaîne → "
                "Paramètres avancés (il commence par `UC…`)."
            ).format(cid=parsed.value)

        params = lookup_params(parsed)
        if params is not None:
            lr = requests.get(
                'https://www.googleapis.com/youtube/v3/channels',
                params={'part': 'id', 'key': api_key, **params},
                timeout=10,
                allow_redirects=False,
            )
            found = (lr.json().get('items') or []) if lr.status_code == 200 else []
            if not found:
                return False, t(
                    "credentials.youtube.handle_not_found",
                    "Aucune chaîne ne correspond à « {cid} ». Vérifie l'orthographe, "
                    "ou lis l'identifiant dans YouTube Studio → Paramètres → Chaîne "
                    "→ Paramètres avancés (il commence par `UC…`)."
                ).format(cid=parsed.value)
            resolved = found[0].get('id', '')
            return False, t(
                "credentials.youtube.handle_resolved",
                "« {given} » correspond à la chaîne **`{cid}`**. Colle cette valeur "
                "dans le champ Channel ID, puis relance le test."
            ).format(given=parsed.value, cid=resolved)

        if not parsed.is_usable:
            return False, t(
                "credentials.youtube.channel_unrecognised",
                "« {cid} » n'est ni un identifiant `UC…`, ni un pseudo `@…`, ni une "
                "adresse de chaîne YouTube. Colle l'identifiant lu dans YouTube "
                "Studio → Paramètres → Chaîne → Paramètres avancés, ou ton pseudo "
                "`@…` — on le convertira pour toi."
            ).format(cid=channel_id)

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
        # NEVER str(e). This probe passes the shared credential as a QUERY
        # PARAMETER, so a ConnectionError's message embeds the full prepared URL —
        # credential included — and _render.py renders it to the tenant with
        # st.error. A DNS blip was enough to show a non-admin the platform-wide
        # token (Meta, never expires) or the billable API key (YouTube).
        return False, t("credentials.probe_network_error",
                        "Erreur réseau ({err}) — réessaie dans un instant. Si ça "
                        "persiste, contacte l'administrateur.").format(
                            err=type(e).__name__)


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
