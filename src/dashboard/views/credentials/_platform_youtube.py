"""Credentials — YouTube connection test + setup guide.

Type: Sub
Uses: requests, streamlit
Pure relocation from the former credentials.py — no logic change.
"""
import os

import requests

from src.dashboard.utils.i18n import t
from src.dashboard.utils.youtube_channel import (
    lookup_params,
    parse_channel_input,
    pick_topic_channel,
    topic_channel_query,
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
                "Chaîne « {cid} » trouvée, mais elle ne contient **aucune vidéo**. "
                "C'est presque toujours le signe que ce n'est pas la bonne chaîne : "
                "un pseudo peut appartenir à quelqu'un d'autre. Recopie l'identifiant "
                "lu sur youtube.com/account_advanced, en étant connecté à ton compte."
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


def discover_topic_channel(channel_id: str, api_key: str) -> tuple[str, str] | None:
    """La chaîne « … - Topic » de cet artiste, trouvée à partir de la principale.

    Demandé le 2026-09-05 : « je ne vois pas d'ID de chaîne normal et d'ID de chaîne
    Topic, comment on gère ça ? ». La réponse mesurée : ce sont DEUX chaînes, elles
    portent des données différentes (FJAAK : 53 vidéos / 11 M vues sur la principale,
    172 vidéos / 880 k vues sur la Topic), et `youtube.com/account_advanced` — le
    seul écran où un artiste lit un identifiant — ne montre QUE la principale. La
    Topic est auto-générée par YouTube et n'appartient pas à son compte Google. Lui
    demander de la coller était donc impossible ; c'est l'app qui la trouve.

    Deux appels : le titre de la chaîne principale, puis une recherche sur
    « <titre> - Topic ». `pick_topic_channel` n'accepte qu'une ÉGALITÉ de titre —
    une recherche par nom a déjà été mesurée non fiable ici (la bonne chaîne de
    Benken n'était pas dans les cinq premiers résultats).

    Ne lève jamais : ne pas trouver la Topic n'empêche pas d'enregistrer la
    principale. Renvoie `None` plutôt qu'un « à peu près ».
    """
    if not (channel_id or "").startswith("UC") or not api_key:
        return None
    try:
        rc = requests.get(
            'https://www.googleapis.com/youtube/v3/channels',
            params={'part': 'snippet', 'id': channel_id, 'key': api_key},
            timeout=10, allow_redirects=False)
        items = (rc.json().get('items') or []) if rc.status_code == 200 else []
        title = ((items[0].get('snippet') or {}).get('title') if items else None)
        query = topic_channel_query(title)
        if not query:
            return None
        rs = requests.get(
            'https://www.googleapis.com/youtube/v3/search',
            params={'part': 'snippet', 'q': query, 'type': 'channel',
                    'maxResults': 10, 'key': api_key},
            timeout=10, allow_redirects=False)
        found = (rs.json().get('items') or []) if rs.status_code == 200 else []
        candidates = [((i.get('snippet') or {}).get('title'),
                       (i.get('snippet') or {}).get('channelId')) for i in found]
        picked = pick_topic_channel(title, candidates)
        # La Topic d'un artiste ne peut pas être sa chaîne principale.
        if picked and picked[0] == channel_id:
            return None
        return picked
    except Exception:  # noqa: BLE001 — une découverte ratée n'est pas un échec de saisie
        return None


def resolve_channel_id(given: str, api_key: str):
    """Un lien de chaîne ou un `@pseudo` → `(identifiant, description, problème)`.

    Ne lève jamais ; au plus un des trois est non nul en cas d'échec. Le problème est
    une phrase CONSTRUITE, jamais un `str(exc)` — la clé API voyage dans la chaîne de
    requête, donc le message d'une `ConnectionError` la contiendrait.

    Pourquoi résoudre ici : jusqu'au 2026-09-05, coller l'adresse de sa chaîne
    enregistrait l'ADRESSE dans `channel_id`. Le test de connexion trouvait bien
    l'identifiant — pour l'afficher et demander à l'artiste de le recopier à la main,
    puis de relancer le test. Trois gestes pour une valeur que nous avions déjà.

    Pourquoi RENDRE une description, et ne pas se contenter de l'identifiant : un
    pseudo n'est pas une identité. Mesuré le jour même — `@fjaak` est une chaîne
    **vide** (0 vidéo) qui n'est pas celle de l'artiste FJAAK, dont le vrai pseudo
    est `@fjaakberlin`. Résoudre en silence aurait branché un locataire sur la chaîne
    de quelqu'un d'autre, ce qui est la classe que ce dépôt a passé deux séances à
    retirer. La description (titre + nombre de vidéos) est ce qui permet à l'artiste
    de voir immédiatement que ce n'est pas la sienne.

    Une adresse personnalisée `/c/…` reste irrésolvable — YouTube ne l'expose par
    aucune arête — et c'est dit plutôt que deviné.
    """
    value = (given or "").strip()
    if not value:
        return None, None, None
    parsed = parse_channel_input(value)
    if parsed.kind == "name":
        return None, None, t(
            "credentials.youtube.channel_vanity_url",
            "« {cid} » est une adresse personnalisée (`/c/…`) : YouTube ne "
            "permet pas de retrouver l'identifiant à partir d'elle. Lis-le "
            "directement dans YouTube Studio → Paramètres → Chaîne → "
            "Paramètres avancés (il commence par `UC…`)."
        ).format(cid=parsed.value)

    direct = parsed.value if (parsed.kind == "id" and parsed.is_usable) else None
    params = None if direct else lookup_params(parsed)
    if not api_key or (direct is None and params is None):
        return direct, None, None

    try:
        query = {'part': 'snippet,statistics', 'key': api_key}
        query.update({'id': direct} if direct else params)
        r = requests.get('https://www.googleapis.com/youtube/v3/channels',
                         params=query, timeout=10, allow_redirects=False)
        found = (r.json().get('items') or []) if r.status_code == 200 else []
        if not found:
            if direct:
                return direct, None, None
            return None, None, t(
                "credentials.youtube.handle_not_found",
                "Aucune chaîne ne correspond à « {cid} ». Vérifie l'orthographe, "
                "ou lis l'identifiant dans YouTube Studio → Paramètres → Chaîne "
                "→ Paramètres avancés (il commence par `UC…`)."
            ).format(cid=parsed.value)
        item = found[0]
        title = (item.get('snippet') or {}).get('title') or ''
        videos = int((item.get('statistics') or {}).get('videoCount') or 0)
        return (item.get('id') or direct), f"{title} — {videos} vidéo(s)", None
    except Exception as exc:  # noqa: BLE001 — jamais str(exc) : la clé est dans l'URL
        if direct:
            return direct, None, None
        return None, None, t(
            "credentials.probe_network_error",
            "Erreur réseau ({err}) — réessaie dans un instant. Si ça persiste, "
            "contacte l'administrateur."
        ).format(err=type(exc).__name__)
