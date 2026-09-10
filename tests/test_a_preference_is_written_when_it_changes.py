"""Un choix qui n'a pas bougé ne se réécrit pas à chaque rerun.

Type: Test
Uses: pytest, monkeypatch
Depends on: src/dashboard/utils/lang_pref.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10, en production)
----------------------------------------------
**932 `UPDATE` sur `saas_users` pour 447 vues de page** — deux écritures par page pour
une valeur qui n'avait pas changé. Le sélecteur de langue est re-rendu à chaque rerun
Streamlit (chaque clic, chaque filtre, chaque navigation) et appelait `remember_lang`
sans rien comparer. Chaque écriture ouvre une connexion, prend un verrou de ligne et
laisse une version morte à l'autovacuum.

Trois comportements sont gardés ici, et le troisième est celui qu'on casse le plus
facilement en optimisant :

1. le premier choix s'écrit ;
2. le même choix, au rerun suivant, ne s'écrit plus ;
3. **une écriture qui a ÉCHOUÉ se retente** — marquer avant d'écrire ferait taire
   l'erreur en perdant le choix, ce qui échange une régression de performance contre
   une perte de donnée utilisateur.
"""
from __future__ import annotations

import pytest

from src.dashboard.utils import lang_pref


class _CountingDB:
    """Compte les écritures ; `boom=True` les fait échouer comme une base en panne."""

    def __init__(self, boom: bool = False):
        self.writes: list[tuple] = []
        self.boom = boom

    def execute_query(self, sql, params):
        if self.boom:
            raise RuntimeError("base injoignable")
        self.writes.append((sql, params))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def wired(monkeypatch):
    """Câble `session_state` et `project_db` sur des doublures, rend le compteur."""
    state: dict = {"user_id": 7}
    monkeypatch.setattr(lang_pref.st, "session_state", state, raising=False)
    db = _CountingDB()

    import src.dashboard.utils as utils
    monkeypatch.setattr(utils, "project_db", lambda *a, **k: db, raising=False)
    return state, db


def test_the_first_choice_is_written(wired) -> None:
    _state, db = wired
    lang_pref.remember_lang("en")
    assert len(db.writes) == 1, "le premier choix doit atteindre la base"
    assert db.writes[0][1] == ("en", 7)


def test_the_same_choice_is_not_rewritten_on_every_rerun(wired) -> None:
    _state, db = wired
    for _ in range(12):
        lang_pref.remember_lang("en")
    assert len(db.writes) == 1, (
        f"{len(db.writes)} écritures pour un choix qui n'a pas bougé — c'est la "
        "forme exacte des 932 UPDATE mesurés pour 447 vues de page")


def test_a_real_change_is_still_written(wired) -> None:
    _state, db = wired
    lang_pref.remember_lang("en")
    lang_pref.remember_lang("fr")
    lang_pref.remember_lang("en")
    assert len(db.writes) == 3, "chaque changement réel doit être persisté"


def test_a_value_already_read_from_the_database_is_not_rewritten(wired) -> None:
    """Au login on LIT la préférence : la réécrire est la première des deux écritures."""
    _state, db = wired
    lang_pref.mark_lang_persisted(7, "en")
    lang_pref.remember_lang("en")
    assert db.writes == []


def test_a_failed_write_is_retried_rather_than_marked_done(monkeypatch) -> None:
    """Marquer avant d'écrire perdrait le choix en silence."""
    state: dict = {"user_id": 7}
    monkeypatch.setattr(lang_pref.st, "session_state", state, raising=False)
    broken = _CountingDB(boom=True)
    import src.dashboard.utils as utils
    monkeypatch.setattr(utils, "project_db", lambda *a, **k: broken, raising=False)

    lang_pref.remember_lang("en")
    assert lang_pref._WROTE_KEY not in state, (
        "une écriture qui a échoué a été marquée comme faite : le choix de langue "
        "est perdu pour toute la session, sans que rien ne le dise")

    healthy = _CountingDB()
    monkeypatch.setattr(utils, "project_db", lambda *a, **k: healthy, raising=False)
    lang_pref.remember_lang("en")
    assert len(healthy.writes) == 1, "la retentative doit écrire"


def test_an_anonymous_visitor_writes_nothing(monkeypatch) -> None:
    monkeypatch.setattr(lang_pref.st, "session_state", {}, raising=False)
    db = _CountingDB()
    import src.dashboard.utils as utils
    monkeypatch.setattr(utils, "project_db", lambda *a, **k: db, raising=False)
    lang_pref.remember_lang("en")
    assert db.writes == []
