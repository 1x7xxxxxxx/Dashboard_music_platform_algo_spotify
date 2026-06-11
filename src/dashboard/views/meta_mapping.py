"""Meta × Spotify campaign-to-track mapping manager.

Type: Feature
Depends on: src/dashboard/utils (view_session), track_mapping_suggest (engine),
            track_matching (canonical_song)
Persists in: campaign_track_mapping (PostgreSQL spotify_etl)

Single home for campaign↔track mapping. Auto-suggestions (title-similarity + release-
date proximity against track_release_reference) are offered at the TOP; manual add +
existing list below. Both paths write the SAME campaign_track_mapping table consumed by
meta_x_spotify, the ROI Breakheaven and the PDF export.
"""
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t
from src.utils.track_matching import canonical_song
from src.utils.track_mapping_suggest import confidence_badge, rank_campaign_candidates

_S4A_FILTER = "%1x7xxxxxxx%"


# ── Auto-suggestion data layer ────────────────────────────────────────────────
def _load_canonical(db, artist_id: int):
    rows = db.fetch_query(
        "SELECT match_key, title, release_date FROM track_release_reference "
        "WHERE artist_id = %s ORDER BY title",
        (artist_id,))
    return [{'match_key': r[0], 'title': r[1], 'release_date': r[2]} for r in (rows or [])]


def _load_unmapped_campaigns(db, artist_id: int):
    """Meta campaigns with no mapping yet → [{campaign, start}]."""
    rows = db.fetch_query(
        "SELECT campaign_name, MAX(start_time) FROM meta_campaigns mc "
        "WHERE mc.artist_id = %s AND NOT EXISTS ("
        "  SELECT 1 FROM campaign_track_mapping ctm "
        "  WHERE ctm.artist_id = mc.artist_id AND ctm.campaign_name = mc.campaign_name) "
        "GROUP BY campaign_name ORDER BY MAX(start_time) DESC NULLS LAST",
        (artist_id,))
    return [{'campaign': r[0], 'start': r[1]} for r in (rows or []) if r[0]]


