"""A write invalidates the cache of the tenant it WROTE — not of whoever is logged in.

Type: Sub
Uses: src/dashboard/utils/cache_invalidation.py, src/dashboard/views/ (AST)
Depends on: nothing — a patched `clear_kpi_caches`, the views read as syntax trees

R335 (2026-09-29): `admin.py` imported a CSV for artist N and called `purge_after_write(n)`;
`bump` then resolved the tenant from the ADMIN session — none — and signalled nothing, so the
other instances served N's stale totals for up to 600 s. Found by the R334 sweep.

Mutation record (2026-09-29): seen red with `artist_id` dropped from the `clear_kpi_caches`
call in `purge_after_write`, and with `target_artist_id` removed at `admin.py`'s call.
"""
import ast
from pathlib import Path
from unittest.mock import patch

from src.dashboard.utils.cache_invalidation import purge_after_write

VIEWS = Path(__file__).resolve().parents[1] / "src/dashboard/views"


def test_the_purge_hands_the_written_tenant_to_the_signal() -> None:
    with patch("src.dashboard.utils.kpi_helpers.clear_kpi_caches") as clear:
        purge_after_write(3, 42)
    clear.assert_called_once_with(42)


def _anonymous_calls(tree: ast.AST) -> list[int]:
    return [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "purge_after_write"
            and len(n.args) < 2 and not any(k.arg == "artist_id" for k in n.keywords)]


def test_every_view_names_the_tenant_it_wrote() -> None:
    found = {str(p.relative_to(VIEWS)): lines for p in sorted(VIEWS.rglob("*.py"))
             if (lines := _anonymous_calls(ast.parse(p.read_text(encoding="utf-8"))))}
    assert not found, f"purge_after_write without the written tenant: {found}"
    assert _anonymous_calls(ast.parse("purge_after_write(n)\n")) == [1]
