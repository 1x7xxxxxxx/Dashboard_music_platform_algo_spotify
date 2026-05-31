# DEVLOG

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
