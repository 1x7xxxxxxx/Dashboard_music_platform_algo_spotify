"""R270 — a collection turns green when its data LANDS, not when its DAG ends well.

Type: Test
Uses: src/dashboard/utils/collection_progress.py (landing),
      src/dashboard/utils/collection_trigger.py (autostart_if_journey_complete)

Owner decision 2026-09-27 (note L157) : « la croix verte quand la donnée arrive ». A DAG
run ends `success` when the collector SKIPPED the tenant (no identity) or wrote zero rows —
locally 23 229 of 31 208 ledger rows are `skipped`. The sidebar drew ✅ on all of them.
And the collection that starts by itself was never remembered, so nothing reported on it;
five texts still sent the artist to a sidebar button removed on 2026-09-08.

Mutation record (2026-09-27) : `landing` answering ✅ on a skipped row → red ; the rows>0
condition dropped → red ; the autostart no longer remembering its runs → red ; the old
button name put back in one EN string → red.
"""
import ast
from pathlib import Path

from src.dashboard.utils import collection_trigger
from src.dashboard.utils.collection_progress import (
    LAUNCHED_AT_KEY, NOT_LAUNCHED_KEY, RUNS_KEY, landing)

ROOT = Path(__file__).resolve().parents[1]


def test_green_only_when_rows_landed():
    assert landing({"status": "success", "rows_inserted": 12}) == ("✅", None)
    assert landing({"status": "success", "rows_inserted": 0})[0] == "⚠️"
    glyph, why = landing({"status": "skipped", "rows_inserted": 0,
                          "error_message": "no YouTube channel_id declared"})
    assert glyph == "⚠️" and "channel_id" in why
    assert landing({"status": "failed", "rows_inserted": 0})[0] == "❌"
    assert landing(None) == ("⏳", None), "an unread ledger is never a ✅"


def test_the_automatic_start_is_remembered(monkeypatch):
    monkeypatch.setattr(collection_trigger, "trigger_all_collections",
                        lambda *a: ({"youtube_daily": "run-1"}, {"meta_ads_api_daily": "refusé"}))
    import src.dashboard.utils.setup_completion as sc
    monkeypatch.setattr(sc, "read_setup_state", lambda db, aid: object())
    monkeypatch.setattr(collection_trigger, "should_autostart", lambda state: True)
    session: dict = {}
    collection_trigger.autostart_if_journey_complete(object(), 7, session, object(), [])
    assert session[RUNS_KEY] == {"youtube_daily": "run-1"}
    assert session[NOT_LAUNCHED_KEY] == {"meta_ads_api_daily": "refusé"}
    assert session[LAUNCHED_AT_KEY]


_GONE = ("Launch ALL collections", "Lancer TOUTES les collectes")


def _strings(tree: ast.AST) -> list[str]:
    """String literals that are NOT docstrings (a docstring may tell the button's story)."""
    doc_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                doc_ids.add(id(body[0].value))
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, str) and id(n) not in doc_ids]


def _naming_the_removed_button(root: Path) -> list[str]:
    hits = []
    for p in root.rglob("*.py"):
        for s in _strings(ast.parse(p.read_text(encoding="utf-8"))):
            if any(g in s for g in _GONE):
                hits.append(str(p.relative_to(ROOT)))
    return hits


def test_no_screen_text_names_the_removed_button():
    assert not _naming_the_removed_button(ROOT / "src" / "dashboard")


def test_the_button_detector_is_not_vacuous(tmp_path):
    (tmp_path / "v.py").write_text(
        '"""the « Launch ALL collections » button was removed"""\n'
        '# Launch ALL collections\n'
        'X = "then run **🚀 Launch ALL collections** in the sidebar."\n', encoding="utf-8")
    global ROOT
    saved, ROOT = ROOT, tmp_path
    try:
        assert _naming_the_removed_button(tmp_path) == ["v.py"]
    finally:
        ROOT = saved
