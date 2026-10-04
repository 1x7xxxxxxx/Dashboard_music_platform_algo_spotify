#!/usr/bin/env python3
"""Mutate, every night, the guards changed this week — and name the ones nothing turns red.

Type: Utility
Uses: tools/dev/mutate_guards.py (try_mutations), git log
Triggers: .github/workflows/security-nightly.yml, job `guard-mutation`
Persists in: nothing — prints a verdict per guard, exit 1 when one is suspect

Rule 15ter says « mutate a new guard before believing it », and until 2026-09-26 that was a
gesture done by hand. The same day, doing it by hand for ~30 guards found three real defects
in guards (one crashed instead of judging, one proof pointed at a renamed test, two
mutations stayed green without embodying the defect). A gesture that finds that much is a
machine's job.

What it can say, honestly: a guard that stays GREEN on every mutation it was given is a
guard nobody has seen bite — it is flagged. What it cannot say: that a RED mutation embodies
the class (a renamed identifier often breaks a guard for a trivial reason). So red is never
reported as proof; only the absence of any red is reported, as a suspicion to read.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutate_guards as mg  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
_MAX_GUARDS = 12          # each guard costs up to 7 pytest runs; the nightly is not unbounded


def changed_guards(days: int = 2) -> list[str]:
    """Guard files ADDED in the window — rule 15ter is about NEW guards (168 were merely
    modified in the week of 2026-09-26: mutating all of them is a day, not a night)."""
    out = subprocess.run(["git", "-C", str(_ROOT), "log", f"--since={days}.days", "--diff-filter=A", "--name-only",
                          "--format=", "--", "tests/test_*.py"],
                         capture_output=True, text=True).stdout.split()
    seen, keep = set(), []
    for rel in out:
        if rel not in seen and (_ROOT / rel).is_file():
            seen.add(rel)
            keep.append(rel)
    return keep


# R238 (2026-09-27) — two kinds of evidence the generic mutations cannot produce, and
# that made the job mail « 6 gardes à relire » for six guards that all bite.
#
# 1. A guard that PROVES ITSELF: a test that builds the defect and demands the detector
#    see it (`test_the_detector_sees_…`) turns red at every run, not one night in six.
# 2. A red seen BY HAND on a mutation that EMBODIES the defect — the only red that says
#    something about the class (a generic rename breaks a guard for a trivial reason).
#    Written with the mutation, never a bare « ok »: a human decided it embodies the class.
SEEN_RED: dict[str, str] = {
    "tests/test_a_creative_funnel_never_widens.py":
        "2026-09-27 — funnel_stages lit `total_results` (le résultat de l'objectif) comme "
        "clics sortants → 3 rouges",
    "tests/test_a_roi_verdict_needs_a_crossing_and_enough_points.py":
        "2026-09-27 — MIN_FIT_POINTS 5 → 2 (un ajustement sur deux points) → 2 rouges",
    "tests/test_a_floor_probability_is_never_shown_as_a_measure.py":
        "2026-09-27 — proba_affichable ne refuse plus le plancher → 16 rouges",
    "tests/test_a_lever_curve_resolves_where_the_model_responds.py":
        "2026-09-27 — _lever_grid échantillonne un levier _log LINÉAIREMENT en unités "
        "humaines (le défaut mesuré) → 7 rouges",
    "tests/test_every_quality_check_has_a_category.py":
        "2026-09-27 — un check_ du soir ajouté sans catégorie → 1 rouge ; un pointeur "
        "renommé vers une fonction absente → 2 rouges",
    # R323 (2026-09-29): the three the 09-28 night listed « à relire », re-mutated by hand.
    "tests/test_the_fleet_readiness_does_not_grow_with_tenants.py":
        "2026-09-29 — readiness_many rendu par le chemin par locataire (artist_readiness en "
        "boucle) → 15 requêtes par locataire contre une borne de 3, 1 rouge",
    "tests/test_a_release_is_benchmarked_with_its_spend.py":
        "2026-09-29 — worth_a_panel répond True sur un cadre tout à zéro → 1 rouge",
    "tests/test_engagement_stacks_actions_not_their_total.py":
        "2026-09-29 — page_interactions remis dans _ENG_STACK (l'agrégat empilé avec ce "
        "qu'il contient) → 1 rouge",
    "tests/test_skills_rules_and_injections_are_counted.py":
        "2026-10-04 — compteur de hooks sans le test de `type` dans la condition d'échec "
        "(le run annulé non compté) → 1 rouge",
    "tests/test_the_precompact_hook_saves_the_state.py":
        "2026-10-04 — court-circuit `_same_state` retiré (second instantané identique écrit) "
        "→ 1 rouge",
    "tests/test_containers_are_on_demand.py":
        "2026-10-04 — exemption `session_scoped` élargie à AutoRemove seul → 1 rouge",
    "tests/test_every_defect_kind_can_close.py":
        "2026-10-04 — un cron clos par le rc=0 de n'importe quelle étape → 1 rouge",
    "tests/test_every_harness_component_has_a_requirement.py":
        "2026-10-04 — vérification de couverture des composants retirée → 1 rouge",
    "tests/test_the_harness_report_renders_every_state.py":
        "2026-10-04 — branche « verte, non prouvée » retirée des opportunités → 1 rouge",
}


def self_proving(path: Path) -> bool:
    """Does the guard carry a test that fabricates its defect? Read in the AST."""
    import ast
    tree = ast.parse(path.read_text())
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name.startswith("test_the_detector_sees") for n in ast.walk(tree))


def verdict(result: dict) -> str | None:
    """A suspicion to report, or None. Pure: tested without running anything."""
    if "skipped" in result:
        return "rouge AVANT toute mutation — le garde ne passe pas sur l'arbre tel quel"
    if "aucune" in result and result["aucune"] > 0:
        return f"vert sur les {result['aucune']} mutation(s) essayées — personne ne l'a vu mordre"
    if "epuise" in result:
        return f"vert sur {result['epuise']} mutations, budget épuisé — personne ne l'a vu mordre"
    return None          # a red mutation, or no applicable site (nothing to conclude)


def main() -> int:
    guards, credited = [], []
    for rel in changed_guards():
        if rel in SEEN_RED:
            credited.append(f"   ✓ {rel} — vu rouge à la main : {SEEN_RED[rel]}")
        elif self_proving(_ROOT / rel):
            credited.append(f"   ✓ {rel} — auto-prouvant (il fabrique son défaut à chaque run)")
        else:
            guards.append(rel)
    if credited:
        print("\n".join(credited))
    dropped = max(0, len(guards) - _MAX_GUARDS)
    guards = guards[:_MAX_GUARDS]
    print(f"▶ {len(guards)} garde(s) ajouté(s) en 2 jours (le job tourne chaque nuit)"
          + (f" — {dropped} non mutés cette nuit (plafond {_MAX_GUARDS})" if dropped else ""))
    suspects = 0
    for rel in guards:
        v = verdict(mg.try_mutations(_ROOT / rel))
        suspects += v is not None
        print(f"   {'✗' if v else '✓'} {rel}" + (f" — {v}" if v else ""))
    print(f"{'❌' if suspects else '✅'} {suspects} garde(s) à relire")
    return 1 if suspects else 0


if __name__ == "__main__":
    raise SystemExit(main())
