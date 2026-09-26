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
    # `test_a_make_target_names_the_mechanism_that_blocks.py` — AJOUTE le 2026-09-17.
    # Il ne lit AUCUN Python : son seul `read_text` porte sur le `Makefile`, et les
    # chemins `tests/….py` qu'il cite ne servent qu'a un `.exists()`. C'est exactement
    # l'exemption que le message de ce test promet (« it inspects Markdown, a Makefile,
    # a workflow ») — quatrieme fois que la promesse existe sans etre implementee pour
    # un cas de plus, apres le YAML (2026-09-05) et `importlib` (2026-09-16).
    #
    # Pourquoi une EXEMPTION et pas un correctif du predicat, alors que le depot tient
    # qu'un garde limite a son instance recidive. Le correctif general a ete cherche et
    # MESURE, trois variantes, toutes refutees — les chiffres sont la pour qu'on ne les
    # rejoue pas :
    #
    #   * « aucune LECTURE d'un `.py` suffit » (remplacer `return executed` par True) :
    #     **12 des 22 geles s'echappent**. C'est precisement la regression que la
    #     docstring de `_the_py_path_is_only_executed` annonce. L'exigence `executed`
    #     est porteuse, pas decorative.
    #   * `exists`/`is_file` ajoutes a `_RUNNERS` : 22/22 conserves, mais ce fichier
    #     reste detecte — `.exists()` porte son chemin dans le RECEVEUR, quand le
    #     predicat ne regarde que `node.args`.
    #   * la meme chose en lisant le receveur : **casse `test_the_views_map_lists_every_view.py`**
    #     et ne corrige toujours pas ce fichier.
    #
    # Le declencheur reel, mesure et non suppose : le dictionnaire `expected` du second
    # test porte de VRAIS litteraux `.py`, legitimement reconnus comme des chemins (4e
    # terme). Le trou est au 5e : ces chemins sont SONDES, jamais ouverts, et la
    # teinture ne se propage pas a travers une variable de boucle issue d'un `dict`.
    # Le combler demande une analyse de teinture dans un predicat partage par 22
    # entrees gelees — hors de proportion avec le gain. **C'est le reste connu de ce
    # cliquet** ; quiconque touche `_the_py_path_is_only_executed` devrait commencer la.
    "test_a_make_target_names_the_mechanism_that_blocks.py",
    "test_canary_onboarding_walk.py",
    "test_claude_config_floor.py",
    "test_env_is_root_anchored.py",
    "test_every_dev_doc_is_reachable.py",
    "test_i18n.py",
    # `test_i18n_orphans.py` est sorti de cette liste le 2026-09-18 : ses deux gardes
    # neufs lisent l'AST (les `t(clé, défaut)` extraits par `ast.walk`), et le cliquet
    # l'a signalé de lui-même. Un cliquet qui se resserre tout seul est le seul qui
    # reste un cliquet — laissé en place, il aurait été du budget pour un futur garde
    # textuel que personne n'aurait décidé d'autoriser.
    "test_identity_fields_collectable.py",
    # `test_only_production_puts_mail_on_the_wire.py` EST SORTI le 2026-09-17, et sans
    # qu'une ligne de ce fichier-la change : il EXECUTE `tools/check_env_parity.py` par
    # `importlib` et ne lit en TEXTE qu'un `.sh`. Il n'a jamais ete un garde textuel —
    # le predicat ne savait pas reconnaitre `importlib` comme une execution. La liste
    # retrecit parce que la MESURE s'est corrigee, pas le depot.
    "test_operational_scripts_are_reachable_in_containers.py",
    "test_os_hints.py",
    "test_probes_scoped_to_repo.py",
    "test_the_views_map_lists_every_view.py",
    # `test_view_connection_budget.py` est SORTI de cette liste le 2026-09-05 :
    # il comptait les connexions par expression régulière et se déclenchait sur un
    # COMMENTAIRE qui citait `get_db_connection()`. Il lit l'AST maintenant.
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
    # `tokenize` EST une lecture structurelle, et c'est la SEULE possible pour un
    # commentaire : l'AST de Python les jette. Un garde qui veut lire « les commentaires
    # en tant que commentaires » ne peut pas passer par `ast`, et l'y contraindre
    # reviendrait à interdire la question.
    #
    # Ajouté le 2026-09-18 pour `test_a_comment_names_a_test_that_exists.py` (R141), qui
    # lit le flux de jetons pour ne PAS attraper un chemin cité dans du code ou une
    # chaîne. Mesuré avant de l'écrire, parce que desserrer un cliquet se mesure :
    # **22 gelées sur 22 restent détectées** avec cette exemption, et seuls **trois**
    # fichiers de tests utilisent `tokenize` dans tout le dépôt. Elle n'ouvre donc pas
    # de budget — elle nomme un outil que le premier terme avait simplement oublié.
    #
    # ⚠️ **Brèche connue, et elle n'est pas neuve.** Un fichier qui écrit `tokenize.`
    # n'importe où est exempté, même s'il compare ensuite des chaînes — vérifié en
    # fabriquant une sonde purement textuelle : rouge sans le mot, verte avec. La MÊME
    # évasion existe depuis toujours pour `ast.parse`, qu'il suffit d'écrire dans un
    # commentaire. La fermer demanderait de prouver que l'outil s'applique au contenu LU,
    # c'est-à-dire une analyse de teinture — le correctif que `_TEXTUAL_GUARDS` documente
    # comme hors de proportion après trois tentatives mesurées. Ce prédicat est une
    # heuristique qui rend le geste facile à faire et le contournement visible, pas une
    # preuve.
    if "tokenize." in body:
        return False
    # DÉLÉGUER LA LECTURE STRUCTURELLE N'EST PAS LA PERDRE. Depuis le 2026-09-12,
    # `tests/nav_source.py` est le seul endroit qui sait où vit la déclaration du
    # menu et l'évalue par `ast` — neuf gardes la lisaient chacun à sa façon, et le
    # déménagement de la constante hors d'`app.py` les a tous cassés le même jour.
    # Un garde qui l'importe fait donc EXACTEMENT ce que ce fichier demande, une
    # fois de moins ; sans cette ligne, le cliquet pousserait à recopier un
    # `ast.parse` décoratif dans chacun pour le faire taire.
    if "nav_source import" in body:
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
        tree = _ast.parse(body)
    except SyntaxError:
        return True
    if not _a_py_literal_is_used_as_a_path(tree):
        return False
    # Cinquieme terme, 2026-09-16 : le `.py` est un chemin — mais est-il LU, ou LANCE ?
    return not _the_py_path_is_only_executed(tree)


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


