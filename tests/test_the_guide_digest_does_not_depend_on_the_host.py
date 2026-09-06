"""Guard: the guide digest asks about the GUIDE, never about the machine.

Type: Utility
Uses: ast, src.dashboard.guides.guide_pdf
Triggers: pytest
Persists in: nothing

Error class `guard-reads-the-host-env-not-the-code`.

Measured 2026-09-06. `credential_guides.META_BUSINESS_ID` is resolved at import —
from `os.environ`, and failing that from the project `.env`, which the module loads
itself. Two things then read it:

  * the Meta sharing step, which said one sentence when the value was there and a
    DIFFERENT one when it was not;
  * `guide_pdf.source_fingerprint`, whose hand-written normalisation list named
    `APP_BASE_URL` and nothing else.

So the digest of "the current guide sources" was one value on the machine that has a
`.env` and another on one that does not. The cost was not one red test: CI runs the
error-class guards at step 10 of 15 and stops there, so **`Run tests` had not
executed for 27 consecutive runs** between 2026-09-04 and 2026-09-06 — every push
merged without its suite ever running.

The three assertions below are the three ways that came back:
its value in the text, its value in the digest, and the `if` that made the sentence
itself vary.
"""
from __future__ import annotations

import ast
from pathlib import Path

from src.dashboard.content import credential_guides as _cg
from src.dashboard.content import credential_guides_en as _en
from src.dashboard.guides import guide_pdf as _gp
from src.dashboard.guides.guide_pdf import (
    ENV_SUBSTITUTIONS,
    _env_values,
    build_guide_html,
)

def _render_path_modules() -> list[Path]:
    """The modules the render actually pulls in — derived, never typed out.

    A hand-picked trio would be `guard-scope-is-a-hand-written-list` written into the
    guard for that very class: it would cover the three files we happened to think
    of, stay silent about `csv_guides` and `os_hints`, and its silence would read as
    coverage. So the set is `guide_pdf` plus every first-party module it imports.
    """
    import ast

    root = Path(_gp.__file__).resolve()
    found = {root}
    tree = ast.parse(root.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not node.module.startswith("src."):
            continue
        candidate = Path(*node.module.split(".")).with_suffix(".py")
        resolved = (root.parents[3] / candidate).resolve()
        if resolved.is_file():
            found.add(resolved)
    return sorted(found)


_GUIDE_MODULES = _render_path_modules()


def _env_names_read(path: Path) -> set[str]:
    """Every literal env-var name this module reads, by AST — not by grep.

    A comment or a docstring naming a variable must not be able to satisfy this,
    and a `grep` cannot tell the two apart.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in ("getenv", "get"):
            continue
        src = ast.unparse(node.func)
        if "environ" not in src and "getenv" not in src:
            continue
        if node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            names.add(node.args[0].value)
    return names


def test_every_env_var_the_guide_reads_is_normalised_out_of_the_digest():
    """The list was hand-kept and the second variable to arrive walked past it."""
    read: set[str] = set()
    for path in _GUIDE_MODULES:
        read |= _env_names_read(path)
    missing = sorted(read - set(ENV_SUBSTITUTIONS))
    assert not missing, (
        f"{missing} reach the rendered guide but are not in "
        "`guide_pdf.ENV_SUBSTITUTIONS`, so `source_fingerprint()` depends on the "
        "machine that computes it. Add each one to ENV_SUBSTITUTIONS and to "
        "`_env_values()`, or stop reading it from a guide module."
    )


def test_no_environment_value_survives_into_the_digested_html():
    """The question itself: is anything host-specific still in what we hash?"""
    joined = "\x00".join(build_guide_html(lang) for lang in ("fr", "en"))
    for name, value in _env_values().items():
        if len(value) < 8:
            continue
        joined = joined.replace(value, "{%s}" % name.removesuffix("_EN"))
    leaked = sorted(
        name for name, value in _env_values().items()
        if len(value) >= 8 and value in joined
    )
    assert not leaked, (
        f"{leaked} still appear in the hashed HTML after normalisation — the digest "
        "is not reproducible off this machine."
    )


def test_the_sharing_sentence_does_not_branch_on_the_business_id():
    """A branch cannot be normalised away: it changes the WORDS, not a token.

    This is what the first fix got wrong. Substituting the value is not enough while
    `META_BUSINESS_ID or "ask us"` produces two different sentences — the digest
    still moves. The shape is now single, and the token inside it is what varies.
    """
    for path in (Path(_cg.__file__), Path(_en.__file__)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.IfExp):
                continue
            used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            assert "META_BUSINESS_ID" not in used, (
                f"{path.name} makes the guide sentence depend on whether "
                "META_BUSINESS_ID is set. Render one shape and let "
                "BUSINESS_ID_SHOWN carry the difference, or the digest — and the "
                "guide an artist reads — differs between machines."
            )


def test_the_shown_token_falls_back_instead_of_leaving_a_hole():
    """Absent id ⇒ the artist is told to ask us, never shown an empty backtick."""
    assert _cg.BUSINESS_ID_SHOWN, "BUSINESS_ID_SHOWN is empty — the guide shows ``"
    assert _en.BUSINESS_ID_SHOWN_EN, "BUSINESS_ID_SHOWN_EN is empty"
