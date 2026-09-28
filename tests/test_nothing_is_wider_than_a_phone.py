"""R271 (owner note L168 : « adaptation mobile ») — nothing in a view is wider than a phone.

Type: Test
Uses: src/dashboard/views/**, src/dashboard/utils/** (parsed with ast)

Measured 2026-09-28 at 390 × 844 (Playwright, the login page): the layout stacks and the
page does not scroll sideways (`scrollWidth` = 390) — Streamlit 1.63 stacks columns by
itself under ~640 px and `width="stretch"` figures follow the screen. What CAN break it is a
fixed width: a `width=<px>` handed to Streamlit, or a CSS `width`/`min-width` in px. One
existed (200 px, an avatar). The ceiling is 360 px — the narrowest common phone, minus the
page margins.

Mutation record (2026-09-28) : `width=900` given to an st.image → red ; a CSS
`min-width: 600px` in a markdown string → red.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_ROOTS = (ROOT / "src" / "dashboard" / "views", ROOT / "src" / "dashboard" / "utils")
_PHONE_PX = 360
_CSS = re.compile(r"(?<!max-)(?:min-)?width\s*:\s*(\d{3,})px")
_OFFLINE = ("pdf", "guide", "email", "branding")    # rendered to files or mails, not screens


def too_wide(tree: ast.AST) -> list[int]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            for k in n.keywords:
                if (k.arg == "width" and isinstance(k.value, ast.Constant)
                        and isinstance(k.value.value, int) and k.value.value > _PHONE_PX):
                    out.append(n.lineno)
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if any(int(m) > _PHONE_PX for m in _CSS.findall(n.value)):
                out.append(n.lineno)
    return out


def test_no_fixed_width_exceeds_a_phone():
    hits = []
    for base in _ROOTS:
        for p in sorted(base.rglob("*.py")):
            if any(w in p.name for w in _OFFLINE) or "pdf_exporter" in p.parts:
                continue
            hits += [f"{p.relative_to(ROOT)}:{ln}"
                     for ln in too_wide(ast.parse(p.read_text(encoding="utf-8")))]
    assert not hits, f"largeur fixe > {_PHONE_PX} px (déborde d'un téléphone) : {hits}"


def test_the_detector_is_not_vacuous():
    code = ('st.image(x, width=900)\nst.image(x, width=200)\n'
            'st.markdown("<div style=\'min-width: 600px\'>")\n'
            'st.markdown("<img style=\'max-width: 900px\'>")\n')
    assert too_wide(ast.parse(code)) == [1, 3]
