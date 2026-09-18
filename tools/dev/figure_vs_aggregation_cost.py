#!/usr/bin/env python3
"""Ou va le temps d'une vue : construire des FIGURES, ou AGREGER des donnees ?

Type: Utility
Uses: streamlit.testing (AppTest), plotly, pandas
Triggers: `python3 tools/dev/figure_vs_aggregation_cost.py <vue> [<vue>...]`
Persists in: nothing

La question qu'il tranche
--------------------------
R121 tenait que le cout des vues etait dans les agregations pandas, a passer en SQL.
Sept sites etaient nommes. Mesure le 2026-09-17 :

    meta_creatives      total 182 ms | figures 77 ms (42 %) | groupby 0,4 ms
    meta_ads_overview   total 189 ms | figures 51 ms (27 %) | groupby 0,2 ms

**Les agregations coutent moins d'une milliseconde.** Le cout est la construction des
figures — ce qu'ADR-007 avait deja profile en production le 2026-08-30 et que la brique
n'avait pas relu.

Pourquoi il n'utilise PAS cProfile
-----------------------------------
Un profileur gonfle ce qu'il mesure : le meme `meta_creatives` rend **601 ms** sous
`cProfile` et **182 ms** sans. Les parts relatives restent lisibles, le total non — et
c'est le total qu'on compare a une mesure serveur. Ici on enveloppe les constructeurs
(`px.*`, `go.Figure`, `DataFrame.groupby`) et on chronometre, sans profileur.

⚠️ Il tourne sous `AppTest`, a chaud. Les caches `@st.cache_data` sont remplis par la
chauffe : une visite FROIDE paye davantage, et seul `streamlytics_rerun_duration_seconds`
cote serveur la mesure.
"""

# ── OUTIL DE MESURE À USAGE PONCTUEL — lu par personne en routine (2026-09-18) ──
#
# Ce fichier n'est appelé par aucun automate : ni Makefile, ni CI, ni hook, ni signature
# du catalogue. C'est VOULU — c'est un instrument, pas un garde. Il ne prétend couvrir
# rien, donc son silence ne ment sur rien.
#
# Il est CONSERVÉ plutôt que supprimé pour une raison chiffrée : son coût est nul (il
# n'est ni injecté en contexte, ni collecté par la suite), et le réécrire coûterait la
# séance qui l'a produit. Sa mesure, elle, est consignée — voir
# `.claude/dev-docs/test-suite-performance.md` et `roadmap/archive.md`.
#
# Si tu le lances : relis d'abord ce que la mesure a déjà rendu. Ce dépôt a plusieurs
# fois remesuré ce qui était écrit à côté.
import os
import statistics
import sys
sys.path.insert(0, os.getcwd())
from streamlit.testing.v1 import AppTest

S = """
import sys, time
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "admin"; st.session_state["artist_id"] = 1
st.session_state["email"] = "a@t"; st.session_state["authenticated"] = True

import plotly.express as _px
import plotly.graph_objects as _go
import pandas as _pd
_T = {{"px": 0.0, "pd": 0.0, "n_px": 0, "n_pd": 0}}

def _wrap(mod, name, key):
    orig = getattr(mod, name)
    def inner(*a, **k):
        t0 = time.perf_counter()
        try:
            return orig(*a, **k)
        finally:
            _T[key] += (time.perf_counter() - t0) * 1000
            _T["n_" + key] += 1
    setattr(mod, name, inner)

for _n in ("line","bar","scatter","area","pie","density_heatmap","histogram","box","imshow"):
    if hasattr(_px, _n): _wrap(_px, _n, "px")
_wrap(_go, "Figure", "px")
_orig_gb = _pd.DataFrame.groupby
def _gb(self, *a, **k):
    t0 = time.perf_counter()
    try:
        return _orig_gb(self, *a, **k)
    finally:
        _T["pd"] += (time.perf_counter() - t0) * 1000
        _T["n_pd"] += 1
_pd.DataFrame.groupby = _gb

import time as _t
_start = _t.perf_counter()
from src.dashboard.views.{view} import show
show()
_T["total"] = (_t.perf_counter() - _start) * 1000
st.session_state["_t"] = dict(_T)
"""

for v in sys.argv[1:]:
    AppTest.from_string(S.format(root=os.getcwd(), view=v)).run(timeout=300)
    rows = []
    for _ in range(3):
        at = AppTest.from_string(S.format(root=os.getcwd(), view=v))
        at.run(timeout=300)
        rows.append(at.session_state["_t"])
    def med(k):
        return statistics.median(r[k] for r in rows)
    print(f"{v:20s} total {med('total'):6.0f} ms | figures {med('px'):6.0f} ms "
          f"({rows[0]['n_px']:2d}) | groupby {med('pd'):5.1f} ms ({rows[0]['n_pd']:2d})")
