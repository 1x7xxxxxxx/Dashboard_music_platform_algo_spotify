"""Le sélecteur de période propose l'étendue de CE QUI EST TRACÉ.

Type: Test
Uses: ast
Triggers: CI, select_tests.py
Depends on: src/dashboard/utils/period_filter.py

Le défaut gardé, et pourquoi le garde est STRUCTUREL
----------------------------------------------------
`_data_span` interpole un nom de table dans un `SELECT MIN(...), MAX(...) FROM {table}
WHERE 1=1` **sans aucun prédicat métier**. Tant que `s4a_song_timeline` figurait dans
`_ALLOWED_TABLES`, l'étendue proposée était donc celle de TOUTE la table — ligne
« Total » des CSV comprise (règle transverse #8 violée par construction), et tous
titres confondus, alors que la figure d'à côté n'en trace qu'un. Un titre mesuré sur
646 jours se voyait offrir la fenêtre de 1 254.

**Ajouter le filtre n'aurait rien gardé.** Le garde textuel du dépôt recoud les
f-strings par `ast.JoinedStr` : le SQL recousu ici vaut littéralement
« SELECT MIN( )::date, MAX( )::date FROM  WHERE 1=1 » — le nom de la table n'y
apparaît pas, donc aucun détecteur de « lecture de s4a_song_timeline » ne peut le
voir. C'est la classe `a-textual-guard-blind-to-its-own-subject`.

Le correctif durable est donc une propriété de l'ALLOWLIST : seules des relations qui
portent leurs prédicats en elles — les vues or — ont le droit d'y entrer.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "dashboard" / "utils" / "period_filter.py"

# Les tables de fait qui portent une règle de filtre OBLIGATOIRE. Une étendue lue
# dessus sans prédicat est fausse par construction.
_MANDATORY_FILTER_TABLES = frozenset({
    "s4a_song_timeline",   # AND song NOT ILIKE '%1x7xxxxxxx%' (CLAUDE.md règle #8)
    "s4a_audience",        # le même export porte deux périmètres (migration 117)
})


@pytest.fixture(scope="module")
def pf():
    import sys
    sys.path.insert(0, str(ROOT))
    from src.dashboard.utils import period_filter
    return period_filter


def test_no_table_with_a_mandatory_filter_is_bornable(pf):
    bad = _MANDATORY_FILTER_TABLES & set(pf._ALLOWED_TABLES)
    assert not bad, (
        f"{sorted(bad)} porte(nt) un filtre obligatoire et ne peu(ven)t pas être "
        f"bornée(s) : `_data_span` lit MIN/MAX sans prédicat, donc l'étendue "
        f"proposée inclurait la ligne « Total » et tous les titres. "
        f"Remplacement : {pf._REPLACED_BY_GOLD}")


def test_each_removed_table_names_its_replacement(pf):
    """Une interdiction sans remplacement se fait contourner « parce que ça marchait »."""
    for table in _MANDATORY_FILTER_TABLES:
        assert table in pf._REPLACED_BY_GOLD, f"{table} interdite sans remplacement nommé"
        assert pf._REPLACED_BY_GOLD[table] in pf._ALLOWED_TABLES, (
            f"le remplacement de {table} n'est pas lui-même bornable")


def test_passing_a_removed_table_raises_with_the_fix(pf):
    """Le message doit nommer la vue à utiliser, pas seulement refuser."""
    for table, replacement in pf._REPLACED_BY_GOLD.items():
        with pytest.raises(ValueError) as exc:
            pf._validate(table, "date", "artist_id")
        assert replacement in str(exc.value), (
            f"le refus de '{table}' ne nomme pas '{replacement}' : « {exc.value} »")


def test_data_span_can_restrict_to_the_entity_drawn(pf):
    """Sans ce paramètre, l'étendue reste celle de toute la table."""
    sig = inspect.signature(pf._data_span)
    assert "entity_column" in sig.parameters, (
        "`_data_span` ne peut pas se restreindre à ce qui est tracé")
    assert "entity_value" in sig.parameters


def test_an_entity_column_is_validated_against_an_allowlist(pf):
    """Un nom de colonne interpolé se valide contre une liste blanche (règle #8).

    La valeur passée ici est un identifiant qui n'est simplement pas dans la liste —
    le point du test est le REFUS, et un refus se prouve avec n'importe quel nom
    absent, sans avoir à écrire une charge hostile.
    """
    with pytest.raises(ValueError):
        pf._data_span(None, "v_s4a_song_daily", "day", "artist_id", 1,
                      entity_column="colonne_absente_de_la_liste", entity_value="x")


# --- non-vacuité -----------------------------------------------------------------

def test_the_allowlist_is_not_empty(pf):
    """Un garde qui vérifie une intersection vide passerait sur une liste vide."""
    assert len(pf._ALLOWED_TABLES) >= 5


def test_an_allowed_entity_column_is_accepted(pf):
    """Le refus ci-dessus ne prouve rien si TOUT est refusé."""
    assert "song" in pf._ALLOWED_ENTITY_COLUMNS
    assert "match_key" in pf._ALLOWED_ENTITY_COLUMNS


def test_the_textual_guard_really_cannot_see_this_sql():
    """La raison d'être du garde structurel, vérifiée plutôt qu'affirmée.

    On recoud le littéral de `_data_span` comme le fait le garde textuel du dépôt :
    le nom de la table ne doit PAS y apparaître. Si un jour il y apparaît, ce test
    rougit — et c'est le signal que le garde textuel suffit, donc que celui-ci peut
    être reconsidéré.
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_data_span")
    stitched = []
    for node in ast.walk(fn):
        if isinstance(node, ast.JoinedStr):
            stitched.append("".join(
                v.value for v in node.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)))
    assert stitched, "`_data_span` n'assemble plus de f-string — relire ce test"
    assert "s4a_song_timeline" not in " ".join(stitched), (
        "le nom de la table apparaît désormais en clair : un garde textuel pourrait "
        "le voir, donc ce garde structurel n'est plus le seul recours")
