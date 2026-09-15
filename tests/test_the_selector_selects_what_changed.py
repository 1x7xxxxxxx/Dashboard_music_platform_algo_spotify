"""Guard: `select_tests.py` must resolve this repo's import style.

Type: Utility
Uses: ast, importlib, .claude/scripts/select_tests.py
Triggers: pytest
Persists in: nothing

Error class `selector-blind-to-the-import-prefix`.

Measured 2026-08-28. `select_tests.py` returned a **byte-identical set of 19 test
files** for three unrelated changes — a collector, a dashboard view, and a util — and
that set excluded the test of the module that changed. Cross-cutting rule 16 tells you
to run that list *instead of* the whole suite, so following the rule meant skipping
exactly the tests covering your edit, while a 19/169 count made it look like real
narrowing.

Root cause, read in the code rather than guessed: `source_roots()` treats `src/` as an
import root (it contains packages), so `src/utils/x.py` was indexed as `utils.x` — but
this repo writes `from src.utils.x import …`, the git-root-relative form. The two names
never met. **59 edges resolved out of 979**: 94 % of the graph lost, every test showing
zero dependencies.

It is the same defect `source_roots()` was written to fix on 2026-07-30, in the other
direction: that day a repo wrote `from app import repo` and `src/` was added as a root
for it. Choosing ONE name breaks whichever style is not chosen; indexing every alias
breaks neither.

What this guard checks is the EFFECT — does a change to a module select that module's
test — and not the artifact (does the file exist, does it exit 0). The script's own
docstring names that distinction as the reason it exists.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Ce fichier mute un état de PROCESSUS partagé (sys.modules, un attribut de
# classe, un fichier du dépôt). Sous `--dist loadgroup` ses tests restent donc
# sur UN worker, comme le faisait `--dist loadfile` pour tout le monde.
# Voir `.claude/dev-docs/test-suite-performance.md` et R110.
pytestmark = pytest.mark.xdist_group("the-selector-selects-what-changed")

REPO = Path(__file__).resolve().parent.parent
SELECTOR = REPO / ".claude" / "scripts" / "select_tests.py"


@pytest.fixture(scope="module")
def st():
    if not SELECTOR.is_file():
        pytest.skip(f"{SELECTOR} absent")
    spec = importlib.util.spec_from_file_location("select_tests_under_test", SELECTOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def graph(st):
    roots = st.source_roots(REPO)
    imports, dynamic, unparsable, known = st.build_graph(REPO, roots)
    return imports, dynamic, known


def test_the_graph_resolves_this_repos_import_style(graph):
    """`from src.x import y` must produce an edge. It produced none.

    Pinned as a floor rather than an exact number so honest growth does not fail it,
    but far above the 59 that the broken resolution yielded — the two are not close,
    and a regression would land back near the floor, not just under it.
    """
    imports, _, _ = graph
    edges = sum(len(v) for v in imports.values())
    assert edges > 400, (
        f"the import graph resolved {edges} edges. Before the alias fix of 2026-08-28 "
        f"it resolved 59 out of 979 — every `from src.…` import dropped because "
        f"`src/` is an import root, so modules were indexed WITHOUT the prefix the "
        f"repo actually writes. If this fails, `module_aliases()` stopped indexing "
        f"every root-relative name."
    )


def test_a_test_reaches_the_module_it_imports(graph, st):
    """The concrete edge the defect destroyed, pinned by name.

    Deliberately a real pair from this repo rather than a synthetic fixture: the bug
    was invisible to any synthetic graph, because it lived in how THIS tree's roots
    interact with THIS tree's import prefix.
    """
    imports, _, _ = graph
    test_mod = st.module_name(REPO, Path(__file__), st.source_roots(REPO))
    assert test_mod in imports, f"{test_mod} is not even a node of the graph"

    target = st.module_name(
        REPO, REPO / "src" / "utils" / "alert_repetition.py", st.source_roots(REPO))
    consumer = next((m for m in imports
                     if m.endswith("test_the_same_night_twice_is_not_two_alerts")), None)
    assert consumer, "the consumer test is missing from the graph"
    assert target in imports[consumer], (
        f"{consumer} imports src/utils/alert_repetition.py but the graph does not link "
        f"them ({target!r} not in its {len(imports[consumer])} resolved deps). This is "
        "the exact edge whose absence made the selector return a constant set."
    )


def test_every_source_root_yields_an_alias(st):
    """Non-vacuity: `module_aliases` must return more than one name where roots nest.

    Without this, a `module_aliases` that silently returned a single name — the old
    behaviour — would satisfy the edge test above by luck of a different root ordering.
    """
    roots = st.source_roots(REPO)
    assert len(roots) > 1, f"expected nested import roots in this repo, got {roots}"
    aliases = st.module_aliases(REPO, REPO / "src" / "utils" / "alert_repetition.py", roots)
    assert {"src.utils.alert_repetition", "utils.alert_repetition"} <= aliases, (
        f"both the prefixed and unprefixed names must be indexed; got {sorted(aliases)}"
    )


def test_an_unimportable_path_yields_no_alias(st):
    """A directory that no `import` can name must not enter the index.

    `.claude/scripts/x.py` cannot be imported — `.claude` is not an identifier — and
    the selector relies on that fact to avoid returning the whole suite for those
    files. An alias built for them would quietly break that reasoning.
    """
    roots = st.source_roots(REPO)
    aliases = st.module_aliases(REPO, REPO / ".claude" / "scripts" / "select_tests.py", roots)
    assert all("claude" not in a.split(".")[0] for a in aliases), sorted(aliases)


# ---------------------------------------------------------------------------
# La RAISON d'un repli, pas seulement le repli — ajouté le 2026-09-15.
#
# Mesuré ce jour-là : `select_tests.py --dry` annonçait « pas un dépôt git, ou diff
# illisible » **dans ce dépôt**, pendant qu'un `audit_runner --deterministic` lançait
# ses 296 pytest sur /mnt/c. `git diff --name-only HEAD` y dépassait les 30 s du
# `timeout` de `_git`, et `except subprocess.SubprocessError` rendait exactement la
# même valeur qu'un répertoire sans `.git`.
#
# Le verdict était juste — suite entière, la direction sûre, celle que la règle
# transverse #16 demande quand le sélecteur ne peut pas conclure. C'est la RAISON qui
# mentait, et c'est elle qu'on lit : on va vérifier son dépôt au lieu de regarder la
# charge de la machine. Un diagnostic qui nomme la mauvaise cause coûte plus cher
# qu'un diagnostic absent, parce qu'on le croit et qu'on cherche là où il pointe.
#
# Même famille que la classe `a-prose-claim-that-cannot-be-verified` inscrite le même
# jour : une phrase affirme un état que rien n'a vérifié.
class _FakeTimeout:
    """Un `subprocess.run` qui expire, comme /mnt/c sous charge."""

    def __init__(self, module):
        self._module = module

    def __call__(self, cmd, **kwargs):
        raise self._module.subprocess.TimeoutExpired(cmd=cmd, timeout=30)


def test_a_git_timeout_is_not_reported_as_a_missing_repository(st, monkeypatch, tmp_path):
    """La machine chargée et le dossier sans `.git` ne doivent pas se dire pareil."""
    monkeypatch.setattr(st.subprocess, "run", _FakeTimeout(st))
    st._DERNIERE_PANNE_GIT = None

    verdict = st.select(REPO)
    raison = verdict["reason"]

    assert verdict["all"] is True, (
        "un diff illisible doit TOUJOURS rendre la suite entière — la raison change, "
        "jamais la direction du repli."
    )
    assert "30 s" in raison and "chargée" in raison, (
        f"la raison ne nomme pas le dépassement de délai : {raison!r}. C'est le "
        "message que lit l'opérateur quand le sélecteur se replie."
    )
    assert "pas un dépôt git" not in raison, (
        f"la raison accuse encore le dépôt alors que `git` a seulement expiré : {raison!r}"
    )


def test_a_directory_without_git_still_says_so(st, tmp_path):
    """Non-vacuité : le message vrai doit rester disponible pour le cas vrai.

    Sans cette moitié, on pourrait satisfaire le test précédent en supprimant toute
    mention du dépôt — et perdre le diagnostic juste le jour où il est juste.
    """
    st._DERNIERE_PANNE_GIT = None
    (tmp_path / "rien.py").write_text("x = 1\n", encoding="utf-8")

    verdict = st.select(tmp_path)

    assert verdict["all"] is True
    assert "30 s" not in verdict["reason"], (
        f"un dossier sans dépôt n'a pas expiré : {verdict['reason']!r}"
    )
    assert "git" in verdict["reason"], (
        f"la raison doit toujours nommer `git` quand c'est lui qui refuse : "
        f"{verdict['reason']!r}"
    )