def _build_campaign_suggestions(db, artist_id: int, canonical):
    """Unmapped campaign → best track via title-sim + release-date proximity. Weak
    matches (junk titles) are flagged 🔴, never hidden, so the choice stays the user's."""
    sugg, disp = [], []
    for c in _load_unmapped_campaigns(db, artist_id):
        cands = rank_campaign_candidates(c['campaign'], c['start'], canonical, set(), top_n=1)
        if not cands:
            continue
        cand = cands[0]
        # track_name stored in `_`-form to match s4a_song_timeline.song (the join key
        # used by meta_x_spotify) + the manual campaign_track_mapping convention.
        sugg.append({'campaign': c['campaign'], 'track_name': canonical_song(cand.title),
                     'confidence': cand.score, 'method': cand.method})
        disp.append({'Fiab.': confidence_badge(cand.score), 'Campagne': c['campaign'],
                     'Suggestion (track)': cand.title, 'Confiance': cand.score,
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


def _render_auto_suggestions(db, artist_id: int):
    st.subheader(t("meta_mapping.auto_header", "🤖 Suggestions automatiques (campagne → titre)"))
    canonical = _load_canonical(db, artist_id)
    if not canonical:
        st.info(t("meta_mapping.auto_no_reference",
                  "Référence de titres absente — importez vos CSV S4A puis reconstruisez "
                  "la référence dans **🧩 Mapping multi-plateformes**."))
        return
    sugg, disp = _build_campaign_suggestions(db, artist_id, canonical)
    if disp.empty:
        st.success(t("meta_mapping.auto_done",
                     "✅ Toutes les campagnes Meta sont déjà associées (ou aucune collectée)."))
        return
    st.caption(t("meta_mapping.auto_legend",
                 "Score = similarité du nom **et** proximité avec la date de sortie. "
                 "Fiabilité : 🟢 ≥ 80 % · 🟡 50–80 % · 🔴 < 50 % (souvent un titre parasite : "
                 "DJ set, autre artiste). Cochez **Associer** puis enregistrez."))
    edited = st.data_editor(
        disp, hide_index=True, width="stretch", key="ed_auto_camp",
        column_config={
            'Confiance': st.column_config.ProgressColumn(
                t("meta_mapping.col_confidence", "Confiance"),
                min_value=0.0, max_value=1.0, format="%.0f%%"),
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


# ── Manual add / existing list ────────────────────────────────────────────────
def _load_campaigns(db, artist_id: int) -> list[str]:
    rows = db.fetch_query(
        "SELECT campaign_name FROM meta_campaigns "
        "WHERE artist_id = %s GROUP BY campaign_name "
        "ORDER BY MAX(start_time) DESC NULLS LAST, campaign_name",
        (artist_id,)
    )
    return [r[0] for r in rows]


def _load_tracks(db, artist_id: int) -> list[str]:
    # Source: s4a_song_timeline (integer artist_id, multi-tenant). Mandatory 1x7 filter.
    rows = db.fetch_query(
        "SELECT DISTINCT song FROM s4a_song_timeline "
        "WHERE artist_id = %s AND song NOT ILIKE %s "
        "ORDER BY song",
        (artist_id, _S4A_FILTER)
    )
    return [r[0] for r in rows]


def _load_mappings(db, artist_id: int):
    return db.fetch_df(
        "SELECT id, campaign_name, track_name, created_at "
        "FROM campaign_track_mapping "
        "WHERE artist_id = %s ORDER BY created_at DESC",
        (artist_id,)
    )


def show():
    st.title(t("meta_mapping.title", "🔗 Meta × Spotify — Mapping campagnes"))
    st.caption(t("meta_mapping.subtitle",
                 "Associez vos campagnes Meta Ads aux titres Spotify pour l'analyse "
                 "d'attribution. Les suggestions automatiques et l'ajout manuel "
                 "alimentent le même mapping (vues META × Spotify + ROI Breakheaven)."))

    with view_session() as (db, artist_id):
        # ── Auto-suggestions on top ───────────────────────────────────────────
        _render_auto_suggestions(db, artist_id)
        st.markdown("---")

        tab_list, tab_add = st.tabs([
            t("meta_mapping.tab_existing", "Mappings existants"),
            t("meta_mapping.tab_add", "Ajout manuel"),
        ])

        # ── Tab 1 : existing mappings ─────────────────────────────────────────
        with tab_list:
            df = _load_mappings(db, artist_id)
            if df.empty:
                st.info(t("meta_mapping.no_mappings",
                          "Aucun mapping pour le moment. Utilisez les suggestions "
                          "ci-dessus ou l'onglet **Ajout manuel**."))
            else:
                st.dataframe(
                    df[["campaign_name", "track_name", "created_at"]],
                    width="stretch", hide_index=True,
                )
                st.markdown("---")
                st.subheader(t("meta_mapping.delete_title", "Supprimer un mapping"))
                mapping_options = {
                    f"{row['campaign_name']} → {row['track_name']}": row["id"]
                    for _, row in df.iterrows()
                }
                selected_label = st.selectbox(
                    t("meta_mapping.select_delete", "Sélectionnez le mapping à supprimer"),
                    list(mapping_options.keys())
                )
                if st.button(t("common.delete", "🗑️ Supprimer"), type="secondary"):
                    mapping_id = mapping_options[selected_label]
                    db.execute_query(
                        "DELETE FROM campaign_track_mapping WHERE id = %s AND artist_id = %s",
                        (mapping_id, artist_id)
                    )
                    st.success(t("meta_mapping.deleted", "Supprimé : {label}").format(label=selected_label))
                    st.rerun()

        # ── Tab 2 : add mapping ───────────────────────────────────────────────
        with tab_add:
            campaigns = _load_campaigns(db, artist_id)
            tracks = _load_tracks(db, artist_id)
            if not campaigns:
                st.warning(t(
                    "meta_mapping.no_campaigns",
                    "Aucune campagne trouvée dans `meta_campaigns`. "
                    "Lancez d'abord le DAG Meta Ads."
                ))
                return
            if not tracks:
                st.warning(t(
                    "meta_mapping.no_tracks",
                    "Aucun titre trouvé. Importez d'abord vos CSV S4A."
                ))
                return

            with st.form("add_mapping_form"):
                campaign = st.selectbox(t("meta_mapping.meta_campaign", "Campagne Meta"), campaigns)
                track = st.selectbox(t("meta_mapping.spotify_track", "Titre Spotify"), tracks)
                submitted = st.form_submit_button(
                    t("meta_mapping.add_btn", "➕ Ajouter le mapping"), type="primary")

            if submitted:
                db.execute_query(
                    """
                    INSERT INTO campaign_track_mapping (artist_id, campaign_name, track_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (artist_id, campaign_name, track_name) DO NOTHING
                    """,
                    (artist_id, campaign, track)
                )
                st.success(t("meta_mapping.mapped", "Associé : **{campaign}** → **{track}**")
                           .format(campaign=campaign, track=track))
                st.rerun()
