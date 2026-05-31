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
