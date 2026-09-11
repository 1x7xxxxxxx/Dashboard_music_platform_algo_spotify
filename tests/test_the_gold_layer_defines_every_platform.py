"""Les quatre plateformes ont une définition OR, en SQL, et une seule.

Type: Test
Uses: psycopg2, une base vivante (les cas synthétiques vivent dans une transaction annulée)
Depends on: migrations/097, migrations/102, v_platform_totals, gold_apple_lifetime()
Persists in: rien — tout est écrit puis annulé

Pourquoi ce garde existe
------------------------
Apple a été jusqu'au 2026-09-12 la dernière plateforme dont le total n'avait AUCUNE
définition SQL : sa règle vivait dans `platform_timeseries.apple_lifetime_plays`, et
cinq fichiers lisaient `apple_songs_performance` directement — aujourd'hui pour
lister, rien n'empêchait le prochain de totaliser à sa façon. C'est exactement ainsi
que YouTube a eu trois définitions incompatibles avant la migration 097.

Sa règle n'est pas un agrégat : elle choisit entre trois formes de relevé, dont une
sélection GLOUTONNE d'intervalles. Un `GROUP BY` ne l'exprime pas, d'où une fonction
PL/pgSQL — et d'où ce garde, parce qu'une fonction est moins relue qu'une requête.

Les trois branches sont épinglées sur des données SYNTHÉTIQUES, dans une transaction
annulée : la base de production n'a qu'un locataire Apple, et une preuve sur un seul
cas n'en est pas une. Chaque branche a sa donnée, choisie pour que la mauvaise
réponse soit différente de la bonne.
"""
from __future__ import annotations

import datetime as _d
import os
import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _dsn() -> dict | None:
    if os.environ.get("DATABASE_URL"):
        return {"dsn": os.environ["DATABASE_URL"]}
    try:
        with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
            pass
    except OSError:
        return None
    return {"host": _DB_HOST, "port": _DB_PORT,
            "dbname": os.environ.get("DATABASE_NAME", "spotify_etl"),
            "user": os.environ.get("DATABASE_USER", "postgres"),
            "password": os.environ.get("DATABASE_PASSWORD")
            or os.environ.get("DB_PASSWORD", "")}


_CONN = _dsn()

pytestmark = pytest.mark.skipif(
    _CONN is None,
    reason=f"Pas de Postgres sur {_DB_HOST}:{_DB_PORT} — seule la base peut répondre",
)

# Un locataire qui n'existe pas : les lignes sont écrites puis annulées, mais un id
# hors de portée évite toute collision avec une vraie donnée si le rollback rate.
_FAKE = -424242


@pytest.fixture
def scratch():
    """Un curseur dans une transaction TOUJOURS annulée."""
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**_CONN)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            # `apple_songs_performance.artist_id` porte une clé étrangère vers
            # `saas_artists` — et c'est une bonne chose : c'est elle qui empêche une
            # ligne orpheline. Le locataire d'essai est donc créé ici, dans la même
            # transaction annulée, plutôt que de désactiver la contrainte.
            cur.execute(
                "INSERT INTO saas_artists (id, name, slug) VALUES (%s, %s, %s)",
                (_FAKE, "scratch-gold-test", f"scratch-gold-{abs(_FAKE)}"))
            yield cur
    finally:
        conn.rollback()
        conn.close()


