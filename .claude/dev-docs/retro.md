# Retrospective Log

Auto-appended by `strategic-plan-architect` background agent after each session.
Format: `## YYYY-MM-DD HH:MM` + Changed / Why / Decisions / Status

---

## 2026-03-27 — Security + performance audit

**Changed:**
- `src/dashboard/auth.py` — `get_artist_id()` default `1` → `None`; `get_artist_plan()` 2–3 connexions → 1 JOIN query
- 9 views (`apple_music`, `instagram`, `soundcloud`, `youtube`, `meta_ads_overview`, `meta_cpr_optimizer`, `meta_creatives`, `meta_x_spotify`, `hypeddit`) — `get_artist_id() or 1` remplacé par guard explicite
- `src/dashboard/views/meta_ads_overview.py` — variable `where_clause` f-string supprimée; requêtes construites explicitement
- `src/utils/freshness_monitor.py` + `src/dashboard/utils/kpi_helpers.py` — allowlists identifiants SQL ajoutées
- `src/dashboard/utils/kpi_helpers.py` — `get_source_freshness()` : 7 requêtes séquentielles → 1 UNION ALL
- `src/collectors/instagram_api_collector.py` + `soundcloud_api_collector.py` — try/except silencieux sur DB init supprimé
- `src/collectors/spotify_api.py` — `search_artist()` raise au lieu de return None
- `src/dashboard/views/register.py` — validation email renforcée (regex)
- `migrations/016_performance_indexes.sql` — 4 index composites sur `(artist_id, date)`

**Why:** Audit sécurité + qualité déclenché manuellement. Double objectif : corriger les failles d'isolation tenant et les anti-patterns de performance avant la mise en production SaaS.

**Decisions:**
- `get_artist_id() or 1` pour admin conservé temporairement dans les vues (admin voit artiste 1) — refactoring complet vers `artist_id_sql_filter()` différé au prochain cycle
- Rotation des secrets `config/config.yaml` laissée à l'utilisateur (fichier non tracké en git, déjà dans `.gitignore`)
- `pip-audit` non intégré en CI — à ajouter au prochain cycle P4

**Status:** Tous les P1 sécurité résolus sauf rotation manuelle des secrets. P2 data integrity résolus. P3 performance résolus.

---

## 2026-03-12 — Bricks 9–13, 16–17 + bug fixes

**Changed:**
- `src/utils/retry.py`, `src/utils/error_handler.py` (Brick 9)
- `tests/` directory — 4 test files, `conftest.py` (Brick 10)
- `src/utils/freshness_monitor.py` (Brick 11)
- `src/dashboard/utils/pdf_exporter.py`, `src/dashboard/views/export_pdf.py` (Brick 12)
- `src/dashboard/utils/csv_exporter.py`, `src/dashboard/views/export_csv.py` (Brick 13)
- `src/database/ml_schema.py`, `src/utils/ml_inference.py` (Brick 16)
- `airflow/dags/ml_scoring_daily.py`, `airflow/debug_dag/debug_ml_scoring.py` (Brick 16)
- `src/dashboard/views/trigger_algo.py`, `src/dashboard/views/ml_performance.py` (Brick 17)
- `scripts/create_missing_tables.sql` — 16 missing tables added

**Why:** Complete P2 (error handling, tests, monitoring) and P3 (exports, ML) bricks from the roadmap.

**Decisions:**
- XGBoost loaded directly from `.ubj` files (not mlflow runtime) — avoids mlflow server dependency
- WeasyPrint with graceful HTML fallback when PDF generation fails
- Tests mock DB connections via `conftest.py` fixtures — avoids live DB requirement for CI

**Status:** 15/17 bricks complete. P2 done. P3 done. Bricks 14–15 (FastAPI + Railway) outstanding.

**Blockers:** SoundCloud + Instagram credentials expired; `meta_campaigns` schema incomplete.

---

## 2026-03-12 — Session: Dashboard bug fixes + useful_links + airflow_kpi logs

**Changed:**
- `src/dashboard/utils/pdf_exporter.py` — fixed `WHERE is_active = TRUE` (column is `active`)
- `src/dashboard/utils/kpi_helpers.py` — fixed table references
- `src/dashboard/utils/csv_exporter.py` — fixed date columns
- `src/dashboard/views/useful_links.py` — new view (5 tabs, static links)
- `src/dashboard/views/airflow_kpi.py` — added "Logs par Run" tab
- `src/dashboard/views/home.py` — DAG status cards
- Multiple views — fixed `use_container_width` deprecation warning

**Why:** Post-test audit revealed 9 bugs across exporter utilities; useful_links and airflow log viewer requested by user.

**Decisions:** `scripts/create_missing_tables.sql` as a migration script (not re-running init_db.sql)

**Status:** ✅ Bugs fixed. Dashboard operational.

---

## 2026-03-23 — Configuration restructuring

