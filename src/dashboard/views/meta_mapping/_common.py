"""Shared helpers for the meta_mapping package (track + campaign sub-views).

Type: Sub
Uses: streamlit (data_editor callback), PostgresHandler
Depends on: track_release_reference
"""
import streamlit as st

# S4A "Total" summary row is filtered out of every s4a_song_timeline query
# (project convention — see CLAUDE.md ARTIST_NAME_FILTER).
_S4A_FILTER = "%1x7xxxxxxx%"


def _load_canonical(db, artist_id):
    # Latest release first (project convention: most-recent release at the top of
    # selectors/grids). title as the stable tie-breaker.
    rows = db.fetch_query(
        "SELECT match_key, title, release_date FROM track_release_reference "
        "WHERE artist_id = %s ORDER BY release_date DESC NULLS LAST, title",
        (artist_id,))
    return [{'match_key': r[0], 'title': r[1], 'release_date': r[2]} for r in (rows or [])]


def _artist_noise(db, artist_id: int):
    """Les jetons du nom d'artiste, à ignorer dans la comparaison de titres.

    SoundCloud et YouTube préfixent le nom de l'artiste au titre
    (« 1x7xxxxxxx - Kimono À Semelle De Fer »). Sans cette liste, ce nom compte
    comme un mot du titre et fait chuter la couverture : mesuré le 2026-09-06, le
    rapprochement tombait de 1,00 à 0,75, sous le seuil d'auto-acceptation.

    Ne lève jamais : une comparaison sans le nom d'artiste est moins bonne, pas
    cassée, et une page qui meurt vaut moins qu'un score un peu bas.
    """
    from src.utils.track_mapping_suggest import artist_noise_tokens
    try:
        rows = db.fetch_query(
            "SELECT name FROM saas_artists WHERE id = %s", (artist_id,))
    except Exception:  # noqa: BLE001
        return frozenset()
    return artist_noise_tokens(rows[0][0] if rows and rows[0] else '')


def _mutex_checkboxes(editor_key: str, col_a: str, col_b: str):
    """data_editor on_change callback: make two boolean columns mutually exclusive —
    ticking one unticks the other (by injecting the counter-change into the editor's
    pending edits before the rerun re-renders the grid)."""
    state = st.session_state.get(editor_key)
    if not state:
        return
    for ch in state.get("edited_rows", {}).values():
        if ch.get(col_a):
            ch[col_b] = False
        elif ch.get(col_b):
            ch[col_a] = False
