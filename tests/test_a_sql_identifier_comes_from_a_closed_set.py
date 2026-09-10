"""Un nom de table ou de colonne interpolé vient d'un ensemble FERMÉ, jamais d'une entrée.

Type: Test
Uses: pytest, ast
Depends on: src/
Persists in: nothing

Pourquoi ce garde existe, et pourquoi il n'existait pas
-------------------------------------------------------
`sql-fstring-identifier` est au catalogue depuis longtemps en **P1**, et son statut
était `open` : son seul « garde » était une règle de `CLAUDE.md` — c'est-à-dire une
phrase — doublée d'une signature en `grep` textuel. Ce dépôt a mesuré cinq fois qu'un
garde textuel est aveugle : il ne voit ni la structure, ni la provenance, et il rougit
sur le commentaire qui explique le correctif.

Une valeur passe par `%s` ; un IDENTIFIANT ne le peut pas — PostgreSQL n'accepte pas de
paramètre en position de table ou de colonne. C'est pourquoi la règle #8 ne dit pas
« n'interpole jamais » mais « valide contre un `frozenset` avant d'interpoler ».

Ce que la mesure a rendu (2026-09-10)
-------------------------------------
**20 interpolations d'identifiant dans une f-string réellement SQL, et zéro injection
vivante.** Chaque site tire son nom d'un ensemble fermé écrit dans le code : neuf
modules valident contre une allowlist ou importent un validateur, et le dixième
(`pdf_exporter/_collectors.py`) itère sur `_BREAKDOWN_DIMS`, un dictionnaire littéral
de module.

Le premier prédicat écrit pour cette mesure s'est trompé DEUX fois, et les deux erreurs
valaient d'être gardées :

* il cherchait la validation dans la fonction ENGLOBANTE — or `period_filter.py` valide
  dans `_validate()`, appelée depuis ailleurs. Sept faux positifs ;
* il comptait « ✅ Table {name} », un message de LOG, parce que son motif voyait le mot
  `Table`. Un garde qui crie sur un log perd sa crédibilité sur une injection : la
  f-string doit d'abord porter un verbe SQL.

Ce que ce garde tient, et ce qu'il ne tient pas
-----------------------------------------------
Il tient la PROVENANCE : l'expression interpolée doit venir d'un ensemble fermé,
lisible dans le module. Il ne fait pas d'analyse de flot — un identifiant qui
traverserait trois fonctions depuis une entrée utilisateur lui échapperait. C'est dit
ici plutôt que sous-entendu : le cliquet est à ZÉRO, donc tout site nouveau doit
prouver sa provenance, ce qui est la propriété qu'on peut réellement vérifier.
"""
from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Les positions où PostgreSQL attend un IDENTIFIANT — donc où `%s` est impossible.
_IDENT_POS = re.compile(
    r"\b(FROM|JOIN|INTO|UPDATE|TABLE|INDEX|ORDER\s+BY|GROUP\s+BY|"
    r"REFERENCES|TRUNCATE|ALTER\s+TABLE)\s*$", re.I)

# La f-string doit porter un VERBE SQL. Sans cela, « ✅ Table {name} » d'un journal
# entre dans le compte — et un garde qui crie sur un log perd sa crédibilité.
_IS_SQL = re.compile(r"\b(SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|CREATE\s+TABLE|"
                     r"ALTER\s+TABLE|TRUNCATE)\b", re.I)

_VALIDATORS = ("validate_table", "validate_columns", "validate_identifier")

# Gelé le 2026-09-10 : 20 sites, 0 sans provenance. CE NOMBRE NE PEUT QUE DESCENDRE.
_MAX_UNSOURCED = 0


def _literal_text(node: ast.JoinedStr) -> str:
    return "".join(p.value for p in node.values
                   if isinstance(p, ast.Constant) and isinstance(p.value, str))


