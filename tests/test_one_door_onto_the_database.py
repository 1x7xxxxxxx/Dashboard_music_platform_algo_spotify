"""One place decides how to reach the database. Everything else asks it.

Installed 2026-08-22. `src/dashboard/utils/get_db_connection` restated the precedence
as `DATABASE_URL → config.yaml` and skipped the middle step, while
`pg_connect.resolve_kwargs` reads `DATABASE_HOST → config.yaml` and never looks at
`DATABASE_URL`.

Measured in production the same day:

    streamlytics_dashboard / streamlytics_api : DATABASE_URL only
    airflow_scheduler                          : DATABASE_HOST / NAME / USER only
    every container                            : no config.yaml at all

So the two halves of one product reached one database through two mechanisms, and
neither worked in the other's place. Setting `DATABASE_HOST` on the dashboard, or
`DATABASE_URL` on the scheduler, breaks that half in silence — the dashboard falling
through to a `config.yaml` that is not there.

`PostgresHandler.from_env_or_config()` already knows all three sources; it was written
on 2026-08-21 for this exact reason, and its docstring already described the
asymmetry. This file stops a fourth copy appearing.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The one implementation, plus the module it delegates to.
_ALLOWED_TO_RESOLVE = {
    REPO / "src" / "database" / "postgres_handler.py",
    REPO / "src" / "utils" / "pg_connect.py",
}
# ⚠️ `airflow/debug_dag/` a ete AJOUTE ici le 2026-09-17, puis RETIRE le meme jour.
# Les douze scripts y construisaient bien un `PostgresHandler` a la main — c'est
# corrige, ils passent tous par la porte. Mais ce qu'ils LISENT encore n'est pas une
# resolution : `debug_alert_monitor` fait `os.environ.setdefault('DATABASE_HOST', …)`
# depuis `config.yaml` pour ALIMENTER le resolveur partage quand on lance un DAG hors
# Docker, et `debug_s4a` liste les noms de variables pour dire lesquelles manquent.
# Nourrir la porte et diagnostiquer son absence ne sont pas inventer une precedence.
# Les garder dans le balayage aurait rendu neuf faux positifs permanents — et un garde
# bruyant se fait desactiver, ce qui coute plus cher que le trou qu'il couvrait.
_SCANNED_TREES = [REPO / "src", REPO / "airflow" / "dags", REPO / "tools"]
_DSN_VARS = {"DATABASE_URL", "DATABASE_HOST", "DATABASE_PORT",
             "DATABASE_NAME", "DATABASE_USER", "DATABASE_PASSWORD"}


def _modules_reading_dsn_env() -> dict:
    """{path: [vars]} for every module that reads a DSN variable itself."""
    out: dict[str, list[str]] = {}
    for tree_root in _SCANNED_TREES:
        for path in sorted(tree_root.rglob("*.py")):
            if path in _ALLOWED_TO_RESOLVE:
                continue
            try:
                found = dsn_reads(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            if found:
                out[str(path.relative_to(REPO))] = found
    return out


def dsn_reads(source: str) -> list[str]:
    """`VAR:line` for every DSN variable a module names itself. Pure."""
    return [f"{n.value}:{n.lineno}" for n in ast.walk(ast.parse(source))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value in _DSN_VARS]


def test_the_dashboard_uses_the_shared_door():
    """The specific regression: the dashboard's own precedence, missing a step."""
    door = REPO / "src" / "dashboard" / "utils" / "__init__.py"
    src = door.read_text("utf-8")
    # ⚠️ READ THE CALL, NOT THE FILE. Until 2026-09-18 this was
    # `assert "from_env_or_config()" in src`, and the file NAMES that method twice
    # more — once in a module comment, once in the docstring of this very function.
    # Replacing the delegation with a hand-built DSN
    # (`PostgresHandler(host=os.getenv('DB_HOST'))`) left all five tests GREEN, which
    # is precisely the second precedence this class exists to forbid. Error class
    # `guard-satisfied-by-its-own-comment`.
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "get_db_connection"), None)
    assert fn is not None, "get_db_connection has disappeared from the shared door"
    delegates = [n for n in ast.walk(fn)
                 if isinstance(n, ast.Call)
                 and ast.unparse(n.func).endswith("from_env_or_config")]
    assert delegates, (
        "get_db_connection no longer CALLS PostgresHandler.from_env_or_config (it may "
        "still name it in a comment) — whatever it does instead is a second "
        "precedence, and the last one omitted DATABASE_HOST, which is the only thing "
        "Airflow has"
    )
    assert "config_loader.load()" not in src, (
        "the config.yaml fallback is back in the dashboard; it belongs in the one "
        "resolver"
    )


