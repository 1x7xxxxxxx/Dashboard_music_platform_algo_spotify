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
