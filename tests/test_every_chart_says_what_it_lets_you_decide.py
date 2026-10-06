"""R314 — every app chart says, under the figure, what it lets you decide in your campaigns.

Type: Test
Uses: tools/dev/charts_dossier/inventory.py (the static sites), tools/dev/build_chart_decisions.py,
      src/dashboard/utils/chart_key.py, src/dashboard/utils/charts.py
Depends on: src/dashboard/content/chart_decisions.py (generated from the charts review)
Persists in: nothing

The owner, 2026-09-28 — « une de mes exigences clés » : not the question the chart asks, but
what it lets you DECIDE when managing your marketing campaigns, under every chart, every time.
Four things must hold, and each can break without a sound:
1. every figure site of the app has a line, in French and English, written as an action
   (a sentence ending in « ? » is a question again), short enough to stay ONE line;
2. the module the app reads was generated from the review the owner validates;
3. the key the door computes at runtime is the dossier's key for that site — a drift would
   put the right line under the wrong chart;
4. every `decision_key=` a page passes (a helper drawn on several pages) has its line.
Grafana is excluded by the owner's choice (a DevOps question, not a campaign one).

Mutation record (2026-09-28): seen red on three lines deleted from the generated module
(check 1 and 2), and on the rank counted from 0 in chart_key.py (check 3).
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / "tools" / "dev" / "charts_dossier"
sys.path.insert(0, str(DOSSIER))
sys.path.insert(0, str(ROOT / "tools" / "dev"))

MAX_LEN = 140


def line_problems(key: str, pair: tuple[str, str] | None) -> list[str]:
    """What is wrong with the decision line of one chart. Pure."""
    if pair is None:
        return [f"{key}: no decision line"]
    out = []
    for lang, text in zip(("fr", "en"), pair):
        text = (text or "").strip()
        if len(text) < 20:
            out.append(f"{key} [{lang}]: too short to say a decision ({text!r})")
        if text.endswith("?"):
            out.append(f"{key} [{lang}]: a question, not what it lets you decide")
        if len(text) > MAX_LEN:
            out.append(f"{key} [{lang}]: {len(text)} characters — one line, ≤ {MAX_LEN}")
    return out


def _decisions() -> dict:
    from src.dashboard.content.chart_decisions import DECISIONS
    return DECISIONS


def _app_sites() -> list[dict]:
    import inventory
    return [s for s in inventory.sites() if s["kind"] == "figure"]


def test_every_app_chart_has_its_decision_line() -> None:
    dec = _decisions()
    problems = [p for s in _app_sites()
                for p in line_problems(s["key"], dec.get(s["key"].removeprefix("src/dashboard/")))]
    assert not problems, ("charts without what they let you decide (write `decision:` and "
                          "`decision_en:` in tools/dev/charts_dossier/review.yaml, then "
                          "`make chart-decisions`):\n  " + "\n  ".join(problems))


def test_the_module_the_app_reads_is_the_review() -> None:
    out = subprocess.run([sys.executable, str(ROOT / "tools/dev/build_chart_decisions.py"),
                          "--check"], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def test_the_runtime_key_is_the_dossiers_key_for_every_site() -> None:
    from src.dashboard.utils.chart_key import key_at
    wrong = [(s["site"], s["key"], key_at(*s["site"].rsplit(":", 1)[:1],
                                          int(s["site"].rsplit(":", 1)[1])))
             for s in _app_sites()]
    wrong = [w for w in wrong if w[1] != w[2]]
    assert not wrong, f"the door would look up another chart's line: {wrong[:5]}"


def _decision_keys_passed(sources=None) -> set[str]:
    keys = set()
    if sources is None:
        sources = [f.read_text(encoding="utf-8") for f in (ROOT / "src").rglob("*.py")]
    for src in sources:
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "decision_key" and isinstance(kw.value, ast.Constant) \
                            and isinstance(kw.value.value, str):
                        keys.add(kw.value.value)
    return keys


def test_every_decision_key_a_page_passes_has_its_line() -> None:
    dec = _decisions()
    passed = _decision_keys_passed()
    # R421 (2026-10-06): home, the last page passing one, dropped its line at the owner's
    # request — `passed` may be empty. Non-vacuity moves to the scanner itself.
    assert _decision_keys_passed(['f(x, decision_key="views/x.py::f")']) == {"views/x.py::f"}, \
        "the scan no longer reads the calls"
    problems = [p for k in sorted(passed) for p in line_problems(k, dec.get(k))]
    assert not problems, "\n".join(problems)


def test_the_door_writes_the_line_under_the_chart(monkeypatch) -> None:
    from src.dashboard.utils import charts

    class Target:
        def __init__(self):
            self.calls = []

        def plotly_chart(self, fig, **kw):
            self.calls.append(("chart", None))

        def caption(self, text):
            self.calls.append(("caption", text))

    monkeypatch.setattr("src.dashboard.content.chart_decisions.DECISIONS",
                        {"views/x.py::f#1": ("Décider où mettre le budget de pub ce mois-ci.",
                                             "Decide where to put ad budget this month.")})
    t = Target()
    charts.plotly_chart(None, container=t, decision_key="views/x.py::f#1")
    assert t.calls[0][0] == "chart" and t.calls[1] == (
        "caption", "🎯 Décider où mettre le budget de pub ce mois-ci."), t.calls
    t2 = Target()
    charts.plotly_chart(None, container=t2, decision_key="views/unknown.py::g#1")
    assert all(c[0] == "chart" for c in t2.calls), "a key with no line must not print a blank"


def test_the_checks_are_not_vacuous_they_see_the_defects_they_are_written_for() -> None:
    assert line_problems("k", None) == ["k: no decision line"]
    assert any("question" in p for p in line_problems(
        "k", ("Quelle créa coûte le moins cher ?", "Which creative costs least here?")))
    assert any("≤" in p for p in line_problems("k", ("x" * 150, "y" * 30)))
    assert not line_problems("k", ("Choisir la créa à couper pour baisser le coût.",
                                   "Choose the creative to cut to lower the cost."))
