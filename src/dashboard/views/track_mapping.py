"""Cross-platform track mapping — unified track ↔ platform links with auto-suggestions.

Type: Feature
Uses: get_db_connection, track_matching (canonical reference), track_mapping_suggest (engine)
Persists in: track_platform_link (PostgreSQL spotify_etl)
Depends on: track_release_reference (canonical track dimension, keyed by match_key)

Free-tier feature. The canonical track list comes from track_release_reference (built
from S4A by rebuild_release_reference); each platform's free-text titles are scored
against it by the pure suggestion engine, then the artist accepts/rejects the links.
"""
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from src.dashboard.utils import view_session
from src.utils.track_matching import canonical_song, rebuild_release_reference
from src.utils.track_mapping_suggest import rank_campaign_candidates, rank_track_candidates

# (platform_key, human label). platform_key is a fixed enum (never user input).
_PLATFORMS = [
    ('s4a', 'Spotify (S4A)'),
    ('spotify', 'Spotify (API)'),
    ('apple', 'Apple Music'),
    ('soundcloud', 'SoundCloud'),
    ('youtube', 'YouTube'),
]
_S4A_FILTER = "%1x7xxxxxxx%"


def _load_canonical(db, artist_id):
    rows = db.fetch_query(
        "SELECT match_key, title, release_date FROM track_release_reference "
        "WHERE artist_id = %s ORDER BY title",
        (artist_id,))
    return [{'match_key': r[0], 'title': r[1], 'release_date': r[2]} for r in (rows or [])]


def _load_platform_titles(db, artist_id, platform):
    """[{title, ref_id}] of distinct platform-local titles. Normalization happens in
    the engine, so the S4A `_`-form vs real-char difference is irrelevant here."""
    q = {
        's4a': ("SELECT DISTINCT song, NULL FROM s4a_song_timeline "
                "WHERE artist_id = %s AND song NOT ILIKE %s", (artist_id, _S4A_FILTER)),
        'spotify': ("SELECT DISTINCT track_name, MAX(track_id) FROM tracks "
                    "WHERE saas_artist_id = %s AND track_name IS NOT NULL "
                    "GROUP BY track_name", (artist_id,)),
        'apple': ("SELECT DISTINCT song_name, NULL FROM apple_songs_performance "
                  "WHERE artist_id = %s AND song_name IS NOT NULL", (artist_id,)),
        'soundcloud': ("SELECT title, MAX(track_id) FROM soundcloud_tracks_daily "
                       "WHERE artist_id = %s AND title IS NOT NULL GROUP BY title",
                       (artist_id,)),
        'youtube': ("SELECT title, MAX(video_id) FROM youtube_videos "
                    "WHERE artist_id = %s AND title IS NOT NULL GROUP BY title", (artist_id,)),
    }.get(platform)
    if not q:
        return []
    try:
        rows = db.fetch_query(q[0], q[1])
    except Exception:
        return []
    return [{'title': r[0], 'ref_id': r[1]} for r in (rows or []) if r[0]]


def _load_links(db, artist_id):
    return db.fetch_df(
        "SELECT match_key, platform, platform_title, status, confidence "
        "FROM track_platform_link WHERE artist_id = %s",
        (artist_id,))


def _save_links(db, artist_id, platform, sugg, edited):
    """Upsert accepted (confirmed) / rejected (tombstone) rows. Returns count written."""
    now = datetime.now(timezone.utc)
    data = []
    for i, row in edited.reset_index(drop=True).iterrows():
        status = 'confirmed' if row.get('Accepter') else 'rejected' if row.get('Rejeter') else None
        if status is None or i >= len(sugg):
            continue
        s = sugg[i]
        data.append({'artist_id': artist_id, 'match_key': s['match_key'], 'platform': platform,
                     'platform_title': s['platform_title'], 'platform_ref_id': s['ref_id'],
                     'status': status, 'confidence': s['confidence'], 'method': s['method'],
                     'updated_at': now})
    if data:
        db.upsert_many(
            'track_platform_link', data,
            conflict_columns=['artist_id', 'platform', 'platform_title', 'match_key'],
            update_columns=['status', 'confidence', 'method', 'updated_at'])
    return len(data)


