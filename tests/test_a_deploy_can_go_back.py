"""Un deploiement qui echoue sa porte de sante REVIENT en arriere.

Type: Test
Uses: pytest, re
Depends on: tools/deploy.sh
Persists in: nothing

Ce qui etait vrai jusqu'au 2026-09-16
-------------------------------------
`tools/deploy.sh` capturait `before="$(git rev-parse --short HEAD)"` a la ligne 19 et
ne s'en servait QUE pour l'affichage a la ligne 22. Quand la porte de sante rougissait,
le script sortait en `exit 1` **en laissant le conteneur casse en service**.

Le script savait ou revenir. Il n'y revenait pas. La seule manoeuvre de secours etait
alors un revert et un second build de plusieurs minutes, a la main, sous trafic.

Ce garde demande deux choses, et les deux comptent
--------------------------------------------------
1. la branche d'echec de la porte APPELLE le retour arriere — pas seulement qu'une
   fonction de retour existe quelque part dans le fichier ;
2. cette fonction utilise vraiment `$before` — une fonction qui ne revient nulle part
   satisferait la premiere condition sans rien garantir.

C'est la distinction « presence != atteignabilite » que ce depot a payee plusieurs
fois : une fonction correcte que rien n'appelle ne protege de rien.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DEPLOY = _ROOT / "tools" / "deploy.sh"

_FAILURE_MARK = "did not return 200"


def _lines() -> list[str]:
    return _DEPLOY.read_text(encoding="utf-8").splitlines()


def _failure_branch() -> list[str]:
    """Les lignes qui suivent immediatement l'echec de la porte de sante."""
    lines = _lines()
    for i, line in enumerate(lines):
        if _FAILURE_MARK in line and not line.strip().startswith("#"):
            return lines[i:i + 5]
    return []


def _rollback_body() -> list[str]:
    lines = _lines()
    start = next((i for i, ln in enumerate(lines)
                  if re.match(r"^\s*rollback\s*\(\)\s*\{", ln)), None)
    if start is None:
        return []
    out = []
    for ln in lines[start + 1:]:
        if ln.startswith("}"):
            break
        out.append(ln)
    return out


def test_a_red_health_gate_puts_the_previous_version_back() -> None:
    branch = _failure_branch()
    assert branch, (
        f"aucune branche d'echec trouvee dans `tools/deploy.sh` (marqueur "
        f"{_FAILURE_MARK!r}). Si la porte de sante a disparu, c'est CA le constat."
    )
    assert any("rollback" in ln for ln in branch), (
        "la porte de sante echoue sans appeler de retour arriere : le conteneur casse "
        "reste EN SERVICE, et la seule manoeuvre de secours est manuelle, sous trafic.\n"
        "Branche lue :\n  " + "\n  ".join(ln.strip() for ln in branch)
    )


def test_the_rollback_actually_goes_back() -> None:
    """Une fonction de retour qui ne revient nulle part satisferait le test d'a cote."""
    body = _rollback_body()
    assert body, "aucune fonction `rollback()` au niveau du script"
    joined = "\n".join(body)
    assert "$before" in joined, (
        "`rollback()` ne mentionne jamais `$before` : elle ne revient donc a rien. "
        "C'est la forme « presence != atteignabilite », prise a l'envers."
    )
    assert "reset" in joined or "checkout" in joined, (
        "`rollback()` ne remet aucun code en place — elle affiche peut-etre un message, "
        "ce qui est pire qu'une absence : on croira que le retour a eu lieu."
    )


def test_a_deploy_refuses_to_run_ahead_of_its_migrations() -> None:
    """Migrer APRES avoir deploye demarre une app qui repond 200 et rend 500."""
    body = _DEPLOY.read_text(encoding="utf-8")
    assert "schema_migrations" in body, (
        "`tools/deploy.sh` ne regarde pas le registre des migrations. Quand l'ordre est "
        "inverse, rien n'echoue bruyamment : l'application DEMARRE, repond 200 sur "
        "/health, et rend 500 sur les donnees — la porte de sante ne teste que la "
        "vivacite. La classe a deja coute un `/kpis` casse, vu le lendemain."
    )
    assert "tools/migrate.sh" in body, (
        "le refus doit NOMMER la commande qui debloque, sinon il laisse l'operateur "
        "chercher (classe `a-printed-command-is-runnable-as-printed`)."
    )
