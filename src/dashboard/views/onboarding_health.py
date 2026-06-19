"""Onboarding health — per-artist readiness matrix.

Type: Feature
Uses: get_db_connection, get_artist_id/is_admin, src.utils.artist_readiness
Triggers: nav "🚦 Santé onboarding"
Persists in: nothing (read-only view)

The visible end of the per-artist closed loop: for each artist × platform, did the artist
provide the IDENTITY and is data actually LANDING? Turns the silent per-tenant gaps the Benken
week exposed (connected-but-0-rows, account-not-shared, empty channel) into a status + the
exact next action. Admin sees every active artist; an artist sees their own row.
"""
import pandas as pd
import streamlit as st

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin
from src.utils.artist_readiness import artist_readiness, NO_DATA


def _matrix_df(matrix: list) -> pd.DataFrame:
    return pd.DataFrame([{
        "Plateforme": m["label"],
        "Statut": f"{m['icon']} {m['status_label']}",
        "Dernière donnée": str(m["last_dt"])[:16] if m["last_dt"] else "—",
        "Action": m["next_action"],
    } for m in matrix])


def show():
    st.title("🚦 Santé onboarding")
    st.caption(
        "Pour chaque artiste × plateforme : l'identité est-elle fournie, et les données "
        "arrivent-elles ? 🟢 OK · 🟡 anciennes · 🔴 connecté mais aucune donnée · ⚪ à connecter."
    )

    db = get_db_connection()
    if db is None:
        st.error("Base de données injoignable.")
        return
    try:
        if is_admin():
            df = db.fetch_df("SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id")
            artists = [(int(r["id"]), r["name"]) for _, r in df.iterrows()]
            if not artists:
                st.info("Aucun artiste actif.")
                return
        else:
            aid = get_artist_id()
            if aid is None:
                st.error("Session invalide.")
                return
            row = db.fetch_query("SELECT name FROM saas_artists WHERE id = %s", (aid,))
            artists = [(aid, row[0][0] if row else f"#{aid}")]

        total_red = 0
        for aid, name in artists:
            matrix = artist_readiness(db, aid)
            reds = [m for m in matrix if m["status"] == NO_DATA]
            total_red += len(reds)
            header = f"{name} (id={aid}) — " + " ".join(m["icon"] for m in matrix)
            with st.expander(header, expanded=bool(reds) or not is_admin()):
                st.dataframe(_matrix_df(matrix), hide_index=True, width="stretch")

        if is_admin():
            if total_red:
                st.warning(f"🔴 {total_red} plateforme(s) connectée(s) sans données — action requise.")
            else:
                st.success("✅ Aucun blocage 'connecté sans données' sur les artistes actifs.")
    finally:
        db.close()
