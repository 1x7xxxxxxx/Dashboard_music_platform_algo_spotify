#!/usr/bin/env python3
"""What one full dashboard render costs, and what that bounds.

Type: Utility
Uses: streamlit.testing.v1.AppTest, src.dashboard.app, a live Postgres
Triggers: manual — `python3 tools/loadtest_dashboard.py`
Persists in: nothing (telemetry writes are silenced for the run)

Why this exists
---------------
On 2026-09-11 the question "how many users at once can we take?" was answered
by a derivation: per-VIEW render p50 = 61 ms, plus a few connection handshakes,
serialised by the GIL because Streamlit serves every session from ONE process.
That arithmetic gave ~25-50 active users.

Measured in the production container the same day, a full PAGE render — sidebar
and auth included, which the per-view figure never contained — costs **468 to
538 ms**, about eight times the number the derivation was built on. That is the
whole reason this file exists.

What it measures, and what it REFUSES to measure
------------------------------------------------
It measures **one full render at a time**: the whole app script (`app.py`), and
how many Postgres connections that render opens. Repeatedly, so you get a
distribution rather than an anecdote.

It does **not** measure concurrency, and it will not pretend to. The first
version did, with a thread pool, and the curve it drew was an artifact of the
harness. `--self-check` reproduces the proof in about ten seconds; measured in
the production container on 2026-09-11 with a **two-line** Streamlit script
(`st.write('hello')`, no app, no database, no plotly):

    1 thread → 352 ms     3 threads → 1216 ms     6 threads → 2144 ms + a timeout

`st.write('hello')` does not cost two seconds. `AppTest` serialises on its own
machinery under threads, so any concurrency curve drawn with it describes
`AppTest`, not this product — and a harness that degrades on an empty script
cannot say when a real one degrades. Measuring true concurrency needs clients
speaking Streamlit's websocket protocol: a browser-level load tool, not this
file.

Also outside the frame: Tornado and the websocket (a real rerun adds them), and
Cloudflare (run against the box, never the public name). `@st.cache_data` is
per-process, so N replicas mean N cold caches; the figure below is the WARM
cost, taken after a discarded warm-up render.

What a single-render cost does buy you
--------------------------------------
One process, one GIL, one render's Python at a time. So the ceiling is
renders/s ≈ 1 / render-seconds, and sustainable active users ≈ that × 0.7
(queueing headroom) × the seconds a user spends reading between two clicks. The
tool prints that arithmetic with the measured number in it and labels it a
derivation — because it is one, just no longer one resting on a guess.

Reading the output
------------------
`p50 / p95 ms` — one full render, warm caches, no contention.
`conns/render` — Postgres handshakes per render. The figure the 2026-08-30
    decision did not take: it timed QUERIES (2 ms) and concluded pooling was
    pointless. The handshake is 13 ms, and a render pays it ~4 times.
`peak backends` — high-water mark on the server, against a stock
    `max_connections` of 100 shared with Airflow and the API.

Usage
-----
    python3 tools/loadtest_dashboard.py                 # 10 renders of /home
    python3 tools/loadtest_dashboard.py -n 20 --page youtube
    python3 tools/loadtest_dashboard.py --self-check    # why there is no curve

Run it where the dashboard runs (`docker exec streamlytics_dashboard python
/app/tools/loadtest_dashboard.py`). It needs that environment: `DATABASE_URL`
or the `DATABASE_*` set, plus `FERNET_KEY` — `app.py` refuses to import without
it. `tools/` is in no container image, so copy the file in first.

Noise you can ignore
--------------------
Each render prints `RuntimeError: Runtime hasn't been created!` from
`streamlit/testing/v1/local_script_runner.py:_on_script_finished`, which sweeps
orphaned media files through a Runtime that bare mode never created. Harmless
for a measurement: the line above it, `self.on_event.send(...)`, is what signals
completion, so the render is already finished and timed when this raises.

    … | grep -vE "ScriptRunContext|Runtime hasn't"
"""
from __future__ import annotations

