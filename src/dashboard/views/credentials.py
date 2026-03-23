"""Vue Credentials — Gestion des credentials API par plateforme (Brick 4).

Accessible à tous les utilisateurs authentifiés.
- Artiste : gère ses propres credentials (artist_id depuis session).
- Admin    : sélectionne n'importe quel artiste.

Stockage :
- token_encrypted (TEXT) : JSON de tous les champs secrets, chiffré Fernet.
- extra_config    (JSONB) : champs non-secrets (client_id, redirect_uri, account_id…).
"""
import json
import requests
import pandas as pd
import streamlit as st

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin
from src.utils.config_loader import config_loader


# ─────────────────────────────────────────────
# Fernet helpers
# ─────────────────────────────────────────────

def _get_fernet():
    """Retourne un objet Fernet ou None si fernet_key non configuré."""
    from cryptography.fernet import Fernet
    config = config_loader.load()
    key = config.get('fernet_key', '')
    if not key:
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        return None


def _encrypt_secrets(secrets: dict) -> str:
    """Chiffre un dict de secrets en JSON avec Fernet."""
    f = _get_fernet()
    if f is None:
        raise ValueError("fernet_key non configuré dans config/config.yaml")
    return f.encrypt(json.dumps(secrets).encode()).decode()


def _decrypt_secrets(token_encrypted: str) -> dict:
    """Déchiffre le blob token_encrypted en dict. Retourne {} en cas d'erreur."""
    if not token_encrypted:
        return {}
    f = _get_fernet()
    if f is None:
        return {}
    try:
        return json.loads(f.decrypt(token_encrypted.encode()).decode())
    except Exception:
        return {}


def _mask(value: str, visible: int = 6) -> str:
    if not value or len(value) <= visible:
        return '***'
    return value[:visible] + '…***'


# ─────────────────────────────────────────────
# Platform definitions
# ─────────────────────────────────────────────
# 'secret': True  → stocké dans token_encrypted (Fernet-chiffré)
# 'secret': False → stocké dans extra_config (JSONB, lisible)

PLATFORMS = {
    'spotify': {
        'label': '🎵 Spotify',
        'fields': [
            {'key': 'client_id',     'label': 'Client ID',     'secret': False},
            {'key': 'client_secret', 'label': 'Client Secret', 'secret': True},
            {'key': 'redirect_uri',  'label': 'Redirect URI',  'secret': False,
             'default': 'http://localhost:8888/callback'},
            {'key': 'refresh_token', 'label': 'Refresh Token', 'secret': True},
        ],
    },
    'youtube': {
        'label': '🎬 YouTube',
        'fields': [
            {'key': 'client_id',     'label': 'Client ID',     'secret': False},
            {'key': 'client_secret', 'label': 'Client Secret', 'secret': True},
            {'key': 'refresh_token', 'label': 'Refresh Token', 'secret': True},
        ],
    },
    'soundcloud': {
        'label': '☁️ SoundCloud',
        'fields': [
            {'key': 'client_id',     'label': 'Client ID',     'secret': False},
            {'key': 'client_secret', 'label': 'Client Secret', 'secret': True},
        ],
    },
    'meta': {
        'label': '📱 Meta / Instagram',
        'fields': [
            {'key': 'access_token', 'label': 'Access Token',         'secret': True},
            {'key': 'account_id',   'label': 'Ad Account ID (act_…)', 'secret': False},
            {'key': 'app_id',       'label': 'App ID',                'secret': False},
            {'key': 'app_secret',   'label': 'App Secret',            'secret': True},
        ],
    },
}


# ─────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────

def _load_credentials(db, artist_id: int) -> dict:
    """Retourne {platform: row_dict} depuis artist_credentials."""
    df = db.fetch_df(
        "SELECT platform, token_encrypted, extra_config, expires_at, updated_at "
        "FROM artist_credentials WHERE artist_id = %s",
        (artist_id,)
    )
    result = {}
    for _, row in df.iterrows():
        result[row['platform']] = row.to_dict()
    return result


def _save_credentials(db, artist_id: int, platform: str,
                      encrypted_blob: str, extra: dict) -> None:
    db.execute_query(
        """
        INSERT INTO artist_credentials
            (artist_id, platform, token_encrypted, extra_config, updated_at)
        VALUES (%s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (artist_id, platform)
        DO UPDATE SET
            token_encrypted = EXCLUDED.token_encrypted,
            extra_config    = EXCLUDED.extra_config,
            updated_at      = NOW()
        """,
        (artist_id, platform, encrypted_blob, json.dumps(extra))
    )


