"""Le résumé quotidien s'écrit même incomplet, et le DIT.

Type: Test
Uses: pytest
Depends on: src/utils/daily_ops_metrics.py, migrations/125_daily_ops_metrics.sql
Persists in: daily_ops_metrics (nettoie ses propres lignes)

Ce que ce fichier tient
-----------------------
Prometheus garde 30 jours ; la traçabilité LONGUE vit en base. Le jour où Prometheus ne
répond pas, deux comportements sont possibles et un seul est bon :

* **ne rien écrire** — l'absence de ligne se lit alors comme « la surveillance n'a pas
  tourné », ce qui est un AUTRE problème et envoie chercher au mauvais endroit ;
* **écrire la ligne avec `complete = FALSE`** — on sait qu'on a mesuré, on sait ce qui
  manque, et la série ne fait pas de trou.

C'est le second. Le champ `complete` est ce qui distingue « zéro mesuré » de « pas de
mesure », et ce dépôt a une classe entière pour cette confusion.

Et le piège du comptage
------------------------
`peak_sessions` EXCLUT les canaris et le bac à sable. Ce n'est pas un raffinement :
mesuré le 2026-09-16, **320 des 1 043 événements d'une journée venaient du locataire
`sandbox`, c'est-à-dire de nous**. Les compter rapprochait artificiellement un seuil de
charge de son déclencheur.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.db_gate import requires_live_db

pytestmark = [
    requires_live_db(),
    pytest.mark.xdist_group("daily-ops-metrics"),
]

_PROBE_DAY = date(2000, 1, 3)      # une date qu'aucune exécution réelle n'écrira


@pytest.fixture
def db():
    from src.database.postgres_handler import PostgresHandler

    handler = PostgresHandler.from_env_or_config()
    yield handler
    try:
        handler.execute_query("DELETE FROM daily_ops_metrics WHERE day = %s",
                              (_PROBE_DAY,))
    finally:
        handler.close()


def test_an_unreachable_prometheus_still_writes_a_row(monkeypatch, db) -> None:
    """Prometheus muet → la ligne existe, et `complete` vaut FALSE."""
    from src.utils import daily_ops_metrics as dom

    monkeypatch.setattr(dom, "PROMETHEUS_URL", "http://127.0.0.1:1")   # rien n'écoute
    summary = dom.write(db, day=_PROBE_DAY)

    assert summary["complete"] is False, (
        "le résumé se déclare COMPLET alors que Prometheus n'a rien rendu — les zéros "
        "qui suivent se liraient comme des mesures."
    )
    rows = db.fetch_query(
        "SELECT complete, p95_render_ms FROM daily_ops_metrics WHERE day = %s",
        (_PROBE_DAY,))
    assert rows, (
        "aucune ligne écrite. L'absence se lit comme « la surveillance n'a pas tourné », "
        "ce qui est un autre problème et envoie chercher au mauvais endroit."
    )
    assert rows[0][0] is False
    assert rows[0][1] is None, (
        "une métrique absente est écrite comme une VALEUR — elle doit rester NULL, "
        "sinon un zéro inventé entre dans la série."
    )


def test_replaying_the_task_corrects_the_row_instead_of_duplicating(monkeypatch, db):
    """Une journée a UN résumé. Rejouer la tâche corrige, n'empile pas."""
    from src.utils import daily_ops_metrics as dom

    monkeypatch.setattr(dom, "PROMETHEUS_URL", "http://127.0.0.1:1")
    dom.write(db, day=_PROBE_DAY)
    dom.write(db, day=_PROBE_DAY)

    rows = db.fetch_query(
        "SELECT count(*) FROM daily_ops_metrics WHERE day = %s", (_PROBE_DAY,))
    assert rows[0][0] == 1, (
        f"{rows[0][0]} lignes pour un jour — `ON CONFLICT (day) DO UPDATE` a disparu. "
        "Une tâche rejouée doit corriger son résumé, pas en empiler un second."
    )


def test_the_peak_excludes_canaries_and_the_sandbox(db) -> None:
    """Un canari n'a jamais été un utilisateur.

    Mesuré : 320 des 1 043 événements d'une journée venaient du bac à sable — nous.
    Les compter rapprochait artificiellement un seuil de charge de son déclencheur.
    """
    from src.utils.daily_ops_metrics import _peak_sessions

    peak = _peak_sessions(db)
    assert peak is not None, "le pic est illisible — la requête est cassée"
    assert peak >= 0

    # Non-vacuité : la requête doit VRAIMENT joindre et filtrer, pas rendre 0 par hasard.
    import inspect

    src = inspect.getsource(_peak_sessions)
    for needle in ("is_canary", "is_sandbox", "saas_artists"):
        assert needle in src, (
            f"`{needle}` a disparu de la requête de pic : les canaris et le bac à sable "
            "recompteraient dans un seuil de charge."
        )


def test_no_column_outside_the_allowlist_can_be_written(db) -> None:
    """Règle transverse #8 : un nom de colonne interpolé se valide avant exécution."""
    from src.utils import daily_ops_metrics as dom

    original = dom.collect
    try:
        dom.collect = lambda _db, _day=None: {"day": _PROBE_DAY, "day; DROP TABLE x": 1}
        with pytest.raises(ValueError, match="hors allowlist"):
            dom.write(db, day=_PROBE_DAY)
    finally:
        dom.collect = original


def test_the_allowlist_covers_every_query() -> None:
    """Non-vacuité : une requête dont la colonne n'est pas permise ne s'écrirait jamais.

    C'est le mode d'échec silencieux de cette forme : la garde protège, et la métrique
    disparaît sans que rien ne le dise.
    """
    from src.utils.daily_ops_metrics import _QUERIES, _WRITABLE_COLUMNS

    missing = sorted(set(_QUERIES) - _WRITABLE_COLUMNS)
    assert not missing, (
        f"requête(s) dont la colonne n'est pas dans l'allowlist : {missing}. "
        "`write()` lèverait à chaque exécution."
    )