import argparse
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src" / "dashboard"))  # app.py does `from views.x import`

_APP = _ROOT / "src" / "dashboard" / "app.py"

# Measured on 2026-09-11 from inside the dashboard container, by connecting 15
# times and taking the median. Used only to price the connections a render
# opens; re-measure if the database moves off the box.
_HANDSHAKE_MS = 13.0


# ── Keeping the run out of the product's own records ────────────────────────
def _silence_telemetry() -> None:
    """A measurement must not write itself into the product's history.

    `usage_tracker.track()` writes a row per page view and the auth heartbeat
    upserts `active_sessions`. Left alone, a 20-render run puts synthetic rows
    into the very tables the dashboard reports on — and this repo has already
    shipped a suite that sent real e-mails to real people because nobody asked
    what the tests do to the outside world.
    """
    from src.dashboard.utils import usage_tracker
    usage_tracker.track = lambda *a, **k: None                      # type: ignore[assignment]
    usage_tracker.track_page_view = lambda *a, **k: None            # type: ignore[assignment]

    from src.dashboard import auth
    auth._maybe_bump_heartbeat = lambda *a, **k: None               # type: ignore[assignment]


class _ConnectionCounter:
    """Count every psycopg2 handshake performed while the block is open."""

    def __init__(self) -> None:
        self.count = 0
        self._original = None

    def __enter__(self) -> "_ConnectionCounter":
        from src.database.postgres_handler import PostgresHandler
        self._original = PostgresHandler._connect

        def counted(inner_self):  # noqa: ANN001
            self.count += 1
            return self._original(inner_self)

        PostgresHandler._connect = counted                          # type: ignore[assignment]
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        from src.database.postgres_handler import PostgresHandler
        PostgresHandler._connect = self._original                   # type: ignore[assignment]


def _peak_backends_sampler(stop: threading.Event, out: list[int]) -> None:
    """Sample the server's own connection count while renders are in flight."""
    from src.database.postgres_handler import PostgresHandler
    try:
        db = PostgresHandler.from_env_or_config()
    except Exception:
        return
    try:
        while not stop.is_set():
            try:
                rows = db.fetch_query(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
                )
                out.append(int(rows[0][0]))
            except Exception:
                pass
            stop.wait(0.05)
    finally:
        db.close()


_SHARED_COMPONENT_MANAGER = None


def _component_manager():
    """One component registry for the whole run — because the SERVER has one.

    `AppTest` caches its `BidiComponentManager` per INSTANCE
    (`app_test.py:373`), and this harness builds a fresh instance per render,
    so every render re-ran `discover_and_register_components()`. That call
    parses the METADATA of every installed distribution: profiled in the
    production container on 2026-09-11, **2565 distributions, ~585 ms, 68 % of
    the measured render**.

    The real server does it exactly once, at startup — `runtime.py:226`, and
    the method's own docstring says "On startup". So charging it to every
    rerun measured the harness, not the product. Scanning once here restores
    the server's arithmetic.

    This is the second artifact found in this file the same day; the first is
    what `--self-check` documents. A harness is a measuring instrument, and an
    instrument that has never been checked against a known quantity is a
    source of numbers, not of facts.
    """
    global _SHARED_COMPONENT_MANAGER
    if _SHARED_COMPONENT_MANAGER is None:
        from streamlit.components.v2.component_manager import BidiComponentManager
        manager = BidiComponentManager()
        manager.discover_and_register_components(start_file_watching=False)
        _SHARED_COMPONENT_MANAGER = manager
    return _SHARED_COMPONENT_MANAGER


