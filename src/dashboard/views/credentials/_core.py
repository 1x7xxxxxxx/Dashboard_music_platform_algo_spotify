"""Credentials — crypto + DB + Airflow-state core (no Streamlit).

Type: Sub
Uses: config_loader, cryptography.Fernet, requests, AirflowMonitor
Depends on: artist_credentials table
Persists in: artist_credentials (token_encrypted Fernet blob + extra_config JSONB)

Pure relocation from the former credentials.py — no logic change.
"""
import json
import logging

from src.utils.config_loader import config_loader
from src.utils.tenant_identity import PLATFORM_IDENTITIES, storage_platform

logger = logging.getLogger(__name__)


# LOGICAL platform → DAG to auto-trigger when its identity is saved.
# CSV-driven sources (apple_music, imusician, s4a) are intentionally absent —
# they pull from filesystem watchers, not on-demand from saved tokens.
#
# Keyed on the logical platform, NOT on the form tab. Keyed on the tab, the
# `instagram` entry was unreachable by construction: `_handle_save` is only ever
# called with a key from `_registry.PLATFORMS`, which has four tabs, and
# `ig_user_id` is a FIELD of the meta tab. So saving an Instagram id triggered
# `meta_ads_api_daily` and never `instagram_daily` — the artist connected
# Instagram, waited, and no first pull ever ran.
_IDENTITY_DAG_MAP = {
    'spotify': 'spotify_api_daily',
    'youtube': 'youtube_daily',
    'soundcloud': 'soundcloud_daily',
    'instagram': 'instagram_daily',
    'meta': 'meta_ads_api_daily',
}


def dags_for_save(tab_key: str, extra: dict) -> list:
    """DAGs to trigger after saving `tab_key`, given the identities actually written.

    Pure. One tab can carry several logical identities (the Meta tab holds both the
    ad account and the Instagram business account), and each has its own DAG. An
    identity left blank triggers nothing: `_handle_save` pops empty values, so an
    untouched tab must not kick off a collection that has no id to collect for.
    """
    from src.utils.tenant_identity import PLATFORM_IDENTITIES

    out = []
    for logical, spec in PLATFORM_IDENTITIES.items():
        if spec.storage != tab_key:
            continue
        if not str((extra or {}).get(spec.field) or "").strip():
            continue
        dag = _IDENTITY_DAG_MAP.get(logical)
        if dag and dag not in out:
            out.append(dag)
    return out


# ─────────────────────────────────────────────
# Fernet helpers
# ─────────────────────────────────────────────

