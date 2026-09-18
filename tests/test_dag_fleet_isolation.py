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


# ── La flotte s'énumère aussi en SQL, et c'était le QUATRIÈME aveuglement ──────
#
# Mesuré le 2026-09-18, en mutant le garde élargi : DEUX des trois sites que je venais de
# corriger restaient invisibles. Remettre le défaut dans `src/utils/metric_bounds.py` ne
# faisait PAS rougir le test.
#
# La cause est celle de la règle 20 : le prédicat cherchait une FORME D'ÉCRITURE — un
# appel nommé `get_active_artists` — là où la classe parle d'une PROPRIÉTÉ : « cette
# boucle parcourt-elle la flotte ». Les deux sites énumèrent leurs locataires en SQL :
#
#     tenants = [r[0] for r in db.fetch_query(
#         "SELECT DISTINCT artist_id FROM s4a_song_timeline …")]   # metric_bounds
#     df = db.fetch_df("SELECT id, name FROM saas_artists WHERE active = TRUE …")
#     artists = [(int(r["id"]), r["name"]) for _, r in df.iterrows()]  # onboarding_health
#
# La preuve qu'une variable porte la flotte n'est donc pas le nom de l'appel : c'est le
# TEXTE de la requête qui l'a produite. On sème sur ce texte, puis on propage par
# affectation jusqu'au point fixe — `df` → `artists` est exactement le cas qui manquait.
_TENANT_QUERY_MARKS = ("from saas_artists", "distinct artist_id")


def _assigns_of_scope(scope: ast.AST):
    """Les affectations de CETTE portée, sans descendre dans les fonctions imbriquées.

    ⚠️ La première version propageait à l'échelle du MODULE, et la mutation l'a montrée
    fausse tout de suite : un `rows` lié à la flotte dans une fonction rendait « flotte »
    le `rows` de toutes les autres. Deux faux positifs mesurés —
    `pdf_exporter/_collectors.py:229` (une boucle sur les TITRES d'un seul artiste) et
    `alert_monitor.py:692` (le canari, qui ne regarde qu'un locataire). Un garde qui
    rougit sur du code correct se fait désarmer ; c'est le mode d'échec que ce dépôt a
    déjà payé sur la liste dérivée de « toute fonction contenant un raise » (108 hits).
    """
    corps = scope.body if hasattr(scope, "body") else []
    sorties = []
    pile = list(corps)
    while pile:
        n = pile.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue                       # une autre portée : ses noms ne fuient pas ici
        if isinstance(n, ast.Assign):
            sorties.append(n)
        pile.extend(ast.iter_child_nodes(n))
    return sorties


def _tenant_bound_names(tree: ast.AST) -> set[str]:
    """Les variables de CETTE portée qui portent une énumération de locataires."""
    def _enumere(node) -> bool:
        if _iterates_the_fleet(node):
            return True
        return any(isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and any(m in n.value.lower() for m in _TENANT_QUERY_MARKS)
                   for n in ast.walk(node))

    assigns = [(n.targets, n.value) for n in _assigns_of_scope(tree)]
    bound: set[str] = set()
    for _ in range(len(assigns) + 1):      # point fixe, borné par le nombre d'affectations
        avant = len(bound)
        for targets, value in assigns:
            derive = _enumere(value) or any(
                isinstance(n, ast.Name) and n.id in bound for n in ast.walk(value))
            if derive:
                for t in targets:
                    bound |= {n.id for n in ast.walk(t) if isinstance(n, ast.Name)}
        if len(bound) == avant:
            break
    return bound


