"""Le budget anti-force-brute tient À TRAVERS les instances, et sous la rafale.

Type: Test
Uses: pytest, psycopg2 (via PostgresHandler), subprocess, threading
Depends on: src/utils/request_throttle.py, migrations/122_rate_limit_hits.sql
Persists in: rate_limit_hits (nettoie ses propres clés)

Pourquoi ce fichier existe
--------------------------
`tests/test_in_memory_limits_forbid_replicas.py` interdit la COMBINAISON répliques +
compteurs en mémoire. Il lit une déclaration ; il ne prouve rien sur le comportement.
Ce fichier-ci est la preuve : le budget vaut 10, pas 10 × N, et il le vaut vraiment.

Deux défauts distincts sont visés, et un seul test ne les couvre pas tous les deux.

1. **Le compteur vit dans le processus.** Prouvé par deux SOUS-PROCESSUS séparés :
   chacun importe le module à neuf, donc ni l'objet limiteur, ni l'état de module, ni
   un cache d'import ne peuvent porter le compte. Deux instances d'objet dans un même
   interpréteur ne l'auraient pas prouvé.

2. **`compter puis insérer` est un check-then-act.** En READ COMMITTED, deux
   transactions qui lisent `count(*)` avant que l'autre n'insère passent toutes les
   deux — le même défaut « budget × N », déplacé du processus vers la transaction.
   Prouvé par une rafale de fils simultanés : sans le verrou consultatif, le nombre
   d'acceptations dépasse le budget.

Le second test est celui qui compte : le premier passerait même sur une implémentation
qui court après elle-même, parce que ses deux sous-processus s'exécutent l'un après
l'autre.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

from tests.db_gate import requires_live_db

# UNE seule affectation de `pytestmark` — `test_the_http_escape_hatch_stays_narrow.py`
# refuse la seconde, et il a raison : réaffecter ce nom ÉCRASE la liste au lieu de
# l'étendre, donc la frontière qu'on croyait poser disparaît sans bruit.
# `xdist_group` parce que ce fichier écrit vraiment dans une table partagée.
pytestmark = [
    requires_live_db(),
    pytest.mark.xdist_group("rate-limit-hits"),
]

_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bucket() -> str:
    """Une clé unique par test, effacée après — deux exécutions ne se gênent pas."""
    key = f"test:{uuid.uuid4()}"
    yield key
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    try:
        db.execute_query("DELETE FROM rate_limit_hits WHERE bucket = %s", (key,))
    finally:
        db.close()


def _limiter(max_requests: int = 10, window_secs: int = 300):
    from src.utils.request_throttle import PostgresHitStore, SlidingWindowLimiter

    # Un magasin NEUF par limiteur : c'est ce qui rend le partage observable. Deux
    # limiteurs partageant l'objet magasin ne prouveraient que le partage d'un objet.
    return SlidingWindowLimiter(max_requests, window_secs, store=PostgresHitStore())


# ─────────────────────────────────────────────────────────────────────────────
# 1 — deux PROCESSUS, un seul budget
# ─────────────────────────────────────────────────────────────────────────────

_CHILD = """
import json, sys
sys.path.insert(0, {root!r})
from src.utils.request_throttle import PostgresHitStore, SlidingWindowLimiter

lim = SlidingWindowLimiter({maxr}, 300, store=PostgresHitStore())
out = [lim.hit({key!r}, now={now!r} + i * 0.001) for i in range({n})]
print(json.dumps(out))
"""


def _child_hits(bucket: str, n: int, now: float, maxr: int = 10) -> list:
    """Lance un interpréteur NEUF qui frappe `n` fois, et rend ses verdicts."""
    code = _CHILD.format(root=str(_ROOT), maxr=maxr, key=bucket, now=now, n=n)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=str(_ROOT), env=dict(os.environ), timeout=120,
    )
    assert proc.returncode == 0, f"sous-processus en échec :\n{proc.stderr[-2000:]}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_ten_attempts_split_over_two_processes_exhaust_one_budget(bucket: str) -> None:
    """5 tentatives sur « l'instance A », 5 sur « B », la 11e est refusée."""
    now = time.time()

    first = _child_hits(bucket, 5, now)
    assert first == [None] * 5, f"l'instance A a refusé dans son propre budget : {first}"

    second = _child_hits(bucket, 5, now + 1)
    assert second == [None] * 5, (
        f"l'instance B a refusé alors que le budget commun n'était pas épuisé : {second}"
    )

    eleventh = _child_hits(bucket, 1, now + 2)
    assert eleventh[0] is not None, (
        "la 11e tentative a été ACCEPTÉE : chaque processus tient son propre compte, "
        "donc le budget réel vaut 10 × nombre d'instances sur un chemin "
        "d'authentification. C'est exactement le défaut que le magasin partagé "
        "supprime."
    )
    assert 0 < eleventh[0] <= 300, f"délai d'attente hors fenêtre : {eleventh[0]}"


