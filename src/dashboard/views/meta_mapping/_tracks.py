"""Cross-platform track tab — each platform's free-text titles scored against the
canonical track_release_reference; accept/reject → track_platform_link.

Type: Sub
Uses: track_mapping_suggest (rank_track_candidates, confidence_badge)
Persists in: track_platform_link (PostgreSQL spotify_etl)
"""
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from src.dashboard.utils.i18n import t
from src.utils.track_mapping_suggest import confidence_badge, rank_track_candidates

from ._common import _S4A_FILTER, _mutex_checkboxes

# (platform_key, human label). platform_key is a fixed enum (never user input).
_PLATFORMS = [
    ('s4a', 'Spotify (S4A)'),
    ('spotify', 'Spotify (API)'),
    ('apple', 'Apple Music'),
    ('soundcloud', 'SoundCloud'),
    ('youtube', 'YouTube'),
    ('hypeddit', 'Hypeddit'),
]

# Short column headers for the coverage grid (compact, no long platform titles).
_PLATFORM_SHORT = {'s4a': 'S4A', 'spotify': 'Spotify', 'apple': 'Apple',
                   'soundcloud': 'SoundCloud', 'youtube': 'YouTube', 'hypeddit': 'Hypeddit'}


def _load_platform_titles(db, artist_id, platform):
    """[{title, ref_id, date}] of distinct platform-local titles. `date` = the platform's
    own upload/release date when the source exposes one (Spotify/SoundCloud/YouTube),
    else None (Apple, and S4A which IS the canonical source → near-exact title match)."""
    q = {
        's4a': ("SELECT DISTINCT song, NULL::text, NULL::date FROM s4a_song_timeline "
                "WHERE artist_id = %s AND song NOT ILIKE %s", (artist_id, _S4A_FILTER)),
        'spotify': ("SELECT track_name, MAX(track_id), MAX(release_date) FROM tracks "
                    "WHERE saas_artist_id = %s AND track_name IS NOT NULL "
                    "GROUP BY track_name", (artist_id,)),
        'apple': ("SELECT DISTINCT song_name, NULL::text, NULL::date "
                  "FROM apple_songs_performance "
                  "WHERE artist_id = %s AND song_name IS NOT NULL", (artist_id,)),
        'soundcloud': ("SELECT title, MAX(track_id), MAX(track_created_at) "
                       "FROM soundcloud_tracks_daily "
                       "WHERE artist_id = %s AND title IS NOT NULL GROUP BY title",
                       (artist_id,)),
        'youtube': ("SELECT title, MAX(video_id), MAX(published_at) FROM youtube_videos "
                    "WHERE artist_id = %s AND title IS NOT NULL GROUP BY title", (artist_id,)),
        # Hypeddit promo campaigns are named after the track (no per-platform release date).
        'hypeddit': ("SELECT campaign_name, NULL::text, NULL::date FROM hypeddit_campaigns "
                     "WHERE artist_id = %s AND campaign_name IS NOT NULL", (artist_id,)),
    }.get(platform)
    if not q:
        return []
    try:
        rows = db.fetch_query(q[0], q[1])
    except Exception:
        return []
    return [{'title': r[0], 'ref_id': r[1], 'date': r[2]} for r in (rows or []) if r[0]]


def _load_links(db, artist_id):
    return db.fetch_df(
        "SELECT match_key, platform, platform_title, status, confidence "
        "FROM track_platform_link WHERE artist_id = %s",
        (artist_id,))


def _build_suggestions(db, artist_id, platform, canonical, links_df):
    """Per-platform unmapped titles → top candidate. `confidence` kept raw [0,1] for the
    DB; the displayed `Confiance` is ×100 so the ProgressColumn text reads a real %."""
    seen = set()
    if not links_df.empty:
        seen = {r.platform_title for r in
                links_df[links_df.platform == platform].itertuples()}
    confirmed_keys = (set(links_df[links_df.status == 'confirmed'].match_key)
                      if not links_df.empty else set())
    sugg, disp = [], []
    for item in _load_platform_titles(db, artist_id, platform):
        if item['title'] in seen:
            continue  # already confirmed/rejected for this platform
        cands = rank_track_candidates(item['title'], canonical, confirmed_keys,
                                      top_n=1, platform_date=item.get('date'))
        if not cands:
            continue
        c = cands[0]
        sugg.append({'platform_title': item['title'], 'ref_id': item['ref_id'],
                     'match_key': c.match_key, 'confidence': c.score, 'method': c.method})
        disp.append({'Fiab.': confidence_badge(c.score), 'Titre plateforme': item['title'],
                     'Suggestion (track)': c.title, 'Confiance': round(c.score * 100, 1),
                     'Accepter': c.score >= 0.8, 'Rejeter': False})
    return sugg, pd.DataFrame(disp)


def _build_all_suggestions(db, artist_id, canonical, links_df):
    """All platforms' top suggestions in ONE list (no per-platform selector). Each
    display row carries a Plateforme column; each sugg dict carries its platform."""
    all_sugg, rows = [], []
    cols = ['Fiab.', 'Titre plateforme', 'Suggestion (track)', 'Confiance', 'Accepter', 'Rejeter']
    for pkey, plabel in _PLATFORMS:
        sugg, disp = _build_suggestions(db, artist_id, pkey, canonical, links_df)
        for i, s in enumerate(sugg):
            s['platform'] = pkey
            all_sugg.append(s)
            r = disp.iloc[i]
            rows.append({'Plateforme': _PLATFORM_SHORT[pkey], **{c: r[c] for c in cols}})
    return all_sugg, pd.DataFrame(rows)


