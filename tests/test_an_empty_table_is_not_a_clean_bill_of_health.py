"""« Aucune ligne » et « tout va bien » ne sont pas la même chose.

Classe `empty-table-rendered-as-health`.

`etl_circuit_breaker` est lue par deux panneaux admin. La requête filtre
`state != 'closed'`, et ne rien trouver a **deux** causes opposées : aucune
plateforme n'est en panne, ou personne n'écrit jamais dans la table. Les deux
affichaient le même `st.success("✅ … fonctionnement normal")`.

Mesuré le 2026-08-24 : `CircuitBreaker` (`src/utils/circuit_breaker.py`) n'a **aucun
appelant de production** — il n'est instancié que dans son propre exemple de
docstring et dans son propre helper `reset_circuit`. La table est vide en base. Les
deux panneaux affirmaient donc une bonne santé qu'aucune mesure ne soutenait, sur la
page d'alertes.

Même famille que le panier à 0 % du PDF et que le compteur d'artistes : une absence
rendue comme une mesure.
"""
import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

_PANELS = [
    "src/dashboard/views/alerts.py",
    "src/dashboard/views/etl_logs.py",
]


def _success_calls_near_circuit_table(path: pathlib.Path) -> list:
    """`st.success(...)` dans une fonction qui interroge `etl_circuit_breaker`.

    AST : la question est « cette fonction affirme-t-elle une bonne santé ? », et un
    `grep` sur `st.success` répondrait pour toute la page.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = ast.dump(fn)
        if "etl_circuit_breaker" not in body:
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "success"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "st"):
                out.append((fn.name, node.lineno))
    return out


@pytest.mark.parametrize("rel", _PANELS, ids=_PANELS)
def test_a_health_claim_is_guarded_by_evidence(rel: str):
    """Un ✅ sur cette table doit être conditionné à « la table est écrite »."""
    path = ROOT / rel
    hits = _success_calls_near_circuit_table(path)
    if not hits:
        return  # aucun ✅ affirmé : rien à garder
    source = path.read_text(encoding="utf-8")
    assert "circuit_mechanism_is_recording" in source, (
        f"{rel} affirme une bonne santé (st.success, ligne(s) "
        f"{[h[1] for h in hits]}) à partir d'une requête qui ne rend rien aussi bien "
        "quand tout va bien que quand personne n'écrit dans la table. Conditionner à "
        "`circuit_mechanism_is_recording(db)`."
    )


def test_the_recorder_reports_an_unwritten_table_as_not_recording():
    """Le prédicat lui-même, sans base : une lecture qui échoue n'affirme rien."""
    from src.utils.circuit_breaker import circuit_mechanism_is_recording

    class _Dead:
        def fetch_query(self, *_a, **_k):
            raise RuntimeError("relation etl_circuit_breaker does not exist")

    class _Empty:
        def fetch_query(self, *_a, **_k):
            return []

    class _Written:
        def fetch_query(self, *_a, **_k):
            return [(1,)]

    assert circuit_mechanism_is_recording(_Dead()) is False
    assert circuit_mechanism_is_recording(_Empty()) is False
    assert circuit_mechanism_is_recording(_Written()) is True


def test_a_recorded_failure_never_persists_a_raw_credential():
    """`record_failure` rédige à l'ENTRÉE — la valeur est persistée puis affichée."""
    from src.utils.circuit_breaker import _redacted

    leaked = ("HTTPSConnectionPool: /v23.0/act_1/insights?"
              "access_token=EAAG_SUPER_SECRET&fields=spend")  # pragma: allowlist secret
    out = _redacted(leaked)
    assert "EAAG_SUPER_SECRET" not in out
    assert "access_token=***" in out
    assert len(out) <= 500