def test_no_new_module_resolves_the_database_itself():
    """A ratchet, not a ban: the known readers are listed, growth fails.

    Some entries below are legitimate — a DAG passing DATABASE_* through to a
    container, a tool printing which source it used. What must not happen is a NEW
    module quietly inventing a fourth precedence.
    """
    # The measured state on 2026-08-22 — 14 modules, all pre-existing. This is a
    # RATCHET, deliberately not a ban: rewriting fourteen DAGs was not the ask, and
    # each of these reads the Airflow container's own env, which is legitimate where
    # it happens. What must not happen is a FIFTEENTH module quietly inventing
    # another precedence.
    #
    # The list may shrink, never grow. Removing an entry as it is migrated is the
    # intended direction of travel.
    known = {
        "src/api/main.py",
        "src/dashboard/utils/usage_tracker.py",
        "airflow/dags/alert_monitor.py",
        "airflow/dags/data_quality_check.py",
        "airflow/dags/ml_outcome_labeling.py",
        "airflow/dags/ml_scoring_daily.py",
        "airflow/dags/onboarding_report.py",
        "airflow/dags/spotify_api_daily.py",
        "airflow/dags/weekly_digest.py",
        "airflow/dags/youtube_daily.py",
    }
    offenders = sorted(set(_modules_reading_dsn_env()) - known)
    assert not offenders, (
        "module(s) de test ouvrant une connexion depuis des variables de DSN, "
        "sans passer par `tests/db_gate.dsn()` :\n  " + "\n  ".join(offenders)
        + "\n\nCes modules skippent sans base et ERREURENT avec une base dont le "
          "mot de passe vit dans config.yaml. Remplacer le corps de `_dsn()` par "
          "`from tests.db_gate import dsn; return dsn()`."
    )


def test_the_known_list_has_not_rotted():
    """An entry for a module that no longer reads a DSN var hides the next one.

    Same reasoning as the acknowledged-red list on the external health probe: a
    stale exemption is an exemption nobody re-examines.
    """
    reading = set(_modules_reading_dsn_env())
    known = {"src/api/main.py"}
    stale = sorted(known - reading)
    assert not stale, (
        f"{stale} no longer read a DSN variable — remove them from the ratchet so it "
        "keeps measuring something"
    )


def test_the_sweep_can_see_a_direct_read():
    """Non-vacuity: prove the AST walk recognises the shape it forbids."""
    # The sweep's OWN predicate — this proof walked the AST with a copy of the rule
    # until 2026-09-26 (class `a-proof-that-tests-a-copy-of-its-detector`).
    assert dsn_reads('import os\nx = os.getenv("DATABASE_HOST")\n') == ["DATABASE_HOST:2"], (
        "the walk does not see a DSN variable — it guards nothing")
    assert dsn_reads("from src.database.connection import dsn\nx = dsn()\n") == []


def test_the_shared_door_still_knows_all_three_sources():
    src = (REPO / "src" / "database" / "postgres_handler.py").read_text("utf-8")
    fn = src[src.index("def from_env_or_config"):]
    fn = fn[:fn.index("\n    def ")]
    assert "DATABASE_URL" in fn and "resolve_kwargs" in fn, (
        "the shared resolver lost a source; every caller now inherits that gap"
    )


# ──────────────────────────────────────────────────────────────────────────────
# La SUITE elle-même — ajouté le 2026-09-22
#
# Ce fichier gardait `src/`, `airflow/dags/` et `tools/`, et pas `tests/`. Vingt
# tests sont devenus rouges le même jour, tous sur `fe_sendauth: no password
# supplied`, et aucun n'avait de rapport avec le changement en cours : douze
# modules de test construisaient leur DSN à la main, en ne lisant QUE
# l'environnement. Sur un poste dont le mot de passe vit dans `config/config.yaml`,
# la socket s'ouvre et l'authentification échoue.
#
# Le symptôme est traître dans les deux sens : sans base, ces modules skippent
# proprement ; avec une base, ils ERREURENT. Un développeur qui démarre sa pile
# voit donc vingt rouges apparaître sans avoir touché à rien — et le docstring de
# `from_env_or_config` décrivait DÉJÀ ce défaut chez trois collecteurs, sans que
# personne pense à le chercher côté tests.
#
# Classe : `a-second-door-that-knows-fewer-sources-than-the-first`.
# ──────────────────────────────────────────────────────────────────────────────

