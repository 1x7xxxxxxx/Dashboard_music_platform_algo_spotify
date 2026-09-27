"""R232 — a view draws its analysis window through the shared filter, never its own.

Six pages once had a period selector each — six definitions of « période », one of
which let an artist pick a window with no data (2026-09-21). The shared layer is
`src/dashboard/utils/filters.py`. A `st.date_input` in a view is either data entry
in a form (declared below, with what it enters) or a hand-written filter — refused.

Structural: every `date_input` call is located by (file, enclosing function) in the
AST, so a comment that describes an old selector (trigger_algo/router.py) never
counts, and a new one in any function does.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "src" / "dashboard" / "views"

DECLARED = {
    "admin.py:_render_costs": "saisie : début et fin d'un coût d'exploitation",
    "revenue_forecast.py:_render_cost_entry": "saisie : début et fin d'un coût de l'artiste",
    "promo_admin.py:show": "saisie : date d'expiration d'un code promo",
    "hypeddit.py:_render_entry_form": "saisie : date d'une campagne entrée à la main",
    "export_pdf.py:_show_form": "filtre gardé À PART, et dit pourquoi : ses préréglages "
        "glissants (28 j, 3/6/12 mois) n'existent pas dans le filtre partagé, et « depuis "
        "la sortie » se résout sur les titres choisis APRÈS le sélecteur (code-critic R232)",
}


def date_input_sites(tree: ast.AST, name: str) -> set[str]:
    sites = set()
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(fn):
                if isinstance(n, ast.Call) and \
                        getattr(n.func, "attr", getattr(n.func, "id", "")) == "date_input":
                    sites.add(f"{name}:{fn.name}")
    return sites


def _all_sites() -> set[str]:
    out = set()
    for f in VIEWS.rglob("*.py"):
        out |= date_input_sites(ast.parse(f.read_text()), f.relative_to(VIEWS).as_posix())
    return out


def test_no_view_writes_its_own_period_filter():
    new = sorted(_all_sites() - set(DECLARED))
    assert not new, (
        f"{new} draw a date filter of their own. Use `filters.period()` "
        "(src/dashboard/utils/filters.py); if it is data entry in a form, declare it in "
        "DECLARED with what it enters.")


def test_every_declared_site_still_exists():
    gone = sorted(set(DECLARED) - _all_sites())
    assert not gone, f"{gone} no longer call date_input — remove them from DECLARED"


def test_the_detector_sees_the_defect_it_is_written_for():
    defect = ast.parse("def show():\n    a = st.date_input('Du')\n")
    assert date_input_sites(defect, "x.py") == {"x.py:show"}
    comment = ast.parse("def show():\n    # the old st.date_input('Du') selector\n    pass\n")
    assert not date_input_sites(comment, "x.py"), "a comment is not a filter"


def test_the_front_door_adds_no_logic_of_its_own():
    from src.dashboard.utils import filters, meta_accounts, period_filter
    assert filters.period is period_filter.smart_period_filter
    assert filters.entity is period_filter.entity_period_filter
    assert filters.account is meta_accounts.account_scope
