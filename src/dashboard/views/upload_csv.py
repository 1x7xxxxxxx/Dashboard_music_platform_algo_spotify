"""Vue Upload CSV — Brick 5.

Accessible à tous les utilisateurs authentifiés.
- Artiste : importe des CSV pour son propre artist_id.
- Admin    : sélectionne l'artiste cible.

Flux : Upload → Preview (10 premières lignes parsées) → Confirmer → Insert DB.
"""
import sys
from pathlib import Path
import streamlit as st
import pandas as pd

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin

# Garantit que la racine est dans sys.path pour les parsers
_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)


# ─────────────────────────────────────────────
# Parsers
# ─────────────────────────────────────────────

PLATFORMS = {
    'S4A — Spotify for Artists (timeline)': {
        'key': 's4a',
        'table': 's4a_song_timeline',
        'conflict_columns': ['artist_id', 'song', 'date'],
        'update_columns': ['streams', 'collected_at'],
        # Each inner list = at least one match required (case-insensitive).
        'required_columns': [
            (['date'], "Date"),
            (['streams', 'ecoutes', 'écoutes'], "Streams / Écoutes"),
        ],
    },
    'Apple Music (performance)': {
        'key': 'apple',
        'table': 'apple_songs_performance',
        'conflict_columns': ['artist_id', 'song_name'],
        'update_columns': ['plays', 'listeners', 'shazam_count'],
        'required_columns': [
            (['morceau', 'song', 'song title', 'title', 'track', 'titre'], "Song / Morceau"),
            (['écoutes', 'plays', 'play count', 'lectures'], "Plays / Écoutes"),
        ],
    },
}


def _validate_columns(df: pd.DataFrame, required_groups: list) -> list[dict]:
    """
    Check that each required column group has at least one match in df.columns.

    Returns a list of dicts: {label, matched, found_col}.
    """
    cols_lower = [c.lower().strip() for c in df.columns]
    results = []
    for candidates, label in required_groups:
        found = next((c for c in candidates if c in cols_lower), None)
        results.append({'label': label, 'matched': found is not None, 'found': found})
    return results


def _parse_csv(platform_key: str, file, artist_id: int) -> list:
    """Parse le fichier CSV selon la plateforme, retourne une liste de dicts."""
    df = pd.read_csv(file)

    if platform_key == 's4a':
        from src.transformers.s4a_csv_parser import S4ACSVParser
        return S4ACSVParser().parse_timeline(df, artist_id=artist_id)

    if platform_key == 'apple':
        from src.transformers.apple_music_csv_parser import AppleMusicCSVParser
        return AppleMusicCSVParser().parse(df, artist_id=artist_id)

    raise ValueError(f"Plateforme inconnue : {platform_key}")


# ─────────────────────────────────────────────
# View
# ─────────────────────────────────────────────

def show():
    st.title("📂 Import CSV")
    st.caption("Importez un fichier CSV exporté depuis une plateforme. "
               "Un aperçu est affiché avant l'insertion en base.")

    db = get_db_connection()
    try:
        # ── Sélection artiste ──────────────────────────────────────────
        if is_admin():
            df_artists = db.fetch_df(
                "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id"
            )
            if df_artists.empty:
                st.warning("Aucun artiste actif. Créez-en un dans l'onglet Admin.")
                return
            choices = {f"{r['id']} — {r['name']}": r['id'] for _, r in df_artists.iterrows()}
            sel_label = st.selectbox("Artiste cible", list(choices.keys()))
            target_artist_id = choices[sel_label]
        else:
            target_artist_id = get_artist_id()
            if target_artist_id is None:
                st.error("Impossible de déterminer votre identifiant artiste.")
                return

        # ── Sélection plateforme + upload ─────────────────────────────
        c1, c2 = st.columns([1, 2])
        with c1:
            platform_label = st.selectbox("Plateforme", list(PLATFORMS.keys()))
        platform_cfg = PLATFORMS[platform_label]

        with c2:
            uploaded = st.file_uploader(
                "Fichier CSV",
                type=["csv"],
                help="Glissez le CSV exporté depuis la plateforme.",
                key=f"upload_{platform_cfg['key']}_{target_artist_id}",
            )

        # ── Validation + Preview ─────────────────────────────────────
        if uploaded:
            # Step 1: read raw header for column validation
            uploaded.seek(0)
            try:
                df_raw = pd.read_csv(uploaded, nrows=0)  # header only
            except Exception as e:
                st.error(f"❌ Impossible de lire le fichier CSV : {e}")
                return

            st.markdown("---")
            st.subheader("🔍 Validation")

            # Column check
            checks = _validate_columns(df_raw, platform_cfg['required_columns'])
            all_ok = all(c['matched'] for c in checks)

            col_v1, col_v2, col_v3 = st.columns(3)
            col_v1.metric("Artiste cible", f"#{target_artist_id}")
            col_v2.metric("Colonnes brutes détectées", len(df_raw.columns))
            col_v3.metric("Validation colonnes", "✅ OK" if all_ok else "❌ Échec")

            for check in checks:
                icon = "✅" if check['matched'] else "❌"
                detail = f"→ `{check['found']}`" if check['matched'] else "non trouvée"
                st.markdown(f"{icon} **{check['label']}** {detail}")

            if not all_ok:
                missing = [c['label'] for c in checks if not c['matched']]
                st.error(
                    f"Colonnes requises manquantes : {', '.join(missing)}. "
                    "Vérifiez que le bon fichier est sélectionné pour cette plateforme."
                )
                return

            # Step 2: parse
            uploaded.seek(0)
            try:
                rows = _parse_csv(platform_cfg['key'], uploaded, target_artist_id)
            except Exception as e:
                st.error(f"❌ Erreur de parsing : {e}")
                st.exception(e)
                return

            if not rows:
                st.warning("Aucune ligne valide détectée dans ce fichier.")
                return

            # Step 3: preview
            df_preview = pd.DataFrame(rows)
            st.markdown("---")
            st.subheader(f"Aperçu — {len(rows)} ligne(s) à importer")
            st.dataframe(
                df_preview.head(10),
                use_container_width=True,
                hide_index=True,
            )
            if len(rows) > 10:
                st.caption(f"… et {len(rows) - 10} ligne(s) supplémentaire(s) non affichées.")

            # Step 4: confirm
            st.markdown("---")
            if st.button("✅ Confirmer l'import", type="primary"):
                try:
                    db.upsert_many(
                        table=platform_cfg['table'],
                        data=rows,
                        conflict_columns=platform_cfg['conflict_columns'],
                        update_columns=platform_cfg['update_columns'],
                    )
                    st.success(
                        f"✅ {len(rows)} ligne(s) importée(s) dans `{platform_cfg['table']}` "
                        f"pour l'artiste #{target_artist_id}."
                    )
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'insertion : {e}")
                    st.exception(e)

    finally:
        db.close()
