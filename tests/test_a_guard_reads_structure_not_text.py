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

import ast as _ast
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
    # ── Révélés le 2026-09-04, pas ajoutés ──────────────────────────────────
    # Ces trois-là étaient déjà des gardes textuels ; le prédicat ne les voyait pas.
    # `test_export_views_generate` échappait sur un `read_text(` coupé en deux lignes
    # (la sous-chaîne cherchée était `read_text(encoding`), les deux autres sur
    # `inspect.getsource()`, que le prédicat ignorait entièrement. Les inscrire ne
    # desserre rien : ils comptaient déjà dans la dette, sans être comptés.
    "test_export_views_generate.py",
    "test_identity_conflict_names_no_other_tenant.py",
    "test_ml_inference.py",
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
    # `read_text(` et non `read_text(encoding` : un appel coupé sur deux lignes
    # (`read_text(\n    encoding="utf-8")`) cassait la sous-chaîne contiguë et
    # exemptait le fichier entier. Un site y échappait pour cette seule raison.
    if "read_text(" not in body and "getsource(" not in body:
        return False
    # Nomme-t-il des fichiers Python ? `".py"` couvre les deux formes utilisées ici :
    # un chemin littéral (`… / "app.py"`) et un balayage (`rglob("*.py")`).
    if not ('.py"' in body or ".py'" in body):
        return False
    # Quatrieme terme, 2026-09-05 : ce `.py` est-il un fichier LU, ou une chaine
    # CHERCHEE ? Voir `_a_py_literal_is_used_as_a_path`.
    try:
        return _a_py_literal_is_used_as_a_path(_ast.parse(body))
    except SyntaxError:
        return True


def _a_py_literal_is_used_as_a_path(tree) -> bool:
    """Le `.py` de ce fichier est-il un fichier LU, ou juste une chaine cherchee ?

    Ajoute le 2026-09-05. Les trois termes precedents ne demandaient que « le mot
    `.py` apparait quelque part » — le meme exces de portee qui avait fait lister
    onze gardes de SQL, de Makefile et de workflows le 2026-09-04. Il s'est
    reproduit sur `test_the_rex_gate_runs_before_the_push.py`, qui ne lit que deux
    YAML (`.pre-commit-config.yaml`, `.github/workflows/ci.yml`) et ne portait `.py`
    que parce que l'outil qu'il verifie s'appelle `validate_rex.py` : le nom
    cherche, jamais le fichier ouvert. Le cliquet promet cette exemption dans son
    propre docstring (« a YAML workflow — nothing here applies ») ; elle n'etait pas
    implementee.

    Un litteral `.py` designe un chemin quand il porte un separateur ou un joker
    (`"src/dashboard/app.py"`, `"*.py"`), quand il vit dans un `Path()`, un `/`, un
    `glob`/`rglob`, ou quand il est l'element d'une collection de noms de fichiers
    (`("credential_guides.py", ...)`, jointe plus loin sur un repertoire — la forme
    que prennent quatre des gardes geles). Il ne designe rien quand il est affecte
    seul et compare par `in`.

    Mesure sur les 24 gardes geles : les 24 restent detectes, et seul le garde YAML
    sort. `test_the_frozen_list_does_not_rot` echoue au premier qui sortirait — ce
    resserrement ne peut donc pas relacher le cliquet sans le dire.
    """
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Constant) and isinstance(node.value, str):
            v = node.value
            if v.endswith(".py") and ("/" in v or "*" in v):
                return True
    for node in _ast.walk(tree):
        if not any(isinstance(sub, _ast.Constant) and isinstance(sub.value, str)
                   and sub.value.endswith(".py") for sub in _ast.walk(node)):
            continue
        if isinstance(node, _ast.BinOp) and isinstance(node.op, _ast.Div):
            return True
        if isinstance(node, (_ast.Tuple, _ast.List, _ast.Set)):
            return True
        if isinstance(node, _ast.Call):
            fn = node.func
            if isinstance(fn, _ast.Attribute) and fn.attr in {"glob", "rglob", "joinpath"}:
                return True
            if isinstance(fn, _ast.Name) and fn.id in {"Path", "open"}:
                return True
    return False


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


# ── Le trou du cliquet : un fichier exempté EN BLOC ──────────────────────────

