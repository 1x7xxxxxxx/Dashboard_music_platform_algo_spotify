"""Guard: a collector's constructor must accept the database it will write to.

Type: Utility
Uses: ast, inspect
Triggers: pytest
Persists in: nothing

Error class `no-db-signature-opens-a-connection`.

Measured 2026-09-06. `InstagramCollector.__init__` and `SoundCloudCollector.__init__`
opened a Postgres connection unconditionally, so no question about their pure logic
could be asked without a live database. The visible cost: the guard for
`guard-asserts-presence-not-reachability` — « un pseudo absent lève-t-il avec le
geste ? », which writes nothing — failed in the CI step that runs BEFORE
`Provision Postgres`, on `psycopg2.OperationalError`. It reported a class it had
nothing to do with.

`MetaAdsCollector` already took `db=None` and fell back to `_default_db()`. The
pattern was in the repo; two of the three collectors had simply never adopted it.
This file makes that a property rather than a coincidence.

**Injection, not laziness.** A lazy `self.db` would move the failure of an
unreachable database to AFTER the API calls — quota spent on rows that cannot be
written. With `db=None` still the production path, production keeps failing
immediately, and only a caller with nothing to write says so.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


_COLLECTORS = _repo_root() / "src" / "collectors"


def _classes_opening_a_db(path: Path) -> list[tuple[str, ast.FunctionDef]]:
    """(class name, its __init__) for every class whose __init__ builds a handler."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        init = next((n for n in node.body
                     if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None)
        if init is None:
            continue
        builds = any(
            isinstance(c, ast.Call) and "from_env_or_config" in ast.unparse(c.func)
            for c in ast.walk(init))
        # `MetaAdsCollector` délègue à `_default_db()` — même fait, une indirection.
        builds = builds or any(
            isinstance(c, ast.Call) and ast.unparse(c.func).endswith("_default_db")
            for c in ast.walk(init))
        if builds:
            out.append((node.name, init))
    return out


def _all_targets() -> list[tuple[str, str, ast.FunctionDef]]:
    found = []
    for path in sorted(_COLLECTORS.glob("*.py")):
        for name, init in _classes_opening_a_db(path):
            found.append((path.name, name, init))
    return found


def test_the_sweep_finds_the_collectors_it_is_about():
    """Sinon les assertions suivantes sont vraies sur l'ensemble vide."""
    targets = _all_targets()
    assert len(targets) >= 3, (
        f"seulement {len(targets)} collecteur(s) ouvrant une base trouvé(s) : "
        f"{[t[1] for t in targets]}. Le balayage ne voit plus ce qu'il garde.")


@pytest.mark.parametrize("module,cls", [(m, c) for m, c, _ in _all_targets()])
def test_every_collector_that_opens_a_database_lets_one_be_passed(module, cls):
    """`db=` dans la signature — la question pure doit pouvoir être posée."""
    init = next(i for m, c, i in _all_targets() if m == module and c == cls)
    args = [a.arg for a in init.args.args] + [a.arg for a in init.args.kwonlyargs]
    assert "db" in args, (
        f"{module}:{cls}.__init__ ouvre une connexion et n'accepte pas `db=` : "
        "aucune question sur sa logique pure ne peut être posée sans une base, et "
        "ses gardes tombent pour une raison qui n'est pas la leur.")


@pytest.mark.parametrize("module,cls", [(m, c) for m, c, _ in _all_targets()])
def test_the_injected_database_is_the_one_that_is_used(module, cls):
    """`db=` doit être POSÉ sur l'instance, pas accepté puis ignoré.

    Un paramètre accepté et jeté est pire que pas de paramètre : l'appelant croit
    avoir débranché la base et ouvre quand même une connexion.
    """
    init = next(i for m, c, i in _all_targets() if m == module and c == cls)
    assigns_from_db = [
        n for n in ast.walk(init)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "db" for t in n.targets)
        and any(isinstance(x, ast.Name) and x.id == "db" for x in ast.walk(n.value))
    ]
    assert assigns_from_db, (
        f"{module}:{cls}.__init__ accepte `db=` sans jamais s'en servir pour "
        "`self.db` — le paramètre ment.")


def test_production_still_fails_immediately_on_an_unreachable_database():
    """`db=None` reste le chemin de production, donc l'échec reste immédiat.

    C'est la moitié qu'une connexion PARESSEUSE aurait perdue : l'API serait appelée
    d'abord, le quota dépensé, et l'écriture échouerait ensuite.
    """
    from src.collectors.instagram_api_collector import InstagramCollector

    sig = inspect.signature(InstagramCollector.__init__)
    assert sig.parameters["db"].default is None, (
        "le défaut de `db` n'est plus None : le chemin de production ne construit "
        "plus sa connexion, et l'échec d'une base injoignable arrivera après les "
        "appels d'API")
