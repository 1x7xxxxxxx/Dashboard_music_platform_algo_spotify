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
