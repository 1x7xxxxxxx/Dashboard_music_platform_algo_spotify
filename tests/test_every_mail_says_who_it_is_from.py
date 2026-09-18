"""
Guard — every outbound mail composes its `From` in the same, single place (R38).

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: src/utils/email_identity.py, src/**
Persists in: nothing

Error class: sender-identity-composed-twice.

Mesuré le 2026-08-23. Deux chemins d'envoi, deux en-têtes `From` différents :

* `verification_email.py` : `f"{from_name} <{from_email}>"` — correct ;
* `email_alerts.py` : **`self.smtp_user`**, l'identifiant de connexion au relais.

En production `SMTP_USER` vaut `ae8df8001@smtp-brevo.com` et `SMTP_FROM` vaut
`noreply@streamlytics.fr`. Toutes les alertes de DAG, le résumé quotidien et le rapport
d'onboarding annonçaient donc le compte de relais ; Brevo, qui exige un expéditeur
validé, y substituait l'expéditeur par défaut du compte.

Ce que ça a coûté en diagnostic est plus intéressant que le défaut : la roadmap tenait
pour acquis que « le code met déjà `streaMLytics` par défaut, donc le nom vient du compte
Brevo, et aucune ligne de Python ne peut le corriger ». Les deux moitiés étaient fausses.
Le nom venait de la clé `smtp.from_name` de `config/config.yaml` — le repli que le code
lit AVANT son défaut, que personne n'avait ouvert — et l'autre chemin d'envoi n'utilisait
aucun nom du tout. On avait regardé le chemin qui marchait.

Le garde interdit donc la seule chose qui rende ça possible : composer un `From` ailleurs
que dans `email_identity.from_header()`.
"""

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
# `tools/` ajouté le 2026-09-18, et son absence avait un coût exact.
# `tools/notify_schema_drift.py` est un TROISIÈME chemin SMTP, hors de `src/` donc hors
# de ce garde, et il posait `msg["From"] = os.getenv("SMTP_FROM") or user` — c'est-à-dire
# l'identifiant du relais sans nom d'affichage, le défaut LITTÉRAL que
# `src/utils/email_identity.py` a été écrit pour supprimer. Il est appelé par deux crons
# (`schema_drift_cron.sh`, `infra_health_cron.sh`).
# La propriété n'est pas « deux chemins d'envoi dans src/ » : c'est **toute identité
# d'expéditeur composée où que ce soit**. Le garde part donc des arbres, pas de `src/`.
_TREES = ("src", "tools", "airflow", "scripts", ".claude/scripts")
_HELPER = "from_header"


def _modules_setting_from() -> list[str]:
    out = []
    fichiers = [f for t in _TREES for f in sorted((_ROOT / t).rglob("*.py"))
                if (_ROOT / t).is_dir()]
    for path in fichiers:
        if "__pycache__" in str(path):
            continue
        if "'From'" in path.read_text(encoding="utf-8") or '"From"' in path.read_text(encoding="utf-8"):
            out.append(str(path.relative_to(_ROOT)))
    return out


def _compose(fn: ast.FunctionDef) -> bool:
    """Cette fonction FABRIQUE-t-elle une identité, ou rend-elle une constante ?

    Compose = elle lit l'environnement, un fichier de configuration, ou appelle quoi
    que ce soit pour construire sa valeur. Ne compose pas = tous ses `return` sont des
    littéraux. C'est la distinction qui sépare un repli de survie d'un second
    mécanisme d'identité.
    """
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            nom = getattr(n.func, "attr", "") or getattr(n.func, "id", "")
            if nom in {"getenv", "environ", "get", "load", "read_text", "format"}:
                return True
        if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Attribute):
            if n.value.attr == "environ":
                return True
        if isinstance(n, ast.JoinedStr):
            return True
    return False


