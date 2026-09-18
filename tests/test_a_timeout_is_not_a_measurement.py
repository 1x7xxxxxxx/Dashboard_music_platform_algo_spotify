"""Cesser d'attendre n'est pas mesurer zéro.

Type: Test
Uses: ast
Depends on: tools/**/*.py, .claude/scripts/**/*.py, src/**/*.py
Persists in: nothing

Une branche d'expiration qui rend `0`, `0.0`, `[]` ou `False` annonce une MESURE là où
elle n'a qu'une attente abandonnée. Le lecteur ne peut pas distinguer les deux, et le
sens de l'erreur est toujours le même : rassurant.

Mesuré le 2026-09-18 sur `tools/loadtest_concurrency.py`, qui portait **trois** branches
de cette forme. La plus coûteuse est `_local_load()` : elle rendait `(0.0, 0.0)` quand
`ps` expirait, ce qui faisait dire au garde de charge « charge 0.00/cœur — mesure
autorisée ».

⚠️ **Le défaut se déclenchait exactement quand il coûtait.** Le seul cas où `ps` met plus
de dix secondes à répondre est celui d'une machine chargée — c'est-à-dire celui où le
verdict aurait dû être « non ». Une mesure prise sous charge auto-infligée a déjà coûté
un facteur **12,8** à ce dépôt (`a-measurement-taken-under-self-inflicted-load`, même
fichier). Deux classes, une seule cause.

Ce que ce garde lit
-------------------
Toute clause `except` qui attrape une expiration (`TimeoutExpired`, `TimeoutError`,
`ReadTimeout`, `Timeout`) et dont le corps rend une valeur qui se lit comme une mesure :
`0`, `0.0`, `False`, `[]`, `{}`, `''`, ou un tuple de zéros. `None` est autorisé — c'est
la façon dont ce dépôt dit « inconnu » —, lever l'est aussi, et **nommer l'expiration
avant de rendre une valeur l'est également** : le défaut est le SILENCE, pas la valeur.

Ce qu'il ne couvre PAS
----------------------
Une expiration attrapée par un `except Exception` nu : le prédicat ne la voit pas, et
c'est la forme la plus répandue. Et les expirations côté SQL (`statement_timeout`), qui
remontent en `OperationalError` et ne portent pas « timeout » dans leur nom de classe.

Mutation record — 2026-09-18 : en remettant `return (0.0, 0.0)` dans `_local_load`, ce
garde le nomme ; avec `return None`, il passe.

---
rex: []
---
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCANNED = ("tools", ".claude/scripts", "src", "airflow")
_TIMEOUTS = {"TimeoutExpired", "TimeoutError", "ReadTimeout", "Timeout",
             "ConnectTimeout", "ReadTimeoutError"}


def _names(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def _looks_like_a_measurement(value: ast.AST | None) -> bool:
    """`0`, `0.0`, `False`, `[]`, `{}`, `''`, ou un tuple de ceux-là."""
    if value is None:
        return False
    if isinstance(value, ast.Constant):
        return value.value in (0, 0.0, False, "") and value.value is not None
    if isinstance(value, (ast.List, ast.Dict, ast.Set)):
        return not getattr(value, "elts", None) and not getattr(value, "keys", None)
    if isinstance(value, ast.Tuple):
        return bool(value.elts) and all(_looks_like_a_measurement(e) for e in value.elts)
    return False


def _offenders() -> list[str]:
    out = []
    for base in _SCANNED:
        racine = _ROOT / base
        if not racine.is_dir():
            continue
        for path in sorted(racine.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):        # pragma: no cover
                continue
            rel = str(path.relative_to(_ROOT)).replace("\\", "/")
            for h in (n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)):
                if not (_names(h.type) & _TIMEOUTS):
                    continue
                # ⚠️ **LE DÉFAUT EST LE SILENCE, PAS LA VALEUR** — corrigé en mutant
                # ce garde le jour où il a été écrit. Sa première version signalait
                # `.claude/scripts/check_env.py` trois fois, à tort : ces branches
                # AVERTISSENT (`warn("timedatectl timed out (>4s)")`) avant de rendre
                # `False`, et `False` y veut dire « ce contrôle ne passe pas » —
                # c'est-à-dire la direction prudente pour un contrôle d'environnement.
                # Une expiration qui se NOMME n'est pas une expiration déguisée en
                # mesure.
                nomme = any(
                    isinstance(c, ast.Call)
                    and (getattr(c.func, "id", "") or getattr(c.func, "attr", ""))
                    in {"warn", "warning", "error", "print", "info", "critical"}
                    for c in ast.walk(h))
                if nomme:
                    continue
                for r in (n for n in ast.walk(h) if isinstance(n, ast.Return)):
                    if _looks_like_a_measurement(r.value):
                        out.append(f"{rel}:{r.lineno} — une expiration rend "
                                   f"{ast.unparse(r.value)}")
    return out


def test_the_scan_sees_timeout_handlers() -> None:
    """Anti-vacuité : sans branche d'expiration lue, ce garde est vert sur rien."""
    vus = 0
    for base in _SCANNED:
        racine = _ROOT / base
        if not racine.is_dir():
            continue
        for path in racine.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):        # pragma: no cover
                continue
            vus += sum(1 for n in ast.walk(tree)
                       if isinstance(n, ast.ExceptHandler) and (_names(n.type) & _TIMEOUTS))
    assert vus >= 5, (
        f"seulement {vus} branche(s) d'expiration trouvée(s) — il y en avait 9 le "
        "2026-09-18. Le lecteur AST est cassé, ou les expirations ont changé de nom.")


def test_no_timeout_returns_something_that_reads_as_a_measurement() -> None:
    fautifs = _offenders()
    assert not fautifs, (
        f"{len(fautifs)} branche(s) d'expiration rendent une valeur qui se lit comme "
        "une MESURE.\nCesser d'attendre n'est pas mesurer zéro, et l'erreur va "
        "toujours dans le sens rassurant.\nMesuré le 2026-09-18 : `_local_load()` "
        "rendait `(0.0, 0.0)` quand `ps` expirait, donc le garde de charge annonçait "
        "« machine inactive — mesure autorisée » — or un `ps` lent est précisément le "
        "symptôme d'une machine chargée.\n"
        "Remède : rendre `None` (ce dépôt lit `None` comme INCONNU) ou lever.\n  "
        + "\n  ".join(fautifs[:12]))
