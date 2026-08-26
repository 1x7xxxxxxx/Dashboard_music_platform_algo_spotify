"""E2E — two tenants collecting side by side. No tenant may ever receive another's data.

Two artist test sessions failed the same way: every credential appeared broken and
the data shown was the ADMIN's. One implicit rule caused both — *when the system
cannot resolve a tenant's identity, it uses the admin's; when it does not know
whose row it is writing, it writes under `artist_id = 1`.*

This suite runs the REAL DAG collection functions against the provisioned Postgres,
with the platform HTTP layer stubbed so that **the response depends on the identity
that was requested**. That is the whole point: a row carrying tenant A's payload
under tenant B's `artist_id` is then directly observable, instead of being a
plausible story about production.

Gated on a live schema (same gate as test_api_db_smoke / test_views_render_smoke):
CI provisions one, so this runs on every commit.

Error classes: `tenant-identity-falls-back-to-admin`,
`write-without-explicit-artist-id`, `upsert-transfers-row-ownership`.
"""
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.dep_gate import requires

# Ce parcours CHARGE les modules de DAG (`_load_dag_module`) pour prouver
# l'isolation locataire de bout en bout. Sans `apache-airflow`, chaque
# chargement rend un module vide et l'échec parle de l'environnement.

_ROOT = Path(__file__).resolve().parents[1]


def _stub_module(name: str) -> None:
    """Insert a MagicMock as a top-level module (and all its dotted parents).

    **N'est plus appelé pour `spotipy` / `googleapiclient` depuis le 2026-08-24.** La
    prémisse — « ils vivent dans l'image Airflow, pas dans le venv de dev ou de CI » —
    est fausse : les quatre paquets sont des dépendances du projet et sont installés.

    Le stub était posé **à l'import du fichier de test**, donc dès la COLLECTE, et sans
    restauration : il remplaçait `spotipy` et `googleapiclient` par des MagicMock pour
    toute la session. Un test qui croit exercer le vrai client travaille alors contre
    un mock et passe au vert sans rien prouver — et un import légitime d'un
    sous-module échoue plus loin sur « n'est pas un paquet ». C'est ce qui est arrivé
    à `airflow.operators` le même jour, avec quatre DAGs qui tombaient en exécution
    groupée et passaient isolément.

    Le helper est conservé pour un paquet réellement absent ; ce jour-là, il n'y en a
    aucun.
    """
    parts = name.split(".")
    for i in range(1, len(parts) + 1):
        key = ".".join(parts[:i])
        if key not in sys.modules:
            sys.modules[key] = MagicMock()




def _load_dag_module(name: str):
    """Import a DAG file pour de vrai, et appeler ses fonctions de tâche.

    **Le stub d'`airflow` a été retiré le 2026-08-24, avec sa prémisse.** Ce helper
    posait `sys.modules.setdefault("airflow.operators", MagicMock())` en expliquant
    qu'« Airflow vit dans l'image Docker, pas dans le venv de dev/CI, donc les
    modules de DAG ne peuvent pas être importés normalement ». Les deux moitiés sont
    fausses aujourd'hui : Airflow **est** dans le venv, et depuis le retrait de
    `schedule_interval` et `provide_context` (deux vestiges d'Airflow 1/2.3 morts sur
    la 2.8.1 de production) les 16 DAGs s'importent réellement.

    Le stub n'était pas seulement inutile, il **cassait les autres tests** : posé
    sans jamais être restauré, il laissait `airflow.operators` être un MagicMock pour
    toute la suite, et tout import ultérieur de `airflow.operators.empty` échouait
    sur « 'airflow.operators' is not a package ». Quatre DAGs tombaient ainsi en
    exécution groupée et passaient isolément — la signature exacte d'une dépendance à
    l'ordre, dont ce dépôt a déjà payé un exemplaire (l'éviction `del sys.modules`).

    Importer pour de vrai est aussi plus fidèle : les opérateurs sont construits, donc
    une erreur de structure du DAG est vue ici, pas au réveil du scheduler.
    """
    key = f"dag_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(
        key, _ROOT / "airflow" / "dags" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module

# ── DB readiness gate ────────────────────────────────────────────────────────
from tests.db_gate import requires_live_db  # noqa: E402

