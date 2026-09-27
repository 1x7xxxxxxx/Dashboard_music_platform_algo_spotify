"""R257 — the architecture catalogue stays usable: every requirement has a source, a
domain that exists, a declared status, and a proof that can actually be replayed.

Type: Test
Uses: tools/dev/arch_benchmark.py (structure_errors, verdict),
      .claude/dev-docs/architecture/{domains,requirements}.yaml

Owner, 2026-09-27 : « dans les livrables il faut identifier la méthode pour confirmer la
bonne gestion avec des tests qu'on fera sur une partie ou ligne ciblée ». A requirement whose
proof names a test that was renamed, a make target that was removed, or a domain file that
moved, would read « conforme » forever while proving nothing — this is what stops it.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("arch_benchmark",
                                               ROOT / "tools/dev/arch_benchmark.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)


def test_the_catalogue_is_well_formed_and_every_proof_resolves():
    domains, reqs = bench.load()
    assert len(domains) >= 20 and len(reqs) >= 40, "the catalogue was emptied"
    errs = bench.structure_errors(domains, reqs)
    assert not errs, "catalogue d'architecture invalide :\n" + "\n".join(errs)


def test_every_domain_of_the_map_carries_at_least_one_requirement_or_says_why():
    domains, reqs = bench.load()
    covered = {r["domaine"] for r in reqs}
    empty = sorted(set(domains) - covered)
    # Declared on purpose: these domains are product or workstation scope, their items live
    # in notes-triage.yaml as roadmap actions, not as architecture properties.
    assert set(empty) <= {"ml", "product-offer", "rag-knowledge", "pc-perf"}, empty


def test_the_detector_sees_each_defect_it_is_written_for():
    domains, _ = bench.load()
    good = {"id": "REQ-X-01", "domaine": "gold", "statut": "conforme", "sources": [{"notes": "L1"}],
            "preuve": {"pytest": "tests/test_every_metric_is_registered.py::"
                                 "test_every_metric_says_its_sense"}}
    assert bench.structure_errors(domains, [good]) == []
    cases = {
        "unknown domain": {**good, "domaine": "nowhere"},
        "no source": {**good, "sources": []},
        "missing proof file": {**good, "preuve": {"pytest": "tests/test_gone.py::test_x"}},
        "renamed test": {**good, "preuve": {"pytest": "tests/test_every_metric_is_registered.py"
                                                      "::test_that_was_renamed"}},
        "missing make target": {**good, "preuve": {"cmd": "make no-such-target"}},
        "conforme without proof": {**good, "preuve": {}},
        "bad status": {**good, "statut": "fini"},
    }
    for name, req in cases.items():
        assert bench.structure_errors(domains, [req]), f"{name} went unseen"
    twice = bench.structure_errors(domains, [good, good])
    assert any("double" in e for e in twice), "a duplicated id went unseen"
    moved = {**domains, "gold": {**domains["gold"],
                                 "fichiers": [*domains["gold"]["fichiers"], "src/moved_away.py"]}}
    assert any("moved_away" in e for e in bench.structure_errors(moved, [good])), (
        "a domain citing a file that no longer exists went unseen")


def test_a_red_proof_is_never_printed_as_conforme():
    assert bench.verdict("conforme", "rouge") == "RÉGRESSION"
    assert bench.verdict("partiel", "rouge").startswith("partiel")
    assert bench.verdict("conforme", "vert") == "conforme"
