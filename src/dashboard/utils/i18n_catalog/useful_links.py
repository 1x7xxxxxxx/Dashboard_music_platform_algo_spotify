"""EN catalog for the useful_links view."""

EN = {
    # Access gate + header
    "useful_links.access_denied": "⛔ Administrator access only.",
    "useful_links.title": "🔧 Links & Tools",
    "useful_links.caption": "Operational reference — all links and commands to run the platform.",
    # Tabs
    "useful_links.tab_external": "🌐 External Links",
    "useful_links.tab_local": "🏠 Local Tools",
    "useful_links.tab_docker": "🐳 Docker & Infra",
    "useful_links.tab_credentials": "🔑 Credentials Guide",
    "useful_links.tab_debug": "🐛 Debug & Scripts",
    # Shared widget labels
    "useful_links.open_btn": "Open →",
    # TAB 1 — external links section headers
    "useful_links.sec_meta": "Meta / Instagram / Facebook",
    "useful_links.sec_spotify": "Spotify",
    "useful_links.sec_soundcloud": "SoundCloud",
    "useful_links.sec_youtube": "YouTube / Google",
    "useful_links.sec_apple": "Apple Music",
    "useful_links.sec_imusician": "iMusician",
    "useful_links.sec_hypeddit": "Hypeddit",
    # TAB 1 — link notes
    "useful_links.note_graph_explorer": "Generate an Instagram access token",
    "useful_links.note_token_debugger": "Check expiry + extend the token ('Extend Access Token' button)",
    "useful_links.note_fb_app_settings": "App ID + App Secret",
    "useful_links.note_business_manager": "Ad accounts, pages",
    "useful_links.note_ads_manager": "Campaigns, ad sets, performance",
    "useful_links.note_spotify_dev": "Client ID + Client Secret",
    "useful_links.note_s4a": "CSV export (streams, audience, songs)",
    "useful_links.note_spotify_api": "Endpoints, scopes, rate limits",
    "useful_links.note_sc_dev_apps": "Client ID (if developer access is active)",
    "useful_links.note_sc_inspect": "Inspect client_id via DevTools F12 → Network → filter 'client_id='",
    "useful_links.note_gcp_creds": "OAuth 2.0 Client IDs, API Keys",
    "useful_links.note_yt_studio": "Analytics, data export",
    "useful_links.note_yt_api": "Enable/disable the API",
    "useful_links.note_apple_a4a": "Songs Performance CSV export",
    "useful_links.note_imusician": "Monthly revenue to enter manually in the dashboard",
    "useful_links.note_hypeddit": "Campaigns CSV export",
    # TAB 2 — local tools
    "useful_links.sec_local_services": "Local services",
    "useful_links.airflow_open_btn": "Open Airflow →",
    "useful_links.airflow_login": "Login: admin / admin (default)",
    "useful_links.dashboard_open_btn": "Open Dashboard →",
    "useful_links.dashboard_caption": "This dashboard — `streamlit run src/dashboard/app.py`",
    "useful_links.api_caption": "Brick 14 — `uvicorn src.api.main:app --reload --port 8502`",
    "useful_links.redoc_caption": "Alternative documentation (readable)",
    "useful_links.sec_postgres": "PostgreSQL",
    "useful_links.pg_table": """
| Parameter | Value |
|---|---|
| Host (from WSL) | `localhost` |
| Port | `5433` |
| Database | `spotify_etl` |
| User | `postgres` |
| Password | see `config/config.yaml` |
""",
    "useful_links.cmd_psql_connect": "Direct psql connection",
    "useful_links.sec_airflow_dags": "Airflow — Quick access to DAGs",
    "useful_links.grid_btn": "Grid →",
    "useful_links.dag_spotify_api_daily": "Spotify API daily",
    "useful_links.dag_youtube_daily": "YouTube daily",
    "useful_links.dag_soundcloud_daily": "SoundCloud daily",
    "useful_links.dag_instagram_daily": "Instagram daily",
    "useful_links.dag_s4a_csv_watcher": "Spotify for Artists CSV",
    "useful_links.dag_apple_music_csv_watcher": "Apple Music CSV",
    "useful_links.dag_meta_ads_api_daily": "Meta Ads API",
    "useful_links.dag_ml_scoring_daily": "ML Scoring daily",
    "useful_links.dag_data_quality_check": "Data quality",
    # TAB 3 — docker & infra
    "useful_links.sec_start_stop": "Start & stop",
    "useful_links.cmd_start_all": "Start all services",
    "useful_links.cmd_stop_all": "Stop all services",
    "useful_links.cmd_rebuild_all": "Rebuild after requirements.txt or Dockerfile change",
    "useful_links.cmd_rebuild_one": "Rebuild a single service",
    "useful_links.sec_logs": "Logs",
    "useful_links.cmd_logs_scheduler": "Scheduler logs (DAG errors, imports)",
    "useful_links.cmd_logs_webserver": "Webserver logs (UI)",
    "useful_links.cmd_logs_postgres": "PostgreSQL logs",
    "useful_links.cmd_logs_tail": "Last 100 scheduler lines",
    "useful_links.cmd_logs_wsl": "Logs via docker.exe (WSL2)",
    "useful_links.sec_containers": "Container state",
    "useful_links.cmd_list_containers": "List running containers",
    "useful_links.cmd_stats": "Resource stats (CPU/RAM)",
    "useful_links.sec_database": "Database",
    "useful_links.cmd_run_sql": "Run a SQL script on spotify_etl",
    "useful_links.cmd_list_tables": "List all tables",
    "useful_links.cmd_check_rows": "Check a table's rows",
    "useful_links.cmd_backup": "Backup DB",
    "useful_links.sec_volumes": "Volumes & reset",
    "useful_links.cmd_list_volumes": "Show Docker volumes",
    "useful_links.warn_reset": "⚠️ The command below deletes ALL data in the DB — irreversible.",
    "useful_links.cmd_reset": "Full DB reset (DANGER)",
    # TAB 4 — credentials guide
    "useful_links.creds_retrigger_info": "After each credential update, retrigger the matching DAG from the Airflow UI.",
    "useful_links.exp_instagram": "📘 Instagram / Meta — Long-lived token (expires in 60 days)",
    "useful_links.body_instagram": """
**Full process:**
1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer)
2. Select your Meta app in the top-right dropdown
3. Click **"Generate Access Token"** → grant the permissions:
   - `instagram_basic`, `instagram_manage_insights`, `pages_read_engagement`, `ads_read`
4. Token generated → click the blue ℹ️ icon → **"Open in Access Token Debugger"**
5. On the debugger page → **"Extend Access Token"** button at the bottom → copy the long-lived token
6. Dashboard → **🔑 API Credentials** → Instagram → paste → Save
7. Retrigger: `instagram_daily` in Airflow

**Expiry reminder**: the token lasts **60 days**. Set a calendar alarm at D-5.

**Related DAG**: `instagram_daily`
""",
    "useful_links.exp_soundcloud": "🎵 SoundCloud — client_id",
    "useful_links.body_soundcloud": """
**Browser method (recommended):**
1. Open SoundCloud in Chrome/Firefox
2. DevTools F12 → **Network** tab
3. Start playing a track
4. Filter requests: look for `client_id=` in requests to `api-v2.soundcloud.com`
5. Copy the `client_id` parameter value (~32 alphanumeric characters)
6. Dashboard → **🔑 API Credentials** → SoundCloud → paste → Save
7. Retrigger: `soundcloud_daily`

**Validity**: variable, may expire without notice (SoundCloud closed its public API).
""",
    "useful_links.exp_spotify": "🎵 Spotify — Client ID + Secret",
    "useful_links.body_spotify": """
1. [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → your app
2. Copy **Client ID** and **Client Secret**
3. Dashboard → **🔑 API Credentials** → Spotify → Save
4. Retrigger: `spotify_api_daily` in Airflow

ℹ️ The collector uses the **client_credentials** flow: the access token
(~1 h) is re-generated automatically on each run. **No refresh_token,
no OAuth flow, no recurring action.** The only intervention case:
`client_secret` revoked/regenerated on Spotify's side → paste it again in the dashboard.

**Related DAG**: `spotify_api_daily`
""",
    "useful_links.exp_youtube": "🎬 YouTube — API key (YouTube Data API v3)",
    "useful_links.body_youtube": """
1. [console.cloud.google.com/apis/library/youtube.googleapis.com](https://console.cloud.google.com/apis/library/youtube.googleapis.com) → **Enable** the YouTube Data API v3
2. [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials) → **Create credentials → API key**
3. (Recommended) Restrict the key to *YouTube Data API v3*
4. Get the **Channel ID** (format `UC…`): YouTube Studio → Settings → Channel → Advanced settings
5. Dashboard → **🔑 API Credentials** → YouTube → paste `api_key` + `channel_id` → Save
6. Retrigger: `youtube_daily` in Airflow

ℹ️ The collector uses a **static API key** (`developerKey`), **not
OAuth**. An API key **does not expire** and **is not refreshed**. If it
is revoked or the daily quota is exceeded: regenerate a key in
Google Cloud Console and paste it again.

**Related DAG**: `youtube_daily`
""",
    "useful_links.exp_meta_ads": "📊 Meta Ads — Same token as Instagram",
    "useful_links.body_meta_ads": """
The same Meta long-lived token serves Instagram **and** Meta Ads.
If the `meta_ads_api_daily` DAG fails → check the Instagram token.

**Related DAG**: `meta_ads_api_daily`
""",
    # TAB 5 — debug & scripts
    "useful_links.sec_debug_dags": "Debug DAGs without Airflow (local)",
    "useful_links.debug_caption": "These scripts reproduce each DAG locally, without Docker Airflow.",
    "useful_links.dbg_spotify": "Test Spotify API collection",
    "useful_links.dbg_youtube": "Test YouTube collection",
    "useful_links.dbg_soundcloud": "Test SoundCloud collection",
    "useful_links.dbg_instagram": "Test Instagram collection",
    "useful_links.dbg_s4a": "Test S4A CSV processing",
    "useful_links.dbg_apple": "Test Apple Music CSV processing",
    "useful_links.dbg_meta": "Test Meta Ads API collection",
    "useful_links.dbg_ml": "Test ML scoring",
    "useful_links.sec_util_scripts": "Utility scripts",
    "useful_links.cmd_migrate": "Apply missing DB migrations",
    "useful_links.cmd_manage_mapping": "Manage artist mapping",
    "useful_links.util_caption": (
        "Spotify (client_credentials) and YouTube (static API key) "
        "have no auth script: test from Dashboard → "
        "Credentials → the platform's « Test connection » button."
    ),
    "useful_links.sec_db_checks": "Quick DB checks",
    "useful_links.q_spotify": "Last Spotify collection",
    "useful_links.q_youtube": "Last YouTube collection",
    "useful_links.q_soundcloud": "Last SoundCloud collection",
    "useful_links.q_instagram": "Last Instagram collection",
    "useful_links.q_s4a": "Last S4A collection",
    "useful_links.q_apple": "Last Apple Music collection",
    "useful_links.q_meta": "Last Meta Insights collection",
    "useful_links.q_ml": "ML prediction count",
    "useful_links.q_artists": "Registered artists",
    "useful_links.sec_ruff": "Ruff — Python syntax check",
    "useful_links.cmd_ruff_check": "Check the whole project",
    "useful_links.cmd_ruff_fix": "Automatic fix",
    "useful_links.page_generated": "Page generated on {ts}",
}
