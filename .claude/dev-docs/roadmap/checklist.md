# Master Roadmap Checklist

Single source of truth for all bricks and open bugs.
Updated by `strategic-plan-architect` background agent.
Resume after `/clear`: *"Read `.claude/dev-docs/roadmap/checklist.md` and continue with the next unchecked item."*

---

## Open Bugs

### P1 — Blocking (data missing or crash)

- [x] **SoundCloud + Instagram DAGs** — fixed 2026-03-30.
  SoundCloud: infinite pagination loop (manual offset ignored `next_href`) → cursor-based pagination + `max_pages=200` cap.
  Instagram: Meta API v18.0 deprecated Sept 2025 → centralized to `META_GRAPH_BASE_URL` (v24.0) via `src/utils/meta_config.py`; fresh personal token with ~56 days validity entered via Credentials page.
- [x] **`meta_campaigns` schema incomplete** — DB has 5 columns, `meta_ads_schema.py` expects 11.
  Fix: applied in `migrations/002_schema_fixes.sql`.
- [x] **DAG health audit** — completed 2026-03-23. Summary:
  | DAG | Schedule | Last run | State | Note |
  |-----|----------|----------|-------|------|
  | apple_music_csv_watcher | 15min | 2026-03-23 | ✅ success | No CSVs to process |
  | data_quality_check | daily 22h | 2026-03-21 | ⚠️ partial | `check_meta_ads_freshness` fails → empty meta_campaigns |
  | instagram_daily | daily 10h | 2025-12-11 | ❌ all failed | Expired credentials (P1) |
  | meta_csv_watcher_config | 5min | 2025-12-08 | ✅ last was ok | Not collecting (no new CSV files in watch dir) |
  | meta_insights_watcher | 5min | 2025-12-09 | ✅ last was ok | Same — idle since Dec 2025 |
  | ml_scoring_daily | daily 6h | — | ❌ paused | `dbname` bug fixed; unpause via UI |
  | s4a_csv_watcher | manual only | 2025-11-23 | ✅ success | schedule_interval=None, manual trigger needed |
  | soundcloud_daily | daily 9h | 2025-12-11 | ❌ all failed | Expired credentials (P1) |
  | spotify_api_daily | manual only | 2025-11-23 | ✅ success | schedule_interval=None, manual trigger needed |
  | youtube_daily | manual only | 2025-11-30 | ✅ success | schedule_interval=None, manual trigger needed |

### P2 — Data Integrity

- [x] **`meta_insights` UNIQUE(ad_id, date)** — missing `artist_id` → collision risk between artists.
  Fix: applied in `migrations/002_schema_fixes.sql`; DAG and view queries already filter by `artist_id`.
- [x] **`apple_songs_history` no `artist_id`** — data shared across all artists.
  Fix: migration in `migrations/002_schema_fixes.sql`; table added to `apple_music_csv_schema.py`; DAG and view queries updated.
- [x] **`meta_x_spotify.py` autocommit bypass** — lines 38–44 use `db.conn.cursor()` + `db.conn.commit()`.
  Fix: replace with `db.execute_query()` calls.
- [x] **`s4a_song_timeline` null artist_id** — rows created before migration may have `artist_id IS NULL`.
  Fix: applied in `migrations/002_schema_fixes.sql`.
