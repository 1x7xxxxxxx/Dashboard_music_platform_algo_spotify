"""Garde : l'effacement RGPD atteint TOUTES les tables du locataire, pas une liste.

Type: Utility
Uses: pytest, psycopg2 (via PostgresHandler), tests.db_gate
Triggers: pytest
Persists in: nothing — every write happens in a transaction that is rolled back

Ce qui a été mesuré le 2026-09-23
----------------------------------
En rédigeant la section « Connexion avec Google » de la politique de confidentialité,
qui promet un « droit à l'effacement », on a confronté `_GDPR_PLATFORM_TABLES` au
schéma local : **~80 tables** portent un `artist_id` INTEGER, la liste en atteignait
**22**. Hors de portée, entre autres : `usage_events` (les pages vues), tous les
`youtube_*`, les `meta_insights_*` par ventilation, `instagram_media*`, `s4a_audience`,
`distrokid_*`, `imusician_*`, `app_error_log`.

Pire que l'oubli : **57 clés étrangères vers `saas_artists` sont en `NO ACTION`**, et
deux passent par une AUTRE colonne que `artist_id` — `tracks.saas_artist_id`,
`referral_events.referrer_artist_id`. Une seule ligne restante dans l'une d'elles
fait échouer le `DELETE FROM saas_artists` final : l'effacement meurt à mi-chemin,
et le reçu n'est jamais écrit.

Le remède n'est pas d'allonger la liste — elle pourrirait de nouveau à la prochaine
table. `_erasure_scope()` lit le schéma VIVANT : toute colonne à clé étrangère vers
`saas_artists(id)`, plus tout `artist_id` INTEGER, dans l'ordre enfants → parents.

Ce que ce garde couvre : un locataire synthétique reçoit des lignes dans trois tables
que l'ancienne liste manquait, chacune d'une forme différente (sans clé étrangère,
clé `NO ACTION` sur `artist_id`, clé `NO ACTION` sur une autre colonne), et
l'effacement doit les vider TOUTES et supprimer le locataire, sans un `ÉCHEC` au reçu.
Ce qu'il NE couvre PAS : une donnée personnelle rangée sous un autre identifiant que
le locataire (un e-mail en clair dans une table sans `artist_id`, un `user_id`), ni
les tables qu'un autre service que Postgres héberge (fichiers, sauvegardes).
"""
from __future__ import annotations

import pytest

from tests.db_gate import db_ready as _db_ready

pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason="No provisioned Postgres on 127.0.0.1:5433 — ce garde efface pour de vrai",
)

_TENANT = 990201
#: A second artist the erased one referred. Their row must SURVIVE the erasure.
_OTHER = 990202


@pytest.fixture
def db():
    """Un handler en TRANSACTION, annulée quoi qu'il arrive.

    `PostgresHandler` vit en `autocommit` ; un garde qui efface pour de vrai doit
    ne rien laisser derrière lui, ni dans un sens ni dans l'autre.
    """
    from src.database.postgres_handler import PostgresHandler

    handler = PostgresHandler.from_env_or_config()
    handler.conn.autocommit = False
    try:
        yield handler
    finally:
        handler.conn.rollback()
        handler.conn.autocommit = True


def _seed(db) -> None:
    cur = db.conn.cursor()
    for aid, slug in ((_TENANT, "zz-erase"), (_OTHER, "zz-other")):
        cur.execute("INSERT INTO saas_artists (id, name, slug, active, tier) "
                    "VALUES (%s, %s, %s, TRUE, 'free')", (aid, slug, slug))
    # 1. no foreign key at all — only the INTEGER type says it is the tenant
    cur.execute("INSERT INTO usage_events (artist_id, event, page) "
                "VALUES (%s, 'page_view', 'privacy')", (_TENANT,))
    # 2. NO ACTION foreign key on `artist_id` — blocks the final delete if left
    cur.execute("INSERT INTO youtube_channels (channel_id, artist_id) "
                "VALUES ('zz-erase-chan', %s)", (_TENANT,))
    # 3. NO ACTION foreign key on ANOTHER column than `artist_id`
    cur.execute("INSERT INTO tracks (track_id, track_name, saas_artist_id) "
                "VALUES ('zz-erase-track', 'zz', %s)", (_TENANT,))
    # 4. a row that belongs to TWO artists: the erased one referred `_OTHER`
    cur.execute("INSERT INTO referral_events (referrer_artist_id, referred_artist_id, "
                "code_used) VALUES (%s, %s, 'ZZERASE')", (_TENANT, _OTHER))


