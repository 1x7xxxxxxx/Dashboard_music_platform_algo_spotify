"""Credentials — YouTube connection test + setup guide.

Type: Sub
Uses: requests, streamlit
Pure relocation from the former credentials.py — no logic change.
"""
import os

import requests

from src.dashboard.utils.i18n import t
from src.dashboard.utils.youtube_channel import (
    lookup_params, parse_channel_input,
)
from src.utils.platform_probes import (  # la situation que cette sonde nomme
    IDENTITY_MISSING,
    NOTHING_TO_COLLECT,
    NOT_FOUND,
    RESOLVED,
    UNREACHABLE,
    tagged,
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
            err = data.get('error', {}) if isinstance(data.get('error'), dict) else {}
            reason = ""
            for d in (err.get('errors') or []):
                reason = d.get('reason', "") or reason
            # Google rend « API key not valid. Please pass a valid API key. » — exact,
            # et inutile pour l'artiste : la clé YouTube est celle de l'ADMIN (ADR-006),
            # partagée par toute la flotte. Lui afficher le message tel quel l'envoie
            # chercher une clé qu'il n'a pas et ne doit pas avoir. Un message d'erreur
            # qui ne fait que constater n'aide pas (Cooper, *About Face*, p.675) : on
            # nomme QUI doit agir.
            if reason in ("badRequest", "keyInvalid") or "API key not valid" in str(
                    err.get('message', "")):
                return False, t(
                    "credentials.youtube.admin_key_invalid",
                    "La clé API YouTube **de la plateforme** est refusée par Google. "
                    "Ce n'est pas ta clé et tu n'as rien à corriger : préviens "
                    "l'administrateur. Ton Channel ID, lui, peut rester saisi.")
            if reason in ("quotaExceeded", "dailyLimitExceeded"):
                return False, t(
                    "credentials.youtube.quota_exceeded",
                    "Le quota YouTube de la plateforme est épuisé pour aujourd'hui. "
                    "Rien à corriger de ton côté — réessaie demain, la collecte "
                    "nocturne reprendra d'elle-même.")
            # Reste : un message de Google qu'on n'a pas su traduire. On le rend, mais
            # borné, et jamais le corps brut de la réponse.
            msg = str(err.get('message', "")).strip()
            return False, t(
                "credentials.youtube.unexpected",
                "YouTube a refusé la requête ({code}). {msg} Si ça persiste, préviens "
                "l'administrateur.").format(code=r.status_code, msg=msg[:120])

        # Key is valid — now validate the Channel ID actually resolves. A wrong/empty
        # channel passes the key test but 404s the collector (uploads playlist UC→UU
        # "playlistNotFound") — exactly Benken's failure. Catch it here, in the form.
        channel_id = fields.get('channel_id', '').strip()
        if not channel_id:
            # Key-only green is the same lie as Meta's /me: the admin key is shared by
            # every tenant. Without the artist's own channel there is nothing to collect.
            return False, tagged(t("credentials.youtube.channel_missing",
                            "Clé API valide, mais ton **Channel ID** n'est pas renseigné — "
                            "sans lui aucune vidéo ne peut être collectée. Il se lit dans "
                            "YouTube Studio → Paramètres → Chaîne → Paramètres avancés "
                            "(commence par `UC…`)."), IDENTITY_MISSING)
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
            return False, tagged(t(
                "credentials.youtube.handle_resolved",
                "« {given} » correspond à la chaîne **`{cid}`**. Colle cette valeur "
                "dans le champ Channel ID, puis relance le test."
            ).format(given=parsed.value, cid=resolved), RESOLVED)

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
            return False, tagged(t("credentials.youtube.channel_not_found",
                            "Channel ID introuvable : « {cid} ». Vérifier qu'il commence "
                            "par UC… (Paramètres avancés de la chaîne).").format(cid=channel_id), NOT_FOUND)
        # An empty channel resolves fine and then collects 0 videos forever — the Benken
        # case. Say so at connect time instead of leaving an eternally empty view.
        video_count = int((items[0].get('statistics') or {}).get('videoCount') or 0)
        if video_count == 0:
            return False, tagged(t(
                "credentials.youtube.channel_empty",
                "Chaîne « {cid} » trouvée, mais elle ne contient **aucune vidéo** — il n'y "
                "aura rien à collecter. Si ta musique est distribuée, c'est souvent la "
                "chaîne **« … - Topic »** générée automatiquement qu'il faut renseigner, "
                "pas ta chaîne personnelle."
            ).format(cid=channel_id), NOTHING_TO_COLLECT)
        return True, t("credentials.youtube.test_ok_channel",
                       "Clé API valide — chaîne trouvée, {n} vidéo(s) ✅").format(n=video_count)
    except Exception as e:
        # NEVER str(e). This probe passes the shared credential as a QUERY
        # PARAMETER, so a ConnectionError's message embeds the full prepared URL —
        # credential included — and _render.py renders it to the tenant with
        # st.error. A DNS blip was enough to show a non-admin the platform-wide
        # token (Meta, never expires) or the billable API key (YouTube).
        return False, tagged(t("credentials.probe_network_error",
                        "Erreur réseau ({err}) — réessaie dans un instant. Si ça "
                        "persiste, contacte l'administrateur.").format(
                            err=type(e).__name__), UNREACHABLE)
