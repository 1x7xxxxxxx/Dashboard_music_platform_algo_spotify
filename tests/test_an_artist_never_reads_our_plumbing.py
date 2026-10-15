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

import ast
import importlib
import pkgutil
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "src/dashboard/app.py"

# Words that name our machinery rather than the artist's world.
# ⚠️ ÉLARGI le 2026-09-17, et le trou était exactement celui de `pkill`/`pgrep` :
# le motif nommait les MOTS de la plomberie et pas ses NOMS. Mesuré ce jour-là, deux
# messages face à l'artiste disaient « (lancez `ml_scoring_daily`) » — sans le mot
# « DAG » — et ce garde était VERT dessus :
#   · `views/trigger_algo/_tab_budget_roi.py`, une vue PREMIUM, pas admin ;
#   · `pdf_exporter/_renderers.py::_render_score20`, dans un document que l'artiste
#     REÇOIT.
# Un nom de DAG EST de la plomberie : l'artiste ne peut lancer aucun d'entre eux, et
# le lui demander est une impasse. La liste se dérive de `airflow/dags/`, donc elle ne
# peut pas se périmer quand un DAG est ajouté ou renommé.
_DAG_NAMES = sorted(
    p.stem for p in (Path(__file__).resolve().parents[1] / "airflow" / "dags").glob("*.py")
    if not p.stem.startswith("_")
)
_PLUMBING = re.compile(
    r"\b(DAG|DAGs|Airflow|dag_id|XCom|scheduler|Postgres|PostgreSQL"
    # R622 — the operator's nouns, measured on 2026-10-15 in messages an artist reads:
    # « vérifiez la config SMTP dans config/config.yaml », « Erreur SQL », « Docker est
    # lancé », « FERNET_KEY ». `table` is NOT here: « table des morceaux » is the artist's.
    r"|Docker|docker-compose|SMTP|config\.yaml|FERNET_KEY|fernet_key|SQL|psycopg2?"
    r"|requirements\.txt"
    + ("|" + "|".join(re.escape(n) for n in _DAG_NAMES) if _DAG_NAMES else "")
    + r")\b")


def test_the_dag_names_are_actually_derived() -> None:
    """Anti-vacuité : une liste vide rendrait l'élargissement sans effet, en silence."""
    assert len(_DAG_NAMES) >= 10, (
        f"seulement {len(_DAG_NAMES)} noms de DAG dérivés de `airflow/dags/` — "
        "l'élargissement de 2026-09-17 ne garde plus rien")
    assert "ml_scoring_daily" in _DAG_NAMES, (
        "`ml_scoring_daily` a disparu de la liste dérivée ; c'est le DAG des DEUX "
        "sites trouvés le 2026-09-17")

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
    # views/meta_creatives.py — `if is_admin():`, the full-history manoeuvre
    "meta_creatives.uncollected_admin",
    # views/credentials/router.py — `if _fernet_state != 'ok' and not is_admin():`
    # shows `credentials.save_unavailable` first; these two are the operator's (R622).
    "credentials.fernet_malformed",
    "credentials.fernet_missing",
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


# ── R622 — the French defaults and the literals, read in the CODE ─────────────────────
# The catalogs above are the ENGLISH half. The French text lives inline, as the
# `default` of `t()`/`_t()` or as a bare literal in `st.error(…)`, and an inline string
# was never in a catalog this guard read: « Vérifiez que Docker est lancé » and
# « table des prédictions » were French-only, and green here until 2026-10-15.

_DASH = _ROOT / "src" / "dashboard"
_ST_DISPLAYS = frozenset({"error", "warning", "info", "exception", "toast", "success"})
_EXC_BASELINE = Path(__file__).with_name("exception_display_baseline.json")


def _admin_modules() -> set[str]:
    """Admin-only pages, plus the `views/` modules ONLY an admin page imports."""
    admin = _admin_only_pages()
    importers: dict[str, set[str]] = {}
    for f in (_DASH / "views").glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module.rsplit(".", 1)[-1]
                names = [mod] + [a.name for a in node.names]
                for n in names:
                    importers.setdefault(n, set()).add(f.stem)
    subs = {m for m, who in importers.items()
            if who and who <= admin and (_DASH / "views" / f"{m}.py").exists()}
    return admin | subs


def _artist_facing_files() -> list[Path]:
    admin = _admin_modules()
    out = []
    for f in sorted(_DASH.rglob("*.py")):
        parts = f.relative_to(_DASH).parts
        if "i18n_catalog" in parts:
            continue
        if parts[0] == "views" and parts[1].removesuffix(".py") in admin:
            continue
        out.append(f)
    return out


