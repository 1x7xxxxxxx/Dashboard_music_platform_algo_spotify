#!/usr/bin/env python3
"""Le PIC memoire d'une suite pytest, en VmHWM, en suivant la DESCENDANCE.

Type: Utility
Uses: /proc
Triggers: `python3 tools/dev/pytest_peak_memory.py <chemin_de_test> <n_workers>`
Persists in: nothing

Pourquoi cet outil existe
--------------------------
Le 2026-09-17, `make test` a ete **tue par l'OOM** en pleine seance longue. Pour choisir
un nombre de workers il fallait le cout memoire d'un worker — et le mesurer a produit
DEUX erreurs d'affilee, toutes deux du meme genre.

**1. Echantillonner le RSS n'est pas mesurer un pic.** Premiere mesure : « ~300 Mo par
worker ». Vraie valeur en `VmHWM` : **508 Mo**. Ce depot a une lecon ecrite exactement
pour ca — *« le plafond memoire se mesure en VmHWM, jamais en echantillonnant »*, apres
225 Mo lus sur un pic reel de 3 Go — et elle a ete refaite.

**2. Chercher « pytest » dans les lignes de commande ne voit AUCUN worker.** xdist les
lance par `execnet` ; leur argv est un `python -c` anonyme. Deux essais ont rendu
« 1 processus » puis « 2 » avant qu'on suive la FILIATION depuis le controleur, qui ne
ment pas. Le nombre de processus qu'on croit voir est le premier chiffre a verifier.

Ce qu'il rend
--------------
Les pics par processus et leur somme. Mesure de reference, meme machine, meme jour :
`tests/test_views_render_smoke.py -n 2` → **508 · 265 · 126 Mo, total 899 Mo**.
C'est ce 508 qui fixe le diviseur de `PYTEST_WORKERS` dans le `Makefile`.
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
import subprocess
import sys
import threading
import time

peaks: dict[int, int] = {}
stop = threading.Event()

def children_of(root: int) -> set[int]:
    kids, changed = {root}, True
    while changed:
        changed = False
        for proc in pathlib.Path("/proc").iterdir():
            if not proc.name.isdigit() or int(proc.name) in kids:
                continue
            try:
                ppid = int((proc / "status").read_text().split("PPid:")[1].split()[0])
            except (OSError, IndexError, ValueError, StopIteration):  # zombie: no VmHWM
                continue
            if ppid in kids:
                kids.add(int(proc.name)); changed = True
    return kids

def watch(root):
    while not stop.is_set():
        for pid in children_of(root):
            try:
                st = (pathlib.Path("/proc") / str(pid) / "status").read_text()
                hwm = int(next(ln for ln in st.splitlines()
                               if ln.startswith("VmHWM")).split()[1])
                peaks[pid] = max(peaks.get(pid, 0), hwm // 1024)
            except (OSError, IndexError, ValueError, StopIteration):  # zombie: no VmHWM
                continue
        time.sleep(0.5)

proc = subprocess.Popen([".venv/bin/python", "-m", "pytest", sys.argv[1], "-q",
                         "-n", sys.argv[2], "--dist", "loadgroup"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
th = threading.Thread(target=watch, args=(proc.pid,), daemon=True); th.start()
proc.wait(); stop.set(); th.join(timeout=2)
vals = sorted((v for v in peaks.values() if v > 20), reverse=True)
print(f"-n {sys.argv[2]} → pics (Mo) : {vals}")
print(f"          total pic : {sum(vals)} Mo sur {len(vals)} processus")
