#!/usr/bin/env python3
"""Profiler une vue DANS le thread qui l'execute — le seul endroit ou elle est visible.

Type: Utility
Uses: streamlit.testing (AppTest), cProfile
Triggers: `python3 tools/dev/profile_view_in_thread.py <vue>`
Persists in: nothing

⚠️ LE PIEGE QUE CET OUTIL EXISTE POUR EVITER
---------------------------------------------
`cProfile` ne profile que **le thread appelant**. `AppTest.run()` execute le script de
l'application dans un AUTRE thread. Un profil pose autour de `at.run()` ne voit donc
**aucune** frame de l'application — il voit le harnais.

Ce n'est pas theorique : le 2026-09-17, un profil pris ainsi a rendu
« `importlib.metadata` : 2,1 s cumulees, 1 007 lectures de METADATA » et j'en ai conclu
que le cout de la page etait ailleurs. Je lisais le harnais en croyant lire la page. Le
symptome qui aurait du alerter : **aucune ligne du depot dans les 30 premieres**.

Le profileur est donc pose DANS le script, autour du seul `show()`, et les statistiques
sont ecrites dans un fichier que le processus parent relit.

Ce qu'il a trouve le premier jour
----------------------------------
Sur l'accueil : `config_loader.load()` **12,5 ms** — un accesseur qui reparsait
2 424 octets de YAML a chaque appel — contre **1,4 ms** pour `_aggregate`, le poste que
la roadmap (R121) designait comme « le mieux place ». Le site nomme etait a 2 % du site
ignore.

Ce qu'il ne dit pas
--------------------
Les valeurs sont celles d'un rendu A CHAUD, caches `@st.cache_data` remplis par la
chauffe. Une visite froide paye davantage, et le seul instrument qui la mesure est
`streamlytics_rerun_duration_seconds`, cote serveur.
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
import pathlib
import pstats
import sys
ROOT = str(pathlib.Path(__file__).resolve().parents[2])
REPO_NAME = pathlib.Path(ROOT).name
sys.path.insert(0, ROOT)
from streamlit.testing.v1 import AppTest

VIEW = sys.argv[1]
OUT = "/tmp/claude-1000/prof.out"
S = """
import sys, cProfile
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "admin"; st.session_state["artist_id"] = 1
st.session_state["email"] = "a@t"; st.session_state["authenticated"] = True
from src.dashboard.views.{view} import show
_pr = cProfile.Profile(); _pr.enable()
show()
_pr.disable(); _pr.dump_stats({out!r})
"""
AppTest.from_string(S.format(root=ROOT, view=VIEW, out="/tmp/claude-1000/warm.out")).run(timeout=300)
AppTest.from_string(S.format(root=ROOT, view=VIEW, out=OUT)).run(timeout=300)

st = pstats.Stats(OUT)
print(f"=== {VIEW} : {st.total_tt:.3f} s cumules dans show()")
rows = []
for (f, line, n), (_cc, nc, tt, ct, _cal) in st.stats.items():
    if ROOT in f and "site-packages" not in f:
        rows.append((ct, tt, nc, f.split(REPO_NAME + "/")[-1], line, n))
for ct, tt, nc, f, line, n in sorted(rows, reverse=True)[:26]:
    print(f"  cum {ct*1000:7.1f} ms  propre {tt*1000:6.1f} ms  {nc:6d}x  {f}:{line} {n}")
