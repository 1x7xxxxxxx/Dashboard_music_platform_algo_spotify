"""Guard: une valeur écrasée laisse une trace, et l'historique s'accumule.

Type: Test
Uses: live Postgres (spotify_etl), migration 096
Depends on: data_revisions, log_value_revision(), trg_revision_s4a_song_timeline
Persists in: rien (les lignes de sonde sont retirées)

Demandé le 2026-09-08 : « une solution automatique qui conserve les données historiques
si elles doivent être écrasées ».

Le risque est documenté par la SOURCE : Spotify retire des streams rétroactivement quand
sa détection de fraude conclut (page « Artificial Streaming »). Notre upsert écrase
`(artist_id, song, date)`, donc un jour déjà collecté peut changer de valeur sans que
rien ne le voie.

Ce fichier prouve l'EFFET du déclencheur, jamais son existence. Un `CREATE TRIGGER`
réussit toujours ; ce qui compte est ce qu'il écrit — et la première version de la
migration 096 n'écrivait RIEN, alors qu'elle s'appliquait sans erreur : `TG_ARGV` est
indexé à partir de 0 en PL/pgSQL, la boucle parcourait le séparateur au lieu de la
colonne surveillée. Sans cette sonde, un journal qui ne garde rien partait en production.
"""
from __future__ import annotations

import os
import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433
# Un identifiant HORS de toute plage réelle, et que ce fichier crée lui-même.
# 471 était utilisé avant : il existait dans la base de développement, posé à la main,
# et nulle part ailleurs — d'où un test vert en local et rouge en CI.
_PROBE_ARTIST = 999_471
_PROBE_SONG = "__probe_revision__"


def _db_ready() -> bool:
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
                pass
        except OSError:
            return False
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        if db is None:
            return False
        try:
            db.fetch_query("SELECT 1 FROM data_revisions LIMIT 1")
            return True
        finally:
            db.close()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason=f"No provisioned Postgres on {_DB_HOST}:{_DB_PORT} (or migration 096 absent)")


@pytest.fixture()
def db():
    """Le locataire technique est CRÉÉ ici, pas supposé.

    `s4a_song_timeline.artist_id` porte une clé étrangère vers `saas_artists` : sans
    la ligne parente, l'insertion est refusée. Le test passait pourtant en local et
    échouait en CI — parce que le locataire 471 existait dans MA base, posé à la main
    un jour, et nulle part ailleurs. Un test qui s'appuie sur l'état local d'une base
    ne prouve rien : il prouve que cette base-là a cet état.
    """
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    conn.execute_query(
        "INSERT INTO saas_artists (id, name, slug, tier, active) "
        "VALUES (%s, %s, %s, 'free', false) ON CONFLICT (id) DO NOTHING",
        (_PROBE_ARTIST, "probe — nothing_overwritten_is_lost",
         f"probe-nothing-overwritten-{_PROBE_ARTIST}"))
    _clean(conn)
    try:
        yield conn
    finally:
        _clean(conn)
        conn.close()


def _clean(conn) -> None:
    conn.execute_query("DELETE FROM data_revisions WHERE artist_id = %s", (_PROBE_ARTIST,))
    conn.execute_query("DELETE FROM s4a_song_timeline WHERE artist_id = %s AND song = %s",
                       (_PROBE_ARTIST, _PROBE_SONG))


def _write(conn, streams: int) -> None:
    conn.execute_query(
        "INSERT INTO s4a_song_timeline (artist_id, song, date, streams) "
        "VALUES (%s, %s, DATE '2026-01-01', %s) "
        "ON CONFLICT (artist_id, song, date) DO UPDATE SET streams = EXCLUDED.streams",
        (_PROBE_ARTIST, _PROBE_SONG, streams))


def _revisions(conn):
    return conn.fetch_query(
        "SELECT column_name, old_value, new_value FROM data_revisions "
        "WHERE artist_id = %s ORDER BY id", (_PROBE_ARTIST,)) or []


def test_a_first_write_is_not_a_revision(db) -> None:
    """Écrire pour la première fois n'écrase rien — le journal doit rester vide."""
    _write(db, 100)
    assert _revisions(db) == [], "une insertion a été journalisée comme une révision"


def test_rewriting_the_same_value_leaves_no_trace(db) -> None:
    """La collecte réécrit les mêmes chiffres chaque nuit : le journal ne doit pas gonfler.

    Sans `IS DISTINCT FROM`, ce serait une ligne par titre et par nuit, pour ne rien dire
    — un journal qu'on cesserait de lire au bout d'une semaine.
    """
    _write(db, 100)
    _write(db, 100)
    assert _revisions(db) == [], "une réécriture identique a été journalisée"


def test_an_overwritten_value_is_kept(db) -> None:
    """Le cas de Spotify : un jour déjà collecté change de valeur."""
    _write(db, 100)
    _write(db, 87)
    rows = _revisions(db)
    assert len(rows) == 1, f"{len(rows)} ligne(s) journalisée(s) au lieu d'une : {rows}"
    col, old, new = rows[0]
    assert (col, old, new) == ("streams", "100", "87"), rows[0]


def test_the_history_accumulates(db) -> None:
    """TOUT est conservé, pas seulement la valeur précédente.

    C'est la différence entre une colonne `previous_streams` — qui ne garderait que
    l'avant-dernière — et un journal.
    """
    for value in (100, 87, 90, 91):
        _write(db, value)
    chain = [(o, n) for _c, o, n in _revisions(db)]
    assert chain == [("100", "87"), ("87", "90"), ("90", "91")], chain


def test_the_revision_carries_the_key_to_find_the_row_again(db) -> None:
    """Une trace sans sa clé métier ne se rattache à rien."""
    _write(db, 100)
    _write(db, 87)
    row = db.fetch_query(
        "SELECT table_name, row_key FROM data_revisions WHERE artist_id = %s",
        (_PROBE_ARTIST,))[0]
    assert row[0] == "s4a_song_timeline"
    key = row[1] if isinstance(row[1], dict) else __import__("json").loads(row[1])
    assert set(key) == {"artist_id", "song", "date"}, key
    assert key["song"] == _PROBE_SONG
