---
rex:
  - date: 2026-05-14
    issue: "Skill had no pitfall section, so Claude rewrote known view bugs (na_rep, tight subplot\
  \ spacing, varchar artist_id)"
    fix: "Appended 'Common Pitfalls' section with 4 entries: .style.format na_rep, make_subplots\
  \ spacing (use px.bar facet_row), .streamlit/config cwd, multi-tenant artist_id\
  \ types"
    severity: "info"
    ref: "DEVLOG#2026-05-14"
  - date: 2026-05-29
    issue: "Meta breakdown tables are lifetime aggregates (no date) with ISO-2 codes; chart assumed period filter + ISO-3 map"
    fix: "Period filter only on datable tables; choropleth needs ISO-2→ISO-3 (pycountry via utils/geo.py); per-creative breakdowns required NEW ad/adset tables (campaign grain != creative grain)"
    severity: "info"
    ref: "DEVLOG#2026-05-29"
  - date: 2026-05-29
    issue: "ML decision gauges trusted inference features imputed-to-0 or inverted+clamped vs the trained definition"
    fix: "algo_knowledge flags live_unavailable/divergent features instead of trusting them; recovered Saves/PlaylistAdds/ReleaseConsistency from DB + fixed ratio (streams/listener, unclamped) in ml_inference"
    severity: "warn"
    ref: "DEVLOG#2026-05-29"
  - date: 2026-05-29
    issue: "ReleaseConsistency from timeline first-appearance was all-zero: backfill gives every song one identical first date"
    fix: "Use real per-tenant dates from track_release_reference for cadence; never derive release dates from backfilled timeline MIN(date)"
    severity: "warn"
    ref: "DEVLOG#2026-05-29"
  - date: 2026-05-30
    issue: "Tempted to reuse DW feature thresholds for Radio, but Radio rules differ/invert (age, velocity, catalog)"
    fix: "Keep per-algo zone sets in algo_knowledge.ALGO_FEATURE_ZONES (algo-keyed); never generalize one algorithm's SHAP thresholds to another. Radio populated separately from DW"
    severity: "info"
    ref: "DEVLOG#2026-05-30"
  - date: 2026-05-30
    issue: "A view hardcoded the velocity cutoff (1.2/1.5) as literals, duplicating zone logic already in algo_knowledge"
    fix: "Added ak.velocity_penalty_threshold(algo) single-source helper; route both the gate and the displayed number through it. Views never re-encode a threshold that lives in algo_knowledge"
    severity: "warn"
    ref: "DEVLOG#2026-05-30"
  - date: 2026-05-30
    issue: "Encoding RR zones from the prose SHAP summary missed feature #4 and oversimplified another (cliff vs firing window)"
    fix: "Encode algo decision zones from the SHAP zoom ARTIFACTS (mlruns/4/.../5_SHAP_Zoom_*.png), not the prose summary; pixel-verify the scorecard against the Dashboard_Performances PNG"
    severity: "warn"
    ref: "DEVLOG#2026-05-30"
  - date: 2026-05-30
    issue: "Divergent gauge message hardcoded 'bornée à ≤1.0' for one feature; wrong for RR PlaylistAdds (a song-age confound)"
    fix: "Per-feature warning strings must be data-driven (read divergent_note from the zone spec), never hardcoded for one expected feature; mark confound features actionable:False to exclude from coach"
    severity: "warn"
    ref: "DEVLOG#2026-05-30"
  - date: 2026-05-30
    issue: "Adding a 2nd zone set (volume regressor) duplicated the classification zone helpers"
    fix: "Generalize the zone helpers with a registry= arg so one machinery serves both ALGO_FEATURE_ZONES and ALGO_VOLUME_ZONES; thread it through ml_widgets gauges too"
    severity: "info"
    ref: "DEVLOG#2026-05-30"
  - date: 2026-05-30
    issue: "Re-audited ListenersStreamRatio as the tracked inverted+clamped P2 bug; already fixed in ml_inference.py:176"
    fix: "Before re-flagging a known bug candidate, read the live code. ListenersStreamRatio is now streams/listeners unclamped (fixed 2026-05-29); close stale bug-candidate notes once confirmed in source"
    severity: "info"
    ref: "DEVLOG#2026-05-30"
  - date: 2026-05-30
    issue: "Imputed-0 feature (RadioCount) rendered a fake live '0' gauge in a new volume zone\
  \ \u2014 live_unavailable wasn't re-set"
    fix: "live_unavailable is per zone-set, not inherited: flag the feature in EACH spec (ALGO_VOLUME_ZONES\
  \ too) so the gauge routes to the pedagogic expander"
    severity: "warn"
    ref: "DEVLOG#2026-05-30"
  - date: 2026-05-31
    issue: "RR volume regressor (R\xB2=0.32, noise) was shown to users as a forecast \u2014 a\
  \ false financial promise"
    fix: "Gate user forecasts on ak.volume_forecast_reliable(algo) (data-driven flag, not if-algo==RR);\
  \ low-R\xB2 regressors ship classification-only, the scatter stays as a labelled\
  \ diagnostic"
    severity: "warn"
    ref: "DEVLOG#2026-05-31"
  - date: 2026-05-31
    issue: "Decision signals (probs/SHAP/velocity) were scattered across 6 tabs — no single kill/optimize/scale call"
    fix: "_show_verdict_banner: argmax of the 3 algo probs → 20/50% bands. Probs uncalibrated so the bands are decision heuristics, surfaced via ak.calibration_note"
    severity: "info"
    ref: "DEVLOG#2026-05-31"
  - date: 2026-05-31
    issue: "Snowball radar relied on HowManySongsInRadioRightNow, imputed-to-0 at inference → unusable directly"
    fix: "Bypass the dead ML feature: scan the catalogue via ml_song_predictions.radio_probability >=0.5; label it a model proxy, not the real radio count"
    severity: "info"
    ref: "DEVLOG#2026-05-31"
  - date: 2026-05-31
    issue: "Verdict banner shipped 20/50% decision bands on UNCALIBRATED XGB probs — a heuristic sold as real likelihoods"
    fix: "Platt-calibrate each classifier on the held-out split (calibration.json), apply in score_song; the bands now mean real trigger probabilities"
    severity: "warn"
    ref: "DEVLOG#2026-05-31"
  - date: 2026-05-31
    issue: "User SHAP notes contradicted each other AND the encoded zones; picking one note risked degrading the registry"
    fix: "derive_thresholds.py computes success-rate knees from data_anon.csv → align algo_knowledge to data, not a note. Velocity stopped penalising 1.2-2.0 (no knee), malus only >3.5"
    severity: "warn"
    ref: "DEVLOG#2026-05-31"
  - date: 2026-05-31
    issue: "User asked to 'integrate' 7 ML graphs but 6/7 already existed in trigger_algo.py (SHAP waterfall, ROI, residuals)"
    fix: "Map the existing tabs before building — only LIME + Meta-lever scoring were real gaps. Reuse meta_cpr_optimizer's join, don't rebuild the 6 charts"
    severity: "info"
    ref: "DEVLOG#2026-05-31"
  - date: 2026-05-31
    issue: "Marketing levers were generic hardcoded text, decoupled from the artist's actual Meta Ads results"
    fix: "Score levers on real Meta perf: join campaign_track_mapping ↔ meta_insights_performance (CPR/CTR) + meta_ads.call_to_action, rank what worked"
    severity: "info"
    ref: "DEVLOG#2026-05-31"
  - date: 2026-05-31
    issue: "Combined algos chart lacked PI + a 28d listeners gate; per-song daily listeners don't exist (snapshot only)"
    fix: "Added PI line (track_popularity_history) on the % axis + a 28d gate panel (s4a_songs_global snapshot) vs data-validated thresholds (DW 9200/4100)"
    severity: "info"
    ref: "DEVLOG#2026-05-31"
  - date: 2026-06-01
    issue: "A NULL in a numeric column loads as object dtype → arithmetic + .round() raised 'Expected numeric dtype, got object'"
    fix: "Coerce every DB numeric column with pd.to_numeric(errors='coerce') (+fillna/where) BEFORE arithmetic/.round(); render-smoke catches live NULLs. Class object-dtype-numeric-op"
    severity: "warn"
    ref: "DEVLOG#2026-06-01"
  - date: 2026-06-01
    issue: "Mixed-offset ISO timestamp strings → pd.to_datetime/px.timeline raised 'Cannot mix tz-aware with tz-naive values'"
    fix: "Normalise heterogeneous datetime string columns at source: pd.to_datetime(col, utc=True, errors='coerce').dt.tz_localize(None). Class tz-aware-naive-mix"
    severity: "warn"
    ref: "DEVLOG#2026-06-01"
  - date: 2026-06-08
    issue: "Exact-match title join across the filename(_)/CSV(real-char) boundary silently returned 0 for ?-titled tracks"
    fix: "Route the CSV/API side of every cross-convention title join through canonical_song_sql() (src/utils/track_matching.py); ad-hoc REPLACE(.,'?','_') only covered '?'. Class song-name-convention-mismatch"
    severity: "warn"
    ref: "DEVLOG#2026-06-08"
  - date: 2026-06-08
    issue: "st.image(width='content'|'stretch') upscaled small screenshots to column width -> pixelated/blurry"
    fix: "Pass an explicit pixel width = native width capped (PIL Image.width, min(w, 720)); never upscale. 'content' is NOT native size in Streamlit 1.54"
    severity: "info"
    ref: "DEVLOG#2026-06-08"
  - date: 2026-06-08
    issue: "Guide screenshots moved into per-platform subfolders -> flat assets_dir()/filename lookup broke (0 images)"
    fix: "screenshot_path() resolves by filename anywhere under the assets dir via rglob (flat OR subfolder), falling back to flat path for graceful-missing"
    severity: "info"
    ref: "DEVLOG#2026-06-08"
  - date: 2026-06-08
    issue: "Manual-entry forms + how-to guides split into standalone views felt like a doublon; user reverted to inline"
    fix: "Keep manual entry + guides inline in the actionable page (Vue Globale expanders), not standalone pages unless content is large/shared. One content module, rendered at point of use"
    severity: "info"
    ref: "DEVLOG#2026-06-08"
  - date: 2026-06-08
    issue: "SoundCloud/Meta forms asked artists for app Client ID/Secret/token, but those are a shared admin app"
    fix: "Artist provides only the per-tenant pointer (user_id / account_id); app creds come from env via an ADDITIVE collector+test fallback (stored per-artist wins). Token lifecycle lives in the admin view"
    severity: "info"
    ref: "DEVLOG#2026-06-08"
  - date: 2026-06-08
    issue: "Emoji in the WeasyPrint PDF rendered as tofu boxes (base fonts ship no emoji glyphs)"
    fix: "Strip emoji from the final HTML before write_pdf. For charts use matplotlib->base64 PNG (utils/pdf_charts.py) - kaleido is absent so plotly->png is unavailable; no new dependency added"
    severity: "info"
    ref: "DEVLOG#2026-06-08 (suite)"
  - date: 2026-06-08
    issue: "Changed render_html output but the byte-exact golden pdf_report_golden.html still pinned old bytes -> snapshot failed"
    fix: "Any render_html change requires regenerating tests/fixtures/pdf_report_golden.html in the same commit; it is byte-exact (see class snapshot-fixture-hook-reflow, kept out of reflow hooks)"
    severity: "info"
    ref: "DEVLOG#2026-06-08 (suite)"
  - date: 2026-06-09
    issue: "New view track_mapping opened DB via get_db_connection()+try/finally instead of view_session() — violates CLAUDE rule #7"
    fix: "Migrated track_mapping + meta_mapping to `with view_session() as (db, artist_id)`; every NEW view MUST use it (handles artist_id guard + admin fallback + close)"
    severity: "warn"
    ref: "DEVLOG#2026-06-09"
  - date: 2026-06-09
    issue: "try/except around the view dispatch swallowed Streamlit st.stop()/st.rerun() control-flow exceptions -> nav broke"
    fix: "Re-raise when type(exc).__name__ in {RerunException,StopException} (error_alert.is_control_flow) BEFORE alerting; verified those exact names on Streamlit 1.54"
    severity: "warn"
    ref: "DEVLOG#2026-06-09"
  - date: 2026-06-09
    issue: "Export PDF moved to free tier let free users tick premium ML/forecast/Meta sections -> paywall leak in the PDF"
    fix: "Added PREMIUM_SECTIONS frozenset (pdf_exporter); export_pdf locks those checkboxes for non-premium AND strips them at generation (defense-in-depth)"
    severity: "warn"
    ref: "DEVLOG#2026-06-09"
