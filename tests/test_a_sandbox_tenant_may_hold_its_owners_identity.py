"""A sandbox tenant is exempt from the identity guard — in both directions.

Type: Test
Uses: live Postgres (spotify_etl), find_identity_conflict
Depends on: migration 080 (saas_artists.is_sandbox)
Persists in: nothing — every row it writes is removed in teardown

Why the exemption exists
------------------------
To check that your own platform credentials work you must walk the onboarding from
zero and type them in. But a platform identity belongs to exactly one tenant, and
yours already belongs to your real account, so the guard refuses — correctly. That
guard is what closed the tenant leak two beta sessions were spent on; turning it off
"temporarily" is not an option, and a duplicate claim, once written, is invisible.

Migration 080 adds a third kind of tenant instead. This file pins the two halves of
its exemption, because only having one is worse than having neither:

  * a sandbox is never blocked — the point of the thing;
  * a sandbox never blocks a real tenant — otherwise a rehearsal left lying around
    would refuse a real artist their own identifier.

The canary is deliberately NOT exempt: it uses public artist ids, where a collision is
a real defect rather than an intended rehearsal.
"""
from __future__ import annotations

import os
import socket
import uuid

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _db_ready() -> bool:
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
                pass
        except OSError:
            return False
    try:
        from src.database.postgres_handler import PostgresHandler
        db = PostgresHandler.from_env_or_config()
        try:
            db.fetch_query("SELECT is_sandbox FROM saas_artists LIMIT 1")
            return True
        finally:
            db.close()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason="needs a provisioned Postgres carrying migration 080")


@pytest.fixture()
def tenants():
    """A sandbox and a real tenant, both removed afterwards whatever happens."""
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    tag = uuid.uuid4().hex[:10]
    made: list[int] = []
    try:
        for slug, sandbox in ((f"sbx-{tag}", True), (f"real-{tag}", False)):
            made.append(db.fetch_query(
                "INSERT INTO saas_artists (name, slug, tier, active, is_sandbox) "
                "VALUES (%s, %s, 'free', TRUE, %s) RETURNING id",
                (slug, slug, sandbox))[0][0])
        yield db, made[0], made[1], f"ID{tag.upper()}"
    finally:
        for aid in made:
            # Les credentials d'abord : une ligne laissée derrière rendrait le
            # locataire suivant introuvable en cascade, et c'est exactement ce
            # qu'une répétition oubliée a produit le 2026-09-04 (voir le dernier
            # test de ce fichier).
            db.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s",
                             (aid,))
            db.execute_query("DELETE FROM saas_artists WHERE id = %s", (aid,))
        db.close()


def test_a_sandbox_may_claim_an_identity_a_real_tenant_holds(tenants):
    from src.dashboard.views.credentials._core import find_identity_conflict

    db, sandbox_id, real_id, value = tenants
    db.execute_query("UPDATE saas_artists SET spotify_artist_id = %s WHERE id = %s",
                     (value, real_id))

    assert find_identity_conflict(
        db, sandbox_id, "spotify", {"spotify_artist_id": value}) is None, (
        "the sandbox was refused an identity its own operator already holds. That is "
        "the exact situation migration 080 exists for: rehearsing the onboarding with "
        "real credentials, from an account that starts empty."
    )


def test_a_real_tenant_is_still_refused(tenants):
    """The exemption must not have widened into 'nobody is ever blocked'."""
    from src.dashboard.views.credentials._core import find_identity_conflict

    db, _sandbox_id, real_id, value = tenants
    db.execute_query("UPDATE saas_artists SET spotify_artist_id = %s WHERE id = %s",
                     (value, real_id))

    conflict = find_identity_conflict(
        db, real_id + 10_000_000, "spotify", {"spotify_artist_id": value})
    assert conflict is not None, (
        "a real tenant was allowed to claim an identity another real tenant holds. "
        "Two dashboards would then collect the same source and nobody could say whose "
        "numbers they are — the defect the guard was written for."
    )
    assert conflict[2] == real_id


def test_a_sandbox_never_blocks_a_real_tenant(tenants):
    """The half that is easy to forget, and worse than not having the feature."""
    from src.dashboard.views.credentials._core import find_identity_conflict

    db, sandbox_id, _real_id, value = tenants
    db.execute_query("UPDATE saas_artists SET spotify_artist_id = %s WHERE id = %s",
                     (value, sandbox_id))

    assert find_identity_conflict(
        db, sandbox_id + 10_000_000, "spotify", {"spotify_artist_id": value}) is None, (
        "a real artist was refused their own identifier because a SANDBOX held it. "
        "A rehearsal left lying around must never cost a customer their account."
    )


def test_a_canary_keeps_the_guard(tenants):
    """The exemption is granted by is_sandbox alone — never by is_canary."""
    from src.dashboard.views.credentials._core import find_identity_conflict

    db, sandbox_id, real_id, value = tenants
    db.execute_query("UPDATE saas_artists SET is_sandbox = FALSE, is_canary = TRUE "
                     "WHERE id = %s", (sandbox_id,))
    db.execute_query("UPDATE saas_artists SET spotify_artist_id = %s WHERE id = %s",
                     (value, real_id))

    assert find_identity_conflict(
        db, sandbox_id, "spotify", {"spotify_artist_id": value}) is not None, (
        "a canary was granted the sandbox exemption. The canary collects PUBLIC "
        "artists; a collision there is an accident to be reported, not a rehearsal, "
        "and widening a dangerous permission to a tenant that never asked for it is "
        "how a guard stops meaning anything."
    )


