"""R598 — « Tes meilleurs réglages » live on the algo page, with the pooled photo.

Type: Hook
Depends on: src/dashboard/utils/best_settings_data.py, src/dashboard/utils/best_settings.py,
            src/dashboard/views/trigger_algo/{_settings,_sections,router}.py,
            src/dashboard/utils/plan_pitch.py

Owner, 2026-10-15 : « déplace les meilleurs réglages dans Prédiction algos, avec la photo
des réglages Meta optimaux ; décris l'offre sur Facturation ». Four properties:
  - the algo page renders a « reglages » section, and the cross view no longer does;
  - the campaigns are the ones mapped to the releases, newest first;
  - the photo POOLS the campaigns (Σ/Σ, never a mean of CPRs) and says when it cannot conclude;
  - the offer names the photo.
"""
import ast
from pathlib import Path

import pandas as pd

from src.dashboard.utils import best_settings, best_settings_data
from src.dashboard.views.trigger_algo._settings import linked_campaigns

ROOT = Path(__file__).resolve().parents[1]


def _calls(rel: str, fn: str) -> set[str]:
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == fn)
    return {ast.unparse(c.func) for c in ast.walk(node) if isinstance(c, ast.Call)}


def test_the_algo_page_has_the_section_and_the_cross_view_not():
    from src.dashboard.views.trigger_algo._sections import ALIAS_SECTION, section_keys
    assert "reglages" in section_keys()
    assert ALIAS_SECTION["meta_campaign_settings"] == "reglages"
    assert "show_settings" in _calls("src/dashboard/views/trigger_algo/router.py", "show")
    assert "_render_best_settings" not in _calls("src/dashboard/views/meta_creatives.py",
                                                 "_render_body")


def test_the_campaigns_are_the_releases_ones_newest_first():
    mapping = pd.DataFrame({"campaign_name": ["old", "new", "other"],
                            "song": ["A", "B", "Z"]})
    creatives = pd.DataFrame({"campaign_name": ["old", "new", "other"],
                              "campaign_start": ["2026-01-01", "2026-06-01", "2026-09-01"]})
    assert linked_campaigns(mapping, creatives, ["A", "B"]) == ["new", "old"]
    assert linked_campaigns(mapping, creatives, []) == []
    assert linked_campaigns(mapping.iloc[0:0], creatives, ["A"]) == []


def _frame(rows):
    return pd.DataFrame(rows, columns=["campaign_name", "v", "spend", "results"])


def test_the_photo_pools_the_campaigns_by_sums():
    # Pooled by sums, X costs 200 € / 120 clicks = 1.67 € and Y 200 / 90 = 2.22 €: X wins.
    # A mean of the campaigns' CPRs would give X (1 + 5) / 2 = 3 € and Y 2.25 €: Y would.
    f = _frame([("c1", "X", 100, 100), ("c1", "Y", 100, 40),
                ("c2", "X", 100, 20), ("c2", "Y", 100, 50)])
    p = best_settings_data.photo([("Créative", f, "v", "spend", "results")])
    row = p.iloc[0]
    assert row["meilleure"] == "X" and row["eviter"] == "Y"
    assert abs(row["cpr"] - 200 / 120) < 1e-3 and row["facteur"] == 1.3


def test_the_photo_says_when_it_cannot_conclude():
    thin = _frame([("c1", "X", 100, 50)])          # ONE reliable value: no rival
    p = best_settings_data.photo([("Pays", thin, "v", "spend", "results")])
    assert p.iloc[0]["cpr"] is None or pd.isna(p.iloc[0]["cpr"])
    assert p.iloc[0]["meilleure"] == "pas assez de données"
    fig = best_settings.photo_figure(p)
    assert fig is not None and len(fig.data[0].y) == 1     # the row stays, said empty
    assert best_settings.photo_figure(p.iloc[0:0]) is None


def test_the_offer_names_the_photo():
    from src.dashboard.utils.plan_pitch import _PITCH
    trigger = next(row for row in _PITCH if row[0] == "trigger_algo")
    assert "photo" in trigger[2] and "réglages Meta" in trigger[2]
