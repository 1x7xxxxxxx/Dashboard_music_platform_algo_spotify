"""R260 — a number is written ONE way on screen, in the reader's language; the hand-made
forms can only become fewer.

Type: Test
Uses: src/dashboard/utils/formats.py, src/dashboard/views/**/*.py (parsed with ast)

Measured 2026-09-27 : 74 `f"{v:,.2f}".replace(",", " ")` hacks and 199 `{…:,…}` format specs
in the views. The hack printed « 1 234.56 » on a French screen (decimal point kept) and on
an English one (comma turned into a space) — wrong in both. 46 migrated to `formats` the same
day ; read by the syntax tree, 26 separators and 77 `{…:,…}` fields remain — frozen
here, they only go down. Tables: 45 of 58
shown with no number format at all.

The counts read the SYNTAX TREE, never the text: a comment or a docstring that quotes the
hack (this one does) must not count.

Mutation record (2026-09-27) : the French branch of `formats.num` replaced by a plain
`.replace(",", " ")` → red ; the absent-value branch removed → red ; one hack appended to a
view → the ratchet went red ; a table with `.style` counted as raw → red.
"""
import ast
import math
import pathlib

from src.dashboard.utils import formats

VIEWS = pathlib.Path(__file__).resolve().parents[1] / "src" / "dashboard" / "views"
# R368 (2026-10-05): the hack used to mean only `.replace(",", " ")`. A sweep found 16
# more written with a NARROW no-break space (U+202F) — the same gesture, invisible to
# the predicate. Ceilings set to the count of that day, no slack: a slack is a free
# regression.
_SEPARATORS = frozenset({" ", "\u202f", "\xa0"})
CEILING_HACKS, CEILING_SPECS = 37, 75
# Tables shown with no number format at all — 45 of 58 on 2026-09-27. `formats.table` is
# the way out ; this count only goes down.
CEILING_RAW_TABLES = 45


def _is_sep_hack(node: ast.AST) -> bool:
    """`<x>.replace(",", " ")` — the hand-made thousands separator, any space."""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "replace" and len(node.args) == 2
            and all(isinstance(a, ast.Constant) for a in node.args)
            and node.args[0].value == "," and node.args[1].value in _SEPARATORS)


def _is_comma_spec(node: ast.AST) -> bool:
    """A `{value:,…}` field of an f-string."""
    if not (isinstance(node, ast.FormattedValue) and node.format_spec is not None):
        return False
    spec = "".join(v.value for v in node.format_spec.values
                   if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return spec.startswith(",")


def _is_raw_table(node: ast.AST) -> bool:
    """`st.dataframe(df)` / `st.table(df)` with no Styler, no format, no column_config."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("dataframe", "table")
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "st"):
        return False
    if any(k.arg == "column_config" for k in node.keywords):
        return False
    first = node.args[0] if node.args else None
    return not any(isinstance(n, ast.Attribute) and n.attr in ("style", "format")
                   for n in ast.walk(first)) if first is not None else True


def count(root: pathlib.Path = VIEWS) -> tuple[int, int, int]:
    hacks = specs = tables = 0
    for p in root.rglob("*.py"):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            hacks += _is_sep_hack(node)
            specs += _is_comma_spec(node)
            tables += _is_raw_table(node)
    return hacks, specs, tables


def test_the_formatter_writes_each_language_its_own_way():
    assert formats.num(1234567.891, 2, lang="fr") == "1 234 567,89"
    assert formats.num(1234567.891, 2, lang="en") == "1,234,567.89"
    assert formats.eur(1234.5, 2, lang="fr") == "1 234,50 €"
    assert formats.pct(12.5, 1, lang="fr") == "12,5 %"
    assert formats.pct(12.5, 1, lang="en") == "12.5%"
    assert formats.num(0, 0, lang="fr") == "0", "un zéro mesuré reste un zéro"


def test_an_absent_value_is_a_dash_never_zero_or_nan():
    for absent in (None, float("nan"), math.nan):
        assert formats.num(absent) == "—" and formats.eur(absent) == "—" and formats.pct(absent) == "—"


def test_the_hand_made_forms_only_become_fewer():
    hacks, specs, tables = count()
    assert hacks <= CEILING_HACKS, (
        f"{hacks} séparateurs faits main (plafond {CEILING_HACKS}) — utiliser formats.num/eur/pct")
    assert specs <= CEILING_SPECS, (
        f"{specs} formats {{…:,…}} dans les vues (plafond {CEILING_SPECS}) — utiliser formats")
    assert tables <= CEILING_RAW_TABLES, (
        f"{tables} tableaux sans format (plafond {CEILING_RAW_TABLES}) — utiliser formats.table")


def test_the_counter_is_not_vacuous(tmp_path):
    """Each form is seen on a real line, and NOT in a docstring or a comment."""
    (tmp_path / "v.py").write_text(
        '"""f"{v:,.2f}".replace(",", " ") in prose"""\n'
        '# st.dataframe(df) in a comment\n'
        'x = f"{v:,.2f}".replace(",", " ")\n'
        'y = f"{w:,}"\n'
        'st.dataframe(df)\n'
        'st.dataframe(df.style.format(f))\n'
        'st.table(df, column_config={})\n'
        'z = f"{v:,}".replace(",", "\\u202f")\n', encoding="utf-8")
    assert count(tmp_path) == (2, 3, 1), "the narrow no-break space is the same hack (R368)"
    assert sum(count()) >= 1, "the views are no longer read"
