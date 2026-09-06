"""Guard: une colonne absente de la PREMIÈRE ligne n'est écrite pour aucune.

Type: Utility
Uses: src.database.postgres_handler
Triggers: pytest
Persists in: nothing

Error class `bulk-write-reads-only-the-first-row`.

`insert_many` et `upsert_many` construisaient la liste des colonnes avec
`list(data[0].keys())`. Un lot hétérogène — la norme dès qu'un parseur n'émet un
champ que lorsqu'il le trouve — perdait donc toute colonne que la première ligne ne
portait pas : pas d'erreur, pas de journal, la valeur n'arrive simplement jamais.

Le défaut est silencieux DANS LES DEUX SENS : la requête est valide, la transaction
réussit, le compte renvoyé est juste. Rien à l'écran ne peut le trahir — seule la
requête effectivement construite le dit, et c'est donc elle qu'on lit ici, pas le
texte du fichier source.
"""
from __future__ import annotations

import pytest

from src.database.postgres_handler import PostgresHandler, _union_columns


class _FakeCursor:
    """Curseur qui enregistre la requête composée au lieu de l'exécuter.

    `execute_batch` appelle `mogrify` avant tout envoi ; le rendre inoffensif
    suffit à faire tourner les deux méthodes hors base.
    """

    def __init__(self) -> None:
        self.queries: list[object] = []
        self.rowcount = 0

    def executemany(self, query, _args=None) -> None:
        self.queries.append(query)

    def execute(self, query, _args=None) -> None:
        self.queries.append(query)

    def mogrify(self, query, _args=None) -> bytes:
        self.queries.append(query)
        return b""


def _handler(cursor: _FakeCursor) -> PostgresHandler:
    h = PostgresHandler.__new__(PostgresHandler)
    h.cursor = cursor
    h._ensure_connection = lambda: None          # type: ignore[method-assign]
    return h


# La colonne témoin est `saves` et NON `streams` : `streams` figure dans
# `update_columns`, donc `upsert_many` l'écrit dans le `DO UPDATE SET` quoi qu'il
# arrive dans les données. Un premier jet de ce garde s'en servait comme témoin et
# restait VERT sur le défaut — l'assertion mesurait la mise à jour, pas les colonnes
# insérées. Le témoin doit n'apparaître QUE par le chemin qu'on teste.
_HETEROGENEOUS = [
    {"artist_id": 1, "song": "A", "date": "2026-01-01", "streams": 12},
    {"artist_id": 1, "song": "B", "date": "2026-01-02", "streams": 42, "saves": 3},
]


def test_union_columns_keeps_a_late_column():
    cols = _union_columns(_HETEROGENEOUS)
    assert "saves" in cols, (
        "`saves` n'apparaît que dans la 2ᵉ ligne. Lire `data[0].keys()` la perd "
        "pour tout le lot, sans erreur ni journal."
    )
    assert cols[:3] == ["artist_id", "song", "date"], (
        "l'ordre de rencontre est ce qui rend la requête lisible et déterministe"
    )


@pytest.mark.parametrize("method", ["insert_many", "upsert_many"])
def test_a_bulk_write_puts_every_column_in_the_query(method):
    cur = _FakeCursor()
    db = _handler(cur)

    if method == "insert_many":
        db.insert_many(table="s4a_song_timeline", data=_HETEROGENEOUS)
    else:
        db.upsert_many(
            table="s4a_song_timeline", data=_HETEROGENEOUS,
            conflict_columns=["artist_id", "song", "date"],
            update_columns=["streams"],
        )

    assert cur.queries, f"{method} n'a composé aucune requête"
    sql = " ".join(repr(q) for q in cur.queries)
    assert "Identifier('saves')" in sql, (
        f"{method} a composé une requête SANS la colonne `saves`, qui n'existe "
        "que dans la deuxième ligne du lot. Les valeurs disparaissent en silence : "
        "la requête est valide, la transaction réussit, le compte renvoyé est juste."
    )
