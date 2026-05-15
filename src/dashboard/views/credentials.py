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
from datetime import datetime

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin
from src.utils.config_loader import config_loader
from src.utils.meta_config import META_GRAPH_BASE_URL


# platform_key → DAG to auto-trigger when credentials are saved.
# CSV-driven sources (apple_music, imusician, s4a) are intentionally absent —
# they pull from filesystem watchers, not on-demand from saved tokens.
_PLATFORM_DAG_MAP = {
    'spotify': 'spotify_api_daily',
    'youtube': 'youtube_daily',
    'soundcloud': 'soundcloud_daily',
    'instagram': 'instagram_daily',
    'meta': 'meta_ads_api_daily',
}


# ─────────────────────────────────────────────
# Fernet helpers
# ─────────────────────────────────────────────

def _get_fernet():
    """Retourne un objet Fernet ou None si FERNET_KEY non configuré.

    Security: reads exclusively from os.environ — never from config.yaml on disk.
    config.yaml is a filesystem artifact; env vars are injected at runtime by
    Docker / the deployment platform and are not committed to the repo.
    """
    import os
    from cryptography.fernet import Fernet
    key = os.environ.get('FERNET_KEY', '')
    if not key:
        # Fallback: read from config.yaml for local dev only
        _cfg = config_loader.load()
        key = _cfg.get('fernet_key', '')
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
        # Collector uses client_credentials only (spotify_api.py) — no
        # redirect_uri / refresh_token needed (those were dormant + misleading).
        'fields': [
            {'key': 'client_id',     'label': 'Client ID',     'secret': False},
            {'key': 'client_secret', 'label': 'Client Secret', 'secret': True},
        ],
    },
    'youtube': {
        'label': '🎬 YouTube',
        # Collector uses a static Data-API key (youtube_collector.py
        # developerKey) + channel_id — NOT OAuth. The old client_id/
        # client_secret/refresh_token fields were dormant and made per-tenant
        # config impossible (no api_key field at all).
        'fields': [
            {'key': 'api_key',    'label': 'API Key (YouTube Data API v3)', 'secret': True},
            {'key': 'channel_id', 'label': 'Channel ID (UC…)',             'secret': False},
        ],
    },
    'soundcloud': {
        'label': '☁️ SoundCloud',
        'fields': [
            {'key': 'client_id',     'label': 'Client ID',                        'secret': False},
            {'key': 'client_secret', 'label': 'Client Secret',                    'secret': True},
            {'key': 'user_id',       'label': 'User ID numérique (ex: 123456789)', 'secret': False},
            # OAuth user-token path (optional): enables real per-track likes.
            # Leave empty to keep the client_credentials fallback.
            {'key': 'redirect_uri',  'label': 'Redirect URI (OAuth, optionnel)',  'secret': False,
             'default': 'http://localhost:8888/callback'},
            {'key': 'refresh_token', 'label': 'Refresh Token (OAuth, optionnel)', 'secret': True},
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


def _fetch_meta_token_expiry(token: str, app_id: str, app_secret: str) -> datetime | None:
    """Appelle /debug_token pour récupérer la vraie date d'expiration du token Meta.

    Non bloquant : retourne None si l'appel échoue (réseau, secrets manquants).
    """
    if not token or not app_id or not app_secret:
        return None
    try:
        r = requests.get(
            f"{META_GRAPH_BASE_URL}/debug_token",
            params={
                'input_token': token,
                'access_token': f"{app_id}|{app_secret}",
            },
            timeout=10,
            allow_redirects=False,
        )
        data = r.json().get('data', {})
        expires_at = data.get('expires_at')  # Unix timestamp, 0 = never-expiring System token
        if expires_at and expires_at > 0:
            return datetime.utcfromtimestamp(expires_at)
    except Exception:
        pass
    return None


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
            allow_redirects=False,  # INFO-04: prevent open-redirect SSRF
        )
        data = r.json()
        if r.status_code == 200 and data.get('access_token'):
            return True, "Token client_credentials obtenu ✅"
        return False, data.get('error_description', r.text[:150])
    except Exception as e:
        return False, str(e)


def _test_youtube(fields: dict) -> tuple:
    # Validate the Data-API key the collector actually uses (developerKey),
    # via a key-only endpoint (no channel needed). i18nLanguages is the
    # cheapest read that exercises the key.
    api_key = fields.get('api_key', '')
    if not api_key:
        return False, "API Key requise pour tester YouTube."
    try:
        r = requests.get(
            'https://www.googleapis.com/youtube/v3/i18nLanguages',
            params={'part': 'snippet', 'key': api_key},
            timeout=10,
            allow_redirects=False,  # INFO-04
        )
        data = r.json()
        if r.status_code == 200 and data.get('items'):
            return True, "Clé API valide ✅"
        err = data.get('error', {})
        return False, err.get('message', r.text[:150]) if isinstance(err, dict) else str(err)
    except Exception as e:
        return False, str(e)


def _test_soundcloud(fields: dict) -> tuple:
    """Test SoundCloud via OAuth 2.0 Client Credentials flow (official API)."""
    client_id     = fields.get('client_id', '').strip()
    client_secret = fields.get('client_secret', '').strip()
    user_id       = fields.get('user_id', '').strip()

    if not client_id:
        return False, "Client ID vide — créer une app sur soundcloud.com/you/apps."
    if not client_secret:
        return False, "Client Secret vide — disponible sur soundcloud.com/you/apps après création de l'app."
    if not user_id:
        return False, "User ID vide — ID numérique visible dans l'URL de ton profil SoundCloud."

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


def _test_meta(fields: dict) -> tuple:
    try:
        r = requests.get(
            f'{META_GRAPH_BASE_URL}/me',
            params={'access_token': fields.get('access_token', ''), 'fields': 'id,name'},
            timeout=10,
            allow_redirects=False,  # INFO-04
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


def _guide_meta():
    with st.expander("📱 Où trouver chaque champ Meta / Instagram ?", expanded=False):
        st.info(
            "Ce dashboard utilise un **System User token** — jamais de token personnel. "
            "Les tokens System User n'expirent pas (sauf révocation manuelle). "
            "Tous les artistes utilisent la même app Meta : **ETL_DASHBOARD_SPOTIFY** — "
            "ne crée pas ta propre app."
        )

        st.markdown("### Étapes — Meta Ads")
        st.markdown(
            "1. **Business Manager → Paramètres → Utilisateurs → Utilisateurs système** → "
            "Créer un utilisateur système (rôle Admin).\n"
            "2. Cliquer sur l'utilisateur → **Générer un nouveau token** → sélectionner "
            "**ETL_DASHBOARD_SPOTIFY** → cocher les scopes `ads_read` + `ads_management` → "
            "**Générer le token**. *(C'est le champ **Access Token**.)*\n"
            "3. **Paramètres → Comptes publicitaires** → relever l'ID numérique "
            "(ex : `123456789`). **Ne pas ajouter le préfixe `act_`** — le dashboard l'ajoute "
            "automatiquement. *(C'est le champ **Ad Account ID**.)*\n"
            "4. **Paramètres → Apps → ETL_DASHBOARD_SPOTIFY → Business Assets → "
            "Ajouter des assets → Compte publicitaire** → sélectionner ton compte → "
            "permission Annonceur. *(Obligatoire — sans ça l'API renvoie \"Object does not exist\".)*\n"
            "5. **App ID** et **App Secret** : contacte l'administrateur de la plateforme "
            "— ils sont pré-remplis par défaut."
        )

        st.markdown("### Étapes supplémentaires — Instagram")
        st.markdown(
            "Si tu veux les stats Instagram, utilise le **même token** mais génère-le avec "
            "les scopes additionnels : `instagram_basic` + `instagram_manage_insights` + `pages_show_list`.\n\n"
            "Le DAG `meta_token_refresh` (hebdo) ne tente **pas** de renouveler les System User tokens "
            "(ils n'expirent pas) — aucune action périodique requise."
        )

        st.markdown("### Instagram Business Account ID (optionnel)")
        st.code(
            "https://graph.facebook.com/v24.0/me/accounts?access_token=TON_TOKEN\n"
            "# → noter l'id de ta Page Facebook\n"
            "https://graph.facebook.com/v24.0/PAGE_ID?fields=instagram_business_account&access_token=TON_TOKEN\n"
            "# → instagram_business_account.id",
            language="text"
        )

        st.markdown(
            "| Champ | Source | Secret |\n"
            "|---|---|---|\n"
            "| **Access Token** | Business Manager → Utilisateurs système → Générer token | Oui |\n"
            "| **App Secret** | developers.facebook.com → ETL_DASHBOARD_SPOTIFY → Paramètres → Général | Oui |\n"
            "| **App ID** | Même page que App Secret | Non |\n"
            "| **Ad Account ID** | Business Manager → Comptes publicitaires (numérique uniquement, sans `act_`) | Non |\n"
            "| **Instagram Business Account ID** | Appel Graph API ci-dessus | Non |\n"
        )

        st.warning(
            "⚠️ **Erreurs fréquentes** : "
            "(1) Token personnel depuis Graph API Explorer → expire en 60 jours, utiliser System User. "
            "(2) Préfixe `act_` dans Ad Account ID → supprimer, le dashboard l'ajoute. "
            "(3) Scope `read_insights` uniquement → relancer avec `ads_read` + `ads_management`."
        )


def _guide_spotify():
    with st.expander("🎵 Comment obtenir les credentials Spotify ?", expanded=False):
        st.markdown(
            "1. Aller sur **[developers.spotify.com](https://developer.spotify.com/dashboard)** → Log in → **Create App**\n"
            "2. Renseigner un nom (la Redirect URI n'a pas d'importance ici)\n"
            "3. Copier le **Client ID** et le **Client Secret** → les coller ci-dessous\n"
        )
        st.info("Le collecteur utilise le flux **client_credentials** : pas de "
                "Redirect URI ni de Refresh Token à gérer, le token se "
                "renouvelle seul à chaque run.")


def _guide_youtube():
    with st.expander("🎬 Comment obtenir les credentials YouTube ?", expanded=False):
        st.markdown(
            "1. **[console.cloud.google.com](https://console.cloud.google.com)** → créer/choisir un projet\n"
            "2. **APIs & Services → Bibliothèque** → activer **YouTube Data API v3**\n"
            "3. **APIs & Services → Identifiants → Créer des identifiants → Clé API**\n"
            "4. (recommandé) Restreindre la clé à **YouTube Data API v3**\n"
            "5. Coller la clé dans **API Key** ci-dessous\n"
            "6. **Channel ID** : sur la chaîne YouTube → *Paramètres avancés* "
            "→ ID de chaîne (commence par `UC…`)\n"
        )
        st.info("Le collecteur utilise une **clé API statique** (pas d'OAuth) : "
                "la clé n'expire pas, aucun refresh à gérer.")


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

    # ── Formulaire standard (toutes plateformes) ─────────────────────
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
                            f'{META_GRAPH_BASE_URL}/oauth/access_token',
                            params={
                                'grant_type': 'fb_exchange_token',
                                'client_id': app_id,
                                'client_secret': app_secret,
                                'fb_exchange_token': access_token,
                            },
                            timeout=10,
                            allow_redirects=False,
                        )
                        data = r.json()
                        if r.status_code == 200 and data.get('access_token'):
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

        # Auto-populate expires_at for Meta tokens so the weekly refresh DAG
        # and proactive refresh in the collector can function without manual input.
        if platform_key == 'meta':
            expiry = _fetch_meta_token_expiry(
                secrets.get('access_token', ''),
                extra.get('app_id', ''),
                secrets.get('app_secret', ''),
            )
            if expiry:
                db.execute_query(
                    "UPDATE artist_credentials SET expires_at = %s "
                    "WHERE artist_id = %s AND platform = 'meta'",
                    (expiry, artist_id),
                )
            else:
                st.warning(
                    "⚠️ Impossible de récupérer la date d'expiration du token Meta "
                    "(app_id / app_secret manquants ou API inaccessible). "
                    "Le renouvellement automatique ne fonctionnera pas jusqu'au prochain save."
                )

        # Auto-trigger first data pull for this artist on this platform.
        # Non-blocking: a DAG-trigger failure must NOT invalidate the credential save.
        dag_id = _PLATFORM_DAG_MAP.get(platform_key)
        if dag_id:
            try:
                import os
                from src.utils.airflow_trigger import AirflowTrigger
                trigger = AirflowTrigger(
                    base_url=os.getenv('AIRFLOW_BASE_URL', 'http://localhost:8080'),
                    username=os.getenv('AIRFLOW_ADMIN_USERNAME', 'admin'),
                    password=os.environ['AIRFLOW_ADMIN_PASSWORD'],
                )
                result = trigger.trigger_dag(dag_id, conf={'artist_id': artist_id})
                if result.get('success'):
                    st.toast(f"🚀 Collecte {platform_key} lancée — données disponibles dans ~2 min", icon="✅")
            except Exception as trigger_err:
                st.warning(f"⚠️ Credentials enregistrés mais déclenchement DAG échoué : {trigger_err}")

        st.success(f"✅ Credentials {platform_key} enregistrés.")
        st.rerun()

    except Exception as e:
        st.error(f"❌ Erreur lors de la sauvegarde : {e}")
