"""Une écriture sur une instance fait manquer son cache à l'autre.

Type: Test
Uses: pytest, subprocess
Depends on: src/dashboard/utils/cache_epoch.py, migrations/123_tenant_cache_epoch.sql
Persists in: saas_artists.cache_epoch (restauré)

Ce qui est en jeu
-----------------
`kpi_helpers.clear_kpi_caches()` purge onze `@st.cache_data(ttl=600)` — DANS LE
PROCESSUS QUI L'APPELLE. Tant qu'il y a une instance, « la purge est immédiate » est
vrai. À deux instances, un artiste déclenche une collecte sur A, voit ses nouveaux
chiffres, recharge, tombe sur B, et revoit les anciens **pendant dix minutes**.

C'est le préalable de R114 : sans lui, la seconde réplique sert des chiffres périmés.

Ce que chaque test prouve
--------------------------
Les trois premiers tiennent la LOGIQUE de décision (ne pas purger au démarrage, ne pas
purger sans changement, purger une seule fois) — elle n'a pas besoin de deux processus,
seulement d'une suite d'observations. Le quatrième touche la base et prouve que
l'incrément est réel et indivisible. Le dernier prouve que le rendu atteint vraiment la
couture, sans quoi tout le reste serait vert sur du code que rien n'exécute.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.db_gate import requires_live_db

pytestmark = [
    requires_live_db(),
    pytest.mark.xdist_group("tenant-cache-epoch"),
]

_ROOT = Path(__file__).resolve().parents[1]
_TENANT = 1


@pytest.fixture
def epoch_restored():
    """Rend au locataire l'époque qu'il avait — le compteur est MONOTONE en prod."""
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    try:
        before = db.fetch_query(
            "SELECT cache_epoch FROM saas_artists WHERE id = %s", (_TENANT,))[0][0]
    finally:
        db.close()
    yield before
    db = PostgresHandler.from_env_or_config()
    try:
        db.execute_query(
            "UPDATE saas_artists SET cache_epoch = %s WHERE id = %s", (before, _TENANT))
    finally:
        db.close()


def _observe(monkeypatch, epochs: list[int]) -> dict:
    """Fait voir `epochs` successivement à la logique, et dit si elle a purgé.

    ⚠️ Une version de ce helper lançait un SOUS-PROCESSUS avec un script qui posait
    les doublures par assignation d'attribut de module. Refusée par
    `tests/test_a_double_posed_in_a_rendered_script_is_taken_back.py`, et il avait
    raison sur la FORME même si le sous-processus rendait la fuite impossible : un
    garde textuel ne distingue pas les deux, et l'exempter aurait appris que son rouge
    est du bruit. `monkeypatch` restaure tout seul, et ces trois cas n'avaient de
    toute façon rien à prouver sur deux processus — c'est le dernier test du fichier
    qui touche la base.
    """
    from src.dashboard.utils import cache_epoch

    purged: list = []
    step = {"i": 0}

    def _read(_db, _aid):
        v = epochs[step["i"]]
        step["i"] += 1
        return v

    monkeypatch.setattr(cache_epoch, "_read", _read)
    monkeypatch.setattr(cache_epoch, "_SEEN", {})
    monkeypatch.setattr(cache_epoch, "_MINE", {})
    # R334: the purge counted is the LOCAL one. The emitting gate must never be reached
    # from a receiver — the old mock stood in for it, which is how the loop stayed green.
    monkeypatch.setattr("src.dashboard.utils.kpi_helpers.clear_local_caches",
                        lambda: purged.append(True))

    def _emitted(artist_id=None):
        raise AssertionError("a remote invalidation re-emitted the invalidation (R334)")
    monkeypatch.setattr("src.dashboard.utils.kpi_helpers.clear_kpi_caches", _emitted)
    monkeypatch.setattr(cache_epoch, "bump", _emitted)

    verdicts = [cache_epoch.honour_remote_invalidation(_TENANT, None) for _ in epochs]
    return {"purges": len(purged), "verdicts": verdicts}


def test_a_fresh_instance_does_not_purge_on_its_first_look(monkeypatch) -> None:
    """Un processus qui démarre n'a rien en cache — purger serait un coût pour rien."""
    assert _observe(monkeypatch, [7]) == {"purges": 0, "verdicts": [False]}


def test_an_unchanged_epoch_never_purges(monkeypatch) -> None:
    """Le cas de très loin le plus fréquent : personne n'a écrit."""
    out = _observe(monkeypatch, [7, 7, 7, 7])
    assert out["purges"] == 0, out
    assert out["verdicts"] == [False, False, False, False], out


