"""Guard: no `except:` bare, anywhere this repo's Python runs.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Error class `bare-except`, ported from `msdr_predictive_maintenance` on 2026-09-03
after confirming live sites here.

A bare `except:` catches `KeyboardInterrupt` and `SystemExit` as well as the error it
was aimed at, so it swallows a deliberate Ctrl-C and a process shutdown. And it never
records WHICH class it ate, which makes the next defect undiagnosable.

## Why this is not decorative in this repo

It is the mechanism that produced the repo's flagship class. Two comments say so,
still in the tree:

* `src/transformers/s4a_csv_parser.py:184` — *« le `except:` nu ci-dessous renvoyait
  `{'type': None}` sans… »*
* `src/transformers/csv_dialect.py:20` — *« the S4A path answered `{'type': None,
  'data': []}` out of a bare `except:` »*

That is `collector-silent-success` — an entire family of guards, a cross-cutting rule
(#6) and a dedicated AST auditor — **caused by a bare except**, fixed twice at the
call site, and never registered as a class of its own.

The live sites found on 2026-09-03: `scripts/manage_mapping.py` ×3 (an operator tool
that writes the Meta mapping table, where swallowing Ctrl-C means an interactive
prompt cannot be aborted) and `airflow/debug_dag/debug_s4a.py` ×1, which logged
« Impossible de créer le dossier » without ever saying why.

## Why the AST and not a grep

Those two comments above contain the literal string this guard is about. A textual
check would fire on the very prose that documents the defect — the failure mode that
caught four guards in one evening (`a-textual-guard-is-blind`) and caught the first
draft of the exec-bit guard in this same session. `ast.ExceptHandler.type is None` is
the structural fact; nothing written in a comment can imitate it.
"""
from __future__ import annotations

import ast
from pathlib import Path

# The trees that actually run: application code, the pipeline, the operator tools and
# the repo's own scripts. Listed rather than derived by exclusion — walking the whole
# repo took 110 s on this /mnt/c mount and pulled in vendored code nobody here wrote.
_ROOTS = ("src", "airflow", "scripts", "tools", ".claude/scripts", ".claude/hooks")

# Retired trees, excluded by NAME and with a reason, never by a wildcard. Both hold
# pre-2026 Meta code kept for reference; `test_the_archives_are_really_dead` below
# proves nothing live imports them, so the exclusion is verified rather than asserted.
_RETIRED = ("archive", ".archive", ".claude/.retired")


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()


def _python_files() -> list[Path]:
    out: list[Path] = []
    for root in _ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        out += [p for p in base.rglob("*.py") if "__pycache__" not in p.parts]
    return sorted(set(out))


def bare_except_sites() -> list[str]:
    """`path:line` for every `except:` with no exception class, repo-wide."""
    found = []
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue  # not ours to parse; other guards cover syntax
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                found.append(f"{path.relative_to(REPO).as_posix()}:{node.lineno}")
    return sorted(found)


def test_no_bare_except_anywhere():
    sites = bare_except_sites()
    assert not sites, (
        f"{len(sites)} bare `except:` — each one also swallows KeyboardInterrupt and "
        f"SystemExit, and none of them records what it caught:\n  "
        + "\n  ".join(sites)
        + "\n\nName the exception class. This is the mechanism that produced "
        "`collector-silent-success`: two comments in src/transformers/ record a bare "
        "except returning `{'type': None, 'data': []}` from a parser."
    )


def test_this_guard_reads_the_ast_and_not_the_text():
    """Pins the decision that lets it coexist with the comments describing the class.

    `src/transformers/s4a_csv_parser.py` and `csv_dialect.py` both contain the literal
    string a grep would look for, inside comments that exist to explain the defect. A
    textual version of this guard would be red on correct code — and the usual next
    step is to weaken the documentation to quiet the test.
    """
    src = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "bare_except_sites")
    names = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    assert "ExceptHandler" in names, (
        "bare_except_sites no longer inspects ast.ExceptHandler. Any string-matching "
        "replacement fires on the two comments in src/transformers/ that document "
        "this very class."
    )


def test_the_comments_that_document_the_class_are_still_there():
    """They are the evidence for the severity; losing them loses the reason.

    If this fails, check whether the comment merely moved before deleting the test:
    the point is that the repo records having been bitten, not the exact wording.
    """
    parser = (REPO / "src" / "transformers" / "s4a_csv_parser.py").read_text(encoding="utf-8")
    dialect = (REPO / "src" / "transformers" / "csv_dialect.py").read_text(encoding="utf-8")
    assert "except:" in parser and "except:" in dialect, (
        "the comments recording that a bare except produced `collector-silent-success` "
        "are gone. They are why this class is P2 here and not a style preference."
    )


def test_the_archives_are_really_dead():
    """The exclusion above is only honest while nothing live imports the archives.

    Without this, `_RETIRED` is a place to move code to in order to silence the guard.
    """
    retired_tops = {r.split("/")[-1].lstrip(".") for r in _RETIRED}
    offenders = []
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        # AST, not a substring — and this is the second time in this one file that the
        # textual version was wrong: `"archive."` matches the prose `archive.md`, which
        # appears in ordinary comments. Only a real import counts.
        for node in ast.walk(tree):
            mods: list[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            for m in mods:
                if m.split(".")[0] in retired_tops:
                    offenders.append(
                        f"{path.relative_to(REPO).as_posix()}:{node.lineno} -> {m}")
    assert not offenders, (
        "live code imports an archived module, so excluding the archives from the "
        f"bare-except sweep hides code that actually runs: {offenders}"
    )
