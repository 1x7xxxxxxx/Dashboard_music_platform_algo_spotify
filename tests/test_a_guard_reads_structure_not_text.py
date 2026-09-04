"""A guard that only reads TEXT is blind, and this ratchet stops the set from growing.

Type: Test
Uses: pathlib
Depends on: tests/*.py
Persists in: nothing

What was measured
-----------------
2026-08-30, on this suite: 111 test files read the source of `src/`, 81 of them parse
it. The remaining ones match strings — and four were caught being blind the same
evening, each on the very defect it existed to catch:

  * "does the function call is_admin()?" — green while the fleet badge was ungated,
    because the SAME function calls is_admin() twenty lines earlier for another reason;
  * `"NOT_LAUNCHED_KEY" in source` — green while the constant was disconnected, because
    the name survived in the other functions of the module;
  * `"_page_mirrored" in source` — green while the condition was removed, because the
    name survived in a comment;
  * `"is_sandbox" in source` — green while the flag left the predicate, because the
    module's docstring names it four times.

The pattern is the same each time: a name appearing somewhere in a file says nothing
about what the code DOES with it. Worse, a textual guard also breaks on innocent
rewording, so it is brittle AND blind — the only combination with no upside.

What this asserts
-----------------
Not that the existing ones are fixed: converting 32 files at once would be a change
nobody can review. It asserts the set does not GROW. A new guard reads the AST, or it
does not get written.

To convert one: delete its name below and make it parse. To add a genuinely textual
check — a Markdown document, a Makefile, a YAML workflow — nothing here applies, since
this only counts tests that read Python under `src/`.
"""
from __future__ import annotations

from pathlib import Path

_TESTS = Path(__file__).resolve().parent

# Frozen 2026-08-30. This list may only ever get SHORTER.
# 2026-09-04 : passée de 32 à 21. Onze entrées n'ont pas été « autorisées » puis
# oubliées — elles ne relevaient JAMAIS de ce cliquet : elles gardent des migrations
# SQL, un Makefile, des workflows CI, la ROADMAP. Le prédicat les attrapait par
# excès de portée, et les avoir listées donnait du budget à un futur garde textuel
# sur du Python que personne n'aurait décidé d'admettre.
_TEXTUAL_GUARDS = {
    "test_a_guide_never_asks_for_a_dead_uri.py",
    "test_a_mirrored_identity_is_seen_by_every_reader.py",
    "test_a_tenant_flag_is_applied_everywhere.py",
    "test_alert_subject_names_the_tenant.py",
    "test_allowed_tables_coverage.py",
    "test_an_artist_never_reads_our_plumbing.py",
    "test_api_partial_dates.py",
    "test_canary_onboarding_walk.py",
    "test_claude_config_floor.py",
    "test_env_is_root_anchored.py",
    "test_every_dag_imports.py",
    "test_every_dev_doc_is_reachable.py",
    "test_i18n.py",
    "test_i18n_orphans.py",
    "test_identity_fields_collectable.py",
    "test_only_production_puts_mail_on_the_wire.py",
    "test_operational_scripts_are_reachable_in_containers.py",
    "test_os_hints.py",
    "test_probes_scoped_to_repo.py",
    "test_the_views_map_lists_every_view.py",
    "test_view_connection_budget.py",
}


def _reads_source_textually(path: Path) -> bool:
    """Lit-il du code PYTHON par correspondance de chaînes ?

    Le troisième terme a été ajouté le 2026-09-04 : sans lui, le prédicat attrapait
    tout fichier lisant un fichier quelconque. Il a refusé un garde qui compare les
    `COPY` d'un **Dockerfile** aux répertoires que le code résout — alors que le
    message de ce test promet exactement cette exemption : « If this file really
    cannot parse (it inspects Markdown, a Makefile, a workflow), it does not trip
    this test at all ». La promesse était écrite, elle n'était pas implémentée.

    Ce que le cliquet vise est précis : inspecter du Python par le TEXTE, là où
    `ast` répond mieux. Un Dockerfile, un Makefile ou un Markdown n'ont pas d'arbre —
    les y interdire ne protège rien et pousse à recopier une liste blanche.
    """
    body = path.read_text(encoding="utf-8")
    if "ast.parse" in body or "ast.walk" in body:
        return False
    if "read_text(encoding" not in body:
        return False
    # Nomme-t-il des fichiers Python ? `".py"` couvre les deux formes utilisées ici :
    # un chemin littéral (`… / "app.py"`) et un balayage (`rglob("*.py")`).
    return '.py"' in body or ".py'" in body


def test_no_new_textual_guard_is_added():
    current = {p.name for p in sorted(_TESTS.glob("test_*.py"))
               if _reads_source_textually(p)}
    added = current - _TEXTUAL_GUARDS
    assert not added, (
        "new test file(s) inspect source code by matching strings instead of parsing "
        f"it: {sorted(added)}\n\n"
        "Four such guards were caught being green on the very defect they existed to "
        "catch, in a single evening — a name present in a file says nothing about what "
        "the code does with it, and a comment or a docstring is enough to satisfy the "
        "match. Use `ast.parse` and ask the structural question.\n"
        "If this file really cannot parse (it inspects Markdown, a Makefile, a "
        "workflow), it does not trip this test at all — check what it actually reads."
    )


def test_the_frozen_list_does_not_rot():
    """A name that no longer matches must leave the list, or the ratchet loosens."""
    current = {p.name for p in sorted(_TESTS.glob("test_*.py"))
               if _reads_source_textually(p)}
    stale = _TEXTUAL_GUARDS - current
    assert not stale, (
        f"these files are no longer textual guards: {sorted(stale)}\n"
        "Remove them from _TEXTUAL_GUARDS. Left in place they are budget for a future "
        "textual guard nobody decided to allow — which is how a ratchet stops being one."
    )
