"""Guard: multi-tenant DAGs must isolate per-artist failures (no fleet poisoning).

Type: Utility
Error class `multitenant-dag-fleet-poisoning` (.claude/dev-docs/error-classes.md).
Benken incident 2026-06-19: a per-tenant loop `for artist_id, ... in get_active_artists()`
that raises on one bad tenant failed the whole DAG for ALL tenants. The fix wraps each
iteration body in try/except-continue. This test fails CI if a NEW artist-loop ships
without that isolation, so the class can't silently return.
"""
import ast
from pathlib import Path

import pytest

_DAGS_DIR = Path(__file__).resolve().parent.parent / "airflow" / "dags"


# What makes a loop a FLEET loop. Widened 2026-08-22 — the original test was
# "does the target bind a variable literally called `artist_id`", which is a
# hand-written scope with two measured evasions in `alert_monitor.py` alone:
#
#   check_onboarding_readiness:  `for aid, name in get_active_artists(...)`
#                                — the name is `aid`, so the guard never looked at it
#   check_data_freshness:        `[(aid, name, check_freshness(db, aid))
#                                   for aid, name in get_active_artists()]`
#                                — a list COMPREHENSION, not an ast.For at all
#
# The second was genuinely unisolated: one `CredentialLoadError` fails the task, and
# `send_consolidated_alert` has `trigger_rule='all_done'`, so the mail still goes out
# with the whole per-tenant section silently missing. Matching on the ITERATOR — a
# call to `get_active_artists` — cannot be evaded by renaming the loop variable.
_FLEET_SOURCES = {"get_active_artists"}


def _iterates_the_fleet(iter_node: ast.AST) -> bool:
    for n in ast.walk(iter_node):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name in _FLEET_SOURCES:
                return True
    return False


def _fleet_bound_names(tree: ast.AST) -> set[str]:
    """Les variables liées au RÉSULTAT d'un appel de flotte : `artists = get_…()`.

    ⚠️ Ajouté le 2026-09-17, et c'est le troisième aveuglement mesuré de ce fichier.
    `_iterates_the_fleet` ne reconnaît la flotte que si l'appel est INLINE dans
    l'itérateur. La docstring ci-dessus revendiquait pourtant que renommer la variable
    de boucle ne peut pas évader le garde — c'est vrai pour le nom de la CIBLE, faux
    pour l'itérateur. La forme réellement écrite dans ce dépôt est :

        artists = get_active_artists()
        for aid, name in artists:          # ← invisible au garde jusqu'ici

    Mesuré : `soundcloud_daily.py:62` et `instagram_daily.py:56` — les DEUX precheck,
    c'est-à-dire exactement les tâches dont l'échec bloque `collect_task` par
    `all_success` — n'étaient pas même REGARDÉES par ce test.
    """
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _iterates_the_fleet(node.value):
            for target in node.targets:
                bound |= {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}
    return bound


def _artist_loops(tree: ast.AST):
    """Yield every loop over the tenant fleet — `for` statements AND comprehensions.

    A loop qualifies if its target binds `artist_id` (the original rule, kept), if it
    iterates a call to `get_active_artists` whatever it names the variable, or if it
    iterates a VARIABLE that was bound to such a call earlier in the module.
    """
    fleet_names = _fleet_bound_names(tree)

    def _iterates(iter_node) -> bool:
        if _iterates_the_fleet(iter_node):
            return True
        return any(isinstance(n, ast.Name) and n.id in fleet_names
                   for n in ast.walk(iter_node))

    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            names = {n.id for n in ast.walk(node.target) if isinstance(n, ast.Name)}
            if "artist_id" in names or _iterates(node.iter):
                yield node
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp,
                               ast.GeneratorExp)):
            if any(_iterates(g.iter) for g in node.generators):
                yield node


def _body_nodes(loop):
    """Every node in the loop's body — statements for a `for`, the element+conditions
    for a comprehension (which has no body, and that is exactly the point: a
    comprehension CANNOT contain a try, so one that touches `db` is unisolated by
    construction)."""
    if isinstance(loop, ast.For):
        return list(ast.walk(ast.Module(body=loop.body, type_ignores=[])))
    parts = [loop.elt] if hasattr(loop, "elt") else []
    if isinstance(loop, ast.DictComp):
        parts = [loop.key, loop.value]
    for gen in loop.generators:
        parts.extend(gen.ifs)
    return [n for part in parts for n in ast.walk(part)]


def _has_try(loop) -> bool:
    """True if the loop body contains a Try (per-iteration isolation).

    Always False for a comprehension: Python has no syntax for a try inside one, so
    a comprehension over the fleet that touches `db` can only be made safe by being
    rewritten as a statement loop.
    """
    return any(isinstance(n, ast.Try) for n in _body_nodes(loop))


