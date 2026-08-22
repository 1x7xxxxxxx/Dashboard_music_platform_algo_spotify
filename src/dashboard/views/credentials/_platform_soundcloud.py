"""Credentials — SoundCloud connection test + setup guide.

Type: Sub
Uses: requests, streamlit
Pure relocation from the former credentials.py — no logic change.
"""
import os

import requests
import streamlit as st

from src.dashboard.utils.i18n import t
from src.dashboard.utils.os_hints import md as _os_md


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
        return False, t("credentials.soundcloud.user_id_empty",
                        "User ID vide — voir le guide ci-dessus pour le trouver (/discover).")
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
            return False, t("credentials.soundcloud.token_missing",
                            "Token absent dans la réponse OAuth.")

        # Step 2: fetch tracks
        r2 = requests.get(
            f'https://api.soundcloud.com/users/{user_id}/tracks',
            headers={'Authorization': f'OAuth {token}'},
            params={'limit': 1, 'linked_partitioning': 1},
            timeout=10,
            allow_redirects=False,  # INFO-04
        )
        if r2.status_code == 200:
            count = len(r2.json().get('collection', []))
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
                return False, t(
                    "credentials.soundcloud.no_public_tracks",
                    "User ID {user_id} joignable, mais **aucun titre public** n'y est "
                    "rattaché — il n'y aura donc rien à collecter. Si tes sorties "
                    "paraissent sous un label ou un autre compte, déclare-les une par "
                    "une dans « Mes titres hébergés ailleurs » ci-dessous. Sinon "
                    "vérifie que c'est bien l'ID de TON profil et que tes titres sont "
                    "en **public**."
                ).format(user_id=user_id)
            return True, t("credentials.soundcloud.test_ok",
                           "API SoundCloud OAuth OK — {count} track(s) récupéré(s) pour user {user_id} ✅").format(
                               count=count, user_id=user_id)
        if r2.status_code == 404:
            return False, t("credentials.soundcloud.not_found",
                            "404 — User ID '{user_id}' introuvable. Vérifier que c'est bien l'ID numérique.").format(
                                user_id=user_id)
        return False, f"HTTP {r2.status_code} — {r2.text[:200]}"
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


def _guide_soundcloud():
    with st.expander(t("credentials.soundcloud.guide_title",
                       "☁️ Comment obtenir les credentials SoundCloud ?"), expanded=False):
        st.info(t(
            "credentials.soundcloud.guide_info",
            "**Admin (toi)** : crée une app une seule fois sur soundcloud.com/you/apps — "
            "le `Client ID` et le `Client Secret` sont partagés par tous les artistes.\n\n"
            "**Chaque artiste** : fournit uniquement son `User ID` numérique."
        ))

        st.markdown(t("credentials.soundcloud.admin_header",
                      "### Admin — Créer l'app (une seule fois)"))
        admin_steps = [
            (t("credentials.soundcloud.admin_prereq_title", "Prérequis"),
             t("credentials.soundcloud.admin_prereq_desc",
               "Avoir un abonnement **Artist Pro** actif sur SoundCloud.")),
            (t("credentials.soundcloud.admin_create_title", "Créer l'app"),
             t("credentials.soundcloud.admin_create_desc",
               "Aller sur **soundcloud.com/you/apps** → **Register a new application**. "
               "Nom : ne pas utiliser le mot « SoundCloud » (ex : `ETL Airflow Dashboard`). "
               "Redirect URI : `http://localhost` (non utilisée).")),
            (t("credentials.soundcloud.admin_copy_title", "Copier les credentials"),
             t("credentials.soundcloud.admin_copy_desc",
               "Sur la page de l'app, copier les identifiants et les poser dans les "
               "variables d'environnement du serveur (`SOUNDCLOUD_CLIENT_ID` / "
               "`SOUNDCLOUD_CLIENT_SECRET`). Ce formulaire ne les accepte pas : "
               "l'app est partagée par tous les artistes (ADR-006).")),
        ]
        for i, (title, desc) in enumerate(admin_steps, 1):
            st.markdown(f"**{i}. {title}** — {desc}")

        st.markdown(t("credentials.soundcloud.artist_header",
                      "### Artiste — Trouver son User ID"))
        st.markdown(t("credentials.soundcloud.two_methods", "Deux méthodes :"))

        st.markdown(t("credentials.soundcloud.method1_title",
                      "**Méthode 1 — URL directe (la plus simple)**"))
        st.code("https://soundcloud.com/api/users/monpseudo", language="text")
        st.markdown(t(
            "credentials.soundcloud.method1_desc",
            "Ouvrir cette URL dans le navigateur (remplacer `monpseudo` par le slug du profil). "
            "La réponse JSON contient `\"id\": 123456789` — c'est le User ID à copier."
        ))

        st.markdown(t("credentials.soundcloud.method2_title", "**Méthode 2 — DevTools**"))
        devtools_steps = [
            t("credentials.soundcloud.devtools_1",
              "Aller sur **soundcloud.com** connecté à son compte."),
            t("credentials.soundcloud.devtools_2", "Appuyer sur **{{DEVTOOLS}}** → onglet **Network**."),
            t("credentials.soundcloud.devtools_3", "Jouer n'importe quelle piste."),
            t("credentials.soundcloud.devtools_4",
              "Filtrer les requêtes par `/users/` — l'URL contient `/users/123456789`."),
            t("credentials.soundcloud.devtools_5", "Copier le nombre — c'est le User ID."),
        ]
        for step in devtools_steps:
            st.markdown(f"- {_os_md(step)}")

        st.markdown(t("credentials.soundcloud.note_header", "### Note"))
        st.markdown(t(
            "credentials.soundcloud.note_body",
            "- `Client ID` et `Client Secret` sont **permanents** — pas de rotation automatique.\n"
            "- Les access tokens OAuth sont renouvelés **automatiquement** par le DAG à chaque run (TTL 3600s).\n"
            "- Création d'app réservée aux comptes **Artist Pro**. "
            "Si les inscriptions sont fermées, contacter `soundcloud-api@soundcloud.com`."
        ))