def _save_all_links(db, artist_id, all_sugg, edited):
    """One upsert across all platforms (track_platform_link carries the platform column)."""
    now = datetime.now(timezone.utc)
    data = []
    for i, row in edited.reset_index(drop=True).iterrows():
        if i >= len(all_sugg):
            continue
        status = 'confirmed' if row.get('Accepter') else 'rejected' if row.get('Rejeter') else None
        if status is None:
            continue
        s = all_sugg[i]
        data.append({'artist_id': artist_id, 'match_key': s['match_key'], 'platform': s['platform'],
                     'platform_title': s['platform_title'], 'platform_ref_id': s['ref_id'],
                     'status': status, 'confidence': s['confidence'], 'method': s['method'],
                     'updated_at': now})
    if data:
        db.upsert_many(
            'track_platform_link', data,
            conflict_columns=['artist_id', 'platform', 'platform_title', 'match_key'],
            update_columns=['status', 'confidence', 'method', 'updated_at'])
    return len(data)


def _render_track_suggestions(db, artist_id, canonical, links_df):
    """Suggestions to validate (all platforms, no selector). Green when nothing left."""
    st.subheader(t("track_mapping.suggest_header", "🔎 Suggestions à valider"))
    all_sugg, disp = _build_all_suggestions(db, artist_id, canonical, links_df)
    if disp.empty:
        st.success(t("track_mapping.nothing_to_map",
                     "✅ Rien à mapper (tout est déjà lié ou rejeté)."))
        return
    st.caption(t("track_mapping.legend",
                 "Score = similarité du nom **+** proximité de date (si la plateforme "
                 "l'expose). Fiabilité : 🟢 ≥80 % · 🟡 50–80 % · 🔴 <50 %. Cochez "
                 "**Accepter** (ou **Rejeter** pour ne plus proposer), puis enregistrez."))
    edited = st.data_editor(
        disp, hide_index=True, width='stretch', key="ed_all_tracks",
        on_change=_mutex_checkboxes, args=("ed_all_tracks", "Accepter", "Rejeter"),
        column_config={
            'Plateforme': st.column_config.TextColumn("Plateforme", width="small"),
            'Fiab.': st.column_config.TextColumn("Fiab.", width="small"),
            'Titre plateforme': st.column_config.TextColumn("Titre plateforme", width="large"),
            'Suggestion (track)': st.column_config.TextColumn("Suggestion (track)", width="medium"),
            'Confiance': st.column_config.ProgressColumn(
                t("track_mapping.col_confidence", "Confiance"),
                min_value=0.0, max_value=100.0, format="%.0f%%", width="small"),
            'Accepter': st.column_config.CheckboxColumn(
                t("track_mapping.col_accept", "Accepter"), width="small"),
            'Rejeter': st.column_config.CheckboxColumn(
                t("track_mapping.col_reject", "Rejeter"), width="small"),
        },
        disabled=['Plateforme', 'Fiab.', 'Titre plateforme', 'Suggestion (track)', 'Confiance'])
    if st.button(t("track_mapping.save_links_button", "💾 Enregistrer les liens"),
                 type="primary"):
        n = _save_all_links(db, artist_id, all_sugg, edited)
        st.success(t("track_mapping.links_saved", "{n} lien(s) enregistré(s).").format(n=n))
        st.rerun()


def _render_coverage_grid(canonical, links_df):
    """Recap: ✅ green where a platform is linked, · otherwise. Cross-platform presence
    only — Meta-campaign info lives in the 📣 Campagnes Meta tab."""
    confirmed = links_df[links_df.status == 'confirmed'] if not links_df.empty else links_df
    st.subheader(t("track_mapping.coverage_header", "🗺️ Couverture cross-plateforme (récap)"))
    grid_rows = []
    for tr in canonical:
        row = {t("track_mapping.col_track", "Track"): tr['title'],
               t("track_mapping.col_release", "Sortie"): str(tr['release_date'] or '—')}
        for pkey, _ in _PLATFORMS:
            linked = (not confirmed.empty and not confirmed[
                (confirmed.match_key == tr['match_key']) & (confirmed.platform == pkey)].empty)
            row[_PLATFORM_SHORT[pkey]] = "✅" if linked else "·"
        grid_rows.append(row)

    grid = pd.DataFrame(grid_rows)
    plat_cols = [_PLATFORM_SHORT[k] for k, _ in _PLATFORMS]

    def _green(v):
        return 'background-color: #1e7d3322; color: #1b8a3a; font-weight: 600' if v == "✅" else ''

    st.dataframe(grid.style.map(_green, subset=plat_cols), hide_index=True, width='stretch')
    st.caption(t("track_mapping.coverage_legend",
                 "✅ = plateforme liée · « · » = non liée. (Les campagnes Meta sont dans "
                 "l'onglet **📣 Campagnes Meta**.)"))


def render_overview_tab(db, artist_id, canonical):
    links_df = _load_links(db, artist_id)
    # Suggestions on top (green when nothing) …
    _render_track_suggestions(db, artist_id, canonical, links_df)
    st.markdown("---")
    # … cross-platform coverage recap just below.
    _render_coverage_grid(canonical, links_df)
