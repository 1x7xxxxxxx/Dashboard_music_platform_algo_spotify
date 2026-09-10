"""Aucune attente n'est illimitée : ni un appel HTTP, ni une connexion à la base.

Type: Test
Uses: pytest, ast
Depends on: src/collectors/, src/database/postgres_handler.py, src/utils/pg_connect.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
**Zéro `connect_timeout`, zéro `statement_timeout`** dans tout le dépôt. L'API tourne en
un seul processus avec des endpoints synchrones : si la base PEND au lieu de refuser
(partition réseau, `max_connections` atteint, table verrouillée), chaque requête retient
un thread jusqu'au délai TCP du système, ~2 minutes. Quarante requêtes concurrentes
suffisent alors à épuiser le pool — et `/health`, synchrone lui aussi, cesse de
répondre : **la sonde externe conclut que l'API est morte alors que seule la base pend**,
ce qui envoie chercher le problème au mauvais endroit.

Et trois appels HTTP du collecteur Instagram ne portaient aucun délai, quand tous les
autres collecteurs en déclarent un. Un appel pendu retient un créneau Airflow jusqu'au
`dagrun_timeout`.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _http_calls_without_timeout(path: Path) -> list[str]:
    """Les appels sur un objet `session`/`requests` sans `timeout=`."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    out = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        if n.func.attr not in ("get", "post", "put", "delete", "patch", "request"):
            continue
        holder = n.func.value
        # On ne juge QUE ce qui parle HTTP : `self.session.get(…)` ou `requests.get(…)`.
        # Sans cette restriction, chaque `dict.get()` du fichier remonterait — mesuré :
        # 52 faux positifs contre 3 vrais.
        name = getattr(holder, "attr", getattr(holder, "id", ""))
        if name not in ("session", "requests", "client"):
            continue
        if "timeout" not in {k.arg for k in n.keywords}:
            out.append(f"{path.name}:{n.lineno}")
    return out


def test_no_collector_makes_an_unbounded_http_call() -> None:
    offenders: list[str] = []
    for f in sorted((REPO / "src" / "collectors").rglob("*.py")):
        offenders += _http_calls_without_timeout(f)
    assert not offenders, (
        "appel HTTP sans délai : " + ", ".join(offenders)
        + ". Un appel pendu retient un créneau Airflow jusqu'au `dagrun_timeout`.")


def test_every_postgres_factory_bounds_its_wait() -> None:
    """Les deux fabriques de connexion bornent l'attente ET la requête."""
    for rel in ("src/database/postgres_handler.py", "src/utils/pg_connect.py"):
        src = (REPO / rel).read_text(encoding="utf-8")
        tree = ast.parse(src)
        connects = [n for n in ast.walk(tree)
                    if isinstance(n, ast.Call)
                    and getattr(n.func, "attr", "") == "connect"
                    and getattr(getattr(n.func, "value", None), "id", "") == "psycopg2"]
        assert connects, f"{rel} : plus aucune fabrique `psycopg2.connect` trouvée"
        for c in connects:
            rendered = ast.unparse(c)
            # Deux formes acceptées : les bornes écrites en clair dans l'appel, ou la
            # constante nommée déballée. Un garde qui n'accepterait que la première
            # obligerait à recopier les valeurs à chaque fabrique — soit exactement la
            # duplication que ce dépôt passe sa journée à retirer.
            direct = "connect_timeout" in rendered and "statement_timeout" in rendered
            via_const = "CONNECT_BOUNDS" in rendered
            assert direct or via_const, (
                f"{rel}:{c.lineno} — aucune borne d'attente : une base qui PEND retient "
                "un thread ~2 min, et l'API n'a qu'un processus.")


def test_the_named_bounds_actually_carry_both_limits() -> None:
    """La constante est vérifiée par sa VALEUR : la nommer ne suffit pas."""
    from src.utils.pg_connect import CONNECT_BOUNDS
    assert CONNECT_BOUNDS.get("connect_timeout"), "pas de délai de connexion"
    assert "statement_timeout" in (CONNECT_BOUNDS.get("options") or ""), (
        "pas de délai de requête : une table verrouillée retient un thread sans limite")


def test_the_predicate_would_see_a_bare_call() -> None:
    """Non-vacuité : le prédicat doit distinguer un vrai appel HTTP d'un `dict.get`."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "probe.py"
        f.write_text("d = {}\nd.get('x')\nself.session.get('u')\n", encoding="utf-8")
        found = _http_calls_without_timeout(f)
    assert len(found) == 1, f"attendu 1 vrai positif, obtenu {found}"