- [x] **`ml_scoring_daily` DAG paused** — ML scoring not running automatically.
  Fix: `dbname` → `database` typo in DAG fixed. 16 `.ubj` model files confirmed present. Unpause via Airflow UI (http://localhost:8080).
- [x] **CSV import — validation before upsert** — `upload_csv.py` watcher inserts files without feedback or `artist_id` check.
  Fix: add pre-upsert validation step: row count, expected column names, detected/prompted `artist_id`; surface result in UI before writing to DB.
- [x] **PostgreSQL schema coherence audit** — completed 2026-03-23. 5 errors fixed:
  - `hypeddit.py`, `soundcloud_api_collector.py`, `instagram_api_collector.py`, `meta_csv_watcher.py`, `meta_insight_watcher.py` — all `db.conn.commit()/rollback()` calls removed (ProgrammingError with autocommit=True).
  - `hypeddit_schema.py` — 5 indexes missing IF NOT EXISTS, fixed.
  - `spotify_s4a_combined.py` — freshness query now filtered by artist_id.
  - `pdf_exporter.py` — 4 song-level queries now include 1x7 filter.
  Remaining warnings (non-blocking): youtube_channel_history/video_stats no UNIQUE, bootstrap gap (24 tables not in init_db.sql), provide_context deprecation in data_quality_check.
- [x] **Release-date filter standardized across all views** — filter by earliest release date (`MIN(date)`) is implemented on S4A/Apple/SoundCloud/Meta but missing on YouTube and inconsistent elsewhere.
  Fix: apply the same `track`/`song` release-date filter in all views; extends the YouTube-specific item (moved from P3).

### P3 — UX / Features

- [x] **SHAP/LIME explanations + marketing levers** — `trigger_algo.py` shows raw feature JSON but no SHAP values. Extend: display SHAP feature importances for the most recent track with marketing interpretation labels ("Increase saves", "Boost week-1 streams", etc.).
- [x] **`data_quality_check` DAG** — last run Dec 2025, status unknown. Verify if failing or just not scheduled.
- [x] **User onboarding doc (PDF)** — extend to a printable PDF checklist: run Docker, launch Streamlit, connect credentials, trigger a DAG, upload a CSV, read KPIs. Deliverable: PDF exportable from the app or standalone file.
- [x] **DAG run log dashboard** — dedicated view listing last run per DAG: status, duration, rows inserted, email alert on failure. Distinct from existing failure-callback emails (Brick 11).
- [x] **Budget tracker in trigger_algo** — in `trigger_algo.py`, show estimated cost per playlist submission (Groover/Fluence rates) and remaining budget from a value stored in DB or entered by user.
- [x] **Rename "iMusician" → "Distributeur" in UI** — update nav menu labels, page titles, and UI strings in `imusician.py` / `imusician_schema.py`. Do not rename DB tables or files (would be a regression).
- [x] **View optimization audit** — review all views for N+1 queries, deprecated `use_container_width` calls, unused columns, unnecessary re-renders.
  Action: run `/review-architecture`.

### P4 — Tech Debt

- [x] **`PostgresHandler` accept `DATABASE_URL`** — prerequisite for Railway deployment (Brick 15).
- [x] **`.github/workflows/ci.yml`** — ruff + pytest in CI (~20 lines).
- [x] **Tests for `csv_exporter.py`** — mock `db.fetch_df`, verify ZIP contains correct files.
- [x] **Export CSV: table selection** — allow checking/unchecking sources before ZIP download.
- [x] **Remove stale SQL views** — `view_soundcloud_latest`, `view_instagram_latest` replaced by DISTINCT ON in Python. DROP applied in `migrations/002_schema_fixes.sql`.
- [x] **`use_container_width` audit** — check `meta_ads_overview.py`, `instagram.py`, `youtube.py`, `hypeddit.py`, `spotify_s4a_combined.py`.

### P2 — Data Integrity (new)

- [x] **Multi-tenancy — artist_id propagation in all collectors** (Brick 20)
  Collectors hardcode `artist_id = 1` in INSERT statements. DAGs don't iterate all active artists.
  Fix: add `artist_id` param to `SoundCloudCollector`, `InstagramCollector`, `MetaAdsWatcher`, `MetaCSVWatcher`; update DAGs to loop via `get_active_artists()`; scope DELETE queries by `artist_id`.
  Files: `soundcloud_api_collector.py`, `instagram_api_collector.py`, `meta_insight_watcher.py`, `meta_csv_watcher.py`, `soundcloud_daily.py` (already OK), `instagram_daily.py`, `youtube_daily.py`, `spotify_api_daily.py`, `meta_insights_dag.py`, `meta_config_dag.py`.

### P3 — UX / Features (new)

- [x] **Scheduled email reports** — `airflow/dags/weekly_digest.py`, every Monday 08:00 UTC. One HTML email per active artist: S4A streams delta, top song, Meta spend/CTR, Instagram delta, SoundCloud delta, ML top prediction. Requires SMTP_USER/SMTP_PASSWORD/ALERT_EMAIL env vars.
- [x] **Stripe integration** (Brick 21) — `subscription_plans` + `artist_subscriptions` tables in `stripe_schema.py` + `migrations/004_stripe_billing.sql`; `POST /webhooks/stripe` in `src/api/routers/stripe_webhook.py` (handles checkout.session.completed, subscription.updated/deleted, invoice.payment_failed); `get_artist_plan()` + `require_plan()` in `auth.py`; billing page `views/billing.py` (current plan, MRR admin view, plan comparison, upgrade links). Requires STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_CHECKOUT_URL, STRIPE_PORTAL_URL env vars.
- [x] **PDF report expansion** — `pdf_exporter.py` extended with 6 new sections: S4A top songs, YouTube, Instagram, Meta Ads, SoundCloud tracks, Apple Music. `songs_filter` parameter added to `_collect_s4a_top_songs`, `collect_report_data`, `generate_pdf`. `export_pdf.py` adds S4A song selector with "Toutes" checkbox.
- [x] **Excel export** — `csv_exporter.py` gains `export_excel()` (openpyxl, multi-sheet). `export_csv.py` adds format selector (ZIP vs Excel).
- [x] **SoundCloud track selector UX** — track list sorted by `first_seen DESC`; defaults to the latest release (`[:1]`).
- [x] **Data Wrapped multi-tenant fix** — admin query no longer filters `active=TRUE`; non-admin loads real artist name from DB instead of hardcoded value.
- [x] **Billing page env fix** — `billing.py` replaced `st.secrets` with `os.getenv` for STRIPE_CHECKOUT_URL and STRIPE_PORTAL_URL (fixes crash when Streamlit secrets file absent).
- [x] **WeasyPrint → xhtml2pdf migration** — `pdf_exporter.py` and `requirements.txt` switched from WeasyPrint to `xhtml2pdf>=0.2.11` (eliminates system-level GTK/Pango dependency).
- [x] **SMTP config fix** — `.env` corrected: SMTP_HOST was set to an email address (now `smtp.gmail.com`); SMTP_PORT moved to its own line.

### P4 — Tech Debt (new)

- [x] **CSV upload audit log** — `csv_upload_log` table (migration 025): filename, artist_id, platform, row_count, status, error_message, imported_at. Logged after every upsert in `upload_csv.py`; audit failure never blocks UI.

- [x] **`init_db.sql` bootstrap gap** — 26 missing tables appended (S4A, Meta Ads, Meta Insights ×10, YouTube ×6, Apple Music ×4, Hypeddit ×2). Fresh install is now self-contained.
- [x] **YouTube UNIQUE constraints** — `UNIQUE(artist_id, channel_id, collected_at::date)` and `UNIQUE(artist_id, video_id, collected_at::date)` added to `youtube_schema.py` + `migrations/003_youtube_unique.sql`.
- [x] **`provide_context` deprecation** — removed `provide_context=True` from all 4 `PythonOperator` instances in `data_quality_check.py`. Functions already accept `**context`.

### P3 — UX / Features (new, 2026-03-27)

- [x] **Meta Ads credential onboarding guide** — step-by-step guide with screenshots for each artist to configure Meta credentials in the dashboard.
  Spec: (1) generate a long-lived User Access Token from Business Manager → System Users (not a personal token); (2) token must have `ads_read` + `ads_management` scopes; (3) account_id = numeric ID from `/me/adaccounts` (no `act_` prefix — the dashboard adds it); (4) artists do NOT create their own app — they use ETL_DASHBOARD_SPOTIFY as OAuth client; (5) link ad account to the app in Business Manager → App Settings → Business Assets.
  Deliverable: dedicated doc in `.claude/dev-docs/` + in-app help tooltip on Credentials page.

### P2 — Data Integrity (new, 2026-03-27)

- [x] **Instagram System User token — activation** — code-side ready (DAG `meta_token_refresh` skip `expires_at=NULL`, collector ne touche plus à `os.environ`). Activation par tenant = acte opérationnel décrit dans `.claude/dev-docs/meta-ads-credential-guide.md` ; suivi par artiste, pas par roadmap.
- [x] **Instagram + Meta System User token migration** (Brick 24) — migrate from personal 60-day tokens (expired Dec 2025) to System User tokens (never expire).
  Changes: `meta_token_refresh.py` skips artists with `expires_at=NULL` instead of attempting `fb_exchange_token` (which fails on System User tokens); `instagram_daily.py` precheck error message updated; `_guide_meta()` extended with Instagram scopes (`instagram_basic`, `instagram_manage_insights`, `pages_show_list`); `meta-ads-credential-guide.md` updated with token refresh behavior table.
  Note: Spotify/YouTube/meta_token_refresh DAGs were already scheduled in previous bricks — no schedule changes needed.

### P1 — Security (new, 2026-03-27)

- [x] **`get_artist_id()` default was `1` instead of `None`** — session non-hydratée queryait silencieusement l'artiste 1. Fix: `auth.py` default → `None`.
- [x] **`get_artist_id() or 1` dans 9 vues** — isolation tenant cassée pour les admins (None coercé sur artiste 1). Fix: guard explicite `if artist_id is None: if not is_admin(): st.stop()` dans `apple_music.py`, `instagram.py`, `soundcloud.py`, `youtube.py`, `meta_ads_overview.py`, `meta_cpr_optimizer.py`, `meta_creatives.py`, `meta_x_spotify.py`, `hypeddit.py`.
- [x] **f-string SQL avec `where_clause` interpolé — `meta_ads_overview.py`** — fragment WHERE interpolé dans 5 requêtes via f-string. Fix: suppression de la variable `where_clause`; chaque requête construite explicitement avec `_campaign_in`.
- [x] **f-string SQL avec identifiants table/colonne — `freshness_monitor.py` + `kpi_helpers.py`** — noms de table et colonne interpolés sans validation. Fix: allowlists `_ALLOWED_TABLES` / `_ALLOWED_COLS` validées avant interpolation.
- [x] **Secrets réels dans `config/config.yaml`** — superseded by "Standing ops: secret rotation" below. Closed as duplicate.

### P1 — Security (2026-03-28 — full OWASP + RGPD hardening)

- [x] **CRITICAL-02: SQL injection in `postgres_handler.py`** — `insert_many()` / `upsert_many()` used f-string table/column interpolation. Fix: `_ALLOWED_TABLES` frozenset + `_VALID_IDENTIFIER_RE`; all queries rewritten with `psycopg2.sql` composition.
- [x] **CRITICAL-03: SQL injection via `artist_id_sql_filter()` table alias** — alias not validated. Fix: `_ALIAS_RE = re.compile(r'^[a-z_][a-z0-9_]*$')` in `auth.py`.
- [x] **CRITICAL-04: Campaign filter IDOR in `meta_ads_overview.py`** — user-supplied campaign IDs not validated against DB. Fix: allowlist check against fetched campaign list.
- [x] **CRITICAL-05: Fernet key on disk** — `credentials.py` read FERNET_KEY only from config.yaml. Fix: `os.getenv('FERNET_KEY')` first, config.yaml as local-dev fallback.
- [x] **CRITICAL-06: Token written to `os.environ` in `instagram_api_collector.py`** — exposed to all child processes. Fix: removed the assignment entirely.
- [x] **HIGH-01: No brute-force protection** — unlimited login attempts. Fix: `failed_login_attempts` + `locked_until` in DB (migration 017); 5 failures → 15-min lockout.
- [x] **HIGH-02: Email enumeration on unverified login** — error message revealed whether email existed. Fix: generic message; email looked up only on "Resend" button click.
- [x] **HIGH-04: Weak password policy** — minimum 8 chars only. Fix: 10 chars + 1 letter + 1 digit enforced in both `auth.py` and `register.py`.
- [x] **HIGH-05: Hardcoded `'admin'` default in AirflowTrigger** — unauthenticated DAG triggering possible. Fix: `RuntimeError` raised if `AIRFLOW_PASSWORD` is falsy.
- [x] **HIGH-06/07: Stored XSS via `unsafe_allow_html`** — DB values interpolated unescaped in `etl_logs.py` and `home.py`. Fix: `html.escape()` on all interpolated values.
- [x] **MEDIUM-01: Session fixation** — session state not cleared on login. Fix: `st.session_state.clear()` before `_hydrate_session()`.
- [x] **MEDIUM-02: Plan gate bypass** — `require_plan()` returned `False` instead of stopping. Fix: `st.stop()` after error.
- [x] **MEDIUM-05: TOCTOU on single-use promo codes** — concurrent registrations could exhaust code without guard. Fix: atomic `UPDATE ... WHERE uses_count < max_uses RETURNING id`.
- [x] **INFO-01: Email verification tokens never expire** — link valid indefinitely. Fix: 48h expiry check in `_verify_email()`; expired token cleared from DB.
- [x] **INFO-02: Secret key names logged at INFO level** — `credential_loader.py` logged key name in update messages. Fix: `logger.debug()` with key name removed.
- [x] **INFO-04: SSRF via open redirects in outbound requests** — 5 `requests` calls in `credentials.py` without `allow_redirects=False`. Fix: `allow_redirects=False` on all 5.
- [x] **INFO-06: No upload size cap** — Streamlit allowed arbitrarily large file uploads. Fix: `.streamlit/config.toml` with `maxUploadSize = 50`.
- [x] **RGPD Art. 5(1)(f): Marketing export not audited** — no record of admin personal data access. Fix: `admin_audit_log` write on download button click in `admin.py`.
- [x] **CRITICAL-01: Credential rotation** — superseded by "Standing ops: secret rotation" below. Closed as duplicate.
- [x] **Task #11: Update all dev-docs with security session** — DEVLOG.md, retro.md, checklist.md updated to reflect the full 2026-03-28 security hardening session (Brick 25: OWASP + RGPD). All implemented items documented.

### P2 — Data Integrity (new, 2026-03-27 — audit)

- [x] **Collecteurs silencieux — `instagram_api_collector.py` + `soundcloud_api_collector.py`** — `except Exception → self.db = None` permettait un run complet à 0 lignes avec DAG SUCCESS. Fix: suppression du try/except autour de `PostgresHandler.__init__`; échec DB = exception levée.
- [x] **`spotify_api.py` `search_artist()` retournait `None`** — au lieu de `raise` sur API error ou artiste introuvable. Fix: `ValueError` si aucun artiste trouvé, `raise` dans le bloc `except`.
- [x] **Validation email trop permissive dans `register.py`** — `'@' not in email` acceptait `a@`, `@b`, `@@`. Fix: `re.fullmatch(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email)`.

### P3 — Performance (new, 2026-03-27 — audit)

- [x] **`get_artist_plan()` ouvrait 2–3 connexions DB par render** — fallback `db2` ouvert séparément. Fix: 1 seule requête avec LEFT JOIN `saas_artists ↔ artist_subscriptions ↔ subscription_plans`; promo + subscription + tier résolus en 1 round-trip. (`auth.py`)
- [x] **`get_source_freshness()` — 7 requêtes séquentielles** — 1 `SELECT MAX()` par source à chaque chargement de la home. Fix: remplacé par 1 `UNION ALL` query. (`kpi_helpers.py`)
- [x] **Index composites manquants** — `migration/016_performance_indexes.sql` ajoute 4 index : `s4a_song_timeline(artist_id, date DESC)`, `soundcloud_tracks_daily(artist_id, track_id, collected_at DESC)`, `meta_insights_performance_day(artist_id, day_date DESC)`, `track_popularity_history(artist_id, date DESC)`.

### P2 — Data Integrity (new, 2026-03-30)

- [ ] **Meta Ads DAG first-run backfill** — re-trigger `meta_ads_api_daily` without conf after smart date range fix. Expected: backfills from earliest campaign `start_time`, `rows_inserted > 0` in ETL Logs, freshness badge updates.
- [ ] **SoundCloud DAG cursor pagination — confirm** — re-trigger `soundcloud_daily` and verify no hang, cursor-based `next_href` is followed, tracks upserted without duplicates.
- [x] **Instagram System User token — migration** — same as line 110 (code path complete). Per-artist migration is operational, not a code task. See guide.

### P1 — Security (new, 2026-03-30)

- [x] **Credential rotation** — superseded by "Standing ops: secret rotation" below. Closed as duplicate.

### Decisions / closed (2026-03-27)

- ❌ **iMusician API** — no public API exists on any iMusician plan (confirmed 2026-03-27), including AMPLIFY Pro. CSV-only. `imusician_csv_watcher` DAG is the final architecture for this source. Contact iMusician support if an enterprise/white-label API becomes available.
- ❌ **Apple Music API** — Apple Music for Artists has no public analytics API. MusicKit covers catalog/playback only. CSV export remains the only option.

---

## Brick Status

| # | Topic | Status | Priority |
|---|---|---|---|
| 1 | DB migration SaaS (artist_id + saas_artists table) | ✅ | — |
| 2 | Auth Streamlit (authenticator + artist_id in session) | ✅ | — |
| 2.5 | SQL filters by artist (artist_id in all queries) | ✅ | — |
| 3 | Admin interface (CRUD artists + CSV upload) | ✅ | — |
| 4 | API credential form (Fernet encryption) | ✅ | — |
| 5 | CSV import via Streamlit with preview + validation | ✅ | — |
| 6 | Parameterized DAGs (credentials from DB) | ✅ | — |
| 7 | iMusician — manual monthly revenue entry + viz | ✅ | — |
| 8 | Home KPI + source freshness + ROI Breakheaven | ✅ | — |
| 9 | Error handling + retry on all collectors | ✅ | P2 |
| 10 | Unit tests (pytest, 79 tests) | ✅ | P2 |
| 11 | Monitoring + alerting (DAG callbacks + freshness) | ✅ | P2 |
| 12 | PDF report export (WeasyPrint) | ✅ | P3 |
| 13 | CSV global export (ZIP per artist) | ✅ | P3 |
| 14 | FastAPI REST backend (JWT auth) | ✅ | P4 |
| 15 | CI/CD Railway deployment | ✅ | P4 |
| 16 | ML — ml_song_predictions table + daily scoring DAG | ✅ | P3 |
| 17 | ML — trigger_algo upgrade + model performance view | ✅ | P3 |
| 18 | Data Wrapped — annual artist performance report (PDF/HTML) | ✅ | P3 |
| 19 | Security audit — SQL injection, Fernet key exposure, auth bypass, SSRF | ✅ | P3 |
| 20 | Multi-tenancy — artist_id propagation in all collectors + DAG iteration | ✅ | P2 |
| 21 | Stripe integration — subscription plans, webhook, billing page | ✅ | P3 |
| 22 | iMusician CSV import — parser, watcher DAG, Distributeur tab, Upload CSV page | ✅ | P2 |
| 23 | Meta Ads API collector — direct pull (facebook_business SDK), daily DAG, CSV data-quality fixes | ✅ | P2 |
| 24 | Instagram + Meta System User token migration — non-expiring tokens, DAG + guide updates | ✅ | P2 |
| 25 | Security hardening — OWASP Top 10 + RGPD: SQL injection (postgres_handler), brute-force lockout, session fixation, SSRF, XSS, weak password policy, Fernet key env, promo TOCTOU, token expiry, upload cap, audit log | ✅ | P1 |
| 26 | Rate limiting — session-based sliding window (10 attempts / 5 min) on login + TOTP challenge | ✅ | P1 |
| 27 | GDPR Art. 17 erasure — cascading DELETE across 34 tables, 2-step admin confirmation, gdpr_erasure_log audit trail | ✅ | P2 |
| 28 | TOTP 2FA — pyotp + qrcode enrollment in account.py, challenge step in login flow, disable-with-password | ✅ | P1 |
| 29 | Onboarding tracker — 4-step progress bar on home page (credentials, DAG run, CSV, 2FA); auto-hidden when complete | ✅ | P3 |
| 30 | Alerting dashboard — circuit breakers, freshness warnings, DAG failures, locked accounts, billing alerts | ✅ | P2 |
| 31 | S4A dashboard view audit — per-track KPIs (listeners, saves) from s4a_songs_global; dual-window (28d/12m) support; DB health view; playlist placement manual entry; s4a_audience saves/playlist_adds columns | ✅ | P3 |

---

### P3 — UX / Features (new, 2026-03-31)

- [x] **S4A per-track KPIs fix** — Listeners and Saves in trigger_algo `_show_tab_global()` were sourced from `s4a_audience` (artist-level → same value for all tracks). Rebound to `s4a_songs_global` per-track snapshot with automatic `time_window` selection (≤35 days → `28d`, else `12m`).
- [x] **s4a_songs_global dual-window** — migration 023 adds `time_window TEXT DEFAULT '12m'` + UNIQUE `(artist_id, song, time_window)`. Parser detects `28d` from filename tokens `28day/28d/28j`, else `12m`. `ml_inference.py` queries now filter `AND time_window = '12m'`.
- [x] **s4a_audience saves + playlist_adds** — migration 020 adds columns. Parser maps `'playlist adds'` (with space) and `'saves'` from audience CSV.
- [x] **Playlist placement manual entry** — migration 021 `s4a_song_playlists` (per-song playlist registry, unused for now). Migration 022 `s4a_song_playlist_adds(artist_id, song, period_start, period_end, count)` — stores manual count from S4A UI (not in CSV exports). `trigger_algo.py` Vue Globale shows count + update form.
- [x] **DB health view** (`src/dashboard/views/db_health.py`) — 11 datasets, freshness table + horizontal bar chart (thresholds 14j/30j), 52-week heatmap, cumulative growth chart, batch sizes chart.
- [x] **Styled dataframe NoneType crash** — `display.style.format(na_rep="—")` added as first call in Score /20 benchmark; `fillna(0)` on all numeric columns before styling.
- [x] **Upload CSV multi-file auto-detection** — `_detect_platform(filename, columns)` priority-ordered detection; `accept_multiple_files=True`; per-file preview + 4-KPI import result.
- [x] **upsert_many row count fix** — was returning `cursor.rowcount` (last batch only = 1); now returns `len(data)` post-dedup.

### P2 — Data Integrity (new, 2026-03-31)

- [x] **s4a_audience playlist_adds / saves still 0** — confirmed: `playlist_adds` is not present in `s4a_songs_global` CSV (neither 28d nor 12m format). Only source is `s4a_audience` daily timeline CSV (artist-level delta) which records 0 for this artist — genuine data. Saves ARE in songs_global CSV and import correctly. playlist_adds entry via manual form (`s4a_song_playlist_adds`) is the intended workflow.

### P1 — Security hardening (closed, 2026-05-14)

- [x] **Explicit SQL allowlist guards** — `db_health.py`, `admin.py`, `airflow_kpi.py` had f-string SQL with implicit allowlist (via constant lookup). Now call `validate_table()` / `validate_columns()` explicitly before each f-string per CLAUDE.md rule #8. Promoted both validators from private (`_validate_*`) to public API in postgres_handler. Commits `d41a842`, `997dcde`.

### P2 — Data integrity (closed, 2026-05-14)

- [x] **Instagram collector silent success** — `_refresh_access_token` and `save_to_db` swallowed exceptions and reported success. Both now `logger.error` + `raise`. Commit `a0f86de`.
- [x] **`requirements.txt` duplicates** — python-dotenv, pandas, psycopg2-binary listed twice (rows 62-64 vs canonical block). Removed dupes. Commit `a0f86de`.

### P3 — Infra / supply chain (closed, 2026-05-14)

- [x] **Airflow base image → Python 3.11** — was 3.10, mismatched `pyproject.toml requires-python = ">=3.11"`. Smoke-validated (15 DAGs load, sklearn/xgboost/shap import). Commit `52db15f`.
- [x] **Dependabot config** — pip weekly (groups), github-actions monthly, docker monthly. Closes the loop with `security-nightly.yml` pip-audit (detection → automated fix PR). Commit `6c323c9`.
- [x] **CI on `uv sync --frozen`** — was `pip install -r requirements*.txt` which ignored uv.lock; CI and local devs could install different transitive deps. Now CI reads uv.lock (231 packages pinned). Necessary for Dependabot to be effective. Commit `e6513b4`.
- [x] **Repo cleanup → `.archive/`** — ~22 obsolete files (unused skills, dev-docs stubs, archived agent doublons, dated retro/audit snapshots, legacy v1 collectors) moved to gitignored `.archive/`. CLAUDE.md aligned. Commits `a4fa11e`, `d60e570`, `418fad5`.
- [x] **Collectors style sweep** — 28 `print()` → `logger.*()` and 13 `datetime.now()` → `datetime.now(timezone.utc)` (filename strftime exempt). Commit `a0f86de`.
- [x] **REX promotion** — 2 drafts (`strategic-plan-architect`, `response-protocol`) validated and injected per `rules/rex-format.md`. Validator 42 tools OK. Commit `a3b13d9`.
- [x] **`check_roadmap_update.py` hook** — was no-op (`_INCLUDE='src/Application'` mismatched repo, tracker paths pointed to non-existent files). Fixed to `_INCLUDE='src'` with proper excludes, trackers = `roadmap/checklist.md` + `DEVLOG.md`. Commit `bcfe774`.
- [x] **`.env*.example` templates trackable** — `.gitignore` rule `.env.*` was swallowing the example onboarding files; added `!.env.example` + `!.env.railway.example` exceptions. Also added missing Stripe vars (Brick 21) to Railway example. Commit `66f807d`.
- [x] **pytest coverage** — added `[tool.coverage]` config in `pyproject.toml`, `--cov=src --cov-report=xml` in CI, coverage.xml uploaded as 7-day artifact. No `fail_under` (measure first). Commit `7376aae`.

### P3 — UX / Features (new, 2026-04-12)

- [x] **Live user counter + registered users widget** (Brick 32) — display on the app (home page or landing) the number of currently active sessions and total registered artists. ✅ 2026-05-14
  Sub-tasks:
  - [x] Active sessions: `active_sessions` table (heartbeat updated on each page load, TTL = 5 min). Migration 026.
  - [x] Registered users: `SELECT COUNT(*) FROM saas_artists WHERE active = TRUE`.
  - [x] SEO name: **Live Activity** chosen. Visible copy on landing: "X artistes utilisent streaMLytics".
  - [x] Read-only widget (counts only, no PII). Admin pulse on `home.py`, public trust signal on `register.py`.
  Priority: P3. Decision: added `active_sessions` heartbeat table with 60s session_state throttle (≤1 INSERT/min/session).

---

### Standing ops — incident-driven (no code action)

These are not roadmap bricks; they are operational standing instructions kept here for visibility.

- **Secret rotation (incident-driven only)** — rotate the following on suspected compromise or scheduled audit (no auto-rotation possible — secrets are external):
  - `DATABASE_PASSWORD` — PG superuser, used by all services
  - `FERNET_KEY` — ⚠️ critical : re-encrypt the entire `artist_credentials` table after rotation (script TBD)
  - `META_APP_SECRET` — Meta Developer Console
  - `SPOTIFY_CLIENT_SECRET` — Spotify Developer Dashboard
  - `YOUTUBE_API_KEY` — Google Cloud Console
  - `SMTP_PASSWORD` — Gmail App Password

  Files: `.env`, Railway env vars. Auto-refreshed tokens (Meta personal 60-day, SoundCloud Client Credentials, Spotify Client Credentials regrant) are NOT in scope — see `.claude/dev-docs/meta-ads-credential-guide.md` § "What is automated vs manual".

---

## Completed

All bricks (1–19) fully implemented. Session implementation notes were archived in `saas-db-migration/checklist.md` (deleted 2026-03-23 — no longer needed).
