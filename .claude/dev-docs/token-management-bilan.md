# Token-management bilan — per platform, with the no-manual-action criterion

Consolidated assessment of auth/token/refresh for every platform that holds a
token, grounded in the code (file:line). Companion to
`meta-ads-credential-guide.md` (Meta setup steps) and
`soundcloud-oauth-guide.md` (SoundCloud mint runbook); this doc is the
cross-platform overview + the explicit **admin vs end-user manual-action**
answer.

## Headline — the manual-action criterion

- **Recurring manual action: NONE on any platform** once set up. Every
  expiring token is auto-refreshed; non-expiring ones never need it.
- **Admin one-time setup: required on every platform** (register the app /
  create the API key / create the System User + paste the global
  credentials). Unavoidable, platform-level, done **once** — not recurring.
- **End-user (artist) action**: a one-time credential paste only — and
  **zero** for Meta (shared admin app) and SoundCloud's default mode. The
  *only* genuine end-user OAuth dance is the optional SoundCloud user-token
  (one-time mint), after which it is fully automatic.

So: for the end user, steady-state operation requires **no token action at
all**. For the admin, only the initial per-platform onboarding + incident
response (a revoked/rotated secret), never a routine refresh.

## Per-platform matrix

| Platform / mode | Token type | Refresh mechanism | Admin one-time | End-user (artist) | Recurring manual? | Failure mode |
|---|---|---|---|---|---|---|
| **Spotify** | `client_credentials` access token (~1 h) | Re-granted every run by Spotipy `SpotifyClientCredentials` — `src/collectors/spotify_api.py:32-40` | Register app on developers.spotify.com → `client_id`/`client_secret` | Paste `client_id`/`client_secret` once (or admin via env) | **None** | Stale/rotated `client_secret` → auth 401 → re-paste in dashboard |
| **YouTube** | Static **API key** (`developerKey`), no expiry — `src/collectors/youtube_collector.py:14-22` | N/A — API keys do not expire | Create API key in Google Cloud Console | Save `api_key` once (or admin via `YOUTUBE_API_KEY` env) | **None** | Revoked key / quota exhausted → 403 → update key |
| **SoundCloud — default** | App-only `client_credentials` (~1 h) — `src/collectors/soundcloud_api_collector.py:70-89` | Auto on each `_ensure_token()` per DAG run | Register app on soundcloud.com/you/apps → `client_id`/`client_secret` | `user_id` once | **None** | Graceful: stays in this mode; **likes = 0** (SoundCloud API limitation for third-party app-only reads) |
| **SoundCloud — user-token** (optional, real likes) | OAuth `refresh_token` → user-context token — `_get_user_token` `:91-134` | Auto-rotate **and persist** every run via `update_platform_secret` (`:121-133`) | Same app registration | **One-time**: mint with `tools/dev/soundcloud_oauth_authorize.py` → run `debug_soundcloud_oauth.py` GO/NO-GO → paste the printed token into Dashboard → Credentials → SoundCloud | **None** (fully automatic after the one-time mint) | Rotation-persist fails if `FERNET_KEY` absent → next run 401 → re-mint. SoundCloud app registration closed for new apps (existing app OK) |
| **Meta / Instagram — System User** (recommended) | Long-lived token, **never expires** (`expires_at = NULL`) | N/A — `meta_token_refresh` DAG skips `expires_at IS NULL` (`airflow/dags/meta_token_refresh.py:104-109`); collector proactive check also skips NULL (`src/collectors/instagram_api_collector.py:120`) | Create System User in Business Manager, generate token with 5 scopes (`ads_read`, `ads_management`, `instagram_basic`, `instagram_manage_insights`, `pages_show_list`), link the ad account to the shared `ETL_DASHBOARD_SPOTIFY` app, paste token | **None** — the app is shared/admin-level, the artist does nothing | **None** | Only if **manually revoked** in Business Manager → admin regenerates. No auto-expiry |
| **Meta / Instagram — personal 60-day** (legacy, not recommended) | Rolling 60-day user token | **Double** auto-refresh: `meta_token_refresh` DAG Mondays 07:00 UTC when ≤30 days left (`:115-151`) **+** Instagram collector proactive refresh when ≤15 days left (`instagram_api_collector.py:107-131`); both persist via `update_platform_secret` | App + initial token | Paste token once | **None** (two independent refresh paths cover the 60-day window ~8×) | Both refresh paths fail for 30+ consecutive days → 401 → re-paste |

## Shared persistence layer

`src/utils/credential_loader.py`:
- `load_platform_credentials(artist_id, platform)` → decrypts
  `token_encrypted` (Fernet, **requires `FERNET_KEY`**) merged over
  `extra_config`; returns `{}` (silent) if absent/undecryptable.
- `update_platform_secret(...)` → re-encrypts a single secret in place;
  **no-op + warning if `FERNET_KEY` is absent** (rotation would silently not
  persist → next run uses the spent token).

`FERNET_KEY` presence in the **Airflow** container is the single point that
makes every auto-rotation actually persist. Verified SET (SoundCloud
user-token rotation worked end-to-end on 2026-05-15).

## Known findings (documented, intentionally not fixed here — bilan only)

1. **YouTube credentials UI ⇄ collector mismatch**: `credentials.py`
   `PLATFORM_FIELDS['youtube']` exposes OAuth fields
   (`client_id`/`client_secret`/`refresh_token`) but the collector uses a
   **static API key** (`developerKey`) only — the OAuth fields are dormant.
   Not a runtime bug (API key path works), but misleading UI. Candidate
   `/sweep` class: *"credentials UI field unused by the collector"*.
2. **Spotify `refresh_token` field** is similarly defined in the UI but
   unused (client_credentials only). Harmless, dormant.
3. **Edge (non-routine) risk points** — not steady-state manual action, but
   the only ways a token needs human touch:
   - Meta System User token **manually revoked** in Business Manager.
   - SoundCloud rotation-persist failing because `FERNET_KEY` was lost/rotated
     (then re-mint via the guide).
   - Any platform secret rotation (incident-driven) per
     `roadmap/checklist.md` § "Standing ops".

## Bottom line

Steady state = **no token action for the artist, none recurring for the
admin**. The admin's only obligations are the one-time per-platform
onboarding and incident response to a revoked/rotated upstream secret.
SoundCloud user-token is the lone exception requiring a single end-user
OAuth mint (then automatic forever). Meta is the cleanest (System User =
never expires, artist does nothing). Spotify/YouTube are stateless
(re-grant / non-expiring key) so they cannot drift.
