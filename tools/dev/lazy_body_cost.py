#!/usr/bin/env python3
"""Ce qu'un rendu PARESSEUX economiserait vraiment, sur une vue a onglets.

Type: Utility
Uses: streamlit.testing (AppTest)
Triggers: `python3 tools/dev/lazy_body_cost.py` — a la main, avant de refactorer
Persists in: nothing

Pourquoi cet outil existe
--------------------------
`st.tabs` execute TOUS les corps : c'est vrai, verifiable, et c'etait le premier poste
de R120. Mesure faite le 2026-09-17 sur `trigger_algo` (7 onglets, 11 figures, la vue
la plus chargee du produit) : **les six onglets caches coutent 0,1 ms a chaud.** Leur
travail passe par `@st.cache_data` ; les re-executer ne fait que relire le cache.

Le premier rendu, lui, paye : **866 ms** sur la meme mesure. La paresse aide donc la
visite FROIDE, une fois par TTL de cache — pas les reruns, qui sont ce qu'on voulait
alleger.

Les trois pieges, tous rencontres en ecrivant ce fichier
--------------------------------------------------------
1. **Le premier rendu d'un processus n'est pas comparable aux suivants** — imports,
   caches vides. Sans une chauffe, on mesure l'amorcage et on l'attribue au code.
   La serie brute le montre crument : `[866, 0, 0, 0, 0]`.
2. **`contextlib.nullcontext()` n'empeche pas le corps de s'executer.** Une premiere
   version remplacait `st.expander` par un `nullcontext` en croyant sauter le corps :
   elle mesurait le cout du WIDGET, pas du corps. `with` ne permet pas de sauter
   proprement — on chronometre, on ne saute pas.
3. **Deux mesures du meme fait peuvent se contredire, et l'une est fausse.** Le stub
   des six fonctions donnait 3,7 ms ; le chronometre par onglet donnait 701 ms. La
   seule facon de trancher a ete de les lancer DANS LE MEME PROCESSUS, alternees —
   le 701 etait un rendu froid. Une comparaison entre deux processus compare aussi
   leurs caches.

Ce qu'il ne dit pas
--------------------
Il tourne sous `AppTest`, dont le rendu porte ~1,8 s de harnais ici (1 007 lectures de
`METADATA`, 0,8 s de `time.sleep`). **Les valeurs ABSOLUES ne veulent rien dire** ; seul
le DELTA entre deux variantes du meme processus en veut. Pour l'absolu, l'instrument est
`streamlytics_rerun_duration_seconds`, cote serveur, en conteneur.
"""
import pathlib
import statistics
import sys
import time
ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, ROOT)
from streamlit.testing.v1 import AppTest

BASE = """
import sys, time, contextlib
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "admin"; st.session_state["artist_id"] = 1
st.session_state["email"] = "a@t"; st.session_state["authenticated"] = True
_HID = [0.0]
_real_tabs = st.tabs
@contextlib.contextmanager
def _t(inner, hidden):
    t0 = time.perf_counter()
    with inner as v:
        yield v
    if hidden: _HID[0] += (time.perf_counter() - t0) * 1000
def _tabs(*a, **k):
    made = _real_tabs(*a, **k)
    return [_t(x, i > 0) for i, x in enumerate(made)]
st.tabs = _tabs
{patch}
from src.dashboard.views.trigger_algo import show
show()
st.session_state["_hidden_ms"] = _HID[0]
"""
STUB = """
import src.dashboard.views.trigger_algo.router as _r
for _n in ("_show_tab_algos", "_show_tab_budget_roi", "_show_tab_explainability",
           "_show_tab_model", "_show_tab_lifecycle", "_show_tab_algo_streams"):
    setattr(_r, _n, lambda *a, **k: None)
"""

def one(patch):
    at = AppTest.from_string(BASE.format(root=ROOT, patch=patch))
    t0 = time.perf_counter(); at.run(timeout=300)
    return (time.perf_counter() - t0) * 1000, at.session_state["_hidden_ms"]

one("")                                    # chauffe
full, stub, hid = [], [], []
for _ in range(5):
    a, h = one("");   full.append(a); hid.append(h)
    b, _x = one(STUB); stub.append(b)
mf, ms = statistics.median(full), statistics.median(stub)
print(f"rendu complet          : {mf:8.1f} ms  {[round(x) for x in full]}")
print(f"6 onglets caches stubs : {ms:8.1f} ms  {[round(x) for x in stub]}")
print(f"chrono DANS ces 6      : {statistics.median(hid):8.1f} ms  {[round(x) for x in hid]}")
print(f"\nDELTA observe          : {mf - ms:8.1f} ms")
