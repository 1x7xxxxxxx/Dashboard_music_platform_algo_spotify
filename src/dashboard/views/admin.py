"""Vue Admin — Gestion des artistes SaaS + upload CSV.

Accessible uniquement au rôle 'admin'.
"""
import io
import streamlit as st
import pandas as pd

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import is_admin, get_artist_id


def _guard():
    """Bloque l'accès si non-admin."""
    if not is_admin():
        st.error("⛔ Accès réservé à l'administrateur.")
        st.stop()


# ─────────────────────────────────────────────
# CRUD helpers
# ─────────────────────────────────────────────

def _load_artists(db) -> pd.DataFrame:
    return db.fetch_df(
        "SELECT id, name, slug, tier, active, created_at FROM saas_artists ORDER BY id"
    )


def _create_artist(db, name: str, slug: str, tier: str):
    db.execute_query(
        "INSERT INTO saas_artists (name, slug, tier, active) VALUES (%s, %s, %s, TRUE)",
        (name.strip(), slug.strip().lower(), tier)
    )


def _update_artist(db, artist_id: int, name: str, tier: str):
    db.execute_query(
        "UPDATE saas_artists SET name = %s, tier = %s WHERE id = %s",
        (name.strip(), tier, artist_id)
    )


def _toggle_active(db, artist_id: int, active: bool):
    db.execute_query(
        "UPDATE saas_artists SET active = %s WHERE id = %s",
        (active, artist_id)
    )


# ─────────────────────────────────────────────
# CSV Upload helpers
# ─────────────────────────────────────────────

def _upload_s4a(db, artist_id: int, file):
    """Parse un CSV Spotify for Artists (timeline) et insère en DB."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
    from src.transformers.s4a_csv_parser import S4ACSVParser

    df = pd.read_csv(file)
    parser = S4ACSVParser()
    rows = parser.parse_timeline(df, artist_id=artist_id)
    if not rows:
        return 0
    db.upsert_many(
        table='s4a_song_timeline',
        data=rows,
        conflict_columns=['artist_id', 'song', 'date'],
        update_columns=['streams', 'collected_at']
    )
    return len(rows)


def _upload_apple(db, artist_id: int, file):
    """Parse un CSV Apple Music et insère en DB."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
    from src.transformers.apple_music_csv_parser import AppleMusicCSVParser

    df = pd.read_csv(file)
    parser = AppleMusicCSVParser()
    rows = parser.parse(df, artist_id=artist_id)
    if not rows:
        return 0
    db.upsert_many(
        table='apple_songs_performance',
        data=rows,
        conflict_columns=['artist_id', 'song_name'],
        update_columns=['plays', 'listeners', 'shazam_count']
    )
    return len(rows)


# ─────────────────────────────────────────────
# View
# ─────────────────────────────────────────────

def show():
    _guard()

    st.title("⚙️ Administration")
    st.markdown("---")

    tab_artists, tab_upload = st.tabs(["👥 Artistes", "📂 Upload CSV"])

    # ══════════════════════════════════════════
    # ONGLET 1 : GESTION DES ARTISTES
    # ══════════════════════════════════════════
    with tab_artists:
        db = get_db_connection()
        try:
            df_artists = _load_artists(db)
        except Exception as e:
            st.error(f"Erreur chargement artistes : {e}")
            db.close()
            return

        st.subheader("📋 Artistes enregistrés")

        if df_artists.empty:
            st.info("Aucun artiste en base.")
        else:
            # Tableau avec statut coloré
            def _status(active):
                return "✅ Actif" if active else "🔴 Inactif"

            df_display = df_artists.copy()
            df_display['Statut'] = df_display['active'].apply(_status)
            df_display['created_at'] = pd.to_datetime(df_display['created_at']).dt.strftime('%d/%m/%Y')
            st.dataframe(
                df_display[['id', 'name', 'slug', 'tier', 'Statut', 'created_at']].rename(columns={
                    'id': 'ID', 'name': 'Nom', 'slug': 'Slug',
                    'tier': 'Tier', 'created_at': 'Créé le'
                }),
                hide_index=True,
                use_container_width=True,
            )

        st.markdown("---")

        # ── Créer un artiste ──────────────────
        with st.expander("➕ Créer un nouvel artiste", expanded=False):
            with st.form("create_artist"):
                c1, c2, c3 = st.columns(3)
                new_name = c1.text_input("Nom *")
                new_slug = c2.text_input("Slug * (unique, minuscules)")
                new_tier = c3.selectbox("Tier", ["basic", "premium"])
                if st.form_submit_button("Créer", type="primary"):
                    if not new_name or not new_slug:
                        st.error("Nom et slug obligatoires.")
                    else:
                        try:
                            _create_artist(db, new_name, new_slug, new_tier)
                            st.success(f"✅ Artiste « {new_name} » créé.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur : {e}")

        # ── Modifier / activer-désactiver ─────
        if not df_artists.empty:
            with st.expander("✏️ Modifier un artiste", expanded=False):
                artist_options = {
                    f"{row['id']} — {row['name']}": row
                    for _, row in df_artists.iterrows()
                }
                sel_label = st.selectbox("Artiste", list(artist_options.keys()))
                sel = artist_options[sel_label]

                with st.form("edit_artist"):
                    c1, c2 = st.columns(2)
                    edit_name = c1.text_input("Nom", value=sel['name'])
                    edit_tier = c2.selectbox(
                        "Tier",
                        ["basic", "premium"],
                        index=0 if sel['tier'] == 'basic' else 1
                    )
                    edit_active = st.checkbox("Actif", value=bool(sel['active']))

                    if st.form_submit_button("Enregistrer", type="primary"):
                        try:
                            _update_artist(db, sel['id'], edit_name, edit_tier)
                            _toggle_active(db, sel['id'], edit_active)
                            st.success("✅ Artiste mis à jour.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur : {e}")

        db.close()

    # ══════════════════════════════════════════
    # ONGLET 2 : UPLOAD CSV
    # ══════════════════════════════════════════
    with tab_upload:
        st.subheader("📂 Importer un CSV pour un artiste")
        st.caption("Formats supportés : Spotify for Artists (timeline), Apple Music (performance)")

        db = get_db_connection()
        try:
            df_active = db.fetch_df(
                "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id"
            )
        except Exception as e:
            st.error(f"Erreur : {e}")
            db.close()
            return

        if df_active.empty:
            st.warning("Aucun artiste actif. Créez-en un dans l'onglet Artistes.")
            db.close()
            return

        c1, c2 = st.columns(2)
        with c1:
            artist_choices = {f"{r['id']} — {r['name']}": r['id'] for _, r in df_active.iterrows()}
            sel_artist_label = st.selectbox("Artiste cible", list(artist_choices.keys()))
            target_artist_id = artist_choices[sel_artist_label]

        with c2:
            platform = st.selectbox("Plateforme", ["Spotify for Artists (S4A)", "Apple Music"])

        uploaded = st.file_uploader(
            "Fichier CSV",
            type=["csv"],
            help="Glissez le CSV exporté depuis la plateforme."
        )

        if uploaded and st.button("⬆️ Importer", type="primary"):
            try:
                if platform.startswith("Spotify"):
                    n = _upload_s4a(db, target_artist_id, uploaded)
                else:
                    n = _upload_apple(db, target_artist_id, uploaded)
                st.success(f"✅ {n} ligne(s) importée(s) pour l'artiste #{target_artist_id}.")
            except Exception as e:
                st.error(f"❌ Erreur import : {e}")
                st.exception(e)

        db.close()
