"""On ne rejoue pas ce qui ne redeviendra jamais vrai, et le disjoncteur est branché.

Type: Test
Uses: pytest
Depends on: src/utils/retry.py, src/utils/dag_run_logger.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
**Le disjoncteur avait zéro appelant.** `src/utils/circuit_breaker.py` existait depuis
des mois ; `etl_circuit_breaker` comptait **0 ligne** en production. Seuls le bouton de
remise à zéro et le détecteur de vacuité l'importaient — l'interface d'un mécanisme
qui ne tournait pas. Un credential cassé consommait donc deux essais × treize DAGs × N
locataires chaque nuit, indéfiniment : exactement ce que le module avait été écrit pour
éviter.

**Et `@retry` rejouait tout.** Sa branche générique reprenait n'importe quelle
exception, y compris un 401 (credential révoqué) ou un 404 (compte publicitaire retiré)
— trois tentatives, six secondes d'attente, pour échouer quand même. `NON_RETRIABLE` ne
couvre que les erreurs de données Python et ne pouvait pas les voir.

Sur 429, enfin, le recul était fixe (2 s, 4 s) quand Spotify et Meta annoncent des
fenêtres de plusieurs minutes dans `Retry-After` — que SoundCloud lit déjà sans
l'utiliser. Les trois tentatives étaient garanties de rater.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.utils.retry import retry

REPO = Path(__file__).resolve().parent.parent


class _Resp:
    def __init__(self, code, after=None):
        self.status_code = code
        self.headers = {"Retry-After": str(after)} if after is not None else {}


class _HttpError(Exception):
    def __init__(self, code, after=None):
        self.response = _Resp(code, after)
        super().__init__(str(code))


def _count_attempts(code, after=None, attempts=3):
    seen = {"n": 0}

    @retry(max_attempts=attempts, base_delay=0.01)
    def _call():
        seen["n"] += 1
        raise _HttpError(code, after)

    with pytest.raises(_HttpError):
        _call()
    return seen["n"]


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_a_definitive_refusal_is_tried_once(code) -> None:
    """Un refus 4xx ne redeviendra pas vrai : le rejouer coûte du temps pour rien."""
    assert _count_attempts(code) == 1, (
        f"HTTP {code} rejoué : un credential révoqué ou une ressource retirée consomme "
        "alors trois tentatives par appel, chaque nuit, pour échouer quand même")


@pytest.mark.parametrize("code", [429, 500, 502, 503])
def test_a_temporary_failure_is_still_retried(code) -> None:
    """L'autre bord : ne pas transformer le correctif en abandon systématique."""
    assert _count_attempts(code) == 3, f"HTTP {code} devrait être rejoué"


def test_the_server_decides_how_long_to_wait(monkeypatch) -> None:
    """`Retry-After` prime sur notre recul, jamais l'inverse.

    On asserte sur la VALEUR passée à l'attente, pas sur le temps écoulé : la suite
    neutralise déjà ce `sleep` — délibérément, il lui coûtait 66 s sur 275 — et une
    assertion d'horloge serait de toute façon instable.
    """
    import src.utils.retry as _retry
    seen: list[float] = []
    monkeypatch.setattr(_retry.time, "sleep", seen.append, raising=False)

    assert _count_attempts(429, after=90, attempts=2) == 2
    assert seen == [90], (
        f"attente de {seen} au lieu des 90 s annoncées par le serveur. Nos 2 s fixes "
        "contre des fenêtres de plusieurs minutes garantissent l'échec des reprises.")

    seen.clear()
    assert _count_attempts(500, attempts=2) == 2
    assert seen and seen[0] < 1, (
        f"sans en-tête du serveur, le recul doit rester le nôtre : {seen}")


def test_a_python_data_error_is_never_retried() -> None:
    """Le contrat d'origine reste : une erreur de données n'est pas une panne."""
    seen = {"n": 0}

    @retry(max_attempts=3, base_delay=0.01)
    def _bad():
        seen["n"] += 1
        raise KeyError("champ absent")

    with pytest.raises(KeyError):
        _bad()
    assert seen["n"] == 1


def test_the_circuit_breaker_is_actually_wired() -> None:
    """Structurel : le contexte qui enveloppe chaque collecte l'alimente.

    Il est branché LÀ et pas dans les treize DAGs : un mécanisme qu'il faut câbler
    treize fois finit par n'être câblé nulle part — c'est comment il en est arrivé à
    zéro appelant.
    """
    src = (REPO / "src" / "utils" / "dag_run_logger.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "_record_on_the_breaker" in names, "le point d'enregistrement a disparu"

    exit_fn = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "__exit__")
    body = ast.unparse(exit_fn)
    assert "_record_on_the_breaker" in body, (
        "le disjoncteur n'est plus alimenté à la fin d'une collecte : il retombe à "
        "zéro appelant, comme avant le 2026-09-10")

    rec = next(n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_record_on_the_breaker")
    called = {getattr(c.func, "attr", "") for c in ast.walk(rec) if isinstance(c, ast.Call)}
    assert {"record_success", "record_failure"} <= called, (
        "le point d'enregistrement n'appelle pas les deux issues : un disjoncteur qui "
        "ne voit que les succès ne s'ouvre jamais")