# ─────────────────────────────────────────────
# Field value helpers
# ─────────────────────────────────────────────

def _decode_row(row: dict, fields: list) -> dict:
    """Reconstruit {field_key: plain_value} depuis une ligne DB."""
    secrets = _decrypt_secrets(row.get('token_encrypted') or '')

    extra = row.get('extra_config') or {}
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except Exception:
            extra = {}

    result = {}
    for f in fields:
        key = f['key']
        result[key] = secrets.get(key, '') if f['secret'] else extra.get(key, '')
    return result


# ─────────────────────────────────────────────
# Connection tests
# ─────────────────────────────────────────────

def _test_spotify(fields: dict) -> tuple:
    try:
        r = requests.post(
            'https://accounts.spotify.com/api/token',
            data={'grant_type': 'client_credentials'},
            auth=(fields.get('client_id', ''), fields.get('client_secret', '')),
            timeout=10,
        )
        data = r.json()
        if r.status_code == 200 and data.get('access_token'):
            return True, "Token client_credentials obtenu ✅"
        return False, data.get('error_description', r.text[:150])
    except Exception as e:
        return False, str(e)


def _test_youtube(fields: dict) -> tuple:
    if not fields.get('refresh_token'):
        return False, "Refresh token requis pour tester YouTube."
    try:
        r = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'client_id':     fields.get('client_id', ''),
                'client_secret': fields.get('client_secret', ''),
                'refresh_token': fields.get('refresh_token', ''),
                'grant_type':    'refresh_token',
            },
            timeout=10,
        )
        data = r.json()
        if r.status_code == 200 and data.get('access_token'):
            return True, f"Access token obtenu (expire dans {data.get('expires_in', '?')}s) ✅"
        return False, data.get('error_description', data.get('error', r.text[:150]))
    except Exception as e:
        return False, str(e)


def _test_soundcloud(fields: dict) -> tuple:
    try:
        r = requests.get(
            'https://api.soundcloud.com/tracks',
            params={'client_id': fields.get('client_id', ''), 'limit': 1},
            timeout=10,
        )
        if r.status_code == 200:
            return True, "API SoundCloud accessible ✅"
        return False, f"HTTP {r.status_code} — {r.text[:150]}"
    except Exception as e:
        return False, str(e)


def _test_meta(fields: dict) -> tuple:
    try:
        r = requests.get(
            'https://graph.facebook.com/v18.0/me',
            params={'access_token': fields.get('access_token', ''), 'fields': 'id,name'},
            timeout=10,
        )
        data = r.json()
        if r.status_code == 200 and data.get('id'):
            return True, f"Connecté : {data.get('name', data['id'])} ✅"
        msg = data.get('error', {})
        if isinstance(msg, dict):
            msg = msg.get('message', r.text[:150])
        return False, str(msg)
    except Exception as e:
        return False, str(e)


CONNECTION_TESTS = {
    'spotify':    _test_spotify,
    'youtube':    _test_youtube,
    'soundcloud': _test_soundcloud,
    'meta':       _test_meta,
}


# ─────────────────────────────────────────────
# View
# ─────────────────────────────────────────────

def show():
    st.title("🔑 Credentials API")
    st.caption(
        "Gérez vos credentials d'accès API par plateforme. "
        "Les secrets sont chiffrés (Fernet) avant stockage en base."
    )

    db = get_db_connection()
    try:
        # ── Sélection artiste ──────────────────────────────────────────────
        if is_admin():
            df_artists = db.fetch_df(
                "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id"
            )
            if df_artists.empty:
                st.warning("Aucun artiste actif. Créez-en un dans l'onglet Admin.")
                return
            choices = {f"{r['id']} — {r['name']}": r['id'] for _, r in df_artists.iterrows()}
            sel_label = st.selectbox("Artiste cible", list(choices.keys()))
            target_artist_id = choices[sel_label]
        else:
            target_artist_id = get_artist_id()
            if target_artist_id is None:
                st.error("Impossible de déterminer votre identifiant artiste.")
                return

        # ── Vérification Fernet ───────────────────────────────────────────
        fernet_ok = _get_fernet() is not None
        if not fernet_ok:
            st.warning(
                "⚠️ `fernet_key` absent de `config/config.yaml`. "
                "La sauvegarde est désactivée. "
                "Générez une clé : "
                "`python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\"`"
            )

        # ── Chargement credentials existants ─────────────────────────────
        existing = _load_credentials(db, target_artist_id)

        # ── Onglets plateforme ────────────────────────────────────────────
        tab_labels = [info['label'] for info in PLATFORMS.values()]
        tabs = st.tabs(tab_labels)

        for tab, (platform_key, platform_info) in zip(tabs, PLATFORMS.items()):
            with tab:
                _render_platform_tab(
                    db=db,
                    platform_key=platform_key,
                    platform_info=platform_info,
                    artist_id=target_artist_id,
                    existing_row=existing.get(platform_key),
                    fernet_ok=fernet_ok,
                )
    finally:
        db.close()