def _build_suggestions(db, artist_id, platform, canonical, links_df):
    """Per-platform unmapped titles → top candidate. Returns (sugg list, display df)."""
    seen = set()
    if not links_df.empty:
        seen = {(r.platform_title) for r in
                links_df[links_df.platform == platform].itertuples()}
    confirmed_keys = (set(links_df[links_df.status == 'confirmed'].match_key)
                      if not links_df.empty else set())
    sugg, disp = [], []
    for item in _load_platform_titles(db, artist_id, platform):
        if item['title'] in seen:
            continue  # already confirmed/rejected for this platform
        cands = rank_track_candidates(item['title'], canonical, confirmed_keys, top_n=1)
        if not cands:
            continue
        c = cands[0]
        sugg.append({'platform_title': item['title'], 'ref_id': item['ref_id'],
                     'match_key': c.match_key, 'confidence': c.score, 'method': c.method})
        disp.append({'Titre plateforme': item['title'], 'Suggestion (track)': c.title,
                     'Confiance': c.score, 'Accepter': c.score >= 0.8, 'Rejeter': False})
    return sugg, pd.DataFrame(disp)


def _load_unmapped_campaigns(db, artist_id):
    """Meta campaigns with no mapping yet → [{campaign, start}]."""
    rows = db.fetch_query(
        "SELECT campaign_name, MAX(start_time) FROM meta_campaigns mc "
        "WHERE mc.artist_id = %s AND NOT EXISTS ("
        "  SELECT 1 FROM campaign_track_mapping ctm "
        "  WHERE ctm.artist_id = mc.artist_id AND ctm.campaign_name = mc.campaign_name) "
        "GROUP BY campaign_name ORDER BY MAX(start_time) DESC NULLS LAST",
        (artist_id,))
    return [{'campaign': r[0], 'start': r[1]} for r in (rows or []) if r[0]]


def _build_campaign_suggestions(db, artist_id, canonical, confirmed_keys):
    """Unmapped campaign → best track via title-sim + release-date proximity."""
    sugg, disp = [], []
    for c in _load_unmapped_campaigns(db, artist_id):
        cands = rank_campaign_candidates(c['campaign'], c['start'], canonical,
                                         confirmed_keys, top_n=1)
        if not cands:
            continue
        cand = cands[0]
        # track_name stored in `_`-form to match s4a_song_timeline.song (the join key
        # used by meta_x_spotify) + the manual campaign_track_mapping convention.
        sugg.append({'campaign': c['campaign'], 'track_name': canonical_song(cand.title),
                     'confidence': cand.score, 'method': cand.method})
        disp.append({'Campagne': c['campaign'], 'Suggestion (track)': cand.title,
                     'Confiance': cand.score, 'Méthode': cand.method,
                     'Associer': cand.score >= 0.6})
    return sugg, pd.DataFrame(disp)


def _save_campaign_links(db, artist_id, sugg, edited):
    now_method = 'auto'  # provenance flag carried by auto_suggested
    data = []
    for i, row in edited.reset_index(drop=True).iterrows():
        if not row.get('Associer') or i >= len(sugg):
            continue
        s = sugg[i]
        data.append({'artist_id': artist_id, 'campaign_name': s['campaign'],
                     'track_name': s['track_name'], 'confidence': s['confidence'],
                     'method': s['method'] or now_method, 'auto_suggested': True})
    if data:
        db.upsert_many(
            'campaign_track_mapping', data,
            conflict_columns=['artist_id', 'campaign_name', 'track_name'],
            update_columns=['confidence', 'method', 'auto_suggested'])
    return len(data)


