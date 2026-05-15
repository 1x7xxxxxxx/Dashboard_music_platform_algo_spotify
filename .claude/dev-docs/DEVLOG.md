# DEVLOG

---

## 2026-05-15 — YouTube collector silent-success fix + credentials.py → package + refactor program

### Why
Close the last open `collector-silent-success` P2 (YouTube collector returned partial
data inside `except` — a truncated fetch could mark a DAG SUCCESS). Land R1 of the
dashboard refactor: `credentials.py` was the worst single-file offender (892 lines)
in `refactor-audit-dashboard.md` (#3). Persist a sequenced refactor queue so future
splits are trigger-gated, not ad-hoc.

### What changed
- `src/collectors/youtube_collector.py` — `get_video_comments()` and `get_playlists()`:
  `return [partial]` in `except` → `raise` (CLAUDE.md rule #6). `audit-collectors.md`
  status table corrected; `error-classes.md` `collector-silent-success` History appended.
  Commit `3b63984`.
- `src/dashboard/views/credentials.py` (892 l) → package `views/credentials/`
  (9 modules: `__init__`, `router`, `_core`, `_registry`, `_render`,
  `_platform_{spotify,youtube,soundcloud,meta}`). Pure cut/paste, zero logic change.
  Public surface unchanged (`from views.credentials import show`). The
  `_fetch_dag_last_states` Airflow N+1 helper moved to `credentials/_core.py`.
  `refactor-audit-dashboard.md` #3 marked DONE with as-built layout. Commit `acf8b6f`.
- `.claude/dev-docs/roadmap/refactor-program.md` (NEW) — sequenced R1–R6 queue +
  guardrails (no big-bang, no FastAPI/React, no service layers per ADR-002, never
  split <400 l) + DoD. P4 brick line added to `checklist.md`. Commit `c30d004`.
- `.claude/dev-docs/architecture.md` — Dashboard Views Map entry `credentials.py`
  → `credentials/` (package); added package-layout block + YouTube compliance note;
  linked (not duplicated) to `refactor-program.md`.

### Tests
`python3 -m pytest tests/ -q` → **237 passed** (unchanged — both code commits are
behavior-preserving). Ruff clean; import smoke OK; blast radius zero throughout.

### Reste à faire
R2 `kpi_helpers.py` ruff (quick win), R4 `trigger_algo.py` split (next edit),
R5 `pdf_exporter.py`, R6 `revenue_forecast.py`. Open P2 items unchanged
(`tracks` multi-tenant migration; Meta/SoundCloud DAG re-trigger verification).

### Cross-refs
- `.claude/dev-docs/roadmap/refactor-program.md` — R1–R6 sequenced queue + DoD
- `.claude/dev-docs/refactor-audit-dashboard.md` #3 — credentials split spec (DONE)
- `.claude/dev-docs/error-classes.md` — `collector-silent-success` History
- `.claude/dev-docs/architecture.md` — Dashboard Views Map + credentials package block

---

## 2026-05-14 (suite 2) — Auto-DEVLOG hook + baseline propagation + dashboard perf audit

### Why
Trois objectifs enchaînés en fin de session :
1. Combler le gap "le DEVLOG ne se met pas à jour seul malgré l'infra existante" — appliquer au DEVLOG le pattern draft-then-promote déjà éprouvé pour les REX.
2. Propager les modifs portables au repo `claude_code_deployment_baseline` pour que tous les futurs projets hériter du système.
3. Audit perf concret du dashboard (statique + live Lighthouse) pour cadrer les actions long-terme et trancher la question "réécriture React/Next.js ?".

### What changed

**Auto-DEVLOG draft system (commits `5cf5720` streamlytics, `ca837cb` baseline)**
- `.claude/hooks/draft_devlog.py` (NEW) — Stop hook qui écrit `.claude/sessions/pending-devlog.md` quand ≥3 fichiers réels (src/, airflow/, migrations/, tests/, docs/, build files) modifiés ET pas d'entrée DEVLOG du jour. Filtre exclut `.claude/` (couvert par draft_rex.py). Silent + non-bloquant.
- `.claude/commands/devlog-promote.md` (NEW) — slash command miroir de `/rex-promote`. Lit le pending, valide `validated: true` + zéro `?` restant, prepend dans DEVLOG.md, supprime le pending.
- `.claude/settings.json` — wire draft_devlog.py dans la chaîne Stop (entre draft_rex et promote_rex).
- Baseline : mêmes 3 modifs propagées dans le payload + suppression du `templates/dev-docs/GANTT.md` mort + création de `tools/dev/repack-claude-payloads.sh` (script référencé par `setup-claude-code.sh:46` mais absent du disque).

**Dashboard perf audit (commits `fd8f558` + `73fd236`)**
- Audit statique : 7 hot points identifiés avec file:line + gain estimé. Top 2 : N+1 Airflow DAG monitoring (`airflow_kpi.py:209`, `home.py:350`, `credentials.py:118` — ~2-3s gain) ; `@st.cache_data` manquant sur 5 KPI helpers (`kpi_helpers.py:147-200+` — ~500-1000ms).
- Audit live Lighthouse : login page = **69/100, LCP 5.7s, bundle JS Streamlit = 532 KiB (324 KiB unused)**. Confirme que le **cold start est JS-bound** et irréductible sans changer de framework. Workaround chrome-devtools-mcp WSL2 (Target closed) en lançant `npx lighthouse@12` direct sur Chrome bundled Puppeteer.
- 8 items P3 ajoutés à `roadmap/checklist.md` § "Performance dashboard (long-term, 2026-05-14 audit)" — incluant un nouvel item "disable Streamlit telemetry" (2 calls externes vers `data.streamlit.io/metrics.json` + `webhooks.fivetran.com` détectés au cold start, aucune trace dans le source = built-in Streamlit).
- `docs/adr/ADR-003-react-rewrite-deferred.md` (NEW) — ADR documente la décision de NE PAS lancer la réécriture React/Next.js maintenant. 4 trigger conditions explicites pour reconsidérer (UX feedback récurrent, besoin WebSocket/SSE, SEO public, scaling >50 artistes). Aucun trigger actif aujourd'hui. Stack cible documentée (Next.js 15 + Tailwind + shadcn + FastAPI existant + NextAuth + React Query + Recharts) + stratégie migration gradual (sous-domaine séparé, vue par vue, pas big-bang).

### Tests
Pas de tests modifiés cette session. Lint ruff OK sur les fichiers touchés (`draft_devlog.py` syntax check OK, JSON valide pour settings.json). Live audit Lighthouse = 69/100 (mesure réelle, pas test).

### Commits
- `5cf5720` — feat(hooks): add draft_devlog Stop hook + /devlog-promote slash command
- `fd8f558` — docs(perf): static dashboard audit → P3 roadmap section + ADR-003 (React rewrite deferred)
- `73fd236` — docs(perf): live Lighthouse audit calibration + Streamlit telemetry item
- baseline `ca837cb` — feat(payload): add draft_devlog hook + /devlog-promote command + repack script; remove dead GANTT.md

### Reste à faire
**Code-side : rien.** Tout pushé sur `origin/main` (4 commits streamlytics au-dessus de cette session + 1 commit baseline).

**Action utilisateur** :
- Re-trigger `meta_ads_api_daily` une fois → vérifier backfill ETL Logs
- Re-trigger `soundcloud_daily` une fois → vérifier no-hang + cursor pagination
- (optionnel ~56j de marge) Activer token IG System User via Business Manager (2FA SMS)
- (quand prêt) Exécuter `migration-hetzner.md` (~1 jour)
- (à ton rythme) Traiter les 8 items P3 perf dashboard (~2 jours dev → -50% render time interne)

**Vérifications smoke à faire** :
- À ta prochaine session avec ≥3 fichiers modifiés : confirmer que `pending-devlog.md` apparaît à la fin de session
- Tester l'auto-trigger DAG : sauve des creds Spotify dans le dashboard → vérifier toast + run dans Airflow UI
- Live audit perf des vues internes (auth requise) — pas faisable cette session sans login

### Cross-refs
- `docs/adr/ADR-003-react-rewrite-deferred.md` — décision React deferred + triggers
- `.claude/dev-docs/migration-hetzner.md` — play-by-play Hetzner CX33 (créé en (suite 1))
- `.claude/dev-docs/meta-ads-credential-guide.md` — table "What is automated vs manual" (créée en (suite 1))
- `.claude/dev-docs/roadmap/checklist.md` § "Performance dashboard" — 8 items P3 chiffrés
- `.claude/dev-docs/roadmap/checklist.md` § "Standing ops" — rotation secrets incident-driven (consolidée en (suite 1))

---

## 2026-05-14 (suite) — Roadmap cleanup + auto-trigger DAG + Hetzner migration doc

### Why
Confusion utilisateur sur ce qui restait "à faire" : roadmap listait 5 items "ouverts" dont 3 doublons (rotation secrets) et 2 obsolètes (IG System User token — code-side complete depuis Brick 24). Demande connexe : pouvoir déclencher automatiquement le DAG dès qu'un artiste sauvegarde ses creds, et avis Hetzner vs Railway.

### What changed
- **`roadmap/checklist.md`** : fermé lignes 110/162 (IG token : code complete, action operational par tenant) ; consolidé lignes 121/143/166 (3 doublons rotation) en une seule section "Standing ops — incident-driven" en bas du fichier.
- **`meta-ads-credential-guide.md`** : ajouté table "What is automated vs manual" couvrant les 5 sources (Meta perso/SystemUser, SoundCloud, Spotify, YouTube) + cross-ref dans la section refresh existante.
- **`airflow/dags/ml_scoring_daily.py`** : reschedule `0 6 * * *` → `0 11 * * *`. L'ancien horaire tournait AVANT spotify(7h)/youtube(8h)/soundcloud(9h)/instagram(10h) → scoring sur données J-1.
- **`src/dashboard/views/credentials.py`** : nouveau `_PLATFORM_DAG_MAP` + bloc trigger non-bloquant à la fin de `_handle_save()`. Quand l'artiste sauve des creds Spotify/YouTube/SoundCloud/Instagram/Meta, le DAG correspondant se déclenche immédiatement avec `conf={'artist_id': X}`. Toast UI sur succès ; warning si Airflow injoignable — la sauvegarde des creds reste effective.
- **`migration-hetzner.md`** (nouveau, 250 lignes) : play-by-play migration Railway → Hetzner CX33 (€6.99/mo vs €30-50/mo). 11 sections : pré-reqs, hardening, Caddy + Let's Encrypt, GitHub Action deploy, backups quotidiens via Storage Box, DNS bascule, rollback. Estimé 1 journée.
- **`GANTT.md`** : supprimé. Stub template jamais adapté (référençait BRICKS.md / generate-dev-docs.py inexistants).

### Tests
Pas de modification fonctionnelle des collecteurs/DAGs ; pytest non re-run. Lint ruff sur fichiers touchés OK (2 F401 pré-existants hors scope).

### Commits
- `60b4a44` — docs(roadmap): consolidate stale token/rotation entries
- `07075a4` — feat(ux): auto-trigger DAG on credential save + ml_scoring reschedule + Hetzner migration doc
- (this commit) — chore(devlog): log session + remove dead GANTT.md stub

### Reste à faire (action utilisateur uniquement)
- Re-trigger `meta_ads_api_daily` une fois → vérifier backfill ETL Logs
- Re-trigger `soundcloud_daily` une fois → vérifier no-hang + cursor pagination
- Activer token IG System User via Business Manager (pas urgent)
- Quand prêt : exécuter `migration-hetzner.md` (~1 jour)

---

## 2026-04-12 — Product naming

**Decision:** App officially named **streaMLytics**.

- Double reading: *Streamlytics* (streaming analytics) + *ML* capitalized → signals ML-powered product.
- SEO rationale: "streaming analytics" is a searchable term in the music SaaS vertical. Brand name stays short; SEO weight carried by page title/meta description, not the name itself.
- Brick 32 added to checklist: live user counter (active sessions + registered artists) widget, SEO name TBD → *streaMLytics Live* candidate.
- Files updated: `CLAUDE.md`, `README.md`, `architecture.md`, `DEVLOG.md`, `checklist.md`.

---

## 2026-03-30 (Session 4)

### Session summary

**Bug fixes: Instagram, SoundCloud, Meta freshness + smart date range**

**`src/utils/meta_config.py` — NEW**
- Single source of truth for Meta Graph API version: `META_API_VERSION = "v24.0"`, `META_GRAPH_BASE_URL`.
- Replaces hardcoded `v18.0` (deprecated Sept 2025) and `v21.0` strings across 6 files.

**`src/collectors/instagram_api_collector.py` — fix(P1)**
- `self.base_url`: `"https://graph.facebook.com/v18.0"` → `META_GRAPH_BASE_URL`.
- Root cause of Instagram DAG 400 errors since Dec 2025.

**`src/collectors/soundcloud_api_collector.py` — fix(P1)**
- Replaced manual `offset += limit` pagination with cursor-based `next_href` following.
- Added `max_pages = 200` safety cap. `params = {}` after first call (next_href is self-contained).
- Root cause of 2-hour DAG hang (infinite loop on last page).

**`src/collectors/meta_ads_api_collector.py` — fix + feat**
- `api_version`: `'v21.0'` → `META_API_VERSION` (import from `meta_config`).
- Added `'collected_at': datetime.now()` to `day_row` dict; added `'collected_at'` to `_insight_cols['meta_insights_performance_day']`. Fixes stale freshness badge (badge was reading `MAX(collected_at)` which was NULL).
- `_fetch_all_insights()`: replaced hardcoded 90-day lookback with smart date range:
  - Incremental: `MAX(day_date) - 3 days` overlap for late-arriving data.
  - First run (no data in DB): backfill from earliest campaign `start_time`.
  - `full_history=True`: always backfill from earliest campaign start.
- `run()`: now returns `int` (total insight rows inserted).

**`airflow/dags/meta_ads_api_daily.py` — feat**
- Added `DagRunLogger` wrapper: every artist run writes to `etl_run_log` with `rows_inserted`.
- Exposed `full_history` from `dag_run.conf` (trigger param).
- Result: ETL Logs view now shows `rows_inserted=0, status=success` when DAG runs but no new data exists (distinguishes from error).

**`airflow/dags/meta_token_refresh.py` — fix**
- Token exchange URL: `graph.facebook.com/v18.0` → `META_GRAPH_BASE_URL`.

**`src/dashboard/views/credentials.py` — feat**
- All hardcoded `graph.facebook.com/v24.0` URLs → `META_GRAPH_BASE_URL`.
- New `_fetch_meta_token_expiry(token, app_id, app_secret)`: calls `/debug_token` to get Unix expiry; auto-populates `expires_at` in `artist_credentials` when saving Meta token.
- Effect: `meta_token_refresh` DAG now has a real `expires_at` to compare against; no manual date entry needed.

**`src/dashboard/utils/kpi_helpers.py` + `src/utils/freshness_monitor.py` — feat**
- Added "Spotify API" entry to `SOURCES_CONFIG` / `MONITOR_TARGETS` with `skip_artist_filter: True`, pointing to `artists.collected_at`.
- Home dashboard freshness badge now shows Spotify API last collection date.

**Migrations applied (PowerShell, 2026-03-30)**
- `migrations/017_security_hardening.sql`: `failed_login_attempts`, `locked_until`, `verification_token_created_at`, `admin_audit_log` table.
- `migrations/018_totp_rate_limit_gdpr.sql`: `totp_secret`, `totp_enabled`, `login_rate_limit` table, `gdpr_erasure_log` table.

**Status at end of session**
- Instagram DAG: ✅ functional (1582 followers collected, fresh personal token, ~56 days remaining).
- SoundCloud DAG: ✅ pagination fixed, re-trigger needed to confirm.
- Meta Ads DAG: smart date range live; re-trigger needed — first run will backfill from earliest campaign start.
- Meta freshness badge: fixed once next DAG run inserts rows with `collected_at`.

---

## 2026-03-28 (Session 3)

### Session summary

**Bricks 26–30 — Rate limiting, GDPR erasure, TOTP 2FA, Onboarding tracker, Alerting dashboard**

**`migrations/018_totp_rate_limit_gdpr.sql` — NEW**
- `saas_users`: added `totp_secret TEXT`, `totp_enabled BOOLEAN DEFAULT FALSE`.
- `login_rate_limit` table: session/IP-based attempt counter (ip_hash, endpoint, attempts, window_start).
- `gdpr_erasure_log` table: RGPD Art. 17 audit trail (admin_user_id, erased identifiers, rows_deleted JSONB, reason).

**`requirements.txt`**
- Added `pyotp>=2.9.0` and `qrcode[pil]>=7.4.2`.

**`src/dashboard/auth.py` — Bricks 26 + 28**
- Added `_check_session_rate_limit()` / `_rate_record_failure()` / `_rate_reset()`: 10-attempt session window (5 min), no IP dependency.
- `_authenticate_user()`: now returns `totp_enabled` + `totp_secret` in user dict; queries new columns.
- `_hydrate_session()`: now stores `user_id` in session (required by admin audit log).
- `_show_totp_challenge()`: TOTP verification step — renders after password success when `totp_enabled=True`; uses `pyotp.TOTP.verify(valid_window=1)`.
- `require_login()`: checks `_totp_pending` session key to route to challenge form; calls `_check_session_rate_limit()` before auth; records failure/reset on outcome.

**`src/dashboard/views/account.py` — Brick 28**
- `_get_user_row()`: now selects `totp_enabled`.
- `_section_change_password()`: uses `_validate_password_strength()` instead of `len(pw) < 8`.
- `_section_totp()` NEW: enrollment QR code (pyotp + qrcode), manual key display, verify+activate form, disable-with-password flow.
- `show()`: added `tab_2fa` tab.

**`src/dashboard/views/admin.py` — Brick 27 (RGPD Art. 17)**
- `_GDPR_PLATFORM_TABLES`: list of 34 platform tables with `artist_id`.
- `_erase_artist_gdpr()`: cascading DELETE across all tables + saas_users + saas_artists; writes to `gdpr_erasure_log`; returns per-table row counts.
- `show()`: added "🗑️ Effacement RGPD" tab with 2-step confirmation and erasure history log.

**`src/dashboard/views/home.py` — Brick 29**
- `_section_onboarding()`: 4-step progress bar (credentials, first DAG run, first CSV, 2FA); single UNION ALL query; hidden once all steps completed.
- `show()`: calls onboarding section before `_section_dag_status()` for artist sessions only.

**`src/dashboard/views/alerts.py` — NEW (Brick 30)**
- 5 sections: circuit breakers (OPEN/HALF_OPEN), data freshness warnings, DAG failures (24h), locked accounts (admin only), billing alerts (admin only).
- Artists see their own data; admins see all.
- Global alert count fed back to sidebar badge.

**`src/dashboard/app.py`**
- Added `"🚨 Alertes": "alerts"` to nav; routing `elif page == "alerts"`.

---

## 2026-03-28 (Session 2)

### Session summary

**Security Hardening — OWASP + RGPD full implementation**

**`migrations/017_security_hardening.sql` — NEW**
- `saas_users`: added `failed_login_attempts INT DEFAULT 0`, `locked_until TIMESTAMPTZ`, `verification_token_created_at TIMESTAMPTZ`.
- `admin_audit_log` table: tracks every admin privileged action (admin_user_id, action, detail, created_at).
- `referral_events`: added CASCADE FK on `referred_artist_id`.

**`src/database/postgres_handler.py` — CRITICAL-02**
- Added `_ALLOWED_TABLES` frozenset (51 tables) and `_VALID_IDENTIFIER_RE` validation.
- `insert_many()` + `upsert_many()` rewritten with `psycopg2.sql` composition; functional index expressions handled separately.

**`src/dashboard/auth.py` — HIGH-01/02/04, MEDIUM-01/02, CRITICAL-03**
- `_validate_password_strength()`: minimum 10 chars, at least 1 letter + 1 digit (was: `len >= 8`).
- `_authenticate_user()`: DB-persisted brute-force lockout (5 failures → 15 min), `locked_until` check before bcrypt.
- Login: `st.session_state.clear()` before hydrate (session fixation fix).
- `require_plan()`: `st.stop()` instead of `return False` (bypass fix).
- `artist_id_sql_filter()`: alias validated against `_ALIAS_RE` (SQL injection fix).

**`src/dashboard/views/register.py` — HIGH-04, MEDIUM-05**
- Imports and uses `_validate_password_strength` from `auth.py`.
- `_apply_promo()`: atomic `UPDATE ... WHERE uses_count < max_uses RETURNING id` prevents TOCTOU race on single-use codes.

**`src/dashboard/views/meta_ads_overview.py` — CRITICAL-04**
- Campaign filter: allowlist check against DB-fetched list before interpolation.

**`src/dashboard/views/credentials.py` — CRITICAL-05, INFO-04**
- `_get_fernet()`: prioritizes `os.getenv('FERNET_KEY')` over config.yaml.
- All 5 outbound `requests` calls (Spotify, YouTube, SoundCloud ×2, Meta, Meta token refresh): `allow_redirects=False` added.

**`src/dashboard/views/etl_logs.py` + `home.py` — HIGH-06/07**
- `html.escape()` on all DB-sourced values inside `unsafe_allow_html=True` blocks.

**`src/dashboard/app.py` — HIGH-05, INFO-01**
- `AirflowTrigger`: raises `RuntimeError` if `AIRFLOW_PASSWORD` is falsy (no more `'admin'` default).
- `_verify_email()`: tokens older than 48h are rejected and cleared from DB.

**`src/collectors/instagram_api_collector.py` — CRITICAL-06**
- Removed `os.environ['INSTAGRAM_ACCESS_TOKEN'] = new_token` (child process token exposure).
- Removed DB host/port `print()` statements (credential leak in logs).

**`src/utils/credential_loader.py` — INFO-02**
- `logger.info(secret_key updated...)` → `logger.debug(...)` with key name removed.

**`.streamlit/config.toml` — NEW (INFO-06)**
- `maxUploadSize = 50` — caps upload to 50 MB, limits DoS via large file upload.

**`src/dashboard/views/admin.py` — RGPD Art. 5(1)(f)**
- Marketing export `download_button`: writes to `admin_audit_log` on click.

**Manual action still required (CRITICAL-01)**
- Rotate all credentials in `.env`: DATABASE_PASSWORD, SPOTIFY_CLIENT_SECRET, META_APP_SECRET, META_ACCESS_TOKEN, YOUTUBE_API_KEY, FERNET_KEY, SMTP_PASSWORD. Re-encrypt `artist_credentials` after rotating FERNET_KEY.

---

## 2026-03-28 (Session 1)

### Session summary

**System Audit — Full architecture documentation**

**`.claude/dev-docs/system-audit.md` — NEW (49 KB)**
- 4 parallel agents scanned the full codebase (51 tables, 15 DAGs, 14 views, 7 collectors, all utils).
- Section 1: PostgreSQL ERD by domain — 6 Mermaid `erDiagram` blocks (SaaS Core, Spotify, Meta Ads, YouTube, Social/Other, ML & Monitoring). Every column, type, UNIQUE constraint, FK and CHECK documented.
- Section 2: DAG execution schedule — Gantt timeline (UTC), retry matrix, detailed flow charts per DAG (Spotify, Meta Ads API, Alert Monitor, Data Quality, CSV Watchers).
- Section 3: KPI workflows — freshness thresholds (green <24h / orange 24–72h / red >72h / gray no-data), per-view SQL patterns, ROI / churn / LTV / ML probability formulas.
- Section 4: Charts catalog — 30+ charts with type, SQL source, colors, axes, filters.
- Section 5: Alert system — freshness thresholds per source (48h API / 168h CSV), circuit breaker state machine (3 failures → OPEN → 6h → HALF_OPEN), data quality checks (streams >1M = warning, duplicates = critical), 26 root-cause patterns mapped to actions.
- Section 6: API endpoints — rate limits, retry strategies, token lifecycle per platform (Spotify client_credentials, YouTube refresh_token, SoundCloud auto-renew 3600s, Meta/Instagram 60d + proactive refresh at ≤15d).
- Section 7: Credential pipelines — Fernet AES-128 storage, retrieval sequence diagram, per-platform field classification (secret vs plain), token refresh flows (proactive / weekly DAG / manual dashboard), access control (admin vs artist).

---

## 2026-03-27

### Session summary

**Brick 24 — Instagram + Meta System User token migration**

**Automation investigation**
- iMusician: no public API exists on any plan (confirmed). Source remains CSV-only.
- Apple Music: no analytics API available. Source remains CSV-only.
- Spotify / YouTube / `meta_token_refresh` DAGs were already scheduled in previous bricks — no changes needed.

**`meta_token_refresh.py`**
- Changed `expires_at IS NULL` behavior: previously triggered an unconditional refresh; now skips the token (System User token assumed). `fb_exchange_token` grant type fails on System User tokens, which never expire, and would have stored a corrupted token.

**`instagram_daily.py`**
- Updated precheck error message: reference changed from "Graph API Explorer" to "Business Manager → System Users" to match the correct credential source.

**`credentials.py _guide_meta()`**
- Added "Étapes supplémentaires — Instagram" section listing required scopes: `instagram_basic`, `instagram_manage_insights`, `pages_show_list`.
- Clarified that `meta_token_refresh` DAG skips System User tokens (never-expiring).

**`meta-ads-credential-guide.md`**
- Step 3: added Instagram scopes (`instagram_basic`, `instagram_manage_insights`, `pages_show_list`).
- Added "Token refresh behavior" table at end of document.

---

**Brick 23 — Meta Ads API collector + CSV data quality fixes**

**Meta Ads API collector (`src/collectors/meta_ads_api_collector.py`) — NEW**
- Direct pull from Meta Marketing API via `facebook_business` SDK (already in requirements at v18).
- `artist_id`-aware; credentials loaded from DB via `credential_loader` (platform=`meta`).
- Credential key mismatch fixed: form stores `account_id`, not `ad_account_id`; collector now reads `account_id` and auto-prefixes `act_` if absent.
- `_fetch_insights`: results = `link_click` + `offsite_conversion.custom` only. `lp_views` extracted from `actions` array (action_type `landing_page_view`) — not a direct API field. `landing_page_views` removed from fields list (invalid at campaign level).
- CPR/CPC = None when denominator is zero.
- All except blocks raise (P2 invariant).

**DAG `airflow/dags/meta_ads_api_daily.py` — NEW**
- Schedule: `0 5 * * *` (05:00 UTC). Iterates active artists. Skips artists with no Meta credentials (WARNING, no failure). Raises RuntimeError if any credentialed artist fails.

**Debug script `airflow/debug_dag/debug_meta_ads_api.py` — NEW**
- 4-step: credential check → `/me` connectivity → dry-run campaigns → `--write` full run.

**CSV watcher fixes (`src/collectors/meta_insight_watcher.py`, `src/transformers/meta_insight_csv_parser.py`)**
- CPR = None when results=0; computed from spend/results when column blank; CPC same for link_clicks.
- `artist_id` guard in `MetaAdsWatcher.__init__`.
- Per-file `except` block now raises (was silently continuing — P2 bug).

**Schema fix (`src/database/meta_ads_schema.py`)**
- `meta_insights` UNIQUE changed from `(ad_id, date)` to `(artist_id, ad_id, date)`.

**Migration `migrations/012_meta_ads_api.sql`**
- Backfill artist_id=1 in meta_insights.
- Fix meta_insights UNIQUE constraint (DROP old + ADD new via DO block).
- Dedup all 5 meta_insights_performance* tables.
- ADD COLUMN optimization_goal, billing_event to meta_adsets (were in schema, missing in DB).

**API authentication debugging (2h)**
- Wrong ad_account_id configured (`act_742826472175198` not accessible to token user).
- Correct account: `act_567214713853881` ("1x7xxxxxxx") — confirmed via `/me/adaccounts`.
- Token scope confirmed: `ads_read` + `ads_management` both granted.

**Brick 23 — Part 2: full rewrite finalization + rate limit handling**

- `meta_ads_api_collector.py`: added `_meta_list()` retry helper (code 17, 3×, 60/120/180s); `run(insights_only=True)` to skip config fetch; trimmed breakdown table rows to slim schema columns before upsert (fixes `frequency column does not exist` on `_age`/`_country`/`_placement`).
- `debug_meta_ads_api.py`: added `--full-history`, `--insights-only` flags; step 4 prints per-table row counts.
- `migrations/013_meta_ads_creative_targeting.sql`: ADD COLUMN title/body/call_to_action on meta_ads; ADD 10 targeting decomposition columns on meta_adsets.
- `meta_ads_schema.py`: schema definition updated to match DB.
- Final full-history run: 10 insight tables populated (perf 216, day 231, age 109, country 492, placement 330 rows; matching engagement).
- Meta rate limit clarification: code 17 = per-ad-account hourly limit (not app-level quota shown in dashboard). `_meta_list()` handles it automatically in production.

---

## 2026-03-26

### Session summary

**SoundCloud DAG — IP block diagnostic**
- Confirmed 403 (IP blocked by SoundCloud) via Airflow logs. Silent success anti-pattern was present in earlier run (2026-03-24); current code already raises `ValueError` on 403 → task marks FAILED correctly.
- Email alert was crashing: `SMTP_HOST` was set to an email address instead of `smtp.gmail.com`. `SMTP_PORT=587` was on the same line as `SMTP_HOST` (never parsed). Fixed `.env`.

**WeasyPrint → xhtml2pdf migration**
- WeasyPrint requires GTK3/Pango/Cairo system libs (unavailable on Windows without MSYS2/GTK runtime).
- Replaced with `xhtml2pdf>=0.2.11` (pure Python, no system deps).
- `requirements.txt` updated. PDF generation logic unchanged (same HTML input).

**billing.py — StreamlitSecretNotFoundError**
- `st.secrets.get()` throws when no `secrets.toml` exists even with `hasattr(st, 'secrets')` guard.
- Replaced both calls (`STRIPE_CHECKOUT_URL`, `STRIPE_PORTAL_URL`) with `os.getenv()`.

**PDF export — 6 new sections**
- Added: Spotify S4A top songs, YouTube, Instagram, Meta Ads, SoundCloud tracks, Apple Music.
- Each section has a dedicated `_collect_xxx` and `_render_xxx` function in `pdf_exporter.py`.
- `_collect_s4a_top_songs` accepts `songs_filter` param; wired through `collect_report_data` and `generate_pdf`.
- `export_pdf.py` UI: added S4A song selector (multiselect + "Toutes" checkbox).

**Export CSV — Excel format**
- Added `export_excel()` to `csv_exporter.py` (openpyxl, one sheet per table, sheet names ≤31 chars).
- `export_csv.py` UI: format radio (ZIP CSV / Excel .xlsx), unified download button.

**Sidebar — DAG button position**
- `show_data_collection_panel()` moved before `show_navigation_menu()` in `main()`.
- Separator `---` moved from top to bottom of the panel function.

**SoundCloud view — track selector UX**
- Added `first_seen` subquery (MIN collected_at per track_id).
- Track multiselect now sorted by `first_seen DESC` (latest release first), defaults to `[:1]`.

**Data Wrapped — artist selector fix**
- Admin query: removed `WHERE active = TRUE` → all artists visible (historical data entry).
- Non-admin: real artist name loaded from `saas_artists` instead of hardcoded `f"Artiste {aid}"`.

---