def test_the_two_processes_would_not_share_an_in_memory_store(bucket: str) -> None:
    """Contrôle NÉGATIF : la même rampe en mémoire laisse passer les 11.

    Sans lui, le test ci-dessus serait vert sur n'importe quel magasin qui refuse
    au-delà de 5 pour une raison sans rapport.
    """
    code = _CHILD.format(
        root=str(_ROOT), maxr=10, key=bucket, now=time.time(), n=5
    ).replace("PostgresHitStore()", "InMemoryHitStore()").replace(
        "import PostgresHitStore", "import InMemoryHitStore"
    )
    outs = []
    for _ in range(3):
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
            cwd=str(_ROOT), env=dict(os.environ), timeout=120,
        )
        assert proc.returncode == 0, proc.stderr[-2000:]
        outs += json.loads(proc.stdout.strip().splitlines()[-1])

    assert outs == [None] * 15, (
        "un magasin EN MÉMOIRE devrait accepter 15 tentatives sur 3 processus "
        f"(5 chacun, budget 10) — obtenu {outs}. Le contrôle négatif ne contrôle plus "
        "rien, donc le test positif ne prouve plus rien."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2 — la rafale SIMULTANÉE ne dépasse pas le budget
# ─────────────────────────────────────────────────────────────────────────────

def test_a_simultaneous_burst_never_exceeds_the_budget(bucket: str) -> None:
    """32 fils partent ensemble sur un budget de 5 : exactement 5 passent.

    C'est le test du verrou consultatif. `DELETE / count(*) / INSERT` sans lui est un
    check-then-act : en READ COMMITTED, deux transactions lisent le même compte avant
    que l'une n'insère, et toutes les deux concluent qu'il reste de la place.
    """
    budget, threads = 5, 32
    lim_by_thread = [_limiter(budget, 300) for _ in range(threads)]
    now = time.time()
    verdicts: list = [None] * threads
    start = threading.Barrier(threads)

    def run(i: int) -> None:
        start.wait(timeout=60)
        verdicts[i] = lim_by_thread[i].hit(bucket, now=now)

    workers = [threading.Thread(target=run, args=(i,)) for i in range(threads)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=120)

    accepted = sum(1 for v in verdicts if v is None)
    assert accepted == budget, (
        f"{accepted} tentatives acceptées sur un budget de {budget}, "
        f"{threads} fils simultanés. Au-dessus : le comptage et l'insertion ne sont "
        "pas indivisibles (check-then-act sous READ COMMITTED). En dessous : une "
        "tentative a été perdue, ce qui refuserait un utilisateur honnête."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3 — le mode dégradé est BORNÉ, pas ouvert
# ─────────────────────────────────────────────────────────────────────────────

def test_a_database_outage_degrades_to_a_bounded_in_memory_budget(bucket: str) -> None:
    """Base injoignable : on limite toujours, en mémoire — jamais « aucune limite ».

    Le choix est fail-open par rapport à la BASE (une panne de base ne doit pas rendre
    500 sur toute authentification) et fail-closed par rapport au BUDGET (le repli
    compte). Sans le repli, une panne de base supprimerait la limitation.
    """
    from src.utils.request_throttle import PostgresHitStore, SlidingWindowLimiter

    store = PostgresHitStore()

    def _explode():
        raise RuntimeError("base injoignable (simulée)")

    store._handler = _explode  # type: ignore[method-assign]
    lim = SlidingWindowLimiter(3, 300, store=store)

    now = time.time()
    verdicts = [lim.hit(bucket, now=now + i * 0.001) for i in range(5)]
    assert verdicts[:3] == [None, None, None], f"le repli refuse trop tôt : {verdicts}"
    assert all(v is not None for v in verdicts[3:]), (
        f"le repli a laissé passer 4 tentatives sur un budget de 3 : {verdicts}. "
        "Une panne de base ne doit pas supprimer la limitation."
    )

    # Et rien n'a été écrit en base pendant la panne.
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    try:
        rows = db.fetch_query(
            "SELECT count(*) FROM rate_limit_hits WHERE bucket = %s", (bucket,))
    finally:
        db.close()
    assert rows[0][0] == 0, "des coups ont été écrits alors que le handler levait"


# ─────────────────────────────────────────────────────────────────────────────
# 4 — la purge ne peut pas tronquer une fenêtre vivante
# ─────────────────────────────────────────────────────────────────────────────

def test_the_purge_refuses_when_a_window_would_outlive_its_margin(monkeypatch) -> None:
    """Porter une fenêtre au-delà d'un jour doit ARRÊTER la purge, pas la laisser faire.

    Les quatre fenêtres sont réglables par variable d'environnement. Au-dessus de la
    borne de purge, le `DELETE` nocturne efface des coups ENCORE DANS LA FENÊTRE : le
    budget repart à zéro chaque nuit, et rien ne le dit. Le seul endroit où les deux
    chiffres se rencontrent est ici.
    """
    from src.dashboard.utils import throttle
    from src.utils import rate_limit_maintenance as rlm

    # Une fenêtre de deux jours contre une purge à un jour.
    monkeypatch.setattr(throttle, "LOGIN_WINDOW_SECS", 2 * 86_400)
    with pytest.raises(ValueError, match="tronquerait une fenêtre VIVANTE"):
        rlm.purge_rate_limit_hits()


def test_the_purge_runs_with_todays_windows_and_deletes_only_old_rows(bucket: str) -> None:
    """Avec les réglages du produit, elle passe — et n'efface que ce qui est vieux."""
    from src.database.postgres_handler import PostgresHandler
    from src.utils import rate_limit_maintenance as rlm

    longest, windows = rlm.longest_window_secs()
    assert longest < rlm.PURGE_AFTER_SECS, windows

    db = PostgresHandler.from_env_or_config()
    try:
        # Une ligne fraîche et une ligne vieille de deux jours, même clé.
        db.execute_query(
            "INSERT INTO rate_limit_hits (bucket, ts, created_at) VALUES "
            "(%s, %s, now()), (%s, %s, now() - interval '2 days')",
            (bucket, time.time(), bucket, time.time() - 2 * 86_400))
        rlm.purge_rate_limit_hits(db=db)
        rows = db.fetch_query(
            "SELECT count(*) FROM rate_limit_hits WHERE bucket = %s", (bucket,))
    finally:
        db.close()

    assert rows[0][0] == 1, (
        f"{rows[0][0]} ligne(s) restante(s) au lieu d'une : la purge efface trop "
        "(elle a emporté la ligne fraîche) ou pas assez (elle n'a pas vu la vieille)."
    )
