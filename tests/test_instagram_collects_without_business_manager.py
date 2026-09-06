"""Un compte Instagram déclaré collecte sans être relié à notre Business Manager.

C'est la mesure qui a justifié de rendre 📸 Instagram autonome le 2026-09-05.
Sur un compte tiers, avec notre jeton System User et AUCUN partage :

    GET /{ig_id}                        → (#100) Object does not exist
    business_discovery.username(fjaak)  → 330 025 abonnés, 706 posts, médias
    business_discovery{media{insights}} → (#10) no permission

Le public passe, le privé non. Sans le repli, l'onglet aurait promis une collecte
que le pipeline ne livre pas — un onglet qu'on peut remplir et qui ne ramène rien.

Ce qui est gardé ici est le BRANCHEMENT, pas la fonction. Une couche présente que
rien n'exécute est le défaut qu'on a déjà rencontré trois fois : le repli doit être
atteint depuis `fetch_stats` ET `fetch_media` (le brancher sur un seul rendrait des
abonnés sans publications, ce qui ressemble à un compte vide), et le DAG doit passer
le pseudo, sans quoi le repli reste inatteignable en production.
"""
import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_COLLECTOR = _ROOT / "src/collectors/instagram_api_collector.py"
_DAG = _ROOT / "airflow/dags/instagram_daily.py"


def _fn(path: pathlib.Path, name: str) -> ast.FunctionDef:
    return next(n for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(n, ast.FunctionDef) and n.name == name)


def _unreachable_parents(fn: ast.FunctionDef, call: ast.Call) -> list:
    """Les `if` d'un test CONSTANTEMENT faux qui enferment cet appel.

    Écrit après avoir vu ce garde passer sur son propre mutant : remplacer la
    condition par `if False:` laisse l'appel dans l'AST, donc « l'appel est là »
    n'a jamais voulu dire « l'appel peut arriver ». C'est la troisième fois que
    cette forme précise rend un garde aveugle.
    """
    dead = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        is_dead = (isinstance(test, ast.Constant) and not test.value)
        if not is_dead:
            continue
        if any(n is call for n in ast.walk(node)):
            dead.append(ast.dump(test))
    return dead


@pytest.mark.parametrize("caller", ["fetch_stats", "fetch_media"])
def test_both_calls_can_reach_the_fallback(caller):
    """Les DEUX appels retombent sur `business_discovery`, pas un seul."""
    fn = _fn(_COLLECTOR, caller)
    calls = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call)
             and getattr(n.func, "attr", "") == "_discover"]
    assert calls, (
        f"`{caller}` n'atteint pas le repli : un compte non relié à une Page de "
        "notre Business y rendrait une erreur, alors que business_discovery le lit")
    for call in calls:
        dead = _unreachable_parents(fn, call)
        assert not dead, (
            f"`{caller}` porte le repli sous une branche morte {dead} : le code "
            "est là et ne s'exécute jamais")


def test_the_dag_passes_the_handle_the_fallback_needs():
    """Sans le pseudo, le repli existe et n'est jamais atteignable en production.

    `business_discovery` est indexé par le PSEUDO. Le DAG ne lisait que
    `ig_user_id` ; passer le repli sans passer le pseudo aurait laissé une couche
    branchée sur rien — et un test qui n'appellerait que `_discover` directement
    l'aurait déclarée bonne.
    """
    src = _DAG.read_text(encoding="utf-8")
    tree = ast.parse(src)
    ctor = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and getattr(n.func, "id", "") in ("InstagramCollector", "InstagramAPICollector")
    )
    passed = {kw.arg for kw in ctor.keywords}
    assert "ig_username" in passed, (
        "le DAG ne passe pas `ig_username` : le repli business_discovery ne peut "
        f"pas être atteint en production (arguments passés : {sorted(passed)})")


class _NoDb:
    """Une base qui n'existe pas, et qui le dit si on l'utilise.

    `db=None` retomberait sur la vraie connexion : le sentinelle doit être un objet.
    Toute méthode appelée dessus lève, donc un test qui croit ne rien écrire et se
    met à écrire ne passe pas en silence.
    """

    def __getattr__(self, name):
        raise AssertionError(
            f"ce test ne doit toucher aucune base — il a appelé db.{name}()")


def test_a_missing_handle_says_the_gesture_instead_of_collecting_zero():
    """Pas de pseudo ⇒ on lève avec le geste, jamais un zéro silencieux.

    Rendre 0 abonné ici serait indistinguable d'un compte vide, et la pastille
    passerait au vert sur une collecte qui n'a rien lu — c'est
    `probe-reads-unreadable-as-absent` appliqué à un collecteur.
    """
    import os

    from src.collectors.instagram_api_collector import InstagramCollector as C

    # `db=` INJECTÉ, et non un `monkeypatch` sur `PostgresHandler`. Cette question
    # porte sur une branche pure de `_discover` et n'écrit rien ; la signature de
    # cette classe est déclarée « no-DB » et tourne dans l'étape CI qui précède
    # `Provision Postgres`, sans `DATABASE_URL` ni schéma. Mesuré le 2026-09-06 : le
    # test tombait là sur un `psycopg2.OperationalError`, donc pour une raison qui
    # n'était pas la sienne.
    #
    # La première version débranchait `from_env_or_config` par monkeypatch — ça
    # marchait, et ça gardait le vrai problème : le collecteur n'offrait aucun moyen
    # de dire « je n'ai rien à écrire ». Le paramètre existe maintenant, comme sur
    # `MetaAdsCollector` depuis toujours ; le patch a disparu avec lui.
    c = C(artist_id=1, access_token="x", ig_user_id="17841400000000000",
          ig_username=None, db=_NoDb())
    os.environ.setdefault("META_IG_DISCOVERY_ID", "17841402151518986")
    with pytest.raises(ValueError) as exc:
        c._discover("id,username")
    message = str(exc.value)
    assert "Credentials" in message and "Instagram" in message, (
        "l'erreur ne nomme pas le geste qui la corrige")


def test_the_owner_id_is_not_read_from_a_tenant_identity_variable():
    """Le compte interrogeant est celui de l'APP, et son nom doit le dire.

    Lu `IG_USER_ID`, ce serait une identité de locataire lue dans l'environnement —
    la classe `tenant-identity-falls-back-to-admin`, qui a fait écrire des mois de
    données sous le mauvais propriétaire. Le nom porte donc `META_IG_DISCOVERY_ID`.
    """
    names = {n.value for n in ast.walk(_fn(_COLLECTOR, "_discovery_owner"))
             if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "META_IG_DISCOVERY_ID" in names
    assert "IG_USER_ID" not in names