# DEUX conditions, dans UNE liste. Elles étaient deux affectations séparées de
# `pytestmark` et la seconde ÉCRASAIT la première sans bruit — une porte qui a
# l'air posée et ne l'est pas. Ce parcours charge des modules de DAG, donc il
# lui faut `apache-airflow` autant que la base.
pytestmark = [requires("airflow"), requires_live_db()]

# Identities. ADMIN_* are what the environment variables hold in production; the
# whole class of bugs is a tenant silently ending up with these.
ADMIN_SC_USER = "999000111"
ADMIN_YT_CHANNEL = "UCadminadminadminadmin"
TENANT_SC_USER = "377065610"
TENANT_YT_CHANNEL = "UCtenanttenanttenantxx"


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture
def env_points_at_test_db(monkeypatch):
    """DAG code builds its own PostgresHandler from DATABASE_* — point it here.

    Also plants the ADMIN identities in the environment, exactly as production
    does, so any fallback to them is caught rather than hypothesised.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        from urllib.parse import urlparse
        u = urlparse(url)
        host, port = u.hostname or "localhost", str(u.port or 5432)
        user, password = u.username or "postgres", u.password or ""
        name = (u.path or "/spotify_etl").lstrip("/")
    else:
        from src.utils.config_loader import config_loader
        cfg = config_loader.load()["database"]
        host, port = cfg["host"], str(cfg["port"])
        user, password, name = cfg["user"], cfg["password"], cfg["database"]

    for key, value in (
        ("DATABASE_HOST", host), ("DATABASE_PORT", port), ("DATABASE_NAME", name),
        ("DATABASE_USER", user), ("DATABASE_PASSWORD", password),
        ("SOUNDCLOUD_CLIENT_ID", "app-client-id"),
        ("SOUNDCLOUD_CLIENT_SECRET", "app-client-secret"),
        ("SOUNDCLOUD_USER_ID", ADMIN_SC_USER),        # the admin's own profile
        ("YOUTUBE_API_KEY", "app-api-key"),
        ("YOUTUBE_CHANNEL_ID", ADMIN_YT_CHANNEL),     # the admin's own channel
    ):
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("LEGACY_SINGLE_TENANT", raising=False)
    monkeypatch.delenv("SOUNDCLOUD_REFRESH_TOKEN", raising=False)


@pytest.fixture
def tenant(db):
    """A freshly created, active tenant with no platform identity yet."""
    import uuid
    slug = f"e2e-{uuid.uuid4().hex[:10]}"
    rows = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active) "
        "VALUES (%s, %s, 'free', TRUE) RETURNING id",
        (f"E2E {slug}", slug),
    )
    artist_id = rows[0][0]
    yield artist_id
    for table in ("soundcloud_tracks_daily", "youtube_video_stats", "youtube_videos",
                  "youtube_channel_history", "youtube_channels",
                  "track_popularity_history", "artist_credentials"):
        try:
            db.execute_query(f"DELETE FROM {table} WHERE artist_id = %s", (artist_id,))
        except Exception:
            pass
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))


def _connect(db, artist_id: int, platform: str, extra: dict) -> None:
    import json
    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, %s, %s::jsonb) "
        "ON CONFLICT (artist_id, platform) DO UPDATE SET extra_config = EXCLUDED.extra_config",
        (artist_id, platform, json.dumps(extra)),
    )


def _dag_context(artist_id=None) -> dict:
    dag_run = MagicMock()
    dag_run.conf = {"artist_id": artist_id} if artist_id else {}
    return {"dag_run": dag_run, "task_instance": MagicMock()}


# ── SoundCloud: HTTP stub keyed on the requested identity ────────────────────

class _FakeSoundCloudAPI:
    """Returns a track whose title names the profile that was actually requested."""

    def __init__(self):
        self.requested_users = []

    def post(self, url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"access_token": "tok", "expires_in": 3600}
        return r

    def get(self, url, **kwargs):
        user_id = url.rstrip("/").split("/users/")[-1].split("/")[0]
        self.requested_users.append(user_id)
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {
            "collection": [{
                "id": f"track-of-{user_id}",
                "title": f"Track owned by {user_id}",
                "permalink_url": f"https://soundcloud.com/{user_id}/t",
                "playback_count": 10, "likes_count": 1, "reposts_count": 0,
                "comment_count": 0, "created_at": "2026-01-01T00:00:00Z",
            }],
            "next_href": None,
        }
        return r


@pytest.fixture
def fake_soundcloud():
    api = _FakeSoundCloudAPI()
    with patch("src.collectors.soundcloud_api_collector.requests.Session",
               return_value=api):
        yield api


def _run_soundcloud(artist_id=None):
    dag = _load_dag_module("soundcloud_daily")
    return dag.run_soundcloud_collector(**_dag_context(artist_id))


# ── The assertions ──────────────────────────────────────────────────────────

def test_connected_tenant_gets_its_own_data(db, tenant, env_points_at_test_db,
                                            fake_soundcloud):
    """Baseline: the happy path must actually work, or the rest proves nothing."""
    _connect(db, tenant, "soundcloud", {"user_id": TENANT_SC_USER})

    _run_soundcloud(artist_id=tenant)

    rows = db.fetch_query(
        "SELECT track_id FROM soundcloud_tracks_daily WHERE artist_id = %s", (tenant,)
    )
    assert rows, "the tenant collected nothing on the happy path"
    assert all(r[0] == f"track-of-{TENANT_SC_USER}" for r in rows)
    assert ADMIN_SC_USER not in fake_soundcloud.requested_users


def test_unconnected_tenant_collects_nothing_not_the_admins_data(
        db, tenant, env_points_at_test_db, fake_soundcloud):
    """A tenant with no identity must stay empty — never inherit the admin's.

    This is the beta failure, reduced to one assertion: the artist registered,
    never opened Credentials, and the next fleet run handed them the admin's
    SoundCloud profile under their own artist_id.
    """
    _run_soundcloud()  # fleet run, tenant has no soundcloud row

    rows = db.fetch_query(
        "SELECT track_id FROM soundcloud_tracks_daily WHERE artist_id = %s", (tenant,)
    )
    assert rows == [], f"unconnected tenant received rows: {rows}"
    assert ADMIN_SC_USER not in fake_soundcloud.requested_users, (
        "the admin's SOUNDCLOUD_USER_ID was fetched on behalf of a tenant"
    )


def test_empty_identity_is_treated_as_absent(db, tenant, env_points_at_test_db,
                                             fake_soundcloud):
    """`{"user_id": ""}` is falsy — it used to select the env (admin) branch.

    An artist who opens the SoundCloud tab and saves without filling it in is the
    single most likely gesture in a live test session.
    """
    _connect(db, tenant, "soundcloud", {"user_id": ""})

    _run_soundcloud(artist_id=tenant)

    rows = db.fetch_query(
        "SELECT track_id FROM soundcloud_tracks_daily WHERE artist_id = %s", (tenant,)
    )
    assert rows == [], f"tenant with a blank identity received rows: {rows}"
    assert ADMIN_SC_USER not in fake_soundcloud.requested_users


def test_unknown_artist_id_fails_loudly(db, env_points_at_test_db, fake_soundcloud):
    """`conf={'artist_id': 999999}` must not degrade into 'collect as tenant 1'."""
    from src.utils.credential_loader import UnknownArtistError

    with pytest.raises(UnknownArtistError):
        _run_soundcloud(artist_id=999_999)

    assert ADMIN_SC_USER not in fake_soundcloud.requested_users


def test_credential_store_failure_does_not_borrow_an_identity(
        db, tenant, env_points_at_test_db, fake_soundcloud):
    """A DB blip used to make the whole fleet collect the admin's data."""
    from src.utils.credential_loader import CredentialLoadError

    _connect(db, tenant, "soundcloud", {"user_id": TENANT_SC_USER})

    with patch("src.utils.credential_loader.load_platform_credentials",
               side_effect=CredentialLoadError("db down")):
        with pytest.raises(CredentialLoadError):
            _run_soundcloud(artist_id=tenant)

    assert ADMIN_SC_USER not in fake_soundcloud.requested_users