def _get_fernet():
    """Retourne un objet Fernet ou None si FERNET_KEY non configuré.

    Security: env FIRST, then config.yaml as a LOCAL-DEV fallback.

    This docstring used to claim "never from config.yaml on disk" while the code
    four lines down read it. Prod has no config.yaml, so the fallback is dead there
    and the claim was true of the deployment and false of the function — which is
    the worst kind of comment, because it is checked by nobody and believed by
    everybody. The fallback stays (local dev needs it); the sentence is now the one
    the code implements.
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


def fernet_state() -> str:
    """Why encryption is unavailable, when it is: 'ok' | 'absent' | 'malformed'.

    `_get_fernet()` returns None for two situations that need different gestures —
    no key at all, and a key that is present but not a valid Fernet key (truncated
    on a copy-paste, wrong encoding, a placeholder left in config.yaml). The banner
    said "clé absente" for both, sending someone to generate a second key when the
    real fix was to repair the one already there.
    """
    import os
    from cryptography.fernet import Fernet
    key = os.environ.get('FERNET_KEY', '')
    if not key:
        try:
            key = (config_loader.load() or {}).get('fernet_key', '')
        except Exception:  # noqa: BLE001 — no config file is "absent", not an error
            key = ''
    if not key:
        return 'absent'
    try:
        Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:  # noqa: BLE001
        return 'malformed'
    return 'ok'


def fernet_key_command_block(root=None) -> tuple:
    """`(language, block)` — the lines to paste to generate a Fernet key HERE.

    The bare `python -c "from cryptography.fernet import Fernet; ..."` the banner used
    to print is not runnable as written: the only interpreter carrying `cryptography`
    is the one inside `venv/`. The activation prelude — and the reason PowerShell needs
    `-Scope Process` first — lives in `utils.shell_block`, which is the single builder
    for every command this app prints. A second copy diverges.
    """
    from src.dashboard.utils.shell_block import command_block
    return command_block(
        'python -c "from cryptography.fernet import Fernet; '
        'print(Fernet.generate_key().decode())"',
        root,
    )


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


def extract_spotify_artist_id(value: str) -> str:
    """Normalise a Spotify artist reference to its bare base-62 ID.

    Accepts the raw ID, a profile URL (open.spotify.com/artist/<id>?...) or a URI
    (spotify:artist:<id>). Returns '' if nothing usable is found.
    """
    import re
    v = (value or '').strip()
    if not v:
        return ''
    m = re.search(r'(?:artist[:/])([0-9A-Za-z]{22})', v)
    if m:
        return m.group(1)
    return v if re.fullmatch(r'[0-9A-Za-z]{22}', v) else v


def _mask(value: str, visible: int = 6) -> str:
    if not value or len(value) <= visible:
        return '***'
    return value[:visible] + '…***'


# ─────────────────────────────────────────────
# Platform → DAG status mapping
# ─────────────────────────────────────────────

# Form tab → the DAGs that feed it (used for the last-run status KPI). DERIVED from
# `_IDENTITY_DAG_MAP` so a third copy of the platform→DAG mapping cannot appear; the
# meta tab gets both its own DAG and Instagram's because it carries both identities.
def _platform_to_dags() -> dict:
    from src.utils.tenant_identity import PLATFORM_IDENTITIES

    out: dict = {}
    for logical, spec in PLATFORM_IDENTITIES.items():
        dag = _IDENTITY_DAG_MAP.get(logical)
        if dag:
            out.setdefault(spec.storage, []).append(dag)
    return out


PLATFORM_TO_DAGS = _platform_to_dags()

_STATE_ICON = {
    'success': '🟢',
    'failed':  '🔴',
    'running': '🔵',
    'queued':  '🟡',
    None:      '⚫',
}


def artist_display_name(db, artist_id: int | None) -> str | None:
    """This tenant's artist name, or None — used only to aim a portal link.

    Never raises and never falls back to another tenant: a name that cannot be read
    simply means the generic portal link is shown, which is what every artist saw
    before. `saas_artists.id` IS the tenant here (the VARCHAR `artist_id` of the
    `artists` table is a Spotify id, a different thing entirely).
    """
    if db is None or artist_id is None:
        return None
    try:
        rows = db.fetch_query("SELECT name FROM saas_artists WHERE id = %s", (artist_id,))
    except Exception as exc:            # noqa: BLE001 — cosmetic read, never fatal
        logger.warning("artist_display_name: %s", exc)
        return None
    return rows[0][0] if rows and rows[0][0] else None

def _fetch_dag_last_states() -> dict:
    """Returns {dag_id: {state, date}} for all platform DAGs. Non-blocking on failure."""
    try:
        from src.dashboard.utils.airflow_monitor import cached_last_run_per_dag
        all_ids = {d for dags in PLATFORM_TO_DAGS.values() for d in dags}
        # One request per DAG, issued concurrently, behind a 60 s cache — this page
        # re-runs on every widget interaction and the fetch costs 16 HTTP round-trips.
        last_states = cached_last_run_per_dag()
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
    'spotify':    (('SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET'), 'spotify'),
    'youtube':    (('YOUTUBE_API_KEY',), 'youtube'),
    'soundcloud': (('SOUNDCLOUD_CLIENT_ID', 'SOUNDCLOUD_CLIENT_SECRET'), 'soundcloud'),
    'meta':       (('META_ACCESS_TOKEN',), 'meta'),
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
    """Upsert one platform row. An EMPTY blob means "leave the secret alone".

    P1 fixed 2026-08-22. `token_encrypted = EXCLUDED.token_encrypted` was an
    overwrite, and `_render._handle_save` computes `encrypted_blob = ''` whenever no
    SECRET field on the tab holds a value. Two tabs declare no secret field at all —
    `soundcloud` (only `user_id`) and `meta` (only `account_id` + `ig_user_id`) — yet
    both rows carry a blob in production:

      * `soundcloud` holds the rotated OAuth `refresh_token` written by
        `soundcloud_api_collector.py:132` (228 bytes on artist 1). Without it the
        collector silently falls back to client_credentials and every like reads 0.
      * `meta` holds the System User token injected by `tools/dev/inject_meta_token.py`
        (804 bytes on artist 1) — the credential EVERY tenant's Meta and Instagram
        collection depends on.

    So pressing "Enregistrer" on the Meta tab, changing nothing, destroyed the
    platform's shared token. No error, no warning, and the DAG stayed green the next
    night because a missing token skips tenants rather than failing.

    `NULLIF(…, '')` + `COALESCE` makes the empty string mean "keep what is there".
    Erasing a secret is then something a caller has to ask for deliberately, which is
    the right shape: a form that cannot DISPLAY a secret must not be able to DELETE
    it as a side effect of saving something else.
    """
    db.execute_query(
        """
        INSERT INTO artist_credentials
            (artist_id, platform, token_encrypted, extra_config, updated_at)
        VALUES (%s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (artist_id, platform)
        DO UPDATE SET
            token_encrypted = COALESCE(
                NULLIF(EXCLUDED.token_encrypted, ''),
                artist_credentials.token_encrypted
            ),
            extra_config    = EXCLUDED.extra_config,
            updated_at      = NOW()
        """,
        (artist_id, platform, encrypted_blob, json.dumps(extra))
    )


# _fetch_meta_token_expiry and META_TOKEN_NEVER_EXPIRES were removed 2026-08-22.
#
# Their only caller passed them the tenant's saved access_token / app_id /
# app_secret — three fields the meta tab does not declare — so the function
# returned None on its first guard every single time, and the caller rendered a
# permanent warning from it. Under ADR-006 the Meta token is a central APP
# credential and a System User token that never expires; its expiry belongs to
# src/utils/central_apps.py::check_meta, which already calls /debug_token with the
# app credentials and is read nightly by alert_monitor.


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

    # `extra_account_ids` est DÉRIVÉ, jamais stocké : la liste canonique est
    # `account_ids`, dont le premier élément est le champ principal. Stocker le
    # champ de saisie en plus de la liste ferait deux états à garder d'accord, et
    # celui qu'on ne relit pas est toujours celui qui se désynchronise.
    if 'extra_account_ids' in {f['key'] for f in fields}:
        from src.utils.tenant_identity import meta_ad_account_ids
        result['extra_account_ids'] = "\n".join(meta_ad_account_ids(extra)[1:])
    return result

# Identity fields whose value must belong to exactly ONE tenant. Two artists
# claiming the same platform account is not a configuration nuance: the collectors
# would write the same upstream data under two artist_ids, and `spotify_api_daily`
# cannot even decide whose catalogue it is (it refuses and logs both ids).
# DERIVED from `src/utils/tenant_identity.PLATFORM_IDENTITIES`, never restated.
#
# Restated, this map had FOUR entries while the registry had five: `instagram` was
# missing, so `find_identity_conflict` below returned None for it and two tenants
# could claim the same Instagram Business Account in silence — the exact collision
# this function exists to refuse. `tools/create_canary.py` carried the same amputated
# copy, so the canary could not exercise Instagram either.
#
# What kept it invisible is worth more than the omission: `tests/test_create_canary`
# asserted the tool EQUALLED this map, so a green guard held the gap in place; and
# `tests/test_identity_uniqueness` parametrised over this map, so the missing entry
# removed test cases instead of failing one. A registry its own guards derive from
# cannot report its own omission.
UNIQUE_IDENTITY_FIELDS = {k: v.field for k, v in PLATFORM_IDENTITIES.items()}


def sandbox_tenant_ids(db) -> set[int]:
    """Tenants the operator runs to rehearse the journey. Never raises.

    A read that fails must NOT be read as "there are no sandboxes" in a way that
    weakens the guard — and it cannot, because the caller only ever uses this set to
    IGNORE conflicts. An empty set on failure means the guard stays fully enforced,
    which is the safe direction.
    """
    try:
        rows = db.fetch_query(
            "SELECT id FROM saas_artists WHERE COALESCE(is_sandbox, FALSE)")
    except Exception as exc:            # noqa: BLE001 — fail towards the strict side
        logger.warning("sandbox_tenant_ids: %s", type(exc).__name__)
        return set()
    return {r[0] for r in rows}


def find_identity_conflict(db, artist_id: int, platform: str, extra: dict):
    """Another active tenant already claiming this identity, or None.

    Returns (field, value, other_artist_id). Checked at SAVE time because that is
    the only moment a human is present to fix it; discovering it at collection
    time means someone's dashboard is already wrong.

    Sandbox tenants (migration 080) are exempt in BOTH directions, and both halves
    are needed:

      * a sandbox is never blocked — that is the whole point: the operator replays
        the onboarding with their OWN platform identity, which a real tenant of
        theirs already holds;
      * a sandbox never blocks anyone — otherwise a rehearsal left lying around
        would refuse a real artist their own identifier, which is worse than the
        problem it was created to explore.

    The canary is NOT exempt: it uses public artist ids and an accidental collision
    there is a real defect, not an intended rehearsal.
    """
    sandboxes = sandbox_tenant_ids(db)
    if artist_id in sandboxes:
        return None
    field = UNIQUE_IDENTITY_FIELDS.get(platform)
    if not field:
        return None

    if platform == 'meta':
        # Même exemption, appliquée dans la fonction dédiée : le chemin Meta ne
        # repasse pas par le filtre ci-dessous.
        # Meta est la seule identité PLURIELLE (R53 / ADR-013 : un artiste passant
        # par une agence a N comptes publicitaires). Comparer le seul scalaire
        # `account_id` rouvrirait exactement le trou que cette fonction ferme : le
        # DEUXIÈME compte d'un artiste n'apparaît dans le scalaire de personne, donc
        # un autre locataire pourrait le revendiquer comme son premier — deux
        # tableaux de bord sur les mêmes dépenses, en silence.
        return _find_meta_account_conflict(db, artist_id, extra, sandboxes)

    value = (extra.get(field) or '').strip()
    if not value:
        return None

    rows = db.fetch_query(
        "SELECT artist_id FROM artist_credentials "
        "WHERE platform = %s AND artist_id <> %s AND extra_config->>%s = %s",
        # STORAGE platform: Instagram's identity lives in the `meta` row, so
        # searching platform='instagram' would scan rows that never exist and
        # therefore always report "no conflict".
        (storage_platform(platform), artist_id, field, value),
    )
    # Le filtre bac à sable s'applique AVANT de décider s'il faut consulter le
    # miroir, et c'est la correction du 2026-09-04.
    #
    # Il vivait après le repli `if not rows`, donc une ligne de bac à sable rendait
    # `rows` non vide, le miroir `saas_artists` n'était jamais interrogé, et le filtre
    # vidait ensuite la liste : la fonction répondait « aucun conflit » alors que deux
    # VRAIS locataires se disputaient l'identifiant. Le bac à sable ne bloquait
    # personne — ce qui est voulu — mais il rendait aussi AVEUGLE au conflit des
    # autres, ce qui ne l'est pas : il détient par construction les identifiants de
    # l'admin, donc il masquait précisément les collisions les plus probables.
    #
    # Trouvé en rejouant l'onboarding sur le locataire bac à sable : le test
    # `test_spotify_conflict_is_seen_through_saas_artists` est passé au rouge à
    # l'exécution suivante, sur une base où une répétition avait laissé sa ligne.
    # C'est la classe « la portée d'un garde est le défaut », appliquée à l'ORDRE
    # des opérations : le prédicat était juste, sa place ne l'était pas.
    rows = [r for r in rows if r[0] not in sandboxes]
    if not rows and platform == 'spotify':
        # Spotify's identity is mirrored onto saas_artists — check there too.
        rows = db.fetch_query(
            "SELECT id FROM saas_artists WHERE id <> %s AND spotify_artist_id = %s",
            (artist_id, value),
        )
        rows = [r for r in rows if r[0] not in sandboxes]
    if rows:
        # The third element is the tenant that already holds this identifier. It is
        # returned on purpose — an admin resolving a duplicate claim needs to know
        # who to ask — and `tests/test_identity_uniqueness.py` pins that.
        #
        # It must NEVER reach the page. The 2026-08-22 pentest listed this line as
        # "displays the other tenant's artist_id"; re-read on the same day, the one
        # caller (`_render.py`) discards it and shows only the field and the value.
        # So the finding named a value that is available rather than one that leaks,
        # and the fix is to keep the boundary where it is and TEST it, not to delete
        # a return value someone deliberately asked for.
        # Guard: tests/test_identity_conflict_names_no_other_tenant.py
        return field, value, rows[0][0]
    return None


def _find_meta_account_conflict(db, artist_id: int, extra: dict,
                                sandboxes: set[int] | None = None):
    """(field, value, other_artist_id) si un autre locataire tient l'un des comptes.

    Compare CHAQUE compte déclaré contre le scalaire `account_id` ET la liste
    `account_ids` de tous les autres locataires. Les deux formes de saisie sont
    testées (`act_123` et `123`) : la normalisation est faite à l'écriture depuis
    2026-08-24, mais les lignes écrites avant portent ce que l'artiste avait tapé,
    et une comparaison qui rate à cause d'un préfixe est un conflit non détecté.
    """
    from src.utils.tenant_identity import meta_ad_account_ids

    accounts = meta_ad_account_ids(extra)
    if not accounts:
        return None
    variants = []
    for acct in accounts:
        variants.append(acct)
        variants.append(acct[len('act_'):])

    rows = db.fetch_query(
        "SELECT artist_id, COALESCE("
        "  (SELECT e.value FROM jsonb_array_elements_text("
        "     CASE WHEN jsonb_typeof(extra_config->'account_ids') = 'array' "
        "          THEN extra_config->'account_ids' ELSE '[]'::jsonb END) e "
        "   WHERE e.value = ANY(%s) LIMIT 1), "
        "  extra_config->>'account_id') AS taken "
        "FROM artist_credentials "
        "WHERE platform = 'meta' AND artist_id <> %s AND ("
        "  extra_config->>'account_id' = ANY(%s) "
        "  OR EXISTS (SELECT 1 FROM jsonb_array_elements_text("
        "       CASE WHEN jsonb_typeof(extra_config->'account_ids') = 'array' "
        "            THEN extra_config->'account_ids' ELSE '[]'::jsonb END) e2 "
        "     WHERE e2.value = ANY(%s)))",
        (variants, artist_id, variants, variants),
    )
    # Le même filtre bac à sable que le chemin scalaire : sans lui, Meta serait la
    # seule plateforme où une répétition bloquerait un vrai artiste.
    sandboxes = sandboxes or set()

    def _owner(r):
        return r[0] if isinstance(r, (tuple, list)) else r['artist_id']

    rows = [r for r in rows if _owner(r) not in sandboxes]
    if not rows:
        return None
    row = rows[0]
    other, taken = (row[0], row[1]) if isinstance(row, (tuple, list)) else (
        row['artist_id'], row['taken'])
    return ('account_id', taken, other)
