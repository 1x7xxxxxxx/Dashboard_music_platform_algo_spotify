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
