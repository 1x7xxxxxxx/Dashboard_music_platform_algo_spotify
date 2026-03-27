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

# DAGs associated to each platform (used for last-run status KPI)
PLATFORM_TO_DAGS = {
    'spotify':    ['spotify_api_daily'],
    'youtube':    ['youtube_daily'],
    'soundcloud': ['soundcloud_daily'],
    'meta':       ['meta_insights_dag', 'instagram_daily'],
}

_STATE_ICON = {
    'success': '🟢',
    'failed':  '🔴',
    'running': '🔵',
    'queued':  '🟡',
    None:      '⚫',
}


def _fetch_dag_last_states() -> dict:
    """Returns {dag_id: {state, date}} for all platform DAGs. Non-blocking on failure."""
    try:
        from src.dashboard.utils.airflow_monitor import AirflowMonitor
        monitor = AirflowMonitor()
        all_ids = {d for dags in PLATFORM_TO_DAGS.values() for d in dags}
        result = {}
        for dag_id in all_ids:
            runs = monitor.get_runs_for_dag(dag_id, limit=1)
            if runs:
                r = runs[0]
                result[dag_id] = {
                    'state': r.get('state'),
                    'date': (r.get('start_date') or '')[:16] or '—',
                }
            else:
                result[dag_id] = {'state': None, 'date': '—'}
        return result
    except Exception:
        return {}


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
            {'key': 'client_id', 'label': 'Client ID (extrait via DevTools)', 'secret': False},
            {'key': 'user_id',   'label': 'User ID numérique (ex: 123456789)', 'secret': False},
        ],
    },
    'meta': {
        'label': '📱 Meta / Instagram',
        'fields': [
            {'key': 'access_token', 'label': 'Access Token (Long-lived)',       'secret': True},
            {'key': 'app_secret',   'label': 'App Secret',                      'secret': True},
            {'key': 'app_id',       'label': 'App ID',                          'secret': False},
            {'key': 'account_id',   'label': 'Ad Account ID (act_…)',           'secret': False},
            {'key': 'ig_user_id',   'label': 'Instagram Business Account ID',   'secret': False},
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
    """Test SoundCloud v2 API using the same headers as SoundCloudCollector."""
    client_id = fields.get('client_id', '').strip()
    user_id   = fields.get('user_id',   '').strip()

    if not client_id:
        return False, "Client ID vide — extraire via DevTools (F12 → Network → filtrer client_id)."
    if not user_id:
        return False, "User ID vide — trouver dans DevTools : chercher une requête /users/XXXXXXXX."

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Origin': 'https://soundcloud.com',
        'Referer': 'https://soundcloud.com/',
    }
    try:
        r = requests.get(
            f'https://api-v2.soundcloud.com/users/{user_id}/tracks',
            params={'client_id': client_id, 'limit': 1, 'linked_partitioning': 1},
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            count = len(data.get('collection', []))
            return True, f"API SoundCloud v2 OK — {count} track(s) récupéré(s) pour user {user_id} ✅"
        if r.status_code == 401:
            return False, "401 — client_id expiré. Recommencer l'extraction DevTools."
        if r.status_code == 403:
            return False, "403 — client_id refusé. Recommencer l'extraction DevTools (le client_id change régulièrement)."
        if r.status_code == 404:
            return False, f"404 — User ID introuvable. Vérifier que '{user_id}' est bien l'ID numérique (pas un nom d'utilisateur)."
        return False, f"HTTP {r.status_code} — {r.text[:200]}"
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

        # ── Statut DAGs (non-bloquant) ────────────────────────────────────
        with st.spinner("Récupération du statut des DAGs…"):
            dag_states = _fetch_dag_last_states()

        # ── KPI global ───────────────────────────────────────────────────
        _render_global_kpi(existing, dag_states)

        # ── First-time setup banner ───────────────────────────────────────
        if not existing:
            st.info(
                "💡 **Aucun credential configuré.** "
                "Sélectionnez une plateforme ci-dessous et suivez le guide "
                "pour connecter vos sources de données. "
                "Commencez par **Spotify** pour démarrer la collecte."
            )

        st.markdown("---")

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
                    dag_states=dag_states,
                )
    finally:
        db.close()


def _render_platform_guide(platform_key: str) -> None:
    """Render a detailed, platform-specific credential guide."""
    guides = {
        'soundcloud': _guide_soundcloud,
        'meta':       _guide_meta,
        'spotify':    _guide_spotify,
        'youtube':    _guide_youtube,
    }
    fn = guides.get(platform_key)
    if not fn:
        return
    fn()


def _guide_soundcloud():
    with st.expander("☁️ Comment obtenir le Client ID SoundCloud ?", expanded=False):
        st.warning(
            "⚠️ **API SoundCloud fermée depuis 2021.** Aucun enregistrement d'app n'est possible. "
            "La seule méthode disponible est d'extraire le `client_id` interne depuis le trafic réseau "
            "du site web SoundCloud. Ces credentials sont non officiels et peuvent changer sans préavis."
        )
        st.markdown("### Méthode : extraction via DevTools Chrome/Firefox")

        steps = [
            ("Ouvrir Chrome ou Firefox", "Aller sur **soundcloud.com** et se connecter à ton compte."),
            ("Ouvrir les DevTools", "Appuyer sur **F12** (ou clic droit → Inspecter). Aller dans l'onglet **Network** (Réseau)."),
            ("Filtrer les requêtes", "Dans la barre de filtre du Network, taper **`client_id`**."),
            ("Déclencher une requête", "Cliquer sur une chanson pour la jouer, ou naviguer dans un profil. Des requêtes vers `api-v2.soundcloud.com` apparaissent."),
            ("Trouver le client_id", "Cliquer sur n'importe quelle requête vers `api-v2.soundcloud.com`. Dans l'onglet **Headers**, regarder la **Request URL**."),
            ("Copier la valeur", "La valeur ressemble à ceci :"),
        ]

        for i, (title, desc) in enumerate(steps, 1):
            st.markdown(f"**{i}. {title}** — {desc}")

        st.code(
            "https://api-v2.soundcloud.com/tracks?client_id=AbCdEf123456789aBcDeFgHiJkLm12&...",
            language="text",
        )
        st.markdown("Copier uniquement la valeur après `client_id=` (chaîne de ~32 caractères alphanumériques).")

        st.markdown("### Trouver ton User ID numérique")
        st.markdown(
            "Dans le même onglet Network (toujours sur soundcloud.com avec F12 ouvert), "
            "chercher une requête contenant `/users/` dans l'URL :"
        )
        st.code(
            "https://api-v2.soundcloud.com/users/123456789?client_id=...&app_version=...",
            language="text",
        )
        st.markdown(
            "Le nombre après `/users/` est ton **User ID** (ex: `123456789`). "
            "C'est un identifiant numérique, **pas** le nom d'utilisateur texte."
        )
        st.info(
            "💡 Astuce : dans le filtre Network, taper `/users/` pour isoler rapidement ces requêtes."
        )

        st.markdown("### Durée de validité")
        st.markdown(
            "- Ce `client_id` est lié à l'app interne de SoundCloud — il change lors de leurs déploiements.\n"
            "- Durée typique : **quelques semaines à quelques mois**.\n"
            "- Si le DAG `soundcloud_daily` échoue avec une erreur 401, le DAG tente un **renouvellement "
            "automatique** (extraction depuis le bundle JS de soundcloud.com) et sauvegarde le nouveau "
            "`client_id` en base sans intervention manuelle.\n"
            "- Si le renouvellement automatique échoue (IP bloquée ou structure du bundle changée), "
            "utiliser le bouton **Rafraîchir le client_id** ci-dessous ou la méthode DevTools.\n"
            "- 📅 **Recommandé** : mettre un rappel calendrier tous les 2 mois."
        )


def _guide_meta():
    with st.expander("📱 Où trouver chaque champ Meta / Instagram ?", expanded=False):
        st.info(
            "Le token est renouvelé **automatiquement** par le DAG `meta_token_refresh` (hebdomadaire). "
            "Ce guide sert uniquement lors de la première configuration ou si le token est expiré."
        )

        st.markdown("**Tout se trouve sur une seule page — ouvre-la dans ton navigateur :**")
        st.code("https://developers.facebook.com/apps/TON_APP_ID/settings/basic/", language="text")

        st.markdown(
            "| Champ | Où le trouver |\n"
            "|---|---|\n"
            "| **App ID** | En haut de la page Paramètres → Général |\n"
            "| **App Secret** | Même page → cliquer **Afficher** à côté de App Secret |\n"
            "| **Access Token** | [Graph API Explorer](https://developers.facebook.com/tools/explorer) → sélectionner ton app → Generate Access Token → puis [Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/) → Extend Access Token (60 jours) |\n"
            "| **Ad Account ID** | [Ads Manager](https://adsmanager.facebook.com) → Paramètres → Paramètres du compte → Account ID → ajouter préfixe `act_` |\n"
            "| **Instagram Business Account ID** | Distinct de l'Ad Account ID — coller ton Access Token dans la barre d'adresse : `https://graph.facebook.com/v18.0/me/accounts?access_token=TON_TOKEN` → récupérer le `id` de ta Page → puis `https://graph.facebook.com/v18.0/PAGE_ID?fields=instagram_business_account&access_token=TON_TOKEN` |\n"
        )

        st.warning(
            "⚠️ **Ne pas confondre** App ID (`2200684950508458`) et Ad Account ID (`act_123456789`). "
            "Ce sont deux identifiants distincts."
        )


def _guide_spotify():
    with st.expander("🎵 Comment obtenir les credentials Spotify ?", expanded=False):
        st.markdown(
            "1. Aller sur **[developers.spotify.com](https://developer.spotify.com/dashboard)** → Log in → **Create App**\n"
            "2. Renseigner un nom + ajouter `http://localhost:8888/callback` comme **Redirect URI**\n"
            "3. Copier le **Client ID** et le **Client Secret** depuis le tableau de bord\n"
            "4. Lancer le script d'auth pour obtenir le **Refresh Token** :\n"
        )
        st.code("python src/collectors/spotify_auth.py", language="bash")


def _guide_youtube():
    with st.expander("🎬 Comment obtenir les credentials YouTube ?", expanded=False):
        st.markdown(
            "1. Aller sur **[console.cloud.google.com](https://console.cloud.google.com)** → Créer un projet\n"
            "2. **APIs & Services → Bibliothèque** → activer **YouTube Data API v3**\n"
            "3. **APIs & Services → Identifiants → Créer des identifiants → ID client OAuth 2.0 → Application de bureau**\n"
            "4. Télécharger le JSON → extraire **Client ID** et **Client Secret**\n"
            "5. Lancer le script d'auth pour obtenir le **Refresh Token** :\n"
        )
        st.code("python src/collectors/youtube_auth.py", language="bash")
        st.info("Le Refresh Token YouTube est permanent tant que l'accès n'est pas révoqué.")


def _render_global_kpi(existing: dict, dag_states: dict) -> None:
    """Summary row: one metric per platform showing credentials + last DAG run."""
    cols = st.columns(len(PLATFORMS))
    for col, (platform_key, platform_info) in zip(cols, PLATFORMS.items()):
        has_creds = platform_key in existing
        dags = PLATFORM_TO_DAGS.get(platform_key, [])

        # Last run state across all DAGs for this platform (worst state wins)
        states = [dag_states.get(d, {}).get('state') for d in dags]
        if 'failed' in states:
            run_icon = '🔴'
            run_label = 'Dernier run : FAILED'
        elif 'running' in states:
            run_icon = '🔵'
            run_label = 'En cours'
        elif 'success' in states:
            run_icon = '🟢'
            run_label = 'Dernier run : OK'
        elif not dag_states:
            run_icon = '⚫'
            run_label = 'Airflow inaccessible'
        else:
            run_icon = '⚫'
            run_label = 'Jamais exécuté'

        creds_icon = '✅' if has_creds else '❌'
        creds_label = 'Connecté' if has_creds else 'Non configuré'

        col.metric(
            label=platform_info['label'],
            value=f"{creds_icon} {creds_label}",
            delta=f"{run_icon} {run_label}",
            delta_color="off",
        )


def _render_dag_status_badge(platform_key: str, dag_states: dict) -> None:
    """Inline status badge inside a platform tab."""
    dags = PLATFORM_TO_DAGS.get(platform_key, [])
    if not dags or not dag_states:
        return
    for dag_id in dags:
        info = dag_states.get(dag_id, {})
        state = info.get('state')
        icon = _STATE_ICON.get(state, '⚫')
        date = info.get('date', '—')
        st.caption(f"DAG `{dag_id}` — {icon} **{state or 'jamais exécuté'}** — dernier run : {date}")


def _render_soundcloud_refresh_button(db, artist_id: int, existing_row: dict | None) -> None:
    """Auto-refresh the SoundCloud client_id from the public JS bundle.

    Extracts the current client_id from SoundCloud's JS bundle (no DevTools needed),
    saves it to artist_credentials, and refreshes the page.
    Non-blocking: errors are surfaced as st.error without crashing the view.
    """
    st.markdown("---")
    st.markdown("#### Renouvellement automatique du Client ID")
    st.caption(
        "Extrait le `client_id` actuel directement depuis le bundle JavaScript de soundcloud.com. "
        "Ne nécessite pas d'ouvrir les DevTools. Le résultat est sauvegardé en base immédiatement."
    )

    col_btn, col_status = st.columns([1, 3])
    with col_btn:
        clicked = st.button(
            "🔄 Rafraîchir le client_id",
            key=f"sc_refresh_{artist_id}",
            type="primary",
        )

    if clicked:
        with st.spinner("Extraction depuis le bundle JS de soundcloud.com…"):
            try:
                from src.collectors.soundcloud_api_collector import SoundCloudCollector
                new_id = SoundCloudCollector._fetch_client_id_from_bundle()
            except Exception as e:
                st.error(
                    f"Extraction échouée : {e}\n\n"
                    "Causes possibles : IP bloquée par SoundCloud, réseau inaccessible, "
                    "ou structure du bundle changée. Utiliser la méthode DevTools en dernier recours."
                )
                return

        # Persist: merge into extra_config (preserves user_id and other fields)
        try:
            fields_def = PLATFORMS['soundcloud']['fields']
            existing_values = _decode_row(existing_row, fields_def) if existing_row else {}
            extra = {f['key']: existing_values.get(f['key'], '') for f in fields_def if not f['secret']}
            extra['client_id'] = new_id
            _save_credentials(db, artist_id, 'soundcloud', '', extra)
            with col_status:
                st.success(f"✅ Nouveau client_id sauvegardé : `{new_id[:8]}…{new_id[-4:]}`")
            st.rerun()
        except Exception as e:
            st.error(f"Extraction réussie mais sauvegarde échouée : {e}")


def _render_platform_tab(db, platform_key, platform_info, artist_id,
                         existing_row, fernet_ok, dag_states: dict | None = None):
    fields_def = platform_info['fields']

    # ── Statut DAG ────────────────────────────────────────────────────
    if dag_states is not None:
        _render_dag_status_badge(platform_key, dag_states)

    # ── Guide ──────────────────────────────────────────────────────────
    _render_platform_guide(platform_key)

    # ── Statut actuel ──────────────────────────────────────────────────
    if existing_row:
        updated = existing_row.get('updated_at')
        updated_str = (
            pd.to_datetime(updated).strftime('%d/%m/%Y %H:%M') if updated else '?'
        )
        # Expiry badge for platforms that use expiring tokens (Meta)
        expires_at = existing_row.get('expires_at')
        if expires_at is not None:
            try:
                exp = pd.to_datetime(expires_at)
                days_left = (exp - pd.Timestamp.utcnow().tz_localize(None)).days
                if days_left <= 0:
                    st.error(f"Token **expiré** depuis le {exp.strftime('%d/%m/%Y')}. Renouvellement requis.")
                elif days_left <= 15:
                    st.warning(f"Token expire dans **{days_left} jour(s)** ({exp.strftime('%d/%m/%Y')}) — renouvellement recommandé.")
                else:
                    st.success(f"Credentials enregistrés — mise à jour : {updated_str} · Token valide jusqu'au {exp.strftime('%d/%m/%Y')} ({days_left}j)")
            except Exception:
                st.success(f"Credentials enregistrés — mise à jour : {updated_str}")
        else:
            st.success(f"Credentials enregistrés — mise à jour : {updated_str}")
        existing_values = _decode_row(existing_row, fields_def)
    else:
        st.info("Aucun credential enregistré pour cette plateforme.")
        existing_values = {}

    st.markdown("---")

    # ── SoundCloud : bouton auto-refresh en premier, formulaire manuel collapsé ──
    if platform_key == 'soundcloud':
        _render_soundcloud_refresh_button(db, artist_id, existing_row)
        with st.expander("✏️ Saisie manuelle (avancé)", expanded=False):
            st.caption("Utilisez ce formulaire uniquement si le renouvellement automatique échoue.")
            with st.form(f"cred_{platform_key}_{artist_id}"):
                form_values = {}
                pairs = [fields_def[i:i + 2] for i in range(0, len(fields_def), 2)]
                for pair in pairs:
                    cols = st.columns(len(pair))
                    for col, field in zip(cols, pair):
                        key = field['key']
                        existing_val = existing_values.get(key, '')
                        val = col.text_input(
                            field['label'],
                            value=existing_val or field.get('default', ''),
                            key=f"{platform_key}_{artist_id}_{key}",
                        )
                        form_values[key] = val
                submitted = st.form_submit_button("💾 Enregistrer", type="primary", disabled=not fernet_ok)
                if submitted and fernet_ok:
                    _handle_save(db=db, platform_key=platform_key, fields_def=fields_def,
                                 artist_id=artist_id, form_values=form_values, existing_values=existing_values)
        return

    # ── Formulaire standard (toutes autres plateformes) ───────────────
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
            "🔌 Tester la connexion",
            key=f"test_{platform_key}_{artist_id}",
        ):
            with st.spinner("Test en cours…"):
                test_fields = _decode_row(existing_row, fields_def)
                ok, msg = CONNECTION_TESTS[platform_key](test_fields)
                if ok:
                    st.success(msg)
                else:
                    st.error(f"Connexion échouée : {msg}")

    # ── Meta : bouton renouvellement automatique du token ─────────────
    if platform_key == 'meta' and existing_row:
        st.markdown("---")
        st.markdown("#### Renouvellement automatique du token")
        st.caption(
            "Échange le token actuel contre un nouveau token de 60 jours via l'API Meta. "
            "Le token doit être encore valide pour pouvoir être échangé. "
            "Le DAG fait ce renouvellement automatiquement quand il reste ≤ 15 jours."
        )
        if st.button("🔄 Rafraîchir le token Meta", key=f"meta_refresh_{artist_id}", type="primary"):
            with st.spinner("Échange du token en cours…"):
                fields_def_meta = PLATFORMS['meta']['fields']
                current = _decode_row(existing_row, fields_def_meta)
                app_id = current.get('app_id', '')
                app_secret = current.get('app_secret', '')
                access_token = current.get('access_token', '')

                if not app_id or not app_secret:
                    st.error("App ID ou App Secret manquant — renseigner d'abord ces champs.")
                elif not access_token:
                    st.error("Access Token manquant — impossible d'effectuer l'échange.")
                else:
                    try:
                        r = requests.get(
                            'https://graph.facebook.com/v18.0/oauth/access_token',
                            params={
                                'grant_type': 'fb_exchange_token',
                                'client_id': app_id,
                                'client_secret': app_secret,
                                'fb_exchange_token': access_token,
                            },
                            timeout=10,
                        )
                        data = r.json()
                        if r.status_code == 200 and data.get('access_token'):
                            from datetime import timedelta as _td
                            new_token = data['access_token']
                            expires_in = data.get('expires_in', 5184000)
                            new_expires = pd.Timestamp.utcnow() + pd.Timedelta(seconds=expires_in)
                            # Save new token + expires_at
                            secrets = {f['key']: current.get(f['key'], '') for f in fields_def_meta if f['secret']}
                            secrets['access_token'] = new_token
                            encrypted_blob = _encrypt_secrets(secrets)
                            _save_credentials(db, artist_id, 'meta', encrypted_blob,
                                              {f['key']: current.get(f['key'], '') for f in fields_def_meta if not f['secret']})
                            db.execute_query(
                                "UPDATE artist_credentials SET expires_at = %s WHERE artist_id = %s AND platform = 'meta'",
                                (new_expires.to_pydatetime(), artist_id)
                            )
                            st.success(f"✅ Token renouvelé — expire le {new_expires.strftime('%d/%m/%Y')} ({expires_in // 86400} jours)")
                            st.rerun()
                        else:
                            err = data.get('error', {})
                            st.error(f"Échec : {err.get('message', data)} — si le token est expiré, générer un nouveau token manuellement via Graph API Explorer.")
                    except Exception as e:
                        st.error(f"Erreur réseau : {e}")


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
