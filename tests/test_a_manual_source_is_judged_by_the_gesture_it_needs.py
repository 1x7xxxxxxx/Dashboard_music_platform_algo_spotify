"""Une source nourrie à la main ne se juge pas au temps qui passe.

Type: Test
Uses: psycopg2, a live Postgres
Depends on: src/utils/freshness_monitor.py
Persists in: nothing — tout est écrit dans une transaction ANNULÉE

Le défaut gardé, mesuré le 2026-09-14
--------------------------------------
L'alerte de fraîcheur du CSV Spotify for Artists a crié **85 nuits d'affilée**.
`csv_upload_log` ne porte que DEUX imports réussis pour le locataire 1 — le
2026-06-08 et le 2026-09-08, **92 jours d'écart** — contre un seuil de 7 jours.

Aucun seuil ne répare ça : à 7 jours elle crie 85 fois, à 90 jours elle ne dit plus
rien d'utile. Ce n'est pas le seuil qui est mauvais, c'est la QUESTION. « Est-ce
vieux ? » n'appelle aucun geste ; « une sortie est parue et tu n'as pas importé
depuis » en appelle un, une seule fois. Classe `an-alert-that-is-always-red`, et le
dépôt en connaissait déjà une instance — c'est pour elle que `silence_expected`
existe (Meta, aucune campagne active).

L'âge reste visible là où il sert : la page Spotify l'affiche titre par titre. Un
état se montre, il ne se crie pas toutes les nuits.
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _dsn() -> dict | None:
    """Les mots-clés de connexion — par la porte canonique, jamais recopiée.

    ⚠️ 2026-09-22 : ce bloc construisait son DSN à la main et ne lisait que
    l'environnement. Sur un poste dont le mot de passe vit dans
    `config/config.yaml`, la socket s'ouvre et l'authentification échoue — le
    module ne skippe pas, il ERREUR. Dix modules de test portaient exactement
    cette forme, trouvés par balayage après que trois d'entre eux ont rougi.
    `tests/db_gate.dsn()` passe par `src.utils.pg_connect.resolve_kwargs`, qui
    connaît les trois sources (`DATABASE_URL`, les `DATABASE_*`, `config.yaml`).

    Classe : `a-second-door-that-knows-fewer-sources-than-the-first`.
    """
    from tests.db_gate import dsn

    return dsn()


_CONN = _dsn()
pytestmark = [pytest.mark.xdist_group("a-manual-source-is-judged-by-the-gesture-it-needs"), pytest.mark.skipif(
    _CONN is None, reason=f"No Postgres on {_DB_HOST}:{_DB_PORT} — la sonde lit la base")]


class _Db:
    """Le minimum que `_s4a_silence` demande : `fetch_query`."""

    def __init__(self, cur):
        self._cur = cur

    def fetch_query(self, sql, params=None):
        self._cur.execute(sql, params)
        return self._cur.fetchall()


@pytest.fixture()
def seeded():
    """Un locataire jetable, une sortie, une mesure — transaction ANNULÉE."""
    psycopg2 = pytest.importorskip("psycopg2")
    sys.path.insert(0, str(ROOT))
    conn = psycopg2.connect(**_CONN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO saas_artists (name, slug, tier, active) "
                "VALUES ('Silence Rule', 'silence-rule-fixture', 'free', TRUE) RETURNING id")
            aid = cur.fetchone()[0]
            yield cur, aid
    finally:
        conn.rollback()
        conn.close()


def _probe(cur, aid):
    from src.utils.freshness_monitor import _s4a_silence
    return _s4a_silence(_Db(cur), aid)


def _seed(cur, aid, release, measured_to):
    cur.execute(
        "INSERT INTO track_release_reference (artist_id, match_key, title, release_date) "
        "VALUES (%s, 'fixture', 'Fixture', %s)", (aid, release))
    cur.execute(
        "INSERT INTO s4a_song_timeline (artist_id, song, date, streams) "
        "VALUES (%s, 'Fixture', %s, 1)", (aid, measured_to))


def test_no_release_since_the_import_is_a_legitimate_silence(seeded):
    """Le cas du locataire 1 : rien n'est sorti, l'import couvre tout."""
    cur, aid = seeded
    _seed(cur, aid, "2024-08-30", "2026-09-05")
    reason = _probe(cur, aid)
    assert reason is not None, (
        "l'alerte reste rouge alors qu'aucune sortie n'attend d'être mesurée — "
        "c'est l'état qui a produit 85 nuits d'affilée")
    assert "aucune sortie" in reason


def test_a_release_the_import_does_not_cover_keeps_the_alert(seeded):
    """Le seul moment où un CSV neuf apporte quelque chose d'indéductible."""
    cur, aid = seeded
    _seed(cur, aid, "2026-09-20", "2026-09-05")
    assert _probe(cur, aid) is None, (
        "une sortie parue après la dernière mesure n'a PAS réveillé l'alerte — "
        "c'est précisément le geste que l'artiste doit faire")


# --- non-vacuité : la sonde est conservatrice --------------------------------------

def test_an_unknown_state_keeps_the_alert(seeded):
    """Sans sortie connue ou sans mesure, on ne tait rien : un doute garde l'alerte."""
    cur, aid = seeded
    assert _probe(cur, aid) is None, "rien n'est connu et la sonde a pourtant tu l'alerte"
    cur.execute(
        "INSERT INTO track_release_reference (artist_id, match_key, title, release_date) "
        "VALUES (%s, 'fixture', 'Fixture', %s)", (aid, "2024-08-30"))
    assert _probe(cur, aid) is None, "une sortie sans aucune mesure doit garder l'alerte"


def test_a_failing_probe_keeps_the_alert():
    """Une sonde en échec ne tait jamais : elle retirerait le seul signal d'une panne."""
    from src.utils.freshness_monitor import _s4a_silence

    class _Broken:
        def fetch_query(self, sql, params=None):
            raise RuntimeError("base injoignable")

    assert _s4a_silence(_Broken(), 1) is None


def test_no_tenant_keeps_the_alert():
    from src.utils.freshness_monitor import _s4a_silence
    assert _s4a_silence(None, None) is None


def test_the_two_cases_really_differ(seeded):
    """Sans ça, un `return None` partout passerait la moitié des tests ci-dessus."""
    cur, aid = seeded
    _seed(cur, aid, "2024-08-30", "2026-09-05")
    silent = _probe(cur, aid)
    cur.execute("UPDATE track_release_reference SET release_date = %s WHERE artist_id = %s",
                ("2026-09-20", aid))
    loud = _probe(cur, aid)
    assert silent is not None and loud is None, (
        f"la sonde rend le même verdict dans les deux cas : {silent!r} / {loud!r}")
