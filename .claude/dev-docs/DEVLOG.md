# DEVLOG

---

## 2026-06-11 — Passe d'optimisation pré-déploiement (perf DB/dashboard/DAG + durcissement sécurité)

Session dédiée (branche `chore/pre-deploy-optimizations` = PR #21, 4 commits), à la suite d'un audit 3-agents (frontend / backend / security specialists).

**Perf DB** (`057_composite_artist_date_indexes.sql`, NEW) — 5 index composites `(artist_id, date)` sur les tables hot-path les plus scannées. Côté code, `get_monthly_roi_series` (`kpi_helpers`) faisait **deux scans** de `v_artist_monthly_revenue` → fusionnés en une seule requête `FILTER`.

**Perf dashboard** — `get_artist_plan` était une **connexion DB fraîche à chaque rerun** de la sidebar → `@st.cache_data(ttl=60)`. Les blobs d'export PDF/CSV stockés en `session_state` sont **libérés à la navigation** (`_render_page`, `app.py`) au lieu de persister en mémoire. Le Booster XGBoost + artefacts JSON sont **mémoïsés** dans `trigger_algo/_common/_loaders.py` (était rechargé/désérialisé à chaque scoring).

**Perf DAG** — `meta_token_refresh` ouvrait une connexion `psycopg2.connect` **par artiste dans la boucle** → une seule connexion réutilisée.

**Durcissement sécurité** (cap D0 déploiement) — `docker-compose.yml` : mot de passe DB (3 occurrences en dur retirées) + creds admin Airflow désormais via `${VAR}` ; Postgres/Airflow **bindés sur `127.0.0.1`** (plus exposés sur `0.0.0.0`). `src/api/auth.py` : secret JWT aléatoire éphémère (plus de fallback connu du repo). `src/api/main.py` : `/docs`+`/redoc` **off par défaut** (gated `API_ENABLE_DOCS`), CORS lu depuis l'env. `stripe_webhook.py` : **fail-closed** sur payload non signé. Ajouts : `.env.example` + checklist ops D0 dans `deployment.md`. Test `test_api_security` verrouille le défaut docs-off.

**Deux findings d'audit volontairement NON actionnés** (tracés ici pour ne pas les redécouvrir) :
- `src/collectors/s4a_csv_watcher.py::S4AWatcher` est **du code mort** (rien ne l'importe ; le DAG live a son propre chemin `upsert_many`) → flaggé pour **suppression**, pas patché (ne pas durcir du code à supprimer).
- Les `db.close()` manquants dans les DAGs sont **mitigés par l'isolation process par-tâche** du LocalExecutor Airflow (chaque tâche = process éphémère, fd libérés à la sortie) → **dépriorisé** P4.

**Prochaine étape** : merger PR #21, puis reprendre C5/C6 (sizing VPS + domaine/accès).

---

## 2026-06-11 — Mapping cross-plateforme unifié, SACEM, revenu consolidé en VIEW, nettoyage i18n + split meta_mapping

Session pré-déploiement (branche `feat/mapping-merge-suggestions` = PR #19). 521 tests verts, ruff clean.

**Mapping cross-plateforme — consolidation en une seule vue 2 onglets** (`meta_mapping`). Fusion de l'ex-`track_mapping` (titres cross-plateforme) et du mapping campagnes Meta : onglet « 🎵 Titres & couverture » (suggestions toutes-plateformes sans sélecteur + grille de couverture ✅/· verte) + onglet « 📣 Campagnes Meta » (suggestions auto, backlog, ajout manuel/existant). **Bug confiance « toujours 0 % » corrigé** : un `ProgressColumn(format="%.0f%%")` applique le format à la valeur brute [0,1] → `0.14` rendait « 0% ». Fix = colonne d'affichage ×100 (`min/max_value=0..100`), la valeur DB reste en [0,1]. Cases vertes ✅ au lieu de « - ». Campagnes à **0 € dépensé pré-cochées Rejeter** (jamais une vraie promo → tombstone `campaign_mapping_rejected`, mig 054). Suggestions auto liées au vrai mapping Meta×Spotify (écrit `campaign_track_mapping` en `_`-form, clé de join `meta_x_spotify`).

**SACEM — nouvelle source de revenus** (royalties société de gestion). Parser `src/transformers/sacem_parser.py` (xlsx « relevé de compte », `classify_line`/`parse_sacem_xlsx`/`is_sacem_statement`), table `sacem_statement` (mig 055), intégré à l'Import CSV (uploader `.xlsx` + how-to : SACEM › Mes répartitions › Relevé de compte › filtre date › télécharger). Les lignes `repartition` (royalties brutes, 43,06 €/3 ans) entrent dans le ROI Breakeven ; évolution mensuelle SACEM visible en **trace distincte** sur le graphe prévision revenus + KPI par source.

**Revenu mensuel consolidé en VIEW Postgres** (`v_artist_monthly_revenue`, mig 056) — l'UNION iMusician + DistroKid + SACEM (`repartition`) était copiée-collée dans ~6 endroits (`kpi_helpers`, `revenue_forecast`, `imusician`). Une seule source `(artist_id, year, month, source, revenue_eur)` ; tous les consommateurs repointés. VIEW en lecture seule → **hors `_ALLOWED_TABLES`** (jamais d'upsert). Vérifié cohérent : 254,96 € total (211,90 iMusician + 43,06 SACEM).

**Dépense « Hypeddit » fantôme retirée du ROI** — les 2 431,50 € venaient de `SUM(hypeddit_daily_stats.budget)`, mais ce budget EST la dépense Meta Ads (mal interprétée). La seule dépense Hypeddit réelle est l'abonnement 10 €/mois. Ligne retirée de TOUS les points ROI (`kpi_helpers`, `imusician` metrics/chart/caption, `billing.feat_roi`) ; `total_spend = meta_spend` seul. Le mapping Hypeddit et la vue analytics Hypeddit restent intacts.

**Nettoyage / outillage**
- **Garde-fou i18n orphelins** (`tests/test_i18n_orphans.py`, NEW) — sens inverse de `test_every_static_t_key_has_en_entry` : flag toute clé EN jamais référencée par un `t()` (features supprimées/renommées laissant des traductions mortes). 43 orphelines retirées (legacy `track_mapping`/`common`, clés `*.invalid_session`/`*.db_unreachable` mortes depuis l'adoption des clés partagées `ui.*` via `view_session()`).
- **`meta_mapping.py` (551 l) → package** (move-only, comportement préservé) : `_common.py` (helpers partagés `_load_canonical`/`_mutex_checkboxes`), `_tracks.py` (onglet titres+couverture), `_campaigns.py` (onglet campagnes Meta), `__init__.py` (`show()` + 2 onglets). Précédent : `trigger_algo/`, `credentials/`, `pdf_exporter/`.
- **Billing Free enrichi** : SACEM + mapping cross-plateforme + ROI unifié surfacés comme value-adds gratuits ; bullet Premium « Road to Algo » détaillé (leviers ML → playlists algorithmiques Spotify : Discover Weekly, Release Radar, Radio). Toggle langue FR/EN sur la page de login (restitué dans l'app + PDF). VPS infra = admin-only (retiré de la vue artiste). `alerts` ajouté à `_ADMIN_ONLY`.
- **CI déterministe** : service Postgres non-provisionné retiré du workflow (les tests DB skip déjà) ; corrige le flake de pull `postgres:17`. Effet de bord corrigé : `get_db` tolère une connexion `None` (`if db is not None: db.close()`).

**Prochaine étape** : merger PR #19 dans `main`, puis reprendre C5/C6 (sizing VPS + domaine/accès).

---

## 2026-06-10 — i18n complète + PDF bilingue, feature ML manuelle, refactors god-modules + harness Meta, CI, PR mergée

Grosse session (PR #14 mergée dans `main`, merge commit `6d213e3`). 437 tests / 2 skipped, ruff clean, CI verte, backup tag `pre-godmodule-refactor`.

**i18n EN/FR — couverture totale (C4 ✅)** : ~47 catalogues `i18n_catalog/`, ~2300 clés. Toutes les vues + packages `trigger_algo`/`credentials` + ml_widgets + guides credentials + coaching ML. **PDF bilingue** (corps + charts matplotlib) piloté par un `lang` explicite (`i18n.translate(key, default, lang)`, découplé de `st.session_state` → testable/headless). FR reste octet-identique (golden test) ; EN = capacité nouvelle. Garde-fou étendu : `test_every_static_t_key_has_en_entry` couvre `t()` ET `_t()`.

**Feature ML — un-imputation des 2 dernières features** : `NonAlgoStreams28Days` + `HowManySongsDoYouHaveInRadioRightNow` (codées en dur à 0) → saisies dans **Saisie S4A** (migration **052** : `s4a_song_nonalgo_streams` + `s4a_artist_radio_count`), lues par `ml_inference`. Contrat 13-features inchangé → pas de retrain. Validé end-to-end (saisie → DB → scoring). **ADR-004** : capture auto S4A rejetée (pas d'export ; scraping = ToS/credential-risky) → saisie manuelle retenue.

**Refactors (tous move-only, comportement préservé)** :
- `pdf_exporter.py` (1734 l) → package (config/collectors/renderers/report) — golden test prouve l'octet-identique. Bug attrapé par le golden : `_ASSETS = Path(__file__)...parent.parent` cassé au déplacement du module (asset path) → +1 `.parent`.
- `trigger_algo/_common.py` (1171 l) → package (loaders/pi_gates/lifecycle/budget_roi/explain/verdict).
- **`meta_ads_api_collector.py` (1178 l) → 201 l + 6 modules** (helpers `_meta_retry`/`_meta_parsers` + mixins ConfigFetch/InsightFetch/Upsert). Rule #6 préservée (15 raises). Gated par un **harness de caractérisation** (`tests/fakes/meta_sdk.py` stub SDK + 17 tests pinning `run()`) → futures modifs API Meta vérifiables sans tokens. **Validé par collecte live réelle** (13 tables écrites, upsert idempotent).
- 13 vues → context-managers `view_session()`/`project_db()` (helpers rendus i18n-aware).

**CI — 3 causes d'échec récurrent corrigées** : render-smoke skip-gate rendu schema-aware (Postgres CI vide), dummy `AIRFLOW_PASSWORD` pour l'import d'`app.py`, fixture distrokid skip-si-absente. + garde-fou `test_db_table_allowlist` (attrape une table absente de `_ALLOWED_TABLES` au PR — le bug qui a shippé et planté la saisie en prod).

**Audit Stripe** : code plombé (Payment Link + webhook FastAPI + portail + schéma) mais **rien d'actif** (`artist_subscriptions`=0, 4 env vars vides, API non déployée). → activation parquée en phase D (cf. checklist). Bouton « Premium » = placeholder aujourd'hui.

**Roadmap** : C4 ✅, Phase-2 ✅ (closed-as-manual, ADR-004). C5 (sizing VPS) + **C6 (domaine/accès, NEW)** : questions ouvertes notées pour 2026-06-11.

---

## 2026-06-09 — Pricing 2-tier, B1 cross-platform mapping, robustness (B3/C1/C2), i18n infra

**Tarification → 2 tiers (free 0€ / premium 10€)** — `basic` retiré, fusionné dans premium.
- Source unique `PLAN_FEATURES` + `PLAN_CATALOG` dans `stripe_schema.py` ; `normalize_plan()`
  rabat tout `basic` résiduel sur premium. `billing.py`/`upgrade.py`/`auth.py`/`revenue_forecast.py`
  lisent le catalogue (fin du drift de prix sur 4 sources). Migrations **047** (alignement
  prix/features) + **048** (basic→premium + désactivation plan basic).
- **Bug latent corrigé** : `saas_artists.tier` avait `DEFAULT 'basic'` + `CHECK IN('basic','premium')`
  → rejetait `'free'` (register.py insère `tier='free'`) et aurait donné premium en fallback
  post-essai. Migration 048 : `DEFAULT 'free'` + `CHECK IN('free','premium')`.
- Export PDF → free ; revenue_forecast → premium. CTA contact (optim. campagnes) sur billing/upgrade.

**Export PDF — leak paywall corrigé** : un free pouvait inclure les sections ML/prévisions/Meta
avancé. `PREMIUM_SECTIONS` (pdf_exporter) → verrou UI + strip à la génération pour non-premium.

**Admin — onglet 📊 Supervision** : business (MRR/ARPU/inscriptions) + fraîcheur données par
plateforme (révèle Meta 617j / Apple 180j obsolètes).

**B1 — Mapping cross-plateforme + suggestions** (LIVRÉ) : migration **049** (`track_platform_link`
+ provenance sur `campaign_track_mapping`), moteur pur `src/utils/track_mapping_suggest.py`
(`title_similarity` containment 0.90 / remix-disagreement 0.0, `date_proximity` halflife 14j ;
+15 tests), vue `views/track_mapping.py` 3 onglets (suggestions par plateforme S4A/Spotify/Apple/
SC/YT, Meta campagnes title+date, vue unifiée). `track_name` stocké en `_`-form (`canonical_song`)
pour matcher `s4a_song_timeline.song` (join meta_x_spotify).

**Robustesse** :
- **B3** : `track_mapping`+`meta_mapping` migrés vers `view_session()` (rule #7).
- **C1** : `utils/error_alert.py` (`notify_app_error` fail-silent, rate-limité, email admin) ;
  dispatch des vues extrait en `_render_page()` + guard try/except dans `app.py` — **re-raise des
  signaux Streamlit** `RerunException`/`StopException` (sinon nav cassée). +4 tests.
- **C2** : `tools/db_backup.sh` (pg_dump→gzip+rétention) + `tools/db_restore_test.sh` (drill) +
  `make backup`/`backup-test`. Drill validé (78 tables, 13794 lignes restaurées). Cron = Phase D.

**C4 — i18n EN/FR (infra)** : `utils/i18n.py` (`t()` FR-source/fallback EN), toggle sidebar,
navigation entièrement traduite (titre+8 sections+35 items), +5 tests (garde-fou trad EN).

**Emails onboarding** (début de session) : welcome+guide PDF à la **vérification** (pas signup),
guide PDF = **API+CSV** (renommé `onboarding_guide.pdf`, réutilise `credential_guides` + screenshots),
DAG `onboarding_report` (1er rapport post-collecte S4A), lien désinscription HMAC, `APP_BASE_URL` env.

**Docs/roadmap** : `deployment.md` créé (programme déploiement différé), `checklist.md` section
« Pré-déploiement program A→B→C→D », `architecture.md` (2-tiers). Graphify régénéré
(2692 nœuds/5248 edges). **384 tests verts**, ruff clean.

---

## 2026-06-08 (suite) — Onboarding merge-back, shared-app credentials, windowed S4A entry, PDF redesign

### Why
The earlier half had split onboarding into standalone pages (Process-Credentials, Process-Import,
Réglages). On review they read as doublons — the how-to belongs next to the action, not on a separate
page. In parallel: the SoundCloud/Meta credential forms wrongly asked artists for the shared *app*
secrets; playlist-adds were a single cumulative count (wrong for manual windowed S4A figures); and the
client-facing PDF looked nothing like the app it summarises.

### What changed
**(a) Onboarding merged back inline (refactor)** — dropped `process_credentials.py`,
`process_import.py`, `reglages.py` (all created earlier this session, removed in `ed9e688`). The rich
guides now render at point of use: per-platform tab in Credentials, full download guide above the CSV
uploader. Manual entry (playlist adds + Discovery Mode) went back to `_tab_global.py` inline expanders,
then to a dedicated Saisie S4A grid (see (c)). Lesson: keep manual entry + how-to inline in the
actionable page; one content module rendered in-place beats a standalone view.

**(b) Credentials overhaul + shared-app model** (`8d17fb3`, `53ca6d8`) — new single-source content
modules `src/dashboard/content/credential_guides.py` + `credential_guides_st.py` (Spotify, YouTube,
SoundCloud, Meta: steps, 9 screenshots under `assets/credential_guide/`, clickable URLs, example
values), rendered per-platform tab via `credentials/_render.py` (replaces the old prose `_guide_*`).
Shared-app: a SoundCloud artist provides only `user_id`, a Meta artist only the Ad Account ID; app
creds come from env (`SOUNDCLOUD_CLIENT_ID/SECRET`, `META_ACCESS_TOKEN/APP_ID/APP_SECRET`) via an
ADDITIVE fallback in `meta_ads_api_collector._load_credentials` + the connection tests (`_test_soundcloud`,
`_test_meta`) — **stored per-artist creds still win**, so existing tenants are unchanged; forms reduced
in `_registry.py`. Instagram stays admin/env. New admin "🔑 Tokens" reference tab (token type / expiry /
refresh / artist-vs-admin action per platform) — makes explicit that no recurring token action is
required by anyone; token lifecycle moved out of the artist view.

**(c) Windowed playlist adds + Saisie S4A grid** (`5c9f605`) — migration 044: `s4a_song_playlist_adds`
gains `time_window` (7d/28d/12m/custom) + `period_start`/`period_end`; PK now
`(artist_id, song, time_window, recorded_at)`. Was a single cumulative count summed over 28 days —
wrong for manual windowed entry. New page `views/saisie_s4a.py`: a bulk `st.data_editor` grid
(row/track × 7j/28j/12m + Discovery Mode) with grouped save, plus a custom date-range section
(`period_start`/`end`, `recorded_at=period_end`) for the first days after a release. `ml_inference`:
`PlaylistAddsLast28Days` now reads the latest `'28d'` snapshot (not SUM-last-28-days). Vue Globale
playlist/Discovery tiles are read-only (28d snapshot) and point to Saisie S4A.

**(d) Nav** (`14e5270`) — Saisie S4A placed above Road to Algo (Prédiction algos section); Export PDF
promoted right after Accueil.

**(e) Export PDF visual redesign** (`175c07a`, `fe839e7`) — new `src/dashboard/utils/pdf_charts.py`:
matplotlib → base64 PNG (NO new dependency — kaleido is absent so plotly→png is not used) for streams
timeline, platform breakdown, ML trigger probabilities, ROI vs spend. `pdf_exporter.py`: branded
full-page cover (artist, period, 4 headline KPIs), modern CSS (cards, `@page` counters, page-breaks), a
"Dernière sortie" spotlight using the latest release's probability chart, charts embedded in
Streams/ROI sections. **Emoji stripped from the final HTML** before `write_pdf` (WeasyPrint base fonts
have no emoji glyphs → tofu). New "Depuis le début" (all-time) period option. `export_pdf.py`: all
sections checked by default; song selectors auto-focus the latest release (`_latest_release`).
Regenerated the byte-exact golden `tests/fixtures/pdf_report_golden.html` since the HTML changed.

### Tests
350 passed, 1 skipped. Migration 044 added (idempotent). Only 044 is new to this half (042/043 landed
in the earlier half).

---

## 2026-06-08 — CSV import audit + canonical_song join fix + Réglages split + Phase-2 live validation

### Why
The Apple CSV upload always crashed (dead method name), several CSV paths reported zero-row
SUCCESS instead of failing, and exact-match title joins silently dropped every `?`-titled track
(filename-derived tables carry `_`, CSV/API tables keep the real char). With 13 fresh S4A files
imported, this was also the first chance to validate the v3 model end-to-end on live data.

### What changed
**(a) Réglages view split** — new `src/dashboard/views/reglages.py` ("⚙️ Réglages — Saisie
manuelle"): the two manual-entry forms (playlist adds → `s4a_song_playlist_adds`, Discovery Mode
→ `s4a_song_discovery_mode`) moved out of trigger_algo Vue Globale; `_tab_global.py` keeps the
read-only tiles + a pointer caption. Nav entry under "📁 Données" + routing in `app.py`; added
`reglages` to `tests/test_views_render_smoke.py`.

**(b) CSV import audit (Phase 1) + P1/P2 hardening** — `upload_csv.py`: Apple branch called the
non-existent `AppleMusicCSVParser().parse()` (always crashed) → `parse_songs_performance()` +
per-row `artist_id` injection. `s4a_csv_watcher` + `apple_music_csv_watcher`: removed the
`try/except → 'skip_processing'` in `check_for_new_csv` so a scan failure FAILS (retry +
callback) instead of a silent zero-row SUCCESS. `s4a_songs_global` upsert conflict key now
includes `time_window` (+ best-effort `rebuild_release_reference`; note: the DAG `parse_csv_file`
path is timeline-only, upload UI is canonical for songs_global). `_detect_window` now raises on an
unmarked filename instead of defaulting to `'12m'`. iMusician parser: required-column check
hoisted out of the row loop (`_require_cols()` fail-fast) — was caught per-row → 0 rows + SUCCESS.
Apple history: per-row DELETE+INSERT → atomic `ON CONFLICT DO UPDATE` (migration 042 adds the
UNIQUE key). Naive `datetime.now()` → `datetime.now(timezone.utc)` in apple + imusician parsers +
apple DAG.

**(c) song-name-convention-mismatch (new error class)** — new single-source `canonical_song()` +
`canonical_song_sql()` in `src/utils/track_matching.py` (covers the full Windows-reserved set,
preserves accents/remix). Applied write-side in `parse_songs_global` and query-side in
`_tab_algos.py` (PI ×4), `meta_cpr_optimizer.py`, `router.py` (×3, replacing ad-hoc
`REPLACE(...,'?','_')`). Migration 043 backfills `s4a_songs_global` + `s4a_song_saves_daily`.
Guard: `tests/test_song_canonical.py` (5 tests); class catalogued in `error-classes.md`.

**(d) Phase-2 end-to-end validation** — user imported 13 fresh S4A files (11 timelines to
2026-06-07 + audience + songs-1year). Re-ran `ml_scoring_daily` → `ml_song_predictions` now carries
model_version `v3` with non-NULL DW/RR/Radio probs for 11 songs (was v1_noscaler/NULL); Vue Globale
streams 28j + score /20 + probas populate. Low probs (~7% DW/RR, ~11% Radio) are honest — tracks at
100–250 streams/28d, far below the ~4–9k thresholds.

### Tests
344 passed, 1 skipped. Migrations 042 + 043 added (idempotent).

---

## 2026-05-31 — WAVE 13: drift surface + alert (completes the WAVE 9 drift foundation)

### Why
The WAVE 9 drift foundation (`check_drift`) only logged in the scoring DAG. Completed it — the
buildable long-term fix — and roadmapped the rest (genuinely data-blocked: Phase-2 sources, more
training data, per-tenant eval, automated retraining).

### What changed
- `src/dashboard/views/trigger_algo.py`: `_show_drift_status` in the Explainabilité tab — flags the
  current track's out-of-distribution features (|z|>4) → "prediction extrapolates, less reliable".
- `airflow/dags/alert_monitor.py`: `check_drift_anomalies` task — scans the latest predictions, flags
  SYSTEMIC drift (a feature OOD on >50% of songs = likely pipeline break) into the consolidated email
  (orange section + subject tag).
- `src/utils/ml_inference.py`: `check_drift` now excludes the imputed features (`_IMPUTED_FEATURES`) —
  they are permanently OOD by design (Phase 2), so including them was permanent false-alarm noise
  (caught by the live scan: NonAlgoStreams flagged on 11/11 → now correctly excluded).
- Roadmap: drift surface/alert marked done; added "Discovery Mode manual input" (cheapest Phase-2 win)
  and "Automated retraining on live outcomes"; Phase-2 imputed list down to 2 features.

### Tests
285 passed, 1 skipped. Drift scan smoke-tested on live DB (clean after excluding imputed features).

---

## 2026-05-31 — WAVE 12: PI on the main algos chart + 28-day streams/listeners gate

### Why
Verifying the user's paper notes: ROI/actual-vs-predicted/residuals/PI-breakeven already exist. The only
gap was the combined chart lacking the PI line and the 28-day streams/listeners gate. User-supplied DW
thresholds (9200 streams / 4100 listeners per 28d) were validated against data_anon.csv (both sit in the
bin where the DW success rate jumps above base). Per-algo derived: DW 9200/4100, RR 1300/600, Radio 8400/4000.

### What changed
- `src/dashboard/views/trigger_algo.py`:
  - `_show_tab_algos` main chart: added the Popularity Index line (track_popularity_history, per-track
    daily) on the secondary axis (PI 0-100 shares the probability scale) → one chart with streams + PI +
    the 3 trigger probabilities.
  - `_GATE_28D` constant + `_show_28d_gate`: the track's 28d streams/listeners (s4a_songs_global snapshot)
    vs the per-algo validated thresholds, ✓/✗ per algo. Per-song listeners only exist as a 28d snapshot
    (no daily series), so a gate panel rather than a chart line.

### Tests
285 passed, 1 skipped. PI + gate queries smoke-tested on live DB (artist 1). No retrain → baseline unchanged.

---

## 2026-05-31 — WAVE 11: ML KPI gaps (LIME + Meta-lever scoring + calibrated budget + PI breakeven)

### Why
The user listed 7 ML graphs to "integrate" — but 6/7 already existed in trigger_algo.py (score /20,
streams+probabilities, SHAP waterfall, ROI regression, actual-vs-predicted+residuals, breakeven). Only
4 real gaps remained: LIME, marketing levers tied to REAL Meta data, hardcoded budget targets, PI not
central to breakeven.

### What changed
- `src/dashboard/views/trigger_algo.py`:
  - Budget tab: `_TRIGGER_STREAM_TARGETS` (RR 417 / DW 1333 / Radio 8423, SHAP Class-1 volumes) replaces
    the hardcoded 1k/10k — 3 per-algo "budget to trigger" estimates.
  - `_show_pi_breakeven`: surfaces the PI gate each algo needs vs the current pi_forecast_7d (PI now
    central to break-even, not a decorative overlay).
  - `_show_meta_lever_scoring`: joins the track's mapped campaigns (campaign_track_mapping) to real Meta
    perf (meta_insights_performance CPR/CTR/results) + ads' call_to_action — ranks which lever/CTA
    actually performed. Reuses the meta_cpr_optimizer join pattern.
  - `_show_lime_explanation`: local LIME explanation for the DW prediction (complements SHAP), graceful
    fallback. Explainability tab signature now takes db + artist_id.
- `machine_learning/train.py`: exports lime_background.json (508×13 training feature sample).
- `pyproject.toml` / `requirements.txt`: add `lime>=0.2.0`.

### Tests
285 passed, 1 skipped. LIME + Meta-lever queries smoke-tested on live DB (artist 1). Baseline unchanged.

---

## 2026-05-31 — WAVE 10: empirical threshold reconciliation + phase/Discovery-Mode/importance features

### Why
A new batch of the user's SHAP notes contradicted each other AND the encoded algo_knowledge zones
(velocity, saves, ratio, catalogue, organic). Rather than arbitrate between conflicting human notes,
the thresholds were re-derived from data_anon.csv. Plus 3 new decision features the registry lacked.

### What changed
- `machine_learning/derive_thresholds.py` (NEW) — per algo/feature success-rate knees from the training
  data (built with the exact inference feature definitions). Output: thresholds_derived.json.
- `src/dashboard/utils/algo_knowledge.py` — 5 DW zones recalibrated to the data:
  Velocity (the old (1.2,5,malus) wrongly penalised the healthy 1.2-2.0 zone → now neutral, malus only
  >3.5); Saves (bonus 50→165); NonAlgoStreams (5000→~3900); PlaylistAdds (200→175); Followers bonus
  (1600→2650); ListenersStreamRatio malus (2.2→1.6). `velocity_penalty_threshold("DW")` now 3.5.
- `src/dashboard/views/trigger_algo.py` — `_show_phase_strategy` (Phase 1 RR / 2 DW / 3 Radio by age +
  the phase's action), `_show_discovery_mode_protocol` (activate/kill-switch), `_show_feature_importance`
  (ranked 13-variable hierarchy per algo).
- `machine_learning/train.py` — exports feature_importance.json (gain per classifier). Gain top-3 for DW
  (StreamsLast7Days, NonAlgoStreams, DaysSinceRelease) matches the user's SHAP hierarchy.

### Tests
285 passed, 1 skipped. Baseline unchanged (same seed). Recalibration smoke-tested (velocity@1.5 now neutral).

---

## 2026-05-31 — WAVE 9: ML hardening — calibration + drift foundation + resurrection alert activation

### Why
The verdict banner shipped 20/50% decision bands on UNCALIBRATED probabilities (a heuristic, not
real likelihoods). The resurrection detection was built but dormant and unwired. And the model
extrapolates blindly outside its N=508 training envelope with no monitoring. These are the buildable
long-term fixes; the rest (Phase-2 data, more data, per-tenant) are roadmapped.

### What changed
- `machine_learning/train.py` — Platt (sigmoid) calibrator per classifier fit on the held-out test
  split → `calibration.json`; `feature_stats` (mean/std/min/max) exported to metrics.json for drift.
- `src/utils/ml_inference.py` — `_calibrate` applied to the 3 probs in `score_song` (stored probs now
  calibrated); `check_drift` flags |z|>4 features vs training envelope, logged per song in scoring.
- `src/dashboard/views/trigger_algo.py` — verdict caption updated (probs now calibrated, bands real).
- `airflow/dags/alert_monitor.py` — new `check_resurrection_sparks` task scans all artists via
  `detect_saves_resurrection`, adds a green "opportunities" section + subject tag to the consolidated
  email (dormant until saves history accrues).
- Roadmap (`checklist.md`) — "Long-term ML hardening" section: Phase-2 data (highest leverage), more
  training data + per-tenant eval, drift dashboard surface, RR regressor, resurrection tuning.

### Tests
285 passed, 1 skipped. Baseline regenerated (calibrated probs). Calibration + drift smoke-tested.

---

## 2026-05-31 — WAVE 8: scaler-free retrain + PI model + decision layer + resurrection foundation

### Why
The deployed models were trained WITH StandardScaler but inference applied none, so the served
probabilities were structurally wrong (z-score thresholds fed raw values). The user's product notes
also asked for a consolidated decision UI, a budget pacing planner, a snowball radar and a long-tail
resurrection alert. The training data (`data_anon.csv`) was finally copied into the repo, unblocking
a reproducible retrain.

### What changed
- `machine_learning/train.py` (NEW) — reproducible, scaler-free training (replaces the 104 MB notebook).
  Trains 3 classifiers + 3 volume regressors + the PI regressor on EXACTLY the served feature contract
  (raw Saves/PlaylistAdds counts + streams/listeners ratio — the CSV `_adj` cols are unreproducible).
  Verified: DW AUC 0.878→0.937, RR 0.952, Radio 0.936, PI R²=0.937/MAE 1.9 (exact). Models committed
  to `machine_learning/models/v2_noscaler/` (old `mlruns/` was gitignored → prod inference was broken).
- `src/utils/ml_inference.py` — MODEL_VERSION v2_noscaler, PI inference (`pi_forecast`), ReleasePhaseEarly<35,
  velocity train/serve note. `pi_forecast_7d` column added across the 6 synced points (init_db, create_missing,
  ml_schema — caught radio drift, migration 037, DAG update_cols, regen frozen baseline).
- `src/dashboard/views/trigger_algo.py` — B2 "Portes par PI" (threshold_tables.json) + decision layer:
  `_show_verdict_banner` (🔴🟠🟢 kill/optimize/scale on argmax of the 3 probs), `_show_radio_snowball`
  (catalogue scan via radio_probability — bypasses the imputed-0 radio-count feature), `_show_resurrection_radar`
  (dormant), `_show_budget_pacing_calculator` (spread budget over the eval window).
- Resurrection data foundation: `s4a_song_saves_daily` table (init_db + create_missing + `saves_history_schema.py`
  + migration 038 + `_ALLOWED_TABLES`), `src/utils/saves_history.py` (`snapshot_saves` + `detect_saves_resurrection`),
  snapshot wired into `ml_scoring_daily` DAG. Fixed `debug_ml_scoring.py` import (`_MLRUNS_DIR`→`_MODELS_DIR`).

### Tests
285 passed, 1 skipped. Migrations 037 + 038 applied to spotify_etl. Writer smoke-tested (11 rows, artist 1).
Phase-2 data (3 imputed-to-0 features) remains the ceiling on model precision + snowball/resurrection.

---

## 2026-05-31 — WAVE 7: Release Radar volume regressor suppressed (R²=0.32, product-protective)

### Why
The RR volume regressor (MLflow exp 7) was wired in the earlier waves and actively showed a
`rr_streams_forecast_7d` floor in two user-facing surfaces. The user's Release Radar
regression SHAP notes deliver the opposite verdict to DW/Radio: **R²=0.32 = the model finds
logic in noise.** RR volume is driven by notification open-rate (a human/chaotic Friday-morning
factor), not by the algorithm — the SHAP summary is a flat vertical line at zero broken by 2-3
viral outliers, and every lever (followers, recent streams, saves, playlist-adds) is flat. A
real +6000-stream hit was even predicted *negative*. Showing that number to users is a false
financial promise. Product decision: RR ships **classification-only** (AUC 0.96); the volume
forecast is suppressed from every user surface, kept only as admin/diagnostic evidence.

### What changed
**Knowledge (P3, `algo_knowledge.py`):** `ALGO_REGRESSOR_METRICS["RR"]` with
`volume_reliable: False` + `r2: 0.32` + a `suppressed_note` (classification-only caption) +
interpretation. Two new single-source helpers: `volume_forecast_reliable(algo)` (defaults
True, only False when explicitly flagged — no `if algo == "RR"` hardcoding anywhere) and
`volume_suppressed_note(algo)`. **Gated user surfaces (P3):** `trigger_algo._show_ml_section`
passes `None` as the RR forecast and renders the "abonnés notifiés — volume non prédictible"
caption instead; `revenue_forecast.py` drops the `rr_streams_forecast_7d` floor column when
unreliable + reworded caption. **Diagnostics kept honest (P4):** the Modèle-tab RR
Actual-vs-Predicted scatter and the admin `ml_performance` exp 7 artifacts stay, now captioned
"R²=0.32 — diagnostic, PAS une prévision" — the R²=0.32 reality is shown honestly, not hidden.

### Design note
The gate is data-driven, not a hardcoded algo check: any future regressor flagged
`volume_reliable: False` is auto-suppressed by the same helper. Threshold-on-R² was rejected —
DW carries `mrd_pct` (347.99), not `r2`, so a numeric threshold is inconsistent across the
three algos; an explicit boolean is self-documenting. No pipeline change:
`rr_streams_forecast_7d` is still computed and persisted (the diagnostic surfaces read it) —
only *display* is gated.

### Tests
`python3 -m pytest tests/ -q` → **285 passed** (283 prior + `test_volume_forecast_reliability_gate`
+ `test_volume_suppressed_note`; `test_regressor_note_and_floor_disclaimer` updated:
`regressor_note("RR")` is now non-None). Ruff clean. No migration, no model retrain.

---

## 2026-05-30 (suite) — WAVE 6: Radio volume regressor wired + knowledge encoded (P2/P3)

### Why
The Radio volume regressor (MLflow exp 6, run `16155f62`) was trained and sitting on disk
with 17 SHAP/learning-curve artifacts, but unwired in **5 places**: no `radio_regressor` in
`MODEL_PATHS` (no forecast ever computed), no `radio_streams_forecast_7d` DB column, no
`RADIO` entry in `ALGO_VOLUME_ZONES` / `ALGO_REGRESSOR_METRICS`, and exp 6 absent from the
ML-perf view. The user's Radio regressor SHAP notes are exactly the input the code was
waiting for (`algo_knowledge.py` literally said "RR/Radio zones plug in here when their
notes arrive"). The notes also carried one genuinely new actionable insight with no home:
Discovery Mode buys radio *entry* (classifier) but is dead-flat for *volume* → past cruising
velocity, turn it off to reclaim 30% royalties.

### What changed
**Pipeline (P2):** `ml_inference.MODEL_PATHS["radio_regressor"]` + `score_song` computes
`radio_streams_forecast_7d`; `ml_scoring_daily` update_cols; `ml_song_predictions
.radio_streams_forecast_7d INTEGER` in `init_db.sql` + `create_missing_tables.sql` +
idempotent `migrations/036_ml_radio_streams_forecast.sql` (**applied to live DB this
session**); `ml_performance._MODELS` registers exp 6. **Knowledge (P3, `algo_knowledge.py`):**
`RADIO_VOLUME_ZONES` — `StreamsLast7Days` amplifier + the FIRST non-flat catalogue lever
`HowManySongsDoYouHaveInRadioRightNow` (superstar effect), with DiscoveryMode/Saves/
PlaylistAdds/ListenersStreamRatio `volume_flat`; `ALGO_REGRESSOR_METRICS["RADIO"]` (R²=0.63
+ viral-cap framing: a +400k real hit was under-predicted → read as floor, not ceiling);
new `radio_discovery_recovery_note()` margin-recovery helper. **View (P4):** radio forecast
in `_display_prob_bar`, Radio SHAP volume autopsy expander, recovery note in the coach loop,
3rd "Radio forecast" column in Actual-vs-Predicted, floor column in `revenue_forecast.py`.

### Long-term fix
`HowManySongsDoYouHaveInRadioRightNow` (RadioCount) is imputed-to-0 in production (Phase-2
feature). Marked `live_unavailable` so its superstar bonus routes to the pedagogic expander
instead of rendering a fake live "0 titres" gauge — the same imputed-0 anti-pattern caught
in the 2026-05-29 audit. `render_volume_gauges` pedagogic caption made algo-generic (was
DW/NonAlgoStreams-hardcoded, wrong for Radio). The `recovery_note` cruising trigger fires off
live `StreamsLast7Days` (available), so it works today; the superstar zone goes live at Phase 2.

### Tests
`python3 -m pytest tests/ -q` → **283 passed** (280 prior + 3 RADIO tests in
`test_algo_knowledge.py`; `test_ml_inference.py` updated to the 6-model + new-key contract,
frozen baseline regenerated via `generate_ml_baseline.py`). Ruff clean. Radio regressor
load+predict smoke-tested. NOTE: existing prediction rows have `radio_streams_forecast_7d`
NULL until the next `ml_scoring_daily` run; views handle NULL via `dropna`.

---

## 2026-05-30 — Road to Algorithms: volume (regressor) decision layer (P3)

### Why
The existing algo UI surfaced only the *classification* / entry-zone story (will a song
trigger?). The user's Discover Weekly regressor SHAP notes describe a SECOND, distinct
question — once in, *how much volume*? — driven by raw fuel (StreamsLast7Days,
NonAlgoStreams28Days) where, paradoxically, saves/playlist-adds go `volume_flat` ("quality
buys the ticket, volume writes the cheque"). That layer had no UI, and the
`*_streams_forecast_7d` point estimate was being read as a promise rather than a
conservative floor while the live regressor runs degraded (its #1 SHAP driver
NonAlgoStreams28Days_log, plus DiscoveryMode/RadioCount, are imputed to 0.0 until Phase 2).

### What changed
Shipped in tiers. **Tier A (live):** `*_streams_forecast_7d` is reframed everywhere as a
conservative FLOOR — wording single-sourced in `algo_knowledge.FORECAST_FLOOR_DISCLAIMER`,
surfaced via new `ml_widgets.render_floor_forecast()`, wired into
`trigger_algo._display_prob_bar` and the `revenue_forecast` ML table (columns renamed
"(plancher ≥)"). A "hungry/conservative" regressor badge (`render_regressor_badge`) plus a
natural-language SHAP "receipt"/autopsy (`render_shap_narrative`) land in the trigger_algo
Explainabilité tab (`ALGO_REGRESSOR_METRICS` for the dw_regressor). **Tier B (live in
"rule + static target" mode, auto-upgrades at Phase 2):** new `ALGO_VOLUME_ZONES` (DW only)
in `algo_knowledge.py` — regressor-SHAP-derived zones with saves/playlist-adds flagged
`volume_flat` — rendered by `render_volume_gauges`; plus an organic budget-scaling section
in the Budget & ROI tab (static ≥6000 organic/28j threshold via
`ak.volume_scaling_threshold("DW")`, explicitly labelled "cible, pas écart live" because
NonAlgoStreams is imputed-to-0 pre-Phase-2). The zone machinery (`_spec`, `zone_for_value`,
`decode_feature_value`) was generalized with a `registry=` arg so the same code serves both
the classification and volume zone sets; `_render_one_gauge`/`_live_value` thread it through.

Correctness audit recorded: `ListenersStreamRatio28Days_adj` — long-tracked as an
inverted+clamped P2 bug candidate — is ALREADY FIXED in `ml_inference.py:176` (now
`streams/listeners`, aligned with training + dashboard zone). No longer a bug candidate.

### Tests
`python3 -m pytest tests/ -q` → **280 passed** (267 prior + new
`TestVolumeZones`/`TestVolumeScalingThreshold`/`TestRegressorNote` in
`test_algo_knowledge.py`, plus one broken placeholder test completed). Ruff clean.

---

## 2026-05-30 — Road to Algorithms WAVE 4: Release Radar (RR) populated (P3)

### Why
WAVE 3 lit up Radio; Release Radar remained the reserved-but-empty algo slot — it was
already wired everywhere structurally (ALGO_LABELS, `populated_algos()` order, palette,
`rr_classifier` model path) but `ALGO_FEATURE_ZONES["RR"]` and `ALGO_MODEL_METRICS["RR"]`
were absent, so its UI never rendered. The user wanted RR's SHAP-derived decision zones,
scorecard, and gauges to light up across the trigger_algo Algos/Modèle tabs and the admin
ml_performance scorecard grid — with NO view-code changes (data-only activation).

### What changed
`algo_knowledge.py` adds `RR_FEATURE_ZONES` (6 features), registers `"RR"` in
`ALGO_FEATURE_ZONES` (order DW/RR/RADIO) and `ALGO_MODEL_METRICS["RR"]` — the UI now
lights up automatically with zero view edits. Zones were sourced from the actual offline
SHAP zoom ARTIFACTS (`machine_learning/mlruns/4/.../5_SHAP_Zoom_*_RR.png`), NOT the prose
notes: the plots refined the notes — (a) `DaysSinceRelease` is a firing WINDOW (too-fresh
dip days 0–7, sweet 7–40, then closes), not a clean 35-day on/off switch; (b)
`ReleaseConsistencyNum` is feature #4 by importance (absent from the notes) and rewards
SPACED releases; (c) `DiscoveryMode` is dead-flat (zero RR impact); (d) the scorecard is
pixel-verified against `1_Dashboard_Performances_RR.png` — confusion {TN76,FP6,FN4,TP16},
AUC 0.961, AP 0.88, lift_top10 5.1. `PlaylistAddsLast28Days` is marked `divergent +
actionable:False` — its negative SHAP is a chronological confound (song-age proxy), not a
causal lever, so it shows in gauges with a warning but is excluded from coach actions
(same class as the known `ListenersStreamRatio` inverted-bug). No RR calibration bands ship
(no calibration-curve artifact exists — only DW has one); `test_rr_has_no_calibration_bands`
documents the gap.

`ml_widgets.py` makes the `divergent` gauge message data-driven (was a hardcoded wrong
"bornée à ≤1.0" string anticipating one feature — now reads per-spec + renders a per-spec
`divergent_note` caption). `ml_performance.py` routes the scorecard loop through
`ak.populated_algos()` instead of a 3rd hardcoded `("DW","RR","RADIO")` tuple (DRY / drift
fix). A new cross-algo coherence guard test (every populated algo has a label; every feature
`json_key ∈ FEATURE_COLUMNS`; confusion sums to `test_n`) is the structural defense against
the reserved-but-empty-slot class.

### Tests
`python3 -m pytest tests/ -q` → **267 passed** (258 prior + 9 new in
`test_algo_knowledge.py`: 9 RR tests + 1 cross-algo coherence guard; 3 placeholders
updated). Ruff clean on all edited source files.

---

## 2026-05-30 — Road to Algorithms WAVE 3: Radio algorithm support + Prescriptive Coach (P3)

### Why
WAVE 2 populated the algo-keyed knowledge layer for Discover Weekly only; Release Radar
and Radio were stubs. The user wanted Radio's own SHAP-derived decision zones surfaced
(its rules differ from and partly invert DW's — notably track age) and the
"next-best-lever" widget upgraded from a single suggestion to a ranked, prescriptive
to-do list (a "Coach") that an artist can action top-down.

### What changed
`algo_knowledge.py` gains `RADIO_FEATURE_ZONES` (9 features; `DaysSinceRelease` is
INVERTED vs DW — honeymoon 0–50d bonus → flat-negative-but-stable; velocity stricter at
1.5 vs DW 1.2; catalog sweet-spot 10–20 "montagne verte"), `ALGO_MODEL_METRICS["RADIO"]`
(AUC 0.941, TN47/FP7/FN7/TP41, n=102, real lift over the 0.529 balanced baseline unlike
DW), `ALGO_LABELS`, `populated_algos()`, `build_coach_actions()` (ranked prescriptive
list, velocity-smooth ranked first), and a NEW `velocity_penalty_threshold(algo)`
single-source-of-truth helper for the hyper-growth cutoff. Radio carries NO calibration
bands (honest — the notes gave no calibration curve). `ml_widgets.py` renames
`render_next_best_lever → render_coach` (ranked to-do list + Discovery-Mode prompt for
Radio). `trigger_algo.py` now stacks all populated algos in the Explainabilité and Modèle
tabs (loop over `populated_algos`) and adds `_show_velocity_budget_advice` (velocity-too-
high → concrete ~30% euro spend-cut cross-link), routed through
`ak.velocity_penalty_threshold` (no hardcoded 1.2/1.5).

Two long-term fixes recorded as REX. (1) A failed Edit mid-session left
`_show_velocity_budget_advice` DEFINED BUT NEVER CALLED — dead code that passed BOTH
pytest and ruff (the `check_python_syntax` hook selects `F401/F811/F821/F841`, none of
which flag an unused module-level function). The whole Coach+budget cross-link was
silently non-functional until the call site was wired in a follow-up. Lesson (→
`check_python_syntax.py` REX): after an Edit errors, verify the wiring landed — green
tests + clean ruff do NOT prove a new top-level helper is reachable. (2) That same helper
originally hardcoded the velocity cutoff (1.2/1.5) as literals, duplicating the zone logic
in `algo_knowledge` — the exact anti-pattern the 2026-05-30 dashboard-view REX warns
against; fixed by adding `velocity_penalty_threshold()` and routing both the gate and the
displayed numbers through it (→ `dashboard-view.md` REX).

### Tests
`python3 -m pytest tests/ -q` → **258 passed, 1 skipped** (247 prior + 12 new in
`test_algo_knowledge.py`: Radio zone shapes, inverted age, coach ranking/exclusions,
`velocity_penalty_threshold` single-source contract). Ruff clean on `src/` + `tests/`.

---

## 2026-05-29 — Road to Algorithms WAVE 2: algo-keyed knowledge layer + shared ML widgets (P3)

### Why
WAVE 1 added the lifecycle/benchmark tab but the per-algorithm explainability
content (feature decision zones, calibration bands, model metrics) was inlined ad-hoc
in `trigger_algo.py` and the admin `ml_performance.py` had no classification scorecard.
The user wanted (1) a single algo-keyed source of truth reusable across both the
end-user "Road to Algorithms" view and the admin ML view, and (2) the explainability
tab to surface, per feature, where the live value sits vs the SHAP-derived decision
zone, with a next-best-lever recommendation, a fake-buzz guard, and a calibration badge.

### What changed
Two new modules. `src/dashboard/utils/algo_knowledge.py` (PURE, no Streamlit/DB) is the
algo-keyed source of truth: `ALGO_FEATURE_ZONES`, `ALGO_CALIBRATION_BANDS`,
`ALGO_MODEL_METRICS` (Discover Weekly populated; Release Radar / Radio configs plug in
later) + pure helpers — unit-tested in `tests/test_algo_knowledge.py` (8 tests).
`src/dashboard/utils/ml_widgets.py` (Streamlit/Plotly render) holds the classification
scorecard shared by the `trigger_algo` Modèle tab AND admin `ml_performance.py`, plus
the feature decision gauges + next-best-lever + fake-buzz guard + calibration badge
rendered in the `trigger_algo` Explainabilité tab. `ml_performance.py` gained a
"Scorecard classification" tab. **Known bug candidate (P2, surfaced not fixed):**
`ListenersStreamRatio28Days_adj` in `src/utils/ml_inference.py:174` is computed
`min(listeners/streams, 1.0)`, i.e. listeners-per-stream clamped to 1.0; the SHAP
analysis expects streams-per-listener with a 2.2–4 bonus sweet-spot — the live feature
is BOTH inverted AND clamped, so it can never enter its bonus zone. The gauge flags this
("définition divergente"); a checklist follow-up is opened.

### Tests
`python3 -m pytest tests/ -q` → **247 passed** (239 prior + 8 new in
`test_algo_knowledge.py`). Ruff clean on `src/` + `tests/`; Streamlit AppTest render
smoke of all `ml_widgets` helpers passed with no exceptions; both views import cleanly.

---

## 2026-05-29 — Road to Algorithms: lifecycle & benchmark tab + elbow thresholds (P3)

### Why
The "Road to Algorithms" (`trigger_algo.py`) view showed only static per-track
scores against ad-hoc goals. The user wanted (1) a cohort lifecycle/standardization
view to see how a track's algorithmic pickup (DW/RR/Radio) compares to the typical
shape over song age, and (2) the J+28 chart anchored to the empirically observed
elbow thresholds rather than loose heuristics. Production has **no per-algorithm
stream split** (`s4a_song_timeline` is total streams only), so per-tenant live
curves are impossible today — the lifecycle reference must be a static global cohort
benchmark.

### What changed
New global read-only table `algo_lifecycle_benchmark` (`src/database/benchmark_schema.py`,
`init_db.sql`, `migrations/035_algo_lifecycle_benchmark.sql` — create + PROVISIONAL
seed: 6 age-in-weeks bins × 3 algos = 18 rows, qualitative P25/median/P75 band shapes
from user notes, `total_stream_median` left NULL pending a real export). Deliberately
**global / non-tenant and NOT in `_ALLOWED_TABLES`** (no artist_id, no user-facing
f-string interpolation). `trigger_algo.py` gains a 6th tab "📉 Cycle de vie & Benchmark"
(DW/RR/Radio band charts P25–P75 + median by song age-in-weeks, live track age
overlaid); new `ELBOW_THRESHOLDS_28D` ({DW:137, RR:130, RADIO:639}) + `HEURISTIC_GOALS`
constants drive a reworked J+28 chart (both elbow solid lines incl. Radio 639 +
heuristic dashed lines, Radio fallback in the heuristic section); the Explainabilité
tab now flags the 6/13 features imputed to 0/neutral (probabilities indicative, not
calibrated). `show()` migrated from `get_db_connection()` + manual artist_id +
try/finally to the `view_session()` context manager (now enforces the non-admin
`st.stop()` guard structurally). New offline `machine_learning/export_lifecycle_benchmark.py`
computes standardization ratios (algo streams / weight-category mean) by age-week bin
from `data_anon.csv` (not committed) and prints INSERT SQL — the path to replace the
provisional seed once a real export exists. Phase 2 (future) = live per-algo capture
from S4A.

### Tests
`python3 -m pytest tests/ -q` → **239 passed, 1 skipped** (no test touches
`algo_lifecycle_benchmark` or the view; count unchanged). Migration 035 applied
(18 rows), ruff clean, end-to-end loader + figure builder validated against the live DB.

---

## 2026-05-29 — Data Wrapped: super-fans "top" metric + combined evolution chart (P3)

### Why
Follow-up on the same-day gains-to-percentages entry. Two issues remained. (1) The
`top_artist_name` (VARCHAR) + `top_artist_fan_pct` (DECIMAL) columns modelled a
*similar artist* and a shared-fans %, which is not the Wrapped metric the user enters:
the real figure is the artist's OWN super-fans — how many fans ranked the artist in
their top N (e.g. 11 fans had the artist in their top 5). (2) The four absolute line
charts (listeners/streams/saves/playlist_adds) were rendered separately, making
cross-metric reads awkward despite a large scale disparity between streams and saves.

### What changed
New idempotent `migrations/034_wrapped_top_fans.sql` (`ADD COLUMN IF NOT EXISTS
top_fans_count INTEGER, top_fans_rank INTEGER`; `DROP COLUMN IF EXISTS top_artist_name,
top_artist_fan_pct`), applied to live `spotify_etl` and verified idempotent; the real
artist_id=1/year=2024 row was preserved and backfilled to 11 fans / rank 5.
`wrapped_schema.py` canonical CREATE TABLE updated to match. In `data_wrapped.py` the 4
absolute line charts were merged into one `_multi_line_chart` helper with a per-tab
`st.toggle` for linear/log y-axis; countries + hours kept as standalone small charts;
the 4 gain % bar charts regrouped under a "Gains annuels (%)" heading; a new "Super-fans"
line chart + table replaced the old "Top artiste similaire" table.
`_load_row_for_year` was refactored to `fetch_df().iloc[0].to_dict()` (robust to the
column reordering caused by the DROP/ADD, vs the previous hardcoded column-order list).

### Tests
`python3 -m pytest tests/ -q` → **239 passed, 1 skipped** (no test touches the
`artist_wrapped` schema; count unchanged).

---

## 2026-05-29 — Data Wrapped gains converted to explicit percentages (P3)

### Why
The user is entering 2024 Spotify Wrapped data where the four gain figures are
percentages, not absolute deltas. The `artist_wrapped` gain columns were generic
signed integers (`listener_gain INTEGER`, `stream_gain BIGINT`, `save_gain`/
`playlist_add_gain INTEGER`), giving no schema-level signal of their unit — a
long-term ambiguity for a once-a-year manual-entry table.

### What changed
The 4 gain columns were renamed to `listener_gain_pct`, `stream_gain_pct`,
`save_gain_pct`, `playlist_add_gain_pct` and widened to `DECIMAL(7,2)` via the
new idempotent `migrations/033_wrapped_gains_pct.sql` (guarded RENAME in a `DO`
block + no-op TYPE widening; applied to the live `spotify_etl` DB and verified
idempotent). `wrapped_schema.py` canonical CREATE TABLE updated so fresh installs
match. `data_wrapped.py`: form inputs are now signed `%` `number_input`s
(`format="%.1f"`), a new `_fmt_pct` helper formats values, `_bar_gain_chart`
gained a `fmt_fn` param, and KPI deltas / bar-chart titles "(%)" / raw-data tab
`rename_map` "△ X %" labels were all updated.

### Tests
`python3 -m pytest tests/ -q` → **239 passed, 1 skipped** (no test touches the
`artist_wrapped` schema; count unchanged from the prior entry).

---

## 2026-05-29 — Meta Ads expansion: creative analytics + multi-grain breakdowns + dual-writer double-count fix (P2)

### Why
Continuation of the Meta session. The Créatives view exposed only flat tables — no
visual read on spend efficiency, ad fatigue, or the click→result funnel. Breakdowns
existed only at campaign grain (and only as raw tables). Investigating those tables
surfaced a P2 data-integrity bug: the campaign-level breakdown tables
(`meta_insights_performance_country/placement/age`) reported ~2× the real spend. Root
cause was a DUAL WRITER — the one-time Dec-2025 legacy Meta CSV import wrote the same
tables as the API collector with incompatible conventions (an aggregate `'All'` total
row doubling country/age, and French placement labels `Reels Instagram` vs API
snake_case `instagram_reels` → distinct conflict keys, both kept). This is the same
legacy import that earlier produced the `cg:`/`a:` prefixed-ID duplicates.

### What changed
- Creative analytics (`meta_creatives.py`): reorganised into 6 tabs (Classement /
  Comparaison / Funnel / Évolution / Fatigue / Activité) — bubble scatter (spend×CPR,
  size=impressions, color=CTR), ad-fatigue dual-axis (frequency vs CTR), go.Funnel
  (impressions→clics→résultats), efficiency bars, weekly density heatmap, cumulative
  spend area, plus a per-creative multi-metric timeline (one Y-axis/metric, weekly
  down-sampling >120d, derived CPR). All from `meta_insights` (ad grain).
- Multi-grain breakdowns: collector `meta_ads_api_collector.py` `_build_goal_maps` now
  returns `goal_by_adset`; new `_fetch_breakdown(level, id_field, breakdown,
  goal_by_entity)` (reuses `_extract_perf/_extract_eng` + FK guard, +6 API calls/run);
  `_fetch_all_insights` +12 result keys, `_upsert_all` +12 DRY-generated entries.
  12 NEW tables `meta_insights_{performance,engagement}_{ad,adset}_{country,placement,age}`
  via `migrations/032_meta_ad_adset_breakdowns.sql`, registered in
  `postgres_handler._ALLOWED_TABLES`, documented in `meta_insight_schema.py`. NEW view
  `meta_breakdowns.py` ("🌍 Breakdowns Meta", in app.py nav+routing): campaign→adset→
  creative cascade, dimension × metric-family selectors, choropleth (new
  `dashboard/utils/geo.py` ISO-2→ISO-3 pycountry wrapper) + Pareto (new shared
  `dashboard/utils/charts.py::pareto_spend_cpr`). Breakdown tables are lifetime
  aggregates (no date col) → filtered by entity, not period. New "🎯 Ciblage vs
  Performance" section in `meta_ads_overview.py` (meta_adsets targeting × CPR).
- Double-count DEFINITIVE fix: (1) cleaned spurious rows (DELETE `'All'` buckets +
  non-snake_case placement rows across the 6 campaign breakdown tables, all artists) —
  all grains now reconcile to ~3088€ (= day total); (2) patched `meta_insight_csv_parser`
  to skip aggregate/total rows (defense); (3) ARCHIVED the entire redundant legacy Meta
  CSV stack — 8 files → `archive/legacy_meta_csv/` (DAGs `meta_insights_dag`/
  `meta_config_dag`, watchers, parsers, debug scripts) + README; removed
  `TestMetaCSVParser` from `tests/test_parsers.py`; repointed ALL dashboard/alerting
  references (app.py sync, home.py, useful_links.py, airflow_kpi.py, credentials/_core.py,
  alert_root_cause.py, alert_monitor.py + debug) from the dead dag_ids to the canonical
  `meta_ads_api_daily`; added `archive/` to `.dockerignore`. RESULT: Meta tables now have
  exactly ONE writer → the double-count cannot recur. Residual (low risk): campaign-grain
  breakdowns key on `campaign_name`, so a future campaign RENAME could re-introduce stale
  rows (ad/adset grains key by ID, immune).
- Recency-ordered entity filters: selectboxes now list most-recent-first via SQL
  `ORDER BY <recency> DESC NULLS LAST` (never Python `sorted()`) across meta_breakdowns,
  meta_creatives, meta_x_spotify, meta_mapping `_load_campaigns`, ml_performance.
- REX/skills (validated this session): `audit-collectors.md` Rule 8 "one canonical
  writer per table" + dual-writer REX; `dashboard-view.md` Pitfalls #7-#9 (aggregate
  tables no date, choropleth ISO-2→ISO-3, recency-ordered filters) + REX entries.

### Tests
`python3 -m pytest tests/ -q` → **239 passed, 1 skipped** (down from 243: removing the
archived legacy CSV stack dropped `TestMetaCSVParser`; the new collector breakdown logic
reuses the existing `_extract_perf/_extract_eng` paths already covered by
`test_meta_ads_collector.py`).

---

## 2026-05-29 — Revenue forecast: NULL-probability crash (P1) + iMusician derived-table staleness (P2)

### Why
Two user-reported problems on the 📈 Prévisions revenus view. (1) `TypeError: Expected
numeric dtype, got object instead.` at `revenue_forecast.py:505`:
`ml_song_predictions.dw/rr/radio_probability` can be NULL (a model that fails to score
writes None — `ml_inference.py:204-237`), turning the pandas Series object-dtype, so
`(ml_df[col]*100).round(1)` raised. The `ml_df.empty` guard didn't cover "non-empty but
all-NULL". (2) The Distributeur view and all revenue-forecast KPIs read ONLY
`imusician_monthly_revenue`, but the CSV import writes per-line detail to
`imusician_sales_detail`; the roll-up helper `rollup_sales_to_monthly` (added earlier
this session) was wired only into the Streamlit path. The user's full 2023-01→2026-01
export (~212€, 4326 rows) had already been imported by the watcher DAG — which archived
the files but never rolled up — so monthly_revenue stayed at the old partial 13 months /
11.56€ while sales_detail held 211.87€. Dashboard showed ~5% of real revenue, no error.

### What changed
- `src/dashboard/views/revenue_forecast.py` (lines 504-506) — replaced
  `(ml_df[col]*100).round(1)` with `pd.to_numeric(ml_df[col], errors='coerce')` +
  `.map(lambda v: f"{v}%" if pd.notna(v) else "—")`, reusing the safe pattern from
  `ml_performance.py:93-99`.
- `airflow/dags/imusician_csv_watcher.py` (`process_csv_files`) — after upserts, if any
  `sales_detail` rows were imported, fires `rollup_sales_to_monthly` per `dag_run.conf`
  artist_id (best-effort, non-blocking).
- `airflow/debug_dag/debug_imusician_csv.py` (`step_5_real_upsert`) — same roll-up per
  distinct artist_id of imported sales rows.
- One-time DB backfill (no migration): ran the roll-up for artist 1 →
  `imusician_monthly_revenue` now 37 months, 2023-01→2026-01, 211.90€ (all
  `source='import'`).
- Context (created earlier this same session): `src/utils/imusician_rollup.py`,
  migration 031 (`source` column manual|import), `src/database/imusician_schema.py`, and
  the `upload_csv.py` roll-up hook wired the Streamlit path. The new code this sub-session
  is the 3 batch-path files above.
- REX: a validated entry already lives in `.claude/skills/audit-collectors.md` frontmatter
  (2026-05-29, "derived table went stale: roll-up hook lived in only 1 of 3 write paths")
  plus a new Rule 8 in that skill body — not duplicated here.

### Tests
`python3 -m pytest tests/ -q` → **243 passed** (unchanged — the crash fix is a display-path
guard and the roll-up wiring is in Airflow batch paths, both outside the unit-test scope;
no new cases this sub-session).

---

## 2026-05-29 — Meta Ads collector: paused/archived insight loss (P2) + throttle robustness

### Why
A debugging session opened by "the Créatives view shows campaign-level spend but no
per-creative detail for 4 paused campaigns". Root cause was a silent data loss:
`meta_ads_api_collector.py` fetched campaigns/adsets/ads with
`effective_status: ['ACTIVE','PAUSED']`. A PAUSED campaign propagates
`CAMPAIGN_PAUSED`/`ADSET_PAUSED` to its ad sets/ads — excluded by that filter — so
those ads never entered `meta_ads`. `_build_goal_maps` → `goal_by_ad` then lacked
them, and `_fetch_ad_insights` silently dropped the ad-level insights the API DID
return via the FK guard `if ad_id not in goal_by_ad: continue`. Campaign-level spend
was present, the per-creative breakdown missing (P2). Broadening the scope then
surfaced two follow-on issues: an aberrant ARCHIVED start_time pushed backfill to
`since=1970-01-01` (Meta error #3018, 37-month limit), and the wider fetch stormed
the API into account-level throttles the single code-17 retry could not absorb.

### What changed
- `src/collectors/meta_ads_api_collector.py` — per-level status allowlists
  `_CAMPAIGN_STATUSES` / `_ADSET_STATUSES` / `_AD_STATUSES` (incl. CAMPAIGN_PAUSED,
  ADSET_PAUSED, ARCHIVED, IN_PROCESS, WITH_ISSUES) replace the 2-value filter.
  Backfill `history_start` clamped to `today − _META_INSIGHTS_RETENTION_MONTHS` (36)
  in `_fetch_all_insights` (fixes #3018). New generic `_meta_retry(callable_fn, …)`
  retries `_META_THROTTLE_CODES = {4,17,32,80004}` with exponential backoff
  (60→120→240s, 4 attempts), materialising the cursor INSIDE the retry (the SDK raises
  during pagination); `_meta_list` now delegates to it, and the per-creative `api_get`
  routes through it. New `run(fetch_creatives: bool = True)` param — when False, skips
  the per-creative content fetch (title/body/CTA, one call per creative, the dominant
  rate-limit driver, not shown by the Créatives view).
- `airflow/debug_dag/debug_meta_ads_api.py` — `--skip-creatives` flag
  (→ `fetch_creatives=False`); step-3 dry-run probe now routes `get_campaigns` through
  `_meta_list` so a transient throttle no longer hard-fails the probe.
- `src/dashboard/views/meta_creatives.py` — the "uncollected campaigns" advisory now
  instructs a FULL full-history collection (not insights_only), explains the
  paused/archived case, and notes Meta's ~37-month insights retention.
- `.claude/skills/audit-collectors.md` — Rule 6 (silent loss via skip-guards fed by
  over-narrow scope) + Rule 7 (throttle must back off on all transient codes and not
  retry-storm BUC), plus 2 REX entries (2026-05-29).
- One-off DB cleanup (not code): removed legacy Dec-2025 prefixed-ID duplicates —
  71 ads (`a:` ad_id), 18 adsets, 15 campaigns (`cg:` campaign_id); 0 insights
  referenced, 0 orphans after.

### Tests
`python3 -m pytest tests/ -q` → **243 passed** (unchanged — collector logic was
status/retry plumbing covered by existing `test_meta_ads_collector.py`; no new cases
this session). Known limitation: a throttle on a late aggregate call discards all
already-fetched insights of the run (no per-chunk persistence) — candidate for a
future brick. Outstanding ops: account currently throttled (80004); after cooldown run
`python airflow/debug_dag/debug_meta_ads_api.py --full-history --write --artist 1 --skip-creatives`
to backfill the paused campaigns — not yet succeeded, so the 4 campaigns are not yet
in the Créatives view.

---

## 2026-05-28 — Multi-view UX pass + welcome trial + plan-history audit table

### Why
Second sub-session on 2026-05-28, focused on dashboard UX and onboarding/billing
flow rather than data integrity. Several per-platform views had usability gaps
(Apple Music multi-select where a single latest release is the norm; YouTube
subscriber axis flattened by `tozeroy`; Hypeddit/Distributeur tab clutter
duplicating the Import CSV page). Billing needed a clearer 3-tier layout and the
upgrade CTA was greyed out unconditionally. New signups had no incentive hook, and
plan changes left no audit trail — so an append-only `subscription_plan_history`
table was introduced and wired into every plan-mutation path. A standalone
"Guide de démarrage" page with downloadable PDF replaces the scattered onboarding hints.

### What changed
- `views/apple_music.py` — song filter → single-select, defaults to latest release
  (`multi=False` in `EntitySpec`).
- `views/youtube.py` — subscriber axis: dropped `fill='tozeroy'`, added a tight
  computed y-range + SI `tickformat` so daily evolution is legible.
- `views/hypeddit.py` — merged the 3 `st.tabs` (Saisie/Stats/Historique) into one
  scrolling page (stats + history first, manual entry last). New helpers
  `_render_global_stats` / `_render_history` / `_render_entry_form`.
- `views/imusician.py` (Distributeur) — removed the "Saisie" and in-view "Import CSV"
  tabs (redundant with the Import CSV page); kept Données + ROI; dropped dead
  `_upsert_revenue`.
- `views/credentials/_core.py` + `_render.py` — new `app_level_configured()`:
  Spotify/YouTube show "Configuré (clé plateforme)" when keys exist in env/config.yaml
  even without an `artist_credentials` row (mirrors the collectors' DB-then-env fallback).
- `views/billing.py` + `stripe_schema.py` — billing reworked into 3 columns
  (Free/Basic/Premium); removed the comparison dataframe; ungreyed the upgrade CTA
  (enabled button + contact message when `STRIPE_CHECKOUT_URL` unset).
  `PLAN_FEATURES['basic']` now includes `revenue_forecast` (ML access moved into Basic);
  `ALWAYS_ACCESSIBLE` now includes `process_guide`.
- `register.py` + `verification_email.py` + `src/utils/plan_history.py` (NEW) — every
  new signup auto-grants a 30-day premium trial (`WELCOME_TRIAL_DAYS`) via `promo_plan`
  precedence; new `send_welcome_email()` recaps first actions; new `log_plan_change()` helper.
- `migrations/029_subscription_plan_history.sql` (NEW) — append-only
  `subscription_plan_history` table + idempotent backfill of existing artists. Write
  hooks added in `register.py` (welcome_trial/promo), `admin.py` (admin_edit),
  `api/routers/stripe_webhook.py` (stripe_webhook).
- `views/alerts.py` — two new admin sections: a plan-evolution stacked-area chart
  (from `subscription_plan_history`) and a users table (email + signup date + effective plan).
- `views/process_guide.py` (NEW, "📋 Guide de démarrage") — downloadable PDF (WeasyPrint,
  HTML fallback). `app.py` nav: Données section reordered Guide → Credentials →
  Import CSV → Mapping → Santé (Credentials moved out of the account section to sit
  just above Import CSV).

### Tests
`python3 -m pytest tests/ -q` → **243 passed** (unchanged — UX/migration session, no
new test cases). Ruff clean. Migration 029 applied to the local DB.

---

## 2026-05-28 — Meta Ads objective-driven `results` (P2) + onboarding/nav/Meta×Spotify UX

### Why
The dashboard "Résultats" metric read `0` for every Meta campaign. Root cause: the
API collector hardcoded `results` to count only `offsite_conversion.custom`, but all 15
campaigns on the test account run objective `OUTCOME_ENGAGEMENT` and fire 0 custom
conversions. The daily DAG was writing `0` and overwriting correct CSV-imported values
— a P2 data-integrity bug. Same session, finish the onboarding/nav cleanups: the home
tracker still pointed at a removed 2FA step, and the Meta×Spotify view carried a broken
duplicate of the dedicated Mapping page.

### What changed
- `src/collectors/meta_ads_api_collector.py` — new `_OBJECTIVE_RESULT_ACTION` map
  (ENGAGEMENT→post_engagement, TRAFFIC→link_click, LEADS/SALES→offsite_conversion.custom,
  APP_PROMOTION→app_install; unknown/NULL/awareness → fallback `custom_conversions`).
  Objective propagated from `meta_campaigns` into `_extract_perf` via `objective_by_name`
  across all 4 `_call_insights` calls + the `insights_only` DB query. Requires a
  `full_history` Meta DAG re-collection to backfill historical `results`.
- `src/dashboard/views/meta_x_spotify.py` — removed the redundant + broken inline
  "Gérer les associations" mapping expander (its INSERT omitted the now-NOT-NULL
  `artist_id`); view is now read-only on mappings and links to the Mapping page. Dropped
  the "Streams Cumulés" series (trace/cumsum/yaxis8/table column). CPR now reads Meta's
  real `cpr` column, falling back to `spend/results` only where `cpr` null but `results>0`.
  Forced number format "13 385" (`tickformat=",d"`) instead of Plotly's "13.385k".
- `src/dashboard/app.py` — moved `meta_mapping` from "Publicité Meta Ads" into "Données"
  under "Import CSV"; relabeled "🔗 Mapping Spotify × Meta Ads (nom de campagne)".
- `src/dashboard/views/home.py` — onboarding tracker: 2FA step → "Upload an Apple Music
  CSV" (checks `apple_songs_performance`); "first data collection" reordered after both
  upload steps; auto-hide replaced by a green "configuration terminée" recap.
- `src/dashboard/views/upload_csv.py` — expander documenting the 6 recognized CSV types
  + info note to run the mapping after launching collection from the home page.
- `tests/test_meta_ads_collector.py` — `TestExtractPerfObjective` (6 tests) covers the
  objective→action mapping and the fallback.

### Tests
`python3 -m pytest tests/ -q` → **243 passed** (was 237; +6 from `TestExtractPerfObjective`).

### Reste à faire
Re-run `meta_ads_api_daily` with `full_history` conf to backfill historical `results`
into `meta_insights_performance`. Open P2 items unchanged (`tracks` multi-tenant
migration; Meta/SoundCloud DAG re-trigger verification).

### Cross-refs
- `.claude/dev-docs/architecture.md` — Meta dual-path note (objective-driven results) + Views Map
- `.claude/skills/audit-collectors.md` — REX: silent *correctness* (not just silent return) in collectors

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