def _text_assertions_on_source(path: Path) -> list[int]:
    """Les `assert "<litt>" in <nom>` où `<nom>` porte du SOURCE lu textuellement.

    Le prédicat du cliquet est au niveau du FICHIER : dès qu'un `ast.parse` y
    apparaît, tout le fichier est exempté. Trois gardes ont été pris au vert sur leur
    propre défaut le 2026-09-04 ; le troisième vivait dans un fichier déjà « à jour »,
    qui parse ailleurs et comparait des chaînes ici. Le fichier était exempté ;
    l'assertion ne l'était pas.

    On cherche donc la FORME, assertion par assertion : un `in` dont le membre droit
    est une variable assignée depuis `read_text`, `get_source_segment` ou une fonction
    dont le nom finit par `_src`.
    """
    import ast as _ast

    tree = _ast.parse(path.read_text(encoding="utf-8"))

    # Les CONSTANTES du module qui désignent un fichier Python : `_APP = _ROOT /
    # "src" / "dashboard" / "app.py"`. Sans elles, le prédicat ne voyait que les
    # chemins écrits en toutes lettres dans l'assertion — c'est-à-dire le cas rare.
    # Trouvé en MUTANT ce garde : la sonde qu'on lui a soumise, écrite exactement
    # comme les trois défauts d'origine, ne le faisait pas rougir.
    py_paths: set[str] = set()
    for node in _ast.walk(tree):
        if (isinstance(node, _ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], _ast.Name)
                and ".py" in _ast.dump(node.value)):
            py_paths.add(node.targets[0].id)

    holders: set[str] = set()
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, _ast.Name):
            continue
        src = _ast.dump(node.value)
        # `inspect.getsource(fn)` rend le texte de la fonction — docstring et
        # commentaires COMPRIS. C'est exactement la même lecture qu'un `read_text`,
        # et le prédicat ne la voyait pas : trois sites y échappaient entièrement
        # (balayage sibling-sweeper du 2026-09-04).
        if "getsource" in src:
            holders.add(target.id)
            continue
        # `get_source_segment` ne rend QUE du Python. Un `read_text` ne compte que si
        # le chemin nomme un `.py` : la moitié des tests de ce dépôt lisent du SQL,
        # du shell, du Markdown ou du YAML, où il n'y a pas d'arbre à interroger et
        # où la comparaison de chaînes est le seul outil possible. Les y interdire
        # n'empêcherait aucun défaut et pousserait à recopier une liste blanche.
        reads_python = "get_source_segment" in src or (
            "read_text" in src
            and (".py" in src
                 # Sans la parenthèse fermante : `ast.dump` écrit
                 # `Name(id='_APP', ctx=Load())` sur certaines versions et
                 # `Name(id='_APP')` sur d'autres. La chercher rendait le prédicat
                 # muet — trouvé en MUTANT ce garde, pas en le relisant.
                 or any(f"Name(id='{n}'" in src for n in py_paths)))
        if reads_python:
            holders.add(target.id)

    bad: list[int] = []
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Assert):
            continue
        for cmp_ in _ast.walk(node.test):
            if not isinstance(cmp_, _ast.Compare):
                continue
            if not any(isinstance(o, (_ast.In, _ast.NotIn)) for o in cmp_.ops):
                continue
            left_is_literal = isinstance(cmp_.left, _ast.Constant)
            right = cmp_.comparators[0] if cmp_.comparators else None
            # `x in y[a:b]` compte aussi : c'est la forme `block = body[i:i+1400]`.
            base = right
            while isinstance(base, _ast.Subscript):
                base = base.value
            if left_is_literal and isinstance(base, _ast.Name) and base.id in holders:
                bad.append(node.lineno)
    return sorted(set(bad))


