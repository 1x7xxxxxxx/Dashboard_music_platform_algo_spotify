"""Cross-platform mapping — one home for all track/campaign links.

Type: Feature
Uses: view_session, track_matching (canonical reference + canonical_song),
      track_mapping_suggest (scoring engine)
Persists in: track_platform_link (cross-platform tracks) + campaign_track_mapping
             (Meta campaigns) — both in PostgreSQL spotify_etl

Free-tier. Three tabs:
  1. Cross-platform tracks — each platform's free-text titles scored against the
     canonical track_release_reference (title similarity + release-date proximity
     where the platform exposes a date); accept/reject → track_platform_link.
  2. Meta campaigns — auto-suggestions (title + campaign-start proximity) on top,
     manual add + existing list below → campaign_track_mapping.
  3. Unified matrix — canonical tracks × confirmed platform links.
Both campaign paths feed meta_x_spotify, the ROI Breakeven and the PDF export.
Confidence is stored in [0,1]; only the displayed % column is scaled ×100 (a raw
[0,1] value in a ProgressColumn with a "%" format would render "0%").
"""
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t
from src.utils.track_matching import canonical_song, rebuild_release_reference
from src.utils.track_mapping_suggest import (
    confidence_badge,
    rank_campaign_candidates,
    rank_track_candidates,
)

# (platform_key, human label). platform_key is a fixed enum (never user input).
_PLATFORMS = [
    ('s4a', 'Spotify (S4A)'),
    ('spotify', 'Spotify (API)'),
    ('apple', 'Apple Music'),
    ('soundcloud', 'SoundCloud'),
    ('youtube', 'YouTube'),
]
_S4A_FILTER = "%1x7xxxxxxx%"


# ── Canonical + cross-platform tracks ─────────────────────────────────────────
def _load_canonical(db, artist_id):
    rows = db.fetch_query(
        "SELECT match_key, title, release_date FROM track_release_reference "
        "WHERE artist_id = %s ORDER BY title",
        (artist_id,))
    return [{'match_key': r[0], 'title': r[1], 'release_date': r[2]} for r in (rows or [])]


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


def _render_matrix(canonical, links_df):
    confirmed = links_df[links_df.status == 'confirmed'] if not links_df.empty else links_df
    rows = []
    col_track = t("track_mapping.col_track", "Track")
    col_release = t("track_mapping.col_release", "Sortie")
    for tr in canonical:
        row = {col_track: tr['title'], col_release: str(tr['release_date'] or '—')}
        for pkey, plabel in _PLATFORMS:
            cell = '—'
            if not confirmed.empty:
                m = confirmed[(confirmed.match_key == tr['match_key'])
                              & (confirmed.platform == pkey)]
                if not m.empty:
                    cell = str(m.iloc[0]['platform_title'])
            row[plabel] = cell
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')


def _render_track_tab(db, artist_id, canonical):
    links_df = _load_links(db, artist_id)
    plabels = dict(_PLATFORMS)
    pkey = st.selectbox(t("track_mapping.platform_label", "Plateforme"),
                        [k for k, _ in _PLATFORMS],
                        format_func=lambda k: plabels[k])
    sugg, disp = _build_suggestions(db, artist_id, pkey, canonical, links_df)
    if disp.empty:
        st.success(t("track_mapping.nothing_to_map",
                     "✅ Rien à mapper ici (tout est déjà lié ou rejeté)."))
        return
    st.caption(t("track_mapping.legend",
                 "Score = similarité du nom **+** proximité de date (si la plateforme "
                 "l'expose). Fiabilité : 🟢 ≥80 % · 🟡 50–80 % · 🔴 <50 %. Cochez "
                 "**Accepter** (ou **Rejeter** pour ne plus proposer), puis enregistrez."))
    edited = st.data_editor(
        disp, hide_index=True, width='stretch', key=f"ed_{pkey}",
        column_config={
            'Confiance': st.column_config.ProgressColumn(
                t("track_mapping.col_confidence", "Confiance"),
                min_value=0.0, max_value=100.0, format="%.0f%%"),
            'Accepter': st.column_config.CheckboxColumn(
                t("track_mapping.col_accept", "Accepter")),
            'Rejeter': st.column_config.CheckboxColumn(
                t("track_mapping.col_reject", "Rejeter")),
        },
        disabled=['Fiab.', 'Titre plateforme', 'Suggestion (track)', 'Confiance'])
    if st.button(t("track_mapping.save_links_button", "💾 Enregistrer les liens"),
                 type="primary"):
        n = _save_links(db, artist_id, pkey, sugg, edited)
        st.success(t("track_mapping.links_saved", "{n} lien(s) enregistré(s).").format(n=n))
        st.rerun()


