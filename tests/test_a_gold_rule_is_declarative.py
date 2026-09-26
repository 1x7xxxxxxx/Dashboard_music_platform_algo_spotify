"""The gold layer holds at most ONE procedural function; every other rule is a view.

Type: Sub
Uses: migrations/*.sql
Depends on: nothing — the SQL is read as text, never executed
Persists in: nothing

Class `a-procedural-rule-in-the-database`: `gold_apple_lifetime()` makes a greedy
selection of non-overlapping intervals that no `GROUP BY` expresses — legitimate once.
The risk is the NEXT function, written "like the previous one" for a rule a declarative
view would express. The class signature counted distinct `gold_*` functions with a
shell pipeline; this file counts them with a predicate that proves itself.

Mutation record — 2026-09-26: the proof was seen red with comments counted, with the
case not folded, and with `OR REPLACE`/schema-qualified creations ignored.
"""
from __future__ import annotations

import re
from pathlib import Path

_MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
_CREATE = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:public\.)?(gold_[a-z_]+)",
                     re.I)
_CEILING = 1   # gold_apple_lifetime, and only it


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)
    return re.sub(r"--[^\n]*", "", sql)


def gold_functions(sql_texts: list[str]) -> set[str]:
    """Distinct `gold_*` functions CREATED by these SQL files — an overload or a
    `CREATE OR REPLACE` of the same name counts once; a comment counts for nothing.
    Pure."""
    return {m.group(1).lower() for sql in sql_texts
            for m in _CREATE.finditer(_strip_comments(sql))}


def test_the_gold_layer_has_at_most_one_procedural_function() -> None:
    found = gold_functions([p.read_text(encoding="utf-8")
                            for p in sorted(_MIGRATIONS.glob("*.sql"))])
    assert found, "aucune fonction gold_* trouvée — le balayage ne voit plus les migrations"
    assert len(found) <= _CEILING, (
        f"{sorted(found)} : {len(found)} fonctions procédurales dans la couche or, pour "
        f"un plafond de {_CEILING}. Une règle qu'un `GROUP BY` ou une fenêtre exprime "
        "s'écrit en VUE — lisible, déclarative, sans surcharge possible. Une seconde "
        "fonction se justifie dans une ADR, et ce plafond monte dans le même commit.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: a second `gold_*` function is counted; the overload of migration
    103, a `CREATE OR REPLACE` or an upper-case spelling of the same name, and a
    function named in a comment are not counted twice — nor at all for the comment;
    a second function written `create or replace function public.…` is counted."""
    first = "CREATE FUNCTION gold_apple_lifetime(a integer) RETURNS bigint AS $$ $$;"
    overload = ("CREATE OR REPLACE FUNCTION public.gold_apple_lifetime(a integer, "
                "m text DEFAULT 'plays') RETURNS bigint AS $$ $$;")
    comment = "-- CREATE FUNCTION gold_youtube_total(a integer)\n/* CREATE FUNCTION gold_x() */"
    shouted = "CREATE FUNCTION GOLD_APPLE_LIFETIME(a integer) RETURNS bigint AS $$ $$;"
    assert gold_functions([first, overload, comment, shouted]) == {"gold_apple_lifetime"}
    # Postgres folds an unquoted name: the upper-case spelling is the same function.
    second = ("create or replace function public.gold_youtube_total(a integer) "
              "returns bigint as $$ $$;")
    assert gold_functions([first, second]) == {"gold_apple_lifetime", "gold_youtube_total"}
