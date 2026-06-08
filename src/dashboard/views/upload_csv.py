"""Vue Upload CSV — Brick 5.

Accessible à tous les utilisateurs authentifiés.
- Artiste : importe des CSV pour son propre artist_id.
- Admin    : sélectionne l'artiste cible.

Flux : Upload (multi-fichier) → Détection auto du type → Aperçu → Confirmer tout.
"""
import sys
from pathlib import Path
import streamlit as st
import pandas as pd

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin

_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)


# ─────────────────────────────────────────────
# Platform registry  (key → DB config)
# ─────────────────────────────────────────────

_PLATFORMS = {
    's4a': {
        'label': 'S4A — Timeline par titre',
        'table': 's4a_song_timeline',
        'conflict_columns': ['artist_id', 'song', 'date'],
        'update_columns': ['streams', 'collected_at'],
    },
    's4a_songs_global': {
        'label': 'S4A — Résumé titres',
        'table': 's4a_songs_global',
        'conflict_columns': ['artist_id', 'song', 'time_window'],
        'update_columns': ['listeners', 'streams', 'saves', 'release_date', 'collected_at'],
    },
    's4a_audience': {
        'label': 'S4A — Audience',
        'table': 's4a_audience',
        'conflict_columns': ['artist_id', 'date'],
        'update_columns': ['listeners', 'streams', 'followers', 'playlist_adds', 'saves', 'collected_at'],
    },
    'apple': {
        'label': 'Apple Music',
        'table': 'apple_songs_performance',
        'conflict_columns': ['artist_id', 'song_name'],
        'update_columns': ['plays', 'listeners', 'shazam_count', 'collected_at'],
    },
    'imusician_summary': {
        'label': 'iMusician — Résumé par sortie',
        'table': 'imusician_release_summary',
        'conflict_columns': ['artist_id', 'barcode', 'year', 'month'],
        'update_columns': [
            'release_title', 'track_downloads', 'track_streams', 'release_downloads',
            'track_downloads_revenue', 'track_streams_revenue',
            'release_downloads_revenue', 'total_revenue', 'collected_at',
        ],
    },
    'imusician_sales': {
        'label': 'iMusician — Rapport de vente',
        'table': 'imusician_sales_detail',
        'conflict_columns': [
            'artist_id', 'isrc', 'sales_year', 'sales_month',
            'statement_year', 'statement_month', 'shop', 'country', 'transaction_type',
        ],
        'update_columns': ['quantity', 'revenue_eur', 'collected_at'],
    },
}


# ─────────────────────────────────────────────
# Auto-detection
# ─────────────────────────────────────────────

def _detect_platform(filename: str, columns: list[str]) -> str | None:
    """Return a platform key from filename + column headers, or None if unknown.

    Detection is ordered from most specific to least specific to avoid false positives.
    """
    name = filename.lower()
    cols = {c.lower().strip() for c in columns}

    # iMusician — sales (ISRC + shop is highly specific)
    if 'isrc' in cols and 'shop' in cols:
        return 'imusician_sales'

    # iMusician — summary
    if 'release title' in cols and 'track streams' in cols:
        return 'imusician_summary'

    # Apple Music
    if any(c in cols for c in ['morceau', 'song title']) and \
       any(c in cols for c in ['écoutes', 'plays', 'play count', 'lectures']):
        return 'apple'

    # S4A audience (filename signal takes priority over column overlap with timeline)
    if 'audience' in name and 'date' in cols and 'listeners' in cols:
        return 's4a_audience'

    # S4A songs-all (has release_date + saves at column level, or filename signal)
    if ('songs-all' in name or 'songs_all' in name) and 'song' in cols:
        return 's4a_songs_global'
    if 'song' in cols and 'release_date' in cols and 'saves' in cols:
        return 's4a_songs_global'

    # S4A per-song timeline (filename has -timeline, columns are just date + streams)
    if ('timeline' in name or 'timeline' in name) and 'date' in cols and \
       any(c in cols for c in ['streams', 'ecoutes', 'écoutes']) and \
       'audience' not in name and 'song' not in cols:
        return 's4a'

    return None


# ─────────────────────────────────────────────
# Parsing dispatch
# ─────────────────────────────────────────────

