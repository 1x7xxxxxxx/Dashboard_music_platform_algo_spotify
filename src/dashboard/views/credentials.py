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
            "- Si le DAG `soundcloud_daily` échoue à nouveau avec une erreur 401/403, recommencer ce process.\n"
            "- 📅 **Recommandé** : mettre un rappel calendrier tous les 2 mois."
        )


def _guide_meta():
    with st.expander("📱 Comment obtenir les credentials Meta / Instagram ?", expanded=False):
        st.info(
            "Meta utilise OAuth 2.0 avec des tokens à durée limitée. "
            "Le **Long-lived token** dure **60 jours** — prévoir un renouvellement mensuel."
        )

        st.markdown("### Étape 1 — Créer une app Meta")
        st.markdown(
            "1. Aller sur **[developers.facebook.com](https://developers.facebook.com)** → **Mes apps** → **Créer une app**\n"
            "2. Choisir le type : **Business** (obligatoire pour Marketing API)\n"
            "3. Donner un nom à l'app (ex: `Music Dashboard`)\n"
            "4. Dans le catalogue de produits, ajouter :\n"
            "   - **Marketing API** (pour Meta Ads)\n"
            "   - **Instagram Graph API** (pour les insights Instagram)\n"
        )

        st.markdown("### Étape 2 — Récupérer App ID et App Secret")
        st.markdown(
            "Dans ton app → **Paramètres → Paramètres de base** :\n"
            "- Copier l'**App ID** → champ `App ID` ci-dessous\n"
            "- Copier l'**App Secret** (cliquer sur Afficher) → champ `App Secret` ci-dessous\n"
        )

        st.markdown("### Étape 3 — Générer un Access Token")
        st.markdown(
            "1. Aller dans **Outils → [Graph API Explorer](https://developers.facebook.com/tools/explorer)**\n"
            "2. En haut à droite, sélectionner **ton app** dans le menu déroulant\n"
            "3. Cliquer sur **Generate Access Token** → autoriser avec ton compte Facebook\n"
            "4. Cocher les permissions suivantes :\n"
        )
        st.code(
            "ads_read\nads_management\ninstagram_basic\ninstagram_manage_insights\npages_read_engagement",
            language="text",
        )
        st.markdown("5. Cliquer **Generate Access Token** — tu obtiens un token à courte durée (1h).")

        st.markdown("### Étape 4 — Convertir en Long-lived token (60 jours)")
        st.markdown("Faire une requête GET avec les valeurs de ton app :")
        st.code(
            "GET https://graph.facebook.com/oauth/access_token"
            "?grant_type=fb_exchange_token"
            "&client_id={TON_APP_ID}"
            "&client_secret={TON_APP_SECRET}"
            "&fb_exchange_token={TOKEN_COURT_TERME}",
            language="text",
        )
        st.markdown(
            "Ou utiliser le **[Token Debugger](https://developers.facebook.com/tools/debug/)** → coller le token → "
            "cliquer **Extend Access Token** en bas de page.\n\n"
            "Copier le nouveau token → champ `Access Token` ci-dessous."
        )

        st.markdown("### Étape 5 — Récupérer l'Ad Account ID (Meta Ads)")
        st.markdown(
            "1. Aller sur **[Meta Ads Manager](https://adsmanager.facebook.com)**\n"
            "2. Menu en haut à gauche → **Paramètres → Paramètres du compte**\n"
            "3. Copier l'**Account ID** (ex: `123456789`)\n"
            "4. Ajouter le préfixe `act_` → format final : `act_123456789` → champ `Ad Account ID` ci-dessous\n"
        )

        st.markdown("### Étape 6 — Récupérer l'Instagram Business Account ID")
        st.info(
            "⚠️ Ce champ est **différent** de l'Ad Account ID. "
            "C'est un identifiant numérique spécifique à ton compte Instagram Business (ex: `17841400008460056`)."
        )
        st.markdown("Appeler cette URL dans le navigateur (remplacer le token) :")
        st.code(
            "https://graph.facebook.com/v18.0/me/accounts?access_token=TON_ACCESS_TOKEN",
            language="text",
        )
        st.markdown(
            "Cela retourne la liste de tes Pages Facebook. Pour chaque page, récupérer l'Instagram Business Account ID :"
        )
        st.code(
            "https://graph.facebook.com/v18.0/{PAGE_ID}?fields=instagram_business_account&access_token=TON_ACCESS_TOKEN",
            language="text",
        )
        st.markdown(
            "La réponse contient : `{\"instagram_business_account\": {\"id\": \"17841400008460056\"}}`. "
            "Copier cette valeur → champ **Instagram Business Account ID** ci-dessous."
        )

        st.warning(
            "⚠️ **Le Long-lived token expire dans 60 jours.** "
            "Répéter les étapes 3 et 4 chaque mois. "
            "📅 Recommandé : mettre un rappel calendrier à J+50."
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

        creds_icon = '🔑' if has_creds else '❌'
        creds_label = 'Credentials OK' if has_creds else 'Aucun credential'

        col.metric(
            label=platform_info['label'],
            value=f"{run_icon} {run_label}",
            delta=f"{creds_icon} {creds_label}",
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

        # SoundCloud: server-side test triggers bot detection — warn instead
        if platform_key == 'soundcloud':
            st.info(
                "⚠️ **Test automatique désactivé pour SoundCloud.** "
                "SoundCloud détecte les requêtes programmatiques et bloque l'IP temporairement. "
                "Pour valider les credentials, déclencher directement le DAG `soundcloud_daily` "
                "dans l'Airflow UI (http://localhost:8080) et vérifier les logs."
            )
        else:
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