**Changed:**
- `CLAUDE.md` — rewritten to ≤200 lines, English only, removed coding standards
- `.claude/hooks/session_summary.py` — added Step 4 (pytest runner), English comments
- `.claude/skills/` — created 4 skill files (dashboard-view, airflow-dag, db-schema, response-protocol)
- `.claude/agents/` — created 4 agent definitions (strategic-plan-architect, code-architecture-reviewer, build-error-resolver, web-research-specialist)
- `.claude/hooks/hook.md` — created hook documentation
- `.claude/commands/review-architecture.md`, `run-tests.md` — 2 new slash commands
- `.claude/scripts/run_tests.sh`, `check_env.py` — automation scripts
- `.claude/dev-docs/architecture.md`, `retro.md`, `roadmap/checklist.md` — created

**Why:** CLAUDE.md was 204 lines with French text and mixed concerns. Modular skills/agents/hooks structure enables progressive disclosure and avoids loading all context at once.

**Decisions:**
- Skills inject on keyword detection (reuse existing inject_context.py pattern)
- session_summary.py extended (not replaced) to preserve existing git/Docker logic
- CLAUDE_CODE_GUIDE.md archived (not deleted) — may contain patterns not yet fully migrated

**Status:** ✅ Restructuring complete. All hooks remain operational.

---

## 2026-03-27 — Brick 23: Meta Ads API collector + data-quality fixes

**Changed:**
- `src/collectors/meta_ads_api_collector.py` — new MetaAdsApiCollector using facebook_business SDK. Reads credentials from DB (`platform='meta'`, key `account_id`). Fetches campaigns / adsets / ads / insights. Results = `link_click + offsite_conversion.custom` only. CPR/CPC = None when denominator=0. `lp_views` extracted from actions array.
- `airflow/dags/meta_ads_api_daily.py` — new DAG `meta_ads_api_daily`, schedule `0 5 * * *`, iterates active artists, skips artists without Meta credentials.
- `airflow/debug_dag/debug_meta_ads_api.py` — 4-step debug script with `--write` flag.
- `migrations/012_meta_ads_api.sql` — backfill `artist_id`, fix `meta_insights` UNIQUE, dedup performance tables, add missing columns to `meta_adsets`.
- `src/transformers/meta_insight_csv_parser.py` — CPR/CPC = None when denominator=0; compute CPR from spend/results when column blank.
- `src/collectors/meta_insight_watcher.py` — `artist_id` guard + raise in except block.
- `src/database/meta_ads_schema.py` — `meta_insights` UNIQUE now `(artist_id, ad_id, date)`.

**Why:** CSV-only pipeline had 4 data-quality issues: (1) `meta_insights` UNIQUE constraint missing `artist_id` → cross-artist collision; (2) CPR/CPC computed as 0 instead of None on zero denominator; (3) CPR column left blank when API omits it; (4) manual CSV export is error-prone and not daily. Adding a direct API path eliminates the manual step and fixes the root causes.

**Decisions:**
- Keep both ingestion paths (API daily + CSV manual fallback) writing idempotently to the same tables. Trade-off: two code paths to maintain vs. zero data loss if API credentials are absent for an artist.
- CPR/CPC = None on zero denominator instead of 0 — prevents divide-by-zero distortion in aggregations without hiding valid zero-spend rows.
- `meta_adsets` schema extended with `optimization_goal`, `billing_event`, `daily_budget`, `lifetime_budget`, `end_time`, `targeting` — necessary to surface budget pacing in the dashboard.

