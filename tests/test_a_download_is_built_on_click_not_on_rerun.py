"""A download payload must not be rebuilt by every Streamlit rerun.

Type: Test
Uses: ast
Depends on: src/dashboard/views/*.py, src/dashboard/utils/guide_assets.py
Persists in: nothing

The defect, measured
--------------------
`show()` runs again on EVERY widget interaction. `st.download_button` needs its
payload present at render time, so a page that builds the file inline pays for it
on each rerun — expanding an accordion re-renders a PDF nobody asked to download.

Measured in the production container on 2026-08-30, `process_guide`:

    573 ms   credentials guide (WeasyPrint, with screenshots)
    148 ms   start guide
    ------
    721 ms   of its 1034 ms per rerun, on the first page a new artist reads

The repo already knew the answer three times over — `export_pdf` and `export_csv`
build on a click and stash the bytes in `session_state`, `onboarding` prefers a
pre-rendered file — and `process_guide`, written the same day for the same reason
and calling the same builder, did neither. A lesson applied in three places and
missed in the fourth is exactly what a guard is for.

Why this reads the AST
----------------------
Four guards written on 2026-08-22 passed on their own explanatory comments. A
`grep` for `write_pdf` would match this docstring; it would also miss a builder
reached through a local alias. The question is structural — *what produces the
value handed to `data=`* — so the answer has to be read from the tree.

What counts as acceptable
-------------------------
Exactly the three shapes already in the repo:
  1. the payload is read back from `st.session_state` (built earlier, on a click);
  2. it comes from a function decorated with `@st.cache_data` / `@st.cache_resource`;
  3. it is not an expensive build at all (a literal, a small dataframe `.to_csv()`).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_VIEWS = _ROOT / "src" / "dashboard" / "views"
_DASH = _ROOT / "src" / "dashboard"

# Builders whose cost was measured in hundreds of milliseconds. This list is
# asserted non-empty AND asserted to still resolve in the tree below, so it cannot
# rot into a guard that watches nothing.
EXPENSIVE = {
    "write_pdf",            # weasyprint HTML(...).write_pdf()
    "build_guide_pdf",      # renders the illustrated credentials guide
    "build_guide_html",     # its HTML half — the costly part is downstream of it
    "ZipFile",              # zipfile.ZipFile(...) — full export archive
    "export_all",           # csv_exporter — every table of a tenant, zipped
    "export_excel",         # csv_exporter — same, as a workbook
    "collect_report_data",  # the PDF report's god-function
}

_CACHE_DECORATORS = {"cache_data", "cache_resource"}


def _iter_view_modules() -> list[Path]:
    return sorted(p for p in _VIEWS.rglob("*.py") if p.name != "__init__.py")


def _is_cached(fn: ast.FunctionDef) -> bool:
    for dec in fn.decorator_list:
        node = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(node, ast.Attribute) and node.attr in _CACHE_DECORATORS:
            return True
    return False


def _calls_expensive(node: ast.AST) -> list[str]:
    """Names of EXPENSIVE builders called anywhere inside `node`."""
    found = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        f = sub.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
        if name in EXPENSIVE:
            found.append(name)
    return found


def _reads_session_state(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr == "session_state":
            return True
    return False


def _cached_names(tree: ast.Module) -> set[str]:
    """Functions defined in this module that carry a Streamlit cache decorator."""
    return {f.name for f in ast.walk(tree)
            if isinstance(f, ast.FunctionDef) and _is_cached(f)}


def _imported_cached_names(tree: ast.Module) -> set[str]:
    """Names imported from a dashboard module where they are cache-decorated.

    One level of resolution is enough and is honest about its limit: a builder
    reached through two uncached hops is not covered, and that shape does not
    exist in the tree today (asserted by `test_the_known_shapes_are_still_there`).
    """
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not node.module.startswith("src.dashboard"):
            continue
        src = _ROOT / Path(*node.module.split(".")).with_suffix(".py")
        if not src.exists():
            continue
        try:
            cached = _cached_names(ast.parse(src.read_text(encoding="utf-8")))
        except SyntaxError:
            continue
        out |= {a.name for a in node.names if a.name in cached}
    return out


def _enclosing_function(tree: ast.Module, target: ast.AST) -> ast.FunctionDef | None:
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and any(n is target for n in ast.walk(fn)):
            return fn
    return None


def _producers(fn: ast.FunctionDef, name: str) -> list[ast.AST]:
    """Right-hand sides assigned to `name` inside `fn`."""
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                out.append(node.value)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name) and node.target.id == name:
                out.append(node.value)
    return out


def offending_downloads(paths: list[Path]) -> list[str]:
    """`file:line` for every download payload rebuilt on each rerun."""
    bad: list[str] = []
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        safe_calls = _cached_names(tree) | _imported_cached_names(tree)

        for call in ast.walk(tree):
            if not isinstance(call, ast.Call):
                continue
            f = call.func
            if not (isinstance(f, ast.Attribute) and f.attr == "download_button"):
                continue
            data = next((kw.value for kw in call.keywords if kw.arg == "data"), None)
            if data is None and len(call.args) >= 2:
                data = call.args[1]
            if data is None:
                continue

            exprs = [data]
            if isinstance(data, ast.Name):
                fn = _enclosing_function(tree, call)
                if fn is not None:
                    exprs += _producers(fn, data.id)

            for expr in exprs:
                if _reads_session_state(expr):
                    continue                      # shape 1 — built on a click
                calls = {c.func.attr if isinstance(c.func, ast.Attribute)
                         else getattr(c.func, "id", None)
                         for c in ast.walk(expr) if isinstance(c, ast.Call)}
                if calls & safe_calls:
                    continue                      # shape 2 — cached producer
                if _calls_expensive(expr):        # shape 3 violated
                    try:
                        rel = path.relative_to(_ROOT)
                    except ValueError:
                        rel = path            # a fixture outside the repo
                    bad.append(f"{rel}:{expr.lineno}")
    return sorted(set(bad))


def test_no_view_rebuilds_a_download_payload_on_every_rerun():
    offenders = offending_downloads(_iter_view_modules())
    assert not offenders, (
        "These download payloads are rebuilt by every Streamlit rerun — a widget "
        "click pays for a file nobody asked to download:\n  "
        + "\n  ".join(offenders)
        + "\n\nUse one of the three shapes already in the repo: build on a click and "
          "stash in st.session_state (export_pdf, export_csv), call a @st.cache_data "
          "producer (utils/guide_assets.py), or serve a pre-rendered file."
    )


def test_the_known_shapes_are_still_there():
    """The guard watches something: every builder it names must still exist.

    Without this, deleting `guide_assets.py` or renaming `write_pdf` would leave a
    green test inspecting an empty set — the failure mode `check_stale_deliverables`
    reports as "this guard is watching nothing".

    The first draft of this list carried two names, `build_zip` and `build_xlsx`,
    that had never existed in this repo. This assertion is what found them, which is
    the whole argument for keeping it: a guard's own vocabulary rots too.
    """
    text = "\n".join(p.read_text(encoding="utf-8")
                     for p in (_DASH).rglob("*.py"))
    missing = sorted(name for name in EXPENSIVE if name not in text)
    assert not missing, (
        f"{missing} no longer appear anywhere under src/dashboard/. Either the list "
        "has rotted or the code moved — re-derive it against the tree, do not shrink it."
    )
    cached = _cached_names(ast.parse(
        (_DASH / "utils" / "guide_assets.py").read_text(encoding="utf-8")))
    assert {"credentials_guide_pdf", "pdf_from_html"} <= cached, (
        "guide_assets no longer caches the guide builders — the 721 ms is back."
    )


@pytest.mark.parametrize("shape", ["inline_write_pdf", "inline_builder_call"])
def test_the_guard_goes_red_on_the_defect_it_was_written_for(tmp_path, shape):
    """Mutation: reintroduce the 2026-08-30 defect and require a red.

    A guard whose red has never been seen does not distinguish "fixed" from "blind".
    """
    body = {
        "inline_write_pdf": (
            "import streamlit as st\n"
            "from weasyprint import HTML\n"
            "def show():\n"
            "    pdf_bytes = HTML(string='<p>x</p>').write_pdf()\n"
            "    st.download_button('dl', data=pdf_bytes, file_name='a.pdf')\n"
        ),
        "inline_builder_call": (
            "import streamlit as st\n"
            "from src.dashboard.guides.guide_pdf import build_guide_pdf\n"
            "def show():\n"
            "    st.download_button('dl', data=build_guide_pdf('fr').read_bytes(),\n"
            "                       file_name='a.pdf')\n"
        ),
    }[shape]
    mutant = tmp_path / "mutant_view.py"
    mutant.write_text(body, encoding="utf-8")
    assert offending_downloads([mutant]), (
        f"The guard stayed green on shape {shape!r} — it does not see the defect."
    )


def test_the_guard_stays_green_on_the_three_accepted_shapes(tmp_path):
    """The counterpart: the fixed code and the click-gated code must NOT be flagged."""
    gated = tmp_path / "gated_view.py"
    gated.write_text(
        "import streamlit as st\n"
        "def show():\n"
        "    if st.button('Generate'):\n"
        "        from weasyprint import HTML\n"
        "        st.session_state['_b'] = HTML(string='x').write_pdf()\n"
        "    if st.session_state.get('_b'):\n"
        "        st.download_button('dl', data=st.session_state['_b'], file_name='a.pdf')\n",
        encoding="utf-8")
    assert not offending_downloads([gated])
    # And the real, fixed views.
    assert not offending_downloads([
        _VIEWS / "process_guide.py", _VIEWS / "onboarding.py",
        _VIEWS / "export_pdf.py", _VIEWS / "export_csv.py",
    ])