def _parse_file(platform_key: str, file, artist_id: int) -> list:
    """Parse an uploaded file for the given platform key. Returns a list of row dicts."""
    filename = getattr(file, 'name', '')
    df = pd.read_csv(file)

    if platform_key == 's4a':
        from src.transformers.s4a_csv_parser import S4ACSVParser
        return S4ACSVParser().parse_timeline(df, artist_id=artist_id, filename=filename)

    if platform_key == 's4a_songs_global':
        from src.transformers.s4a_csv_parser import S4ACSVParser
        return S4ACSVParser().parse_songs_global(df, artist_id=artist_id, filename=filename)

    if platform_key == 's4a_audience':
        from src.transformers.s4a_csv_parser import S4ACSVParser
        return S4ACSVParser().parse_audience(df, artist_id=artist_id)

    if platform_key == 'apple':
        # _detect_platform only routes songs-performance CSVs here (morceau/song + plays);
        # parse_songs_performance does not inject artist_id, so add it per row.
        from src.transformers.apple_music_csv_parser import AppleMusicCSVParser
        rows = AppleMusicCSVParser().parse_songs_performance(df)
        for row in rows:
            row['artist_id'] = artist_id
        return rows

    if platform_key == 'imusician_summary':
        from src.transformers.imusician_csv_parser import IMusicianCSVParser
        return IMusicianCSVParser().parse_release_summary(df, artist_id=artist_id)

    if platform_key == 'imusician_sales':
        from src.transformers.imusician_csv_parser import IMusicianCSVParser
        return IMusicianCSVParser().parse_sales_detail(df, artist_id=artist_id)

    raise ValueError(f"Plateforme inconnue : {platform_key}")


# ─────────────────────────────────────────────
# View
# ─────────────────────────────────────────────