def _the_py_path_is_only_executed(tree) -> bool:
    """Le seul `.py` du fichier est-il passe a `subprocess`, et jamais ouvert ?

    Ajoute le 2026-09-16, meme motif que le quatrieme terme et meme cause : le predicat
    exigeait un `read_text(` ET un chemin `.py` sans demander si les deux se
    RENCONTRENT. `tests/test_the_night_protocol_is_runnable.py` a ete refuse pour ca —
    il lit un Markdown et un Makefile, et son unique litteral `.py` est le script qu'il
    EXECUTE, jamais ouvert. Le message du cliquet promet cette exemption mot pour mot
    (« it inspects Markdown, a Makefile, a workflow ») ; elle n'etait pas implementee
    pour ce cas, exactement comme pour le YAML le 2026-09-05.

    ⚠️ Une premiere version, plus large, demandait « un `read_text` a-t-il pour receveur
    un nom portant un `.py` ? ». Elle faisait SORTIR **huit** gardes geles — et ils
    lisent bel et bien du Python : `(ROOT / rel).read_text()` ou `rel` parcourt une
    liste de `.py`, une propagation que l'analyse ne suivait pas. `test_the_frozen_list_
    does_not_rot` l'a refusee, ce qui est tout l'interet de l'avoir. Le terme retenu est
    donc le plus etroit qui couvre le cas reel : il faut un appel `subprocess` PORTANT
    le `.py`, et aucune lecture de ce meme `.py`. Les huit ne lancent aucun subprocess,
    donc rien ne bouge pour eux — remesure : les 27 geles restent detectes.
    """
    # ⚠️ `importlib` ajoute le 2026-09-17, sur deux fichiers refuses a tort. Le raisonnement
    # de cette exemption est « le `.py` est EXECUTE, pas lu » — et `spec_from_file_location`
    # + `exec_module` execute tout autant qu'un `subprocess`. Ne connaitre que `subprocess`
    # etait une liste de VERBES la ou la question porte sur le geste, exactement le defaut
    # que `a-kill-pattern-that-matches-its-own-shell` a coute trois fois le 2026-09-16.
    _RUNNERS = {"run", "check_output", "check_call", "call", "Popen",
                "spec_from_file_location", "exec_module", "module_from_spec"}

    def _carries_py(node) -> bool:
        return any(isinstance(sub, _ast.Constant) and isinstance(sub.value, str)
                   and sub.value.endswith(".py") for sub in _ast.walk(node))

    tainted = {
        target.id
        for node in _ast.walk(tree) if isinstance(node, _ast.Assign)
        for target in node.targets
        if isinstance(target, _ast.Name) and _carries_py(node.value)
    }

    def _mentions_py(node) -> bool:
        if _carries_py(node):
            return True
        return any(isinstance(sub, _ast.Name) and sub.id in tainted
                   for sub in _ast.walk(node))

    executed = False
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, _ast.Attribute) else getattr(fn, "id", "")
        if name in _RUNNERS and any(_mentions_py(a) for a in node.args):
            executed = True
        if name in {"read_text", "read_bytes", "getsource"}:
            subject = node.args[0] if name == "getsource" and node.args else (
                fn.value if isinstance(fn, _ast.Attribute) else None)
            if subject is not None and _mentions_py(subject):
                return False
    return executed


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
        # ⚠️ `code_of()` N'EST PAS UN LECTEUR DE PROSE, et l'ignorer créait une
        # CONTRADICTION entre deux gardes de la même famille — trouvée le 2026-09-22.
        #
        # `tests/code_text.code_of` retire commentaires et docstrings : c'est
        # exactement le remède que `test_a_presence_assertion_is_not_satisfied_by_prose`
        # PRESCRIT dans son message d'échec (« Lire `tests.code_text.code_of(<chemin>)`
        # au lieu de `<chemin>.read_text()` »). Ce garde-ci le signalait quand même,
        # parce que son argument est une constante de chemin `.py`.
        #
        # Un auteur devait donc choisir LEQUEL des deux gardes satisfaire, et aucun
        # choix n'était bon. Une comparaison contre la sortie de `code_of` ne peut pas
        # être satisfaite par un commentaire — il n'y en a plus dedans — donc ce n'est
        # pas la forme que ce garde existe pour refuser.
        if "code_of" in src:
            continue
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
    # 2 → 0 le 2026-09-22 : ce fichier lit par `code_of()`, que ce garde ignore
    # désormais (voir `_text_assertions_on_source`). Ses deux assertions n'étaient
    # jamais des comparaisons contre de la PROSE ; le prédicat ne savait pas le voir.
    "test_a_probe_says_when_it_cannot_see.py": 0,
    "test_a_sandbox_tenant_may_hold_its_owners_identity.py": 1,
    "test_a_timestamptz_column_survives_daylight_saving.py": 0,
    "test_a_view_opens_on_one_decision.py": 1,
    "test_alert_delivery_is_proven.py": 1,
    "test_an_error_leaves_a_row.py": 5,
    "test_audit_scope_is_derived.py": 1,  # 2 → 1 le 2026-09-25 (prédicat extrait, R169)
    "test_central_apps_are_monitored.py": 4,
    "test_expected_silence.py": 2,
    "test_freshness_measures_the_right_column.py": 1,
    "test_freshness_uses_one_clock.py": 1,
    "test_identity_has_no_env_fallback.py": 1,
    "test_no_detector_is_written_and_never_called.py": 0,
    "test_no_except_swallows_the_interrupt.py": 1,
    "test_one_door_onto_the_database.py": 1,
    "test_one_email_path_for_freshness.py": 1,
    "test_tenant_scope_is_not_view_session.py": 2,
    "test_the_alert_names_a_workable_action.py": 2,
    "test_the_credentials_page_asks_before_it_reports.py": 2,
    # 2 → 0 le 2026-09-21. Les deux assertions textuelles cherchaient
    # `"def secondary_analyses("` et `"expanded=False"` dans le source de
    # `ui.py`. La seconde est passée ROUGE le jour où la fonction a gagné un
    # paramètre `expanded: bool = False` — le défaut était toujours `False`,
    # donc la propriété gardée toujours vraie : le garde parlait de
    # l'orthographe. Les deux lisent désormais l'AST.
    "test_the_dense_views_use_the_pattern_written_for_them.py": 0,
    "test_the_digest_is_a_paid_feature.py": 1,
    "test_the_error_boundary_covers_everything.py": 1,
    "test_the_first_look_does_not_cry_wolf.py": 1,
    "test_the_guide_is_fetchable_not_only_mailed.py": 1,
    "test_the_guide_tells_the_artist_only_what_is_theirs.py": 1,
    "test_the_http_escape_hatch_stays_narrow.py": 2,
    "test_the_language_choice_survives_a_logout.py": 1,
    "test_the_menu_says_what_each_page_is.py": 1,
    "test_the_pdf_says_what_the_screen_says.py": 2,
    "test_the_setup_asks_only_what_it_needs.py": 1,
    "test_the_setup_guide_is_reachable.py": 3,
    "test_the_setup_page_is_reachable_and_on_top.py": 23,
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


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path):
    """Non-vacuity on FABRICATED guards: one that reads a Python FILE and searches its
    text (the shape that went green on its own comment four times) is flagged; the same
    read through `ast.parse` is not; a guard reading a Makefile has no tree to prefer."""
    textual = tmp_path / "test_textual.py"
    textual.write_text(
        "from pathlib import Path\n"
        "def test_x():\n"
        "    body = (Path('src') / 'app.py').read_text()\n"
        "    assert 'view_session(' in body\n", encoding="utf-8")
    structural = tmp_path / "test_structural.py"
    structural.write_text(textual.read_text(encoding="utf-8").replace(
        "    assert 'view_session(' in body\n",
        "    import ast\n    assert ast.parse(body)\n"), encoding="utf-8")
    makefile = tmp_path / "test_makefile.py"
    makefile.write_text(
        "from pathlib import Path\n"
        "def test_x():\n"
        "    assert 'check-env' in Path('Makefile').read_text()\n", encoding="utf-8")
    assert _reads_source_textually(textual)
    assert not _reads_source_textually(structural)
    assert not _reads_source_textually(makefile)