# ── Les frontières d'E/S qui LÈVENT, et le test qui empêche cette liste de pourrir ──
#
# ⚠️ C'est le PREMIER aveuglement mesuré de ce fichier, le 2026-09-17. Le prédicat
# d'origine demandait « le corps référence-t-il le symbole `db` ? », et sa docstring
# AFFIRMAIT que les boucles sans `db` « can't fail per-tenant and need no isolation ».
# C'est faux : `load_platform_credentials` ouvre sa PROPRE connexion
# (`credential_loader._connect`) et lève `CredentialLoadError` — elle ne mentionne
# jamais `db`. Huit sites vivaient sous ce garde vert, dont deux dans des precheck qui
# bloquent la collecte de TOUTE la flotte par `all_success`.
#
# Un ensemble DÉRIVÉ de « toute fonction de `src/` contenant un `raise` » a été testé
# et REJETÉ : il rend **108 fonctions**, dont `__init__`, `_build`, `_call`, et des
# validateurs Pydantic qui n'ouvrent aucune connexion. Un garde qui rougit sur du code
# pur se fait contourner, et ce dépôt a mesuré ce mode d'échec.
#
# La liste est donc COURTE et volontairement limitée aux frontières d'E/S — mais elle
# ne peut pas devenir le prochain `pkill`/`pgrep` : `test_the_io_boundary_list_is_complete`
# échoue si une fonction de ces deux modules se met à lever sans y être inscrite.
_IO_BOUNDARY_MODULES = ("src/utils/credential_loader.py", "src/utils/pg_connect.py")
_RAISING_IO_BOUNDARIES = frozenset({
    "load_platform_credentials",   # CredentialLoadError — le magasin est illisible
    "get_active_artists",          # même module, même mode d'échec
    "resolve_kwargs",              # pg_connect — configuration de connexion absente
})


def _raising_functions_of(rel: str) -> set[str]:
    """Les fonctions de ce module dont le corps contient un `raise`."""
    path = Path(__file__).resolve().parent.parent / rel
    if not path.exists():
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(isinstance(x, ast.Raise) for x in ast.walk(n))}


def test_the_io_boundary_list_is_complete() -> None:
    """La liste courte ne peut pas pourrir en silence.

    Bloquant, et posé AVANT d'élargir le prédicat : une liste tapée à la main qui n'a
    pas de test de complétude EST le défaut `a-textual-guard-is-blind`. Si quelqu'un
    ajoute un lecteur qui lève dans l'un de ces deux modules, ce test le dit.
    """
    manquantes = set()
    for rel in _IO_BOUNDARY_MODULES:
        manquantes |= _raising_functions_of(rel) - _RAISING_IO_BOUNDARIES
    assert not manquantes, (
        "des frontières d'E/S lèvent sans être dans `_RAISING_IO_BOUNDARIES` : "
        f"{sorted(manquantes)}.\n"
        "Les ajouter à la liste, ou expliquer ici pourquoi elles ne peuvent pas être "
        "appelées dans une boucle de flotte. Une liste sans ce test est un garde aveugle.")


def test_the_io_boundary_list_names_something_real() -> None:
    """Anti-vacuité : une liste qui ne désigne aucune fonction existante ne garde rien."""
    reelles = set()
    for rel in _IO_BOUNDARY_MODULES:
        reelles |= _raising_functions_of(rel)
    assert _RAISING_IO_BOUNDARIES & reelles, (
        "aucun nom de `_RAISING_IO_BOUNDARIES` n'existe dans les modules scrutés — "
        "la liste a été vidée, ou les modules ont été renommés")


def _risky_calls(loop) -> list[tuple[str, int]]:
    """Les appels du corps qui peuvent LEVER par locataire, avec leur ligne.

    Deux sources, et la seconde est celle qui manquait :
      * le symbole `db` — la règle d'origine, conservée telle quelle ;
      * un appel à une frontière d'E/S qui lève, `db` ou pas.
    """
    out: list[tuple[str, int]] = []
    for n in _body_nodes(loop):
        if isinstance(n, ast.Name) and n.id == "db":
            out.append(("db", n.lineno))
        elif isinstance(n, ast.Call):
            name = getattr(n.func, "attr", None) or getattr(n.func, "id", "")
            if name in _RAISING_IO_BOUNDARIES:
                out.append((name, n.lineno))
    return out


def _unprotected_calls(loop) -> list[tuple[str, int]]:
    """Les appels risqués qui ne sont DANS aucun `try` de la boucle.

    ⚠️ DEUXIÈME aveuglement mesuré le 2026-09-17. `_has_try` demandait « y a-t-il UN
    `try` quelque part dans le corps ? ». Quatre boucles en avaient un — qui commençait
    24 à 46 lignes APRÈS l'appel risqué. Un `try` présent n'isole que ce qu'il contient ;
    la question est la PORTÉE, pas la présence.

    Une compréhension n'a aucun `try` possible : tout appel risqué y est donc nu par
    construction, ce que `_body_nodes` et l'absence de `ast.Try` rendent automatiquement.
    """
    spans = [(n.lineno, n.end_lineno) for n in _body_nodes(loop) if isinstance(n, ast.Try)]
    return [(name, line) for name, line in _risky_calls(loop)
            if not any(a <= line <= b for a, b in spans)]


