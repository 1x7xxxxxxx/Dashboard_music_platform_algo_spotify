# Master Roadmap Checklist

Single source of truth for all bricks and open bugs.
Updated by `strategic-plan-architect` background agent.
Resume after `/clear`: *"Read `.claude/dev-docs/roadmap/checklist.md` and continue with the next unchecked item."*

---

## Open Bugs

### P1 — Blocking (data missing or crash)

- [ ] **SoundCloud + Instagram DAGs** — credentials expired since Dec 2025 → 67 failures, no data for 3 months.
  Fix: enter valid credentials via `Credentials API` page in dashboard, then retrigger the DAGs.
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

### P4 — Tech Debt (new)

- [x] **`init_db.sql` bootstrap gap** — 26 missing tables appended (S4A, Meta Ads, Meta Insights ×10, YouTube ×6, Apple Music ×4, Hypeddit ×2). Fresh install is now self-contained.
- [x] **YouTube UNIQUE constraints** — `UNIQUE(artist_id, channel_id, collected_at::date)` and `UNIQUE(artist_id, video_id, collected_at::date)` added to `youtube_schema.py` + `migrations/003_youtube_unique.sql`.
- [x] **`provide_context` deprecation** — removed `provide_context=True` from all 4 `PythonOperator` instances in `data_quality_check.py`. Functions already accept `**context`.

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

---

## Completed

All bricks (1–19) fully implemented. Session implementation notes were archived in `saas-db-migration/checklist.md` (deleted 2026-03-23 — no longer needed).
