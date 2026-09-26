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


def _success_calls_near_circuit_table(source: str) -> list:
    """`st.success(...)` dans une fonction qui interroge `etl_circuit_breaker`.

    AST : la question est « cette fonction affirme-t-elle une bonne santé ? », et un
    `grep` sur `st.success` répondrait pour toute la page.
    """
    tree = ast.parse(source)
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


def unguarded_health_claims(source: str) -> list:
    """The ✅ claims on the circuit table, when nothing checks the table is written. Pure."""
    hits = _success_calls_near_circuit_table(source)
    return [] if not hits or "circuit_mechanism_is_recording" in source else hits


@pytest.mark.parametrize("rel", _PANELS, ids=_PANELS)
def test_a_health_claim_is_guarded_by_evidence(rel: str):
    """Un ✅ sur cette table doit être conditionné à « la table est écrite »."""
    source = (ROOT / rel).read_text(encoding="utf-8")
    hits = unguarded_health_claims(source)
    assert not hits, (
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


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity: a ✅ drawn from an EMPTY `etl_circuit_breaker` query is refused; the
    same ✅ conditioned on the recorder, and a ✅ in a function that never reads the
    table, are accepted."""
    defect = ("import streamlit as st\n"
              "def show_circuits(db):\n"
              "    rows = db.fetch_query('SELECT * FROM etl_circuit_breaker')\n"
              "    if not rows:\n"
              "        st.success('Aucun circuit ouvert')\n")
    assert unguarded_health_claims(defect) == [("show_circuits", 5)]
    fixed = defect.replace("    if not rows:", "    if not rows and circuit_mechanism_is_recording(db):")
    assert unguarded_health_claims(fixed) == []
    assert unguarded_health_claims("import streamlit as st\ndef f():\n    st.success('ok')\n") == []