def test_an_epoch_that_moved_purges_exactly_once(monkeypatch) -> None:
    """Une écriture ailleurs → une purge ici, et une seule."""
    out = _observe(monkeypatch, [7, 7, 8, 8, 8])
    assert out["purges"] == 1, (
        f"{out['purges']} purge(s) pour UNE écriture distante : {out}. "
        "Plus d'une : chaque rendu paierait une purge après la moindre écriture. "
        "Zéro : l'autre instance sert des chiffres périmés pendant dix minutes."
    )
    assert out["verdicts"] == [False, False, True, False, False], out


def test_the_write_really_moves_the_epoch_in_the_database(epoch_restored) -> None:
    """Le bout de chaîne réel : `bump()` incrémente, et une lecture neuve le voit."""
    from src.database.postgres_handler import PostgresHandler
    from src.dashboard.utils.cache_epoch import bump

    db = PostgresHandler.from_env_or_config()
    try:
        bump(_TENANT, db=db)
        bump(_TENANT, db=db)
        after = db.fetch_query(
            "SELECT cache_epoch FROM saas_artists WHERE id = %s", (_TENANT,))[0][0]
    finally:
        db.close()

    assert after == epoch_restored + 2, (
        f"époque {epoch_restored} → {after} après DEUX écritures. "
        "`cache_epoch = cache_epoch + 1` doit être indivisible : un `SELECT` puis "
        "`UPDATE` perdrait une des deux sous concurrence."
    )


def test_bump_never_raises_when_the_tenant_is_unknown() -> None:
    """Session admin sans locataire résolu : on ne devine pas un locataire."""
    from src.dashboard.utils.cache_epoch import bump

    bump(None, db=None)   # ne doit pas lever — et ne doit rien incrémenter
    bump(0, db=None)


def test_the_seam_is_actually_reached_by_a_real_render() -> None:
    """`view_session()` appelle vraiment la vérification — présence ≠ atteignabilité.

    Sans ce test, tout ce fichier pourrait être vert sur un module que RIEN n'exécute.
    Ce dépôt a payé six fois cette forme en une séance : du code correct qu'aucun
    chemin n'atteint, remonté par des artistes et invisible aux tests.

    On ne simule pas le rendu : on entre dans `view_session()` comme une vue le fait,
    et on observe que la vérification a été appelée avec LE locataire résolu.
    """
    from unittest import mock

    from src.dashboard.utils import view_session

    seen: list = []
    with mock.patch("src.dashboard.utils.cache_epoch.honour_remote_invalidation",
                    side_effect=lambda aid, db=None: seen.append(aid)):
        with mock.patch("src.dashboard.auth.get_artist_id", return_value=_TENANT), \
                mock.patch("src.dashboard.auth.is_admin", return_value=False):
            with view_session() as (_db, artist_id):
                assert artist_id == _TENANT

    assert seen == [_TENANT], (
        f"`view_session()` n'a pas consulté l'époque du locataire (appels : {seen}). "
        "Le module `cache_epoch` existerait alors sans qu'aucun rendu ne l'atteigne — "
        "l'invalidation ne traverserait jamais les instances, et tous les autres tests "
        "de ce fichier resteraient verts."
    )


class _EpochDB:
    """A saas_artists.cache_epoch in memory, with the one UPDATE … RETURNING bump sends."""

    def __init__(self, epoch: int) -> None:
        self.epoch, self.updates = epoch, 0

    def fetch_query(self, sql, params=None):
        if sql.lstrip().upper().startswith("UPDATE"):
            self.epoch += 1
            self.updates += 1
        return [(self.epoch,)]

    def close(self) -> None:
        pass


def test_a_purge_does_not_restart_the_loop_it_answers(monkeypatch) -> None:
    """R334 (2026-09-29) — real `clear_local_caches`, real `bump`, one remote write.

    Before: honour → clear_kpi_caches → bump moved the epoch again, read back 30 s later
    as another remote write, for ever. Mutation record (2026-09-29): seen red with honour
    calling `clear_kpi_caches()` again, and with `_MINE` no longer consulted.
    """
    from src.dashboard.utils import cache_epoch

    db = _EpochDB(7)
    monkeypatch.setattr(cache_epoch, "_read", lambda _db, _aid: _db.epoch)
    monkeypatch.setattr(cache_epoch, "_SEEN", {})
    monkeypatch.setattr(cache_epoch, "_MINE", {})
    monkeypatch.setattr("src.dashboard.utils.get_db_connection", lambda: db)
    assert cache_epoch.honour_remote_invalidation(_TENANT, db) is False  # first look
    db.epoch += 1                                                          # another instance
    assert cache_epoch.honour_remote_invalidation(_TENANT, db) is True
    assert db.updates == 0, "the purge wrote the epoch: every instance will purge again"
    assert [cache_epoch.honour_remote_invalidation(_TENANT, db) for _ in range(3)] == [False] * 3
    cache_epoch.bump(_TENANT, db=db)                                       # a write HERE
    assert cache_epoch.honour_remote_invalidation(_TENANT, db) is False, (
        "this process read its own bump back as a remote write")
