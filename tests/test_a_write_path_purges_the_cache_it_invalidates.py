"""A dashboard write to a cached table purges the cache that serves it.

Type: Test
Uses: ast
Depends on: src/dashboard/**/*.py, src/dashboard/utils/kpi_helpers.py
Persists in: nothing

Why this exists
---------------
`kpi_helpers` keeps its reads for 600 s. That long TTL is only safe because the
gestures that change data mid-day purge explicitly — the module says so itself:
*« on ne fait pas confiance à l'horloge, on écoute l'événement »*, with
`clear_kpi_caches()` wired at `collection_trigger.py:46` and
`credentials/_render.py:1135`.

Three write paths were never wired, found 2026-09-11:

  * `views/upload_csv.py` — a CSV re-import. The only purge it could reach is
    `autostart_if_journey_complete`, which does nothing once a tenant's first
    collection has been recorded: i.e. on every subsequent re-upload, which is
    the ordinary case for an installed tenant. The artist re-uploads, the screen
    says "✅ Importé", and their figures do not move for ten minutes.
  * `views/admin.py` — the same import done on a tenant's behalf. Streamlit's
    cache is global to the process, so the admin-side purge is the only one that
    can reach the artist's entry.
  * `views/imusician.py` — manual monthly revenue, both the upsert and the
    delete. The purge lives inside the two helpers rather than at their call
    sites, so a third caller inherits it instead of having to remember.

Why AST, and why it asks about WRITES
-------------------------------------
A text search for the table name matches every reader too: run textually, this
same question reported eleven files, of which two actually wrote. The structural
question — "does this module call `upsert_many` on a table `kpi_helpers` caches"
— reports exactly the modules that can make the cache wrong.

A dynamic table argument (`upsert_many(cfg['table'], …)`) counts as a hit: a
static reader cannot prove it never names a cached table, and the honest default
for "cannot prove safe" is to require the purge.

Mutation record — 2026-09-11: with the purge removed from `upload_csv.py`, this
guard names that file and fails; with all three wired, it passes.
"""
from __future__ import annotations

import ast
import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_DASHBOARD = _ROOT / "src" / "dashboard"
_KPI = _DASHBOARD / "utils" / "kpi_helpers.py"
# Les DEUX formes acceptées, et rien d'autre. `purge_after_write()` est le point
# d'entrée unique (`utils/cache_invalidation`), né le 2026-09-11 quand la même
# explication s'est retrouvée recopiée dans trois vues ; `clear_kpi_caches()`
# reste la forme des deux sites historiques, qui purgent sur un déclenchement de
# collecte et non sur une écriture.
_PURGES = ("purge_after_write", "clear_kpi_caches")
_PURGE = _PURGES[0]


def _cached_tables() -> set[str]:
    """The tables `kpi_helpers` reads behind `@st.cache_data`."""
    text = _KPI.read_text(encoding="utf-8")
    return (set(re.findall(r'"table"\s*:\s*"(\w+)"', text))
            | set(re.findall(r"'table'\s*:\s*'(\w+)'", text)))


def _calls_purge(path: pathlib.Path) -> bool:
    """Does this module CALL `clear_kpi_caches()` — not merely mention it?

    The first version asked `"clear_kpi_caches" in text`, and the mutation that
    was supposed to prove it caught the defect passed instead: the name survived
    in the comment explaining the fix. That is this repository's most repeated
    guard failure, and this is another instance of it, written the same hour the
    lesson was being quoted. An AST call node cannot be satisfied by prose.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return False
    return any(
        isinstance(n, ast.Call)
        and (getattr(n.func, "id", "") in _PURGES or getattr(n.func, "attr", "") in _PURGES)
        for n in ast.walk(tree)
    )


def _tables_written(path: pathlib.Path) -> set[str]:
    """Tables this module passes to `upsert_many`; `<dynamic>` when unresolvable."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "attr", "") == "upsert_many"):
            continue
        kwargs = {k.arg: k.value for k in node.keywords}
        table = kwargs.get("table") or (node.args[0] if node.args else None)
        out.add(table.value if isinstance(table, ast.Constant) else "<dynamic>")
    return out


def test_every_dashboard_writer_of_a_cached_table_purges_it() -> None:
    cached = _cached_tables()
    assert cached, "kpi_helpers declares no cached table — the reader is broken"

    offenders = []
    for path in sorted(_DASHBOARD.rglob("*.py")):
        written = _tables_written(path)
        relevant = (written & cached) | ({"<dynamic>"} & written)
        if not relevant:
            continue
        if _calls_purge(path):
            continue
        offenders.append(
            f"{path.relative_to(_ROOT)} writes {', '.join(sorted(relevant))} but never "
            f"calls {_PURGE}()"
        )

    assert not offenders, (
        "A write that does not purge leaves the tenant looking at the old number for\n"
        "up to 600 s, with nothing on screen to explain it. The TTL is only safe\n"
        "because the events that change data purge — «on ne fait pas confiance à\n"
        "l'horloge, on écoute l'événement».\n\n" + "\n".join(offenders)
    )


def test_the_predicate_separates_a_writer_from_a_reader() -> None:
    """A module that only READS a cached table must not be required to purge.

    The textual version of this question reported eleven files where two wrote.
    Without this, the guard could be "fixed" back into a name search and nobody
    would see the difference until it demanded a purge from a read-only page.
    """
    import tempfile

    writer = "def f(db):\n    db.upsert_many(table='s4a_song_timeline', data=[])\n"
    reader = "def f(db):\n    return db.fetch_df('SELECT * FROM s4a_song_timeline')\n"
    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        (base / "w.py").write_text(writer, encoding="utf-8")
        (base / "r.py").write_text(reader, encoding="utf-8")
        assert _tables_written(base / "w.py") == {"s4a_song_timeline"}
        assert _tables_written(base / "r.py") == set()


def test_a_mention_in_a_comment_does_not_satisfy_the_guard() -> None:
    """The exact way the first version of this guard was green on the defect.

    Written after the mutation passed: `"clear_kpi_caches" in text` was true
    because the comment explaining the fix contained the name. The predicate now
    asks for a call, and this pins that it still does.
    """
    import tempfile

    commented = (
        "def f(db):\n"
        "    # on devrait appeler clear_kpi_caches() ici\n"
        "    db.upsert_many(table='s4a_song_timeline', data=[])\n"
    )
    calling = (
        "from src.dashboard.utils.kpi_helpers import clear_kpi_caches\n"
        "def f(db):\n"
        "    db.upsert_many(table='s4a_song_timeline', data=[])\n"
        "    clear_kpi_caches()\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        (base / "c.py").write_text(commented, encoding="utf-8")
        (base / "k.py").write_text(calling, encoding="utf-8")
        assert not _calls_purge(base / "c.py"), "a comment satisfied the guard again"
        assert _calls_purge(base / "k.py")