def _render_once(page: str, artist_id: int, role: str, timeout: int) -> float:
    """Run the whole app script once; return wall-clock ms.

    The session is seeded on `session_state` BEFORE `.run()`, never from inside
    the script: a harness that re-seeds on every run hides exactly the state
    bugs it is supposed to expose.
    """
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_APP), default_timeout=timeout)
    at._bidi_component_manager = _component_manager()
    at.session_state["authenticated"] = True
    at.session_state["role"] = role
    at.session_state["artist_id"] = artist_id
    at.session_state["email"] = "loadtest@local"
    at.session_state["page"] = page
    at.query_params["page"] = page

    start = time.perf_counter()
    at.run()
    elapsed = (time.perf_counter() - start) * 1000

    if at.exception:
        raise RuntimeError(f"render raised: {at.exception[0].value}")
    return elapsed


# ── The self-check: why this tool draws no concurrency curve ────────────────
def _self_check() -> int:
    """Show that AppTest, not the app, is what degrades under threads.

    A two-line script with no app, no database and no plotly. If THIS slows
    down and times out as threads are added, no concurrency number taken with
    AppTest means anything.
    """
    from streamlit.testing.v1 import AppTest

    script = "import streamlit as st\nst.write('hello')\n"

    def one(_: int) -> float:
        start = time.perf_counter()
        AppTest.from_string(script, default_timeout=30).run()
        return (time.perf_counter() - start) * 1000

    print("Script témoin : `st.write('hello')`. Aucune app, aucune base.\n")
    print(f"{'fils':>5} {'ok':>4} {'échecs':>7} {'médiane ms':>11}")
    print("-" * 30)
    for threads in (1, 3, 6):
        times: list[float] = []
        failures = 0
        with ThreadPoolExecutor(max_workers=threads) as pool:
            for fut in [pool.submit(one, i) for i in range(threads * 2)]:
                try:
                    times.append(fut.result())
                except Exception:                    # noqa: BLE001 — the failure IS the point
                    failures += 1
        median = statistics.median(times) if times else float("nan")
        print(f"{threads:>5} {len(times):>4} {failures:>7} {median:>11.0f}")
    print("\nUn `st.write('hello')` ne coûte pas deux secondes. Si la médiane monte")
    print("et que des runs expirent, c'est AppTest qui sature, pas le produit —")
    print("donc aucune courbe de concurrence tracée avec lui ne vaut.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("-n", "--renders", type=int, default=10,
                        help="nombre de rendus mesurés (défaut 10)")
    parser.add_argument("--page", default="home")
    parser.add_argument("--artist-id", type=int, default=1)
    parser.add_argument("--role", default="artist", choices=["artist", "admin"])
    parser.add_argument("--timeout", type=int, default=120,
                        help="délai max d'un rendu, en secondes (défaut 120)")
    parser.add_argument("--think", default="5,10,20",
                        help="secondes entre deux clics, pour la dérivation (défaut 5,10,20)")
    parser.add_argument("--force-wsl", action="store_true",
                        help="mesurer quand même depuis /mnt/… (les temps y sont du bruit)")
    parser.add_argument("--self-check", action="store_true",
                        help="montrer pourquoi cet outil ne trace pas de courbe")
    args = parser.parse_args()

    if args.self_check:
        return _self_check()

    # On INTERROGE la porte unique au lieu de deviner ses entrées.
    #
    # La première version lisait `DATABASE_URL` / `DATABASE_HOST` pour dire « rien
    # n'est configuré », et `tests/test_one_door_onto_the_database.py` l'a refusée
    # en CI. Le garde a raison même ici : deux endroits qui savent nommer les
    # variables du DSN sont deux endroits à corriger le jour où elles changent.
    # Et ouvrir vraiment est un meilleur test que vérifier des noms — il attrape
    # aussi un mot de passe faux, que la présence d'une variable n'aurait pas vu.
    try:
        from src.database.postgres_handler import PostgresHandler
        PostgresHandler.from_env_or_config().close()
    except Exception as exc:      # noqa: BLE001 — le message compte, pas le type
        print(f"❌ Base injoignable ({type(exc).__name__}). Lancer là où le dashboard "
              f"tourne :\n   docker exec streamlytics_dashboard python "
              f"/app/tools/loadtest_dashboard.py", file=sys.stderr)
        return 1

    on_drvfs = str(_ROOT).startswith("/mnt/")
    if on_drvfs and not args.force_wsl:
        print("❌ Chemin /mnt/… : montage DrvFS sous WSL, où les latences sont gonflées\n"
              "   de 5× à 160×. Publier ce chiffre serait publier du bruit.\n"
              "   Lancer sur le serveur, ou --force-wsl si seul le nombre de CONNEXIONS\n"
              "   vous intéresse : c'est un comptage, pas un chronomètre.", file=sys.stderr)
        return 2

    _silence_telemetry()

    # Le PREMIER rendu porte tous les imports et remplit les caches. Le compter
    # publierait un coût de démarrage sous le nom de coût de rendu.
    print("préchauffage…", flush=True)
    try:
        warm = _render_once(args.page, args.artist_id, args.role, args.timeout)
    except Exception as exc:                         # noqa: BLE001
        print(f"❌ le préchauffage a échoué : {exc}", file=sys.stderr)
        return 1
    print(f"  premier rendu, imports + caches froids, EXCLU : {warm:.0f} ms\n")

    if on_drvfs:
        print("⚠️  --force-wsl : les colonnes de TEMPS sont du bruit ici. "
              "Seul `conns/rendu` vaut.\n")

    stop = threading.Event()
    peaks: list[int] = []
    sampler = threading.Thread(target=_peak_backends_sampler, args=(stop, peaks), daemon=True)
    sampler.start()

    latencies: list[float] = []
    failures = 0
    with _ConnectionCounter() as counter:
        for i in range(args.renders):
            try:
                latencies.append(
                    _render_once(args.page, args.artist_id, args.role, args.timeout))
            except Exception as exc:                 # noqa: BLE001 — a failed render IS a result
                failures += 1
                if failures == 1:
                    print(f"  première erreur : {exc}", file=sys.stderr)
            print(f"  {i + 1}/{args.renders}\r", end="", flush=True)
    stop.set()
    sampler.join(timeout=2)
    print(" " * 24 + "\r", end="")

    if not latencies:
        print("❌ aucun rendu n'a abouti.", file=sys.stderr)
        return 1

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[min(int(len(latencies) * 0.95), len(latencies) - 1)]
    per_render = counter.count / len(latencies)

    print(f"page={args.page} role={args.role} artist_id={args.artist_id}")
    print(f"rendus mesurés : {len(latencies)}   échecs : {failures}\n")
    print(f"  p50           {p50:>8.0f} ms")
    print(f"  p95           {p95:>8.0f} ms")
    print(f"  min / max     {latencies[0]:>8.0f} / {latencies[-1]:.0f} ms")
    print(f"  conns/rendu   {per_render:>8.1f}   (≈ {per_render * _HANDSHAKE_MS:.0f} ms "
          f"de poignées de main, {per_render * _HANDSHAKE_MS / p50 * 100:.0f} % du rendu)")
    print(f"  pic backends  {max(peaks) if peaks else 0:>8}   sur max_connections=100, "
          f"partagé avec Airflow et l'API")

    print("\n── Dérivé, PAS mesuré ────────────────────────────────────────────")
    print("Un processus, un GIL : les rendus se sérialisent.")
    ceiling = 1000.0 / p50
    print(f"  plafond    ≈ {ceiling:.1f} rendus/s   (1 / p50)")
    print(f"  soutenable ≈ {ceiling * 0.7:.1f} rendus/s   (×0,7 de marge de file)")
    for think in [int(x) for x in args.think.split(",") if x.strip()]:
        print(f"    un clic toutes les {think:>2} s  →  "
              f"~{ceiling * 0.7 * think:.0f} utilisateurs actifs")
    print("\nCes trois dernières lignes sont une arithmétique sur p50, pas une")
    print("observation. Pour la vraie concurrence : --self-check dit pourquoi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