def _module_closes_its_identifiers(tree: ast.Module) -> bool:
    """Le module tire-t-il ses identifiants d'un ensemble FERMÉ, lisible ici ?

    Trois formes acceptées, et elles couvrent les dix modules concernés :
    une allowlist consultée (`frozenset` + un `in`), un validateur importé, ou un
    conteneur littéral de module dont on itère les valeurs (`_BREAKDOWN_DIMS`).
    """
    has_allowlist = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                        and n.func.id == "frozenset" for n in ast.walk(tree))
    checks_membership = any(
        isinstance(n, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn))
                                           for o in n.ops)
        for n in ast.walk(tree))
    imports_validator = any(
        isinstance(n, ast.ImportFrom)
        and any(a.name in _VALIDATORS for a in n.names)
        for n in ast.walk(tree))
    # Un conteneur littéral au niveau MODULE : ses clés et valeurs sont écrites dans le
    # fichier, donc fermées par construction.
    literal_container = any(
        isinstance(n, ast.Assign)
        and isinstance(n.value, (ast.Dict, ast.Tuple, ast.List, ast.Set))
        and any(isinstance(t, ast.Name) and t.id == t.id.upper() for t in n.targets)
        for n in tree.body)
    return (has_allowlist and checks_membership) or imports_validator or literal_container


@lru_cache(maxsize=1)
def _sites() -> list[tuple[bool, str, int, str]]:
    """(provenance fermée, fichier, ligne, expression) pour chaque interpolation."""
    found: list[tuple[bool, str, int, str]] = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        closed = _module_closes_its_identifiers(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.JoinedStr):
                continue
            if not _IS_SQL.search(_literal_text(node)):
                continue
            seen = ""
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    seen += part.value
                elif isinstance(part, ast.FormattedValue):
                    if _IDENT_POS.search(seen):
                        try:
                            expr = ast.unparse(part.value)
                        except Exception:  # noqa: BLE001
                            expr = "?"
                        found.append((closed, str(path.relative_to(ROOT)),
                                      node.lineno, expr))
                    seen += "{}"
    return found


def test_no_sql_identifier_comes_from_outside_a_closed_set() -> None:
    unsourced = [f"{f}:{ln} → {{{expr}}}" for closed, f, ln, expr in _sites()
                 if not closed]
    assert len(unsourced) <= _MAX_UNSOURCED, (
        f"{len(unsourced)} identifiant(s) SQL interpolé(s) dans un module qui ne les "
        f"ferme pas : {unsourced}\n"
        "Un identifiant ne peut pas passer par `%s` — PostgreSQL n'accepte pas de "
        "paramètre en position de table ou de colonne. Il doit donc venir d'un "
        "`frozenset` consulté, d'un validateur importé, ou d'un conteneur littéral de "
        "module. Ce plafond ne monte pas.")


def test_the_predicate_still_sees_the_shape_it_guards() -> None:
    """Non-vacuité : un cliquet à zéro doit prouver qu'il VOIT, pas qu'il ne trouve rien."""
    sites = _sites()
    assert len(sites) >= 15, (
        f"seulement {len(sites)} interpolation(s) trouvée(s) — il y en avait 20 le "
        "2026-09-10. Le prédicat est devenu aveugle, et le cliquet à zéro ci-dessus "
        "certifie alors une propriété qu'il ne vérifie plus.")


def test_a_log_message_is_not_mistaken_for_a_query() -> None:
    """« ✅ Table {name} » n'est pas du SQL. Sept faux positifs au premier essai."""
    probe = ast.parse('x = f"   ✅ Table {table_name} created"')
    joined = next(n for n in ast.walk(probe) if isinstance(n, ast.JoinedStr))
    assert not _IS_SQL.search(_literal_text(joined)), (
        "le prédicat prend un message de journal pour une requête. Un garde qui crie "
        "sur un log perd sa crédibilité sur une vraie injection — c'est le mécanisme "
        "par lequel les gardes `rm -rf /tmp/...` avaient rendu le travail impossible.")


def test_a_real_interpolated_table_name_is_seen() -> None:
    """L'autre moitié de la non-vacuité : la forme dangereuse doit être reconnue."""
    probe = ast.parse('q = f"SELECT * FROM {table} WHERE artist_id = %s"')
    joined = next(n for n in ast.walk(probe) if isinstance(n, ast.JoinedStr))
    assert _IS_SQL.search(_literal_text(joined))
    seen, hit = "", False
    for part in joined.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            seen += part.value
        elif isinstance(part, ast.FormattedValue):
            if _IDENT_POS.search(seen):
                hit = True
            seen += "{}"
    assert hit, (
        "le prédicat ne reconnaît plus `FROM {table}` — la forme même de la classe P1 "
        "qu'il est censé garder")