# ── YouTube: identity + row ownership ───────────────────────────────────────

def _fake_youtube_collector(channel_id, **_):
    """collect_all_data keyed on the channel actually asked for."""
    return {
        "channel_stats": {
            "channel_id": channel_id, "channel_name": f"Channel {channel_id}",
            "description": "", "subscriber_count": 10, "video_count": 1,
            "view_count": 100, "thumbnail_url": "", "country": "FR",
            "collected_at": "2026-08-20T00:00:00",
        },
        "videos": [{
            "video_id": f"vid-of-{channel_id}", "channel_id": channel_id,
            "title": f"Video of {channel_id}", "description": "",
            "published_at": "2026-01-01T00:00:00", "thumbnail_url": "",
        }],
        "video_stats": [{
            "video_id": f"vid-of-{channel_id}", "view_count": 5, "like_count": 1,
            "comment_count": 0, "favorite_count": 0,
            "collected_at": "2026-08-20T00:00:00", "duration": "PT3M", "definition": "hd",
        }],
        "comments": [],
    }


@pytest.fixture
def fake_youtube():
    # Import the module explicitly: patch() resolves the target by attribute walk,
    # and `src.collectors.youtube_collector` is only imported inside the DAG task.
    import src.collectors.youtube_collector as yt_mod

    collector = MagicMock()
    collector.collect_all_data.side_effect = lambda **kw: _fake_youtube_collector(**kw)
    with patch.object(yt_mod, "YouTubeCollector", return_value=collector):
        yield collector


