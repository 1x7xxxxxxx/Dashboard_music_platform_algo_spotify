"""Credentials — crypto + DB + Airflow-state core (no Streamlit).

Type: Sub
Uses: config_loader, cryptography.Fernet, requests, AirflowMonitor
Depends on: artist_credentials table
Persists in: artist_credentials (token_encrypted Fernet blob + extra_config JSONB)

Pure relocation from the former credentials.py — no logic change.
"""
import json
import requests
from datetime import datetime

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
# Platform → DAG status mapping
# ─────────────────────────────────────────────

# DAGs associated to each platform (used for last-run status KPI)
PLATFORM_TO_DAGS = {
    'spotify':    ['spotify_api_daily'],
    'youtube':    ['youtube_daily'],
    'soundcloud': ['soundcloud_daily'],
    'meta':       ['meta_ads_api_daily', 'instagram_daily'],
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
        # Single batch call for all DAGs' latest run (was N+1: one call per DAG).
        last_states = monitor.get_all_dags_last_state()
        result = {}
        for dag_id in all_ids:
            r = last_states.get(dag_id)
            if r:
                result[dag_id] = {
                    'state': r.get('state'),
                    'date': (r.get('start_date') or '')[:16] or '—',
                }
            else:
                result[dag_id] = {'state': None, 'date': '—'}
        return result
    except Exception:
        return {}


# ─────────────────────────────────────────────
# App-level (env / config.yaml) credential detection
# ─────────────────────────────────────────────

# Platforms whose credentials may live at the app level (env vars / config.yaml)
# instead of the per-artist artist_credentials table. The collector DAGs read
# these with a DB-then-env fallback (e.g. spotify_api_daily, youtube_daily), so
# the dashboard must NOT show '❌ Non configuré' when only the app-level path is
# wired. Each entry: (env_var_names, config.yaml section key).
_APP_LEVEL_CREDS = {
    'spotify': (('SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET'), 'spotify'),
    'youtube': (('YOUTUBE_API_KEY', 'YOUTUBE_CHANNEL_ID'), 'youtube'),
}

# Placeholder values shipped in config.example.yaml — never count as configured.
_CONFIG_PLACEHOLDER_PREFIX = 'VOTRE_'


def app_level_configured(platform_key: str) -> bool:
    """True if a platform is configured at the app level (env or config.yaml).

    Mirrors the DB-then-env fallback used by the collector DAGs so the
    credentials view reflects Spotify/YouTube as configured even when there is
    no artist_credentials row (their keys live in .env / config.yaml).
    """
    import os
    entry = _APP_LEVEL_CREDS.get(platform_key)
    if not entry:
        return False
    env_keys, cfg_section = entry
    if all(os.getenv(k) for k in env_keys):
        return True
    try:
        section = (config_loader.load() or {}).get(cfg_section) or {}
    except Exception:
        return False
    if not isinstance(section, dict):
        return bool(section)
    return any(
        v and not str(v).startswith(_CONFIG_PLACEHOLDER_PREFIX)
        for v in section.values()
    )


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


# Sentinel returned by _fetch_meta_token_expiry for never-expiring tokens.
META_TOKEN_NEVER_EXPIRES = "never"


def _fetch_meta_token_expiry(token: str, app_id: str, app_secret: str):
    """Appelle /debug_token pour récupérer la date d'expiration du token Meta.

    Non bloquant. Returns one of three states:
      - datetime                    → real expiry (personal long-lived token)
      - META_TOKEN_NEVER_EXPIRES    → never expires (System User token, expires_at==0)
      - None                        → could not determine (network / missing secrets)

    The caller must map META_TOKEN_NEVER_EXPIRES → set expires_at NULL (so the weekly
    refresh DAG skips it), NOT to a warning. Conflating "never expires" with "unknown"
    is what left a stale/false 60-day expiry on System User tokens.
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
        # System User tokens never expire: debug_token reports expires_at==0 and/or type.
        if data.get('type') == 'SYSTEM_USER' or expires_at == 0:
            return META_TOKEN_NEVER_EXPIRES
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
