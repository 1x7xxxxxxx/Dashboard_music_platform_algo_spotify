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


def bare_handlers(source: str) -> list[int]:
    """Line numbers of every `except:` with no exception class, in ONE source.

    Extracted so the guard can be handed a FABRICATED source. While the sweep was
    the only entry point, the sole way to know whether it still bit was to break a
    real file — so nobody checked, and `test_no_bare_except_anywhere` would have
    stayed green on a detector that found nothing.
    """
    tree = ast.parse(source)
    return sorted(n.lineno for n in ast.walk(tree)
                  if isinstance(n, ast.ExceptHandler) and n.type is None)


def bare_except_sites() -> list[str]:
    """`path:line` for every `except:` with no exception class, repo-wide."""
    found = []
    for path in _python_files():
        try:
            lignes = bare_handlers(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue  # not ours to parse; other guards cover syntax
        found += [f"{path.relative_to(REPO).as_posix()}:{n}" for n in lignes]
    return sorted(found)


def test_the_detector_sees_the_bare_except_it_is_written_for():
    """Non-vacuity: the forbidden shape is fabricated here, and must be caught.

    `test_this_guard_reads_the_ast_and_not_the_text` below asserts the detector's
    SHAPE — that it mentions `ast.ExceptHandler`. A detector can mention it and
    still return nothing (walk the wrong tree, filter on the wrong attribute), and
    this repo has measured that exact blindness. Shape is not behaviour.

    The second half matters just as much: the CORRECTED form, and the comments that
    document the class, must stay silent. `src/transformers/s4a_csv_parser.py`
    carries the literal `except:` inside a comment on purpose.
    """
    defect = (
        "def parse(path):\n"
        "    try:\n"
        "        return read(path)\n"
        "    except:\n"
        "        return {'type': None, 'data': []}\n"
    )
    assert bare_handlers(defect) == [4], (
        f"the detector returns {bare_handlers(defect)} on a bare `except:` written "
        "in plain sight. It guards nothing, and the repo-wide sweep is green by "
        "blindness — exactly how `collector-silent-success` was produced.")

    corrected = (
        "# A bare `except:` here used to return {'type': None, 'data': []}.\n"
        "def parse(path):\n"
        "    try:\n"
        "        return read(path)\n"
        "    except (OSError, UnicodeDecodeError) as e:\n"
        "        raise ParseError(path) from e\n"
    )
    assert bare_handlers(corrected) == [], (
        "the detector fires on the corrected form or on the comment that documents "
        "the defect. Documenting the class would turn the CI red, and the cheapest "
        "way out would be to delete the documentation.")


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

    This is a SHAPE assertion, and it is no longer the proof: a detector can name
    `ast.ExceptHandler` and still return nothing.
    `test_the_detector_sees_the_bare_except_it_is_written_for` is what proves the
    behaviour; this one only pins WHY the AST was chosen over a grep. Measured
    2026-09-18: retargeting the detector to a helper made this test red while the
    behaviour was intact — a shape assertion breaks on refactors and stays green on
    blindness, which is the wrong way round.
    """
    src = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "bare_handlers")
    names = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    assert "ExceptHandler" in names, (
        "bare_handlers no longer inspects ast.ExceptHandler. Any string-matching "
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
