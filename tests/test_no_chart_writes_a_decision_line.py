"""R491 — no « 🎯 decision » line under any chart ; the purpose stays in the charts dossier.

Type: Test
Uses: src/dashboard/utils/charts.py, tools/dev/charts_dossier/review.yaml

Owner, 2026-10-09 : « aucun texte d'aide sous les graphiques — si le graphique est bien
pensé, pas besoin d'aide textuelle ». R314 had put a decision line under every chart ;
twelve pages had already opted out one by one (R421 → R488). R491 reverses it at the
door, so no page can bring it back by forgetting an argument.

The question a chart answers is not dropped : it stays in the review that builds the
charts dossier, where a chart without one is still refused here.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import yaml

from src.dashboard.utils import charts

ROOT = Path(__file__).resolve().parents[1]


class _Target:
    def __init__(self):
        self.captions = []

    def plotly_chart(self, fig, **kw):
        return None

    def pyplot(self, fig, **kw):
        return None

    def caption(self, text):
        self.captions.append(text)


def _decision_captions(target: _Target) -> list[str]:
    return [c for c in target.captions if "🎯" in c]


def test_the_door_writes_no_decision_line():
    t = _Target()
    charts.plotly_chart(None, container=t)
    charts.pyplot(None, container=t)
    assert not _decision_captions(t), t.captions


def test_no_page_can_ask_for_it_back():
    for door in (charts.plotly_chart, charts.pyplot):
        params = inspect.signature(door).parameters
        assert not {"decision", "decision_key"} & set(params), door.__name__


def test_the_detector_sees_a_decision_caption():
    """Non-vacuité : a door that still wrote the line would be seen."""
    t = _Target()
    t.caption("🎯 Décider où mettre le budget.")
    assert _decision_captions(t)


def test_every_app_chart_keeps_its_question_in_the_dossier():
    review = yaml.safe_load((ROOT / "tools/dev/charts_dossier/review.yaml").read_text(
        encoding="utf-8"))
    missing = [k for k, r in review.items()
               if k.startswith("src/dashboard/") and not (r or {}).get("decision")]
    assert not missing, f"graphique sans la décision qu'il permet, dans le dossier : {missing}"
