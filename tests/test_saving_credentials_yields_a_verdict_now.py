"""Connecting a platform must produce a verdict immediately, not at 23h.

Type: Test
Uses: ast
Depends on: src/dashboard/views/credentials/_render.py, utils/status_matrix.py
Persists in: nothing

The gap this closes
-------------------
Two things already answer "does this tenant actually work":

  * `make artist-preflight` — five chained checks, run by hand;
  * the nightly `alert_monitor` DAG — `check_central_apps`,
    `check_onboarding_readiness`, `check_tenant_contamination`, and a per-tenant
    probe loop that remembers each verdict.

Both are real. Neither is available **when the artist needs it**. An artist who
connects Spotify at 15h had no answer until 23h, and `make artist-preflight` is not
something an artist can run — it is an operator command on the box.

Verification time is too early: at that point there are no credentials, no identity
and no data, so all five checks are red and none of the reds means anything. The
first moment the question HAS an answer is the moment credentials are saved.

So `_handle_save()` now calls `run_probes_now(db, artist_id, [platform_key])` — the
same probe the "🔌 Vérifier maintenant" button runs — and it writes the verdict to
`tenant_platform_probe`, where the matrix on Home, Onboarding and Credentials reads
it without anyone pressing anything.

What this asserts, and why it is structural
-------------------------------------------
That the save path still reaches the probe. A future refactor that splits
`_handle_save` or adds a second save route would otherwise silently go back to
"connected, and nobody knows whether it works" — which is the sentence both beta
sessions ended on.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_RENDER = _ROOT / "src" / "dashboard" / "views" / "credentials" / "_render.py"
_MATRIX = _ROOT / "src" / "dashboard" / "utils" / "status_matrix.py"

PROBE_CALL = "run_probes_now"


def save_paths_without_a_probe(path: Path) -> list[str]:
    """`func:line` for every credential-save function that never probes.

    A save function is one that triggers a DAG — that is what "the artist just
    connected something" looks like in this tree.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return []
    bad = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        triggers = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "trigger_dag"
            for n in ast.walk(fn)
        )
        if not triggers:
            continue
        probes = any(
            isinstance(n, ast.Call)
            and (getattr(n.func, "id", "") == PROBE_CALL
                 or getattr(n.func, "attr", "") == PROBE_CALL)
            for n in ast.walk(fn)
        )
        if not probes:
            bad.append(f"{fn.name}:{fn.lineno}")
    return sorted(bad)


def test_the_credentials_save_path_probes_immediately():
    offenders = save_paths_without_a_probe(_RENDER)
    assert not offenders, (
        f"These save credentials and launch a collection without asking whether it "
        f"works: {offenders}.\n"
        f"Call `{PROBE_CALL}(db, artist_id, [platform_key])` before the success "
        "message. Otherwise the artist is told 'collecte lancée' and learns whether "
        "it worked at 23h — or never."
    )


def test_the_guard_goes_red_on_a_save_that_stays_silent(tmp_path):
    """Mutation: the shape that shipped until 2026-08-30."""
    mutant = tmp_path / "silent_save.py"
    mutant.write_text(
        "import streamlit as st\n"
        "def _handle_save(db, platform_key, artist_id, trigger, dag_id):\n"
        "    result = trigger.trigger_dag(dag_id, conf={'artist_id': artist_id})\n"
        "    st.success('enregistré')\n", encoding="utf-8")
    assert save_paths_without_a_probe(mutant) == ["_handle_save:2"], (
        "the guard does not see a save path that never asks for a verdict"
    )

    ok = tmp_path / "probing_save.py"
    ok.write_text(
        "import streamlit as st\n"
        "def _handle_save(db, platform_key, artist_id, trigger, dag_id):\n"
        "    result = trigger.trigger_dag(dag_id, conf={'artist_id': artist_id})\n"
        "    from src.dashboard.utils.status_matrix import run_probes_now\n"
        "    run_probes_now(db, artist_id, [platform_key])\n"
        "    st.success('enregistré')\n", encoding="utf-8")
    assert save_paths_without_a_probe(ok) == []


def test_the_probe_helper_still_remembers_its_verdict():
    """A probe whose answer is thrown away leaves the matrix as blank as before.

    That regression happened once already in the nightly loop — the comment at
    `alert_monitor.py` records it: "it used to throw the answer away after the
    email — so the artist's own screen could not show the sentence the alert
    carried."
    """
    tree = ast.parse(_MATRIX.read_text(encoding="utf-8"))
    fn = next((f for f in ast.walk(tree)
               if isinstance(f, ast.FunctionDef) and f.name == PROBE_CALL), None)
    assert fn is not None, f"{PROBE_CALL} is gone from status_matrix.py"
    saves = any(
        isinstance(n, ast.Call) and getattr(n.func, "id", "") == "save_probe"
        for n in ast.walk(fn)
    )
    assert saves, (
        f"{PROBE_CALL} no longer calls save_probe — it would run the API check and "
        "discard the answer, leaving every matrix exactly as empty as before."
    )