def _run_youtube(artist_id=None):
    dag = _load_dag_module("youtube_daily")
    return dag.collect_youtube_data(**_dag_context(artist_id))


def test_youtube_unconnected_tenant_does_not_get_the_admin_channel(
        db, tenant, env_points_at_test_db, fake_youtube):
    _run_youtube()

    rows = db.fetch_query(
        "SELECT channel_id FROM youtube_videos WHERE artist_id = %s", (tenant,)
    )
    assert rows == [], f"unconnected tenant received the admin's videos: {rows}"


def test_youtube_row_ownership_is_not_transferable(db, tenant, env_points_at_test_db,
                                                   fake_youtube):
    """Two tenants on the same video must not steal the row from each other.

    `youtube_videos` upserted on `video_id` alone with `artist_id` in the update
    list, so the last collector to run took ownership and the previous tenant's
    row vanished from their (artist-scoped) views.
    """
    import uuid
    other_slug = f"e2e-{uuid.uuid4().hex[:10]}"
    other = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active) "
        "VALUES (%s, %s, 'free', TRUE) RETURNING id",
        (f"E2E {other_slug}", other_slug),
    )[0][0]
    try:
        shared_channel = "UCsharedchannelxxxxxx"
        _connect(db, tenant, "youtube", {"channel_id": shared_channel})
        _connect(db, other, "youtube", {"channel_id": shared_channel})

        _run_youtube(artist_id=tenant)
        _run_youtube(artist_id=other)

        first = db.fetch_query(
            "SELECT video_id FROM youtube_videos WHERE artist_id = %s", (tenant,)
        )
        second = db.fetch_query(
            "SELECT video_id FROM youtube_videos WHERE artist_id = %s", (other,)
        )
        assert first, "the first tenant lost its row to the second"
        assert second, "the second tenant has no row"
    finally:
        for table in ("youtube_video_stats", "youtube_videos", "youtube_channel_history",
                      "youtube_channels", "artist_credentials"):
            try:
                db.execute_query(f"DELETE FROM {table} WHERE artist_id = %s", (other,))
            except Exception:
                pass
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (other,))


# ── Writes must name their tenant, never inherit DEFAULT 1 ──────────────────

