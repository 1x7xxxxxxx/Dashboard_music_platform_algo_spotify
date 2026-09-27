"""What is left of the former « Algorithmes » tab: one pure helper a guard still reads.

Type: Utility
Uses: src.dashboard.utils.algo_preview_data (proba_affichable)
Triggers: tests/test_a_floor_probability_is_never_shown_as_a_measure.py
Persists in: nothing

R247 (2026-09-27, fiches 47/48/56): `_show_tab_algos` was called by no page — the router
stopped routing to it — and the owner's review found its figures only in the dossier. The
dead tab, `_show_pi_gate_section` (fiche 49, whose PI bands now feed the redesign of fiche
42) and `render_prerelease_rr_estimator` (fiche 56) are deleted. `_proba_series` stays:
the floor guard proves on it that a floor value becomes a GAP, never a level.
"""
from src.dashboard.utils.algo_preview_data import proba_affichable


def _proba_series(algo: str, values) -> list[float | None]:
    """One probability curve in %, with every floor value turned into a GAP. Pure.

    Through the shared door (`proba_affichable`): a floor point drawn at 6,5 % reads
    as a level the title sits at; it is the model saying nothing (2026-09-26).
    """
    out = []
    for v in values:
        p = proba_affichable(algo, v)
        out.append(None if p is None else p * 100)
    return out