---

# Skill: Dashboard View

Injected when prompt contains: "dashboard", "view", "streamlit", "page", "show()"

---

## Relational Classification

- **Type**: Feature
- **Depends on**: `src/dashboard/utils/__init__.py` (get_db_connection)
- **Persists in**: PostgreSQL `spotify_etl` (read-only for most views)
- **Triggers**: Streamlit re-render on `st.session_state` change

---

## Quick Reference (always apply)

| Rule | Detail |
|---|---|
| Entry point | `show()` — no arguments |
| DB + artist | `with view_session() as (db, artist_id):` from `src/dashboard/utils` — opens 1 conn, resolves tenant, auto-closes, enforces rules #7/#9 |
| DB close | handled by `view_session()` (legacy: `db.close()` in `finally`) |
| Artist filter | `WHERE artist_id = %(artist_id)s` — value from `st.session_state['artist_id']` |
| S4A mandatory filter | `AND song NOT ILIKE '%1x7xxxxxxx%'` on `s4a_song_timeline` |
| Role gate | `if st.session_state.get('role') == 'admin':` |

---

## Registration (3 steps)

1. Create `src/dashboard/views/<name>.py` with `show()` function
2. Add `("<label>", "<name>")` to the relevant section in `_NAV_SECTIONS` (`app.py`) — the sidebar is grouped by section, pick the one matching the user journey. Admin-only pages: also add the key to `_ADMIN_ONLY`.
3. Add routing: `elif page == "<name>": from views.<name> import show; show()`