def _is_st_display(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in _ST_DISPLAYS and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "st")


def _is_t_call(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in {"t", "_t"} and node.args
            and isinstance(node.args[0], ast.Constant))


def _plumbing_in_source(source: str) -> list[tuple[int, str]]:
    """(line, word) for each infrastructure word an artist would read in this module."""
    hits: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if _is_t_call(node):
            if node.args[0].value in _ADMIN_GATED_KEYS:
                continue
            texts = [a for a in node.args[1:] + [k.value for k in node.keywords]
                     if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        elif _is_st_display(node):
            gated = any(_is_t_call(n) and n.args[0].value in _ADMIN_GATED_KEYS
                        for n in ast.walk(node))
            texts = [] if gated else [n for n in ast.walk(node) if isinstance(n, ast.Constant)
                                      and isinstance(n.value, str)
                                      and not any(_is_t_call(c) and n is c.args[0]
                                                  for c in ast.walk(node))]
        else:
            continue
        for c in texts:
            m = _PLUMBING.search(c.value)
            if m:
                hits.append((c.lineno, m.group(0)))
    return sorted(set(hits))


def test_no_french_default_or_literal_names_our_infrastructure() -> None:
    offenders = [f"{f.relative_to(_ROOT)}:{line} says {word!r}"
                 for f in _artist_facing_files()
                 for line, word in _plumbing_in_source(f.read_text(encoding="utf-8"))]
    assert not offenders, (
        "an artist-facing French default or literal names our machinery:\n  "
        + "\n  ".join(offenders)
        + "\n\nSame rule as the catalogs: the outcome in the artist's terms. If the "
          "string is admin-gated, its key goes in _ADMIN_GATED_KEYS with the gate.")


def test_the_source_detector_sees_a_default_and_skips_a_gated_key() -> None:
    assert _plumbing_in_source('st.error(t("x.y", "Vérifiez Docker"))\n') == [(1, "Docker")]
    assert _plumbing_in_source('msg = t("x.y", "le DAG")\n') == [(1, "DAG")]
    assert _plumbing_in_source('st.error(t("app.db_health_error", "Docker"))\n') == []
    assert _plumbing_in_source('st.error(t("ui.SQL_key", "Réessaie"))\n') == []


# ── R622 — an exception's own text shown to an artist: a shrink-only ratchet ───────────
# `st.error(f"… {e}")` prints whatever the driver says — a SQL fragment, a hostname, a
# column name. 33 such displays were measured on 2026-10-15 in non-admin modules; the one
# that printed SQL (`soundcloud.py`, « Erreur SQL (KPIs) : {err} ») was fixed first.
# The baseline is keyed `file::function`, not by line, so an unrelated edit never moves it.

def _exception_displays(source: str, rel: str) -> set[str]:
    """`file::function` (innermost) for each handler that displays its own exception."""
    found: set[str] = set()

    def visit(node: ast.AST, owner: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            if isinstance(child, ast.ExceptHandler) and child.name and any(
                    _is_st_display(c) and any(isinstance(n, ast.Name) and n.id == child.name
                                              for n in ast.walk(c))
                    for c in ast.walk(child)):
                found.add(f"{rel}::{owner}")
            visit(child, owner)

    visit(ast.parse(source), "<module>")
    return found


def test_exception_displays_only_shrink() -> None:
    import json

    now = set()
    for f in _artist_facing_files():
        now |= _exception_displays(f.read_text(encoding="utf-8"),
                                   f.relative_to(_ROOT).as_posix())
    baseline = set(json.loads(_EXC_BASELINE.read_text(encoding="utf-8")))
    assert not now - baseline, (
        "a NEW place shows an exception's own text to an artist:\n  "
        + "\n  ".join(sorted(now - baseline))
        + "\n\nLog it (`logger.exception`) and show the outcome in the artist's terms.")
    assert not baseline - now, (
        "fixed — remove from tests/exception_display_baseline.json so it cannot return:\n  "
        + "\n  ".join(sorted(baseline - now)))


def test_the_exception_detector_sees_the_handler_name_only() -> None:
    src = ("def f():\n    try:\n        x()\n    except Exception as e:\n"
           "        st.error(f'oops {e}')\n"
           "def g():\n    try:\n        x()\n    except Exception as e:\n"
           "        st.error('oops')\n")
    assert _exception_displays(src, "m.py") == {"m.py::f"}
