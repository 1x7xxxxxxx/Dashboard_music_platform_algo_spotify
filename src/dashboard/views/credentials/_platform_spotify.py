"""Credentials — Spotify connection test + setup guide.

Type: Sub
Uses: requests, streamlit
Pure relocation from the former credentials.py — no logic change.
"""
import requests
import streamlit as st

from src.dashboard.utils.i18n import t


def _test_spotify(fields: dict) -> tuple:
    try:
        r = requests.post(
            'https://accounts.spotify.com/api/token',
            data={'grant_type': 'client_credentials'},
            auth=(fields.get('client_id', ''), fields.get('client_secret', '')),
            timeout=10,
            allow_redirects=False,  # INFO-04: prevent open-redirect SSRF
        )
        data = r.json()
        if r.status_code == 200 and data.get('access_token'):
            return True, t("credentials.spotify.test_ok",
                           "Token client_credentials obtenu ✅")
        return False, data.get('error_description', r.text[:150])
    except Exception as e:
        return False, str(e)


def _guide_spotify():
    with st.expander(t("credentials.spotify.guide_title",
                       "🎵 Comment obtenir les credentials Spotify ?"), expanded=False):
        st.markdown(t(
            "credentials.spotify.guide_steps",
            "1. Aller sur **[developers.spotify.com](https://developer.spotify.com/dashboard)** → Log in → **Create App**\n"
            "2. Renseigner un nom (la Redirect URI n'a pas d'importance ici)\n"
            "3. Copier le **Client ID** et le **Client Secret** → les coller ci-dessous\n"
        ))
        st.info(t("credentials.spotify.guide_info",
                  "Le collecteur utilise le flux **client_credentials** : pas de "
                  "Redirect URI ni de Refresh Token à gérer, le token se "
                  "renouvelle seul à chaque run."))