def test_every_write_names_its_tenant_explicitly(db, tenant, env_points_at_test_db,
                                                 fake_soundcloud):
    """No row may reach the DB relying on `artist_id INTEGER DEFAULT 1`.

    `track_popularity_history` did exactly that: the payload had no `artist_id`
    key, upsert_many derives INSERT columns from the payload keys, so Postgres
    filled in 1 — every tenant's Spotify popularity history landed on the admin,
    daily, with no error anywhere.
    """
    from src.database.postgres_handler import PostgresHandler

    seen = []
    original = PostgresHandler.upsert_many

    def recording(self, table, data, conflict_columns, update_columns):
        if data:
            seen.append((table, set(data[0].keys())))
        return original(self, table, data, conflict_columns, update_columns)

    _connect(db, tenant, "soundcloud", {"user_id": TENANT_SC_USER})
    with patch.object(PostgresHandler, "upsert_many", recording):
        _run_soundcloud(artist_id=tenant)

    tenant_scoped = {
        t for t, _ in seen
        if db.fetch_query(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = 'artist_id'", (t,))
    }
    for table, keys in seen:
        if table in tenant_scoped:
            assert "artist_id" in keys, (
                f"{table}: payload has no artist_id key — the row would fall back "
                f"to the column DEFAULT (tenant 1). Keys were {sorted(keys)}"
            )


def test_spotify_popularity_history_carries_its_tenant(db, tenant, env_points_at_test_db):
    """The live leak, asserted directly on the payload the DAG builds."""
    from src.database.postgres_handler import PostgresHandler

    # A spotify id unique to this run: two tenants claiming the same one is a
    # genuine ambiguity the DAG now refuses (and this test must not create it).
    import uuid
    spotify_id = f"e2e{uuid.uuid4().hex[:19]}"
    db.execute_query(
        "UPDATE saas_artists SET spotify_artist_id = %s WHERE id = %s",
        (spotify_id, tenant),
    )
    db.execute_query(
        "INSERT INTO artists (artist_id, name) VALUES (%s, %s) "
        "ON CONFLICT (artist_id) DO NOTHING",
        (spotify_id, "E2E artist"),
    )
    # Everything after the seed is inside the try: the DAG call used to sit OUTSIDE
    # it, so a raising DAG skipped the cleanup and left an `artists` row behind.
    # The next run then saw two artists, failed differently, and leaked again —
    # a test that poisons the next test is worse than a test that fails.
    captured = {}
    original = PostgresHandler.upsert_many

    def recording(self, table, data, conflict_columns, update_columns):
        if table == "track_popularity_history" and data:
            captured["keys"] = set(data[0].keys())
            captured["artist_ids"] = {r.get("artist_id") for r in data}
        return original(self, table, data, conflict_columns, update_columns)

    # `artist_id` (the SPOTIFY id, VARCHAR) belongs in the payload: `tracks` is a
    # catalogue keyed by it. Omitting it made the fixture pass only because the
    # column happened to be nullable.
    fake_tracks = [{
        "track_id": "trk-e2e-1", "artist_id": spotify_id, "track_name": "E2E",
        "popularity": 42, "duration_ms": 1000, "album_name": "A",
        "release_date": "2026-01-01", "collected_at": "2026-08-20T00:00:00",
    }]
    try:
        import src.collectors.spotify_api as sp_mod
        with patch.object(sp_mod, "SpotifyCollector") as sp:
            sp.return_value.get_artist_top_tracks.return_value = fake_tracks
            with patch.object(PostgresHandler, "upsert_many", recording):
                dag = _load_dag_module("spotify_api_daily")
                # SCOPED to this tenant, like the dashboard triggers it
                # (`conf={'artist_id': …}`). Called without it the DAG runs in
                # FLEET mode over every active tenant, and the stubbed collector
                # returns the same track for each — so the injected row landed
                # under the admin too and the assertion below failed on a correct
                # behaviour. The bug it guards against is per-tenant; the call
                # has to be per-tenant to see it.
                dag.collect_spotify_top_tracks(**_dag_context(tenant))

        assert captured, "the popularity upsert never ran — fixture did not reach it"
        assert "artist_id" in captured["keys"], (
            "track_popularity_history payload has no artist_id key → DEFAULT 1 → "
            "every tenant's history is stored under the admin"
        )
        # NOT `== {tenant}`: the DAG is called without an artist_id, so it runs in
        # FLEET mode and legitimately builds one payload covering every active
        # tenant. That assertion only held on an empty database — it failed on the
        # real dev DB (`{1, 203}`) for a correct behaviour, which is a guard that
        # cries wolf the moment the fleet has a second member.
        #
        # What the leak actually looks like: the row lands under artist 1 because
        # the payload had no `artist_id` key and the column defaulted. So assert on
        # the ROW we injected — independent of how many tenants exist.
        assert captured["artist_ids"] == {tenant}, (
            f"a scoped run built a payload for {captured['artist_ids']} instead of "
            f"{{{tenant}}} — the conf artist_id is not scoping the collection"
        )
        landed = db.fetch_query(
            "SELECT artist_id FROM track_popularity_history WHERE track_id = %s",
            ("trk-e2e-1",),
        )
        assert landed, "the injected track never reached track_popularity_history"
        owners = {r[0] for r in landed}
        assert owners == {tenant}, (
            f"the track collected FOR tenant {tenant} is filed under {owners}. "
            "This is the leak: every tenant's popularity history under the admin."
        )
    finally:
        db.execute_query("DELETE FROM track_popularity_history WHERE track_id = %s",
                         ("trk-e2e-1",))
        db.execute_query("DELETE FROM tracks WHERE track_id = %s", ("trk-e2e-1",))
        db.execute_query("DELETE FROM artists WHERE artist_id = %s", (spotify_id,))
