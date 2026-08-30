"""An artist-facing string must not name our infrastructure, nor an admin-only page.

Type: Test
Uses: ast, the i18n catalogs, app.py (_ADMIN_ONLY)
Depends on: src/dashboard/utils/i18n_catalog/, src/dashboard/app.py
Persists in: nothing

The class, named from four sightings in one test session
-------------------------------------------------------
`DAG`, `Airflow`, a dag_id: these are names for OUR machinery. An artist has no model
for them, so a sentence containing one is either noise or — worse — read as a claim
about their own data:

  * "DAG spotify_api_daily — 🟢 success" on the Credentials tab: a brand-new artist
    read it as proof their collection had run. It was the fleet's, i.e. the admin's.
  * "✅ Spotify" then "Lancé !" after pressing collect: that reports the TRIGGER, not
    the collection. "Launched" and "you have data" are different claims, and the
    second is the one being asked.
  * "Credentials saved but DAG trigger failed" — the English string had drifted from
    a French one that says it properly ("la première collecte n'a pas pu démarrer").
  * "Échec non reconnu — voir 📊 Airflow KPI pour le détail" — sent the artist to a
    page listed in `_ADMIN_ONLY`, which they cannot open. A dead end, not help.

The rule this holds
-------------------
A string in a catalog that serves a non-admin page must not contain infrastructure
vocabulary, and must not point at an admin-only page by name.

Admin surfaces are exempt by module (their catalog is named after an admin-only page).
Strings that are genuinely admin-gated inside a SHARED module are listed explicitly in
`_ADMIN_GATED_KEYS`, each with the gate that proves it — an allowlist that has to be
argued for, rather than a rule that quietly stops applying.
"""
from __future__ import annotations

import importlib
import pkgutil
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "src/dashboard/app.py"

# Words that name our machinery rather than the artist's world.
_PLUMBING = re.compile(r"\b(DAG|DAGs|Airflow|dag_id|XCom|scheduler|Postgres|PostgreSQL)\b")

# Keys living in a SHARED catalog but rendered only to admins. Each needs its gate.
_ADMIN_GATED_KEYS = {
    # views/credentials/_render.py::_render_platform_tab — `if … and is_admin()`
    "credentials.dag_badge",
    "credentials.dag_state_never",
    # views/credentials/router.py — `if is_admin(): … _fetch_dag_last_states()`
    "credentials.fetching_dag_status",
    # app.py::_check_db_health — the operator's own "Docker is down" banner; an
    # artist never sees a reachable app in that state.
    "app.db_health_error",
    # views/home.py::_section_dag_status — `if not is_admin(): return`
    "home.airflow_unreachable",
    "home.no_dags",
    # views/meta_creatives.py — `if is_admin():`, the full-history manoeuvre
    "meta_creatives.uncollected_admin",
}


def _admin_only_pages() -> set[str]:
    body = _APP.read_text(encoding="utf-8")
    m = re.search(r"_ADMIN_ONLY\s*=\s*\{(.*?)\}", body, re.S)
    assert m, "app.py no longer defines _ADMIN_ONLY"
    return set(re.findall(r"'([^']+)'", m.group(1)))


def _artist_facing_catalogs() -> dict[str, dict[str, str]]:
    """{module: {key: english string}} for every catalog serving a non-admin page."""
    import src.dashboard.utils.i18n_catalog as pkg

    admin = _admin_only_pages()
    out: dict[str, dict[str, str]] = {}
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name in admin:
            continue
        m = importlib.import_module(f"{pkg.__name__}.{mod.name}")
        table = getattr(m, "EN", None) or getattr(m, "TRANSLATIONS", None)
        if isinstance(table, dict):
            out[mod.name] = {k: v for k, v in table.items() if isinstance(v, str)}
    return out


def test_no_artist_string_names_our_infrastructure():
    offenders: list[str] = []
    for module, table in _artist_facing_catalogs().items():
        for key, text in table.items():
            if key in _ADMIN_GATED_KEYS:
                continue
            hit = _PLUMBING.search(text)
            if hit:
                offenders.append(f"{module}: {key} says {hit.group(0)!r} — {text[:70]!r}")

    assert not offenders, (
        "an artist-facing string names our machinery:\n  " + "\n  ".join(offenders)
        + "\n\nSay what happened in the artist's terms — the platform and the outcome — "
          "not the component that produced it. 'Launched' is not 'you have data'.\n"
          "If the string really is admin-only, add its key to _ADMIN_GATED_KEYS with "
          "the gate that proves it."
    )


def test_no_artist_string_points_at_a_page_the_artist_cannot_open():
    """Naming an admin-only page in artist-facing help is a dead end."""
    admin = _admin_only_pages()
    # The human-readable names of admin-only pages, as they appear in nav labels.
    names = {"Airflow KPI", "ETL Logs", "DB Health", "ML Performance"}
    offenders: list[str] = []

    for module, table in _artist_facing_catalogs().items():
        for key, text in table.items():
            if key in _ADMIN_GATED_KEYS:
                continue
            for name in names:
                if name.lower() in text.lower():
                    offenders.append(f"{module}: {key} sends the reader to {name!r}")

    assert not offenders, (
        "artist-facing help points at an admin-only page:\n  " + "\n  ".join(offenders)
        + f"\n\nThose pages are gated by _ADMIN_ONLY ({sorted(admin)[:4]}…): the artist "
          "reading this cannot open them. Give them an action they can actually take."
    )