# L'inventaire GELÉ des assertions qui comparent une chaîne au source Python, par
# fichier. Mesuré le 2026-09-04 : 29 fichiers, 64 assertions. Chaque nombre ne peut
# que DIMINUER — c'est un cliquet, pas une autorisation.
#
# Pourquoi un cliquet et pas zéro : la classe est réelle mais son stock est ancien,
# et exiger zéro aujourd'hui bloquerait la suite entière sur un travail qui n'a rien
# à voir avec le changement en cours. Ce qui compte est qu'elle cesse de CROÎTRE —
# les trois occurrences du 2026-09-04 étaient toutes neuves.
_TEXT_ASSERTIONS_ON_PY: dict[str, int] = {
    "test_a_backup_survives_its_disk.py": 12,
    "test_a_dependency_gate_cannot_hide_a_break.py": 2,
    "test_a_label_signed_artist_is_collectable.py": 2,
    "test_a_link_is_enough_to_identify_a_tenant.py": 1,
    "test_a_probe_says_when_it_cannot_see.py": 2,
    "test_a_sandbox_tenant_may_hold_its_owners_identity.py": 1,
    "test_a_timestamptz_column_survives_daylight_saving.py": 2,
    "test_a_view_opens_on_one_decision.py": 1,
    "test_alert_delivery_is_proven.py": 1,
    "test_an_error_leaves_a_row.py": 5,
    "test_audit_scope_is_derived.py": 3,
    "test_central_apps_are_monitored.py": 4,
    "test_expected_silence.py": 2,
    "test_freshness_measures_the_right_column.py": 1,
    "test_freshness_uses_one_clock.py": 1,
    "test_identity_has_no_env_fallback.py": 1,
    "test_no_detector_is_written_and_never_called.py": 2,
    "test_no_except_swallows_the_interrupt.py": 1,
    "test_one_door_onto_the_database.py": 2,
    "test_one_email_path_for_freshness.py": 1,
    "test_tenant_scope_is_not_view_session.py": 2,
    "test_the_alert_names_a_workable_action.py": 2,
    "test_the_credentials_page_asks_before_it_reports.py": 2,
    "test_the_dense_views_use_the_pattern_written_for_them.py": 2,
    "test_the_digest_is_a_paid_feature.py": 3,
    "test_the_error_boundary_covers_everything.py": 1,
    "test_the_first_look_does_not_cry_wolf.py": 1,
    "test_the_guide_is_fetchable_not_only_mailed.py": 6,
    "test_the_guide_tells_the_artist_only_what_is_theirs.py": 1,
    "test_the_http_escape_hatch_stays_narrow.py": 2,
    "test_the_language_choice_survives_a_logout.py": 1,
    "test_the_menu_says_what_each_page_is.py": 1,
    "test_the_pdf_says_what_the_screen_says.py": 2,
    "test_the_setup_asks_only_what_it_needs.py": 1,
    "test_the_setup_guide_is_reachable.py": 3,
    "test_the_setup_page_is_reachable_and_on_top.py": 25,
    "test_the_soundcloud_ask_is_one_thing.py": 1,
    "test_the_trigger_rate_compares_the_same_ruler.py": 1,
    "test_two_checks_one_question.py": 7,
}


def test_no_new_assertion_compares_strings_against_source_text():
    """La forme, pas le fichier — c'est le trou par lequel trois gardes sont passés.

    Un `assert "<nom de symbole>" in <source du fichier>` est vrai dès que le nom
    apparaît quelque part : un commentaire, une docstring, une autre fonction. Les
    trois pris le 2026-09-04 accusaient chacun un COMMENTAIRE, dont deux fois celui
    qui expliquait le correctif qu'ils devaient valider.

    Le cliquet du haut de fichier ne les voyait pas : son prédicat est au niveau du
    FICHIER, et dès qu'un `ast.parse` y apparaît, tout le fichier est exempté. Le
    troisième vivait dans un fichier qui parse ailleurs et comparait des chaînes ici.
    """
    current: dict[str, int] = {}
    for path in sorted(_TESTS.glob("test_*.py")):
        if path.name in _TEXTUAL_GUARDS:
            continue           # déjà admis en bloc, décision prise ailleurs
        found = _text_assertions_on_source(path)
        if found:
            current[path.name] = len(found)

    grew = {n: (c, _TEXT_ASSERTIONS_ON_PY.get(n, 0))
            for n, c in current.items() if c > _TEXT_ASSERTIONS_ON_PY.get(n, 0)}
    assert not grew, (
        "Ces fichiers ont GAGNÉ des assertions qui comparent une chaîne au texte "
        "d'un source Python :\n  "
        + "\n  ".join(f"{n} : {c} (gelé à {was})" for n, (c, was) in sorted(grew.items()))
        + "\n\nElles sont satisfaites par un commentaire ou une docstring — trois "
          "gardes ont été pris au vert sur leur propre défaut le 2026-09-04, dont "
          "deux sur le commentaire expliquant le correctif. Passe par `ast` et "
          "interroge la structure : quel NOM le code lit-il vraiment ?"
    )


def test_the_text_assertion_inventory_does_not_rot():
    """Un nombre gelé au-dessus du réel est du budget pour une future régression."""
    current: dict[str, int] = {}
    for path in sorted(_TESTS.glob("test_*.py")):
        if path.name in _TEXTUAL_GUARDS:
            continue
        found = _text_assertions_on_source(path)
        if found:
            current[path.name] = len(found)

    stale = {n: (v, current.get(n, 0)) for n, v in _TEXT_ASSERTIONS_ON_PY.items()
             if current.get(n, 0) < v}
    assert not stale, (
        "Ces entrées gelées sont plus hautes que la réalité — descends-les :\n  "
        + "\n  ".join(f"{n} : gelé {v}, réel {c}" for n, (v, c) in sorted(stale.items()))
        + "\n\nLaissé tel quel, l'écart est du budget pour une régression que "
          "personne n'aurait décidé d'admettre."
    )
