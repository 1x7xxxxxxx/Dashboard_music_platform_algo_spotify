"""Meta × Spotify campaign-to-track mapping manager.

Type: Feature
Depends on: src/dashboard/utils (get_db_connection)
Persists in: campaign_track_mapping (PostgreSQL spotify_etl)
"""
import streamlit as st

from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t


def _load_campaigns(db, artist_id: int) -> list[str]:
    rows = db.fetch_query(
        "SELECT campaign_name FROM meta_campaigns "
        "WHERE artist_id = %s GROUP BY campaign_name "
        "ORDER BY MAX(start_time) DESC NULLS LAST, campaign_name",
        (artist_id,)
    )
    return [r[0] for r in rows]


def _load_tracks(db, artist_id: int) -> list[str]:
    # Source: s4a_song_timeline (integer artist_id, multi-tenant). The legacy
    # `tracks` table stores Spotify-API artist_id as varchar (single-tenant),
    # incompatible with the SaaS integer key. Mandatory 1x7 filter per CLAUDE.md.
    rows = db.fetch_query(
        "SELECT DISTINCT song FROM s4a_song_timeline "
        "WHERE artist_id = %s AND song NOT ILIKE %s "
        "ORDER BY song",
        (artist_id, "%1x7xxxxxxx%")
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
                 "Associez vos campagnes Meta Ads aux titres Spotify pour l'analyse d'attribution."))

    with view_session() as (db, artist_id):
        tab_list, tab_add = st.tabs([
            t("meta_mapping.tab_existing", "Mappings existants"),
            t("meta_mapping.tab_add", "Ajouter / Supprimer"),
        ])

        # ── Tab 1 : existing mappings ─────────────────────────────────────────
        with tab_list:
            df = _load_mappings(db, artist_id)
            if df.empty:
                st.info(t("meta_mapping.no_mappings",
                          "Aucun mapping pour le moment. Utilisez l'onglet **Ajouter / Supprimer** pour en créer un."))
            else:
                st.dataframe(
                    df[["campaign_name", "track_name", "created_at"]],
                    width="stretch",
                    hide_index=True,
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
                    "Aucun titre trouvé dans `tracks`. "
                    "Lancez d'abord le DAG Spotify API."
                ))
                return

            with st.form("add_mapping_form"):
                campaign = st.selectbox(t("meta_mapping.meta_campaign", "Campagne Meta"), campaigns)
                track = st.selectbox(t("meta_mapping.spotify_track", "Titre Spotify"), tracks)
                submitted = st.form_submit_button(t("meta_mapping.add_btn", "➕ Ajouter le mapping"), type="primary")

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
