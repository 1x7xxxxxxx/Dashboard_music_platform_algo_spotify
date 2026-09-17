"""Une retention declaree est appliquee, et une declaration incomprise ECHOUE.

Type: Sub
Uses: src.utils.telemetry_retention
Triggers: pytest
Depends on: src/utils/telemetry_retention.py, migration 124
Persists in: —

Error class `a-retention-declared-in-a-comment-and-applied-by-nobody`.

Le defaut mesure le 2026-09-17
-------------------------------
La migration 124 (2026-09-16) declare les retentions de 13 tables de telemetrie dans des
`COMMENT ON TABLE`, et affirme que « les purges correspondantes vivent dans
`src/utils/telemetry_retention.py` ». **Ce fichier n'existait pas.** Les retentions
etaient donc declarees en commentaire SQL et appliquees par personne — exactement la
situation que la migration pretendait fermer. `usage_events`, que la migration nomme
elle-meme « la table qui grossit le plus vite », croissait sans borne.

Les deux proprietes tenues
---------------------------
1. **Chaque forme de declaration a un traitement.** Cinq formes existent en base et
   elles ne disent pas la meme chose : un age simple, une condition (« les defauts
   RESOLUS », un defaut OUVERT n'est jamais purge), « garde tout », « bornee par
   construction » (une cle unique ecrase la ligne) et « TABLE MORTE ».
2. **Une declaration incomprise LEVE.** Sauter rendrait « rien a purger » et « je n'ai
   pas compris la declaration » indistinguables — le defaut d'origine sous une autre
   forme. Deux des cinq formes ont d'ailleurs ete trouvees comme ca : le module a leve
   sur la base reelle, au lieu de les ignorer.

Mutation record — 2026-09-17, trois mutations EXECUTEES et vues rouges :
  1. la branche finale `raise UndeclaredRetention` remplacee par `continue` -> rouge ;
  2. `_purge_conditional` purgeant AUSSI les defauts ouverts -> rouge ;
  3. `_purge_simple` sans sa clause d'age (purge tout) -> rouge.
0 apres remise en etat.

⚠️ Ce garde tourne SANS base : il exerce les fonctions pures et un faux `db`. Le
comportement contre la vraie base a ete verifie a la main le 2026-09-17 — une ligne de
200 jours supprimee, une de 10 jours epargnee — et c'est ce que `test_the_age_clause_
spares_recent_rows` rejoue en lisant le SQL emis.
"""
from __future__ import annotations

import pytest

from src.utils import telemetry_retention as tr


class _FakeDb:
    """Rend les commentaires qu'on lui donne et enregistre le SQL des suppressions."""

    def __init__(self, comments: dict[str, str]):
        self._comments = comments
        self.deletes: list[tuple[str, tuple]] = []

    def fetch_query(self, sql, params=None):
        if "obj_description" in sql and "pg_class" in sql:
            return sorted(self._comments.items())
        if sql.lstrip().upper().startswith("DELETE"):
            self.deletes.append((sql, params or ()))
            return [(1,)]
        return []

    def execute_query(self, sql, params=None):
        pass


def test_an_unrecognised_declaration_raises_instead_of_skipping():
    """Le coeur du garde : le silence est interdit."""
    db = _FakeDb({"mystere": "TÉLÉMÉTRIE. RÉTENTION : quand on aura le temps."})
    with pytest.raises(tr.UndeclaredRetention) as exc:
        tr.purge_telemetry(db)
    assert "mystere" in str(exc.value), (
        "L'exception ne nomme pas la table fautive : elle envoie chercher dans neuf "
        "commentaires."
    )


def test_a_table_declaring_days_without_an_age_column_raises():
    """Une migration future qui declare sans dire OU lire l'age doit se voir."""
    db = _FakeDb({"table_neuve": "TÉLÉMÉTRIE. RÉTENTION : 90 jours, purgée par alert_monitor."})
    with pytest.raises(tr.UndeclaredRetention) as exc:
        tr.purge_telemetry(db)
    assert "_AGE_COLUMN" in str(exc.value)


def test_the_five_shapes_are_each_routed_somewhere():
    """Cinq formes existent en base, et aucune ne doit tomber dans le trou."""
    db = _FakeDb({
        "usage_events": "RÉTENTION : 180 jours, purgée par alert_monitor.",
        "app_error_log": "RÉTENTION : les défauts RÉSOLUS depuis plus de 365 jours sont purgés.",
        "daily_ops_metrics": "RÉTENTION : garde tout.",
        "etl_circuit_breaker": "TÉLÉMÉTRIE bornée par construction : UNIQUE (platform, artist_id).",
        "etl_daily_metrics": "⚠️ TABLE MORTE — 2 lignes. RÉTENTION : rien.",
    })
    r = tr.purge_telemetry(db)
    assert set(r["purged"]) == {"usage_events", "app_error_log"}
    assert r["kept"] == ["daily_ops_metrics"]
    assert r["bounded"] == ["etl_circuit_breaker"]
    assert r["dead"] == ["etl_daily_metrics"]
    assert r["tables"] == 5


def test_an_open_defect_is_never_purged_however_old():
    """« Un défaut ouvert depuis deux ans est le plus intéressant du registre. »"""
    db = _FakeDb({"app_error_log":
                  "RÉTENTION : les défauts RÉSOLUS depuis plus de 365 jours sont purgés."})
    tr.purge_telemetry(db)
    sql = " ".join(s for s, _ in db.deletes)
    assert "resolved_at IS NOT NULL" in sql, (
        "La purge conditionnelle ne filtre pas sur `resolved_at IS NOT NULL` : elle "
        "effacerait des défauts OUVERTS, c'est-à-dire exactement les lignes que le "
        "registre existe pour garder."
    )


def test_the_age_clause_spares_recent_rows():
    """Une purge sans clause d'âge viderait la table entière."""
    db = _FakeDb({"usage_events": "RÉTENTION : 180 jours, purgée par alert_monitor."})
    tr.purge_telemetry(db)
    sql, params = db.deletes[0]
    assert "WHERE" in sql and "now() - make_interval" in sql, (
        "Le DELETE ne porte pas de clause d'âge : il viderait `usage_events` en entier. "
        "Vérifié à la main le 2026-09-17 contre la vraie base — une ligne de 200 jours "
        "supprimée, une de 10 jours épargnée."
    )
    assert params == (180,)


def test_the_age_column_of_every_purged_table_is_an_allowlist():
    """Un nom de table interpolé se valide contre une allowlist — règle transverse 8."""
    assert isinstance(tr._AGE_COLUMN, dict) and tr._AGE_COLUMN
    for table, column in tr._AGE_COLUMN.items():
        assert table.replace("_", "").isalnum(), f"nom de table douteux : {table!r}"
        assert column.replace("_", "").isalnum(), f"nom de colonne douteux : {column!r}"
