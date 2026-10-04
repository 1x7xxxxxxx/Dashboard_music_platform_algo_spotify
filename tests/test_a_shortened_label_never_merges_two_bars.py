"""A shortened label never makes two bars one category.

Type: Test
Uses: src.dashboard.utils.pdf_charts (_unique_labels, _hbar)
Depends on: nothing — pure
Persists in: nothing

R209 (2026-09-27), two sites the same night. A title and its remix cut to the same 24
characters became ONE matplotlib category in the PDF: both bars drew on one row, their
numbers overlapped (« 305 » inside the bar of 422, dossier fiche 96). The app's YouTube top
did the same with ten titles sharing a long prefix: ten bars stacked on one line.
"""
from __future__ import annotations

from src.dashboard.utils.pdf_charts import _short, _unique_labels


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the plain cut DOES merge these two names."""
    a, b = "Qui a sali mon slip avec de la gadoue?", "Qui a sali mon slip avec de la gadoue? (Remix)"
    assert _short(a) == _short(b), "the fixture no longer reproduces the collision"


def test_two_names_with_one_prefix_stay_two_labels() -> None:
    names = ["Qui a sali mon slip avec de la gadoue?",
             "Qui a sali mon slip avec de la gadoue? (Remix)", "Kimono"]
    labels = _unique_labels(names)
    assert len(set(labels)) == 3, labels
    assert labels[2] == "Kimono", "a label without a clash must stay the plain short one"


def test_even_a_middle_cut_clash_gets_its_rank() -> None:
    names = ["A" * 30 + "x" + "B" * 30, "A" * 30 + "y" + "B" * 30]
    assert len(set(_unique_labels(names))) == 2


def test_the_pdf_bar_chart_draws_one_row_per_name(monkeypatch) -> None:
    """The USE, not only the helper: `_hbar` itself must give each name its own row."""
    from src.dashboard.utils import pdf_charts
    captured = {}
    monkeypatch.setattr(pdf_charts, "_fig_to_uri", lambda fig: captured.setdefault("fig", fig))
    pdf_charts._hbar([("Qui a sali mon slip avec de la gadoue? (Remix)", 422),
                      ("Qui a sali mon slip avec de la gadoue?", 305)], "t")
    ax = captured["fig"].axes[0]
    rows = {round(b.get_y(), 3) for b in ax.patches}
    assert len(rows) == 2, "two names were drawn on ONE row: their labels merged"


# ── The structural guard: every « cut + … » in the dashboard is accounted for ──────────
import ast  # noqa: E402
from pathlib import Path  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]

# (file, enclosing function) → why this cut cannot merge two categories.
_ALLOWED = {
    ("src/dashboard/utils/labels.py", "plain"): "the helper itself — its caller dedupes",
    ("src/dashboard/utils/labels.py", "middle"): "the helper itself — its caller dedupes",
    ("src/dashboard/utils/pdf_charts.py", "_short"): "chart titles; bar labels go through _unique_labels",
    ("src/dashboard/views/youtube.py", "_cut"): "every label is prefixed with its rank",
    ("src/dashboard/views/meta_mapping/_campaigns.py", "_trunc"): "table cells, not an axis",
    ("src/dashboard/utils/pdf_exporter/_renderers.py", "_trunc"): "HTML <td> cells, not an axis",
    ("src/dashboard/views/billing.py", "_admin_frame"): "a Stripe id in a table cell",
}


def _cuts(tree) -> list[tuple[int, str]]:
    """(line, enclosing function) of every `x[:n] + '…'` — the cut-label idiom."""
    fns = [f for f in ast.walk(tree) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))]
    out = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add)
                and isinstance(n.left, ast.Subscript) and isinstance(n.left.slice, ast.Slice)
                and isinstance(n.right, ast.Constant) and n.right.value in ("…", "...")):
            inside = [f.name for f in fns if f.lineno <= n.lineno <= (f.end_lineno or 0)]
            out.append((n.lineno, inside[-1] if inside else "<module>"))
    return out


def test_every_cut_label_in_the_dashboard_is_accounted_for() -> None:
    unaccounted = []
    for p in sorted((_ROOT / "src/dashboard").rglob("*.py")):
        rel = str(p.relative_to(_ROOT))
        for line, fn in _cuts(ast.parse(p.read_text(encoding="utf-8"))):
            if (rel, fn) not in _ALLOWED:
                unaccounted.append(f"{rel}:{line} ({fn})")
    assert not unaccounted, (
        "a label is cut with « … » outside `utils/labels.unique_short_labels`: if it is an "
        f"axis category, two names can become one bar. Use the helper, or allow it with "
        f"its reason: {unaccounted}")


def test_the_structural_detector_sees_the_idiom() -> None:
    """Non-vacuity: the exact form of the three sites fixed on 2026-09-27."""
    defect = ast.parse('def f(d):\n    court = [s if len(s) <= 34 else s[:33] + "…" for s in d]\n')
    assert _cuts(defect) == [(2, "f")]
    fixed = ast.parse('def f(d):\n    court = unique_short_labels(d, 34)\n')
    assert _cuts(fixed) == []