def _remaining(db) -> dict[str, int]:
    cur = db.conn.cursor()
    out = {}
    for table, column in (("usage_events", "artist_id"), ("youtube_channels", "artist_id"),
                          ("tracks", "saas_artist_id"), ("saas_artists", "id")):
        cur.execute(f"SELECT count(*) FROM {table} WHERE {column} = %s", (_TENANT,))
        out[f"{table}.{column}"] = cur.fetchone()[0]
    return out


def test_the_erasure_empties_tables_the_hand_list_never_named(db):
    from src.dashboard.views.admin_accounts import _erase_artist_gdpr

    _seed(db)
    assert all(_remaining(db).values()), "non-vacuité : le locataire n'a pas été semé"

    receipt = _erase_artist_gdpr(db, _TENANT, admin_user_id=None, reason="test")

    echecs = {k: v for k, v in receipt.items() if str(v).startswith("ÉCHEC")}
    assert not echecs, f"l'effacement a échoué sur {echecs} — des données peuvent subsister"
    left = {k: n for k, n in _remaining(db).items() if n}
    assert not left, (
        f"après effacement, il reste {left}. Une table du locataire est hors de la "
        "portée de `_erasure_scope()` — ou la liste tenue à la main est revenue.")


def test_every_tenant_column_of_the_schema_is_allowlisted(db):
    """Sinon le reçu dit `non-allowlistée` et la table survit — règle 8 oblige."""
    from src.dashboard.views.admin_accounts import _tenant_columns_in_schema
    from src.database.postgres_handler import _ALLOWED_TABLES

    tables = {tb for tb, _ in _tenant_columns_in_schema(db)}
    assert len(tables) > 50, f"non-vacuité : {len(tables)} table(s) de locataire seulement"
    hors = sorted(tables - _ALLOWED_TABLES)
    assert not hors, (
        f"{hors} portent le locataire et ne sont pas dans `_ALLOWED_TABLES` : "
        "l'effacement RGPD les saute. Les ajouter à l'allowlist.")


def test_erasing_a_referrer_keeps_the_referred_artists_record(db):
    """Effacer X retire X, pas Y. Trouvé par `code-critic` avant commit : une portée
    dérivée du schéma supprimait la ligne entière, donc l'historique de Y."""
    from src.dashboard.views.admin_accounts import _erase_artist_gdpr

    _seed(db)
    _erase_artist_gdpr(db, _TENANT, admin_user_id=None, reason="test")
    cur = db.conn.cursor()
    cur.execute("SELECT referrer_artist_id FROM referral_events "
                "WHERE referred_artist_id = %s", (_OTHER,))
    rows = cur.fetchall()
    assert rows == [(None,)], (
        f"le parrainage de l'artiste {_OTHER} vaut {rows} après l'effacement de son "
        "parrain : attendu une ligne au parrain NULL (migration 136, ON DELETE SET NULL).")
    cur.execute("SELECT count(*) FROM saas_artists WHERE id = %s", (_OTHER,))
    assert cur.fetchone()[0] == 1, "l'effacement a atteint un AUTRE artiste"


class _FakeDb:
    def __init__(self, edges):
        self._edges = edges

    def fetch_query(self, *_a, **_k):
        return self._edges


def test_children_first_orders_children_before_parents_and_survives_a_cycle():
    from src.dashboard.views.admin_accounts import _children_first

    order = _children_first(_FakeDb([("child", "parent"), ("grandchild", "child")]),
                            {"parent", "child", "grandchild"})
    assert order.index("grandchild") < order.index("child") < order.index("parent"), order
    # A cycle must not loop forever nor drop a table: every table is still attempted.
    cyc = _children_first(_FakeDb([("a", "b"), ("b", "a")]), {"a", "b", "c"})
    assert sorted(cyc) == ["a", "b", "c"], cyc
