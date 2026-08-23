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
_SRC = _ROOT / "src"
_HELPER = "from_header"


def _modules_setting_from() -> list[str]:
    out = []
    for path in sorted(_SRC.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        if "'From'" in path.read_text(encoding="utf-8") or '"From"' in path.read_text(encoding="utf-8"):
            out.append(str(path.relative_to(_ROOT)))
    return out


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
    bad = []
    for lineno, value in _from_assignments(tree):
        is_helper = (isinstance(value, ast.Call)
                     and (getattr(value.func, "id", "") == _HELPER
                          or getattr(value.func, "attr", "") == _HELPER))
        if not is_helper:
            bad.append(lineno)

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
