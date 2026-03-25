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
| DB connection | `get_db_connection()` from `src/dashboard/utils/__init__.py` |
| DB close | `db.close()` in `finally` block or context manager |
| Artist filter | `WHERE artist_id = %(artist_id)s` — value from `st.session_state['artist_id']` |
| S4A mandatory filter | `AND song NOT ILIKE '%1x7xxxxxxx%'` on `s4a_song_timeline` |
| Role gate | `if st.session_state.get('role') == 'admin':` |

---

## Registration (3 steps)

1. Create `src/dashboard/views/<name>.py` with `show()` function
2. Add entry to `pages` dict in `show_navigation_menu()` in `app.py`
3. Add routing: `elif page == "<name>": from views.<name> import show; show()`

---

## Code Patterns

### Standard DB Query
```python
from src.dashboard.utils import get_db_connection

def show():
    db = get_db_connection()
    try:
        df = db.fetch_df(
            "SELECT * FROM some_table WHERE artist_id = %(artist_id)s",
            {"artist_id": st.session_state["artist_id"]}
        )
    finally:
        db.close()
```

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
```python
if df.empty:
    st.info("No data available for the selected period.")
    return
```

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