_PORTES_PARTAGEES = {"dsn", "resolve_kwargs", "from_env_or_config"}


def _passe_par_la_porte(tree) -> bool:
    """Le module IMPORTE-t-il vraiment une porte partagée ?

    ⚠️ La première version cherchait `resolve_kwargs|from tests.db_gate import`
    dans le TEXTE du fichier, et la mutation du 2026-09-22 ne l'a pas fait rougir :
    la docstring que je venais d'écrire dans les neuf modules corrigés CITE
    `resolve_kwargs`. Le garde se satisfaisait donc de la prose qui décrit le fix,
    pendant que le code portait de nouveau le défaut.

    C'est `a-textual-guard-that-matches-its-own-prose`, mesuré quatre fois en une
    soirée sur ce dépôt le 2026-08-22. On lit l'AST : un `import`, jamais un mot.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if any(a.name in _PORTES_PARTAGEES for a in node.names):
                return True
        elif isinstance(node, ast.Attribute) and node.attr in _PORTES_PARTAGEES:
            return True
    return False


def _tests_connecting_without_the_door() -> list[str]:
    """Les modules de test qui SE CONNECTENT depuis des variables, sans la porte.

    La propriété n'est pas « lire une variable de DSN » — vingt-cinq modules le
    font, dont celui-ci et `test_pg_connect`, qui testent le résolveur. C'est
    « ouvrir une connexion » à partir de ces variables **et** ignorer la porte.
    """
    out = []
    moi = Path(__file__).resolve()
    for path in sorted((REPO / "tests").rglob("*.py")):
        if path.name == "db_gate.py" or path.resolve() == moi:
            continue
        txt = path.read_text(encoding="utf-8")
        # Une connexion s'ouvre par `psycopg2.connect` OU par `PostgresHandler(**…)`.
        # Filtrer sur le premier seul laissait passer
        # `tests/test_every_way_of_asking_gives_one_answer.py`, qui composait son DSN
        # depuis l'environnement et ouvrait par le second — rouge EN LOCAL (le mot de
        # passe vit dans `config.yaml`), vu le 2026-09-24 par un balayage, pas par ce
        # garde.
        if "psycopg2.connect" not in txt and "PostgresHandler(" not in txt:
            continue
        try:
            tree = ast.parse(txt)
        except SyntaxError:
            continue
        # ⚠️ LE COMPOSÉ SUR PLACE SE JUGE AVANT L'EXEMPTION DE MODULE, et je l'ai
        # découvert en mutant. `_passe_par_la_porte` court-circuite le module ENTIER dès
        # qu'il IMPORTE un nom de porte quelque part. Un module qui importe `dsn()` pour
        # une sonde et recompose son DSN dix lignes plus bas lui était donc invisible —
        # ma mutation du 2026-09-22 a remis un `psycopg2.connect(host=…, password=…)` en
        # dur et le garde est resté **VERT**. Importer la porte prouve quelque chose du
        # MODULE ; ça ne prouve rien de CET appel-là.
        if _compose_son_dsn(tree):
            out.append(str(path.relative_to(REPO)))
            continue
        if _passe_par_la_porte(tree):
            continue
        # LA PROPRIÉTÉ EST « LIRE », PAS « NOMMER » — et la distinction a coûté un
        # faux positif au premier jet. `test_credential_loader` porte les cinq noms
        # dans un `assert var not in code` : c'est un GARDE qui vérifie leur
        # absence, exactement l'inverse du défaut. On exige donc que le nom soit
        # l'argument d'un `os.environ.get(...)` / `os.getenv(...)`, pas un littéral
        # quelque part dans le fichier.
        if any(_lit_une_variable(n) for n in ast.walk(tree)):
            out.append(str(path.relative_to(REPO)))
    return out


def _compose_son_dsn(tree) -> bool:
    """LA PROPRIÉTÉ, là où `_lit_une_variable` ne tient qu'une LISTE DE NOMS.

    ⚠️ Ajouté le 2026-09-22, après un TREIZIÈME site passé au travers du cliquet à
    zéro. `_DSN_VARS` énumère six noms `DATABASE_*` ;
    `tests/test_an_erasure_receipt_tells_failure_from_absence.py:135` composait sa
    connexion avec `password=os.getenv("DB_PASSWORD", <valeur par défaut>)` — **toute la famille
    `DB_*` était invisible**, et un mot de passe écrit en clair l'aurait été aussi.

    Une liste de noms est une FORME ; « ce module compose-t-il lui-même son DSN » est la
    PROPRIÉTÉ, et elle se lit sans connaître aucun nom de variable : un
    `psycopg2.connect(...)` dont les arguments de connexion sont passés en MOTS-CLEFS
    sur place. La porte partagée se passe en `**dsn()`, donc elle n'en porte aucun.

    Entonnoir mesuré le jour même sur `tests/` : **15 appels** `psycopg2.connect`,
    **14 écartés** — tous en `**kw` venu d'un résolveur — **1 site vivant**, celui-ci.

    ⚠️ Ce qu'il ne tient PAS : un DSN composé dans une VARIABLE puis déballé
    (`kw = {"host": …}; connect(**kw)`). La forme n'existe pas aujourd'hui dans ce
    dépôt ; `_lit_une_variable` l'attraperait si elle lisait un nom connu, et rien
    sinon.
    """
    kw_dsn = {"host", "port", "dbname", "database", "user", "password"}
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if not (getattr(f, "attr", None) == "connect"
                and getattr(getattr(f, "value", None), "id", None) == "psycopg2"):
            continue
        if {k.arg for k in n.keywords if k.arg} & kw_dsn:
            return True
    return False


def _lit_une_variable(node) -> bool:
    """Vrai si `node` est un `os.environ.get("DATABASE_…")` ou `os.getenv(…)`."""
    if not isinstance(node, ast.Call) or not node.args:
        return False
    cible = node.func
    nom = getattr(cible, "attr", None) or getattr(cible, "id", None)
    if nom not in {"get", "getenv", "environ"}:
        return False
    premier = node.args[0]
    return (isinstance(premier, ast.Constant) and isinstance(premier.value, str)
            and premier.value in _DSN_VARS)


def test_no_test_module_opens_its_own_door():
    """Un cliquet à ZÉRO : les douze sont corrigés, aucun treizième."""
    offenders = _tests_connecting_without_the_door()
    assert not offenders, (
        "module(s) de test ouvrant une connexion depuis des variables de DSN, sans "
        "passer par `tests/db_gate.dsn()` : " + ", ".join(offenders)
        + ". Ces modules skippent sans base et ERREURENT avec une base dont le mot "
          "de passe vit dans config.yaml. Remplacer le corps de `_dsn()` par "
          "`from tests.db_gate import dsn; return dsn()`."
    )


def test_the_test_sweep_sees_the_modules_that_connect():
    """Anti-vacuité : un balayage qui ne trouve plus personne garde zéro.

    Douze modules de test ouvrent une connexion Postgres. Si ce nombre tombe sous
    huit, c'est le PRÉDICAT qui a cessé de voir, pas la suite qui s'est simplifiée.
    """
    qui_se_connectent = [
        p for p in (REPO / "tests").rglob("*.py")
        if "psycopg2.connect" in p.read_text(encoding="utf-8")
    ]
    assert len(qui_se_connectent) >= 8, (
        f"seulement {len(qui_se_connectent)} module(s) de test ouvrent une "
        "connexion — le balayage ne voit plus rien, son zéro ne prouve rien."
    )


def test_a_guard_that_asserts_absence_is_not_an_offender():
    """Le faux positif nommé — `test_credential_loader` VÉRIFIE cette absence.

    Il porte les cinq noms de variables dans un `assert var not in code`. Un
    prédicat qui cherche le nom plutôt que l'usage le compte comme coupable : il
    était dans les dix trouvés au premier jet, et il ne l'est plus.
    """
    assert "tests/test_credential_loader.py" not in _tests_connecting_without_the_door()


def _un_module_jetable_ouvre_sa_porte(tmp_path, source: str) -> bool:
    """Le MÊME prédicat, appliqué à un module fabriqué pour l'occasion."""
    f = tmp_path / "test_jetable.py"
    f.write_text(source, encoding="utf-8")
    if "psycopg2.connect" not in source:
        return False
    tree = ast.parse(source)
    if _passe_par_la_porte(tree):
        return False
    return any(_lit_une_variable(n) for n in ast.walk(tree))


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path):
    """Le garde se prouve lui-même — la porte maison est VUE."""
    assert _un_module_jetable_ouvre_sa_porte(tmp_path, '''
import os, psycopg2

def _dsn():
    return {"host": "localhost", "port": 5433,
            "password": os.environ.get("DATABASE_PASSWORD", "")}

def test_x():
    psycopg2.connect(**_dsn())
'''), "une porte maison lisant DATABASE_PASSWORD doit être signalée"


