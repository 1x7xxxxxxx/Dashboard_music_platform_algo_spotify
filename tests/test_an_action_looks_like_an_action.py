"""R271 (owner note L242) — a gesture has ONE look, defined once: `ui.action`.

Type: Test
Uses: src/dashboard/utils/ui.py (action, note), src/dashboard/views/** (parsed with ast)

« Les actions dans une section grosse, en gras, surlignée ; les informations en plus
petit. » The look was written by hand on one page; now a page says WHICH line is its
gesture and `ui.action` draws it. A hand-made `:orange-background[…]` outside `ui.py` is
a second definition that will drift.

Mutation record (2026-09-28) : a hand-made `:orange-background[` put back in
credentials/_render.py → red ; the home page's `action(` call removed → red.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "src" / "dashboard" / "views"


def hand_made_highlights(root: Path = VIEWS) -> list[str]:
    out = []
    for p in sorted(root.rglob("*.py")):
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and ":orange-background[" in n.value:
                out.append(f"{p.relative_to(root)}:{n.lineno}")
    return out


def test_no_view_draws_its_own_action_look():
    assert not hand_made_highlights(), hand_made_highlights()


def test_the_pages_that_carry_a_gesture_use_the_contract():
    for rel in ("src/dashboard/views/home.py", "src/dashboard/views/credentials/_render.py"):
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        calls = {n.func.id for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "action" in calls, rel


def test_the_detector_is_not_vacuous(tmp_path):
    (tmp_path / "v.py").write_text('# :orange-background[in a comment]\n'
                                   'st.markdown("### :orange-background[👉 x]")\n',
                                   encoding="utf-8")
    assert hand_made_highlights(tmp_path) == ["v.py:2"], "the comment must not count"