def _render_platform_tab(db, platform_key, platform_info, artist_id,
                         existing_row, fernet_ok):
    fields_def = platform_info['fields']

    # ── Statut actuel ──────────────────────────────────────────────────
    if existing_row:
        updated = existing_row.get('updated_at')
        updated_str = (
            pd.to_datetime(updated).strftime('%d/%m/%Y %H:%M') if updated else '?'
        )
        st.success(f"Credentials enregistrés — mise à jour : {updated_str}")
        existing_values = _decode_row(existing_row, fields_def)
    else:
        st.info("Aucun credential enregistré pour cette plateforme.")
        existing_values = {}

    st.markdown("---")

    # ── Formulaire ────────────────────────────────────────────────────
    with st.form(f"cred_{platform_key}_{artist_id}"):
        st.subheader("Mettre à jour")
        st.caption(
            "🔒 Champs secrets chiffrés • Laissez vide pour conserver la valeur actuelle"
        )

        form_values = {}
        pairs = [fields_def[i:i + 2] for i in range(0, len(fields_def), 2)]

        for pair in pairs:
            cols = st.columns(len(pair))
            for col, field in zip(cols, pair):
                key = field['key']
                existing_val = existing_values.get(key, '')

                if field['secret']:
                    val = col.text_input(
                        field['label'],
                        type='password',
                        placeholder=_mask(existing_val) if existing_val else 'Non défini',
                        help="🔒 Chiffré en base — laisser vide pour conserver",
                        key=f"{platform_key}_{artist_id}_{key}",
                    )
                else:
                    val = col.text_input(
                        field['label'],
                        value=existing_val or field.get('default', ''),
                        key=f"{platform_key}_{artist_id}_{key}",
                    )
                form_values[key] = val

        submitted = st.form_submit_button(
            "💾 Enregistrer",
            type="primary",
            disabled=not fernet_ok,
        )

        if submitted and fernet_ok:
            _handle_save(
                db=db,
                platform_key=platform_key,
                fields_def=fields_def,
                artist_id=artist_id,
                form_values=form_values,
                existing_values=existing_values,
            )

    # ── Test de connexion (hors form) ─────────────────────────────────
    if existing_row and platform_key in CONNECTION_TESTS:
        st.markdown("---")
        if st.button(
            f"🔌 Tester la connexion",
            key=f"test_{platform_key}_{artist_id}",
        ):
            with st.spinner("Test en cours…"):
                test_fields = _decode_row(existing_row, fields_def)
                ok, msg = CONNECTION_TESTS[platform_key](test_fields)
                if ok:
                    st.success(msg)
                else:
                    st.error(f"Connexion échouée : {msg}")


def _handle_save(db, platform_key, fields_def, artist_id, form_values, existing_values):
    """Prépare et sauvegarde les credentials chiffrés."""
    try:
        secrets = {}
        extra = {}

        for field in fields_def:
            key = field['key']
            new_val = form_values.get(key, '').strip()

            # Secret vide → conserver l'ancienne valeur
            if not new_val and field['secret']:
                new_val = existing_values.get(key, '')

            if field['secret']:
                secrets[key] = new_val
            else:
                extra[key] = new_val

        encrypted_blob = _encrypt_secrets(secrets) if any(secrets.values()) else ''
        _save_credentials(db, artist_id, platform_key, encrypted_blob, extra)
        st.success(f"✅ Credentials {platform_key} enregistrés.")
        st.rerun()

    except Exception as e:
        st.error(f"❌ Erreur lors de la sauvegarde : {e}")
