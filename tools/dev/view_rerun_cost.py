#!/usr/bin/env python3
"""Ce que coute un rerun A CHAUD d'une vue — la grandeur qu'un fragment borne.

Type: Utility
Uses: streamlit.testing (AppTest)
Triggers: `python3 tools/dev/view_rerun_cost.py <vue> [<vue>...]`
Persists in: nothing

La mesure
----------
Rendu complet moins rendu vide, **dans le meme processus, alternes**, mediane de 4. Le
plancher d'`AppTest` — ~1,8 s ici — s'annule par soustraction ; alterner evite qu'une
serie paye la contention que l'autre a creee.

⚠️ CE QU'IL MESURE, ET CE QU'IL NE MESURE PAS
----------------------------------------------
Il mesure le **rerun a chaud**, jamais le cout d'une visite. La difference n'est pas
academique : confronte le 2026-09-17 aux quatre pages dont le cout SERVEUR est connu,
il n'a concorde qu'une fois sur quatre.

    instagram           serveur  96,3 ms  |  ici 104,9 ms   ✅
    meta_cpr_optimizer  serveur  98,7 ms  |  ici  10,8 ms   ❌
    apple_music         serveur  87,3 ms  |  ici   1,6 ms   ❌
    saisie_s4a          serveur  49,8 ms  |  ici  12,0 ms   ❌

L'explication est `@st.cache_data` : apres la chauffe, une page entierement memoisee ne
repaie plus rien, alors que la mesure serveur portait des visites a froid. Les trois
desaccords ne sont donc pas du bruit — ils DISENT que ces pages sont memoisees.

Consequence pratique : cet outil repond a « que borne un fragment ? » et a rien d'autre.
Pour le cout d'une visite, l'instrument est `streamlytics_rerun_duration_seconds`, cote
serveur, en conteneur. Annoncer « calibre » sur un accord sur quatre aurait ete le genre
de chiffre que ce depot a deja paye trois fois.
"""
import pathlib
import statistics
import sys
import time
ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, ROOT)
from streamlit.testing.v1 import AppTest

REAL = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "admin"; st.session_state["artist_id"] = 1
st.session_state["email"] = "a@t"; st.session_state["authenticated"] = True
from src.dashboard.views.{view} import show
show()
"""
NULL = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "admin"; st.session_state["artist_id"] = 1
st.write("x")
"""

def once(script):
    at = AppTest.from_string(script)
    t0 = time.perf_counter(); at.run(timeout=300)
    return (time.perf_counter() - t0) * 1000

base = []
for v in sys.argv[1:]:
    try:
        AppTest.from_string(REAL.format(root=ROOT, view=v)).run(timeout=300)   # chauffe
        full, floor = [], []
        for _ in range(4):                       # ALTERNER
            full.append(once(REAL.format(root=ROOT, view=v)))
            floor.append(once(NULL.format(root=ROOT)))
        mf, ml = statistics.median(full), statistics.median(floor)
        print(f"{v:20s} complet {mf:7.1f} ms | plancher {ml:7.1f} ms | "
              f"**vue {mf - ml:7.1f} ms**")
    except Exception as exc:
        print(f"{v:20s} ECHEC {type(exc).__name__}: {str(exc)[:60]}")