def test_the_shared_door_leaves_the_detector_silent(tmp_path):
    """La réciproque : sans elle, un prédicat qui dit « oui » à tout passerait."""
    assert not _un_module_jetable_ouvre_sa_porte(tmp_path, '''
import psycopg2
from tests.db_gate import dsn

def test_x():
    psycopg2.connect(**dsn())
'''), "un module qui passe par la porte partagée ne doit pas être signalé"


def test_naming_the_variable_without_reading_it_is_not_the_defect(tmp_path):
    """Le faux positif synthétique — un garde qui vérifie leur ABSENCE.

    C'est la forme exacte de `test_credential_loader.py`, comptée coupable par le
    premier prédicat parce qu'elle NOMME les variables.
    """
    assert not _un_module_jetable_ouvre_sa_porte(tmp_path, '''
import psycopg2

def test_the_module_reads_no_connection_variable():
    code = open("src/utils/credential_loader.py").read()
    for var in ("DATABASE_HOST", "DATABASE_PASSWORD"):
        assert var not in code
    assert psycopg2 is not None
'''), "nommer une variable dans une assertion d'absence n'est pas la lire"

def _handler_kwargs() -> set:
    import inspect

    from src.database.postgres_handler import PostgresHandler
    return set(inspect.signature(PostgresHandler.__init__).parameters) - {"self"}


