---
name: dashboard-view
description: "Rules for Streamlit views: page structure, sidebar, caching, plotly charts and KPI tiles. Use when writing or reviewing a dashboard page, a show() function, a filter or a widget, or when the user mentions streamlit, view, page, navigation or metric. Not for the pipeline that feeds it and not for the database layer. Assumes a Streamlit app following this repo's view layout."
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