---

## Code Patterns

### Standard DB Query (use `view_session()`)
```python
from src.dashboard.utils import view_session

def show():
    with view_session() as (db, artist_id):
        df = db.fetch_df(
            "SELECT * FROM some_table WHERE artist_id = %s",
            (artist_id,),
        )
        # render; connection auto-closed, non-admin invalid session auto-stopped
```
`view_session()` replaces the `get_db_connection()` + manual `get_artist_id()`
guard + `try/finally db.close()` boilerplate (rules #7 & #9 enforced).

### S4A Query (mandatory filter)
```python
df = db.fetch_df(
    """SELECT song, SUM(streams) FROM s4a_song_timeline
       WHERE artist_id = %(artist_id)s
         AND song NOT ILIKE '%%1x7xxxxxxx%%'
       GROUP BY song""",
    {"artist_id": st.session_state["artist_id"]}
)
```

### Role-Gated Content
```python
if st.session_state.get("role") == "admin":
    st.subheader("Admin section")
    # admin-only content
```

### Empty State Handling
Use `show_empty_state` (`src/dashboard/utils/ui.py`) — factors the
`if df.empty: st.info(...); return` pattern; caller keeps the early return:
```python
from src.dashboard.utils.ui import show_empty_state

if show_empty_state(df, "Aucune donnée pour cette période."):
    return
# level="warning" / "error" for non-info severities
```

---

## Common Pitfalls (learned the hard way)

### 1. `df.style.format({...})` crashes on NULL columns
Pandas styler invokes `"{:,.2f}".format(value)` and Python raises `TypeError`
when `value is None`. LEFT JOIN, NULLIF, and SUM/AVG over empty windows all
produce NULL. **Always** pass `na_rep="—"`:

```python
st.dataframe(df.style.format({"CPR": "{:,.2f} €"}, na_rep="—"))
```
Precedent: `src/dashboard/views/trigger_algo.py:411`.

### 2. Plotly `make_subplots` with tight `vertical_spacing` renders empty bars
`make_subplots(rows=N, subplot_titles=[...], vertical_spacing=0.025)` with
N≥6 silently produces zero-height plot areas — titles consume the layout
budget, no exception raised. Two safe options:
- `vertical_spacing ≥ 0.05` AND keep height ≥ 120px per row, OR
- Use `plotly.express.bar(df_long, facet_row='metric')` + `update_yaxes(matches=None)` — auto-handles spacing.

Precedent (working): `src/dashboard/views/meta_ads_overview.py` "Comparaison multi-métriques" section.

### 3. `.streamlit/config.toml` is cwd-relative
Streamlit reads `.streamlit/config.toml` from the directory you launch from.
If `make dashboard` does `cd src/dashboard && streamlit run app.py`, the
repo-root config is invisible (`headless = true` not applied → `gio:`
errors on WSL2). Launch from repo root: `streamlit run src/dashboard/app.py`.

### 4. Multi-tenant: never assume `artist_id` is int across all tables
Some legacy tables (e.g. `tracks`) store `artist_id` as **VARCHAR(50)** (Spotify
artist ID), not the SaaS integer. Before adding a new query: `\d <table>` and
check the column type. Cross-type comparison raises `UndefinedFunction:
operator does not exist: character varying = integer`. See
`.claude/dev-docs/audit-tracks-legacy.md` for the inventory.

### 5. Mixed `datetime.date` / `pd.Timestamp` → sort/compare/merge crash
psycopg2 returns DATE columns as `datetime.date`; `pd.to_datetime(df['date'])`
yields `pd.Timestamp`. If one source df is converted and another isn't, then
`sorted(pd.concat([...]).unique())` (or a `pd.merge` on `date`, or any `<`/`==`)
raises `TypeError: Cannot compare Timestamp with datetime.date`. **Normalize
every date column with `pd.to_datetime` immediately after `fetch_df`**, before
any concat/sort/merge — never conditionally. Precedent (fixed):
`src/dashboard/views/meta_x_spotify.py` `all_dates`. Class:
`mixed-date-timestamp` (`.claude/dev-docs/error-classes.md`).

### 6. `entity_period_filter`: `collected_at` is ingest time, not release date
`EntitySpec(table, entity, date_column)` orders "latest release" by
`MIN(date_column)`. If `date_column` is the ingest timestamp (`collected_at`),
the default entity = first one WE collected, NOT the most recently released —
wrong default + wrong "Depuis dernière release" anchor (backfill / late-added
rows). When a true upload/release date exists, pass `release_column=` (e.g.
soundcloud `track_created_at`); the period span still uses `date_column`.
Precedent (fixed): `soundcloud.py` `release_column="track_created_at"`.
Accepted exception: `apple_music.py` (no Apple API created_at — `MIN(date)`
proxy, do NOT name-join `tracks`). Class: `ingest-time-as-release-date`.

### 7. Aggregate breakdown tables have no date dim → no period filter
`meta_insights_performance_{country,placement,age}` (and the ad/adset-grain
variants) are **lifetime aggregates** keyed by `(artist_id, entity, dimension)` —
there is NO `date`/`day_date` column. Do not wire `smart_date_range` to them:
filter by **entity** (campaign/adset/creative) instead, and label the data as
lifetime. Period filters belong on datable tables (`meta_insights` ad-level,
`*_performance_day`). Precedent: `meta_breakdowns.py`.

### 8. Choropleth needs ISO-3, Meta stores ISO-2
Meta `country` columns are ISO-3166 **alpha-2** ('US','FR'); `px.choropleth`
needs **alpha-3** with `locationmode='ISO-3'`. Convert via `utils/geo.iso2_to_iso3`
(pycountry wrapper) and `.dropna(subset=['iso3'])` before plotting — unmapped
codes silently vanish otherwise. Precedent: `meta_breakdowns.py::_render_performance`.

### 9. Entity filters: order by recency in SQL, never `sorted()`
A `selectbox`/`multiselect` over entities (campaign, ad set, ad, track, video…)
must list the **most recent first** (last launched/released on top), so the user
lands on what they're working on now. Do it in **SQL** — `ORDER BY <recency_col>
DESC NULLS LAST` — and keep that order through to the widget. Never `sorted(...)`
the options in Python (it re-alphabetises and buries the latest entity).

There is no generic helper: the recency column differs per table, so it's a
convention, not a function.

| Table | Recency column |
|---|---|
| `meta_campaigns` / `meta_adsets` | `start_time` |
| `meta_ads` | `created_time` |
| `soundcloud_tracks*` | `track_created_at` |
| `youtube_videos` | `published_at` |
| S4A releases | `release_date` (`track_release_reference`) |

For a list derived from an already-fetched DataFrame, carry the recency column and
`df.sort_values(recency, ascending=False, na_position='last')[label].drop_duplicates()`.
Precedents: `meta_breakdowns.py` cascade, `meta_creatives.py` campaign/creative pickers.

### 10. Coerce DB numerics before arithmetic (`object` dtype crash)

A numeric column with **any** NULL row loads as pandas `object` dtype; subsequent
arithmetic + `Series.round(n)` then raises `TypeError: Expected numeric dtype, got
object instead.` at render. Data-dependent — green until a row goes NULL (LEFT JOIN,
empty window, a model that failed to score).

Coerce **every** DB numeric column before any arithmetic/`.round()`:
```python
likes = pd.to_numeric(df["likes_count"], errors="coerce").fillna(0)
pc    = pd.to_numeric(df["playback_count"], errors="coerce")
df["eng_rate"] = (likes / pc.where(pc != 0) * 100).round(1)   # 0/NULL → NaN, never crashes
```
Precedents: `soundcloud.py` eng_rate, `revenue_forecast.py` ML probs. Error class
`object-dtype-numeric-op`; the render-smoke harness is the net.

### 11. Normalise heterogeneous datetime columns to naive-UTC at source

A column of ISO timestamp strings where some carry a tz offset (`+00:00`) and some are
naive (older rows) makes `pd.to_datetime(series)` **and** Plotly datetime coercion
(`px.timeline`, scatter x) raise `ValueError: Cannot mix tz-aware with tz-naive values,
at position N`. Normalise **once, at the point you build the column** — not per chart:
```python
for col in ("start_date", "end_date"):
    df[col] = pd.to_datetime(df[col], utc=True, errors="coerce").dt.tz_localize(None)
```
`utc=True` unifies the offsets; `.dt.tz_localize(None)` drops the tz so every consumer
sees plain naive-UTC. Precedent: `airflow_kpi.py` `df_runs`. Error class
`tz-aware-naive-mix` (sibling of Pitfall #5). 

---

## Reference Implementations

| Pattern | File |
|---|---|
| Admin-only multi-tab view | `src/dashboard/views/admin.py` |
| KPI cards + charts | `src/dashboard/views/home.py` |
| Multi-tab with DB queries | `src/dashboard/views/imusician.py` |
| CSV upload flow | `src/dashboard/views/upload_csv.py` |
| Role-gated with export | `src/dashboard/views/export_csv.py` |

---

## Cross-Cutting Rules

1. **Language**: English in all variable names, comments, docstrings — no exceptions
2. **Neutrality**: Describe data as-is; do not label "good" or "bad" trends in code comments
3. **Classification**: Add docstring with Type/Depends on/Persists in at top of every new view file
