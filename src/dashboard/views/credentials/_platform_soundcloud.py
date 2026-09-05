"""Credentials — SoundCloud connection test + setup guide.

Type: Sub
Uses: requests, streamlit
Pure relocation from the former credentials.py — no logic change.
"""
import os

import requests

from src.dashboard.utils.i18n import t
from src.utils.platform_probes import (  # la situation que cette sonde nomme
    IDENTITY_MISSING,
    NOTHING_TO_COLLECT,
    NOT_FOUND,
    REFUSED,
    UNREACHABLE,
    tagged,
)


def _claimed_count(fields: dict) -> int:
    """How many tracks this tenant declared as hosted elsewhere. Never raises.

    Read through the probe's `fields` dict so the connection test stays a pure
    function of what it was handed — it is called from the form, from
    `tools/artist_preflight.py` and from the nightly monitor, and only the first has
    a Streamlit session to borrow a DB connection from.
    """
    try:
        artist_id = fields.get('_artist_id')
        if not artist_id:
            return 0
        from src.dashboard.utils import get_db_connection
        from src.utils.claimed_tracks import claimed_track_ids
        db = get_db_connection()
        if db is None:
            return 0
        try:
            return len(claimed_track_ids(db, int(artist_id), 'soundcloud'))
        finally:
            db.close()
    except Exception:  # noqa: BLE001 — an unreadable claim list is not a red profile
        return 0


