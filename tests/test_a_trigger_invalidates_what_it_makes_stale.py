"""Launching a DAG makes the cached DAG state wrong. Drop it there, not on a timer.

Type: Test
Uses: ast
Depends on: src/dashboard/**, src/dashboard/utils/airflow_monitor.py
Persists in: nothing

The gap this closes
-------------------
`cached_last_run_per_dag()` was added on 2026-08-30 to stop two artist-facing pages
paying 16 HTTP round-trips on every widget interaction. It shipped **without
invalidation**, and the moment that matters was exactly the one it got wrong:

    views/credentials/_render.py  saves credentials, triggers the DAG, and toasts
                                  "🚀 Collecte lancée — données dans ~2 min"

The artist then looks at the status — and would have been served a cached view of
the runs from before their own click, for up to the whole TTL. The page would have
told them nothing had started. That is the same shape as the defect the cached call
was introduced to fix (`home` showing 12 of 16 DAGs as "no run"), one layer up.

Why this is the right knob, and a shorter TTL is not
----------------------------------------------------
Measured on production `dag_run` over 7 days: **16.3 runs finish per hour**, median
16, **no empty hour**. No TTL short of seconds keeps the page current. But 384 of the
392 daily runs are the four CSV watchers, which no artist is reading. The value an
artist cares about changes once a night — or the instant they press the button.

So freshness here is **event-driven**. Clearing on the event makes that instant
exact; the TTL then only governs background drift and can be set for the reader (a
cold miss costs ~1 s, so 300 s means one stall per five-minute session instead of
five).
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DASH = _ROOT / "src" / "dashboard"

CACHE_NAME = "cached_last_run_per_dag"


def _success_scope(tree: ast.Module, call: ast.Call) -> list[ast.AST]:
    """Les instructions où un `clear()` compte pour CE déclenchement.

    ⚠️ Réécrit le 2026-09-16 après une critique qui a mesuré ce que la version
    précédente faisait vraiment. Elle cherchait le `ast.If` ENGLOBANT l'appel :

        best = innermost If such that `call` in ast.walk(If)

    Or le seul site de production écrit la forme la plus naturelle — l'appel
    d'abord, le test ensuite :

        result = trigger.trigger_dag(dag_id, conf={'artist_id': artist_id})
        if result.get('success'):
            cached_last_run_per_dag.clear()

    L'appel n'est donc PAS un descendant du `If`, aucun englobant n'existait, et la
    portée retombait sur `tree` — **le fichier entier**. Mutation exécutée : un
    `clear()` posé dans une fonction sans aucun rapport du même fichier contentait le
    garde. Le `long_term_fix` de la classe annonçait « remonte du `trigger_dag(...)` à
    son `if` » ; le code ne remontait nulle part et se rabattait sur un fichier.

    Le garde ne mentait pas sur un cas tordu : il mentait sur le SEUL cas réel, et sa
    propre mutation ne pouvait pas le voir parce qu'elle n'écrit aucun `clear()` du
    tout — un fichier sans `clear()` échoue même avec une portée large. C'est la forme
    `un-garde-qui-ne-garde-pas` : verte sur son mutant, aveugle sur sa cible.

    On lit désormais la SUITE : l'instruction qui porte l'appel, puis celles qui la
    suivent dans le même bloc. Un `clear()` placé avant le déclenchement, ou dans une
    autre fonction, ne compte plus.
    """
    best: tuple[int, list[ast.AST]] | None = None
    for parent in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(parent, field, None)
            if not isinstance(block, list):
                continue
            for index, stmt in enumerate(block):
                if not isinstance(stmt, ast.stmt):
                    continue
                if not any(n is call for n in ast.walk(stmt)):
                    continue
                # ⚠️ Le bloc le plus PROFOND, jamais le premier rencontré. `ast.walk`
                # visite le module avant la fonction : prendre le premier ferait
                # commencer la portée à la `def`, et un `clear()` écrit AVANT le
                # déclenchement — qui ne sert à rien, le cache se repeuplant ensuite —
                # contenterait le garde. Mesuré en écrivant ce correctif, sur le
                # deuxième mutant.
                depth = getattr(stmt, "lineno", 0)
                if best is None or depth > best[0]:
                    best = (depth, list(block[index:]))
    return best[1] if best else []


def _clears_the_cache(scope: list[ast.AST]) -> bool:
    return any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "clear"
        and getattr(n.func.value, "id", "") == CACHE_NAME
        for stmt in scope for n in ast.walk(stmt)
    )


def trigger_sites_without_invalidation(paths: list[Path]) -> list[str]:
    """`file:line` for every `trigger_dag(...)` whose success path never clears."""
    bad = []
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for call in ast.walk(tree):
            if not (isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "trigger_dag"):
                continue
            if not _clears_the_cache(_success_scope(tree, call)):
                try:
                    rel = path.relative_to(_ROOT)
                except ValueError:
                    rel = path
                bad.append(f"{rel}:{call.lineno}")
    return sorted(set(bad))


def _dashboard_sources() -> list[Path]:
    return sorted(_DASH.rglob("*.py"))


def test_every_dag_trigger_drops_the_cached_state():
    offenders = trigger_sites_without_invalidation(_dashboard_sources())
    assert not offenders, (
        "These launch a DAG without dropping the cached 'latest run per DAG':\n  "
        + "\n  ".join(offenders)
        + f"\n\nAdd `{CACHE_NAME}.clear()` on the success path. The artist reads the "
          "status immediately after triggering; serving them the runs from before "
          "their own click is the page telling them nothing started."
    )


def test_the_guard_goes_red_on_a_trigger_that_forgets(tmp_path):
    """Mutation: the shape that shipped on 2026-08-30 and had to be found by hand."""
    mutant = tmp_path / "forgot.py"
    mutant.write_text(
        "import streamlit as st\n"
        "def save(trigger, dag_id, artist_id):\n"
        "    result = trigger.trigger_dag(dag_id, conf={'artist_id': artist_id})\n"
        "    if result.get('success'):\n"
        "        st.toast('lancé')\n", encoding="utf-8")
    assert trigger_sites_without_invalidation([mutant]), (
        "the guard does not see a trigger whose success path never clears the cache"
    )

    ok = tmp_path / "clears.py"
    ok.write_text(
        "import streamlit as st\n"
        "def save(trigger, dag_id, artist_id):\n"
        "    result = trigger.trigger_dag(dag_id, conf={'artist_id': artist_id})\n"
        "    if result.get('success'):\n"
        "        from src.dashboard.utils.airflow_monitor import cached_last_run_per_dag\n"
        "        cached_last_run_per_dag.clear()\n"
        "        st.toast('lancé')\n", encoding="utf-8")
    assert trigger_sites_without_invalidation([ok]) == []


def test_a_clear_somewhere_else_in_the_file_does_not_count(tmp_path):
    """La mutation que la version précédente ne voyait pas — sur le SEUL cas réel.

    Jusqu'au 2026-09-16 la portée était le `ast.If` ENGLOBANT l'appel. Le site de
    production écrit `result = trigger.trigger_dag(...)` PUIS `if result.get(...)` :
    l'appel n'est pas un descendant du `if`, aucun englobant n'existait, et la portée
    retombait sur le fichier entier. Un `clear()` dans une fonction sans rapport
    suffisait donc — vérifié, puis corrigé.
    """
    mutant = tmp_path / "elsewhere.py"
    mutant.write_text(
        "import streamlit as st\n"
        "from src.dashboard.utils.airflow_monitor import cached_last_run_per_dag\n"
        "def unrelated_cleanup():\n"
        "    cached_last_run_per_dag.clear()\n"
        "def save(trigger, dag_id, artist_id):\n"
        "    result = trigger.trigger_dag(dag_id, conf={'artist_id': artist_id})\n"
        "    if result.get('success'):\n"
        "        st.toast('lancé')\n", encoding="utf-8")
    assert trigger_sites_without_invalidation([mutant]), (
        "un `clear()` d'une fonction sans rapport contente le garde — la portée est "
        "retombée sur le fichier"
    )


def test_a_clear_before_the_trigger_does_not_count(tmp_path):
    """Vider AVANT de déclencher ne sert à rien : le cache se repeuple juste après."""
    mutant = tmp_path / "too_early.py"
    mutant.write_text(
        "import streamlit as st\n"
        "from src.dashboard.utils.airflow_monitor import cached_last_run_per_dag\n"
        "def save(trigger, dag_id, artist_id):\n"
        "    cached_last_run_per_dag.clear()\n"
        "    result = trigger.trigger_dag(dag_id, conf={'artist_id': artist_id})\n"
        "    if result.get('success'):\n"
        "        st.toast('lancé')\n", encoding="utf-8")
    assert trigger_sites_without_invalidation([mutant]), (
        "un `clear()` posé avant le déclenchement contente le garde"
    )


def test_the_cache_still_exposes_clear_and_a_reader_sized_ttl():
    """The two halves of the design must both still be there.

    `.clear()` is what makes the artist's own click exact; the TTL is what keeps a
    five-minute visit from paying the ~1 s cold miss five times. Losing either
    silently turns this into a different trade-off than the one measured.
    """
    src = (_DASH / "utils" / "airflow_monitor.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next((f for f in ast.walk(tree)
               if isinstance(f, ast.FunctionDef) and f.name == CACHE_NAME), None)
    assert fn is not None, f"{CACHE_NAME} is gone — the trigger sites now call nothing"

    dec = next((d for d in fn.decorator_list if isinstance(d, ast.Call)), None)
    assert dec is not None, f"{CACHE_NAME} is no longer cached"
    ttl = next((kw.value for kw in dec.keywords if kw.arg == "ttl"), None)
    assert isinstance(ttl, ast.Constant) and 60 <= ttl.value <= 900, (
        f"ttl={getattr(ttl, 'value', None)} is outside 60..900 s. Below 60 the cold "
        "miss (~1 s, 16 HTTP round-trips) is paid constantly; above 900 the "
        "background drift stops being bounded by anything measured."
    )