# ── Meta campaigns ────────────────────────────────────────────────────────────
def _load_unmapped_campaigns(db, artist_id: int):
    rows = db.fetch_query(
        "SELECT campaign_name, MAX(start_time) FROM meta_campaigns mc "
        "WHERE mc.artist_id = %s AND NOT EXISTS ("
        "  SELECT 1 FROM campaign_track_mapping ctm "
        "  WHERE ctm.artist_id = mc.artist_id AND ctm.campaign_name = mc.campaign_name) "
        "GROUP BY campaign_name ORDER BY MAX(start_time) DESC NULLS LAST",
        (artist_id,))
    return [{'campaign': r[0], 'start': r[1]} for r in (rows or []) if r[0]]


def _build_campaign_suggestions(db, artist_id: int, canonical):
    """Unmapped campaign → best track via title-sim + release-date proximity. `confidence`
    kept raw [0,1]; displayed `Confiance` ×100. Weak matches flagged 🔴, never hidden."""
    sugg, disp = [], []
    for c in _load_unmapped_campaigns(db, artist_id):
        cands = rank_campaign_candidates(c['campaign'], c['start'], canonical, set(), top_n=1)
        if not cands:
            continue
        cand = cands[0]
        # track_name in `_`-form to match s4a_song_timeline.song (the meta_x_spotify join key).
        sugg.append({'campaign': c['campaign'], 'track_name': canonical_song(cand.title),
                     'confidence': cand.score, 'method': cand.method})
        disp.append({'Fiab.': confidence_badge(cand.score), 'Campagne': c['campaign'],
                     'Suggestion (track)': cand.title, 'Confiance': round(cand.score * 100, 1),
                     'Méthode': cand.method, 'Associer': cand.score >= 0.6})
    return sugg, pd.DataFrame(disp)


def _save_campaign_links(db, artist_id: int, sugg, edited):
    now = datetime.now(timezone.utc)
    data = []
    for i, row in edited.reset_index(drop=True).iterrows():
        if not row.get('Associer') or i >= len(sugg):
            continue
        s = sugg[i]
        data.append({'artist_id': artist_id, 'campaign_name': s['campaign'],
                     'track_name': s['track_name'], 'confidence': s['confidence'],
                     'method': s['method'] or 'auto', 'auto_suggested': True,
                     'created_at': now})
    if data:
        db.upsert_many(
            'campaign_track_mapping', data,
            conflict_columns=['artist_id', 'campaign_name', 'track_name'],
            update_columns=['confidence', 'method', 'auto_suggested'])
    return len(data)


def _load_campaigns(db, artist_id: int) -> list[str]:
    rows = db.fetch_query(
        "SELECT campaign_name FROM meta_campaigns WHERE artist_id = %s GROUP BY campaign_name "
        "ORDER BY MAX(start_time) DESC NULLS LAST, campaign_name", (artist_id,))
    return [r[0] for r in rows]


def _load_tracks(db, artist_id: int) -> list[str]:
    rows = db.fetch_query(
        "SELECT DISTINCT song FROM s4a_song_timeline "
        "WHERE artist_id = %s AND song NOT ILIKE %s ORDER BY song",
        (artist_id, _S4A_FILTER))
    return [r[0] for r in rows]


def _load_mappings(db, artist_id: int):
    return db.fetch_df(
        "SELECT id, campaign_name, track_name, created_at FROM campaign_track_mapping "
        "WHERE artist_id = %s ORDER BY created_at DESC", (artist_id,))