def _artist_loops(tree: ast.AST):
    """Yield every loop over the tenant fleet — `for` statements AND comprehensions.

    A loop qualifies if its target binds `artist_id` (the original rule, kept), if it
    iterates a call to `get_active_artists` whatever it names the variable, or if it
    iterates a VARIABLE that was bound to such a call earlier in the module.
    """
    fleet_names = _fleet_bound_names(tree) | _tenant_bound_names(tree)
    par_portee = {id(sc): fleet_names | _tenant_bound_names(sc)
                  for sc in ast.walk(tree)
                  if isinstance(sc, (ast.FunctionDef, ast.AsyncFunctionDef))}
    proprietaire = {}
    for sc in ast.walk(tree):
        if isinstance(sc, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(sc):
                proprietaire.setdefault(id(n), id(sc))

    def _iterates(iter_node, loop=None) -> bool:
        if _iterates_the_fleet(iter_node):
            return True
        noms = par_portee.get(proprietaire.get(id(loop if loop is not None else iter_node)),
                              fleet_names)
        return any(isinstance(n, ast.Name) and n.id in noms
                   for n in ast.walk(iter_node))

    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            names = {n.id for n in ast.walk(node.target) if isinstance(n, ast.Name)}
            if "artist_id" in names or _iterates(node.iter, node):
                yield node
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp,
                               ast.GeneratorExp)):
            if any(_iterates(g.iter, node) for g in node.generators):
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

# ── La flotte ne vit pas QUE dans `airflow/dags/` — 2026-09-18 (R132) ────────
#
# Le balayage du 2026-09-17 a corrigé 8 sites dans `airflow/dags/` et en a laissé
# **6 hors périmètre**, documentés et non corrigés. Deux d'entre eux étaient de vraies
# pannes de flotte :
#
#   * `src/utils/metric_bounds.py:124` — la boucle de `check_metric_bounds`, une tâche du
#     DAG de surveillance NOCTURNE. Un locataire illisible tuait la tâche entière, donc le
#     contrôle devenait aveugle pour toute la flotte — et son silence se lit comme
#     « rien à signaler ».
#   * `src/dashboard/views/onboarding_health.py:65` — un artiste dont la lecture lève
#     emportait TOUTE la page de supervision.
#
# ⚠️ **Et `metric_bounds` a quitté ce garde le jour où il est devenu plus facile à
# tester.** La boucle a été SORTIE d'`alert_monitor.py` vers `src/utils/` le 2026-09-12,
# « pour qu'un contrôle enfermé dans un DAG soit exerçable sans Airflow ». Le garde, lui,
# ne parcourait que `airflow/dags/`. Un déplacement qui améliore la testabilité peut faire
# sortir le code d'un garde — et rien ne le dit.
#
# ── L'entonnoir, contredisable (règle 20) ─────────────────────────────────────
#
#   candidats bruts, une fois le prédicat élargi aux énumérations SQL : **6**
#   écartés, avec leur raison :
#     · `pdf_exporter/_collectors.py:229,236` — boucle sur les TITRES d'UN artiste ;
#       faux positif de ma propre propagation, aveugle aux portées (corrigé)
#     · `alert_monitor.py:692` — le canari ne regarde qu'un locataire ; même cause
#     · `airflow/debug_dag/` (4 fichiers, 8 appels) — scripts lancés À LA MAIN. Le
#       traceback y EST la sortie attendue : un `try` par locataire masquerait
#       précisément ce que l'opérateur est venu voir, et personne n'attend de ces
#       scripts une couverture de flotte. Écartés sur la CONSÉQUENCE, pas sur la forme.
#   **2 sites vivants** — `onboarding_health.py:92` (le rendu lit la base hors du
#   `try`) et `tools/metric_check.py:44,45` (le jumeau CLI de `metric_bounds`).
#   Les deux corrigés le 2026-09-18.
#
# Mesuré après correction : `src/` **0**, `tools/` **0**, `.claude/scripts/` **0**,
# `airflow/dags/` **0** (le prédicat élargi n'y ajoute aucun rouge).
_AUTRES_ARBRES = ("src", "tools", ".claude/scripts")
_FLEET_FILES = sorted(
    f for arbre in _AUTRES_ARBRES
    for f in (Path(__file__).resolve().parent.parent / arbre).rglob("*.py")
    if "__pycache__" not in str(f)
)

# Les fichiers dont on SAIT qu'ils portent une boucle de flotte, parce qu'ils ont été
# corrigés à la main le 2026-09-18. Le test ci-dessous exige que le prédicat les VOIE.
_PORTENT_UNE_BOUCLE_DE_FLOTTE = (
    "src/utils/metric_bounds.py",
    "src/dashboard/views/onboarding_health.py",
    "tools/tenant_contamination_check.py",
    "tools/metric_check.py",
)


