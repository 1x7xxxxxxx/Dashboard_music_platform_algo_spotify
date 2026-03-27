# DEVLOG

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
