# SoundCloud OAuth — minting the `refresh_token` (real per-track likes)

## Why

`client_credentials` (app-only) tokens return `likes_count = 0` for
third-party reads — only ~public tracks show likes. A **user-context token**
(OAuth `authorization_code`) returns real per-track likes for the owner's own
tracks. The dual-mode collector (B2 P2) is already shipped & dormant: give it
a `refresh_token` and it switches automatically (else it stays on
`client_credentials`, unchanged).

The collector/spike/dashboard all *consume* a `refresh_token`. Minting the
**first** one is a one-time browser step — that's what
`tools/dev/soundcloud_oauth_authorize.py` does. After that the collector
auto-rotates & re-persists it every run (`update_platform_secret`).

## Prerequisites

- A SoundCloud app you already registered (https://soundcloud.com/you/apps) →
  you have `client_id` + `client_secret`. (App registration is closed for
  *new* apps — not a problem since yours exists.)
- The app's **Redirect URI must exactly include** the one you pass to the
  script. Default: `http://localhost:8888/callback`. If your app registered a
  different URI, pass `--redirect-uri "<exactly what you registered>"` — an
  inexact match makes the token exchange 400.
- Your numeric SoundCloud **User ID** (for the spike) — see the in-app
  Credentials → SoundCloud help (`_guide_soundcloud`).

## Step 1 — mint the refresh_token

```bash
python tools/dev/soundcloud_oauth_authorize.py \
  --client-id "<client_id>" --client-secret "<client_secret>"
# or set SOUNDCLOUD_CLIENT_ID / SOUNDCLOUD_CLIENT_SECRET and run with no args
# non-default callback:  --redirect-uri "http://localhost:9000/cb"
```

It opens the SoundCloud authorize page (also prints the URL — on WSL2
copy-paste into your Windows browser), captures the redirect on a local
one-shot server, exchanges the code (PKCE), and prints the `refresh_token`
plus a ready-to-run spike command.

If the token exchange 400s on the host, retry with
`--authorize-url https://api.soundcloud.com/connect` (SoundCloud's authorize
host has varied across API versions; the token endpoint is fixed to
`https://api.soundcloud.com/oauth2/token` to match the collector).

## Step 2 — GO / NO-GO

Run the printed command (it sets the 4 env vars and runs
`airflow/debug_dag/debug_soundcloud_oauth.py`):

- `✅ GO` → a track has `likes_count > 0` via the user token → proceed.
- `❌ NO-GO` → the user token still returns 0 (account/app limitation). Do
  **not** store it; likes stay partial. Nothing else changes.

## Step 3 — store it (only if GO)

Dashboard → **Credentials → SoundCloud** → paste into **"Refresh Token
(OAuth, optionnel)"** (and `redirect_uri` if you used a non-default one).
Stored Fernet-encrypted (`refresh_token` is a secret field). The collector
picks it up on the next run (DB cred or `SOUNDCLOUD_REFRESH_TOKEN` env).

## Step 4 — verify

Trigger `soundcloud_daily` (Airflow UI), then:

```sql
SELECT COUNT(*) FILTER (WHERE likes_count > 0)
FROM soundcloud_tracks_daily
WHERE collected_at::date = CURRENT_DATE;
```

Should rise well above the ~17/119 baseline once the user token is active.

## What is automated vs manual

| Step | Who |
|---|---|
| Mint first refresh_token (auth-code + PKCE) | **manual, one-time** — this script |
| GO/NO-GO feasibility check | manual — `debug_soundcloud_oauth.py` |
| Store token | manual — paste into dashboard (Fernet) |
| Per-run token refresh (`grant_type=refresh_token`) | **automatic** — collector `_get_user_token` |
| refresh_token rotation persistence | **automatic** — `update_platform_secret` |

## Risks

- **Authorize-host instability**: if SoundCloud changes the authorize host,
  use `--authorize-url`. The token host is pinned to match the collector.
- **Redirect URI exact-match**: must equal a URI registered on the app, char
  for char (scheme, host, port, path) — the #1 cause of a 400.
- **NO-GO is possible**: a user token does not guarantee non-zero likes for
  every account; the spike is the gate — believe its verdict, don't force it.
- The script never writes to the DB or repo — it only prints. Storing stays
  an explicit human step behind the GO gate.
