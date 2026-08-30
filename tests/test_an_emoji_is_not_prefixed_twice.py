"""An emoji written OUTSIDE t() must not also live inside the translation.

Type: Test
Uses: ast, the i18n catalogs
Depends on: src/dashboard/views/**.py, src/dashboard/utils/i18n_catalog/
Persists in: nothing

The defect
----------
Caught while writing it, 2026-08-30. Highlighting a heading turned

    st.markdown("### " + t("onboarding.guide_cta", "📄 Ton guide de démarrage"))

into

    st.markdown("### :orange-background[📄 " + t("onboarding.guide_cta",
                                                 "Ton guide de démarrage") + "]")

The French default lost its emoji to the prefix, but the ENGLISH catalog entry still
read "📄 Your starter guide". An English artist would have seen "📄 📄 Your starter
guide". Nothing in the suite could see it: `test_i18n` checks that every key HAS an
entry, and the render tests assert a string appears — a doubled emoji is still a
string that appears.

The general shape: a literal glued to a t() call is written against ONE language.
Every language whose translation already carries that literal doubles it.

What this asserts
-----------------
For every `"<literal>" + t(key, default)` in the dashboard views: no leading emoji in
the literal is also the first character of any translation of that key.

Limits, stated rather than hidden: this only sees concatenation where the literal is a
sibling of the t() call in the same BinOp. A prefix built through a variable, an
f-string, or `.format()` is out of reach — and would be the next place to look.
"""
from __future__ import annotations

import ast
import importlib
import pkgutil
import unicodedata
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_VIEWS = _ROOT / "src/dashboard/views"


def _catalogs() -> dict[str, str]:
    """Every key → its English string, across every catalog module."""
    import src.dashboard.utils.i18n_catalog as pkg
    out: dict[str, str] = {}
    for mod in pkgutil.iter_modules(pkg.__path__):
        m = importlib.import_module(f"{pkg.__name__}.{mod.name}")
        for attr in ("EN", "TRANSLATIONS"):
            table = getattr(m, attr, None)
            if isinstance(table, dict):
                out.update({k: v for k, v in table.items() if isinstance(v, str)})
    return out


def _is_emoji(ch: str) -> bool:
    """Symbol or private-use char — good enough to spot a decorative prefix."""
    return unicodedata.category(ch) in {"So", "Sk", "Co"}


def _leading_emojis(text: str) -> str:
    out = ""
    for ch in text:
        if _is_emoji(ch) or (out and ch in " ‍️"):
            out += ch
        else:
            break
    return out.strip()


def _prefixed_t_calls(tree: ast.AST):
    """Yield (key, literal_prefix) for every `"lit" + t(key, ...)` in the tree."""
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)):
            continue
        left, right = node.left, node.right
        if not (isinstance(left, ast.Constant) and isinstance(left.value, str)):
            continue
        if not (isinstance(right, ast.Call) and isinstance(right.func, ast.Name)
                and right.func.id == "t" and right.args):
            continue
        key_node = right.args[0]
        if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
            yield key_node.value, left.value


def test_no_view_prefixes_an_emoji_a_translation_already_carries():
    catalog = _catalogs()
    offenders: list[str] = []

    for path in sorted(_VIEWS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for key, literal in _prefixed_t_calls(tree):
            prefix = _leading_emojis(literal.split("[")[-1])
            if not prefix:
                continue
            translated = catalog.get(key)
            if translated and _leading_emojis(translated).startswith(prefix[0]):
                offenders.append(
                    f"{path.relative_to(_ROOT)} — {key}: prefix {prefix!r} is also the "
                    f"start of the translation {translated!r}"
                )

    assert not offenders, (
        "an emoji is written outside t() AND inside the translation, so that language "
        "renders it twice:\n  " + "\n  ".join(offenders) +
        "\nPut the emoji inside the t() default (and inside every translation), or "
        "remove it from the translations. Only the language you tested looks right."
    )