def _render_campaign_tab(db, artist_id, canonical):
    # ── Auto-suggestions (top) ──
    st.subheader(t("meta_mapping.auto_header", "🤖 Suggestions automatiques (campagne → titre)"))
    sugg, disp = _build_campaign_suggestions(db, artist_id, canonical)
    if disp.empty:
        st.success(t("meta_mapping.auto_done",
                     "✅ Toutes les campagnes Meta sont déjà associées (ou aucune collectée)."))
    else:
        st.caption(t("meta_mapping.auto_legend",
                     "Score = similarité du nom **et** proximité avec la date de sortie. "
                     "Fiabilité : 🟢 ≥ 80 % · 🟡 50–80 % · 🔴 < 50 % (souvent un titre parasite : "
                     "DJ set, autre artiste). Cochez **Associer** puis enregistrez."))
        edited = st.data_editor(
            disp, hide_index=True, width="stretch", key="ed_auto_camp",
            column_config={
                'Confiance': st.column_config.ProgressColumn(
                    t("meta_mapping.col_confidence", "Confiance"),
                    min_value=0.0, max_value=100.0, format="%.0f%%"),
                'Associer': st.column_config.CheckboxColumn(
                    t("meta_mapping.col_associate", "Associer")),
            },
            disabled=['Fiab.', 'Campagne', 'Suggestion (track)', 'Confiance', 'Méthode'])
        if st.button(t("meta_mapping.associate_button", "💾 Associer les campagnes cochées"),
                     type="primary"):
            n = _save_campaign_links(db, artist_id, sugg, edited)
            st.success(t("meta_mapping.campaigns_associated",
                         "{n} campagne(s) associée(s).").format(n=n))
            st.rerun()

    st.markdown("---")
    # ── Existing + manual ──
    sub_existing, sub_add = st.tabs([
        t("meta_mapping.tab_existing", "Mappings existants"),
        t("meta_mapping.tab_add", "Ajout manuel"),
    ])
    with sub_existing:
        df = _load_mappings(db, artist_id)
        if df.empty:
            st.info(t("meta_mapping.no_mappings",
                      "Aucun mapping pour le moment. Utilisez les suggestions ci-dessus ou "
                      "l'onglet **Ajout manuel**."))
        else:
            st.dataframe(df[["campaign_name", "track_name", "created_at"]],
                         width="stretch", hide_index=True)
            st.markdown("---")
            st.subheader(t("meta_mapping.delete_title", "Supprimer un mapping"))
            options = {f"{r['campaign_name']} → {r['track_name']}": r["id"]
                       for _, r in df.iterrows()}
            sel = st.selectbox(
                t("meta_mapping.select_delete", "Sélectionnez le mapping à supprimer"),
                list(options.keys()))
            if st.button(t("common.delete", "🗑️ Supprimer"), type="secondary"):
                db.execute_query(
                    "DELETE FROM campaign_track_mapping WHERE id = %s AND artist_id = %s",
                    (options[sel], artist_id))
                st.success(t("meta_mapping.deleted", "Supprimé : {label}").format(label=sel))
                st.rerun()
    with sub_add:
        campaigns = _load_campaigns(db, artist_id)
        tracks = _load_tracks(db, artist_id)
        if not campaigns:
            st.warning(t("meta_mapping.no_campaigns",
                         "Aucune campagne trouvée dans `meta_campaigns`. "
                         "Lancez d'abord le DAG Meta Ads."))
            return
        if not tracks:
            st.warning(t("meta_mapping.no_tracks",
                         "Aucun titre trouvé. Importez d'abord vos CSV S4A."))
            return
        with st.form("add_mapping_form"):
            campaign = st.selectbox(t("meta_mapping.meta_campaign", "Campagne Meta"), campaigns)
            track = st.selectbox(t("meta_mapping.spotify_track", "Titre Spotify"), tracks)
            submitted = st.form_submit_button(
                t("meta_mapping.add_btn", "➕ Ajouter le mapping"), type="primary")
        if submitted:
            db.execute_query(
                "INSERT INTO campaign_track_mapping (artist_id, campaign_name, track_name) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (artist_id, campaign_name, track_name) DO NOTHING",
                (artist_id, campaign, track))
            st.success(t("meta_mapping.mapped", "Associé : **{campaign}** → **{track}**")
                       .format(campaign=campaign, track=track))
            st.rerun()


def show():
    st.title(t("meta_mapping.title", "🔗 Mapping cross-plateforme"))
    st.caption(t("meta_mapping.subtitle",
                 "Reliez vos titres entre plateformes (Spotify, Apple, SoundCloud, YouTube) "
                 "et associez vos campagnes Meta Ads aux titres. Suggestions automatiques + "
                 "saisie manuelle alimentent META × Spotify et le ROI Breakheaven."))

    with view_session() as (db, artist_id):
        canonical = _load_canonical(db, artist_id)
        if not canonical:
            st.info(t("track_mapping.no_reference",
                      "Aucune référence de titres trouvée. Importez vos CSV S4A puis "
                      "reconstruisez la référence ci-dessous."))
            if st.button(t("track_mapping.rebuild_button",
                           "🔄 Reconstruire la référence des titres")):
                n = rebuild_release_reference(db, artist_id)
                st.success(t("track_mapping.rebuilt",
                             "{n} titre(s) de référence reconstruits.").format(n=n))
                st.rerun()
            return

        tab_tracks, tab_camp, tab_matrix = st.tabs(
            [t("meta_mapping.tab_tracks", "🎵 Titres cross-plateformes"),
             t("meta_mapping.tab_campaigns", "📣 Campagnes Meta"),
             t("track_mapping.tab_matrix", "🧩 Vue unifiée")])

        with tab_tracks:
            _render_track_tab(db, artist_id, canonical)
        with tab_camp:
            _render_campaign_tab(db, artist_id, canonical)
        with tab_matrix:
            _render_matrix(canonical, _load_links(db, artist_id))