def _from_assignments(tree: ast.Module) -> list[tuple[int, ast.AST]]:
    """Chaque `msg['From'] = <valeur>`, avec sa valeur."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if (isinstance(tgt, ast.Subscript)
                    and isinstance(tgt.slice, ast.Constant)
                    and tgt.slice.value == "From"):
                found.append((node.lineno, node.value))
    return found


def test_the_scope_is_not_empty() -> None:
    mods = _modules_setting_from()
    assert mods, "aucun module ne compose d'en-tête From — la recherche a raté sa cible"


@pytest.mark.parametrize("rel", _modules_setting_from())
def test_the_from_header_is_never_composed_locally(rel: str) -> None:
    tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
    # ⚠️ Le nom ne suffit PAS, et ce garde s'est fait battre par le sien le
    # 2026-09-18. Élargi le matin même pour attraper `tools/notify_schema_drift.py`,
    # il est redevenu vert le soir quand ce fichier a reçu un repli d'import
    # `def from_header(): return os.getenv("SMTP_USER") or ""` — le login du relais,
    # sans nom d'affichage, c'est-à-dire le défaut LITTÉRAL que ce fichier interdit.
    # `value.func.id == "from_header"` matchait, et la composition locale passait.
    # Un garde qui vérifie un NOM vérifie ce que l'appel s'appelle, pas d'où il vient.
    # Et un repli d'import a le DROIT de définir le nom — c'est ainsi qu'un outil
    # autonome survit à un `src/` cassé. Ce qu'il n'a pas le droit de faire, c'est de
    # COMPOSER : lire une variable d'environnement ou un fichier de configuration pour
    # fabriquer une identité. Un repli qui rend une constante ne compose rien ; un
    # repli qui rend `os.getenv("SMTP_USER")` rend le login du relais sans nom
    # d'affichage, exactement le défaut que ce fichier interdit ailleurs.
    # Premier prédicat écrit ici : « défini sur place ⇒ refusé ». Il refusait aussi le
    # repli constant, donc il aurait poussé à SUPPRIMER la survivabilité pour faire
    # taire un test. Un garde qui force à retirer une protection est mal écrit.
    composants = {n.name for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and _compose(n)}
    # Et la valeur peut arriver par une VARIABLE. Exiger un appel direct
    # `msg["From"] = from_header()` est encore une forme d'écriture, pas la propriété :
    # `e = from_header()` puis `msg["From"] = e` est le même code. Le garde a rougi
    # dessus le 2026-09-18, sur du code CORRECT, pour cette seule raison — et cette
    # forme-là existe parce qu'il faut tester la valeur avant de poser l'en-tête.
    liaisons = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1:
            cible = n.targets[0]
            if isinstance(cible, ast.Name):
                liaisons.setdefault(cible.id, []).append(n.value)

    def _vient_du_helper(v: ast.AST, profondeur: int = 0) -> bool:
        if isinstance(v, ast.Call):
            nom = getattr(v.func, "id", "") or getattr(v.func, "attr", "")
            if nom != _HELPER:
                return False
            return getattr(v.func, "id", "") not in composants
        if isinstance(v, ast.Name) and profondeur < 3:
            sources = liaisons.get(v.id, [])
            # UNE seule liaison, sinon on ne sait pas laquelle arrive ici.
            return len(sources) == 1 and _vient_du_helper(sources[0], profondeur + 1)
        return False

    bad = [lineno for lineno, value in _from_assignments(tree)
           if not _vient_du_helper(value)]

    assert not bad, (
        f"{rel} ligne(s) {bad} : l'en-tête `From` est composé sur place. Il doit venir de "
        f"`src.utils.email_identity.from_header()`. Deux compositions ont divergé une "
        f"fois — l'une posait l'identifiant du relais, sans nom d'affichage — et le "
        f"symptôme (le mauvais nom dans la boîte des utilisateurs) a été attribué au "
        f"compte Brevo pendant des semaines."
    )


def test_the_default_name_is_ours_and_the_address_is_not_the_login():
    """Le login SMTP n'est un expéditeur qu'en dernier recours, jamais le cas nominal."""
    import os

    from src.utils.email_identity import DEFAULT_FROM_NAME, sender_identity

    assert DEFAULT_FROM_NAME == "streaMLytics"

    keep = {k: os.environ.get(k) for k in ("SMTP_FROM_NAME", "SMTP_FROM", "SMTP_USER")}
    try:
        os.environ["SMTP_FROM_NAME"] = "streaMLytics"
        os.environ["SMTP_FROM"] = "noreply@streamlytics.fr"
        os.environ["SMTP_USER"] = "ae8df8001@smtp-brevo.com"
        name, email = sender_identity()
        assert name == "streaMLytics"
        assert email == "noreply@streamlytics.fr", (
            "l'adresse d'expédition doit être celle du domaine authentifié, pas le "
            "login du relais — sinon le relais y substitue son expéditeur par défaut"
        )
    finally:
        for k, v in keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ── La composition DORMANTE — 2026-09-18 ─────────────────────────────────────
#
# Le garde ci-dessus attrape `msg['From'] = <autre chose que from_header()>`. Il ne
# voit RIEN d'une identité composée qui n'est jamais posée dans un en-tête.
#
# `src/utils/verification_email._smtp_config()` en portait une : `from_name` et
# `from_email` y étaient calculés, et les DEUX consommateurs de ce dict (`:115` et
# `:430`) ne lisaient que host/port/user/password. Dormante — et déjà divergente de la
# source unique sur deux points mesurés : avec `from_name: ""` dans `config.yaml` elle
# rendait `""` là où `sender_identity()` rend `streaMLytics`, et son adresse n'avait
# pas le repli `SMTP_USER`.
#
# Une seconde composition que personne ne lit est une seconde composition que
# quelqu'un LIRA, parce qu'elle est à portée de main dans le module d'envoi. La
# propriété qui la coince ne parle donc pas d'en-tête : **une seule unité de
# traduction a le droit de lire les variables d'identité d'expéditeur.**
_IDENTITY_VARS = ("SMTP_FROM_NAME", "SMTP_FROM")
_IDENTITY_OWNER = "src/utils/email_identity.py"


def _reads_identity_env(path: Path) -> list[int]:
    """Les lignes où ce module lit une variable d'identité d'expéditeur (AST).

    AST et non texte : ce fichier-ci NOMME `SMTP_FROM_NAME` dans sa prose, et le
    catalogue porte `guard-satisfied-by-its-own-comment` pour cette raison exacte —
    six gardes de ce dépôt sont passés verts sur leur propre commentaire.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # pragma: no cover - defensive
        return []
    lignes = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        nom = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if nom not in {"get", "getenv"}:
            continue
        for arg in node.args[:1]:
            if isinstance(arg, ast.Constant) and arg.value in _IDENTITY_VARS:
                lignes.append(node.lineno)
    return lignes


