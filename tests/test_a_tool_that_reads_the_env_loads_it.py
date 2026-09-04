"""Un outil qui lit l'environnement le charge — sinon il dégrade en silence.

Type: Test
Uses: ast, tools/, .claude/scripts/
Depends on: src/utils/env_files.load_project_env
Persists in: nothing

Le défaut, signalé le 2026-09-05
---------------------------------
« Je viens de refaire le script pour sandbox et je n'ai pas l'email. »

`tools/create_sandbox.py` ne chargeait ni `.env` ni `.env.local`. Lancé depuis un
shell ordinaire — c'est-à-dire de la seule façon dont on le lance — il ne voyait ni
`SANDBOX_EMAIL`, ni `ALERT_EMAIL`, ni `SMTP_USER`, et retombait sur son défaut
`<slug>@sandbox.local` : un domaine qui n'existe pas. Puis il tentait d'envoyer le
mail de vérification à cette adresse, avec un SMTP dont il n'avait pas les
identifiants non plus.

Ce qui rend la classe invisible
--------------------------------
La moitié qui compte marche quand même. `PostgresHandler.from_env_or_config()`
retombe sur `config/config.yaml`, donc la base répond, le compte est créé, le mot de
passe s'affiche, le script se termine en vert. Seul ce qui dépend UNIQUEMENT de
l'environnement dégrade — et il dégrade vers une valeur par défaut plausible, pas
vers une erreur.

Quatre outils frères chargeaient déjà `load_project_env` (`artist_preflight`,
`artist_first_look`, `create_canary`, `check_central_apps`). Deux ne le faisaient pas.
Le second, `notify_schema_drift.py`, lit SIX variables SMTP et EST le cron de dérive
de schéma qui s'auto-notifie : il fonctionne aujourd'hui parce que le cron de prod
exporte l'environnement lui-même, c'est-à-dire pour une raison qui vit ailleurs que
dans le fichier et qu'une réécriture du cron peut retirer sans le savoir.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DIRS = ("tools", ".claude/scripts")

# Les outils qui n'ont légitimement PAS besoin de l'environnement du projet : ils
# lisent une variable posée par leur appelant (CI, hook, harnais de test), pas une
# configuration du dépôt. Chaque entrée dit laquelle.
_EXEMPT = {
    # ex. : "tools/x.py": "lit CI, posé par GitHub Actions",
}


def _reads_env(tree: ast.AST) -> set[str]:
    """Les variables lues — noms littéraux ET listes de noms parcourues.

    La deuxième moitié compte : `create_sandbox._default_email` boucle sur un tuple
    de noms (`for var in ("SANDBOX_EMAIL", "ALERT_EMAIL", "SMTP_USER")`). Un
    détecteur qui n'inspecte que `os.getenv("LITTÉRAL")` n'y voyait qu'UNE variable
    (`APP_BASE_URL`) et ratait les trois qui causaient le défaut.
    """
    out: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "attr", "") == "getenv"):
            continue
        if node.args and isinstance(node.args[0], ast.Constant):
            out.add(str(node.args[0].value))
        elif node.args and isinstance(node.args[0], ast.Name):
            # `os.getenv(var)` dans une boucle : on remonte au tuple parcouru.
            out.add(f"<{node.args[0].id}>")
    return out


def _loads_env(tree: ast.AST) -> bool:
    return any(isinstance(n, ast.Call)
               and getattr(n.func, "id", "") in ("load_project_env", "load_dotenv")
               for n in ast.walk(tree))


def _tools() -> list[Path]:
    out: list[Path] = []
    for d in _DIRS:
        out += sorted((_ROOT / d).rglob("*.py"))
    return out


def test_the_sweep_actually_reads_the_tools():
    """Non-vacuité : sans outils lus, ce fichier passerait pour rien."""
    assert len(_tools()) > 20, f"seulement {len(_tools())} outils lus"


def test_every_tool_that_reads_the_env_loads_it():
    offenders: list[str] = []
    for path in _tools():
        rel = str(path.relative_to(_ROOT)).replace("\\", "/")
        if rel in _EXEMPT:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        names = _reads_env(tree)
        if names and not _loads_env(tree):
            offenders.append(f"{rel} → {sorted(names)}")

    assert not offenders, (
        "Ces outils lisent l'environnement sans le charger :\n  "
        + "\n  ".join(offenders)
        + "\n\nLancés depuis un shell ordinaire ils ne verront rien, et ils "
          "dégraderont vers une valeur par défaut PLAUSIBLE au lieu d'échouer — "
          "`create_sandbox` envoyait le mail de vérification à `@sandbox.local`, un "
          "domaine qui n'existe pas, pendant que la base répondait normalement via "
          "`config.yaml`.\n"
          "Ajoute `from src.utils.env_files import load_project_env` puis "
          "`load_project_env()` après le `sys.path.insert`, comme les quatre outils "
          "frères. Si la variable vient légitimement de l'appelant, inscris-la dans "
          "`_EXEMPT` avec sa raison."
    )


def test_the_sandbox_default_address_is_deliverable():
    """Le cas signalé, épinglé : le bac à sable ne s'écrit pas à un domaine mort.

    `@sandbox.local` n'existe pas — Gmail a renvoyé le mot de bienvenue le
    2026-09-04, et c'est ce rebond qui a fait remplacer le défaut par un alias `+`.
    Le garde vérifie que la substitution TIENT quand l'environnement est chargé,
    puisque c'est la seule condition dans laquelle elle fonctionne.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_cs", _ROOT / "tools" / "create_sandbox.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # charge l'env au passage — c'est le sujet

    addr = mod._default_email("sandbox")
    assert not addr.endswith(".local"), (
        f"l'adresse par défaut du bac à sable est {addr!r} : les e-mails de "
        "vérification et de bienvenue rebondiront, et le parcours qu'il prétend "
        "rejouer saute son premier écran")
    assert "+sandbox@" in addr, (
        f"{addr!r} n'est pas un alias `+` : il n'arriverait pas dans la boîte de "
        "l'opérateur, ou ne s'y filtrerait pas")
