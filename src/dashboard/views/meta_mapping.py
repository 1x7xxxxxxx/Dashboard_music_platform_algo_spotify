"""Meta × Spotify campaign-to-track mapping manager.

Type: Feature
Depends on: src/dashboard/utils (get_db_connection)
Persists in: campaign_track_mapping (PostgreSQL spotify_etl)
"""
import streamlit as st

from src.dashboard.utils import get_db_connection


def _load_campaigns(db) -> list[str]:
    rows = db.fetch_query(
        "SELECT DISTINCT campaign_name FROM meta_campaigns ORDER BY campaign_name"
    )
    return [r[0] for r in rows]


def _load_tracks(db) -> list[str]:
    rows = db.fetch_query(
        "SELECT DISTINCT track_name FROM tracks ORDER BY track_name"
    )
    return [r[0] for r in rows]


def _load_mappings(db):
    return db.fetch_df(
        "SELECT id, campaign_name, track_name, created_at "
        "FROM campaign_track_mapping ORDER BY created_at DESC"
    )


def show():
    if st.session_state.get("role") != "admin":
        st.warning("Access restricted to administrators.")
        return

    st.title("🔗 Meta × Spotify — Campaign Mapping")
    st.caption("Link Meta ad campaigns to Spotify track names for attribution analysis.")

    db = get_db_connection()
    if db is None:
        st.error("Database unreachable.")
        return

    try:
        tab_list, tab_add = st.tabs(["Existing mappings", "Add / Remove"])

        # ── Tab 1 : existing mappings ─────────────────────────────────────────
        with tab_list:
            df = _load_mappings(db)
            if df.empty:
                st.info("No mappings yet. Use the **Add / Remove** tab to create one.")
            else:
                st.dataframe(
                    df[["campaign_name", "track_name", "created_at"]],
                    use_container_width=True,
                    hide_index=True,
                )

                st.markdown("---")
                st.subheader("Delete a mapping")

                mapping_options = {
                    f"{row['campaign_name']} → {row['track_name']}": row["id"]
                    for _, row in df.iterrows()
                }
                selected_label = st.selectbox(
                    "Select mapping to delete", list(mapping_options.keys())
                )
                if st.button("🗑️ Delete", type="secondary"):
                    mapping_id = mapping_options[selected_label]
                    db.execute_query(
                        "DELETE FROM campaign_track_mapping WHERE id = %s",
                        (mapping_id,)
                    )
                    st.success(f"Deleted: {selected_label}")
                    st.rerun()

        # ── Tab 2 : add mapping ───────────────────────────────────────────────
        with tab_add:
            campaigns = _load_campaigns(db)
            tracks = _load_tracks(db)

            if not campaigns:
                st.warning(
                    "No campaigns found in `meta_campaigns`. "
                    "Run the Meta Ads DAG first."
                )
                return
            if not tracks:
                st.warning(
                    "No tracks found in `tracks`. "
                    "Run the Spotify API DAG first."
                )
                return

            with st.form("add_mapping_form"):
                campaign = st.selectbox("Meta campaign", campaigns)
                track = st.selectbox("Spotify track", tracks)
                submitted = st.form_submit_button("➕ Add mapping", type="primary")

            if submitted:
                db.execute_query(
                    """
                    INSERT INTO campaign_track_mapping (campaign_name, track_name)
                    VALUES (%s, %s)
                    ON CONFLICT (campaign_name, track_name) DO NOTHING
                    """,
                    (campaign, track)
                )
                st.success(f"Mapped **{campaign}** → **{track}**")
                st.rerun()

    finally:
        db.close()
