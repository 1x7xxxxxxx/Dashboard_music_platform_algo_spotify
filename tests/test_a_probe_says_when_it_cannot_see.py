"""Guard: a journey probe never turns "I cannot read this" into "it is not there".

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Error class `probe-reads-unreadable-as-absent`.

Measured 2026-09-03, and it accused the product of a defect it did not have.

`make artist-firstlook` reported `upload_csv` as a **CUL-DE-SAC** — "rien à cliquer,
saisir ou télécharger sur cette page" — on the page that carries a `st.file_uploader`
and has a **0-out-of-4** completion rate among invited artists. The page was fine.

The chain:

* the Makefile ran the tool under the **system** `python3`, which carries Streamlit
  **1.54**; the venv the suite uses carries **1.62**;
* on 1.54, `AppTest` has no `file_uploader` attribute at all — `getattr` raises;
* `_has_any` caught that with `except: continue` and returned `False`;
* `False` fed straight into `dead_end`, and the tool printed a verdict.

Two distinct defects, and both had to be fixed or the next Streamlit bump reopens it:
the interpreter (`tests-run-a-different-core-than-prod`) and the collapse of *unknown*
into *no* (`broken-probe-rendered-as-user-fault`, one layer up — here the false fault
was pinned on the product rather than on the user).

It is worth being precise about the cost: this verdict pointed at the exact page a
real onboarding defect would matter most on, and it was wrong. A probe that cries wolf
about the most important page teaches its reader to discount it.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
TOOL = REPO / "tools" / "artist_first_look.py"
MAKEFILE = REPO / "Makefile"


def test_the_probe_reports_what_it_could_not_read():
    """`_has_any` must hand back the unreadable accessors, not swallow them."""
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_has_any"), None)
    assert fn is not None, "_has_any is gone — this guard points at air"

    returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
    assert returns, "_has_any returns nothing"
    assert any(isinstance(r.value, ast.Tuple) for r in returns), (
        "_has_any returns a bare boolean again. It cannot then distinguish "
        "'this Streamlit exposes no such accessor' from 'the page has none', and the "
        "second reading produces a false CUL-DE-SAC verdict."
    )


def test_a_dead_end_verdict_requires_every_accessor_to_be_readable():
    """The verdict must be withheld when anything was unreadable."""
    src = TOOL.read_text(encoding="utf-8")
    tree = ast.parse(src)
    node = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and n.value == "dead_end"), None)
    assert node is not None, "no dead_end key in the tool's result"
    # The whole expression assigned to "dead_end", read from source.
    line = src.splitlines()[node.lineno - 1: node.lineno + 3]
    joined = " ".join(line)
    assert "unreadable" in joined, (
        "the dead_end verdict no longer accounts for unreadable accessors: an "
        "AttributeError from an older Streamlit becomes 'nothing to click', which is "
        "how `upload_csv` was falsely accused on 2026-09-03."
    )


def test_the_journey_tools_do_not_run_on_the_system_interpreter():
    """The Makefile must use the same interpreter as the suite.

    `python3` here is Streamlit 1.54; the venv is 1.62. Two interpreters, two answers,
    and the tool is the one an operator trusts before inviting a real artist.
    """
    tools = ("tools/artist_first_look.py", "tools/artist_preflight.py",
             "tools/tenant_contamination_check.py")
    # Continuation lines joined first: a make recipe is a COMMAND, not a line, and
    # `artist-preflight-prod` puts `docker exec` on one line and `python3` on the
    # next. Reading line by line, the second version of this guard failed on a
    # correct target — the same "predicate wider than its question" it warns about,
    # committed twice in a row while writing it.
    raw = MAKEFILE.read_text(encoding="utf-8").replace("\\\n", " ")
    for lineno, line in enumerate(raw.splitlines(), 1):
        if not any(f"python3 {tool}" in line for tool in tools):
            continue
        # `python3` INSIDE a container or over ssh is that machine's interpreter, and
        # there it is the right one — the dashboard image carries the same Streamlit
        # as the venv. The question is only whether a target runs the tool on the
        # HOST's system python. Narrowed after the first version failed on
        # `artist-preflight-prod`, whose `docker exec … python3` is correct: a
        # predicate wider than its question invents defects, which is exactly the
        # class this file is about.
        assert "docker exec" in line or "ssh " in line, (
            f"Makefile:{lineno} invokes a journey tool with the bare system "
            "`python3`. Use $(GUIDE_PY) — the system one carries a different "
            "Streamlit (1.54 vs 1.62 here) whose AppTest lacks `file_uploader`."
        )


def test_a_tenant_without_a_user_row_is_refused_not_rendered():
    """Rendering as a user who does not exist produces findings about nothing.

    `--artist 17` against the LOCAL database rendered every page as user id 0 and
    reported « Utilisateur introuvable » plus a CUL-DE-SAC on the account page. Artist
    17 has a user row in production and none locally; neither finding was about the app.
    """
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    main = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    src = ast.get_source_segment(TOOL.read_text(encoding="utf-8"), main) or ""
    assert "if not user_id:" in src, (
        "the tool no longer checks that the tenant has a user row before rendering. "
        "Without it, every page renders as a non-existent user and the output "
        "describes the database, not the product."
    )
    assert "artist-firstlook-prod" in src, (
        "the refusal no longer names the command that WOULD work. A refusal that does "
        "not say what to do next is half a refusal."
    )