def _render_matrix(canonical, links_df):
    confirmed = links_df[links_df.status == 'confirmed'] if not links_df.empty else links_df
    rows = []
    for t in canonical:
        row = {'Track': t['title'], 'Sortie': str(t['release_date'] or '—')}
        for pkey, plabel in _PLATFORMS:
            cell = '—'
            if not confirmed.empty:
                m = confirmed[(confirmed.match_key == t['match_key'])
                              & (confirmed.platform == pkey)]
                if not m.empty:
                    cell = str(m.iloc[0]['platform_title'])
            row[plabel] = cell
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')


def show():
    st.title("🧩 Mapping multi-plateformes")
    st.caption("Reliez automatiquement vos titres entre plateformes (Spotify, Apple, "
               "SoundCloud, YouTube) à partir de la similarité des noms.")

    with view_session() as (db, artist_id):
        canonical = _load_canonical(db, artist_id)
        if not canonical:
            st.info("Aucune référence de titres trouvée. Importez vos CSV S4A puis "
                    "reconstruisez la référence ci-dessous.")
            if st.button("🔄 Reconstruire la référence des titres"):
                n = rebuild_release_reference(db, artist_id)
                st.success(f"{n} titre(s) de référence reconstruits.")
                st.rerun()
            return

        tab_sugg, tab_camp, tab_matrix = st.tabs(
            ["Suggestions par plateforme", "Meta campagnes", "Vue unifiée"])

        with tab_sugg:
            links_df = _load_links(db, artist_id)
            plabels = {k: v for k, v in _PLATFORMS}
            pkey = st.selectbox("Plateforme", [k for k, _ in _PLATFORMS],
                                format_func=lambda k: plabels[k])
            sugg, disp = _build_suggestions(db, artist_id, pkey, canonical, links_df)
            if disp.empty:
                st.success("✅ Rien à mapper ici (tout est déjà lié ou rejeté).")
            else:
                st.caption("🟢 ≥80 % · 🟡 50–80 % · 🔴 <50 %. Cochez **Accepter** (ou "
                           "**Rejeter** pour ne plus proposer), puis enregistrez.")
                edited = st.data_editor(
                    disp, hide_index=True, width='stretch', key=f"ed_{pkey}",
                    column_config={
                        'Confiance': st.column_config.ProgressColumn(
                            'Confiance', min_value=0.0, max_value=1.0, format="%.0f%%"),
                        'Accepter': st.column_config.CheckboxColumn('Accepter'),
                        'Rejeter': st.column_config.CheckboxColumn('Rejeter'),
                    },
                    disabled=['Titre plateforme', 'Suggestion (track)', 'Confiance'])
                if st.button("💾 Enregistrer les liens", type="primary"):
                    n = _save_links(db, artist_id, pkey, sugg, edited)
                    st.success(f"{n} lien(s) enregistré(s).")
                    st.rerun()

        with tab_camp:
            links_df = _load_links(db, artist_id)
            confirmed_keys = (set(links_df[links_df.status == 'confirmed'].match_key)
                              if not links_df.empty else set())
            sugg, disp = _build_campaign_suggestions(db, artist_id, canonical, confirmed_keys)
            if disp.empty:
                st.info("Aucune campagne Meta à associer (toutes déjà mappées, ou aucune "
                        "campagne collectée).")
            else:
                st.caption("Suggestions basées sur la similarité du nom de campagne **et** la "
                           "proximité avec la date de sortie du titre.")
                edited = st.data_editor(
                    disp, hide_index=True, width='stretch', key="ed_camp",
                    column_config={
                        'Confiance': st.column_config.ProgressColumn(
                            'Confiance', min_value=0.0, max_value=1.0, format="%.0f%%"),
                        'Associer': st.column_config.CheckboxColumn('Associer'),
                    },
                    disabled=['Campagne', 'Suggestion (track)', 'Confiance', 'Méthode'])
                if st.button("💾 Associer les campagnes", type="primary"):
                    n = _save_campaign_links(db, artist_id, sugg, edited)
                    st.success(f"{n} campagne(s) associée(s).")
                    st.rerun()

        with tab_matrix:
            _render_matrix(canonical, _load_links(db, artist_id))
