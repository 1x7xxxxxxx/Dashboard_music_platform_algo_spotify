"""Render-smoke tests for every dashboard view.

Type: Test
Uses: streamlit.testing.v1.AppTest, live Postgres (spotify_etl)
Depends on: src/dashboard/views/*.show(), a reachable DB on localhost:5433
Persists in: —

Each view's `show()` is executed inside a Streamlit `AppTest` script context with a
minimal admin session. The single assertion is "no uncaught exception" — this catches
import-scope regressions (e.g. a `NameError` from a mis-scoped lazy `import plotly`),
broken `@st.fragment` refactors, and SQL/identifier typos that only fire at render time.
The committed suite previously had ZERO view-render coverage, so any such regression
shipped silently (see DEVLOG WAVE 3 "failed-Edit dead code passed tests+ruff").

The whole module is SKIPPED when Postgres is unreachable (CI has no live DB on 5433),
so it adds value locally without breaking CI. Views render against real data as admin
(role='admin' → premium plan, no tenant filter), exercising the real query paths.
"""
import os
import socket

import pytest

# ── DB readiness gate ────────────────────────────────────────────────────────
# Views open a real connection via get_db_connection() and query real tables, so
# skip the whole module unless a *provisioned* Postgres is up. A TCP check alone is
# insufficient: CI starts an EMPTY `postgres:17` service on 5433 (schema never
# migrated), so the socket connects but every view fails with 'relation … does not
# exist'. Gate on a core table's presence so the suite runs locally (real populated
# DB) and skips cleanly against an unprovisioned CI DB.
_DB_HOST, _DB_PORT = "127.0.0.1", 5433


# La porte LÉGÈRE. Le corps recopié ici importait `get_db_connection`
# (**5,30 s**, dont 5,19 s de Streamlit) et ouvrait une connexion À L'IMPORT du
# module, donc à la collecte, une fois par fichier et par worker.
# `tests.db_gate.db_ready` répond en 0,19 s, derrière un `lru_cache` partagé, et
# sonde en plus `DATABASE_URL` et le schéma réel. Le nom est conservé : seuls le
# coût et le nombre de connexions changent.
from tests.db_gate import db_ready as _db_ready  # noqa: E402


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason=f"No provisioned Postgres on {_DB_HOST}:{_DB_PORT} "
           "(socket down or schema not migrated) — render-smoke needs the live DB",
)

# Every view wired into app.py's dispatch (src/dashboard/app.py). Keep in sync when
# adding a view (the same step that adds it to _NAV_SECTIONS).
# Source UNIQUE — `tests/render_harness.py`. Ces constantes vivaient en double
# dans les deux fichiers de rendu et ont divergé NEUF JOURS (voir le module).
from tests.render_harness import TENANT_SCRIPT as _TENANT_SCRIPT_SRC  # noqa: E402
from tests.render_harness import EMPTY_TENANT_VIEWS as _TENANT_VIEWS  # noqa: E402
from tests.render_harness import VIEWS  # noqa: E402
from tests.render_harness import render_once  # noqa: E402

# Même rendu que `test_a_render_opens_one_connection.py`, payé une fois — voir
# le module. `xdist_group` est ce qui rend le partage effectif sous `-n`.
_VUES = [pytest.param(v, marks=pytest.mark.xdist_group(v)) for v in VIEWS]

# AppTest re-execs a script string in a fresh interpreter path, so the script must
# re-inject the repo root and seed an admin session before importing the view.


@pytest.mark.parametrize("view", _VUES)
def test_view_renders_without_exception(view):
    erreur = render_once(view).erreur
    if erreur:
        pytest.fail(f"{view}.show() raised {erreur}")

# ── The new-artist case: non-admin, own tenant, no data yet ─────────────────
# Everything above renders as ADMIN on artist 1 — a tenant with years of data and
# no tenant filter. That configuration cannot fail the way a fresh account does:
# empty dataframes, no credentials row, no collection yet. Both beta testers were
# in exactly this state, and no test ever rendered it.

_TENANT_SCRIPT = _TENANT_SCRIPT_SRC

# Views an artist can actually reach (admin-only pages excluded), kept small
# enough to stay fast while covering every data-shape an empty tenant produces.
# `upload_csv` a quitté LES DEUX listes le 2026-09-06, et la raison est le défaut
# lui-même : sa `show()` n'était importée par aucune route — `?page=upload_csv`
# rend `views.credentials` depuis la fusion du 2026-09-04. Ce fichier l'appelait
# directement, donc elle rendait vert dans une liste intitulée « ce qu'un artiste
# peut atteindre » alors qu'aucun artiste ne pouvait l'atteindre. Le composant de
# dépôt reste couvert : `credentials` est dans les deux listes et rend son onglet.
# `process_guide` a quitté LES DEUX listes le 2026-09-06 avec la vue elle-même :
# « 📋 Guide de démarrage » redisait ce que l'assistant montre et ce que la matrice
# mesure. Ses deux sections uniques — PDF des identifiants, définition des CSV —
# vivent dans `onboarding_health`, qui est dans les deux listes et les rend donc.
# La ROUTE `?page=process_guide` survit et mène là-bas ; c'est `app.py` qui la
# porte, pas une vue, donc rien à rendre ici.


@pytest.fixture(scope="module")
def empty_tenant():
    """A tenant with no credentials and no rows — the state on day one."""
    import uuid

    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    slug = f"smoke-{uuid.uuid4().hex[:10]}"
    artist_id = db.fetch_query(
        # `is_sandbox` — 2026-09-20 (R140 §16.9d). Sans lui, un locataire fabriqué par
        # un test entre dans le compteur PUBLIC de `live_pulse.py`. Mesuré ce jour-là :
        # il annonçait 10 artistes, dont 9 artefacts. Cette fixture nettoie normalement
        # derrière elle, mais une exécution morte en route laisse sa ligne — et le
        # nettoyage ne peut pas être la seule défense.
        "INSERT INTO saas_artists (name, slug, tier, active, is_sandbox) "
        "VALUES (%s, %s, 'free', TRUE, TRUE) RETURNING id", (f"Smoke {slug}", slug),
    )[0][0]
    db.close()
    yield artist_id
    db = get_db_connection()
    db.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s", (artist_id,))
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
    db.close()


@pytest.mark.parametrize("view", _TENANT_VIEWS)
def test_view_renders_for_a_brand_new_artist(view, empty_tenant):

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(
        _TENANT_SCRIPT.format(root=os.getcwd(), view=view, artist_id=empty_tenant))
    at.run(timeout=90)

    if at.exception:
        ex = at.exception[0]
        detail = getattr(ex, "value", ex)
        pytest.fail(
            f"{view}.show() raised {type(detail).__name__} for a new artist "
            f"(empty tenant, non-admin): {detail}"
        )