def _test_soundcloud(fields: dict) -> tuple:
    """Test SoundCloud via OAuth 2.0 Client Credentials flow (official API)."""
    # The artist only provides user_id; app credentials come from the shared env
    # app (SOUNDCLOUD_CLIENT_ID/SECRET), with a per-artist stored override if any.
    user_id       = fields.get('user_id', '').strip()
    client_id     = fields.get('client_id', '').strip() or os.getenv('SOUNDCLOUD_CLIENT_ID', '')
    client_secret = fields.get('client_secret', '').strip() or os.getenv('SOUNDCLOUD_CLIENT_SECRET', '')

    if not user_id:
        return False, tagged(t("credentials.soundcloud.user_id_empty",
                        "Rien à tester : colle le **lien de ton profil SoundCloud** "
                        "(https://soundcloud.com/ton-nom) dans le champ ci-dessous — "
                        "on en déduit ton User ID."), IDENTITY_MISSING)

    # A profile URL is what an artist HAS; the numeric id is what the pipeline needs.
    # The CANONICAL conversion happens at write time, in `_render._save_credentials`,
    # so the column only ever holds digits. This branch is the tolerant read for rows
    # stored BEFORE 2026-09-03: saving never validated, so a URL could land in the
    # column and then fail here with SoundCloud's own opaque error. One rule, two
    # entry points — both call `soundcloud_user_id_from_url`, so they cannot drift.
    #
    # Substituting rather than reporting, unlike YouTube: `/resolve` on a profile URL
    # is not a NAME search, it is the platform dereferencing a link that already
    # identifies exactly one account. Nothing is inferred. YouTube's resolve-and-report
    # answers a different question ("which channel is called this?") and stays as it is.
    if not user_id.isdigit():
        from src.utils.platform_identity_resolver import (
            ResolutionError,
            soundcloud_user_id_from_url,
        )
        try:
            user_id, _permalink = soundcloud_user_id_from_url(user_id)
        except ResolutionError as exc:
            from ._render import resolve_message
            return False, resolve_message(exc.code)
    if not client_id or not client_secret:
        return False, t("credentials.soundcloud.app_not_configured",
                        "App SoundCloud non configurée côté plateforme "
                        "(SOUNDCLOUD_CLIENT_ID/SECRET) — contactez l'administrateur.")

    try:
        # Step 1: obtain token
        r = requests.post(
            'https://api.soundcloud.com/oauth2/token',
            data={
                'grant_type':    'client_credentials',
                'client_id':     client_id,
                'client_secret': client_secret,
            },
            timeout=10,
            allow_redirects=False,  # INFO-04
        )
        if r.status_code != 200:
            return False, f"OAuth token request failed: HTTP {r.status_code} — {r.json().get('error_description', r.text[:150])}"

        token = r.json().get('access_token')
        if not token:
            return False, tagged(t("credentials.soundcloud.token_missing",
                            "Token absent dans la réponse OAuth."), REFUSED)

        # Step 2: fetch tracks — LA MÊME PAGE QUE LE COLLECTEUR.
        #
        # `limit: 1` a fait dire à la sonde « aucun titre public » sur un profil qui
        # en a DIX-SEPT. Mesuré le 2026-09-05 sur `users/377065610` avec le jeton
        # d'application, `linked_partitioning=1` :
        #
        #     limit=1  → 0 titre      limit=5  → 4      limit=50 → 17
        #     limit=2  → 1 titre      limit=10 → 8
        #
        # SoundCloud filtre certains titres APRÈS avoir appliqué la limite : demander
        # une page de 1 rend une page vide dès que le premier élément est écarté.
        # Le collecteur, lui, demande `limit: 50` (`soundcloud_api_collector.py`) et
        # ramenait donc les titres pendant que la sonde jurait qu'il n'y en avait
        # aucun. Une sonde qui ne pose pas la question du collecteur ne prédit pas son
        # résultat : elle en invente un autre.
        r2 = requests.get(
            f'https://api.soundcloud.com/users/{user_id}/tracks',
            headers={'Authorization': f'OAuth {token}'},
            params={'limit': 50, 'linked_partitioning': 1},
            timeout=10,
            allow_redirects=False,  # INFO-04
        )
        if r2.status_code == 200:
            _body = r2.json()
            _page = _body.get('collection', []) if isinstance(_body, dict) else (_body or [])
            count = len(_page)
            # Une page vide AVEC une page suivante n'est pas un profil vide : c'est
            # une réponse dont on ne peut rien conclure. On ne l'annonce donc pas
            # comme « aucun titre public » — la phrase qui envoyait un artiste
            # déclarer des titres ailleurs alors que les siens étaient là.
            if count == 0 and isinstance(_body, dict) and _body.get('next_href'):
                return True, t(
                    "credentials.soundcloud.inconclusive_page",
                    "Profil joignable. La première page de titres est revenue vide "
                    "alors que la plateforme en annonce d'autres — la collecte de "
                    "cette nuit tranchera.")
            # A resolvable user_id with ZERO tracks is NOT a success: the collector will
            # upsert 0 rows, the DAG will exit SUCCESS and the view will stay empty —
            # the silent-success class (rule #6), reported from the Grinch session
            # ("SoundCloud correctement configuré mais aucune donnée"). Fail HERE, in
            # the form, where the artist can still act on it.
            if count == 0:
                # …unless the artist declared tracks hosted on someone else's profile.
                # That is the GRiNCH case: released by a label, so his own profile is
                # empty and always will be, and the collectable unit is the TRACK.
                # Telling him to fix his User ID would be telling him to fix the one
                # thing that is already right.
                claimed = _claimed_count(fields)
                if claimed:
                    return True, t(
                        "credentials.soundcloud.claimed_only",
                        "Profil sans titre public, mais **{n} titre(s) déclaré(s)** "
                        "hébergé(s) sur d'autres comptes — c'est eux qui seront "
                        "collectés ✅"
                    ).format(n=claimed)
                return False, tagged(t(
                    "credentials.soundcloud.no_public_tracks",
                    "User ID {user_id} joignable, mais **aucun titre public** n'y est "
                    "rattaché — il n'y aura donc rien à collecter. Deux cas :\n\n"
                    # « plus haut dans cet onglet » était vrai jusqu'au 2026-09-04,
                    # jour où le panneau a été déplacé sur ☁️ SoundCloud —
                    # Performance. Le message a survécu au déplacement et envoyait
                    # chercher, dans cet onglet, une section qui n'y est plus. Il
                    # nomme donc la PAGE, la seule chose qui ne bouge pas quand la
                    # mise en page change.
                    "• **Tes sorties paraissent sous un label ou un autre compte** → "
                    "déclare-les sur la page **☁️ SoundCloud — Performance**, section "
                    "**« Mes titres hébergés sur d'autres comptes »**. Colle l'URL de "
                    "chaque titre, une par ligne.\n"
                    "• **Sinon** → vérifie que c'est bien l'ID de TON profil et que tes "
                    "titres sont en **public** (et non privés ou en écoute restreinte)."
                ).format(user_id=user_id), NOTHING_TO_COLLECT)
            return True, t("credentials.soundcloud.test_ok",
                           "API SoundCloud OAuth OK — {count} track(s) récupéré(s) pour user {user_id} ✅").format(
                               count=count, user_id=user_id)
        if r2.status_code == 404:
            return False, tagged(t("credentials.soundcloud.not_found",
                            "404 — User ID '{user_id}' introuvable. Vérifier que c'est bien l'ID numérique.").format(
                                user_id=user_id), NOT_FOUND)
        return False, f"HTTP {r2.status_code} — {r2.text[:200]}"
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
