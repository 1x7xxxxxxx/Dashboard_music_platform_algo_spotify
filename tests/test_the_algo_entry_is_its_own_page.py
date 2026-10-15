"""R587 — the « une fois déclenché » entry is its own page, after « Saisie trésorerie ».

Type: Guard
Uses: src/dashboard/utils/nav_sections.py, src/dashboard/views/saisie_algo.py,
      src/dashboard/views/trigger_algo/router.py
Depends on: nothing (AST + a recording double)
Persists in: nothing

Owner, Prédiction algos 2026-10-15: « une vue saisie des streams algorithmiques
déclenchés, sous saisie trésorerie ; on y saisit aussi le coût de distribution ».
"""
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path


def _called(path: str) -> set[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {getattr(n.func, "id", getattr(n.func, "attr", "")) for n in ast.walk(tree)
            if isinstance(n, ast.Call)}


def test_the_entry_page_sits_right_after_the_treasury_entry() -> None:
    from src.dashboard.routes import ROUTES
    from src.dashboard.utils.nav_sections import NAV_SECTIONS

    keys = [k for sid, _, items in NAV_SECTIONS if sid == "data" for _, k in items]
    assert keys[keys.index("saisie_tresorerie") + 1] == "saisie_algo", keys
    assert ROUTES["saisie_algo"] == "views.saisie_algo"


def test_the_prediction_page_renders_no_entry_grid() -> None:
    page = set()
    for f in Path("src/dashboard/views/trigger_algo").glob("*.py"):
        if f.name not in ("_outcome_entry.py", "_custom_window_entry.py"):
            page |= _called(str(f))
    assert not page & {"render_outcomes", "render_custom_grid", "data_editor"}, page
    assert {"render_outcomes", "render_custom_grid", "render_distribution_cost"} <= _called(
        "src/dashboard/views/saisie_algo.py")


def test_the_distribution_cost_is_written_on_its_tenant_as_a_one_off() -> None:
    from src.dashboard.views.saisie_algo import save_distribution_cost

    class _Db:
        def execute_query(self, sql, params):
            self.sql, self.params = sql, params
    db = _Db()
    save_distribution_cost(db, 7, "Titre", 29.0, dt.date(2026, 10, 15), "distribution — Titre")
    assert "'distribution'" in db.sql and "'one_off'" in db.sql
    assert db.params == (7, "distribution — Titre", 29.0, dt.date(2026, 10, 1))