def show():
    st.title("📂 Import CSV")
    st.caption(
        "Déposez jusqu'à une dizaine de fichiers CSV en une fois. "
        "Le type est détecté automatiquement depuis le nom de fichier et les colonnes."
    )

    from src.dashboard.content.csv_guides_st import render_csv_guides
    render_csv_guides()

    st.info(
        "🔗 **Mapping Spotify × Meta Ads** — après avoir **lancé la collecte "
        "depuis la page d'accueil**, pensez à faire le mapping "
        "(menu **📣 Publicité Meta Ads → Mapping Spotify × Meta Ads (nom de campagne)**) "
        "pour relier vos campagnes Meta à vos titres Spotify."
    )

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

        # ── Upload multi-fichier ───────────────────────────────────────
        uploaded_files = st.file_uploader(
            "Fichiers CSV",
            type=["csv"],
            accept_multiple_files=True,
            help="Glissez tous vos fichiers CSV en même temps. "
                 "Le type (S4A timeline, audience, songs-all, Apple, iMusician…) "
                 "est détecté automatiquement.",
            key=f"multi_upload_{target_artist_id}",
        )

        if not uploaded_files:
            return

        # ── Détection + parsing de tous les fichiers ───────────────────
        st.markdown("---")
        st.subheader(f"🔍 Détection — {len(uploaded_files)} fichier(s)")

        file_results = []  # list of dicts: filename, platform_key, label, rows, error

        for f in uploaded_files:
            entry = {'filename': f.name, 'platform_key': None, 'label': '—',
                     'rows': [], 'error': None}
            try:
                f.seek(0)
                df_head = pd.read_csv(f, nrows=0)
                platform_key = _detect_platform(f.name, df_head.columns.tolist())

                if platform_key is None:
                    entry['error'] = 'Type non reconnu — vérifiez le nom et les colonnes du fichier.'
                else:
                    entry['platform_key'] = platform_key
                    entry['label'] = _PLATFORMS[platform_key]['label']
                    f.seek(0)
                    entry['rows'] = _parse_file(platform_key, f, target_artist_id)
                    if not entry['rows']:
                        entry['error'] = 'Aucune ligne valide détectée après parsing.'

            except Exception as exc:
                entry['error'] = str(exc)

            file_results.append(entry)

        # ── Tableau de détection ───────────────────────────────────────
        summary_rows = []
        for r in file_results:
            if r['error']:
                status = f"❌ {r['error']}"
                count = '—'
            else:
                status = '✅ Prêt'
                count = len(r['rows'])
            summary_rows.append({
                'Fichier': r['filename'],
                'Type détecté': r['label'],
                'Lignes': count,
                'Statut': status,
            })

        st.dataframe(pd.DataFrame(summary_rows), hide_index=True, width='stretch')

        # ── Aperçus (collapse par défaut) ──────────────────────────────
        ok_results = [r for r in file_results if not r['error']]
        if not ok_results:
            st.error("Aucun fichier valide à importer.")
            return

        for r in ok_results:
            with st.expander(f"Aperçu — {r['filename']} ({len(r['rows'])} lignes)", expanded=False):
                st.dataframe(pd.DataFrame(r['rows']).head(10), hide_index=True, width='stretch')

        # ── Confirmation ───────────────────────────────────────────────
        st.markdown("---")
        n_ok = len(ok_results)
        n_skip = len(file_results) - n_ok
        label = f"✅ Importer {n_ok} fichier(s)"
        if n_skip:
            label += f"  (⚠️ {n_skip} ignoré(s))"

        if st.button(label, type="primary"):
            result_rows = []
            total_ok = 0
            total_err = 0

            for r in ok_results:
                cfg = _PLATFORMS[r['platform_key']]
                try:
                    count = db.upsert_many(
                        table=cfg['table'],
                        data=r['rows'],
                        conflict_columns=cfg['conflict_columns'],
                        update_columns=cfg['update_columns'],
                    )
                    total_ok += count
                    result_rows.append({
                        'Fichier': r['filename'],
                        'Type': r['label'],
                        'Table': cfg['table'],
                        'Lignes traitées': count,
                        'Statut': '✅ OK',
                    })
                    db.execute_query(
                        "INSERT INTO csv_upload_log "
                        "(artist_id, filename, platform, row_count, status) "
                        "VALUES (%s, %s, %s, %s, 'success')",
                        (target_artist_id, r['filename'], r['platform_key'], count),
                    )
                except Exception as exc:
                    total_err += 1
                    result_rows.append({
                        'Fichier': r['filename'],
                        'Type': r['label'],
                        'Table': cfg['table'],
                        'Lignes traitées': 0,
                        'Statut': f'❌ {exc}',
                    })
                    try:
                        db.execute_query(
                            "INSERT INTO csv_upload_log "
                            "(artist_id, filename, platform, row_count, status, error_message) "
                            "VALUES (%s, %s, %s, 0, 'error', %s)",
                            (target_artist_id, r['filename'], r['platform_key'], str(exc)[:500]),
                        )
                    except Exception:
                        pass  # audit log failure must never block the UI

            # If S4A global summary was imported, rebuild the canonical
            # release-date reference (authoritative source for "latest release"
            # across all platforms). Non-blocking — never fails the import.
            if any(r['platform_key'] == 's4a_songs_global' for r in ok_results):
                try:
                    from src.utils.track_matching import rebuild_release_reference
                    n_ref = rebuild_release_reference(db, target_artist_id)
                    if n_ref:
                        st.caption(f"🎵 Référentiel de sorties mis à jour ({n_ref} titres).")
                except Exception as exc:  # noqa: BLE001 — reference is best-effort
                    st.caption(f"⚠️ Référentiel de sorties non mis à jour : {exc}")

            # If an iMusician sales report was imported, roll its per-line detail up
            # into monthly_revenue so the Distributeur view + ROI surface it. Manual
            # entries are preserved. Non-blocking — never fails the import.
            if any(r['platform_key'] == 'imusician_sales' for r in ok_results):
                try:
                    from src.utils.imusician_rollup import rollup_sales_to_monthly
                    n_months = rollup_sales_to_monthly(db, target_artist_id)
                    if n_months:
                        st.caption(f"💰 Revenus mensuels agrégés ({n_months} mois) — visibles dans Distributeur.")
                except Exception as exc:  # noqa: BLE001 — roll-up is best-effort
                    st.caption(f"⚠️ Agrégation des revenus mensuels non effectuée : {exc}")

            st.markdown("---")
            st.subheader("📋 Résultats de l'import")

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Fichiers traités", len(ok_results))
            k2.metric("Lignes insérées / mises à jour", f"{total_ok:,}")
            k3.metric("Fichiers en erreur", total_err,
                      delta=None if total_err == 0 else "⚠️", delta_color="inverse")
            k4.metric("Fichiers ignorés (type inconnu)", n_skip)

            st.dataframe(pd.DataFrame(result_rows), hide_index=True, width='stretch')

    finally:
        db.close()