def _the_handler_accepts(kw: dict | None) -> bool:
    """Can `PostgresHandler(**kw)` be called with what the test door returned?"""
    return bool(kw) and set(kw) <= _handler_kwargs()


def test_the_handler_check_sees_the_defect_it_is_written_for() -> None:
    """The form `tests/db_gate.dsn()` returned in CI until 2026-09-24 must be refused.

    Without this, `_the_handler_accepts` could be loosened into accepting anything and
    the door test above would stay green on the very defect that kept CI red two days.
    """
    assert not _the_handler_accepts({"dsn": "postgresql://u:p@h:5432/db"})  # pragma: allowlist secret
    assert not _the_handler_accepts({})
    assert _the_handler_accepts({"host": "h", "port": 5432, "database": "db",
                                 "user": "u", "password": "p"})  # pragma: allowlist secret


def test_the_test_door_speaks_the_handlers_language_under_DATABASE_URL(monkeypatch) -> None:
    """`dsn()` est déballé dans `PostgresHandler(**…)` ET `psycopg2.connect(**…)`.

    Sous `DATABASE_URL` (la CI) il rendait `{"dsn": url}`, que le premier refuse : dix
    tests rouges en CI du 2026-09-22 au 24, verts sur le poste qui ne pose pas la
    variable. Ne demande aucune base : la branche `DATABASE_URL` ne touche pas au réseau.
    """
    from tests.db_gate import dsn

    monkeypatch.setenv("DATABASE_URL", "postgresql://u%40x:p%3Aw@h:6543/db")  # pragma: allowlist secret
    kw = dsn()
    assert _the_handler_accepts(kw), (
        f"`dsn()` rend {sorted(kw or {})} ; `PostgresHandler` accepte {sorted(_handler_kwargs())}")
    assert (kw["user"], kw["password"], kw["port"]) == ("u@x", "p:w", 6543), (
        "les identifiants d'une URI se décodent comme le fait libpq")