_DAG_FILES = sorted(_DAGS_DIR.glob("*.py"))


@pytest.mark.parametrize("dag_file", _DAG_FILES, ids=lambda p: p.name)
def test_artist_loops_are_isolated(dag_file):
    tree = ast.parse(dag_file.read_text(encoding="utf-8-sig"))
    violations = []
    for loop in _artist_loops(tree):
        for name, line in _unprotected_calls(loop):
            kind = ("compréhension — aucun `try` n'y est possible, la réécrire en boucle"
                    if not isinstance(loop, ast.For) else "hors de tout `try` de la boucle")
            violations.append(
                f"{dag_file.name}:{line} — `{name}` peut lever par locataire, {kind} "
                f"(boucle l.{loop.lineno})")
    assert not violations, (
        "Fleet-poisoning risk — un appel qui LÈVE par locataire doit être DANS le "
        "`try/except-continue` de son itération, sinon un seul locataire fautif fait "
        "tomber le DAG pour toute la flotte (voir youtube_daily.py / soundcloud_daily.py)"
        ":\n  " + "\n  ".join(violations)
    )


# Les trois formes qui ont RÉELLEMENT échappé au garde le 2026-09-17, en source
# synthétique. Chacune correspond à un aveuglement mesuré, et à des sites de production.
_SOURCE_FLEET_BOUND_TO_A_NAME = (
    "artists = get_active_artists()\n"
    "for aid, name in artists:\n"
    "    creds = load_platform_credentials(aid, 'meta')\n"
)
_SOURCE_TRY_STARTS_BELOW_THE_CALL = (
    "for aid, name in get_active_artists():\n"
    "    creds = load_platform_credentials(aid, 'meta')\n"
    "    try:\n"
    "        collect(aid)\n"
    "    except Exception:\n"
    "        continue\n"
)
_SOURCE_COMPREHENSION = (
    "artists = get_active_artists()\n"
    "ok = [n for a, n in artists if load_platform_credentials(a, 'meta').get('x')]\n"
)
_SOURCE_CORRECTED = (
    "artists = get_active_artists()\n"
    "for aid, name in artists:\n"
    "    try:\n"
    "        creds = load_platform_credentials(aid, 'meta')\n"
    "    except Exception:\n"
    "        continue\n"
)


@pytest.mark.parametrize("libelle,source", [
    ("source de flotte liée à une variable", _SOURCE_FLEET_BOUND_TO_A_NAME),
    ("appel risqué au-dessus d'un `try` présent plus bas", _SOURCE_TRY_STARTS_BELOW_THE_CALL),
    ("compréhension sur la flotte", _SOURCE_COMPREHENSION),
])
def test_the_detector_sees_the_forms_it_was_written_for(libelle, source) -> None:
    """Anti-vacuité, sur les TROIS aveuglements mesurés le 2026-09-17.

    Chacun a laissé passer des sites de production réels ; chacun a ici sa source.
    """
    nus = [c for loop in _artist_loops(ast.parse(source)) for c in _unprotected_calls(loop)]
    assert nus, f"le détecteur ne voit pas : {libelle}"


def test_the_corrected_form_is_not_a_false_positive() -> None:
    """Et il ne rougit pas sur la forme CORRIGÉE — sinon il serait contourné."""
    nus = [c for loop in _artist_loops(ast.parse(_SOURCE_CORRECTED))
           for c in _unprotected_calls(loop)]
    assert not nus, f"faux positif sur la forme corrigée : {nus}"


def test_the_detector_sees_the_form_this_repo_actually_writes() -> None:
    """Non-vacuité, sur la forme qui a produit le TROISIÈME aveuglement de ce fichier.

    Ajouté le 2026-09-18. Un garde de balayage reste vert tant qu'aucun DAG ne viole
    la règle — donc, s'il est aveugle, exactement aussi vert. La forme fabriquée ici
    est celle que le dépôt écrit réellement : l'appel de flotte est affecté à une
    variable, puis la boucle itère cette variable. C'est précisément ce que la version
    « appel INLINE dans l'itérateur » ne voyait pas.
    """
    reel = ast.parse(
        "def collect():\n"
        "    artists = get_active_artists()\n"
        "    for artist_id, name in artists:\n"
        "        pass\n"
    )
    assert "artists" in _fleet_bound_names(reel), (
        "une variable liée au RÉSULTAT d'un appel de flotte n'est plus reconnue : le "
        "garde revient à n'accepter que l'appel inline, et les boucles réelles de ce "
        "dépôt lui échappent toutes.")

    sans = ast.parse(
        "def collect():\n"
        "    artists = [1, 2, 3]\n"
        "    for a in artists:\n"
        "        pass\n"
    )
    assert "artists" not in _fleet_bound_names(sans), (
        "une liste littérale est prise pour la flotte : le garde mordrait sur du code "
        "qui n'itère aucun locataire.")
