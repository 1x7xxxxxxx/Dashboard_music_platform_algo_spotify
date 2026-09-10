"""Un artiste sans données ne reçoit pas « 0 stream cette semaine ».

Type: Test
Uses: pytest, ast
Depends on: src/utils/digest_queries.py, airflow/dags/weekly_digest.py
Persists in: nothing

Ce qui a été mesuré
-------------------
2026-09-10. `weekly_digest.py` portait `COALESCE(SUM(…), 0)` sur les streams des
7 jours, sur la dépense Meta et un `ELSE 0` sur le CTR. Un locataire premium sans
dépôt S4A recevait donc, par e-mail :

    Streams (last 7 days)   0     +0 vs prev week
    Spend                   0.00 €
    CTR                     0.00 %

Trois affirmations qu'on n'avait pas mesurées. Le CTR est le pire des trois : sans
impression il n'est pas nul, il est **indéfini** — 0/0.

Le même fichier écrivait déjà, vingt lignes plus bas, à propos de SoundCloud :
« No COALESCE: an absent snapshot must read "N/A", not a fabricated 0. » La règle
était donc connue, écrite, appliquée à trois sources sur cinq, et contredite sur les
deux autres.

Pourquoi ce garde-ci et pas une lecture du texte du DAG
-------------------------------------------------------
Chercher « COALESCE » dans le fichier serait aveugle de deux façons : le mot survit
dans un commentaire qui explique le correctif, et il est LÉGITIME ailleurs (le
`COALESCE` d'un `ORDER BY`, par exemple). On teste donc ce que la requête REND —
sur une base réelle, pour un locataire qui n'existe pas — et ce que le gabarit FAIT
de ce retour, par l'AST.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.utils.digest_queries import (
    META_WEEKLY_SPEND_SQL,
    SPOTIFY_WEEKLY_STREAMS_SQL,
    fmt_delta,
    fmt_value,
)

# Un identifiant qui n'a jamais existé : la requête doit rendre « je ne sais pas »,
# et non « il ne s'est rien passé ».
_ABSENT_TENANT = 999_999

_DAG = Path(__file__).resolve().parent.parent / "airflow" / "dags" / "weekly_digest.py"

# Les quatre nombres que l'e-mail montre à l'artiste. Aucun ne doit être interpolé
# directement : `f"{last_7d:,}"` lève sur None, donc le correctif honnête se paierait
# d'un e-mail non envoyé — c'est la raison d'être de `fmt_value`.
_ARTIST_FACING = {"last_7d", "prev_7d", "meta_spend", "meta_ctr", "top_song_streams"}


def _live_db():
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        if db is None:
            return None
        db.fetch_query("SELECT 1")
        return db
    except Exception:
        return None


# ── Ce que la requête rend, sur une vraie base ──────────────────────────────

@pytest.mark.parametrize("sql", [SPOTIFY_WEEKLY_STREAMS_SQL, META_WEEKLY_SPEND_SQL])
def test_an_absent_tenant_reads_unknown_not_zero(sql: str) -> None:
    """Zéro ligne doit rendre NULL sur CHAQUE colonne, jamais 0."""
    db = _live_db()
    if db is None:
        pytest.skip("pas de Postgres sur 5433 — ce garde a besoin du vrai moteur")
    try:
        rows = db.fetch_query(sql, (_ABSENT_TENANT,))
    finally:
        db.close()

    assert rows, "la requête doit rendre une ligne d'agrégats, même sans donnée"
    for i, value in enumerate(rows[0]):
        assert value is None, (
            f"la colonne {i} rend {value!r} pour un locataire qui n'a AUCUNE ligne. "
            "Un zéro à cet endroit part par e-mail chez l'artiste et lui décrit une "
            "semaine qu'on n'a pas mesurée."
        )


# ── Ce que le gabarit fait de ce retour ─────────────────────────────────────

def test_the_formatter_says_it_does_not_know() -> None:
    assert "N/A" in fmt_value(None)
    assert "N/A" in fmt_value(None, ".2f", " €")
    assert "N/A" in fmt_delta(None)
    assert "0" not in fmt_value(None), "une absence ne doit contenir aucun chiffre"


def test_the_formatter_still_prints_a_real_zero() -> None:
    """Un zéro MESURÉ reste un zéro : le correctif ne doit pas effacer l'information."""
    assert "0" in fmt_value(0)
    assert "N/A" not in fmt_value(0)
    assert "0.00 €" in fmt_value(0.0, ".2f", " €")


def test_every_artist_facing_number_goes_through_the_formatter() -> None:
    """Aucun de ces noms n'est interpolé à nu dans le gabarit HTML.

    Structurel, jamais textuel : on lit les `FormattedValue` de l'f-string, donc un
    nom qui survit dans un commentaire ou dans une autre fonction ne peut pas rendre
    ce garde vert par accident.
    """
    tree = ast.parse(_DAG.read_text(encoding="utf-8"))
    bare: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FormattedValue):
            continue
        expr = node.value
        if isinstance(expr, ast.Name) and expr.id in _ARTIST_FACING:
            bare.append(f"{expr.id} (ligne {expr.lineno})")

    assert not bare, (
        "interpolés à nu dans le gabarit de l'e-mail : " + ", ".join(bare) + ". "
        "Ces valeurs valent None quand rien n'a été mesuré : `:,` et `:.2f` lèvent, "
        "et l'artiste ne reçoit plus rien du tout. Passer par `fmt_value`."
    )
