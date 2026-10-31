"""Garde : `audit_runner.py` charge le compteur `tools/dev/error_class_health.py` PAR CHEMIN.

Type: Test
Uses: importlib, sys.modules, .claude/scripts/audit_runner.py
Triggers: pytest
Persists in: nothing

Pourquoi (R678, courrier du parc msg:1793471803914610114-1615975, T219 du master)
---------------------------------------------------------------------------------
Importé PAR NOM après `sys.path.insert(tools/dev)`, le compteur perd contre tout homonyme
déjà présent dans `sys.modules` ou plus tôt sur le chemin. Le payload du parc livre un
`error_class_health.py` (le GÉNÉRATEUR du document, un autre module) à côté de
`audit_runner.py` : dans 9 dépôts sur 13, la porte répondait « illisible (cannot import
name '_blocks') » et sortait 1 sans rien juger.

Le test plante l'homonyme là où un import par nom le prendrait, puis appelle les deux
lecteurs du compteur (`proof_gaps`, `_sweep_verdict`) : ils doivent juger, pas planter.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_RUNNER = ROOT / ".claude" / "scripts" / "audit_runner.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("audit_runner_r678", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_homonym_counter_module_does_not_blind_the_gate(
        monkeypatch: object, capsys: object) -> None:
    homonym = types.ModuleType("error_class_health")  # the generator: none of the predicates
    monkeypatch.setitem(sys.modules, "error_class_health", homonym)
    runner = _load_runner()

    gaps = runner.proof_gaps({"siblings": "swept:2026-10-31 — 3 candidats → **2 sites vivants**"},
                             exists=lambda p: True)
    assert not any("sweep" in g for g in gaps), gaps

    runner._sweep_verdict([])
    out = capsys.readouterr().out
    assert "illisible" not in out and "absent de ce dépôt" not in out, out