**Status:** API collector verified working via `debug_meta_ads_api.py`. Migration `012_meta_ads_api.sql` applied. DAG `meta_ads_api_daily` ready to unpause in Airflow UI (http://localhost:8080).

**Meta rate limit gotcha**: Meta developer dashboard shows app-level quota (percentage), but code 17 / subcode 2446079 is a separate per-ad-account hourly call rate. Two consecutive manual full runs triggered it. Mitigated with `_meta_list()` retry + `--insights-only` flag for repeated manual runs.

**Breakdown table schema mismatch**: `_extract_perf()` returns all perf fields (frequency, cpm, cpc, ctr, lp_views) but breakdown tables (_age, _country, _placement) only store (spend, impressions, reach, results, cpr). `upsert_many` uses all dict keys for INSERT → column-not-found error. Fix: trim rows to allowed columns before upsert in `_upsert_all`.

**Two-tier quota**: meta_ads table needed 3 schema additions (title, body, call_to_action); meta_adsets needed 10 targeting decomposition columns. Both tables were created from CSV watcher schema, which predated the API collector full-rewrite scope. Migration 013 fixes this idempotently.

---

## 2026-03-28 — Meta CAPI funnel + perf monitor + deploy prep

**Changed:**
- `src/collectors/meta_ads_api_collector.py` — `_RESULT_ACTION_TYPES` réduit à `{'offsite_conversion.custom'}` seulement. `link_click` retiré : causait un double comptage (fan qui clique l'ad ET le bouton Spotify = 2 résultats). `custom_conversions` ajouté comme champ explicite. `results = custom_conversions` (alias backward-compat). CPR = `spend / custom_conversions`.
- `migrations/017_meta_custom_conversions.sql` — `ADD COLUMN custom_conversions INT DEFAULT 0` sur 5 tables performance. Appliquée.
- `src/dashboard/views/meta_ads_overview.py` — Section 1b "Funnel Hypeddit" ajoutée : funnel chart Plotly (impressions → link_clicks → lp_views → custom_conversions), taux de conversion par étape, tableau par campagne. Query temporelle mise à jour (`custom_conversions`). Tableau récapitulatif enrichi (`lp_views`, `custom_conversions`). CPR corrigé sur dénominateur `custom_conversions`.
- `src/dashboard/views/perf_monitor.py` — Nouvelle vue admin : render time Streamlit (rolling 100, sparkline colorée), DB ping, RAM + CPU process (psutil), seuils d'alerte (vert/orange/rouge), tableau summary par page.
- `src/dashboard/app.py` — Timer `time.perf_counter()` injecté autour de tout le routing. Log stocké dans `st.session_state._perf_log`. Route + nav `perf_monitor` enregistrés.
- `requirements.txt` — `psutil>=5.9.0` ajouté.
- `tests/test_collectors_errors.py` — 6 tests cassés corrigés : SoundCloud fixture + `_access_token`/`_token_expires_at`; Instagram fixture + `session`.
- `tests/test_meta_ads_collector.py` — 15 nouveaux tests sur `_extract_perf` et `_extract_eng` : no double-counting, CPR/CPC None sur dénominateur 0, lp_views, artist_id, multiple conversions, types inconnus ignorés.

**Why:** (1) Double-counting CPR détecté lors de la discussion CAPI Hypeddit — `link_click` + `offsite_conversion.custom` = un fan comptabilisé 2 fois → CPR sous-estimé artificiellement. (2) Funnel nécessaire pour voir le taux LP→Spotify qui détermine la qualité de la landing page Hypeddit. (3) Perf monitor pour anticiper la limite Streamlit (>3s = migration React) avant d'avoir 50+ artistes.

**Decisions:**
- `results` conservé comme alias de `custom_conversions` pour backward-compat (CPR Optimizer, Meta × Spotify queries non modifiées).
- Données historiques `custom_conversions = 0` — impossible de rétrospectivement isoler la part `offsite_conversion` dans l'ancien `results` gonflé. Acceptable.
- CAPI Hypeddit derrière paywall : configuré ultérieurement. Funnel fonctionne sans CAPI (3 étapes visibles, 4ème masquée avec message info).
- Perf monitor session-only (pas de table DB) : suffisant pour monitorer en local et en prod légère. Persistance DB différée à Phase 2 (Hetzner).

**Status:** Migration 017 appliquée. Tests : 154 passed → 169 passed, 0 failed. CI vert.

---

## 2026-03-27 — Brick 24: Instagram + Meta System User token migration

**Changed:**
- `meta_token_refresh.py` — `expires_at IS NULL` now skips token instead of refreshing unconditionally.
- `instagram_daily.py` — precheck error message updated to reference Business Manager → System Users.
- `credentials.py _guide_meta()` — added Instagram scopes section; clarified System User token behavior.
- `meta-ads-credential-guide.md` — added Instagram scopes to Step 3; added token refresh behavior table.

**Why:** Two findings during Brick 24 scoping: (1) iMusician has no public API on any plan including Pro — automating that source is not possible; closed as not automatable. (2) `meta_token_refresh` DAG had a latent data-integrity bug: `expires_at IS NULL` was interpreted as "never refreshed → refresh now", but `fb_exchange_token` silently fails on System User tokens and would have written a corrupted (empty or error) token back to the DB, breaking all subsequent Meta API calls for that artist.

**Decisions:**
- iMusician API investigation: ❌ not automatable. Saved several hours of building against a non-existent API. Source stays CSV-only indefinitely.
- Skip NULL `expires_at` on token refresh rather than treating it as an edge case to handle. System User tokens never expire; an exchange attempt produces an error response, not a refreshed token.

**Post-mortem — `meta_token_refresh` bug:**
- Root cause: `expires_at IS NULL` guard was written for personal user tokens that had never been through a refresh cycle. System User tokens were added in Brick 23/24 without updating the NULL-handling branch.
- Should have been caught during Brick 23 when System User credential support was introduced. Detection gap: no test covers the `expires_at IS NULL` branch specifically.
- Fix: unconditional skip on NULL. Low risk — System User tokens do not expire.

**Status:** ✅ Token refresh fix applied. Instagram scope guidance added to credential guide and in-app helper. No migration required.
