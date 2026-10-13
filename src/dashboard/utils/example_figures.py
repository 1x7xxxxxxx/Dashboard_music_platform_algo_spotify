"""The example figures — one generic overview and the two promises, never tenant data.

Type: Utility
Uses: src/dashboard/assets/examples/*.png (built offline by `make example-charts`), i18n
Triggers: views/onboarding.py (« 1. streaMLytics en bref »), views/algo_preview.py
Persists in: nothing

R374 (2026-10-05, owner's screen review V11, V12, V55). R347 had removed the welcome
block's figures because the first one was drawn from the tenant's data — with its
platform legend, its decision sentence and its period comparison. The owner wants a
figure back, but a GENERIC one, always available: a new tenant has no data, and the
figure must say what the tool does, not what it has collected so far.

R480 (2026-10-09, W3) : no « Exemple — données fictives » any more, neither in the pixels
nor as a caption — the owner's call. The figures are shown only where the sentence beside
them presents what the tool will show. The two promise figures are generated at the same
pixel height so they sit level side by side.

ONE module so the algo preview shows the SAME prediction figure (V55: DW / RR / Radio had
no chart) instead of a second illustration that would drift from the first.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import streamlit as st


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "assets" / "examples"

OVERVIEW = "dashboard-global.png"
ALGO_PREDICTION = "prediction-discover-weekly.png"
CAMPAIGN = "meta-x-s4a.png"
PROMISES = (ALGO_PREDICTION, CAMPAIGN)   # the order the owner asked for (V12)
SHAP_OVERVIEW = "shap-overview.png"
# R545 (2026-10-12): the Meta-budget figure (R533) is retired — « les trois répondent bien ».
# R456 (C8, C10): the free Road to Algo preview shows the two promises, then the SHAP
# overview — every figure an example, never the tenant's data.
ALGO_PREVIEW = (ALGO_PREDICTION, CAMPAIGN, SHAP_OVERVIEW)

# R551 (2026-10-13) — where each illustration is drawn for REAL, and what the Vue croisée
# (`meta_ads_overview`) holds of it. Owner's question: « les schémas de l'assistant et de
# l'aperçu sont-ils bien dans la vue croisée ? » Measured answer: none is whole there. The
# owner chose to record the gap, not to add charts. Each counterpart is
# (page route, file, function); `cross_view` is "partial" or "absent", `gap` says what the
# illustration promises that no live chart of the Vue croisée draws.
# Guard: tests/test_every_illustration_names_its_live_chart.py
ILLUSTRATION_COUNTERPART: dict[str, dict] = {
    CAMPAIGN: {
        "cross_view": "partial",
        "counterparts": (
            ("meta_ads_overview", "src/dashboard/views/meta_ads_overview.py", "_render_timeline"),
        ),
        "gap": "streams, Meta €/jour, clics Hypeddit et CPR y sont ; la prévision des "
               "streams, la fenêtre Discover Weekly et le conseil « couper / relancer » non",
    },
    OVERVIEW: {
        "cross_view": "absent",
        "counterparts": (
            ("home", "src/dashboard/utils/platform_chart.py", "render_platform_chart"),
        ),
        "gap": "les aires empilées multi-plateformes vivent sur l'accueil, pas dans la "
               "vue croisée",
    },
    ALGO_PREDICTION: {
        "cross_view": "absent",
        "counterparts": (),
        "gap": "aucune figure réelle ne trace la probabilité DW / RR / Radio dans le "
               "temps (mesurée puis prévue) — ni dans la vue croisée, ni dans Prédiction",
    },
    SHAP_OVERVIEW: {
        "cross_view": "absent",
        "counterparts": (
            ("trigger_algo", "src/dashboard/views/trigger_algo/_playlist_detail.py", "_figure"),
        ),
        "gap": "le poids des critères par playlist vit dans Prédiction, sans le panneau "
               "« Ta track » ni le Meta € derrière",
    },
}


def render_example(name: str) -> None:
    """Show one prebuilt example figure at the width of its container.

    Missing, it renders nothing: the sentence beside it already states the promise.
    """
    path = EXAMPLES_DIR / name
    if path.exists():
        st.image(str(path), width="stretch")


def render_zigzag(rows: Sequence[tuple[str, Callable[[], None]]]) -> None:
    """One row per figure, figure and text side by side, sides alternating (R545).

    Owner, 2026-10-12: « un graphique à gauche avec sa description à droite, le deuxième
    graphique à droite et ce qu'on peut faire à gauche, et le dernier graphique à
    gauche » — row 0 puts the figure left, row 1 right, row 2 left again.
    """
    for i, (name, text) in enumerate(rows):
        left, right = st.columns(2, gap="large", vertical_alignment="center")
        figure_col, text_col = (left, right) if i % 2 == 0 else (right, left)
        with figure_col:
            render_example(name)
        with text_col:
            text()