@pytest.mark.parametrize("tree_name", _TREES)
def test_only_one_module_reads_the_sender_identity(tree_name: str) -> None:
    base = _ROOT / tree_name
    if not base.is_dir():
        pytest.skip(f"{tree_name} absent de cet arbre")
    coupables = {}
    for path in sorted(base.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        rel = str(path.relative_to(_ROOT))
        if rel == _IDENTITY_OWNER:
            continue
        lignes = _reads_identity_env(path)
        if lignes:
            coupables[rel] = lignes
    assert not coupables, (
        f"{coupables} lisent une variable d'identité d'expéditeur "
        f"({', '.join(_IDENTITY_VARS)}) alors que seul {_IDENTITY_OWNER} en a le "
        "droit. Une composition parallèle diverge, qu'elle soit lue ou non : celle "
        "de `_smtp_config()` était dormante ET déjà fausse sur deux points. "
        "Passer par `from_header()` / `sender_identity()`."
    )


def test_the_identity_predicate_is_not_vacuous() -> None:
    """Le prédicat voit-il le propriétaire lui-même ? Sinon il ne voit personne."""
    assert _reads_identity_env(_ROOT / _IDENTITY_OWNER), (
        f"{_IDENTITY_OWNER} ne lit plus aucune variable d'identité selon ce prédicat "
        "— soit le module a changé, soit le prédicat ne trouve rien nulle part et le "
        "test ci-dessus est vert pour une raison qui n'a rien à voir avec la propriété."
    )