def test_a_sandbox_row_does_not_hide_a_conflict_between_two_real_tenants(tenants):
    """La troisième moitié, celle que personne n'avait vue.

    Les deux exemptions déjà épinglées plus haut portent sur QUI est bloqué. Celle-ci
    porte sur ce que le bac à sable rend INVISIBLE, et c'est un défaut trouvé en
    production locale le 2026-09-04, en rejouant simplement l'onboarding : la ligne
    laissée par la répétition a fait passer au rouge, au run suivant,
    `test_spotify_conflict_is_seen_through_saas_artists`.

    Le mécanisme tenait à l'ORDRE de deux opérations justes. L'identité Spotify est
    cherchée dans `artist_credentials`, puis — **seulement si rien n'est trouvé** —
    dans son miroir `saas_artists`, que le collecteur lit vraiment. Le filtre bac à
    sable, lui, s'appliquait APRÈS. Une ligne de bac à sable suffisait donc à rendre
    la première recherche non vide, le miroir n'était jamais consulté, et le filtre
    vidait ensuite le résultat : « aucun conflit », alors que deux VRAIS locataires
    se disputaient l'identifiant.

    Ce n'est pas un cas de laboratoire : le bac à sable existe pour rejouer
    l'onboarding avec les identifiants de l'exploitant, donc il détient par
    construction ceux que son locataire réel détient aussi. Il masquait exactement
    les collisions les plus probables.
    """
    import json

    from src.dashboard.views.credentials._core import find_identity_conflict

    db, sandbox_id, real_id, value = tenants

    # Le bac à sable détient l'identifiant dans artist_credentials — l'état que
    # `make artist-sandbox` + une saisie laissent derrière eux.
    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, 'spotify', %s::jsonb)",
        (sandbox_id, json.dumps({"spotify_artist_id": value})))
    # Un VRAI locataire le détient dans le miroir, celui que spotify_api_daily lit.
    db.execute_query("UPDATE saas_artists SET spotify_artist_id = %s WHERE id = %s",
                     (value, real_id))

    conflict = find_identity_conflict(
        db, real_id + 10_000_000, "spotify", {"spotify_artist_id": value})

    assert conflict is not None, (
        "a sandbox row hid a conflict between two REAL tenants: the guard looked in "
        "artist_credentials, found the sandbox, therefore never looked at the "
        "saas_artists mirror, then filtered the sandbox out and answered « no "
        "conflict ». Two dashboards would collect the same artist and nobody could "
        "say whose numbers they are."
    )
    assert conflict[2] == real_id, (
        f"the conflict is reported against {conflict[2]} instead of the real tenant "
        f"{real_id} — the sandbox must never be named as the holder."
    )


def test_the_collector_does_not_call_a_sandbox_share_an_ambiguous_owner():
    """L'exemption vaut aussi POUR LE COLLECTEUR, pas seulement pour la saisie.

    Défaut de prod du 2026-09-04, arrivé par une alerte e-mail :

        ⚠️ Spotify id 7sbf… is claimed by 2 tenants ([1, 18]) — skipping,
        ownership is ambiguous.
        ❌ ValueError: Spotify API collected 0 tracks from 1 artist(s)

    Le locataire 18 est le bac à sable, et il porte l'identifiant de l'exploitant
    **par construction** — c'est exactement ce que la migration 080 autorise et ce
    que `find_identity_conflict` exempte trois fonctions plus haut. `spotify_api_daily`
    lisait ce même partage comme une propriété ambiguë, sautait la ligne, comptait
    zéro titre et faisait échouer la tâche. Deux gardes écrits séparément se
    contredisaient : l'un autorise le partage, l'autre le refuse — et la répétition
    d'onboarding réveillait l'admin à chaque fois.

    Le test lit le SQL du DAG plutôt que d'exécuter Airflow : ce qui doit rester vrai,
    c'est que la requête d'ambiguïté écarte les bacs à sable, et qu'un run scopé n'a
    même pas à la poser.
    """
    import ast
    from pathlib import Path as _Path

    dag = (_Path(__file__).resolve().parents[1] / "airflow" / "dags"
           / "spotify_api_daily.py")
    src = dag.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef)
              and f.name == "collect_spotify_top_tracks")
    body = ast.get_source_segment(src, fn) or ""

    claim_queries = [n for n in ast.walk(fn)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)
                     and "spotify_artist_id = %s" in n.value
                     and "FROM saas_artists" in n.value]
    assert claim_queries, "la requête de propriété a disparu du DAG"
    assert any("is_sandbox" in q.value for q in claim_queries), (
        "la requête qui décide « cet id est-il revendiqué par plusieurs locataires ? » "
        "ne filtre pas les bacs à sable. Un bac à sable porte l'identifiant de "
        "l'exploitant par construction (migration 080) : sans ce filtre, sa seule "
        "existence rend la collecte de l'artiste réel « ambiguë » et fait échouer "
        "la tâche chaque nuit."
    )
    assert "if artist_id_conf:" in body, (
        "un run scopé sur un locataire ne tranche plus la propriété par lui-même — "
        "il n'y a pourtant rien à deviner quand l'appelant a nommé le locataire"
    )
