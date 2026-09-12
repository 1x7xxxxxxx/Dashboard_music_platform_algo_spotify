"""Un locataire jamais mesuré n'a pas « zéro » — il n'a pas de mesure.

Type: Test
Uses: psycopg2, a live Postgres
Depends on: les vues or, src/dashboard/utils/platform_timeseries.py
Persists in: nothing

Why this exists
---------------
Mesuré le 2026-09-12, sur un locataire sans aucune donnée :

    platform_totals(db, 999999)
      → {'spotify': 0, 'youtube': 0, 'soundcloud': 0, 'apple': 0}

Quatre zéros AFFIRMÉS, pendant que les vues or rendaient correctement « aucune
ligne ». ADR-022 dit pourtant, mot pour mot, que le travail de la porte est de
rendre `None` quand rien n'a été mesuré. Elle ne le faisait que sur sa branche
bornée ; la branche « depuis le début » portait un `COALESCE(total, 0)` dans son
SQL et un `or 0` dans son Python, et `gold_apple_lifetime` un `COALESCE` de plus.

Ce que l'artiste lisait : « 0 écoute » le jour de son inscription. Ça ne se lit pas
comme « la collecte n'a pas encore tourné », ça se lit comme un produit qui ne
marche pas — la classe `absence-rendered-as-a-measurement`, sur une surface qu'elle
n'avait pas encore atteinte.

Pourquoi ce test balaie les HUIT plateformes
---------------------------------------------
Parce que la question se repose pour chacune, et qu'une réponse pour Spotify ne dit
rien d'Instagram. Le tableau `plateforme × famille` de
`.claude/dev-docs/gold-coverage.md` comptait huit cases vides sur cette famille : ce
fichier est ce qui les remplit.

Le locataire fantôme et la transaction annulée
-----------------------------------------------
On n'invente pas de données : on interroge un identifiant qui n'existe pas. Rien
n'est écrit, rien n'est à nettoyer, et le test ne dépend d'aucun jeu de données
particulier — il marche sur une base vide comme sur la production.

Mutation record — 2026-09-12 : avec `COALESCE(total, 0)` remis dans `_SQL_LIFETIME`,
ce test nomme les trois plateformes de `platform_totals` ; avec le `COALESCE` remis
dans `gold_apple_lifetime` (migration 113), il nomme Apple. Vu rouge sur les deux
moitiés du défaut.
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_DB_HOST, _DB_PORT = "127.0.0.1", 5433

# Un identifiant qu'aucune table ne porte. Choisi hors de toute séquence : les
# `saas_artists.id` sont des SERIAL à trois chiffres, et un test qui prendrait
# `max(id) + 1` se mettrait à interroger un vrai locataire le jour d'une inscription.
_GHOST = 999_999

# (plateforme, la relation or qui la définit, la colonne qu'on somme)
#
# La relation est NOMMÉE ici — et pas seulement la plateforme — parce que le tableau
# `plateforme × famille` compte les gardes qui lisent une relation dans un littéral
# SQL. Un garde qui prononce « Instagram » sans lire `v_instagram_media_monthly` ne
# garde rien, et ce dépôt a pris quatre gardes au vert sur leur propre commentaire.
_GOLD_BY_PLATFORM = (
    ("Spotify S4A", "SELECT SUM(streams) FROM v_s4a_song_daily WHERE artist_id = %s"),
    ("YouTube", "SELECT SUM(total) FROM v_platform_totals "
                "WHERE platform = 'youtube' AND artist_id = %s"),
    ("SoundCloud", "SELECT SUM(playback_count) FROM v_soundcloud_track_latest "
                   "WHERE artist_id = %s"),
    ("Apple Music", "SELECT SUM(total) FROM v_platform_totals "
                    "WHERE platform = 'apple' AND artist_id = %s"),
    ("Instagram", "SELECT SUM(likes) FROM v_instagram_media_monthly WHERE artist_id = %s"),
    ("Meta Ads", "SELECT SUM(spend) FROM v_meta_daily WHERE artist_id = %s"),
    ("Hypeddit", "SELECT SUM(visits) FROM v_hypeddit_daily WHERE artist_id = %s"),
    ("Revenu", "SELECT SUM(revenue_eur) FROM v_artist_monthly_revenue WHERE artist_id = %s"),
)


def _dsn() -> dict | None:
    if os.environ.get("DATABASE_URL"):
        return {"dsn": os.environ["DATABASE_URL"]}
    try:
        with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
            pass
    except OSError:
        return None
    return {
        "host": _DB_HOST,
        "port": _DB_PORT,
        "dbname": os.environ.get("DATABASE_NAME", "spotify_etl"),
        "user": os.environ.get("DATABASE_USER", "postgres"),
        "password": os.environ.get("DATABASE_PASSWORD") or os.environ.get("DB_PASSWORD", ""),
    }


_CONN = _dsn()

pytestmark = pytest.mark.skipif(
    _CONN is None,
    reason=f"No Postgres on {_DB_HOST}:{_DB_PORT} — l'absence ne se lit que dans la base",
)


@pytest.fixture(scope="module")
def cursor():
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**_CONN)
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.parametrize("platform,sql", _GOLD_BY_PLATFORM,
                         ids=[p for p, _ in _GOLD_BY_PLATFORM])
def test_a_gold_view_renders_no_row_rather_than_a_zero(cursor, platform, sql) -> None:
    """La vue or ne fabrique pas de ligne pour un locataire qu'elle n'a pas vu."""
    cursor.execute(sql, (_GHOST,))
    row = cursor.fetchone()
    value = row[0] if row else None
    assert value is None, (
        f"{platform} : la couche or rend {value} pour un locataire qui n'a AUCUNE "
        "donnée. Un zéro affirmé se lit comme une mesure — « ce compte n'a rien "
        "fait » — quand la vérité est « on n'a rien mesuré ». Les deux méritent deux "
        "affichages différents, et la vue est l'endroit où la distinction se perd "
        "en premier.")


def test_the_python_door_says_none_for_every_platform_it_serves() -> None:
    """La PORTE, et c'est elle qui avait le défaut.

    ADR-022 : « elle rend `None` quand rien n'a été mesuré (jamais `0`) ». Ce test
    est la phrase exécutable de cette ADR.
    """
    sys.path.insert(0, str(_ROOT))
    import psycopg2  # noqa: F401 — l'import prouve la dépendance avant de connecter
    from src.dashboard.utils.platform_timeseries import platform_totals
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler(
        host=_DB_HOST, port=_DB_PORT,
        database=os.environ.get("DATABASE_NAME", "spotify_etl"),
        user=os.environ.get("DATABASE_USER", "postgres"),
        password=os.environ.get("DATABASE_PASSWORD") or os.environ.get("DB_PASSWORD", ""),
    )
    try:
        totals = platform_totals(db, _GHOST)
    finally:
        db.close()

    affirmed = {k: v for k, v in (totals or {}).items() if v == 0}
    assert not affirmed, (
        f"`platform_totals` affirme un zéro pour {sorted(affirmed)} sur un locataire "
        "jamais mesuré. Mesuré le 2026-09-12, la porte rendait les QUATRE à zéro "
        "pendant que les vues rendaient correctement « aucune ligne » — le "
        "`COALESCE(total, 0)` était dans la porte, pas dans la couche or.")
    assert set(totals) >= {"spotify", "youtube", "soundcloud", "apple"}, (
        f"la porte ne sert plus les quatre plateformes : {sorted(totals)}. Un test "
        "vert sur trois clés ne dit rien de la quatrième.")


def test_a_measured_zero_is_still_a_zero(cursor) -> None:
    """Non-vacuité, et la moitié qu'on oublie : on ne demande pas d'EFFACER les zéros.

    Un locataire mesuré dont le compteur vaut zéro doit rendre `0`, pas `None`. Sans
    cette assertion, « rendre None partout » satisferait le test ci-dessus et
    détruirait l'information inverse — c'est la forme que ce dépôt appelle un
    correctif qui casse le cas symétrique.
    """
    cursor.execute("""
        SELECT count(*) FROM v_hypeddit_daily
         WHERE artist_id IS NOT NULL AND visits = 0
    """)
    measured_zeros = (cursor.fetchone() or [0])[0]
    cursor.execute("SELECT count(*) FROM v_platform_totals")
    gold_rows = (cursor.fetchone() or [0])[0]
    if not gold_rows:
        pytest.skip("base sans données or — rien à distinguer")
    assert measured_zeros >= 0          # la requête a tourné
    cursor.execute("""
        SELECT count(*) FROM v_platform_totals WHERE total IS NULL
    """)
    nulls = (cursor.fetchone() or [0])[0]
    assert nulls == 0, (
        f"{nulls} ligne(s) de `v_platform_totals` portent NULL. Une LIGNE veut dire "
        "« mesuré » ; sa valeur doit donc être un nombre, fût-il zéro. Rendre NULL "
        "ici déplacerait l'ambiguïté au lieu de la lever.")