def _insert(cur, rows) -> None:
    for song, start, end, snap, plays in rows:
        cur.execute(
            "INSERT INTO apple_songs_performance "
            "(artist_id, song_name, period_start, period_end, snapshot_date, plays) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (_FAKE, song, start, end, snap, plays))


def _gold(cur) -> int:
    cur.execute("SELECT gold_apple_lifetime(%s)", (_FAKE,))
    return int(cur.fetchone()[0] or 0)


def test_nested_readings_are_never_counted_twice(scratch) -> None:
    """L'export « depuis le début » CONTIENT les années : on ne les additionne pas.

    Additionner 1 000 (le cumul) et 400 + 300 (les deux années qu'il contient)
    rendrait 1 700 pour 1 000 écoutes réelles. C'est la faute qui a produit
    « 23 560 écoutes par jour » le 2026-09-08.
    """
    _insert(scratch, [
        ("a", _d.date(2020, 1, 1), _d.date(2026, 1, 1), _d.date(2026, 9, 1), 1000),
        ("a", _d.date(2024, 1, 1), _d.date(2024, 12, 31), _d.date(2026, 9, 1), 400),
        ("a", _d.date(2025, 1, 1), _d.date(2025, 12, 31), _d.date(2026, 9, 1), 300),
    ])
    got = _gold(scratch)
    assert got == 1000, (
        f"{got} au lieu de 1 000 : les années imbriquées dans le cumul ont été "
        "comptées en plus de lui (1 700), ou le cumul a été ignoré (700).")


def test_disjoint_years_are_summed(scratch) -> None:
    """Deux années qui ne se chevauchent pas s'additionnent — il n'y a pas de cumul."""
    _insert(scratch, [
        ("a", _d.date(2024, 1, 1), _d.date(2024, 12, 31), _d.date(2026, 9, 1), 400),
        ("a", _d.date(2025, 1, 1), _d.date(2025, 12, 31), _d.date(2026, 9, 1), 300),
    ])
    got = _gold(scratch)
    assert got == 700, f"{got} au lieu de 700 — le découpage disjoint doit se sommer"


def test_the_cover_wins_when_it_is_more_complete_than_the_widest(scratch) -> None:
    """Le cumul peut être INCOMPLET : on rend le plus grand des deux.

    Un export « depuis le début » déposé avant la dernière année ne la contient pas.
    Préférer aveuglément le plus large perdrait cette année.
    """
    _insert(scratch, [
        ("a", _d.date(2020, 1, 1), _d.date(2024, 6, 30), _d.date(2026, 9, 1), 500),
        ("a", _d.date(2025, 1, 1), _d.date(2025, 12, 31), _d.date(2026, 9, 1), 300),
        ("a", _d.date(2026, 1, 1), _d.date(2026, 6, 30), _d.date(2026, 9, 1), 250),
    ])
    got = _gold(scratch)
    assert got == 1050, (
        f"{got} au lieu de 1 050 : le découpage (500 + 300 + 250) est plus complet "
        "que le seul relevé le plus large (500).")


def test_without_any_bounded_reading_the_last_snapshot_answers(scratch) -> None:
    """La troisième branche : les lignes d'avant la lecture automatique de période.

    Et c'est le DERNIER instantané, pas leur somme — deux instantanés du même titre
    compteraient ce titre deux fois.
    """
    _insert(scratch, [
        ("a", None, None, _d.date(2026, 1, 1), 100),
        ("b", None, None, _d.date(2026, 1, 1), 50),
        ("a", None, None, _d.date(2026, 9, 1), 180),
        ("b", None, None, _d.date(2026, 9, 1), 70),
    ])
    got = _gold(scratch)
    assert got == 250, (
        f"{got} au lieu de 250 : les deux instantanés ont été additionnés (400) au "
        "lieu de retenir le dernier.")


def test_no_reading_at_all_is_zero_not_an_error(scratch) -> None:
    assert _gold(scratch) == 0


def test_the_gold_view_answers_for_all_four_platforms(scratch) -> None:
    """La vue doit NOMMER les quatre plateformes, pas trois.

    Avant la migration 102 elle n'en portait que trois, et Apple répondait `None` —
    un appelant qui teste `if total` traitait donc Apple comme « pas de données »
    alors que la valeur existait, dans une fonction Python que lui seul connaissait.
    """
    scratch.execute("SELECT DISTINCT platform FROM v_platform_totals")
    platforms = {r[0] for r in scratch.fetchall()}
    for expected in ("spotify", "youtube", "soundcloud", "apple"):
        assert expected in platforms, (
            f"la couche or ne définit pas « {expected} » : une surface qui veut son "
            f"total devra la recalculer. Vue actuelle : {sorted(platforms)}")


def test_python_reads_the_sql_rule_instead_of_repeating_it() -> None:
    """Deux implémentations qui s'accordent aujourd'hui ne sont pas une définition.

    `apple_lifetime_plays` portait une copie Python de la règle jusqu'au 2026-09-12.
    Elles s'accordaient sur tous les locataires — et c'est exactement ce qu'on ne peut
    pas garantir dans le temps.
    """
    import ast
    import inspect

    from src.dashboard.utils import platform_timeseries as pts

    fn = ast.parse(inspect.getsource(pts.apple_lifetime_plays).lstrip()).body[0]
    doc = ast.get_docstring(fn, clean=False)

    # Les REQUÊTES de la fonction, docstring exclue — `ast.unparse` la garderait, et
    # une simple mention dans l'explication suffirait alors à satisfaire le test.
    # Le cliquet anti-garde-textuel a refusé cette première version, à raison.
    queries = [n.value for n in ast.walk(fn)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and n.value != doc]
    assert any("gold_apple_lifetime" in q for q in queries), (
        "`apple_lifetime_plays` n'interroge plus la fonction SQL — elle a de nouveau "
        f"sa propre règle, et il y a deux définitions du même nombre. Requêtes : "
        f"{queries}")

    # Et les APPELS : la sélection gloutonne ne doit pas revenir en Python.
    called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "non_overlapping_cover" not in called, (
        "la sélection gloutonne est revenue en Python : c'est la copie qu'on vient "
        "de retirer.")