def test_the_wider_scope_is_not_empty() -> None:
    """Sans fichiers, le test de flotte ci-dessous est vert sur un arbre entièrement cassé."""
    assert len(_FLEET_FILES) > 100, (
        f"seulement {len(_FLEET_FILES)} fichier(s) hors `airflow/dags/` — la liste a raté "
        "sa cible, et `test_fleet_loops_outside_the_dags_are_isolated` n'affirme rien.")


@pytest.mark.parametrize("rel", _PORTENT_UNE_BOUCLE_DE_FLOTTE)
def test_the_widened_scope_is_not_vacant(rel: str) -> None:
    """Élargir la PORTÉE ne sert à rien si le PRÉDICAT ne voit pas les fichiers ajoutés.

    ⚠️ C'est le défaut mesuré le 2026-09-18, et il serait passé sans la mutation.
    Après avoir corrigé trois boucles de flotte à la main, j'ai étendu ce fichier de
    `airflow/dags/` à `src/`, `tools/` et `.claude/scripts/`, mesuré **0 site partout**,
    et conclu que l'élargissement verrouillait les trois corrections. Puis j'ai remis le
    défaut dans `metric_bounds.py` : **le test est resté VERT**. `_artist_loops` ne
    reconnaissait la flotte que sur un appel nommé `get_active_artists` ; deux des trois
    fichiers énumèrent leurs locataires en SQL, donc le garde ne les REGARDAIT pas.

    Un « 0 » peut vouloir dire « rien à signaler » ou « je n'ai rien regardé », et rien
    dans le chiffre ne permet de trancher. Ce test rend les deux distinguables : il
    échoue si le prédicat cesse de voir une boucle qu'on sait présente — par un
    renommage, une réécriture de la requête d'énumération, ou une restriction de portée.
    """
    chemin = Path(__file__).resolve().parent.parent / rel
    if not chemin.exists():
        pytest.skip(f"{rel} n'existe plus")
    tree = ast.parse(chemin.read_text(encoding="utf-8-sig"))
    assert list(_artist_loops(tree)), (
        f"`{rel}` porte une boucle par locataire corrigée à la main, et `_artist_loops` "
        "n'en voit AUCUNE. Le fichier est bien dans la portée du garde, mais le garde "
        "n'affirme rien à son sujet : remettre le défaut ne le ferait pas rougir.\n"
        "C'est la forme de vacance la plus coûteuse, parce qu'elle se lit comme une "
        "couverture acquise.")


@pytest.mark.parametrize("fichier", _FLEET_FILES, ids=lambda p: p.name)
def test_fleet_loops_outside_the_dags_are_isolated(fichier):
    """Le MÊME détecteur, sur les arbres où la flotte vit aussi.

    Seule sa PORTÉE était le défaut — puis, mesuré le même jour, son PRÉDICAT aussi.
    C'est le motif de la nuit : sur treize familles balayées, aucun garde vert ne
    mentait ; ils lisaient une surface qui n'était pas celle où le défaut vivait.
    """
    tree = ast.parse(fichier.read_text(encoding="utf-8-sig"))
    violations = []
    for loop in _artist_loops(tree):
        for name, line in _unprotected_calls(loop):
            kind = ("compréhension — aucun `try` n'y est possible, la réécrire en boucle"
                    if not isinstance(loop, ast.For) else "hors de tout `try` de la boucle")
            violations.append(
                f"{fichier.name}:{line} — `{name}` peut lever par locataire, {kind} "
                f"(boucle l.{loop.lineno})")
    assert not violations, (
        "\n".join(violations) + "\n\nUne boucle de flotte sans `try` par locataire fait "
        "d'un artiste cassé une panne pour TOUS. Ici, hors d'Airflow, la conséquence n'est "
        "pas un DAG bloqué mais un contrôle AVEUGLE ou une page vide — et le silence se "
        "lit comme « rien à signaler ».\nIsoler ne veut pas dire taire : le locataire non "
        "lu doit apparaître dans la sortie, comme le fait `metric_bounds` avec sa ligne "
        "« lecture impossible » et `tenant_contamination_check` avec son constat "
        "`UNREADABLE`.")


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
