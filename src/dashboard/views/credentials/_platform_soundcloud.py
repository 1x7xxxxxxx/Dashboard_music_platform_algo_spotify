"""Credentials — SoundCloud connection test + setup guide.

Type: Sub
Uses: requests, streamlit
Pure relocation from the former credentials.py — no logic change.
"""
import os

import requests
import streamlit as st


def _test_soundcloud(fields: dict) -> tuple:
    """Test SoundCloud via OAuth 2.0 Client Credentials flow (official API)."""
    # The artist only provides user_id; app credentials come from the shared env
    # app (SOUNDCLOUD_CLIENT_ID/SECRET), with a per-artist stored override if any.
    user_id       = fields.get('user_id', '').strip()
    client_id     = fields.get('client_id', '').strip() or os.getenv('SOUNDCLOUD_CLIENT_ID', '')
    client_secret = fields.get('client_secret', '').strip() or os.getenv('SOUNDCLOUD_CLIENT_SECRET', '')

    if not user_id:
        return False, "User ID vide — voir le guide ci-dessus pour le trouver (/discover)."
    if not client_id or not client_secret:
        return False, ("App SoundCloud non configurée côté plateforme "
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
            return False, "Token absent dans la réponse OAuth."

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
            return True, f"API SoundCloud OAuth OK — {count} track(s) récupéré(s) pour user {user_id} ✅"
        if r2.status_code == 404:
            return False, f"404 — User ID '{user_id}' introuvable. Vérifier que c'est bien l'ID numérique."
        return False, f"HTTP {r2.status_code} — {r2.text[:200]}"
    except Exception as e:
        return False, str(e)


def _guide_soundcloud():
    with st.expander("☁️ Comment obtenir les credentials SoundCloud ?", expanded=False):
        st.info(
            "**Admin (toi)** : crée une app une seule fois sur soundcloud.com/you/apps — "
            "le `Client ID` et le `Client Secret` sont partagés par tous les artistes.\n\n"
            "**Chaque artiste** : fournit uniquement son `User ID` numérique."
        )

        st.markdown("### Admin — Créer l'app (une seule fois)")
        admin_steps = [
            ("Prérequis", "Avoir un abonnement **Artist Pro** actif sur SoundCloud."),
            ("Créer l'app", "Aller sur **soundcloud.com/you/apps** → **Register a new application**. "
             "Nom : ne pas utiliser le mot « SoundCloud » (ex : `ETL Airflow Dashboard`). "
             "Redirect URI : `http://localhost` (non utilisée)."),
            ("Copier les credentials", "Sur la page de l'app, copier le **Client ID** et le **Client Secret** "
             "et les saisir dans le formulaire ci-dessous."),
        ]
        for i, (title, desc) in enumerate(admin_steps, 1):
            st.markdown(f"**{i}. {title}** — {desc}")

        st.markdown("### Artiste — Trouver son User ID")
        st.markdown("Deux méthodes :")

        st.markdown("**Méthode 1 — URL directe (la plus simple)**")
        st.code("https://soundcloud.com/api/users/monpseudo", language="text")
        st.markdown(
            "Ouvrir cette URL dans le navigateur (remplacer `monpseudo` par le slug du profil). "
            "La réponse JSON contient `\"id\": 123456789` — c'est le User ID à copier."
        )

        st.markdown("**Méthode 2 — DevTools**")
        devtools_steps = [
            "Aller sur **soundcloud.com** connecté à son compte.",
            "Appuyer sur **F12** → onglet **Network**.",
            "Jouer n'importe quelle piste.",
            "Filtrer les requêtes par `/users/` — l'URL contient `/users/123456789`.",
            "Copier le nombre — c'est le User ID.",
        ]
        for step in devtools_steps:
            st.markdown(f"- {step}")

        st.markdown("### Note")
        st.markdown(
            "- `Client ID` et `Client Secret` sont **permanents** — pas de rotation automatique.\n"
            "- Les access tokens OAuth sont renouvelés **automatiquement** par le DAG à chaque run (TTL 3600s).\n"
            "- Création d'app réservée aux comptes **Artist Pro**. "
            "Si les inscriptions sont fermées, contacter `soundcloud-api@soundcloud.com`."
        )
